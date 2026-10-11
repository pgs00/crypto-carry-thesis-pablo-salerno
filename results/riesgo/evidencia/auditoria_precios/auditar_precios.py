"""Read-only audit of frozen price conventions and local persisted inputs.

Run with explicit source paths; JSON is emitted to stdout. No input is modified,
and this script neither imports the strategy nor launches a backtest.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import sys
import time
import zipfile
from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

MINUTE = 60_000_000_000
START = 1640995200000000000
END = 1788220800000000000
ANCHOR = 1679657280000000000
REOPEN_AVAILABLE = 1679666460000000000
RUNS = {
    "BASE_E3_conditional": "run_ad71d751b20623006c195ff3",
    "BASE_E3_permanent": "run_dfea4b7ac1475668d5968c97",
    "MARGEN_2X_conditional": "run_70383794701c4f0fc157b2ed",
    "MARGEN_2X_permanent": "run_3f5d9cce8ff1c2ba5447e3b6",
}


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def utc(value: int) -> str:
    seconds, nanos = divmod(int(value), 1_000_000_000)
    return datetime.fromtimestamp(seconds, UTC).strftime("%Y-%m-%dT%H:%M:%S") + (f".{nanos:09d}Z")


def blocks(values: list[int]) -> list[dict]:
    result = []
    for value in values:
        if result and value == result[-1]["last_available_at"] + MINUTE:
            result[-1]["last_available_at"] = value
            result[-1]["rows"] += 1
        else:
            result.append({"first_available_at": value, "last_available_at": value, "rows": 1})
    for item in result:
        item["first_utc"] = utc(item["first_available_at"])
        item["last_utc"] = utc(item["last_available_at"])
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", required=True, type=Path)
    parser.add_argument("--data-root", required=True, type=Path)
    args = parser.parse_args()
    started = datetime.now(UTC).isoformat()
    began = time.perf_counter()
    package, data_root = args.package.resolve(), args.data_root.resolve()
    manifest_path = data_root / (
        "data/minutes/2022_2026_continuous/derived_marks/futures_scaled/manifests/processed.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    report = {
        "schema": "intraday_price_audit_v1",
        "started_at_utc": started,
        "package": str(package),
        "data_root": str(data_root),
        "working_directory": str(Path.cwd()),
        "script": str(Path(__file__).resolve()),
        "script_sha256": sha256(Path(__file__)),
        "command": [
            sys.executable,
            "-B",
            "-X",
            "utf8",
            str(Path(__file__).resolve()),
            "--package",
            str(package),
            "--data-root",
            str(data_root),
        ],
        "python": sys.version,
        "numpy": np.__version__,
        "pyarrow": pa.__version__,
        "range": {"start": START, "end_exclusive": END, "minute_points": (END - START) // MINUTE},
        "manifest": {"path": str(manifest_path), "sha256": sha256(manifest_path)},
        "preservation_policy": "Read-only; outputs are stdout only; no engine/replay imports.",
        "failures": [],
        "runs": [],
        "partitions": [],
        "groups": [],
    }
    failures = report["failures"]
    daily_runs = {}
    published_inputs = {}
    base_inputs = None
    for label, run_id in RUNS.items():
        run = package / "corridas" / run_id
        run_manifest = json.loads((run / "run_manifest.json").read_text(encoding="utf-8"))
        code_dir = package / ("codigo_base" if label.startswith("BASE") else "codigo_ejecutado")
        code_checks = []
        for relative, expected in run_manifest["code_files"].items():
            actual = sha256(code_dir / relative) if (code_dir / relative).exists() else None
            code_checks.append({"path": relative, "expected": expected, "actual": actual})
            if actual != expected:
                failures.append({"type": "frozen_code", "run_id": run_id, "path": relative})
        inputs = run_manifest["input_hashes"]
        published_inputs[run_id] = inputs
        manifest_expected = run_manifest["output_hashes"]["source_manifests/processed.json"]
        if report["manifest"]["sha256"] != manifest_expected:
            failures.append({"type": "published_processed_manifest", "run_id": run_id})
        if base_inputs is None:
            base_inputs = inputs
        differences = [
            {"path": path, "base": base_inputs.get(path), "run": inputs.get(path)}
            for path in sorted(base_inputs.keys() | inputs.keys())
            if base_inputs.get(path) != inputs.get(path)
        ]
        with (run / "equity_daily.csv").open(encoding="utf-8", newline="") as stream:
            daily_runs[run_id] = list(csv.DictReader(stream))
        report["runs"].append(
            {
                "label": label,
                "run_id": run_id,
                "frozen_code": str(code_dir),
                "code_checks": code_checks,
                "config": run_manifest["config"],
                "manifest_sha256": sha256(run / "run_manifest.json"),
                "effective_config_sha256": sha256(run / "effective_config.toml"),
                "daily_sha256": sha256(run / "equity_daily.csv"),
                "conventions": run_manifest["conventions"],
                "input_differences_from_base": differences,
            }
        )
    daily_times = np.array(
        [int(row["time_ns"]) for row in next(iter(daily_runs.values()))], dtype=np.int64
    )
    if any(
        [int(row["time_ns"]) for row in rows] != daily_times.tolist()
        for rows in daily_runs.values()
    ):
        failures.append({"type": "daily_time_grids_differ"})
    groups = defaultdict(list)
    for entry in manifest["entries"]:
        if entry["dataset"] in {"minute_bars", "marks", "funding", "gaps"}:
            groups[(entry["dataset"], entry["symbol"], entry.get("market", ""))].append(entry)

    # Short measured window, using Arrow numeric casts rather than Decimal rows.
    window_start = time.perf_counter()
    window_rows, window_files = 0, []
    for key, entries in sorted(groups.items()):
        if key[0] not in {"minute_bars", "marks"}:
            continue
        entry = next(entry for entry in entries if entry.get("date") == "2023-03")
        columns = ["available_at", "close"]
        if key[0] == "minute_bars":
            columns.append("base_volume")
        table = pq.ParquetFile(data_root / entry["path"]).read(columns=columns)
        table = table.filter(
            pc.and_(
                pc.greater_equal(table["available_at"], ANCHOR - 8 * MINUTE),
                pc.less_equal(table["available_at"], REOPEN_AVAILABLE + 9 * MINUTE),
            )
        )
        pc.cast(table["close"], pa.float64()).to_numpy()
        window_rows += len(table)
        window_files.append(entry["path"])
    report["short_window_benchmark"] = {
        "available_start_utc": utc(ANCHOR - 8 * MINUTE),
        "available_end_inclusive_utc": utc(REOPEN_AVAILABLE + 9 * MINUTE),
        "seconds": time.perf_counter() - window_start,
        "rows": window_rows,
        "files": window_files,
        "method": "Arrow selected columns; monthly partition read then window filter; cache state uncontrolled",
    }

    daily_prices, march = {}, {}
    scan_start = time.perf_counter()
    for (dataset, symbol, market), entries in sorted(groups.items()):
        key = (dataset, symbol, market)
        group = {
            "dataset": dataset,
            "symbol": symbol,
            "market": market,
            "partitions": len(entries),
            "rows_disk": 0,
            "rows_in_sample": 0,
            "nonincreasing_times": 0,
            "off_minute_grid": 0,
            "nonpositive_prices": 0,
            "missing_minute_blocks": [],
            "estimated_marks": [],
            "schemas": [],
        }
        zeros, previous_time, first_sample, last_sample = [], None, None, None
        daily_cursor, last_valid, daily_values = 0, None, {}
        march[key] = {}
        for entry in sorted(entries, key=lambda item: item["start"]):
            path = data_root / entry["path"]
            actual = sha256(path) if path.exists() else None
            report["partitions"].append(
                {
                    "dataset": dataset,
                    "symbol": symbol,
                    "market": market,
                    "path": str(path),
                    "expected_sha256": entry["sha256"],
                    "actual_sha256": actual,
                    "rows_manifest": entry["rows"],
                    "source_path": entry.get("source_path"),
                    "source_timestamp_unit": entry.get("timestamp_unit"),
                    "published_sha256_by_run": {
                        run_id: values.get(entry["path"])
                        for run_id, values in published_inputs.items()
                    },
                }
            )
            if actual != entry["sha256"]:
                failures.append({"type": "partition_hash", "path": str(path)})
                if actual is None:
                    continue
            for run_id, values in published_inputs.items():
                if actual != values.get(entry["path"]):
                    failures.append(
                        {
                            "type": "published_partition_hash",
                            "run_id": run_id,
                            "path": entry["path"],
                        }
                    )
            parquet = pq.ParquetFile(path)
            schema = {field.name: str(field.type) for field in parquet.schema_arrow}
            if schema not in group["schemas"]:
                group["schemas"].append(schema)
            if parquet.metadata.num_rows != entry["rows"]:
                failures.append({"type": "partition_row_count", "path": str(path)})
            if dataset == "funding":
                table = parquet.read()
                table = table.filter(
                    pc.and_(
                        pc.greater_equal(table["funding_time"], START),
                        pc.less(table["funding_time"], END),
                    )
                )
                event_times = table["funding_time"].to_numpy()
                available_times = table["available_at"].to_numpy()
                group.update(
                    {
                        "rows_disk": parquet.metadata.num_rows,
                        "rows_in_sample": len(table),
                        "settlement_mark_nulls": table["settlement_mark_price"].null_count,
                        "funding_times_off_exact_hour": int(
                            np.sum(event_times % (60 * MINUTE) != 0)
                        ),
                        "available_minus_funding_time_ns": np.unique(
                            available_times - event_times
                        ).tolist(),
                        "first_record": table.slice(0, 1).to_pylist()[0],
                        "last_record": table.slice(len(table) - 1, 1).to_pylist()[0],
                        "event_clock": "funding_time (events.py:18-25); rate availability remains available_at",
                    }
                )
                continue
            columns = ["available_at", "open_time", "close", "source_file"]
            columns += (
                ["end_time", "base_volume", "trade_count"]
                if dataset == "minute_bars"
                else ["close_time"]
            )
            columns += [
                name for name in ("estimation_method", "anchor_open_time") if name in schema
            ]
            for batch in parquet.iter_batches(batch_size=65536, columns=columns):
                times = batch.column("available_at").to_numpy()
                prices = pc.cast(batch.column("close"), pa.float64()).to_numpy()
                keep = (times >= START) & (times < END)
                selected_times = times[keep]
                group["rows_disk"] += len(batch)
                group["rows_in_sample"] += int(np.sum(keep))
                group["off_minute_grid"] += int(np.sum(times % MINUTE != 0))
                group["nonpositive_prices"] += int(np.sum((prices <= 0) | ~np.isfinite(prices)))
                if len(selected_times):
                    differences = np.diff(selected_times)
                    earlier = selected_times[:-1]
                    if previous_time is not None:
                        differences = np.concatenate(
                            ([int(selected_times[0]) - previous_time], differences)
                        )
                        earlier = np.concatenate(([previous_time], earlier))
                    group["nonincreasing_times"] += int(np.sum(differences <= 0))
                    for left, delta in zip(
                        earlier[differences > MINUTE], differences[differences > MINUTE]
                    ):
                        group["missing_minute_blocks"].append(
                            {
                                "last_available_before": int(left),
                                "first_available_after": int(left + delta),
                                "last_utc": utc(left),
                                "next_utc": utc(left + delta),
                                "absent_grid_points": int(delta // MINUTE - 1),
                            }
                        )
                    first_sample = int(selected_times[0]) if first_sample is None else first_sample
                    last_sample, previous_time = int(selected_times[-1]), int(selected_times[-1])
                valid = np.ones(len(batch), dtype=bool)
                if dataset == "minute_bars":
                    volume = pc.cast(batch.column("base_volume"), pa.float64()).to_numpy()
                    valid = volume > 0
                    zeros.extend(times[(volume == 0) & keep].tolist())
                if "estimation_method" in schema:
                    nonofficial = pc.not_equal(batch.column("estimation_method"), "official")
                    for row in batch.filter(nonofficial).to_pylist():
                        group["estimated_marks"].append(row)
                window = (times >= ANCHOR - 8 * MINUTE) & (times <= REOPEN_AVAILABLE + 9 * MINUTE)
                for row in batch.filter(pa.array(window)).to_pylist():
                    march[key][row["available_at"]] = row
                if dataset == "marks" or market == "spot":
                    valid_batch = batch.filter(pa.array(valid))
                    valid_times = valid_batch.column("available_at").to_numpy()
                    price_strings = valid_batch.column("close").to_numpy(zero_copy_only=False)
                    if len(valid_times):
                        while (
                            daily_cursor < len(daily_times)
                            and daily_times[daily_cursor] < valid_times[0]
                        ):
                            stamp = int(daily_times[daily_cursor])
                            if last_valid is not None:
                                daily_values[stamp] = last_valid
                            daily_cursor += 1
                        stop = int(np.searchsorted(daily_times, valid_times[-1], side="right"))
                        for stamp in daily_times[daily_cursor:stop]:
                            index = int(np.searchsorted(valid_times, stamp, side="right") - 1)
                            daily_values[int(stamp)] = (
                                str(price_strings[index]),
                                int(valid_times[index]),
                            )
                        daily_cursor = stop
                        last_valid = (str(price_strings[-1]), int(valid_times[-1]))
        if dataset != "funding":
            while daily_cursor < len(daily_times):
                if last_valid is not None:
                    daily_values[int(daily_times[daily_cursor])] = last_valid
                daily_cursor += 1
            field = f"{symbol}_{'mark' if dataset == 'marks' else 'spot_price'}"
            if dataset == "marks" or market == "spot":
                daily_prices[field] = daily_values
            group.update(
                {
                    "first_available": first_sample,
                    "last_available": last_sample,
                    "first_utc": utc(first_sample),
                    "last_utc": utc(last_sample),
                    "zero_volume_rows": len(zeros),
                    "zero_volume_blocks": blocks(zeros),
                }
            )
            if (
                group["nonincreasing_times"]
                or group["off_minute_grid"]
                or group["nonpositive_prices"]
            ):
                failures.append({"type": "invalid_price_series", "group": key})
        report["groups"].append(group)
    report["full_scan_seconds"] = time.perf_counter() - scan_start

    daily_checks = []
    for run_id, rows in daily_runs.items():
        errors = []
        for row in rows:
            for field, values in daily_prices.items():
                match = values.get(int(row["time_ns"]))
                if match is None or Decimal(match[0]) != Decimal(row[field]):
                    errors.append(
                        {
                            "time_ns": row["time_ns"],
                            "field": field,
                            "published": row[field],
                            "reconstructed": match,
                        }
                    )
        daily_checks.append(
            {
                "run_id": run_id,
                "days": len(rows),
                "price_comparisons": len(rows) * len(daily_prices),
                "exact_decimal_failures": errors,
            }
        )
        failures.extend(
            {"type": "daily_price_mismatch", "run_id": run_id, **error} for error in errors
        )
    report["daily_price_checks"] = daily_checks
    report["daily_price_examples"] = [
        {
            "time_ns": stamp,
            "timestamp_utc": utc(stamp),
            "prices": {
                field: {
                    "value": values[stamp][0],
                    "available_at": values[stamp][1],
                    "age_ns": stamp - values[stamp][1],
                }
                for field, values in daily_prices.items()
            },
        }
        for stamp in [int(daily_times[0]), 1679702399999999999, int(daily_times[-1])]
    ]
    report["suspension"] = []
    for symbol in ("BTCUSDT", "ETHUSDT"):
        spots, futures, marks = (
            march[(dataset, symbol, market)]
            for dataset, market in (
                ("minute_bars", "spot"),
                ("minute_bars", "futures"),
                ("marks", "futures"),
            )
        )
        spot_anchor, future_anchor = spots[ANCHOR], futures[ANCHOR]
        proxy = []
        for stamp in range(ANCHOR, REOPEN_AVAILABLE, MINUTE):
            future = futures.get(stamp)
            if future is None or Decimal(future["base_volume"]) <= 0:
                failures.append(
                    {"type": "proxy_unavailable_future", "symbol": symbol, "time_ns": stamp}
                )
                continue
            proxy.append(
                (
                    stamp,
                    Decimal(spot_anchor["close"])
                    * Decimal(future["close"])
                    / Decimal(future_anchor["close"]),
                )
            )
        samples = []
        for stamp in [
            ANCHOR - MINUTE,
            ANCHOR,
            ANCHOR + MINUTE,
            1679659200000000000,
            1679661600000000000,
            1679661660000000000,
            REOPEN_AVAILABLE - MINUTE,
            REOPEN_AVAILABLE,
            REOPEN_AVAILABLE + MINUTE,
        ]:
            raw_spot = spots.get(stamp)
            valid = raw_spot is not None and Decimal(raw_spot["base_volume"]) > 0
            observed = raw_spot if valid else spot_anchor
            samples.append(
                {
                    "time_ns": stamp,
                    "timestamp_utc": utc(stamp),
                    "spot_source": raw_spot,
                    "original_spot": observed["close"],
                    "original_spot_available_at": observed["available_at"],
                    "original_spot_age_ns": stamp - observed["available_at"],
                    "reason": "observed_positive_volume"
                    if valid
                    else (
                        "carry_zero_volume_documented_closure"
                        if raw_spot is not None
                        else "carry_absent_row_documented_closure"
                    ),
                    "future": futures[stamp],
                    "risk_mark": marks[stamp],
                    "proxy_applied": ANCHOR <= stamp < REOPEN_AVAILABLE,
                    "fixed_anchor_proxy": str(
                        Decimal(spot_anchor["close"])
                        * Decimal(futures[stamp]["close"])
                        / Decimal(future_anchor["close"])
                    )
                    if ANCHOR <= stamp <= REOPEN_AVAILABLE
                    else None,
                }
            )
        reopen_proxy = (
            Decimal(spot_anchor["close"])
            * Decimal(futures[REOPEN_AVAILABLE]["close"])
            / Decimal(future_anchor["close"])
        )
        raw_path = (
            data_root
            / f"data/minutes/2022_2026_continuous/raw/spot/klines/{symbol}/{symbol}-1m-2023-03.zip"
        )
        raw_samples = []
        with zipfile.ZipFile(raw_path) as archive:
            with archive.open(archive.namelist()[0]) as stream:
                for row in csv.reader(io.TextIOWrapper(stream, encoding="utf-8")):
                    if row[0].isdigit() and int(row[0]) in {
                        1679657220000,
                        1679657280000,
                        1679661540000,
                        1679666400000,
                    }:
                        raw_samples.append(row)
        lowest = min(proxy, key=lambda item: item[1])
        report["suspension"].append(
            {
                "symbol": symbol,
                "anchor_spot": spot_anchor,
                "anchor_future": future_anchor,
                "proxy_method": "valoracion_proxy_hipotetica: S(anchor) * F(t) / F(anchor)",
                "anchor_available_at": ANCHOR,
                "reopening_spot_available_at": REOPEN_AVAILABLE,
                "missing_new_spot_grid_points": (REOPEN_AVAILABLE - ANCHOR) // MINUTE - 1,
                "proxy_points_including_anchor": len(proxy),
                "proxy_missing_points": (REOPEN_AVAILABLE - ANCHOR) // MINUTE - len(proxy),
                "proxy_minimum": {
                    "time_ns": lowest[0],
                    "timestamp_utc": utc(lowest[0]),
                    "price": str(lowest[1]),
                },
                "reopening_spot": spots[REOPEN_AVAILABLE]["close"],
                "diagnostic_proxy_at_reopening": str(reopen_proxy),
                "reopening_observed_minus_proxy": str(
                    Decimal(spots[REOPEN_AVAILABLE]["close"]) - reopen_proxy
                ),
                "samples": samples,
                "raw_archive": str(raw_path),
                "raw_archive_sha256": sha256(raw_path),
                "raw_sample_rows_12_binance_fields": raw_samples,
            }
        )
    report["finished_at_utc"] = datetime.now(UTC).isoformat()
    report["elapsed_seconds"] = time.perf_counter() - began
    report["passed"] = not failures
    json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
