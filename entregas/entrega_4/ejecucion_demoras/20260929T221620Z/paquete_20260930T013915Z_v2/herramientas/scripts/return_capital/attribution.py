"""Daily and cycle attribution with explicit boundary prices and residual inventory."""

from bisect import bisect_right
from collections import defaultdict
from decimal import Decimal as D

from .accounting import (
    Account,
    account_history,
    components,
    cycle_catalog,
    segment_changes,
    validate_entry_timing,
)
from .common import COMPONENTS, SYMBOLS, close, iso, number, parquet, read_csv


def analyze_run(run_path, compact, periods, source_daily, capital="10000"):
    ledger = parquet(run_path / "ledger.parquet")
    events = parquet(run_path / "risk_events.parquet")
    fills = parquet(run_path / "fills.parquet")
    signals = parquet(run_path / "signals.parquet")
    positions = parquet(run_path / "positions.parquet")
    daily = read_csv(run_path / "equity_daily.csv")
    start, end = min(p[1] for p in periods), max(p[2] for p in periods)
    cycles = cycle_catalog(events, end)
    validate_entry_timing(cycles, ledger)
    run_id, strategy = daily[0]["run_id"], daily[0]["strategy"]
    identity = dict(run_id=run_id, strategy=strategy)
    history = account_history(ledger, capital, SYMBOLS)
    prices = {}
    for ordinal, row in enumerate(compact):
        if row["run_id"] != run_id:
            continue
        key = int(row["time_ns"])
        candidate = {s: row[f"{s}_spot_price"] for s in SYMBOLS}
        if key in prices and candidate != prices[key][0]:
            raise ValueError("Conflicting compact prices at the same instant")
        prices[key] = candidate, ordinal
    signal_keys = defaultdict(list)
    for ordinal, row in enumerate(signals):
        signal_keys[row["symbol"], int(row["time_ns"])].append((ordinal, row))
    daily_keys = {int(row["time_ns"]): (i, row) for i, row in enumerate(daily)}
    if len(daily_keys) != len(daily):
        raise ValueError("Duplicate financial day")
    boundaries, segments, checks = [], [], []
    source_assets = {}
    for symbol in SYMBOLS:
        states = history[symbol]
        state_times = [r[0] for r in states]
        selected_cycles = [c for c in cycles if c["symbol"] == symbol]
        entries = {c["entry_ns"]: c for c in selected_cycles}
        closures = {c["closed_ns"]: c for c in selected_cycles if c["closed_ns"] is not None}
        times = sorted({start, *daily_keys, *entries, *closures})
        active = None
        points = []
        for t in times:
            _, ledger_ordinal, state = states[bisect_right(state_times, t) - 1]
            account = Account(**state)
            source, source_row, price, mark = "initial", "", None, None
            if t in daily_keys:
                source_row, row = daily_keys[t]
                source = "equity_daily.csv"
                price, mark = row[f"{symbol}_spot_price"], row[f"{symbol}_mark"]
                for key in (
                    "spot",
                    "short",
                    "average",
                    "spot_cost",
                    "realized_spot",
                    "realized_futures",
                    "funding",
                    "fees",
                    "liquidation_fees",
                    "collateral",
                ):
                    close(
                        getattr(account, key),
                        row[f"{symbol}_{key}"],
                        f"{run_id}/{symbol}/{t}/{key}",
                    )
                original = Account(
                    **{
                        key: number(row[f"{symbol}_{key}"])
                        for key in (
                            "spot",
                            "short",
                            "average",
                            "spot_cost",
                            "realized_spot",
                            "realized_futures",
                            "funding",
                            "fees",
                            "liquidation_fees",
                            "collateral",
                        )
                    }
                )
                source_assets[symbol, t] = components(original, price, mark)
            elif t in entries:
                matches = signal_keys[symbol, t]
                if len(matches) != 1 or matches[0][1]["decision"] != "accepted":
                    raise ValueError("Entry has no unique accepted evaluation")
                source_row, row = matches[0]
                source, price, mark = "signals.parquet", row["spot_price"], row["mark_price"]
            elif t in closures:
                if account.short:
                    raise ValueError("Terminal cycle still has a short")
                if t in prices:
                    source = "intraday/evidencia/eventos_financieros.parquet"
                    price, source_row = prices[t][0][symbol], prices[t][1]
                elif account.spot:
                    raise ValueError(f"Missing exact cycle-close valuation {symbol}/{t}")
                else:
                    source = "zero_inventory_no_price_required"
            values = components(account, price, mark)
            cash_value = (
                account.asset_cash
                + account.collateral
                + account.spot * number(price, optional=True)
                + account.short * (account.average - number(mark, optional=True))
            )
            close(values["net_pnl_usdt"], cash_value, "asset cash/inventory identity")
            if t in closures:
                if active != closures[t]["cycle_id"]:
                    raise ValueError("Cycle closure out of sequence")
                active = None
            if t in entries:
                if active:
                    raise ValueError("Overlapping cycles for one asset")
                active = entries[t]["cycle_id"]
            category = "cycle" if active else "outside_dust" if account.spot else "outside_flat"
            point = dict(
                time_ns=t, category_after=category, cycle_after=active or "", values=values
            )
            points.append(point)
            boundaries.append(
                dict(
                    **identity,
                    symbol=symbol,
                    time_ns=t,
                    timestamp_utc=iso(t),
                    boundary_source=source,
                    source_row=source_row,
                    ledger_row=ledger_ordinal,
                    spot_price=price,
                    mark_price=mark,
                    **state,
                    **values,
                    category_after=category,
                    cycle_after=active or "",
                )
            )
        for change in segment_changes(points):
            segments.append(
                dict(**identity, symbol=symbol, date=iso(change["time_ns"])[:10], **change)
            )
    # Validate every persisted position snapshot against the ledger sequence; ties
    # may represent pre/post states, so require an exact matching state at that time.
    for ordinal, row in enumerate(positions):
        wanted = (number(row["spot"]), number(row["short"]))
        # The latest snapshot can precede a later same-time ledger event.
        same = [s for t, _, s in history[row["symbol"]] if t == int(row["time_ns"])]
        before = [s for t, _, s in history[row["symbol"]] if t < int(row["time_ns"])]
        candidates = same + before[-1:]
        if not any((s["spot"], s["short"]) == wanted for s in candidates):
            raise ValueError(f"Position snapshot not linked to ledger: {ordinal}")
    aggregate = defaultdict(lambda: defaultdict(D))
    for row in segments:
        for field in (*COMPONENTS, "net_pnl_usdt"):
            aggregate[row["date"]][field] += row[field]
    for row in source_daily:
        if row["run_id"] != run_id:
            continue
        calculated = aggregate[row["date"]]
        for field in (*COMPONENTS, "net_pnl_usdt"):
            close(calculated[field], row[field], f"daily attribution/{row['date']}/{field}")
        checks.append(
            dict(
                **identity,
                scope="portfolio_day",
                period=row["date"],
                attributed_usdt=calculated["net_pnl_usdt"],
                source_usdt=row["net_pnl_usdt"],
                residual_usdt=calculated["net_pnl_usdt"] - number(row["net_pnl_usdt"]),
            )
        )
    movements = []
    fill_lookup = {"fill:" + f["fill_id"]: f for f in fills}
    for ordinal, row in enumerate(ledger):
        t = int(row["time_ns"])
        matched = [
            c for c in cycles if c["symbol"] == row["symbol"] and c["entry_ns"] <= t <= c["end_ns"]
        ]
        if len(matched) > 1:
            raise ValueError("Ambiguous cycle for financial movement")
        cycle = matched[0]["cycle_id"] if matched else ""
        fill = fill_lookup.get(row["event_id"], {})
        movements.append(
            dict(
                **identity,
                symbol=row["symbol"],
                ledger_row=ordinal,
                time_ns=t,
                event_id=row["event_id"],
                kind=row["kind"],
                cycle_id=cycle,
                assignment="cycle_interval_and_order"
                if cycle and fill
                else "cycle_pre_fill_funding"
                if cycle
                else "outside_cycle",
                order_id=fill.get("order_id", ""),
                fill_id=fill.get("fill_id", ""),
                trade_id=fill.get("trade_id", ""),
                quantity=row.get("quantity"),
                price=row.get("price"),
                realized_pnl_usdt=row.get("pnl"),
                funding_usdt=row.get("funding"),
                fee_usdt=row.get("fee"),
                liquidation_fee_usdt=row.get("liquidation_fee"),
            )
        )
    for cycle in cycles:
        own = [m for m in movements if m["cycle_id"] == cycle["cycle_id"]]
        own_fills = [m for m in own if m["fill_id"]]
        cycle.update(
            **identity,
            fills=len(own_fills),
            orders_with_fills=len({m["order_id"] for m in own_fills}),
            status="open_at_end"
            if cycle["still_open_at_end"]
            else "closed"
            if cycle["complete"]
            else "incomplete_opening"
            if own_fills
            else "attempt_without_fill",
            entry_utc=iso(cycle["entry_ns"]),
            closed_utc=iso(cycle["closed_ns"]) if cycle["closed_ns"] is not None else "",
        )
        for field in (*COMPONENTS, "net_pnl_usdt"):
            cycle[field] = sum(
                (s[field] for s in segments if s["cycle_id"] == cycle["cycle_id"]), D(0)
            )
    contributions = []
    for period, lower, upper in periods:
        selected = [s for s in segments if lower <= s["time_ns"] < upper]
        for symbol in SYMBOLS:
            groups = defaultdict(list)
            for row in selected:
                if row["symbol"] == symbol:
                    groups[row["category"], row["cycle_id"]].append(row)
            for (category, cycle_id), rows in sorted(groups.items()):
                values = {f: sum((r[f] for r in rows), D(0)) for f in (*COMPONENTS, "net_pnl_usdt")}
                contributions.append(
                    dict(
                        **identity,
                        period=period,
                        start_ns=lower,
                        end_exclusive_ns=upper,
                        symbol=symbol,
                        category=category,
                        cycle_id=cycle_id,
                        segments=len(rows),
                        **values,
                    )
                )
            zero = dict.fromkeys((*COMPONENTS, "net_pnl_usdt"), D(0))
            beginning = source_assets.get((symbol, lower - 1), zero)
            ending = source_assets[symbol, upper - 1]
            for field in (*COMPONENTS, "net_pnl_usdt"):
                attributed = sum((r[field] for r in selected if r["symbol"] == symbol), D(0))
                source = ending[field] - beginning[field]
                close(attributed, source, f"asset period/{symbol}/{period}/{field}")
                checks.append(
                    dict(
                        **identity,
                        scope="asset_period",
                        symbol=symbol,
                        period=period,
                        field=field,
                        attributed_usdt=attributed,
                        source_usdt=source,
                        residual_usdt=attributed - source,
                    )
                )
    return dict(
        cycles=cycles,
        contributions=contributions,
        segments=segments,
        boundaries=boundaries,
        movements=movements,
        checks=checks,
    )
