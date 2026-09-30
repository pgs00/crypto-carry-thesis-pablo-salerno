"""Align a separate gross account with unchanged, persisted carry summaries."""

from datetime import date
from decimal import localcontext

from scripts.return_capital.common import RUNS, number, truth, utc_ns

from .accrual import period_summary

CAPITAL_FIELDS = (
    "capital_deployed_usdt_daily_mean",
    "capital_deployed_usdt_daily_max",
    "capital_utilization_daily_mean",
    "capital_utilization_daily_max",
    "invested_fraction",
)


def window(row):
    start, end = [date.fromisoformat(row[k][:10]) for k in ("start_utc", "end_exclusive_utc")]
    if any(
        utc_ns(row[k]) != utc_ns(str(d) + "T00:00:00Z")
        for k, d in (("start_utc", start), ("end_exclusive_utc", end))
    ):
        raise ValueError("Period must use exact UTC midnight boundaries")
    if int(row["days"]) != (end - start).days or not truth(row["coverage_complete"]):
        raise ValueError("Invalid persisted period coverage")
    return start, end


def compare_periods(daily, metrics):
    known, periods = {}, {}
    for row in metrics:
        strategy, period = row["strategy"], row["period"]
        if strategy not in RUNS or row["run_id"] != RUNS[strategy] or row["scenario"] != "BASE_E3":
            raise ValueError("Unapproved carry run or scenario")
        key = strategy, period
        if key in known:
            raise ValueError("Duplicate persisted period")
        known[key] = row
        boundaries = window(row)
        if period in periods and periods[period] != boundaries:
            raise ValueError("Carry strategies have different period boundaries")
        periods[period] = boundaries
    if not periods or set(known) != {(s, p) for s in RUNS for p in periods}:
        raise ValueError("Comparison requires both original carry strategies")
    result, differences = [], []
    with localcontext(prec=50):
        for period, (start, end) in periods.items():
            summary = period_summary(daily, start, end)
            metadata = dict(
                period=period,
                start_utc=summary["start_utc"],
                end_exclusive_utc=summary["end_exclusive_utc"],
                days=summary["days"],
                cagr_day_basis=365,
                nominal_USDT_USD_parity="1",
            )
            benchmark = dict(
                **metadata,
                portfolio="sofr",
                run_id="",
                currency="USD",
                cost_basis="hypothetical_gross",
                opening_balance=summary["equity_start"],
                closing_balance=summary["equity_end"],
                pnl=summary["pnl_usd"],
                net_return=summary["net_return"],
                cagr365=summary["cagr"],
                accrual_day_basis=360,
                sharpe_rf0_carry="",
                sharpe_reason="not_calculated_for_benchmark",
                **{k: "" for k in CAPITAL_FIELDS},
            )
            for strategy in RUNS:
                source = known[strategy, period]
                result.append(
                    dict(
                        **metadata,
                        portfolio=strategy,
                        run_id=source["run_id"],
                        currency="USDT",
                        cost_basis="net_modeled_costs",
                        opening_balance=source["starting_equity_usdt"],
                        closing_balance=source["final_equity_usdt"],
                        pnl=source["net_pnl_usdt"],
                        net_return=source["net_return"],
                        cagr365=source["cagr"],
                        accrual_day_basis="",
                        sharpe_rf0_carry=source["sharpe"],
                        sharpe_reason=source["sharpe_reason"],
                        **{k: source.get(k, "") for k in CAPITAL_FIELDS},
                    )
                )
                differences.append(
                    dict(
                        **metadata,
                        carry_strategy=strategy,
                        carry_run_id=source["run_id"],
                        comparison="carry_net_modeled_minus_sofr_hypothetical_gross",
                        pnl_carry_minus_sofr_nominal=number(source["net_pnl_usdt"])
                        - summary["pnl_usd"],
                        return_difference_pp=100
                        * (number(source["net_return"]) - summary["net_return"]),
                        cagr365_difference_pp=100 * (number(source["cagr"]) - summary["cagr"]),
                    )
                )
            result.append(benchmark)
    return result, differences


def align_daily(daily, carry):
    if not daily or len({r["date"] for r in daily}) != len(daily):
        raise ValueError("Missing or duplicate SOFR daily observations")
    mapping = {(r["strategy"], r["date"]): r for r in carry}
    if len(mapping) != len(carry) or set(mapping) != {(s, r["date"]) for s in RUNS for r in daily}:
        raise ValueError("Carry daily population does not match SOFR")
    first = daily[0]
    initial = dict(
        date=first["date"],
        boundary_utc=first["date"] + "T00:00:00Z",
        carry_close_time_ns="",
        observation="initial",
        sofr_usd=first["balance_open"],
    )
    initial.update({s + "_usdt": mapping[s, first["date"]]["starting_equity_usdt"] for s in RUNS})
    result = [initial]
    for row in daily:
        aligned = dict(
            date=row["date"],
            boundary_utc=row["benchmark_boundary_utc"],
            carry_close_time_ns=row["carry_close_time_ns"],
            observation="daily_close",
            sofr_usd=row["balance_close"],
        )
        for strategy in RUNS:
            source = mapping[strategy, row["date"]]
            if source["run_id"] != RUNS[strategy] or int(source["time_ns"]) != int(
                row["carry_close_time_ns"]
            ):
                raise ValueError("Carry daily run or timestamp mismatch")
            aligned[strategy + "_usdt"] = source["equity_usdt"]
        result.append(aligned)
    return result
