"""Coverage and integrity validation for historical inputs."""

from __future__ import annotations

import csv
import hashlib
import json
import zipfile
from bisect import bisect_left
from decimal import Decimal, InvalidOperation
from itertools import pairwise
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from ..config import DAY, HOUR, SECOND, Config, iso, timestamp
from .normalize import _funding_calendar_times
from .rules import RuleBook

_REQUIRED_SCHEMAS = {
    "trades": {
        "symbol": "string",
        "market": "string",
        "trade_id": "string",
        "event_time": "int64",
        "available_at": "int64",
        "price": "string",
        "quantity": "string",
        "source_file": "string",
    },
    "funding": {
        "symbol": "string",
        "funding_time": "int64",
        "available_at": "int64",
        "funding_rate": "string",
        "interval_hours": "string",
        "settlement_mark_price": "string",
        "source_file": "string",
        "interval_verified": "bool",
    },
    "marks": {
        "symbol": "string",
        "open_time": "int64",
        "close_time": "int64",
        "available_at": "int64",
        "open": "string",
        "high": "string",
        "low": "string",
        "close": "string",
        "source_file": "string",
    },
}


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _required_keys(config: Config):
    for symbol in config.symbols:
        yield "trades", symbol, "spot"
        yield "trades", symbol, "futures"
        yield "marks", symbol, "futures"
        yield "funding", symbol, "futures"


def _scoped_parts(parts: list[dict], start: int, end: int, *, antecedent: bool) -> list[dict]:
    """Partition bounds are inclusive; replay also consumes one prior observation."""
    selected = [
        entry for entry in parts if int(entry["end"]) >= start and int(entry["start"]) < end
    ]
    if antecedent:
        prior = [entry for entry in parts if int(entry["end"]) < start]
        latest = max((int(entry["end"]) for entry in prior), default=None)
        known_prior = max(
            (int(entry["start"]) for entry in selected if int(entry["start"]) < start),
            default=None,
        )
        if latest is not None and (known_prior is None or latest >= known_prior):
            selected.extend(entry for entry in prior if int(entry["end"]) == latest)
    return selected


def _adjacent_month(month: str, offset: int) -> str:
    year, number = map(int, month.split("-"))
    year, zero_based_month = divmod(year * 12 + number - 1 + offset, 12)
    return f"{year:04d}-{zero_based_month + 1:02d}"


def _funding_calendar(
    config: Config, root: Path, symbol: str, start: int, end: int
) -> dict[int, tuple[Decimal, Decimal]]:
    """Read independently hashed monthly schedules, including interval antecedents."""
    manifest_path = root / config.data_dir / "manifests" / "download.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    by_month: dict[str, list[dict]] = {}
    for entry in manifest.get("entries", []):
        if entry.get("dataset") == "funding_calendar" and entry.get("symbol") == symbol:
            month = iso(timestamp(entry["start"]))[:7]
            by_month.setdefault(month, []).append(entry)
    calendar: dict[int, tuple[Decimal, Decimal]] = {}

    def read_month(month: str):
        entries = by_month.get(month, [])
        if not entries:
            raise ValueError(f"missing independent funding calendar month: {month}")
        month_start = timestamp(f"{month}-01T00:00:00Z")
        month_end = timestamp(f"{_adjacent_month(month, 1)}-01T00:00:00Z")
        for entry in entries:
            if entry.get("status") not in {"cached", "downloaded"}:
                raise ValueError(f"unverified independent funding calendar: {entry['path']}")
            path = root / entry["path"]
            if _hash(path) != entry.get("sha256"):
                raise ValueError(f"independent funding calendar hash mismatch: {entry['path']}")
            for time_ms, value in _funding_calendar_times(path).items():
                time_ns = time_ms * 1_000_000
                if not month_start <= time_ns < month_end:
                    raise ValueError(f"funding calendar timestamp outside archive month: {month}")
                interval, rate = value
                if not interval.is_finite() or interval <= 0 or not rate.is_finite():
                    raise ValueError(f"invalid independent funding calendar value: {month}")
                previous = calendar.get(time_ns)
                if previous is not None and previous != value:
                    raise ValueError(f"conflicting independent funding calendar at {time_ns}")
                calendar[time_ns] = value

    first_month = month = iso(start)[:7]
    last_month = iso(end - 1)[:7]
    while month <= last_month:
        read_month(month)
        month = _adjacent_month(month, 1)
    # The first consumed funding observation precedes the warmup boundary; its
    # own interval also needs the preceding independently published settlement.
    while sum(time_ns < start for time_ns in calendar) < 2:
        first_month = _adjacent_month(first_month, -1)
        read_month(first_month)
    return calendar


def _validate_funding(
    config: Config,
    root: Path,
    symbol: str,
    parts: list[dict],
    start: int,
    end: int,
    coverage: dict,
    issues: list[str],
):
    records: list[dict] = []
    antecedents: list[dict] = []
    try:
        for entry in parts:
            for batch in pq.ParquetFile(root / entry["path"]).iter_batches():
                for record in batch.to_pylist():
                    time_ns = int(record["funding_time"])
                    if start <= time_ns < end:
                        records.append(record)
                    elif time_ns < start:
                        if not antecedents or time_ns > int(antecedents[0]["funding_time"]):
                            antecedents = [record]
                        elif time_ns == int(antecedents[0]["funding_time"]):
                            antecedents.append(record)
    except (KeyError, OSError, TypeError, ValueError, pa.ArrowException) as exc:
        coverage["status"] = "invalid"
        issues.append(f"unreadable funding rows: {symbol}: {exc}")
    records = antecedents + records
    times = [int(record["funding_time"]) for record in records]
    coverage["observed_start"] = min(times, default=None)
    coverage["observed_end"] = max(times, default=None)
    if not antecedents:
        coverage["status"] = "unknown"
        issues.append(f"funding warmup or antecedent missing: {symbol}")
    if any(
        record["available_at"] != int(record["funding_time"]) + 60 * SECOND for record in records
    ):
        coverage["status"] = "invalid"
        issues.append(f"funding availability mismatch: {symbol}")

    marks_complete = bool(records)
    for record in records:
        try:
            mark = Decimal(str(record["settlement_mark_price"]))
            marks_complete &= mark.is_finite() and mark > 0
        except KeyError, InvalidOperation:
            marks_complete = False
    if not marks_complete:
        coverage["status"] = "unknown"
        issues.append(f"funding settlement mark missing: {symbol}")

    try:
        calendar = _funding_calendar(config, root, symbol, start, end)
        ordered_times = sorted(calendar)
        antecedent = max(time_ns for time_ns in ordered_times if time_ns < start)
        expected = {antecedent, *(time_ns for time_ns in ordered_times if start <= time_ns < end)}
        verified = len(times) == len(set(times)) and set(times) == expected
        for record in records:
            time_ns = int(record["funding_time"])
            index = bisect_left(ordered_times, time_ns)
            if index == 0 or time_ns not in calendar:
                verified = False
                continue
            previous = ordered_times[index - 1]
            scheduled_interval, rate = calendar[time_ns]
            verified &= (
                record["symbol"] == symbol
                and record["interval_verified"] is True
                and Decimal(record["funding_rate"]) == rate
                and Decimal(record["interval_hours"]) == Decimal(time_ns - previous) / Decimal(HOUR)
                and scheduled_interval == Decimal(time_ns // HOUR - previous // HOUR)
            )
        if not verified:
            raise ValueError("settlement rows differ from the independent calendar or intervals")
        coverage["checks"].append("independent_funding_calendar")
    except (
        csv.Error,
        KeyError,
        OSError,
        TypeError,
        UnicodeError,
        ValueError,
        InvalidOperation,
        zipfile.BadZipFile,
    ) as exc:
        coverage["status"] = "unknown"
        issues.append(f"funding calendar unverified: {symbol}: {exc}")


def validate_data(config: Config, root: Path, scope: str = "sample") -> dict:
    """Validate the requested range, retaining unknown data as explicit incompleteness."""
    if scope not in {"sample", "full"}:
        raise ValueError("scope must be 'sample' or 'full'")
    root = Path(root).resolve()
    data_root = root / config.data_dir
    manifest_path = data_root / "manifests" / "processed.json"
    start = timestamp(config.sample_start if scope == "sample" else config.start)
    end = timestamp(config.sample_end if scope == "sample" else config.end)
    funding_start = start - (config.window_hours + 24) * HOUR
    issues: list[str] = []
    entries: list[dict] = []
    if not manifest_path.exists():
        issues.append("missing processed manifest")
    else:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        entries = payload.get("entries", [])
        issues.extend(f"normalization error: {item}" for item in payload.get("errors", []))

    grouped: dict[tuple[str, str, str], list[dict]] = {}
    for entry in entries:
        if int(entry["start"]) > int(entry["end"]):
            issues.append(f"invalid partition bounds: {entry['path']}")
            continue
        grouped.setdefault((entry["dataset"], entry["symbol"], entry["market"]), []).append(entry)

    coverage: list[dict] = []
    for dataset, symbol, market in _required_keys(config):
        key = (dataset, symbol, market)
        lower = funding_start if dataset == "funding" else start
        parts = _scoped_parts(grouped.get(key, []), lower, end, antecedent=True)
        row = {
            "dataset": dataset,
            "symbol": symbol,
            "market": market,
            "expected_start": funding_start if dataset == "funding" else start,
            "expected_end": end,
            "observed_start": min((int(item["start"]) for item in parts), default=None),
            "observed_end": max((int(item["end"]) for item in parts), default=None),
            "files": len(parts),
            "rows": sum(int(item.get("rows", 0)) for item in parts),
            "duplicates_removed": sum(int(item.get("duplicate_count", 0)) for item in parts),
            "conflicts": sum(int(item.get("conflict_count", 0)) for item in parts),
            "status": "complete",
            "checks": [],
        }
        if not parts:
            row["status"] = "unknown"
            issues.append(f"missing processed file: {dataset}/{symbol}/{market}")
        if dataset in {"trades", "marks"}:
            dates = {entry.get("date", iso(int(entry["start"]))[:10]) for entry in parts}
            required_dates = {
                iso(day * DAY)[:10] for day in range(start // DAY, (end - 1) // DAY + 1)
            }
            missing = sorted(required_dates - dates)
            if missing:
                row["status"] = "unknown"
                issues.append(
                    f"missing archive date: {dataset}/{symbol}/{market}: {len(missing)} days, first {missing[0]}"
                )
        verified_parts: list[dict] = []
        for entry in parts:
            path = root / entry["path"]
            if not path.exists():
                row["status"] = "unknown"
                issues.append(f"missing processed file: {entry['path']}")
                continue
            actual = _hash(path)
            if actual != entry.get("sha256"):
                row["status"] = "invalid"
                issues.append(f"hash mismatch: {entry['path']}")
            else:
                row["checks"].append(f"sha256:{entry['path']}")
                try:
                    schema = pq.read_schema(path)
                    actual_schema = {field.name: str(field.type) for field in schema}
                    expected_schema = _REQUIRED_SCHEMAS[dataset]
                    if any(
                        actual_schema.get(name) != kind for name, kind in expected_schema.items()
                    ):
                        row["status"] = "invalid"
                        issues.append(f"schema mismatch: {entry['path']}")
                    elif entry.get("schema") and entry["schema"] != actual_schema:
                        row["status"] = "invalid"
                        issues.append(f"manifest schema mismatch: {entry['path']}")
                    else:
                        row["checks"].append(f"schema:{entry['path']}")
                        verified_parts.append(entry)
                except (KeyError, OSError, pa.ArrowException) as exc:
                    row["status"] = "invalid"
                    issues.append(f"unreadable parquet schema: {entry['path']}: {exc}")
            if not entry.get("complete", False):
                row["status"] = "unknown"
                issues.append(f"incomplete source file: {entry['path']}")
            if int(entry.get("conflict_count", 0)):
                row["status"] = "invalid"
                issues.append(f"conflicting duplicates: {entry['path']}")
        if dataset == "trades" and parts:
            values = [entry.get("trade_id_continuous") for entry in parts]
            if any(value is False for value in values):
                row["status"] = "unknown"
                issues.append(f"unresolved trade-id discontinuity: {symbol}/{market}")
            ordered_parts = sorted(parts, key=lambda entry: int(entry.get("start", 0)))
            endpoints = [
                (entry.get("first_trade_id"), entry.get("last_trade_id"))
                for entry in ordered_parts
                if entry.get("first_trade_id") is not None
            ]
            for previous, current in pairwise(endpoints):
                try:
                    continuous = int(current[0]) == int(previous[1]) + 1
                except TypeError, ValueError:
                    continuous = False
                if not continuous:
                    row["status"] = "unknown"
                    issues.append(
                        f"unresolved cross-file trade-id discontinuity: {symbol}/{market}"
                    )
                    break
        if (
            dataset == "marks"
            and parts
            and not all(entry.get("minute_coverage_complete") is True for entry in parts)
        ):
            row["status"] = "unknown"
            issues.append(f"incomplete one-minute mark coverage: {symbol}")
        if dataset == "marks" and parts:
            available = set()
            for entry in parts:
                path = root / entry["path"]
                if not path.exists():
                    continue
                try:
                    for batch in pq.ParquetFile(path).iter_batches(columns=["available_at"]):
                        available.update(
                            int(t)
                            for t in batch.column(0).to_pylist()
                            if start - 60_000_000_000 < t < end
                        )
                except pa.ArrowException, KeyError, TypeError, IndexError:
                    continue
            first = (start // 60_000_000_000) * 60_000_000_000
            expected_count = (end - 1 - first) // 60_000_000_000 + 1
            present_count = sum(
                1 for t in available if t >= first and (t - first) % 60_000_000_000 == 0
            )
            if expected_count > present_count:
                row["status"] = "unknown"
                issues.append(
                    f"missing closed mark minute or initial antecedent: {symbol}, {expected_count - present_count} minutes"
                )
        if dataset == "funding" and parts:
            _validate_funding(config, root, symbol, verified_parts, funding_start, end, row, issues)
        coverage.append(row)

    rules_path = root / config.rules_file
    if not rules_path.exists():
        issues.append("missing historical market rules")
    else:
        try:
            rulebook = RuleBook.load(rules_path)
            for symbol in config.symbols:
                for market in ("spot", "futures"):
                    if (
                        rulebook.get(symbol, market, start) is None
                        or rulebook.get(symbol, market, end - 1) is None
                    ):
                        issues.append(f"missing verified rules: {symbol}/{market}")
                    boundaries = {start, end - 1, *rulebook.transition_times(start, end - 1)}
                    for boundary in sorted(boundaries):
                        if rulebook.get(symbol, market, boundary) is None:
                            issues.append(
                                f"rule coverage gap: {symbol}/{market} at {iso(boundary)}"
                            )
                            break
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            issues.append(f"invalid historical market rules: {exc}")

    status = (
        "complete"
        if not issues and all(row["status"] == "complete" for row in coverage)
        else "incomplete_data"
    )
    full_baseline = (
        status == "complete"
        and scope == "full"
        and start == timestamp(config.start)
        and end == timestamp(config.end)
    )
    result = {
        "status": status,
        "historical": True,
        "scope": scope,
        "start": start,
        "end": end,
        "funding_warmup_start": funding_start,
        "full_baseline_coverage": full_baseline,
        "issues": sorted(set(issues)),
        "coverage": coverage,
    }

    manifests = data_root / "manifests"
    manifests.mkdir(parents=True, exist_ok=True)
    (manifests / "coverage.json").write_text(
        json.dumps(result, indent=2, sort_keys=True), encoding="utf-8"
    )
    csv_path = manifests / "data_coverage.csv"
    fields = [
        "dataset",
        "symbol",
        "market",
        "expected_start",
        "expected_end",
        "observed_start",
        "observed_end",
        "files",
        "rows",
        "duplicates_removed",
        "conflicts",
        "status",
        "checks",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in coverage:
            value = dict(row)
            value["checks"] = ";".join(value["checks"])
            writer.writerow(value)
    lines = [
        "# Informe de calidad de datos",
        "",
        f"Estado: **{status}**. Datos históricos: **sí**.",
        f"Rango solicitado: `{iso(start)}` hasta antes de `{iso(end)}`.",
        f"Inicio exigido para funding: `{iso(funding_start)}` (ventana más 24 horas y antecedente).",
        f"Cobertura completa del baseline: **{'sí' if full_baseline else 'no'}**.",
        "",
        "## Problemas",
        "",
    ]
    lines.extend(
        f"- {issue}" for issue in result["issues"] or ["Ninguno para el alcance solicitado."]
    )
    lines.extend(
        [
            "",
            "La ausencia de un archivo se trata como información desconocida, no como inactividad ni funding cero.",
        ]
    )
    (manifests / "data_quality_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return result
