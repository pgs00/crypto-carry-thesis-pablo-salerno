"""Descriptive H1/H2/H3 evaluation; missing evidence stays missing."""

from decimal import Decimal
from math import sqrt

import numpy as np
import pandas as pd

from .config import DAY, HOUR, Config, iso, timestamp


def portfolio_metrics(rows: list[dict], capital: Decimal, start: int, end: int) -> dict:
    valid_rows = sorted(
        (r for r in rows if not r.get("partial_day", False)), key=lambda r: r["time_ns"]
    )
    result = dict(
        observations=len(valid_rows),
        net_return=None,
        cagr=None,
        sharpe=None,
        annual_volatility=None,
        max_drawdown=None,
        max_drawdown_days=None,
        cagr_reason="no verified daily equity",
        sharpe_reason="no verified daily equity",
    )
    if not valid_rows or end <= start:
        return result
    equity = np.array([float(capital)] + [float(r["equity"]) for r in valid_rows])
    result["net_return"] = equity[-1] / float(capital) - 1
    years = (end - start) / DAY / 365
    if np.all(equity > 0):
        result["cagr"] = float(np.exp(np.log(equity[-1] / float(capital)) / years) - 1)
        result["cagr_reason"] = ""
    else:
        result["cagr_reason"] = "nonpositive equity or insolvency"
    peak = np.maximum.accumulate(equity)
    drawdowns = equity / peak - 1
    result["max_drawdown"] = float(drawdowns.min())
    times = [start - 1] + [int(r["time_ns"]) for r in valid_rows]
    peak_time, duration = times[0], 0.0
    for t, v, high in zip(times, equity, peak):
        if v >= high:
            peak_time = t
        else:
            duration = max(duration, (t - peak_time) / DAY)
    result["max_drawdown_days"] = duration
    if np.any(equity <= 0):
        result["sharpe_reason"] = "nonpositive equity or insolvency"
        return result
    returns = equity[1:] / equity[:-1] - 1
    if len(returns) < 2:
        result["sharpe_reason"] = "fewer than two daily returns"
        return result
    std = float(np.std(returns, ddof=1))
    result["annual_volatility"] = std * sqrt(365)
    if std == 0:
        result["sharpe_reason"] = "zero sample volatility"
    else:
        result["sharpe"] = float(np.mean(returns)) / std * sqrt(365)
        result["sharpe_reason"] = ""
    return result


def forecast_evaluation(signals: list[dict], funding: list, config: Config) -> pd.DataFrame:
    histories = {
        s: sorted((r for r in funding if r.symbol == s), key=lambda r: r.funding_time)
        for s in config.symbols
    }
    unique = {(r["symbol"], r["time_ns"]): r for r in signals}
    output = []
    for (symbol, time_ns), signal in sorted(unique.items()):
        end = time_ns + config.horizon_hours * HOUR
        history = histories[symbol]
        reason = ""
        if not signal["valid"]:
            reason = "invalid_forecast_history"
        elif end >= timestamp(config.end):
            reason = "horizon_outside_sample"
        prior = [r for r in history if r.funding_time <= time_ns]
        through = [r for r in history if time_ns < r.funding_time <= end]
        following = next((r for r in history if r.funding_time >= end), None)
        check = ([prior[-1]] if prior else []) + through
        if following is not None and (not check or check[-1].funding_time < following.funding_time):
            check.append(following)
        if not reason and (not prior or following is None):
            reason = "funding_calendar_boundary_unverified"
        if not reason:
            for previous, current in zip(check, check[1:]):
                interval = Decimal(current.funding_time - previous.funding_time) / Decimal(HOUR)
                if not current.interval_verified or current.interval_hours != interval:
                    reason = "missing_or_unverified_funding_interval"
                    break
        valid = not reason
        realized = float(sum((r.funding_rate for r in through), Decimal(0))) if valid else None
        ewma, nc = float(signal["forecast"]), float(signal["no_change"])
        output.append(
            dict(
                symbol=symbol,
                time_ns=time_ns,
                anchor=signal["anchor"],
                history_start=signal["history_start"],
                horizon_end=end,
                forecast=ewma,
                no_change=nc,
                realized=realized,
                horizon_valid=valid,
                reason=reason,
                error_ewma=ewma - realized if valid else None,
                error_no_change=nc - realized if valid else None,
                absolute_error_ewma=abs(ewma - realized) if valid else None,
                absolute_error_no_change=abs(nc - realized) if valid else None,
            )
        )
    return pd.DataFrame(
        output,
        columns=[
            "symbol",
            "time_ns",
            "anchor",
            "history_start",
            "horizon_end",
            "forecast",
            "no_change",
            "realized",
            "horizon_valid",
            "reason",
            "error_ewma",
            "error_no_change",
            "absolute_error_ewma",
            "absolute_error_no_change",
        ],
    )


def h1_summary(frame: pd.DataFrame, config: Config) -> pd.DataFrame:
    output = []
    split = timestamp("2024-01-01T00:00:00Z")
    for label, lower, upper in (
        ("full", timestamp(config.start), timestamp(config.end)),
        ("2022-2023", timestamp(config.start), split),
        ("2024+", split, timestamp(config.end)),
    ):
        group = (
            frame[(frame.time_ns >= lower) & (frame.time_ns < upper)] if not frame.empty else frame
        )
        means = []
        for symbol in config.symbols:
            subset = group[group.symbol == symbol]
            valid = subset[subset.horizon_valid.astype(bool)]
            ewma = float(valid.absolute_error_ewma.mean()) if len(valid) else None
            nc = float(valid.absolute_error_no_change.mean()) if len(valid) else None
            output.append(
                dict(
                    period=label,
                    symbol=symbol,
                    observations=len(valid),
                    excluded=len(subset) - len(valid),
                    mae_ewma=ewma,
                    mae_no_change=nc,
                )
            )
            means.append((ewma, nc))
        complete = all(x is not None and y is not None for x, y in means)
        output.append(
            dict(
                period=label,
                symbol="EQUAL_WEIGHT",
                observations=sum(r["observations"] for r in output[-2:]),
                excluded=sum(r["excluded"] for r in output[-2:]),
                mae_ewma=sum(x for x, y in means) / 2 if complete else None,
                mae_no_change=sum(y for x, y in means) / 2 if complete else None,
            )
        )
    return pd.DataFrame(output)


def daily_opportunity(rows: list[dict], config: Config) -> pd.DataFrame:
    output = []
    frame = pd.DataFrame(rows)
    if frame.empty:
        return pd.DataFrame(
            columns=["time_ns", "date", "complete", "opportunity", "eligible_fraction", "reason"]
        )
    frame["day"] = frame.time_ns // DAY
    for day, group in frame.groupby("day", sort=True):
        values = []
        counts = []
        complete = True
        for symbol in config.symbols:
            subset = group[group.symbol == symbol]
            good = (
                len(subset) == 1440 and subset.time_ns.nunique() == 1440 and subset.complete.all()
            )
            complete &= good
            values.append(pd.to_numeric(subset.value).sum() / 1440 if good else np.nan)
            counts.append(subset.eligible.astype(bool).sum() / 1440 if good else np.nan)
        output.append(
            dict(
                time_ns=int((day + 1) * DAY - 1),
                date=iso(int(day * DAY))[:10],
                complete=bool(complete),
                opportunity=float(np.mean(values)) if complete else np.nan,
                eligible_fraction=float(np.mean(counts)) if complete else np.nan,
                reason="" if complete else "missing minute, asset, or required data",
            )
        )
    return pd.DataFrame(output)


def metric_tables(backtests: list, config: Config) -> pd.DataFrame:
    output = []
    split = timestamp("2024-01-01T00:00:00Z")
    start, end = timestamp(config.start), timestamp(config.end)
    periods = [
        ("full", start, end),
        ("2022-2023", start, min(end, split)),
        ("2024+", max(start, split), end),
    ]
    for year in range(int(config.start[:4]), int(config.end[:4]) + 1):
        lower = timestamp(f"{year}-01-01T00:00:00Z")
        upper = timestamp(f"{year + 1}-01-01T00:00:00Z")
        periods.append((str(year), max(start, lower), min(end, upper)))
    for b in backtests:
        for period, lower, upper in periods:
            if lower >= upper:
                continue
            before = [r for r in b.daily if r["time_ns"] < lower]
            capital = Decimal(before[-1]["equity"]) if before else config.capital
            selected = [
                r
                for r in b.daily
                if lower <= r["time_ns"] < upper and not r.get("partial_day", False)
            ]
            observed_end = min(upper, max((r["time_ns"] + 1 for r in selected), default=lower))
            result = portfolio_metrics(selected, capital, lower, observed_end)
            result.update(
                strategy=b.strategy,
                symbol="PORTFOLIO",
                period=period,
                start=iso(lower),
                end=iso(observed_end),
                time_ns=observed_end,
                status=b.status,
                coverage_complete=(observed_end == upper and b.status in {"complete", "insolvent"}),
            )
            output.append(result)
    return pd.DataFrame(output)


def regime_comparison(opportunities: pd.DataFrame, metrics: pd.DataFrame) -> pd.DataFrame:
    split = timestamp("2024-01-01T00:00:00Z")
    output = []
    for label, side in (("2022-2023", False), ("2024+", True)):
        frame = (
            opportunities[(opportunities.time_ns >= split) == side]
            if not opportunities.empty
            else opportunities
        )
        valid = frame[frame.complete.astype(bool)] if not frame.empty else frame
        match = (
            metrics[(metrics.strategy == "conditional") & (metrics.period == label)]
            if not metrics.empty
            else metrics
        )
        cagr = float(match.iloc[0].cagr) if len(match) and pd.notna(match.iloc[0].cagr) else None
        output.append(
            dict(
                period=label,
                symbol="EQUAL_WEIGHT",
                observed_days=len(frame),
                valid_days=len(valid),
                coverage_complete=bool(
                    len(frame)
                    and len(valid) == len(frame)
                    and len(match)
                    and match.iloc[0].coverage_complete
                ),
                opportunity_mean=float(valid.opportunity.mean()) if len(valid) else None,
                eligible_fraction=float(valid.eligible_fraction.mean()) if len(valid) else None,
                conditional_cagr=cagr,
            )
        )
    a, b = output
    if any(
        not r["coverage_complete"] or r["opportunity_mean"] is None or r["conditional_cagr"] is None
        for r in output
    ):
        verdict = "no_concluyente"
    elif (
        b["opportunity_mean"] < a["opportunity_mean"]
        and b["conditional_cagr"] < a["conditional_cagr"]
    ):
        verdict = "favorable"
    elif (
        b["opportunity_mean"] > a["opportunity_mean"]
        and b["conditional_cagr"] > a["conditional_cagr"]
    ):
        verdict = "contraria"
    else:
        verdict = "mixta"
    for row in output:
        row["h3_descriptive"] = verdict
    return pd.DataFrame(output)
