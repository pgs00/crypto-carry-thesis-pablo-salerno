"""Shared calculations over retained observations; no market replay or build state.

The period formulas are unchanged from verify_rules_sensitivity_package.py.
"""

from __future__ import annotations

import csv
import math
import re
from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal as D
from decimal import InvalidOperation, localcontext
from pathlib import Path

SECOND = 1_000_000_000

DAY = 86_400 * SECOND

SYMBOLS = ("BTCUSDT", "ETHUSDT")

TOLERANCE = D("1E-8")

COMPONENTS = (
    "spot_pnl_usdt",
    "futures_pnl_usdt",
    "funding_usdt",
    "fees_usdt",
    "liquidation_fees_usdt",
    "slippage_informational_usdt",
)

SPLIT_COMPONENTS = (
    "spot_realized_pnl_usdt",
    "spot_unrealized_pnl_usdt",
    "futures_realized_pnl_usdt",
    "futures_unrealized_pnl_usdt",
)


def decimal(value, field="number"):
    if value is None or value == "" or isinstance(value, bool):
        raise ValueError(f"Missing or invalid decimal: {field}")
    try:
        number = D(str(value))
    except InvalidOperation as exc:
        raise ValueError(f"Invalid decimal: {field}={value!r}") from exc
    if not number.is_finite():
        raise ValueError(f"Nonfinite decimal: {field}={value!r}")
    return number


def yes(value):
    if value in (True, "True", "true", "1", 1):
        return True
    if value in (False, "False", "false", "0", 0):
        return False
    raise ValueError(f"Invalid boolean: {value!r}")


def timestamp(value):
    match = re.fullmatch(r"(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)(?:\.(\d{1,9}))?Z", value)
    if not match:
        raise ValueError(f"Expected exact UTC timestamp: {value!r}")
    date = datetime.fromisoformat(match[1]).replace(tzinfo=UTC)
    seconds = int((date - datetime(1970, 1, 1, tzinfo=UTC)).total_seconds())
    return seconds * SECOND + int((match[2] or "").ljust(9, "0"))


def iso(value):
    seconds, fraction = divmod(int(value), SECOND)
    return datetime.fromtimestamp(seconds, UTC).strftime("%Y-%m-%dT%H:%M:%S") + f".{fraction:09d}Z"


def periods(config):
    start, end = timestamp(config["start"]), timestamp(config["end"])
    if start >= end or start % DAY or end % DAY:
        raise ValueError("Report requires a positive interval bounded by UTC midnights")
    split = timestamp("2024-01-01T00:00:00Z")
    candidates = [
        ("full", start, end),
        ("2022-2023", start, min(end, split)),
        ("2024+", max(start, split), end),
    ]
    for year in range(int(config["start"][:4]), int(config["end"][:4]) + 1):
        candidates.append(
            (
                str(year),
                max(start, timestamp(f"{year}-01-01T00:00:00Z")),
                min(end, timestamp(f"{year + 1}-01-01T00:00:00Z")),
            )
        )
    return [(name, lower, upper) for name, lower, upper in candidates if lower < upper]


def period_financials(daily, periods):
    output = []
    for label, start, end in periods:
        selected = [r for r in daily if start <= r["time_ns"] < end]
        expected = list(range(start + DAY - 1, end, DAY))
        if (
            [r["time_ns"] for r in selected] != expected
            or any(r["partial_day"] for r in selected)
            or not selected
        ):
            raise ValueError(f"Incomplete daily coverage: {label}")
        opening, final = selected[0]["starting_equity_usdt"], selected[-1]["equity_usdt"]
        equities = [opening] + [r["equity_usdt"] for r in selected]
        returns = [r["daily_return"] for r in selected]
        positive = all(equity > 0 for equity in equities)
        reason = "" if positive else "nonpositive equity or insolvency"
        cagr = (
            math.expm1(math.log(float(final / opening)) * 365 * DAY / (end - start))
            if positive
            else None
        )
        sharpe = volatility = None
        if positive:
            if len(returns) < 2:
                reason = "fewer than two daily returns"
            else:
                mean = sum(returns, D(0)) / len(returns)
                variance = sum(((x - mean) ** 2 for x in returns), D(0)) / (len(returns) - 1)
                volatility = math.sqrt(float(variance) * 365)
                if variance == 0:
                    reason = "zero sample volatility"
                else:
                    sharpe = float(mean) / math.sqrt(float(variance)) * math.sqrt(365)
        peak, peak_time, drawdown, duration = opening, start - 1, D(0), D(0)
        for row in selected:
            value, moment = row["equity_usdt"], row["time_ns"]
            if value >= peak:
                peak, peak_time = value, moment
            elif peak > 0:
                drawdown = min(drawdown, value / peak - 1)
                duration = max(duration, D(moment - peak_time) / DAY)
        row = dict(
            period=label,
            start_utc=iso(start),
            end_exclusive_utc=iso(end),
            days=len(selected),
            coverage_complete=True,
            starting_equity_usdt=opening,
            final_equity_usdt=final,
            net_pnl_usdt=final - opening,
            net_return=final / opening - 1 if opening > 0 else None,
            cagr=cagr,
            cagr_reason="" if positive else "nonpositive equity or insolvency",
            sharpe=sharpe,
            sharpe_reason=reason,
            annual_volatility=volatility,
            max_drawdown=drawdown if opening > 0 else None,
            max_drawdown_days=duration,
        )
        for key in (*COMPONENTS, *SPLIT_COMPONENTS):
            row[key] = sum((r[key] for r in selected), D(0))
        row["reconciliation_residual_usdt"] = row["net_pnl_usdt"] - sum(
            (row[key] for key in COMPONENTS[:-1]), D(0)
        )
        for key in (
            "capital_deployed_usdt",
            "capital_utilization",
            "gross_exposure_usdt",
            "collateral_usdt",
            "debt_usdt",
        ):
            values = [r[key] for r in selected]
            row[f"{key}_daily_mean"] = (
                sum(values, D(0)) / len(values) if None not in values else None
            )
            row[f"{key}_daily_max"] = max(values) if None not in values else None
        output.append(row)
    return output


def read_rows(path):
    """Read one retained representation, including lossless string Parquet."""
    path = Path(path)
    if path.suffix == ".parquet":
        import pyarrow.parquet as pq

        return pq.ParquetFile(path).read().to_pylist()
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def daily_observations(rows):
    """Reconstruct returns and utilization from balances, then reconcile each day."""
    output = []
    money = (
        *COMPONENTS,
        *SPLIT_COMPONENTS,
        "equity_usdt",
        "starting_equity_usdt",
        "capital_deployed_usdt",
        "gross_exposure_usdt",
        "collateral_usdt",
        "debt_usdt",
    )
    previous = None
    with localcontext() as context:
        context.prec = 50
        for source in sorted(rows, key=lambda row: int(row["time_ns"])):
            row = dict(source)
            row.update({key: decimal(source[key], key) for key in money})
            row["time_ns"] = int(source["time_ns"])
            row["partial_day"] = yes(source["partial_day"])
            opening, equity = row["starting_equity_usdt"], row["equity_usdt"]
            if previous is not None and opening != previous:
                raise ValueError("Daily balance discontinuity: " + row["date"])
            row["net_pnl_usdt"] = equity - opening
            row["daily_return"] = equity / opening - 1 if opening > 0 else None
            row["capital_utilization"] = (
                row["capital_deployed_usdt"] / equity if equity > 0 else None
            )
            residual = row["net_pnl_usdt"] - sum((row[k] for k in COMPONENTS[:-1]), D(0))
            if abs(residual) > TOLERANCE:
                raise ValueError("Daily accounting does not reconcile: " + row["date"])
            output.append(row)
            previous = equity
    return output


def scenario_metrics(root, topic, scenarios, *, folder="tablas", summarize=None):
    """One runner for declarative scenario matrices; never invokes a backtest."""
    source = Path(root) / "results" / topic / "evidencia" / folder / "diario.csv"
    if not source.is_file():
        source = source.with_suffix(".parquet")
    grouped = defaultdict(list)
    for row in read_rows(source):
        grouped[(row["scenario"], row["strategy"])].append(row)
    expected = {
        (scenario, strategy) for scenario in scenarios for strategy in ("conditional", "permanent")
    }
    if set(grouped) != expected:
        raise ValueError(
            f"Unexpected {topic} scenario/strategy observations: {set(grouped) ^ expected}"
        )
    output = []
    for (scenario, strategy), rows in grouped.items():
        daily = daily_observations(rows)
        start = scenarios[scenario].get("start", "2022-01-01T00:00:00Z")
        end = scenarios[scenario].get("end", "2026-09-01T00:00:00Z")
        run_ids = {r["run_id"] for r in rows}
        if len(run_ids) != 1:
            raise ValueError("Multiple runs in one scenario/strategy")
        summary = (
            period_financials(daily, periods(dict(start=start, end=end)))
            if summarize is None
            else summarize(daily, timestamp(start), timestamp(end))
        )
        for row in summary:
            if abs(row["reconciliation_residual_usdt"]) > TOLERANCE:
                raise ValueError("Period accounting does not reconcile")
            row.update(scenario=scenario, strategy=strategy, run_id=next(iter(run_ids)))
            output.append(row)
    return output


MINUTE = 60 * SECOND


def recalculate(root):
    """Run each retained analysis once, returning an in-memory table overlay."""
    from . import costs, execution, risk, signal, stability, stress

    tables = {}
    for analysis in (signal, costs, execution, risk, stress, stability):
        for path, rows in analysis.recalculate(root).items():
            if path in tables:
                raise ValueError("Duplicate recalculated table: " + path)
            tables[path] = rows
    return tables
