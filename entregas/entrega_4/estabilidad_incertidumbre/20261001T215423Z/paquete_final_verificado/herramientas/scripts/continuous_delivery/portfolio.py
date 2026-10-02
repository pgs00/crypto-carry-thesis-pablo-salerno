"""Accounting and exposure summaries without executing a strategy."""

from collections import defaultdict
from decimal import Decimal as D

from crypto_carry.config import DAY, SECOND, iso
from crypto_carry.evaluation import portfolio_metrics

from .common import SYMBOLS, decimal

COMPONENTS = (
    "spot_pnl_usdt",
    "futures_pnl_usdt",
    "funding_usdt",
    "fees_usdt",
    "liquidation_fees_usdt",
    "slippage_informational_usdt",
)


def financial_daily(rows, config):
    """Difference cumulative asset P&L; never restart accounting at a regime cut."""
    previous = {s: dict.fromkeys(COMPONENTS, D(0)) for s in config.symbols}
    previous_equity = config.capital
    daily, assets = [], []
    for row in sorted(rows, key=lambda r: int(r["time_ns"])):
        time_ns = int(row["time_ns"])
        common = dict(time_ns=time_ns, date=iso(time_ns)[:10])
        totals = dict.fromkeys(COMPONENTS, D(0))
        deployed, gross = D(0), D(0)
        for symbol in config.symbols:

            def value(field):
                return decimal(row.get(f"{symbol}_{field}"))

            spot_value = value("spot") * value("spot_price")
            unrealized_spot = spot_value - value("spot_cost") if value("spot") else D(0)
            unrealized_future = value("short") * (value("average") - value("mark"))
            cumulative = dict(
                zip(
                    COMPONENTS,
                    (
                        value("realized_spot") + unrealized_spot,
                        value("realized_futures") + unrealized_future,
                        value("funding"),
                        -value("fees"),
                        -value("liquidation_fees"),
                        value("slippage"),
                    ),
                )
            )
            changes = {k: cumulative[k] - previous[symbol][k] for k in COMPONENTS}
            assets.append(
                dict(
                    common,
                    symbol=symbol,
                    **changes,
                    net_pnl_usdt=sum((changes[k] for k in COMPONENTS[:-1]), D(0)),
                )
            )
            previous[symbol] = cumulative
            for key in totals:
                totals[key] += changes[key]
            deployed += spot_value + value("collateral")
            gross += spot_value + value("short") * value("mark")
        equity = decimal(row["equity"])
        pnl = equity - previous_equity
        residual = pnl - sum((totals[k] for k in COMPONENTS[:-1]), D(0))
        if abs(residual) > config.accounting_tolerance:
            raise ValueError(f"Daily P&L does not reconcile at {common['date']}: {residual}")
        daily.append(
            dict(
                common,
                equity_usdt=equity,
                starting_equity_usdt=previous_equity,
                daily_return=equity / previous_equity - 1 if previous_equity > 0 else None,
                net_pnl_usdt=pnl,
                **totals,
                reconciliation_residual_usdt=residual,
                capital_deployed_usdt=deployed,
                capital_utilization=deployed / equity if equity > 0 else None,
                gross_exposure_usdt=gross,
                free_cash_usdt=decimal(row.get("free_spot")) + decimal(row.get("free_futures")),
                debt_usdt=decimal(row.get("debt")),
            )
        )
        previous_equity = equity
    return daily, assets


def period_financials(daily, assets, config, periods):
    output = []
    for period, start, end in periods:
        selected = [r for r in daily if start <= r["time_ns"] < end]
        if not selected:
            raise ValueError(f"Empty financial period: {period}")
        if len(selected) != (end - start) // DAY:
            raise ValueError(f"Incomplete daily financial period: {period}")
        opening = selected[0]["starting_equity_usdt"]
        metric = portfolio_metrics(
            [dict(time_ns=r["time_ns"], equity=r["equity_usdt"]) for r in selected],
            opening,
            start,
            end,
        )
        total = {key: sum((r[key] for r in selected), D(0)) for key in COMPONENTS}
        output.append(
            dict(
                period=period,
                start_utc=iso(start),
                end_exclusive_utc=iso(end),
                days=len(selected),
                starting_equity_usdt=opening,
                final_equity_usdt=selected[-1]["equity_usdt"],
                net_pnl_usdt=selected[-1]["equity_usdt"] - opening,
                **total,
                **metric,
                capital_deployed_daily_mean_usdt=sum(
                    (r["capital_deployed_usdt"] for r in selected), D(0)
                )
                / len(selected),
                capital_deployed_daily_max_usdt=max(r["capital_deployed_usdt"] for r in selected),
                capital_utilization_daily_mean=sum(
                    (r["capital_utilization"] for r in selected), D(0)
                )
                / len(selected),
                capital_utilization_daily_max=max(r["capital_utilization"] for r in selected),
            )
        )
    return output


def exposure_intervals(rows, start, end, tolerance, symbols=SYMBOLS):
    """Keep the last state at each timestamp and classify dust separately."""
    output = []
    for symbol in symbols:
        values = {start: dict(symbol=symbol, spot="0", short="0", state="FLAT")}
        for row in sorted(rows, key=lambda r: int(r["time_ns"])):
            if row["symbol"] == symbol and int(row["time_ns"]) < end:
                values[max(start, int(row["time_ns"]))] = row
        times = sorted(values)
        known_dust = D(0)
        for i, lower in enumerate(times):
            row = values[lower]
            upper = times[i + 1] if i + 1 < len(times) else end
            spot, short = decimal(row.get("spot")), decimal(row.get("short"))
            dust = (
                spot > 0
                and short == 0
                and (
                    decimal(row.get("dust_spot")) > 0
                    or row.get("state") in {"FLAT", "COOLDOWN"}
                    or spot <= known_dust
                )
            )
            if dust:
                exposure, known_dust = "dust", spot
            elif spot > 0 and short > 0 and abs(spot - short) / spot <= tolerance:
                exposure = "covered"
            elif spot > 0 or short > 0:
                exposure = "unhedged"
            else:
                exposure = "flat"
            item = dict(
                symbol=symbol,
                start_ns=lower,
                end_ns=upper,
                start_utc=iso(lower),
                end_exclusive_utc=iso(upper),
                seconds=D(upper - lower) / SECOND,
                exposure=exposure,
                spot=spot,
                short=short,
                state=row.get("state"),
                collateral_usdt=decimal(row.get("collateral")),
            )
            if upper > lower:
                output.append(item)
    return sorted(output, key=lambda r: (r["start_ns"], r["symbol"]))


def exposure_summary(intervals, periods):
    output = []
    for period, start, end in periods:
        groups = defaultdict(lambda: defaultdict(lambda: D(0)))
        endpoints = {start, end}
        for row in intervals:
            lo, hi = max(start, row["start_ns"]), min(end, row["end_ns"])
            if lo < hi:
                groups[row["symbol"]][row["exposure"]] += D(hi - lo) / SECOND
                endpoints.update((lo, hi))
        for symbol, durations in groups.items():
            output.append(
                dict(
                    period=period,
                    symbol=symbol,
                    **{
                        f"{k}_seconds": durations[k]
                        for k in ("covered", "unhedged", "dust", "flat")
                    },
                    invested_seconds=durations["covered"] + durations["unhedged"],
                    calendar_seconds=D(end - start) / SECOND,
                )
            )
        totals = defaultdict(lambda: D(0))
        by_symbol = {
            s: sorted((r for r in intervals if r["symbol"] == s), key=lambda r: r["start_ns"])
            for s in SYMBOLS
        }
        pointers = dict.fromkeys(SYMBOLS, 0)
        times = sorted(endpoints)
        for lo, hi in zip(times, times[1:]):
            states = []
            for symbol, rows in by_symbol.items():
                while pointers[symbol] + 1 < len(rows) and rows[pointers[symbol]]["end_ns"] <= lo:
                    pointers[symbol] += 1
                states.append(rows[pointers[symbol]]["exposure"] if rows else "flat")
            seconds = D(hi - lo) / SECOND
            totals["invested_seconds"] += seconds * any(
                s in {"covered", "unhedged"} for s in states
            )
            totals["any_unhedged_seconds"] += seconds * ("unhedged" in states)
            totals["any_covered_seconds"] += seconds * ("covered" in states)
            totals["both_covered_seconds"] += seconds * all(s == "covered" for s in states)
            totals["cash_or_dust_seconds"] += seconds * all(s in {"flat", "dust"} for s in states)
        output.append(
            dict(
                period=period,
                symbol="PORTFOLIO",
                **totals,
                calendar_seconds=D(end - start) / SECOND,
            )
        )
    return output


def cycle_rows(events, end):
    grouped = defaultdict(list)
    for event in events:
        if event.get("cycle_id"):
            grouped[(event["symbol"], event["cycle_id"])].append(event)
    output = []
    for (symbol, cycle_id), rows in grouped.items():
        entered = [
            int(r["time_ns"])
            for r in rows
            if r.get("kind") == "transition" and r.get("cause") == "entry"
        ]
        opened = [
            int(r["time_ns"])
            for r in rows
            if r.get("kind") == "transition" and r.get("cause") == "opening_complete"
        ]
        closed = [
            int(r["time_ns"])
            for r in rows
            if r.get("kind") == "transition"
            and r.get("cause") in {"ordinary_close_complete", "unwind_complete"}
            and r.get("state") in {"FLAT", "COOLDOWN"}
        ]
        output.append(
            dict(
                symbol=symbol,
                cycle_id=cycle_id,
                entry_ns=min(entered) if entered else None,
                opened_ns=min(opened) if opened else None,
                closed_ns=min(closed) if closed else None,
                complete=bool(opened and closed),
                failed=bool(closed and not opened),
                still_open_at_end=bool(not closed),
                close_causes=sorted(
                    {
                        r["cause"]
                        for r in events
                        if r.get("kind") == "close_requested"
                        and r["symbol"] == symbol
                        and (min(entered) if entered else min(int(v["time_ns"]) for v in rows))
                        <= int(r["time_ns"])
                        <= (min(closed) if closed else end)
                    }
                ),
            )
        )
    for row in output:
        for field in ("entry", "opened", "closed"):
            row[f"{field}_utc"] = (
                iso(row[f"{field}_ns"]) if row[f"{field}_ns"] is not None else None
            )
    return output


def activity_summary(fills, orders, risks, cycles, periods):
    output = []
    for period, start, end in periods:
        for symbol in (*SYMBOLS, "PORTFOLIO"):

            def selected(row):
                return start <= int(row["time_ns"]) < end and (
                    symbol == "PORTFOLIO" or row["symbol"] == symbol
                )

            f = [r for r in fills if selected(r)]
            e = [r for r in risks if selected(r)]
            o = [r for r in orders if r.get("record_type") == "event" and selected(r)]
            c = [r for r in cycles if symbol == "PORTFOLIO" or r["symbol"] == symbol]

            def inside(value):
                return value is not None and start <= value < end

            output.append(
                dict(
                    period=period,
                    symbol=symbol,
                    orders_submitted=len(
                        {r["order_id"] for r in o if r.get("action") == "submitted"}
                    ),
                    fills=len(f),
                    partial_fills=sum(str(r.get("partial")).lower() == "true" for r in f),
                    opening_attempts=sum(inside(r["entry_ns"]) for r in c),
                    completed_openings=sum(inside(r["opened_ns"]) for r in c),
                    completed_cycles=sum(r["complete"] and inside(r["closed_ns"]) for r in c),
                    failed_cycles=sum(r["failed"] and inside(r["closed_ns"]) for r in c),
                    close_requests=sum(r.get("kind") == "close_requested" for r in e),
                    execution_failure_events=sum(r.get("kind") == "attempt_failed" for r in e),
                    failed_order_ids=len(
                        {
                            r["order_id"]
                            for r in e
                            if r.get("kind") == "attempt_failed" and r.get("order_id")
                        }
                    ),
                    renewals=sum(r.get("kind") == "renewal" for r in e),
                    rebalances=sum(
                        r.get("kind") == "transition" and r.get("state") == "REBALANCING" for r in e
                    ),
                    corrections=sum(
                        r.get("kind") == "transition" and r.get("state") == "CORRECTING_HEDGE"
                        for r in e
                    ),
                    liquidation_fills=sum(str(r.get("liquidation")).lower() == "true" for r in f),
                    turnover_usdt=sum(
                        (decimal(r["quantity"]) * decimal(r["price"]) for r in f), D(0)
                    ),
                )
            )
    return output
