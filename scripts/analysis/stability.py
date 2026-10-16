"""Fixed paired circular bootstrap over retained BASE observations.

The statistical function bodies and constants below are extracted unchanged
from the original analysis. Only the loading adapter is new: raw compact
observations are aggregated to daily data, then all bootstrap samples and
intervals are recalculated in memory. No backtest or historical build executes.
"""

from __future__ import annotations

import hashlib
import json
import math
import statistics
import time
from collections import Counter, defaultdict
from decimal import Decimal as D
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from . import common as core
from .common import DAY, iso, scenario_metrics, timestamp

ROOT_SEED = 20261001


SEED_VERSION = 1


LENGTHS = (28, 14, 56)


REPLICATES = 5000


BATCH_SIZE = 128


DAY_NS = 86_400_000_000_000


SYMBOLS = ("BTCUSDT", "ETHUSDT")


BASES = {"conditional": "run_ad71d751b20623006c195ff3", "permanent": "run_dfea4b7ac1475668d5968c97"}


PERIOD_BOUNDS = {
    "full": ("2022-01-01", "2026-09-01"),
    "2022-2023": ("2022-01-01", "2024-01-01"),
    "2024+": ("2024-01-01", "2026-09-01"),
}


SCALAR_ATOL = 2e-11


def raw_schemas():
    return {
        "carteras_base": pa.schema(
            [
                ("strategy", pa.string()),
                ("run_id", pa.string()),
                ("date", pa.string()),
                ("time_ns", pa.int64()),
                ("equity_usdt", pa.string()),
                ("starting_equity_usdt", pa.string()),
                ("partial_day", pa.bool_()),
            ]
        ),
        "h1_base": pa.schema(
            [
                ("symbol", pa.string()),
                ("time_ns", pa.int64()),
                ("horizon_end", pa.int64()),
                ("horizon_valid", pa.bool_()),
                ("absolute_error_ewma", pa.string()),
                ("absolute_error_no_change", pa.string()),
                ("reason", pa.string()),
            ]
        ),
        "oportunidad_base": pa.schema(
            [
                ("date", pa.string()),
                ("time_ns", pa.int64()),
                ("opportunity", pa.string()),
                ("eligible_fraction", pa.string()),
                ("complete", pa.bool_()),
                ("reason", pa.string()),
            ]
        ),
    }


def daily_schema():
    fields = [
        ("date", pa.string()),
        ("day_ns", pa.int64()),
        ("year", pa.int64()),
        ("return_conditional", pa.float64()),
        ("return_permanent", pa.float64()),
        ("return_conditional_reason", pa.string()),
        ("return_permanent_reason", pa.string()),
        ("opportunity_bps", pa.float64()),
        ("opportunity_reason", pa.string()),
        ("joint_known", pa.bool_()),
    ]
    for symbol in SYMBOLS:
        fields.extend(
            [
                (f"h1_ewma_{symbol}", pa.float64()),
                (f"h1_no_change_{symbol}", pa.float64()),
                (f"h1_count_{symbol}", pa.int64()),
                (f"h1_observed_{symbol}", pa.int64()),
                (f"h1_excluded_{symbol}", pa.int64()),
                (f"h1_horizon_excluded_{symbol}", pa.int64()),
                (f"h1_known_{symbol}", pa.bool_()),
                (f"h1_exclusion_reasons_{symbol}", pa.string()),
            ]
        )
    return pa.schema(fields)


def day_number(date):
    return int(np.datetime64(date, "D").astype(np.int64))


def compact_sources(daily, h1, opportunity):
    """Aggregate only once; raw Decimal strings and counts remain independently auditable."""
    portfolios, opportunities, errors = {}, {}, defaultdict(list)
    for row in daily:
        if type(row["partial_day"]) is not bool:
            raise ValueError("Portfolio source boolean is unknown or mistyped")
        if not D(row["equity_usdt"]).is_finite():
            raise ValueError("Portfolio source equity is nonfinite")
        key = row["date"], row["strategy"]
        if key in portfolios or row["strategy"] not in BASES:
            raise ValueError("Duplicate or unknown BASE portfolio day")
        if row["time_ns"] // DAY_NS != day_number(row["date"]):
            raise ValueError("Portfolio UTC date mismatch")
        portfolios[key] = row
    for row in opportunity:
        if type(row["complete"]) is not bool:
            raise ValueError("Opportunity source boolean is unknown or mistyped")
        if row["date"] in opportunities or row["time_ns"] // DAY_NS != day_number(row["date"]):
            raise ValueError("Duplicate or misaligned opportunity day")
        if row["complete"] and row["opportunity"] is None:
            raise ValueError("Known opportunity has no value")
        opportunities[row["date"]] = row
    seen = set()
    for row in h1:
        if type(row["horizon_valid"]) is not bool:
            raise ValueError("H1 source boolean is unknown or mistyped")
        key = row["symbol"], row["time_ns"]
        if key in seen or row["symbol"] not in SYMBOLS:
            raise ValueError("Duplicate or unknown H1 observation")
        seen.add(key)
        if row["horizon_end"] - row["time_ns"] != 168 * 3_600_000_000_000:
            raise ValueError("H1 target horizon differs from BASE 168h")
        if row["horizon_valid"]:
            if row["reason"] or any(
                row[f] is None or not D(row[f]).is_finite() or D(row[f]) < 0
                for f in ("absolute_error_ewma", "absolute_error_no_change")
            ):
                raise ValueError("Invalid paired H1 error or validity label")
        elif not row["reason"] or any(
            row[f] is not None for f in ("absolute_error_ewma", "absolute_error_no_change")
        ):
            raise ValueError("Excluded H1 observation has an error or lacks its reason")
        errors[(str(np.datetime64(row["time_ns"] // DAY_NS, "D")), row["symbol"])].append(row)
    dates = sorted({key[0] for key in portfolios} | set(opportunities) | {key[0] for key in errors})
    if not dates:
        raise ValueError("Empty BASE statistical inputs")
    output = []
    for number in range(day_number(dates[0]), day_number(dates[-1]) + 1):
        date = str(np.datetime64(number, "D"))
        result = dict(date=date, day_ns=number * DAY_NS, year=int(date[:4]))
        for strategy in BASES:
            row = portfolios.get((date, strategy))
            reason, value = "missing_portfolio_day", None
            if row:
                if row["partial_day"]:
                    reason = "partial_portfolio_day"
                elif row["starting_equity_usdt"] is None:
                    reason = "unverified_previous_close"
                else:
                    opening, closing = float(row["starting_equity_usdt"]), float(row["equity_usdt"])
                    if not np.isfinite([opening, closing]).all() or opening <= 0:
                        reason = "nonpositive_or_nonfinite_starting_equity"
                    else:
                        value, reason = closing / opening - 1, ""
            result[f"return_{strategy}"] = value
            result[f"return_{strategy}_reason"] = reason
        row = opportunities.get(date)
        known = row is not None and row["complete"]
        result["opportunity_bps"] = float(D(row["opportunity"]) * 10000) if known else None
        result["opportunity_reason"] = (
            "" if known else (row["reason"] if row else "missing_opportunity_day")
        )
        for symbol in SYMBOLS:
            rows = errors.get((date, symbol), [])
            valid = [r for r in rows if r["horizon_valid"]]
            exclusions = Counter(r["reason"] for r in rows if not r["horizon_valid"])
            result.update(
                {
                    f"h1_ewma_{symbol}": float(
                        sum((D(r["absolute_error_ewma"]) for r in valid), D(0)) * 10000
                    ),
                    f"h1_no_change_{symbol}": float(
                        sum((D(r["absolute_error_no_change"]) for r in valid), D(0)) * 10000
                    ),
                    f"h1_count_{symbol}": len(valid),
                    f"h1_observed_{symbol}": len(rows),
                    f"h1_excluded_{symbol}": len(rows) - len(valid),
                    f"h1_horizon_excluded_{symbol}": exclusions.get("horizon_outside_sample", 0),
                    f"h1_known_{symbol}": bool(rows),
                    f"h1_exclusion_reasons_{symbol}": json.dumps(dict(exclusions), sort_keys=True),
                }
            )
        result["joint_known"] = (
            all(result[f"return_{s}"] is not None for s in BASES)
            and known
            and all(result[f"h1_known_{s}"] for s in SYMBOLS)
        )
        output.append(result)
    return pa.Table.from_pylist(output, schema=daily_schema())


def make_strata(dates, known=None):
    dates = np.asarray(dates)
    numbers = dates.astype("datetime64[D]").astype(np.int64)
    if len(numbers) == 0 or np.any(np.diff(numbers) <= 0):
        raise ValueError("Daily UTC axis must be nonempty, unique and increasing")
    known = np.ones(len(dates), dtype=bool) if known is None else np.asarray(known, dtype=bool)
    if len(known) != len(dates):
        raise ValueError("Daily coverage mask length differs")
    starts = [0]
    for i in range(1, len(dates)):
        if (
            str(dates[i])[:4] != str(dates[i - 1])[:4]
            or numbers[i] != numbers[i - 1] + 1
            or not known[i]
            or not known[i - 1]
        ):
            starts.append(i)
    strata = []
    for first, stop in zip(starts, starts[1:] + [len(dates)], strict=True):
        strata.append(
            dict(
                first=first,
                stop=stop,
                year=int(str(dates[first])[:4]),
                first_day=int(numbers[first]),
                last_day=int(numbers[stop - 1]),
                start_date=str(dates[first]),
                end_date=str(dates[stop - 1]),
                stratum_id=f"{dates[first]}__{dates[stop - 1]}",
                known=bool(known[first]),
            )
        )
    return strata


def draw_indices(strata, block_length, replica_ids):
    if block_length not in LENGTHS:
        raise ValueError("Unauthorized block length; closed B6 protocol")
    ids = list(replica_ids)
    if len(set(ids)) != len(ids) or any(type(i) is not int or i < 0 for i in ids):
        raise ValueError("Replica IDs must be distinct nonnegative integers")
    indices = np.empty((len(ids), strata[-1]["stop"]), dtype=np.int64)
    seeds = []
    for s in strata:
        n = s["stop"] - s["first"]
        offsets = np.arange(block_length, dtype=np.int64)
        for row, replica in enumerate(ids):
            entropy = [
                SEED_VERSION,
                block_length,
                replica,
                s["year"],
                s["first_day"],
                s["last_day"],
                ROOT_SEED,
            ]
            sequence = np.random.SeedSequence(entropy, pool_size=4)
            rng = np.random.Generator(np.random.PCG64(sequence))
            starts = rng.integers(0, n, size=(n + block_length - 1) // block_length)
            indices[row, s["first"] : s["stop"]] = ((starts[:, None] + offsets) % n).ravel()[
                :n
            ] + s["first"]
            seeds.append(
                dict(
                    block_length_days=block_length,
                    replica_id=replica,
                    stratum_id=s["stratum_id"],
                    seed_entropy=entropy,
                    seed_state_uint32=[int(v) for v in sequence.generate_state(4)],
                )
            )
    return indices, seeds


def as_arrays(table):
    return {name: table[name].to_numpy(zero_copy_only=False) for name in table.column_names}


def period_indices(data):
    dates = data["date"].astype("datetime64[D]")
    return {
        name: np.flatnonzero((dates >= np.datetime64(start)) & (dates < np.datetime64(end)))
        for name, (start, end) in PERIOD_BOUNDS.items()
    }


def _return_statistics(values):
    count, n = values.shape
    cagr, sharpe = np.full(count, np.nan), np.full(count, np.nan)
    cr = np.full(count, "no_daily_returns", dtype=object)
    sr = np.full(count, "fewer_than_two_daily_returns", dtype=object)
    if n == 0:
        return cagr, sharpe, cr, sr
    finite = np.isfinite(values).all(axis=1)
    positive = (values > -1).all(axis=1)
    valid = finite & positive
    cr[:] = np.where(~finite, "unknown_daily_return", "nonpositive_equity_or_insolvency")
    with np.errstate(invalid="ignore", divide="ignore", over="ignore"):
        cagr[valid] = np.expm1(np.log1p(values[valid]).sum(axis=1) * 365 / n)
    cr[np.isfinite(cagr)] = ""
    sr[~finite] = "unknown_daily_return"
    sr[finite & ~positive] = "nonpositive_equity_or_insolvency"
    if n >= 2:
        mean = values.mean(axis=1)
        std = values.std(axis=1, ddof=1)
        nonconstant = np.ptp(values, axis=1) > 0
        good = valid & (std > 0) & nonconstant
        sharpe[good] = mean[good] / std[good] * math.sqrt(365)
        sr[valid & ~good] = "zero_sample_volatility"
        sr[good] = ""
    return cagr, sharpe, cr, sr


def batch_statistics(data, indices, periods=None, with_reasons=False):
    periods = period_indices(data) if periods is None else periods
    output, reasons, opportunities, cagrs = {}, {}, {}, {}
    m = len(indices)
    for period, positions in periods.items():
        selection = indices[:, positions]
        for strategy in BASES:
            values = np.asarray(data[f"return_{strategy}"], dtype=np.float64)[selection]
            cagr, sharpe, cr, sr = _return_statistics(values)
            cagrs[period, strategy] = cagr, cr
            if strategy == "conditional":
                name = f"h2_conditional_cagr__{period}__PORTFOLIO"
                output[name], reasons[name] = cagr, cr
                cond_sharpe, cond_reason = sharpe, sr
            else:
                name = f"h2_sharpe_delta__{period}__PORTFOLIO"
                output[name] = cond_sharpe - sharpe
                reasons[name] = np.array(
                    [
                        ";".join(
                            filter(
                                None,
                                (f"conditional:{a}" if a else "", f"permanent:{b}" if b else ""),
                            )
                        )
                        for a, b in zip(cond_reason, sr, strict=True)
                    ],
                    dtype=object,
                )
        asset_values, asset_reasons = [], []
        for symbol in SYMBOLS:
            count = np.asarray(data[f"h1_count_{symbol}"], dtype=np.int64)[selection].sum(axis=1)
            known = np.asarray(data.get(f"h1_known_{symbol}", np.ones(len(data["date"]), bool)))[
                selection
            ].all(axis=1)
            sums = np.asarray(data[f"h1_ewma_{symbol}"], dtype=np.float64)[selection].sum(
                axis=1
            ) - np.asarray(data[f"h1_no_change_{symbol}"], dtype=np.float64)[selection].sum(axis=1)
            values = np.full(m, np.nan)
            valid = (count > 0) & known & np.isfinite(sums)
            values[valid] = sums[valid] / count[valid]
            reason = np.where(
                valid,
                "",
                np.where(~known, "unknown_H1_observation_day", "no_valid_paired_H1_observations"),
            )
            name = f"h1_mae_delta_bps__{period}__{symbol}"
            output[name], reasons[name] = values, reason
            asset_values.append(values)
            asset_reasons.append(reason)
        name = f"h1_mae_delta_bps__{period}__EQUAL_WEIGHT"
        output[name] = (asset_values[0] + asset_values[1]) / 2
        reasons[name] = np.array(
            [";".join(sorted({v for v in pair if v})) for pair in zip(*asset_reasons, strict=True)],
            dtype=object,
        )
        opportunity = np.asarray(data["opportunity_bps"], dtype=np.float64)[selection]
        opportunities[period] = opportunity.mean(axis=1) if len(positions) else np.full(m, np.nan)
    early, late = "2022-2023", "2024+"
    covered = len(periods.get(early, [])) > 0 and len(periods.get(late, [])) > 0
    for metric in ("h3_opportunity_delta_bps", "h3_conditional_cagr_delta"):
        name = f"{metric}__contrast__PORTFOLIO"
        if not covered:
            output[name] = np.full(m, np.nan)
            reasons[name] = np.full(m, "original_regime_not_covered", dtype=object)
        elif metric == "h3_opportunity_delta_bps":
            output[name] = opportunities[late] - opportunities[early]
            reasons[name] = np.where(np.isfinite(output[name]), "", "unknown_daily_opportunity")
        else:
            output[name] = cagrs[late, "conditional"][0] - cagrs[early, "conditional"][0]
            reasons[name] = np.array(
                [
                    ";".join(sorted({v for v in pair if v}))
                    for pair in zip(
                        cagrs[early, "conditional"][1], cagrs[late, "conditional"][1], strict=True
                    )
                ],
                dtype=object,
            )
    return (output, reasons) if with_reasons else output


def scalar_statistics(data, indices, periods=None):
    """Independent small control: Python products, fsum and sample stdev."""
    periods = period_indices(data) if periods is None else periods
    result, opportunities, cagr_by_period = {}, {}, {}
    for period, positions in periods.items():
        chosen = [int(indices[int(i)]) for i in positions]
        sharpes = []
        for strategy in BASES:
            values = [float(data[f"return_{strategy}"][i]) for i in chosen]
            good = bool(values) and all(math.isfinite(v) and v > -1 for v in values)
            cagr = math.prod(1 + v for v in values) ** (365 / len(values)) - 1 if good else math.nan
            std = statistics.stdev(values) if good and len(values) > 1 else math.nan
            sharpe = statistics.mean(values) / std * math.sqrt(365) if std > 0 else math.nan
            sharpes.append(sharpe)
            if strategy == "conditional":
                result[f"h2_conditional_cagr__{period}__PORTFOLIO"] = cagr
                cagr_by_period[period] = cagr
        result[f"h2_sharpe_delta__{period}__PORTFOLIO"] = sharpes[0] - sharpes[1]
        asset = []
        for symbol in SYMBOLS:
            count = sum(int(data[f"h1_count_{symbol}"][i]) for i in chosen)
            known = (
                all(bool(data[f"h1_known_{symbol}"][i]) for i in chosen)
                if f"h1_known_{symbol}" in data
                else True
            )
            a = math.fsum(float(data[f"h1_ewma_{symbol}"][i]) for i in chosen)
            b = math.fsum(float(data[f"h1_no_change_{symbol}"][i]) for i in chosen)
            value = (a - b) / count if count and known else math.nan
            result[f"h1_mae_delta_bps__{period}__{symbol}"] = value
            asset.append(value)
        result[f"h1_mae_delta_bps__{period}__EQUAL_WEIGHT"] = sum(asset) / 2
        values = [float(data["opportunity_bps"][i]) for i in chosen]
        opportunities[period] = math.fsum(values) / len(values) if values else math.nan
    result["h3_opportunity_delta_bps__contrast__PORTFOLIO"] = opportunities.get(
        "2024+", math.nan
    ) - opportunities.get("2022-2023", math.nan)
    result["h3_conditional_cagr_delta__contrast__PORTFOLIO"] = cagr_by_period.get(
        "2024+", math.nan
    ) - cagr_by_period.get("2022-2023", math.nan)
    return result


def summarize_distribution(values):
    finite = np.asarray(values)[np.isfinite(values)]
    count, valid = len(values), len(finite)
    fraction = valid / count if count else 0
    quantiles = (
        [float(v) for v in np.quantile(finite, [0.025, 0.975], method="linear")]
        if valid
        else [None, None]
    )
    status = "evaluable" if valid == count and count else "conditional_on_evaluability"
    return dict(
        n_replicates=count,
        valid_replicates=valid,
        invalid_replicates=count - valid,
        valid_fraction=fraction,
        interval_low=quantiles[0] if fraction >= 0.95 else None,
        interval_high=quantiles[1] if fraction >= 0.95 else None,
        interval_status=status if fraction >= 0.95 else "ND_less_than_95_percent_evaluable",
        finite_quantile_low=quantiles[0],
        finite_quantile_high=quantiles[1],
        finite_quantile_status=status if valid else "ND_no_evaluable_replicates",
    )


def describe_metric(name, data):
    metric, period, symbol = name.split("__")
    original_period = period
    period = "2024+ minus 2022-2023" if period == "contrast" else period
    start, end = PERIOD_BOUNDS.get(original_period, PERIOD_BOUNDS["full"])
    dates = data["date"].astype("datetime64[D]")
    mask = (dates >= np.datetime64(start)) & (dates < np.datetime64(end))
    units = (
        "pb/168 h"
        if "bps" in metric
        else ("Sharpe RF=0" if "sharpe" in metric else "fraction/year")
    )
    row = dict(
        metric=metric,
        hypothesis=metric[:2].upper(),
        period=period,
        symbol=symbol,
        unit=units,
        start_utc=start + "T00:00:00Z",
        end_exclusive_utc=end + "T00:00:00Z",
        observed_days=int(mask.sum()),
        expected_days=day_number(end) - day_number(start),
    )
    if metric.startswith("h1"):
        selected = SYMBOLS if symbol == "EQUAL_WEIGHT" else (symbol,)
        row["paired_observations"] = sum(int(data[f"h1_count_{s}"][mask].sum()) for s in selected)
        row["population"] = {s: int(data[f"h1_count_{s}"][mask].sum()) for s in selected}
    else:
        row["paired_observations"] = int(mask.sum())
        row["population"] = "daily returns include inactive days; fixed historical calendar"
    return row


def calculate(data, progress=None):
    strata = make_strata(data["date"], data["joint_known"])
    periods = period_indices(data)
    original = np.arange(len(data["date"]), dtype=np.int64)[None, :]
    points, point_reasons = batch_statistics(data, original, periods, with_reasons=True)
    point_rows = [
        dict(
            describe_metric(name, data),
            point_estimate=float(values[0]) if np.isfinite(values[0]) else None,
            reason=str(point_reasons[name][0]),
        )
        for name, values in points.items()
    ]
    all_rows, seed_rows, intervals, scalar_checks = [], [], [], []
    for length in LENGTHS:
        collected = defaultdict(list)
        invalid_reasons = defaultdict(Counter)
        started = time.monotonic()
        for first in range(0, REPLICATES, BATCH_SIZE):
            ids = list(range(first, min(first + BATCH_SIZE, REPLICATES)))
            indices, seeds = draw_indices(strata, length, ids)
            values, reasons = batch_statistics(data, indices, periods, with_reasons=True)
            seed_rows.extend(seeds)
            if first == 0:
                difference = 0.0
                for i in range(min(8, len(indices))):
                    scalar = scalar_statistics(data, indices[i], periods)
                    for name in values:
                        actual, expected = float(values[name][i]), scalar[name]
                        if not np.isclose(
                            actual, expected, rtol=0, atol=SCALAR_ATOL, equal_nan=True
                        ):
                            raise ValueError(f"Scalar/vectorized bootstrap mismatch: {name}")
                        if np.isfinite(actual):
                            difference = max(difference, abs(actual - expected))
                scalar_checks.append(
                    dict(
                        block_length_days=length,
                        replica_ids=ids[:8],
                        statistics=len(values),
                        maximum_absolute_difference=difference,
                        absolute_tolerance=SCALAR_ATOL,
                    )
                )
            for name, array in values.items():
                collected[name].append(array)
                invalid_reasons[name].update(str(v) for v in reasons[name][~np.isfinite(array)])
            for i, replica in enumerate(ids):
                row = dict(
                    block_length_days=length,
                    replica_id=replica,
                    root_seed=ROOT_SEED,
                    seed_scheme_version=SEED_VERSION,
                    indices_sha256=hashlib.sha256(indices[i].astype("<i8").tobytes()).hexdigest(),
                )
                for name, array in values.items():
                    row[name] = float(array[i]) if np.isfinite(array[i]) else None
                    row[name + "__reason"] = str(reasons[name][i])
                all_rows.append(row)
        for name, batches in collected.items():
            values = np.concatenate(batches)
            point = points[name][0]
            intervals.append(
                dict(
                    describe_metric(name, data),
                    point_estimate=float(point) if np.isfinite(point) else None,
                    block_length_days=length,
                    block_role="principal" if length == 28 else "method_sensitivity",
                    **summarize_distribution(values),
                    nd_reasons=dict(invalid_reasons[name]),
                )
            )
        if progress:
            progress(
                f"bootstrap L={length}: {REPLICATES} replicas, {time.monotonic() - started:.2f}s",
                flush=True,
            )
    return dict(
        points=point_rows,
        intervals=intervals,
        replicas=all_rows,
        seeds=seed_rows,
        strata=strata,
        scalar_checks=scalar_checks,
    )


def load_bootstrap_daily(root):
    """Reconstruct daily returns and H1 sums/counts from retained raw rows."""
    folder = Path(root) / "results/estabilidad/evidencia/estadistica"
    sources = []
    for name, schema in raw_schemas().items():
        table = pq.read_table(folder / f"{name}.parquet")
        if not table.schema.equals(schema):
            raise ValueError(f"Bootstrap raw input type mismatch: {name}")
        sources.append(table.to_pylist())
    return compact_sources(*sources)


def bootstrap_tables(root):
    """Return both complete bootstrap tables without reading prior results."""
    result = calculate(as_arrays(load_bootstrap_daily(root)))
    folder = "results/estabilidad/evidencia/tablas"
    return {
        f"{folder}/bootstrap_puntos.csv": result["points"],
        f"{folder}/bootstrap_intervalos.csv": result["intervals"],
    }


END = timestamp("2026-09-01T00:00:00Z")


SCENARIOS = {
    "BASE_E3": {},
    "I2023": {"start": "2023-01-01T00:00:00Z"},
    "I2024": {"start": "2024-01-01T00:00:00Z"},
    "BASE_CONTINUA_I2023": {"start": "2023-01-01T00:00:00Z"},
    "BASE_CONTINUA_I2024": {"start": "2024-01-01T00:00:00Z"},
}


CAPITAL_FIELDS = (
    "capital_deployed_usdt",
    "capital_utilization",
    "gross_exposure_usdt",
    "collateral_usdt",
    "debt_usdt",
)


METRICS = ("net_return", "cagr", "sharpe", "annual_volatility", "max_drawdown", "max_drawdown_days")


def period_specs(start, end):
    """Original cuts retain nominal dates and receive explicit partial labels."""
    output = [
        dict(
            period="full",
            lower=start,
            upper=end,
            nominal_lower=start,
            nominal_upper=end,
            period_kind="available_sample",
        )
    ]
    originals = (
        ("2022-2023", timestamp("2022-01-01T00:00:00Z"), timestamp("2024-01-01T00:00:00Z")),
        ("2024+", timestamp("2024-01-01T00:00:00Z"), END),
    )
    for label, lo, hi in originals:
        lower, upper = max(start, lo), min(end, hi)
        if lower < upper:
            output.append(
                dict(
                    period=label if (lower, upper) == (lo, hi) else label + "_disponible",
                    lower=lower,
                    upper=upper,
                    nominal_lower=lo,
                    nominal_upper=hi,
                    period_kind="original_cut",
                )
            )
    for year in range(int(iso(start)[:4]), int(iso(end - 1)[:4]) + 1):
        lo = timestamp(f"{year}-01-01T00:00:00Z")
        hi = timestamp(f"{year + 1}-01-01T00:00:00Z")
        output.append(
            dict(
                period=str(year),
                lower=max(start, lo),
                upper=min(end, hi),
                nominal_lower=lo,
                nominal_upper=hi,
                period_kind="calendar_year",
            )
        )
    return output


def summarize_periods(daily, start, end):
    output = []
    for spec in period_specs(start, end):
        selected = [r for r in daily if spec["lower"] <= r["time_ns"] < spec["upper"]]
        if not selected:
            continue
        lower = max(spec["lower"], selected[0]["time_ns"] // DAY * DAY)
        upper = min(spec["upper"], selected[-1]["time_ns"] + 1)
        full_days = sum(not r["partial_day"] for r in selected)
        expected_times = list(range(lower + DAY - 1, upper, DAY))
        regular = [r["time_ns"] for r in selected] == expected_times and not any(
            r["partial_day"] or r["daily_return"] is None and r["starting_equity_usdt"] > 0
            for r in selected
        )
        if regular:
            row = core.period_financials(daily, [(spec["period"], lower, upper)])[0]
        else:
            opening, final = selected[0]["starting_equity_usdt"], selected[-1]["equity_usdt"]
            row = dict(
                period=spec["period"],
                starting_equity_usdt=opening,
                final_equity_usdt=final,
                net_pnl_usdt=final - opening,
            )
            row.update({key: None for key in METRICS})
            row.update(cagr_reason="incomplete_daily_grid", sharpe_reason="incomplete_daily_grid")
            for key in (*core.COMPONENTS, *core.SPLIT_COMPONENTS):
                row[key] = sum((r[key] for r in selected), D(0))
            for key in CAPITAL_FIELDS:
                row[key + "_daily_mean"] = row[key + "_daily_max"] = None
            row["reconciliation_residual_usdt"] = row["net_pnl_usdt"] - sum(
                (row[key] for key in core.COMPONENTS[:-1]), D(0)
            )
        if abs(row["reconciliation_residual_usdt"]) > D("1E-8"):
            raise ValueError("Period Decimal reconciliation exceeds 1E-8")
        complete = regular and (lower, upper) == (spec["lower"], spec["upper"])
        nominal = complete and (lower, upper) == (spec["nominal_lower"], spec["nominal_upper"])
        row.update(
            start_utc=iso(lower),
            end_exclusive_utc=iso(upper),
            requested_start_utc=iso(spec["lower"]),
            requested_end_exclusive_utc=iso(spec["upper"]),
            nominal_start_utc=iso(spec["nominal_lower"]),
            nominal_end_exclusive_utc=iso(spec["nominal_upper"]),
            period_kind=spec["period_kind"],
            days=full_days,
            observed_snapshots=len(selected),
            missing_days=max(0, (spec["upper"] - spec["lower"]) // DAY - full_days),
            coverage_complete=complete,
            original_period_complete=nominal,
            year_complete=nominal if spec["period_kind"] == "calendar_year" else None,
            coverage_reason="" if complete else "actual_dates_only_no_extrapolation",
            metrics_evaluable_on_observed_grid=regular,
            drawdown_frequency="daily_close",
            sharpe_rf=0,
            sharpe_ddof=1,
            annualization_days=365,
        )
        if row["starting_equity_usdt"] <= 0:
            row["net_return"] = row["max_drawdown"] = row["max_drawdown_days"] = None
        output.append(row)
    return output


def recalculate(root):
    """New-account comparisons and fixed-seed uncertainty, from observed inputs."""
    metrics = scenario_metrics(root, "estabilidad", SCENARIOS, summarize=summarize_periods)
    grouped = {(r["scenario"], r["strategy"], r["period"]): r for r in metrics}
    comparisons = []
    for row in metrics:
        if row["scenario"] not in ("I2023", "I2024"):
            continue
        base = grouped[("BASE_CONTINUA_" + row["scenario"], row["strategy"], row["period"])]
        same_dates = all(row[k] == base[k] for k in ("start_utc", "end_exclusive_utc"))
        result = dict(
            scenario=row["scenario"],
            strategy=row["strategy"],
            period=row["period"],
            run_id=row["run_id"],
            base_run_id=base["run_id"],
            start_utc=row["start_utc"],
            end_exclusive_utc=row["end_exclusive_utc"],
            matching_observed_dates=same_dates,
            new_denominator_usdt=row["starting_equity_usdt"],
            inherited_denominator_usdt=base["starting_equity_usdt"],
        )
        for key in METRICS:
            result["new_" + key], result["inherited_" + key] = row[key], base[key]
            result["difference_" + key] = (
                D(str(row[key])) - D(str(base[key]))
                if same_dates and row[key] is not None and base[key] is not None
                else None
            )
        comparisons.append(result)
    result = bootstrap_tables(root)
    result["results/estabilidad/evidencia/tablas/metricas.csv"] = metrics
    result["results/estabilidad/evidencia/tablas/comparacion_inicios.csv"] = comparisons
    return result
