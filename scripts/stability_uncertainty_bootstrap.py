"""Fixed B6 paired circular bootstrap, using authenticated BASE evidence only.

No strategy, minute reader or engine is executed here. Raw compact inputs retain
Decimal strings; statistical arrays and reductions use NumPy float64.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import math
import os
import platform
import statistics
import sys
import time
from collections import Counter, defaultdict
from decimal import Decimal as D
from pathlib import Path

# This module is also imported by the local postprocessing worker. Set limits
# before importing numerical libraries, and set Arrow's separate pools explicitly.
for _name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_name] = "1"
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
os.environ["MPLBACKEND"] = "Agg"
sys.dont_write_bytecode = True

import numpy as np  # noqa: E402
import pyarrow as pa  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402

pa.set_cpu_count(1)
pa.set_io_thread_count(1)

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
B5 = Path("entregas/entrega_4/estres_contrafactual/20260930T214617Z/distribucion_20261010")
B5_MANIFEST_SHA = "091fe38bba57ad5be62275cabb03579b1c47f2d96784ed7c5e2ce6377467a8de"
POINT_ATOL = 2e-10
SCALAR_ATOL = 2e-11
SOURCES = (
    dict(
        url="https://bashtage.github.io/arch/bootstrap/generated/arch.bootstrap.CircularBlockBootstrap.html",
        documentation_version="arch 8.0.0",
        support="Fixed-length blocks with end-to-start wrapping.",
    ),
    dict(
        url="https://bashtage.github.io/arch/bootstrap/timeseries-bootstraps.html",
        documentation_version="arch 8.0.0",
        support="Circular versus nonwrapping moving blocks; endpoint coverage.",
    ),
    dict(
        url="https://numpy.org/doc/stable/reference/random/parallel.html",
        documentation_version="NumPy 2.5",
        support="SeedSequence combines deterministic unique IDs and a root seed; IDs precede the root.",
    ),
    dict(
        url="https://numpy.org/doc/stable/reference/global_state.html",
        documentation_version="NumPy 2.5",
        support="BLAS thread counts depend on its backend; environment limits must precede imports.",
    ),
)


def sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf8",
        newline="\n",
    )
    temporary.replace(path)


def read_json(path):
    return json.loads(Path(path).read_text("utf8"))


def write_table(path, table):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    pq.write_table(table, temporary, compression="zstd")
    temporary.replace(path)


def write_rows(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(csv_text(rows).encode("utf8"))


def csv_text(rows):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(
        {
            k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v
            for k, v in row.items()
        }
        for row in rows
    )
    return stream.getvalue()


def protocol():
    return dict(
        schema="b6_paired_circular_year_gap_v1",
        root_seed=ROOT_SEED,
        seed_scheme_version=SEED_VERSION,
        bit_generator="PCG64",
        seed_entropy_order=[
            "schema_version",
            "block_length_days",
            "replica_id",
            "year",
            "first_day_since_1970",
            "last_day_since_1970",
            "root_seed",
        ],
        seedsequence_pool_size=4,
        replica_ids="0 through 4999 inclusive",
        principal_length_days=28,
        sensitivity_lengths_days=[14, 56],
        replicates_per_length=REPLICATES,
        batch_size=BATCH_SIZE,
        dtype="float64",
        percentiles=[0.025, 0.975],
        quantile_method="linear",
        minimum_valid_fraction_for_interval=0.95,
        annualization=365,
        sharpe_ddof=1,
        risk_free_rate=0,
        pairing="One index per day shared by both portfolios, both H1 assets and opportunity.",
        strata="Calendar year and contiguous known daily segment; unknown days retained as singleton strata.",
        h1="Sum absolute paired errors / valid observation counts within each asset, then BTC/ETH 50/50; errors fixed before resampling.",
        h3="2024+ minus 2022-2023, opportunity pb/168h and conditional CAGR; each regime keeps its day count.",
        periods={name: list(bounds) for name, bounds in PERIOD_BOUNDS.items()},
        economic_replay=False,
        selection="BASE_E3 only",
        missing_data="No missing return/opportunity is zero or cash; unknown inputs make affected effects ND.",
        decision_source="User-authorized B6 protocol, fixed before calculation; numerical choices are study decisions.",
        references=list(SOURCES),
        references_consulted_utc="2026-10-01",
        documentation_scope="Documentation supports the mechanism, not 28/14/56, 5000, annual strata or the 95% presentation rule.",
    )


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


def write_compact_inputs(candidate, daily, h1, opportunity):
    folder = Path(candidate) / "estadistica"
    write_json(folder / "protocolo.json", protocol())  # Fixed before any bootstrap calculation.
    for name, rows in zip(raw_schemas(), (daily, h1, opportunity), strict=True):
        write_table(
            folder / f"{name}.parquet", pa.Table.from_pylist(rows, schema=raw_schemas()[name])
        )
    compact = compact_sources(daily, h1, opportunity)
    write_table(folder / "diario_base.parquet", compact)
    return compact


def verify_inputs(candidate):
    folder = Path(candidate) / "estadistica"
    if read_json(folder / "protocolo.json") != protocol():
        raise ValueError("Bootstrap protocol/options changed")
    sources = []
    for name, schema in raw_schemas().items():
        table = pq.read_table(folder / f"{name}.parquet")
        if not table.schema.equals(schema):
            raise ValueError(f"Compact source type mismatch: {name}")
        sources.append(table.to_pylist())
    actual = pq.read_table(folder / "diario_base.parquet")
    if not actual.schema.equals(daily_schema()):
        raise ValueError("Daily statistical input type mismatch")
    expected = compact_sources(*sources)
    if not actual.equals(expected):
        raise ValueError("Daily inputs differ from reconstructed source sums/counts/returns")
    return actual, sources


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


def _same_rows(actual, expected, label):
    if len(actual) != len(expected):
        raise ValueError(f"{label}: row count changed")
    for i, (a, b) in enumerate(zip(actual, expected, strict=True)):
        if set(a) != set(b):
            raise ValueError(f"{label}: fields changed at {i}")
        for key in a:
            if isinstance(b[key], float):
                if type(a[key]) is not float or not math.isclose(
                    a[key], b[key], rel_tol=0, abs_tol=SCALAR_ATOL
                ):
                    raise ValueError(f"{label}: numeric value/type changed at {i}:{key}")
            elif type(a[key]) is not type(b[key]) or a[key] != b[key]:
                raise ValueError(f"{label}: value changed at {i}:{key}")


def verify_replica_table(path, expected):
    actual = pq.read_table(path)
    if not actual.schema.equals(pa.Table.from_pylist(expected).schema):
        raise ValueError("Replica/seed output types changed")
    _same_rows(actual.to_pylist(), expected, str(Path(path).name))


def verify_csv(path, expected):
    if Path(path).read_bytes() != csv_text(expected).encode("utf8"):
        raise ValueError("Bootstrap CSV differs from recomputed statistics")


def authenticate_and_load(candidate, project):
    """Authenticate just consumed B5 members and original BASE manifest outputs, once."""
    package = project / B5
    # Authenticate original source bytes, not the new documentary seal.
    seal_path = package / "procedencia/manifiesto_original.json"
    seal_sha = sha256(seal_path)
    if (
        seal_sha != B5_MANIFEST_SHA
        or (package / "procedencia/manifiesto_original.sha256").read_text().strip() != seal_sha
    ):
        raise ValueError("B5 authenticated reference manifest identity changed")
    seal = read_json(seal_path)
    members = {r["path"]: r for r in seal["members"]}
    inventory = {}

    def checked(relative):
        relative = Path(relative).as_posix()
        if relative in inventory:
            return package / relative
        member = members.get(relative)
        path = package / relative
        if (
            member is None
            or path.stat().st_size != member["bytes"]
            or sha256(path) != member["sha256"]
        ):
            raise ValueError(f"Unauthenticated B5 consumed member: {relative}")
        inventory[relative] = dict(member)
        return path

    references = read_json(checked("indice_referencias.json"))["references"]
    manifests, raw_daily, opportunities = {}, [], {}
    saved_forecasts = {}
    for strategy, run_id in BASES.items():
        ref = next(r for r in references if r["strategy"] == strategy)
        if ref["original_run_id"] != run_id:
            raise ValueError("BASE run ID changed in B5 references")
        relative = Path("evidencia") / run_id
        manifest_path = checked(relative / "run_manifest.json")
        if sha256(manifest_path) != ref["original_manifest_sha256"]:
            raise ValueError("BASE run manifest differs from B5 authenticated reference")
        manifest = read_json(manifest_path)
        manifests[strategy] = manifest
        if manifest["run_id"] != run_id or manifest["status"] != "complete":
            raise ValueError("BASE reference identity/completeness invalid")
        if manifest["config"]["horizon_hours"] != 168:
            raise ValueError("Bootstrap requires original BASE 168h")
        for name in ("equity_daily.csv", "opportunity_daily.csv", "effective_config.toml"):
            path = checked(relative / name)
            if sha256(path) != manifest["output_hashes"][name]:
                raise ValueError(f"BASE original output authentication failed: {name}")
        with (package / relative / "equity_daily.csv").open(encoding="utf8", newline="") as stream:
            rows = sorted(csv.DictReader(stream), key=lambda r: int(r["time_ns"]))
        previous, previous_day = (
            manifest["config"]["capital"],
            day_number(manifest["config"]["start"][:10]) - 1,
        )
        for row in rows:
            now = int(row["time_ns"]) // DAY_NS
            raw_daily.append(
                dict(
                    strategy=strategy,
                    run_id=run_id,
                    date=str(np.datetime64(now, "D")),
                    time_ns=int(row["time_ns"]),
                    equity_usdt=row["equity"],
                    starting_equity_usdt=previous if now == previous_day + 1 else None,
                    partial_day=row["partial_day"].lower() == "true",
                )
            )
            previous, previous_day = row["equity"], now
        with (package / relative / "opportunity_daily.csv").open(
            encoding="utf8", newline=""
        ) as stream:
            opportunities[strategy] = [
                dict(
                    date=r["date"],
                    time_ns=int(r["time_ns"]),
                    opportunity=r["opportunity"] or None,
                    eligible_fraction=r["eligible_fraction"] or None,
                    complete=r["complete"].lower() == "true",
                    reason=r["reason"],
                )
                for r in csv.DictReader(stream)
            ]
        compressed = checked(relative / "forecast_evaluation.csv.gz")
        with gzip.open(compressed, "rb") as stream:
            raw = stream.read()
        if hashlib.sha256(raw).hexdigest() != manifest["output_hashes"]["forecast_evaluation.csv"]:
            raise ValueError("Compressed H1 archive differs from original manifest")
        saved_forecasts[strategy] = list(csv.DictReader(raw.decode("utf8").splitlines()))
    if opportunities["conditional"] != opportunities["permanent"]:
        raise ValueError(
            "BASE opportunity depends on portfolio; pairing cannot silently choose one"
        )
    h1_all = pq.read_table(checked("resultados/h1_observaciones.parquet")).to_pylist()
    selected = {}
    for strategy, run_id in BASES.items():
        original_rows = [
            r
            for r in h1_all
            if r["scenario"] == "BASE_E3" and r["strategy"] == strategy and r["run_id"] == run_id
        ]
        selected[strategy] = [
            dict(
                symbol=r["symbol"],
                time_ns=int(r["time_ns"]),
                horizon_end=int(r["horizon_end"]),
                horizon_valid=r["horizon_valid"].lower() == "true",
                absolute_error_ewma=r["absolute_error_ewma"] or None,
                absolute_error_no_change=r["absolute_error_no_change"] or None,
                reason=r["reason"],
            )
            for r in original_rows
        ]
        from scripts.signal_sensitivity_hypotheses import compare_saved_h1

        compare_saved_h1(
            [
                dict(row, realized=original["realized"])
                for row, original in zip(selected[strategy], original_rows, strict=True)
            ],
            saved_forecasts[strategy],
        )
    if selected["conditional"] != selected["permanent"]:
        raise ValueError("BASE H1 populations differ across strategies")
    saved_points = {}
    for name in ("h1_resumen", "h3_resumen", "metricas"):
        rows = pq.read_table(checked(f"resultados/{name}.parquet")).to_pylist()
        saved_points[name] = [r for r in rows if r["scenario"] == "BASE_E3"]
    folder = Path(candidate) / "estadistica"
    write_json(folder / "referencias_base.json", references)
    write_json(folder / "manifiestos_base.json", manifests)
    write_json(folder / "puntos_referencia_b5.json", saved_points)
    write_json(
        folder / "procedencia.json",
        dict(
            schema="b6_bootstrap_sources_v1",
            source_package=B5.as_posix(),
            source_manifest_sha256=seal_sha,
            consumed_members=list(inventory.values()),
            source_selection="Only BASE_E3 run IDs; duplicated portfolio H1/opportunity populations compared, then retained once.",
            preserved_run_ids=BASES,
            engine_replay=False,
            massive_minute_inputs_reread=False,
            authentication_scope="Consumed member bytes + original run output hashes; historical B5 full integrity suites not rerun.",
            h1_saved_float_tolerance="1E-14 rate (original helper)",
            data_root_used=False,
        ),
    )
    return raw_daily, selected["conditional"], opportunities["conditional"]


def point_parity(candidate, data, sources):
    from crypto_carry.config import Config
    from crypto_carry.evaluation import portfolio_metrics
    from scripts.signal_sensitivity_hypotheses import summarize_h1, summarize_h3

    folder = Path(candidate) / "estadistica"
    manifests = read_json(folder / "manifiestos_base.json")
    # Config.from_dict is not a public API; use the accepted dataclass types through TOML.
    from dataclasses import fields

    config_dict = manifests["conditional"]["config"]
    defaults = Config()
    config = Config(
        **{
            f.name: D(config_dict[f.name])
            if isinstance(getattr(defaults, f.name), D)
            else tuple(config_dict[f.name])
            if isinstance(getattr(defaults, f.name), tuple)
            else config_dict[f.name]
            for f in fields(Config)
            if f.name in config_dict
        }
    )
    financial, h1, opportunity = sources
    helper_metrics = []
    for strategy in BASES:
        for period, (start, end) in PERIOD_BOUNDS.items():
            rows = [r for r in financial if r["strategy"] == strategy and start <= r["date"] < end]
            if not rows:
                continue
            metric = portfolio_metrics(
                [
                    dict(
                        time_ns=r["time_ns"], equity=r["equity_usdt"], partial_day=r["partial_day"]
                    )
                    for r in rows
                ],
                D(rows[0]["starting_equity_usdt"]),
                day_number(start) * DAY_NS,
                day_number(end) * DAY_NS,
            )
            helper_metrics.append(
                dict(
                    metric,
                    period=period,
                    strategy=strategy,
                    coverage_complete=len(rows) == day_number(end) - day_number(start),
                )
            )
    helper_h1 = summarize_h1(h1, config)
    helper_h3 = summarize_h3(opportunity, config, helper_metrics)
    lookup_h1 = {
        (r["period"], r["symbol"]): float((r["mae_ewma"] - r["mae_no_change"]) * 10000)
        for r in helper_h1
        if r["mae_ewma"] is not None
    }
    lookup_metric = {(r["period"], r["strategy"]): r for r in helper_metrics}
    lookup_h3 = {r["period"]: r for r in helper_h3}
    expected = {}
    for period in PERIOD_BOUNDS:
        for symbol in (*SYMBOLS, "EQUAL_WEIGHT"):
            expected[f"h1_mae_delta_bps__{period}__{symbol}"] = lookup_h1[period, symbol]
        expected[f"h2_conditional_cagr__{period}__PORTFOLIO"] = lookup_metric[
            period, "conditional"
        ]["cagr"]
        expected[f"h2_sharpe_delta__{period}__PORTFOLIO"] = (
            lookup_metric[period, "conditional"]["sharpe"]
            - lookup_metric[period, "permanent"]["sharpe"]
        )
    expected["h3_opportunity_delta_bps__contrast__PORTFOLIO"] = float(
        (lookup_h3["2024+"]["opportunity_mean"] - lookup_h3["2022-2023"]["opportunity_mean"])
        * 10000
    )
    expected["h3_conditional_cagr_delta__contrast__PORTFOLIO"] = (
        lookup_metric["2024+", "conditional"]["cagr"]
        - lookup_metric["2022-2023", "conditional"]["cagr"]
    )
    actual = batch_statistics(data, np.arange(len(data["date"]))[None, :])
    checks = []
    for name, point in expected.items():
        difference = abs(float(actual[name][0]) - point)
        if difference > POINT_ATOL:
            raise ValueError(f"Original helper point parity failed: {name}: {difference}")
        checks.append(
            dict(
                statistic=name,
                bootstrap_original=float(actual[name][0]),
                helper_original=point,
                absolute_difference=difference,
                tolerance=POINT_ATOL,
            )
        )
    archived = read_json(folder / "puntos_referencia_b5.json")
    saved_checks = []
    for row in archived["metricas"]:
        if row["period"] not in PERIOD_BOUNDS:
            continue
        helper = lookup_metric[row["period"], row["strategy"]]
        for field in ("cagr", "sharpe"):
            difference = abs(float(row[field]) - helper[field])
            if difference > POINT_ATOL:
                raise ValueError(f"B5 original financial parity failed: {field}")
            saved_checks.append(
                dict(
                    period=row["period"],
                    strategy=row["strategy"],
                    metric=field,
                    absolute_difference=difference,
                )
            )
    for row in archived["h1_resumen"]:
        if row["period"] in PERIOD_BOUNDS:
            value = float((D(row["mae_ewma"]) - D(row["mae_no_change"])) * 10000)
            if abs(value - lookup_h1[row["period"], row["symbol"]]) > POINT_ATOL:
                raise ValueError("B5 original H1 parity failed")
    for row in archived["h3_resumen"]:
        if (
            row["period"] in PERIOD_BOUNDS
            and abs(
                float(row["opportunity_mean_bps"])
                - float(lookup_h3[row["period"]]["opportunity_mean_bps"])
            )
            > POINT_ATOL
        ):
            raise ValueError("B5 original H3 parity failed")
    return dict(
        status="verified",
        checks=checks,
        archived_financial_checks=saved_checks,
        helpers=[
            "crypto_carry.evaluation.portfolio_metrics",
            "scripts.signal_sensitivity_hypotheses.summarize_h1",
            "scripts.signal_sensitivity_hypotheses.summarize_h3",
        ],
        rate_to_bps=10000,
        absolute_tolerance=POINT_ATOL,
        convention="Float equity ratios, sample Sharpe ddof=1 RF=0; CAGR compound with 365 days; Decimal H1 sums/counts.",
    )


def coverage_report(data, sources, strata):
    financial, h1, _ = sources
    missing = [
        {
            "date": str(data["date"][i]),
            "reasons": [str(data[k][i]) for k in data if k.endswith("_reason") and data[k][i]],
        }
        for i in range(len(data["date"]))
        if not data["joint_known"][i]
    ]
    exclusion_rows = []
    for symbol in SYMBOLS:
        rows = [r for r in h1 if r["symbol"] == symbol]
        valid = [r for r in rows if r["horizon_valid"]]
        exclusion_rows.append(
            dict(
                symbol=symbol,
                observed=len(rows),
                valid=len(valid),
                excluded=len(rows) - len(valid),
                exclusion_reasons=dict(
                    Counter(r["reason"] for r in rows if not r["horizon_valid"])
                ),
                first_valid_signal_ns=min(r["time_ns"] for r in valid),
                last_valid_signal_ns=max(r["time_ns"] for r in valid),
                final_target_exclusions=sum(r["reason"] == "horizon_outside_sample" for r in rows),
            )
        )
    return dict(
        first_date=str(data["date"][0]),
        last_date=str(data["date"][-1]),
        axis_days=len(data["date"]),
        joint_known_days=int(data["joint_known"].sum()),
        missing_days=missing,
        strata=strata,
        h1_population=exclusion_rows,
        strategy_rows=dict(Counter(r["strategy"] for r in financial)),
        annual_days=dict(Counter(str(d)[:4] for d in data["date"])),
        annual_inference="Descriptive breakdown only; no annual interval family.",
        horizon_edge="H1 target exclusions retained as known exclusions, separately from true missing calendar data.",
    )


def _build_code_identity(project):
    dependencies = (
        "scripts/stability_uncertainty_bootstrap.py",
        "src/crypto_carry/evaluation.py",
        "src/crypto_carry/config.py",
        "scripts/signal_sensitivity_hypotheses.py",
        "scripts/verify_rules_sensitivity_package.py",
        "scripts/continuous_delivery/hypotheses.py",
    )
    return {name: sha256(project / name) for name in dependencies}


def _reuse_completed(candidate, project):
    path = candidate / "estadistica/estado_build.json"
    if not path.is_file():
        return None
    state = read_json(path)
    if state["code_identity"] != _build_code_identity(project):
        return None
    if sha256(project / B5 / "procedencia/manifiesto_original.json") != B5_MANIFEST_SHA:
        raise ValueError("B5 source manifest changed before bootstrap reuse")
    for row in state["outputs"]:
        path = candidate / row["path"]
        if not path.is_file() or sha256(path) != row["sha256"]:
            raise ValueError(f"Completed bootstrap output changed: {row['path']}")
    for row in state["source_fingerprints"]:
        path = project / B5 / row["path"]
        stat = path.stat()
        if stat.st_mtime_ns != row["mtime_ns"] or stat.st_size != row["bytes"]:
            if sha256(path) != row["sha256"]:
                raise ValueError(f"Authenticated bootstrap source changed: {row['path']}")
    return dict(state["result"], status="reused_authenticated", calculation_repeated=False)


def _save_build_state(candidate, project, result):
    provenance = read_json(candidate / "estadistica/procedencia.json")
    output_paths = [
        p
        for p in (candidate / "estadistica").iterdir()
        if p.is_file() and p.name not in ("estado_build.json", "verificacion.json")
    ]
    output_paths.extend((candidate / "tablas").glob("bootstrap_*.json"))
    output_paths.extend((candidate / "tablas").glob("bootstrap_*.csv"))
    sources = []
    for row in provenance["consumed_members"]:
        path = project / B5 / row["path"]
        sources.append(dict(row, mtime_ns=path.stat().st_mtime_ns))
    write_json(
        candidate / "estadistica/estado_build.json",
        dict(
            schema="b6_bootstrap_build_complete_v1",
            code_identity=_build_code_identity(project),
            result=result,
            source_fingerprints=sources,
            outputs=[
                dict(path=p.relative_to(candidate).as_posix(), sha256=sha256(p))
                for p in sorted(output_paths)
            ],
        ),
    )


def build(candidate: Path, data_root: Path = Path("D:/Backtesting")):
    from scripts.run_signal_sensitivity import peak_memory_bytes

    candidate = Path(candidate).resolve()
    started = time.monotonic()
    project = Path(__file__).resolve().parents[1]
    reused = _reuse_completed(candidate, project)
    if reused:
        return reused
    write_json(candidate / "estadistica/protocolo.json", protocol())
    sources = authenticate_and_load(candidate, project)
    compact = write_compact_inputs(candidate, *sources)
    data = as_arrays(compact)
    parity = point_parity(candidate, data, sources)
    write_json(candidate / "estadistica/paridad_punto.json", parity)
    calculation_start = time.monotonic()
    result = calculate(data, print)
    for name in ("points", "intervals"):
        stem = "bootstrap_puntos" if name == "points" else "bootstrap_intervalos"
        write_json(candidate / "tablas" / (stem + ".json"), result[name])
        write_rows(candidate / "tablas" / (stem + ".csv"), result[name])
    write_table(
        candidate / "estadistica/replicas.parquet", pa.Table.from_pylist(result["replicas"])
    )
    write_table(candidate / "estadistica/semillas.parquet", pa.Table.from_pylist(result["seeds"]))
    write_json(candidate / "estadistica/control_escalar.json", result["scalar_checks"])
    write_json(
        candidate / "estadistica/cobertura.json", coverage_report(data, sources, result["strata"])
    )
    version_info = dict(
        python=platform.python_version(),
        numpy=np.__version__,
        pyarrow=pa.__version__,
        arrow_cpu_count=pa.cpu_count(),
        arrow_io_thread_count=pa.io_thread_count(),
        environment={
            k: os.environ.get(k)
            for k in (
                "OMP_NUM_THREADS",
                "OPENBLAS_NUM_THREADS",
                "MKL_NUM_THREADS",
                "NUMEXPR_NUM_THREADS",
                "PYTHONDONTWRITEBYTECODE",
                "MPLBACKEND",
            )
        },
        versions_updated=False,
        arch_installed_for_task=False,
        analytical_processes=1,
        peak_process_bytes=peak_memory_bytes(),
        source_preparation_seconds=calculation_start - started,
        statistical_seconds=time.monotonic() - calculation_start,
        total_seconds=time.monotonic() - started,
        data_root_argument=str(data_root),
        data_root_read=False,
    )
    if not (
        np.__version__.startswith("2.3.")
        and pa.__version__.startswith("25.")
        and sys.version_info[:2] == (3, 14)
    ):
        raise ValueError("B6 requires unchanged project numerical dependency family")
    write_json(candidate / "estadistica/entorno_tiempos.json", version_info)
    write_json(
        candidate / "estadistica/integridad_insumos.json",
        dict(
            files=[
                dict(path=f"estadistica/{name}", sha256=sha256(candidate / "estadistica" / name))
                for name in (
                    "carteras_base.parquet",
                    "h1_base.parquet",
                    "oportunidad_base.parquet",
                    "diario_base.parquet",
                    "protocolo.json",
                    "referencias_base.json",
                    "manifiestos_base.json",
                    "puntos_referencia_b5.json",
                    "procedencia.json",
                )
            ]
        ),
    )
    summary = dict(
        status="built",
        axis_days=len(data["date"]),
        replicates=REPLICATES * len(LENGTHS),
        statistics_per_replica=len(result["points"]),
        intervals=len(result["intervals"]),
        engine_replay=False,
        seconds=version_info["total_seconds"],
    )
    _save_build_state(candidate, project, summary)
    return summary


def verify(candidate: Path):
    candidate = Path(candidate)
    started = time.monotonic()
    table, sources = verify_inputs(candidate)
    folder = candidate / "estadistica"
    for item in read_json(folder / "integridad_insumos.json")["files"]:
        if sha256(candidate / item["path"]) != item["sha256"]:
            raise ValueError(f"Compact input authentication failed: {item['path']}")
    data = as_arrays(table)
    parity = point_parity(candidate, data, sources)
    if parity != read_json(folder / "paridad_punto.json"):
        raise ValueError("Original point parity evidence differs")
    result = calculate(data)
    verify_replica_table(folder / "replicas.parquet", result["replicas"])
    verify_replica_table(folder / "semillas.parquet", result["seeds"])
    _same_rows(
        read_json(candidate / "tablas/bootstrap_puntos.json"), result["points"], "Original points"
    )
    _same_rows(
        read_json(candidate / "tablas/bootstrap_intervalos.json"),
        result["intervals"],
        "Percentile intervals",
    )
    verify_csv(candidate / "tablas/bootstrap_puntos.csv", result["points"])
    verify_csv(candidate / "tablas/bootstrap_intervalos.csv", result["intervals"])
    if read_json(folder / "cobertura.json") != coverage_report(data, sources, result["strata"]):
        raise ValueError("Bootstrap coverage record changed")
    if read_json(folder / "control_escalar.json") != result["scalar_checks"]:
        raise ValueError("Scalar/vectorized control record changed")
    output = dict(
        status="verified",
        offline=True,
        engine_replay=False,
        massive_sources_reread=False,
        daily_axis=table.num_rows,
        replicate_rows=len(result["replicas"]),
        seed_streams=len(result["seeds"]),
        scalar_control_replicates=24,
        statistics_per_replica=len(result["points"]),
        intervals=len(result["intervals"]),
        degenerate_intervals=sum(
            r["interval_status"].startswith("ND") for r in result["intervals"]
        ),
        recalculated_from_compact_sources=True,
        seconds=time.monotonic() - started,
    )
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, default=Path("D:/Backtesting"))
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.verify:
        result = verify(args.candidate)
    else:
        result = build(args.candidate, args.data_root)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    project_root = str(Path(__file__).resolve().parents[1])
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    main()
