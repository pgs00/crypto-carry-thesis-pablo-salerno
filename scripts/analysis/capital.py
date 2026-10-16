"""Capital attribution and decision analysis from persisted financial observations.

Financial functions are retained from the original return_capital modules.
Only read helpers required by analyze_run remain; this module writes no evidence.
"""

import csv
import json
import math
import statistics
from bisect import bisect_right
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

D = Decimal

TOLERANCE = Decimal("1E-8")


SYMBOLS = ("BTCUSDT", "ETHUSDT")


RUNS = {
    "conditional": "run_ad71d751b20623006c195ff3",
    "permanent": "run_dfea4b7ac1475668d5968c97",
}


DAY = 86_400_000_000_000


COMPONENTS = (
    "spot_realized_pnl_usdt",
    "spot_unrealized_pnl_usdt",
    "futures_realized_pnl_usdt",
    "futures_unrealized_pnl_usdt",
    "funding_usdt",
    "fees_usdt",
    "liquidation_fees_usdt",
)


def number(value, *, optional=False):
    if value in (None, "") and optional:
        return Decimal(0)
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"Invalid number {value!r}") from exc
    if not result.is_finite():
        raise ValueError(f"Nonfinite number {value!r}")
    return result


def truth(value):
    if value is True or value == "True":
        return True
    if value is False or value == "False":
        return False
    raise ValueError(f"Unknown boolean {value!r}")


def close(actual, expected, label):
    if abs(number(actual) - number(expected)) > TOLERANCE:
        raise ValueError(f"{label}: {actual} != {expected}")


def utc_ns(value):
    text = value.removesuffix("Z")
    main, _, fraction = text.partition(".")
    dt = datetime.fromisoformat(main).replace(tzinfo=UTC)
    return int(dt.timestamp()) * 1_000_000_000 + int((fraction + "000000000")[:9])


def iso(value):
    seconds, nanos = divmod(int(value), 1_000_000_000)
    return datetime.fromtimestamp(seconds, UTC).strftime("%Y-%m-%dT%H:%M:%S") + f".{nanos:09d}Z"


def read_csv(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def parquet(path):
    import pyarrow.parquet as pq

    return pq.ParquetFile(path).read().to_pylist()


def periods(metrics):
    result = []
    for row in metrics:
        item = row["period"], utc_ns(row["start_utc"]), utc_ns(row["end_exclusive_utc"])
        if item not in result:
            result.append(item)
    return result


@dataclass
class Account:
    spot: D = D(0)
    short: D = D(0)
    average: D = D(0)
    spot_cost: D = D(0)
    realized_spot: D = D(0)
    realized_futures: D = D(0)
    funding: D = D(0)
    fees: D = D(0)
    liquidation_fees: D = D(0)
    collateral: D = D(0)
    asset_cash: D = D(0)

    def apply(self, row):
        """Check actual proportional accounting and retain all original cash costs."""
        kind = row["kind"]
        if kind == "transfer":
            return
        fee = number(row.get("fee"), optional=True)
        charge = number(row.get("liquidation_fee"), optional=True)
        realized = D(0)
        if kind == "funding":
            if "short" in row:
                close(row["short"], self.short, "funding position before simultaneous fills")
            self.funding += number(row["funding"])
        else:
            q, price = number(row["quantity"]), number(row["price"])
            if q <= 0 or price <= 0:
                raise ValueError("Nonpositive fill")
            if kind == "spot_buy":
                net = q - number(row["base_fee_quantity"])
                close(number(row["base_fee_quantity"]) * price, fee, "base fee valued once")
                self.spot += net
                self.spot_cost += net * price
            elif kind == "spot_sell":
                if q > self.spot:
                    raise ValueError("Sell exceeds spot")
                allocated = self.spot_cost * q / self.spot
                realized = q * price - allocated
                self.spot -= q
                self.spot_cost -= allocated
                self.realized_spot += realized
            elif kind == "futures_sell":
                self.average = (self.short * self.average + q * price) / (self.short + q)
                self.short += q
            elif kind == "futures_buy":
                if q > self.short:
                    raise ValueError("Buy exceeds short")
                realized = q * (self.average - price)
                self.short -= q
                self.realized_futures += realized
                if not self.short:
                    self.average = D(0)
            else:
                raise ValueError(f"Unknown ledger kind {kind}")
            if row.get("pnl") is not None:
                close(realized, row["pnl"], "ledger realized P&L")
        self.fees += fee
        self.liquidation_fees += charge
        if row.get("collateral") is not None:
            self.collateral = number(row["collateral"])
        for field in ("spot", "short", "average"):
            if row.get(field) is not None:
                close(getattr(self, field), row[field], f"ledger post {field}")


def components(account, spot_price, mark):
    if account.spot and spot_price is None or account.short and mark is None:
        raise ValueError("Missing valuation price for nonzero inventory")
    values = dict(
        spot_realized_pnl_usdt=account.realized_spot,
        spot_unrealized_pnl_usdt=account.spot * number(spot_price, optional=True)
        - account.spot_cost,
        futures_realized_pnl_usdt=account.realized_futures,
        futures_unrealized_pnl_usdt=account.short * (account.average - number(mark, optional=True)),
        funding_usdt=account.funding,
        fees_usdt=-account.fees,
        liquidation_fees_usdt=-account.liquidation_fees,
    )
    values["net_pnl_usdt"] = sum((values[k] for k in COMPONENTS), D(0))
    return values


def account_history(rows, capital, symbols):
    accounts = {s: Account() for s in symbols}
    history = {s: [(-1, -1, asdict(accounts[s]))] for s in symbols}
    prior_cash, seen, previous_time = number(capital), set(), -1
    for ordinal, row in enumerate(rows):
        t, identity = int(row["time_ns"]), row["event_id"]
        if identity in seen or t < previous_time:
            raise ValueError("Duplicate or unordered ledger event")
        seen.add(identity)
        previous_time = t
        account = accounts[row["symbol"]]
        account.apply(row)
        cash = number(row["free_spot"]) + number(row["free_futures"]) - number(row["debt"])
        account.asset_cash += cash - prior_cash
        prior_cash = cash
        history[row["symbol"]].append((t, ordinal, asdict(account)))
    return history


def cycle_catalog(events, end):
    """Same original entry/open/first terminal semantics as E3 cycle_rows()."""
    grouped = defaultdict(list)
    for ordinal, row in enumerate(events):
        if row.get("cycle_id"):
            grouped[row["symbol"], row["cycle_id"]].append((ordinal, row))
    result = []
    for (symbol, cycle), rows in grouped.items():
        entries = [
            (i, r) for i, r in rows if r["kind"] == "transition" and r.get("cause") == "entry"
        ]
        if len(entries) != 1:
            raise ValueError(f"Cycle must have one entry: {cycle}")
        opened = [
            int(r["time_ns"])
            for _, r in rows
            if r["kind"] == "transition" and r.get("cause") == "opening_complete"
        ]
        closed = [
            int(r["time_ns"])
            for _, r in rows
            if r["kind"] == "transition"
            and r.get("cause") in {"ordinary_close_complete", "unwind_complete"}
            and r.get("state") in {"FLAT", "COOLDOWN"}
        ]
        entry = int(entries[0][1]["time_ns"])
        closure = min(closed) if closed else None
        result.append(
            dict(
                symbol=symbol,
                cycle_id=cycle,
                entry_ns=entry,
                opened_ns=min(opened) if opened else None,
                closed_ns=closure,
                complete=bool(opened and closed),
                failed=bool(closed and not opened),
                still_open_at_end=not closed,
                entry_risk_row=entries[0][0],
                end_ns=closure if closure is not None else end - 1,
            )
        )
    return sorted(result, key=lambda r: (r["entry_ns"], r["symbol"]))


def validate_entry_timing(cycles, ledger):
    """Entry snapshots are post-event: the frozen next-minute contract forbids fills here."""
    entries = {(c["symbol"], c["entry_ns"]): c["cycle_id"] for c in cycles}
    for row in ledger:
        key = row["symbol"], int(row["time_ns"])
        economic = row["kind"] in {"spot_buy", "spot_sell", "futures_buy", "futures_sell"} or any(
            number(row.get(field), optional=True)
            for field in ("pnl", "funding", "fee", "liquidation_fee")
        )
        if key in entries and economic:
            raise ValueError(
                f"Simultaneous economic movement at cycle entry {entries[key]}; "
                "requires an explicit pre/post entry boundary, outside this frozen next_minute_vwap contract"
            )


def segment_changes(points):
    output = []
    for before, after in zip(points, points[1:]):
        if after["time_ns"] <= before["time_ns"]:
            raise ValueError("Non-increasing attribution boundaries")
        delta = {key: value - before["values"][key] for key, value in after["values"].items()}
        output.append(
            dict(
                start_ns=before["time_ns"],
                time_ns=after["time_ns"],
                category=before["category_after"],
                cycle_id=before["cycle_after"],
                **delta,
            )
        )
    return output


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


def concentration(rows, ranks):
    pairs = [(r["identity"], number(r["net_pnl_usdt"])) for r in rows]
    if len({r[0] for r in pairs}) != len(pairs):
        raise ValueError("Duplicate concentration identity")
    gain = sum((max(p, D(0)) for _, p in pairs), D(0))
    loss = sum((max(-p, D(0)) for _, p in pairs), D(0))
    net = gain - loss
    result = []
    for sign in ("positive", "negative"):
        selected = (
            sorted(
                ((i, p) for i, p in pairs if p > 0 if sign == "positive"),
                key=lambda x: (-x[1], x[0]),
            )
            if sign == "positive"
            else sorted(((i, p) for i, p in pairs if p < 0), key=lambda x: (x[1], x[0]))
        )
        denominator = gain if sign == "positive" else loss
        for k in ranks:
            total = sum((p for _, p in selected[:k]), D(0))
            result.append(
                dict(
                    sign=sign,
                    requested_k=k,
                    effective_k=min(k, len(selected)),
                    population=len(pairs),
                    sign_population=len(selected),
                    identities=[i for i, _ in selected[:k]],
                    selected_pnl_usdt=total,
                    G_usdt=gain,
                    L_usdt=loss,
                    net_usdt=net,
                    share_sign=abs(total) / denominator if denominator else None,
                    share_net=total / net if net else None,
                    net_warning="nonpositive"
                    if net <= 0
                    else "small_relative_to_G_plus_L"
                    if net < (gain + loss) / 10
                    else "",
                )
            )
    return result


STATES = {"pass", "fail", "not_evaluable"}


def classify(row, *, validate_recorded=True, basis_max="0.005"):
    order = json.loads(row["filter_order"])
    if len(order) != len(set(order)):
        raise ValueError("Duplicate filter order")
    values = {name: row["filter_" + name] for name in order}
    if any(v not in STATES for v in values.values()):
        raise ValueError("Unknown filter state")
    enabled = truth(row["funding_filter_enabled"])
    applied = {
        name: not (name in {"funding", "funding_positive"} and not enabled)
        and not (name == "price_alignment" and not truth(row["price_alignment_enforced"]))
        for name in order
    }
    failed = [name for name in order if values[name] == "fail"]
    unknown = [name for name in order if values[name] == "not_evaluable"]
    first = next(
        (
            ("not_evaluable:" if values[n] == "not_evaluable" else "") + n
            for n in order
            if applied[n] and values[n] != "pass"
        ),
        "all_pass",
    )
    if validate_recorded:
        if (row.get("sequential_rejection") or "all_pass") != first:
            raise ValueError("Recorded sequential rejection disagrees with recorded order")
        if json.loads(row["simultaneous_rejections"]) != failed:
            raise ValueError("Recorded simultaneous failures disagree")
        if json.loads(row["simultaneous_not_evaluable"]) != unknown:
            raise ValueError("Recorded simultaneous unknowns disagree")
    funding = row["filter_funding"]
    negative, high = row["filter_basis_negative"], row["filter_basis_above_max"]
    basis = (
        "not_evaluable"
        if "not_evaluable" in (negative, high)
        else "fail"
        if "fail" in (negative, high)
        else "pass"
    )
    reason = (
        "negative"
        if negative == "fail"
        else "above_max"
        if high == "fail"
        else "unknown"
        if basis == "not_evaluable"
        else "within_inclusive_range"
    )
    if row["decision_kind"] == "renewal":
        cell = "not_applicable_renewal"
    elif "not_evaluable" in (funding, basis):
        cell = "not_evaluable"
    else:
        cell = {
            ("pass", "pass"): "both_pass",
            ("fail", "pass"): "funding_only_fail",
            ("pass", "fail"): "basis_only_fail",
            ("fail", "fail"): "both_fail",
        }[funding, basis]
    if validate_recorded and row["decision_kind"] == "entry":
        if basis != "not_evaluable":
            value = number(row["basis"])
            if (value < 0) != (negative == "fail") or (value > number(basis_max)) != (
                high == "fail"
            ):
                raise ValueError("Basis classifications disagree with inclusive bounds")
        if funding != "not_evaluable":
            expected = number(row["forecast"]) > number(row["estimated_cycle_cost"])
            if expected != (funding == "pass"):
                raise ValueError("Funding classification disagrees with forecast/cost")
    if validate_recorded and row["decision_kind"] == "renewal":
        state = row["filter_funding_positive"]
        if state != "not_evaluable" and ((number(row["forecast"]) > 0) != (state == "pass")):
            raise ValueError("Renewal must use zero funding threshold")
    return dict(
        market_cell=cell,
        basis_state=basis,
        basis_reason=reason,
        unknown_market_reasons=json.dumps(
            [
                n
                for n in ("funding", "basis_negative", "basis_above_max")
                if row["filter_" + n] == "not_evaluable"
            ]
        ),
        first_block=first,
        simultaneous_failures=json.dumps(failed),
        simultaneous_unknowns=json.dumps(unknown),
        applied_failures=json.dumps([n for n in failed if applied[n]]),
        budget_interpretation="prospective_with_prior_state"
        if row.get("filter_state_active") == "fail"
        else "prospective_no_prior_active_state",
    )


def identify(rows, source_file):
    multiplicity = Counter((r["symbol"], int(r["decision_time"]), r["decision_kind"]) for r in rows)
    seen, output = set(), []
    for ordinal, row in enumerate(rows):
        fingerprint = json.dumps(
            {k: v for k, v in row.items() if k not in {"units", "source_row", "evaluation_id"}},
            sort_keys=True,
        )
        if fingerprint in seen:
            raise ValueError("Duplicate identical evaluation")
        seen.add(fingerprint)
        if int(row["time_ns"]) != int(row["decision_time"]):
            raise ValueError("Evaluation timestamp disagrees")
        output.append(
            dict(
                row,
                source_file=source_file,
                source_row=ordinal,
                evaluation_id=f"{row['run_id']}:{source_file}:{ordinal}",
                timestamp_multiplicity=multiplicity[
                    row["symbol"], int(row["decision_time"]), row["decision_kind"]
                ],
            )
        )
    return output


def link_actions(evaluations, events, orders, fills):
    lookup = defaultdict(list)
    for row in evaluations:
        lookup[row["symbol"], int(row["decision_time"])].append(row)
    submissions = {r["order_id"]: r for r in orders if r.get("action") == "submitted"}
    result = []
    for source, rows in (
        ("risk_events.parquet", events),
        ("orders.parquet", orders),
        ("fills.parquet", fills),
    ):
        for ordinal, row in enumerate(rows):
            if source == "orders.parquet" and row.get("action") != "submitted":
                continue
            candidates = lookup[row["symbol"], int(row["time_ns"])]
            kind = (
                "renewal"
                if row.get("kind") in {"renewal", "rebalance_skipped"}
                or row.get("cause") in {"holding_expiry", "renewal_rebalance"}
                else "entry"
                if row.get("cause") == "entry"
                or row.get("purpose") == "open_spot"
                and row.get("action") == "submitted"
                else None
            )
            if kind:
                candidates = [c for c in candidates if c["decision_kind"] == kind]
            linked = candidates[0] if len(candidates) == 1 else None
            order_id = row.get("order_id") or ""
            submitted = submissions.get(order_id)
            roots = (
                lookup[row["symbol"], int(submitted["submitted_at"])]
                if submitted and submitted.get("purpose") == "open_spot"
                else []
            )
            roots = [
                c
                for c in roots
                if c["decision_kind"] == "entry" and c.get("decision") == "accepted"
            ]
            result.append(
                dict(
                    run_id=row.get("run_id", evaluations[0]["run_id"]),
                    strategy=row.get("strategy", ""),
                    symbol=row["symbol"],
                    source_file=source,
                    source_row=ordinal,
                    time_ns=int(row["time_ns"]),
                    kind=row.get("kind") or row.get("action") or "fill",
                    cause=row.get("cause") or "",
                    purpose=row.get("purpose") or "",
                    order_id=order_id,
                    fill_id=row.get("fill_id") or "",
                    cycle_id=row.get("cycle_id") or "",
                    evaluation_id=linked["evaluation_id"] if linked else "",
                    link_status="exact_time_unique"
                    if linked
                    else "unreconciled_ambiguous_time"
                    if candidates
                    else "unreconciled_no_exact_evaluation",
                    link_scope="temporal_concordance_only; causal_for_entry_transition_or_root_order",
                    accepted_entry_order_evaluation_id=roots[0]["evaluation_id"]
                    if len(roots) == 1
                    else "",
                    actual_decision=linked.get("decision") or "" if linked else "",
                )
            )
    return result


def analyze_decisions(signals, renewals, events, orders, fills, periods, basis_max):
    rows = identify(signals, "signals.parquet") + identify(renewals, "renewal_diagnostics.parquet")
    retained = {
        "run_id",
        "strategy",
        "symbol",
        "time_ns",
        "timestamp_utc",
        "decision_time",
        "decision_kind",
        "anchor",
        "forecast_anchor",
        "funding_filter_enabled",
        "price_alignment_enforced",
        "forecast",
        "estimated_cycle_cost",
        "basis",
        "basis_raw",
        "portfolio_state",
        "current_spot",
        "current_short",
        "available_cash",
        "equity_snapshot",
        "target_usdt",
        "budget_required_cash",
        "budget_reason",
        "sizing_reason",
        "prospective_sizing_reason",
        "sizing_enforcement",
        "decision",
        "actual_outcome",
        "state_after",
        "expiry_after",
        "renewal_status_kind",
        "renewal_funding_threshold",
        "source_file",
        "source_row",
        "evaluation_id",
        "timestamp_multiplicity",
        "sequential_rejection",
        "simultaneous_rejections",
        "simultaneous_not_evaluable",
    }
    classified = [
        dict(
            {k: v for k, v in row.items() if k in retained or k.startswith("filter_")},
            **classify(row, basis_max=basis_max),
        )
        for row in rows
    ]
    groups, reasons, decision_cross = summarize_decisions(
        classified, periods, rows[0]["run_id"], rows[0]["strategy"]
    )
    return dict(
        classified=classified,
        groups=groups,
        reasons=reasons,
        decision_cross=decision_cross,
        actions=link_actions(rows, events, orders, fills),
    )


def summarize_decisions(classified, periods, run_id, strategy):
    """Derive every aggregate from the declared evaluation population."""
    groups, reasons, decision_cross = [], [], []
    for period, lower, upper in periods:
        for symbol in ("BTCUSDT", "ETHUSDT", "PORTFOLIO"):
            for kind in ("entry", "renewal"):
                selected = [
                    r
                    for r in classified
                    if lower <= int(r["time_ns"]) < upper
                    and (symbol == "PORTFOLIO" or r["symbol"] == symbol)
                    and r["decision_kind"] == kind
                ]
                common = dict(
                    run_id=run_id,
                    strategy=strategy,
                    period=period,
                    start_ns=lower,
                    end_exclusive_ns=upper,
                    symbol=symbol,
                    decision_kind=kind,
                    denominator=len(selected),
                )
                for view, field in (
                    ("market", "market_cell"),
                    ("sequential", "first_block"),
                    ("actual_decision", "decision"),
                    ("basis_reason", "basis_reason"),
                ):
                    if view in {"market", "basis_reason"} and kind != "entry":
                        continue
                    counts = Counter((r.get(field) or "not_recorded") for r in selected)
                    if view == "market":
                        for name in (
                            "both_pass",
                            "funding_only_fail",
                            "basis_only_fail",
                            "both_fail",
                            "not_evaluable",
                        ):
                            counts.setdefault(name, 0)
                    for label, count in sorted(counts.items()):
                        groups.append(
                            dict(
                                **common,
                                view=view,
                                group=label,
                                count=count,
                                fraction=count / len(selected) if selected else None,
                            )
                        )
                counts = Counter()
                for row in selected:
                    for rank, name in enumerate(json.loads(row["filter_order"])):
                        applied = not (
                            name in {"funding", "funding_positive"}
                            and not truth(row["funding_filter_enabled"])
                        ) and not (
                            name == "price_alignment" and not truth(row["price_alignment_enforced"])
                        )
                        counts[rank, name, row["filter_" + name], applied] += 1
                for (rank, name, state, applied), count in sorted(counts.items()):
                    reasons.append(
                        dict(
                            **common,
                            order_position=rank,
                            filter=name,
                            state=state,
                            applied=applied,
                            count=count,
                            overlaps=True,
                            fraction=count / len(selected),
                        )
                    )
                for (first, actual), count in sorted(
                    Counter(
                        (r["first_block"], r.get("decision") or "not_recorded") for r in selected
                    ).items()
                ):
                    decision_cross.append(
                        dict(**common, first_block=first, actual_decision=actual, count=count)
                    )
    return groups, reasons, decision_cross


def paired_coverage(classified, periods):
    result = []
    for period, lower, upper in periods:
        for symbol in ("BTCUSDT", "ETHUSDT"):
            for kind in ("entry", "renewal"):
                sides = {}
                for strategy in ("conditional", "permanent"):
                    sides[strategy] = Counter(
                        int(r["decision_time"])
                        for r in classified
                        if r["strategy"] == strategy
                        and r["symbol"] == symbol
                        and r["decision_kind"] == kind
                        and lower <= int(r["decision_time"]) < upper
                    )
                a, b = sides["conditional"], sides["permanent"]
                paired = sum(1 for t in a.keys() & b.keys() if a[t] == b[t] == 1)
                result.append(
                    dict(
                        period=period,
                        symbol=symbol,
                        decision_kind=kind,
                        conditional_rows=sum(a.values()),
                        permanent_rows=sum(b.values()),
                        paired_unique=paired,
                        conditional_unpaired=sum(a.values()) - paired,
                        permanent_unpaired=sum(b.values()) - paired,
                        conditional_pair_fraction=paired / sum(a.values()) if a else None,
                        permanent_pair_fraction=paired / sum(b.values()) if b else None,
                    )
                )
    return result


def published_portfolio(rows):
    """Audit selected compact portfolio rows with the original published convention."""
    opening = D(rows[0]["starting_equity_usdt"])
    equity = [opening] + [D(r["equity_usdt"]) for r in rows]
    # Reconstruct returns from balances, not the provided daily_return column.
    returns = [float(b / a - 1) for a, b in zip(equity, equity[1:])]
    final = equity[-1]
    peak = opening
    maxdd = D(0)
    for value in equity:
        peak = max(peak, value)
        maxdd = min(maxdd, value / peak - 1)
    out = {
        "final_equity_usdt": final,
        "net_pnl_usdt": final - opening,
        "net_return": final / opening - 1,
        "cagr": math.expm1(math.log(float(final / opening)) * 365 / len(rows)),
        "sharpe": statistics.mean(returns) / statistics.stdev(returns) * math.sqrt(365)
        if statistics.stdev(returns)
        else 0,
        "max_drawdown": maxdd,
        "days": len(rows),
    }
    for field in [
        "spot_pnl_usdt",
        "futures_pnl_usdt",
        "funding_usdt",
        "fees_usdt",
        "liquidation_fees_usdt",
    ]:
        out[field] = sum((D(r[field]) for r in rows), D(0))
    out["capital_deployed_daily_mean_usdt"] = sum(
        (D(r["capital_deployed_usdt"]) for r in rows), D(0)
    ) / len(rows)
    out["capital_utilization_daily_mean"] = sum(
        (D(r["capital_deployed_usdt"]) / D(r["equity_usdt"]) for r in rows), D(0)
    ) / len(rows)
    # Accounting is checked day by day, independently of the aggregate table.
    for r in rows:
        pnl = sum(
            (
                D(r[f])
                for f in [
                    "spot_pnl_usdt",
                    "futures_pnl_usdt",
                    "funding_usdt",
                    "fees_usdt",
                    "liquidation_fees_usdt",
                ]
            ),
            D(0),
        )
        if abs(D(r["equity_usdt"]) - D(r["starting_equity_usdt"]) - pnl) > D("1e-8"):
            raise ValueError("Daily accounting mismatch " + r["date"])
    return out
