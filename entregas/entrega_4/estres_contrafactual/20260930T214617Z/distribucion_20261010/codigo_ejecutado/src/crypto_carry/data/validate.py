"""Coverage and integrity validation for historical inputs."""

from __future__ import annotations

import csv
import hashlib
import json
import zipfile
from bisect import bisect_left
from dataclasses import asdict
from decimal import Decimal, InvalidOperation
from itertools import pairwise
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from ..config import DAY, HOUR, SECOND, Config, iso, timestamp
from ..models import Funding, Mark
from .funding_proxy import MINUTE, resolve_funding_mark
from .market_calendar import closed_minute_count, closure_for_minute, quality_closures
from .normalize import VWAP_OHLC_REL_TOLERANCE, _funding_calendar_times
from .prescribed import prescribed_rules, research_assumptions
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
    "minute_prices": {
        "symbol": "string",
        "market": "string",
        "reference_id": "string",
        "event_time": "int64",
        "available_at": "int64",
        "price": "string",
        "source_file": "string",
    },
    "minute_volumes": {
        "symbol": "string",
        "market": "string",
        "open_time": "int64",
        "close_time": "int64",
        "available_at": "int64",
        "quantity": "string",
        "trade_count": "int64",
        "source_file": "string",
    },
    "minute_bars": {
        "symbol": "string",
        "market": "string",
        "open_time": "int64",
        "end_time": "int64",
        "available_at": "int64",
        "open": "string",
        "high": "string",
        "low": "string",
        "close": "string",
        "base_volume": "string",
        "quote_volume": "string",
        "trade_count": "int64",
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
        if config.execution_model == "next_minute_vwap":
            yield "minute_bars", symbol, "spot"
            yield "minute_bars", symbol, "futures"
        elif config.execution_model == "minute_open":
            yield "minute_prices", symbol, "spot"
            yield "minute_volumes", symbol, "spot"
            yield "minute_prices", symbol, "futures"
            yield "minute_volumes", symbol, "futures"
        else:
            yield "trades", symbol, "spot"
            yield "trades", symbol, "futures"
        if (
            config.execution_model != "next_minute_vwap"
            and getattr(config, "signal_price_model", "execution_default") == "closed_minute"
        ):
            yield "minute_bars", symbol, "spot"
            yield "minute_bars", symbol, "futures"
        yield "marks", symbol, "futures"
        yield "funding", symbol, "futures"


def _minute_rows(root: Path, parts: list[dict], columns: list[str]):
    for entry in sorted(parts, key=lambda item: (int(item["start"]), item["path"])):
        for batch in pq.ParquetFile(root / entry["path"]).iter_batches(columns=columns):
            yield from batch.to_pylist()


def _validate_minute_bars(
    root: Path,
    symbol: str,
    market: str,
    parts: list[dict],
    start: int,
    end: int,
    coverage: dict,
    issues: list[str],
) -> None:
    """Validate closed bars, including the bar available exactly at sample start."""
    columns = list(_REQUIRED_SCHEMAS["minute_bars"])
    expected_end = start
    previous_end: int | None = None
    missing_count = 0
    documented_count = 0
    invalid = False
    volume_mismatch = False
    vwap_outside = False
    observed = 0
    try:
        for row in _minute_rows(root, parts, columns):
            bar_end = int(row["end_time"])
            if bar_end < start:
                continue
            if bar_end >= end:
                break
            observed += 1
            open_time = int(row["open_time"])
            if previous_end is not None and bar_end <= previous_end:
                invalid = True
            previous_end = bar_end
            if bar_end > expected_end:
                missing = (bar_end - expected_end) // MINUTE
                documented = min(
                    missing,
                    closed_minute_count(symbol, market, expected_end - MINUTE, bar_end - MINUTE),
                )
                documented_count += documented
                missing_count += missing - documented
            elif bar_end < expected_end:
                invalid = True
            expected_end = max(expected_end, bar_end + MINUTE)
            try:
                open_price = Decimal(row["open"])
                high = Decimal(row["high"])
                low = Decimal(row["low"])
                close = Decimal(row["close"])
                base_volume = Decimal(row["base_volume"])
                quote_volume = Decimal(row["quote_volume"])
                trade_count = int(row["trade_count"])
                prices = (open_price, high, low, close)
                closure = closure_for_minute(symbol, market, open_time)
                row_valid = (
                    row["symbol"] == symbol
                    and row["market"] == market
                    and open_time % MINUTE == 0
                    and bar_end == open_time + MINUTE
                    and int(row["available_at"]) == bar_end
                    and all(value.is_finite() and value > 0 for value in prices)
                    and low <= open_price <= high
                    and low <= close <= high
                    and low <= high
                    and base_volume.is_finite()
                    and base_volume >= 0
                    and quote_volume.is_finite()
                    and quote_volume >= 0
                    and trade_count >= 0
                    and (closure is None or trade_count == 0)
                )
                consistent_zero = (base_volume == 0) == (quote_volume == 0)
                consistent_count = trade_count != 0 or (base_volume == 0 and quote_volume == 0)
                if not consistent_zero or not consistent_count:
                    volume_mismatch = True
                if base_volume > 0 and quote_volume > 0:
                    vwap = quote_volume / base_volume
                    tolerance = max(abs(low), abs(high), Decimal(1)) * VWAP_OHLC_REL_TOLERANCE
                    if not low - tolerance <= vwap <= high + tolerance:
                        vwap_outside = True
                if closure is not None:
                    documented_count += 1
            except InvalidOperation, KeyError, TypeError, ValueError:
                row_valid = False
            if not row_valid:
                invalid = True
        if expected_end < end:
            missing = (end - expected_end) // MINUTE
            documented = min(
                missing,
                closed_minute_count(symbol, market, expected_end - MINUTE, end - MINUTE),
            )
            documented_count += documented
            missing_count += missing - documented
    except (KeyError, OSError, TypeError, ValueError, pa.ArrowException) as exc:
        invalid = True
        issues.append(f"unreadable closed minute bars: {symbol}/{market}: {exc}")

    if missing_count or observed == 0:
        coverage["status"] = "unknown"
        count = missing_count or (end - start) // MINUTE
        issues.append(f"missing closed minute bar: {symbol}/{market}: {count} minutes")
    else:
        coverage["checks"].append("complete_closed_bar_coverage")
    if documented_count:
        coverage["checks"].append("documented_market_closure")
    if invalid:
        coverage["status"] = "invalid"
        issues.append(f"invalid closed minute bar: {symbol}/{market}")
    if volume_mismatch:
        coverage["status"] = "invalid"
        issues.append(f"closed bar volume mismatch: {symbol}/{market}")
    if vwap_outside:
        coverage["status"] = "invalid"
        issues.append(
            f"closed bar VWAP outside OHLC tolerance {VWAP_OHLC_REL_TOLERANCE}: {symbol}/{market}"
        )
    if not invalid and not volume_mismatch and not vwap_outside:
        coverage["checks"].append("closed_bar_vwap_within_ohlc")


def _validate_minute_pair(
    root: Path,
    symbol: str,
    market: str,
    price_parts: list[dict],
    volume_parts: list[dict],
    start: int,
    end: int,
    price_coverage: dict,
    volume_coverage: dict,
    issues: list[str],
) -> None:
    """Stream exact minute coverage and positive-count price membership."""
    price_columns = [
        "symbol",
        "market",
        "reference_id",
        "event_time",
        "available_at",
        "price",
    ]
    volume_columns = [
        "symbol",
        "market",
        "open_time",
        "close_time",
        "available_at",
        "quantity",
        "trade_count",
    ]
    prices = iter(())
    current_price = None
    expected_open = start
    gap_count = 0
    documented_closure_minutes = 0
    membership_mismatch = False
    volume_invalid = False
    previous_price_time: int | None = None

    def scoped_price(raw: dict | None) -> dict | None:
        nonlocal previous_price_time
        while raw is not None and int(raw["event_time"]) < start:
            raw = next(prices, None)
        if raw is not None:
            value = int(raw["event_time"])
            if previous_price_time is not None and value <= previous_price_time:
                raise ValueError("minute prices are not strictly chronological and unique")
            previous_price_time = value
        return raw

    try:
        prices = iter(_minute_rows(root, price_parts, price_columns))
        current_price = next(prices, None)
        current_price = scoped_price(current_price)
        previous_volume_time: int | None = None
        for volume in _minute_rows(root, volume_parts, volume_columns):
            open_time = int(volume["open_time"])
            if open_time < start:
                continue
            if open_time >= end:
                break
            if previous_volume_time is not None and open_time <= previous_volume_time:
                volume_invalid = True
            previous_volume_time = open_time
            if open_time > expected_open:
                missing = (open_time - expected_open) // MINUTE
                documented = min(
                    missing, closed_minute_count(symbol, market, expected_open, open_time)
                )
                documented_closure_minutes += documented
                gap_count += missing - documented
            elif open_time < expected_open:
                volume_invalid = True
            expected_open = max(expected_open, open_time + MINUTE)
            try:
                quantity = Decimal(volume["quantity"])
                count = int(volume["trade_count"])
                close_time = int(volume["close_time"])
                available_at = int(volume["available_at"])
                closure = closure_for_minute(symbol, market, open_time)
                standard_timing = available_at == open_time + MINUTE and close_time in {
                    open_time + MINUTE - 1_000,
                    open_time + MINUTE - 1_000_000,
                }
                early_closed_zero = (
                    closure is not None
                    and count == 0
                    and quantity == 0
                    and open_time <= close_time < open_time + MINUTE - 1_000_000
                    and available_at - close_time in {1_000, 1_000_000}
                )
                valid_volume = (
                    volume["symbol"] == symbol
                    and volume["market"] == market
                    and open_time % MINUTE == 0
                    and (standard_timing or early_closed_zero)
                    and quantity.is_finite()
                    and quantity >= 0
                    and count >= 0
                    and (count != 0 or quantity == 0)
                    and (closure is None or count == 0)
                )
                if closure is not None:
                    documented_closure_minutes += 1
            except InvalidOperation, KeyError, TypeError, ValueError:
                valid_volume = False
                count = 0
            if not valid_volume:
                volume_invalid = True

            while current_price is not None and int(current_price["event_time"]) < open_time:
                if int(current_price["event_time"]) >= start:
                    membership_mismatch = True
                current_price = scoped_price(next(prices, None))
            has_price = current_price is not None and int(current_price["event_time"]) == open_time
            if has_price:
                try:
                    price = Decimal(current_price["price"])
                    valid_price = (
                        current_price["symbol"] == symbol
                        and current_price["market"] == market
                        and current_price["reference_id"] == f"bar:{symbol}:{market}:{open_time}"
                        and int(current_price["available_at"]) == open_time
                        and price.is_finite()
                        and price > 0
                    )
                except InvalidOperation, KeyError, TypeError, ValueError:
                    valid_price = False
                if not valid_price:
                    membership_mismatch = True
                current_price = scoped_price(next(prices, None))
            if has_price != (count > 0):
                membership_mismatch = True
        if expected_open < end:
            missing = (end - expected_open) // MINUTE
            documented = min(missing, closed_minute_count(symbol, market, expected_open, end))
            documented_closure_minutes += documented
            gap_count += missing - documented
        while current_price is not None and int(current_price["event_time"]) < end:
            membership_mismatch = True
            current_price = scoped_price(next(prices, None))
    except (KeyError, OSError, TypeError, ValueError, pa.ArrowException) as exc:
        volume_invalid = True
        membership_mismatch = True
        issues.append(f"unreadable minute rows: {symbol}/{market}: {exc}")

    if gap_count:
        volume_coverage["status"] = "unknown"
        issues.append(f"missing minute volume: {symbol}/{market}: {gap_count} minutes")
    else:
        volume_coverage["checks"].append("complete_minute_volume_coverage")
    if documented_closure_minutes:
        volume_coverage["checks"].append("documented_market_closure")
    if volume_invalid:
        volume_coverage["status"] = "invalid"
        issues.append(f"invalid minute volume: {symbol}/{market}")
    if membership_mismatch:
        price_coverage["status"] = "invalid"
        issues.append(f"price-volume membership mismatch: {symbol}/{market}")
    else:
        price_coverage["checks"].append("price_volume_membership")


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
    *,
    mark_parts: list[dict] | None = None,
    audit: list[dict] | None = None,
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
    if config.analysis_mode == "prescribed_research":
        try:
            candidates = _proxy_candidates(config, root, records, mark_parts or [])
            for raw in records:
                event = Funding(
                    symbol=raw["symbol"],
                    funding_time=int(raw["funding_time"]),
                    available_at=int(raw["available_at"]),
                    funding_rate=Decimal(raw["funding_rate"]),
                    interval_hours=Decimal(raw["interval_hours"]),
                    settlement_mark_price=(
                        Decimal(raw["settlement_mark_price"])
                        if raw["settlement_mark_price"] is not None
                        else None
                    ),
                    source_file=raw["source_file"],
                    interval_verified=raw["interval_verified"],
                )
                boundary = event.funding_time // MINUTE * MINUTE
                resolved = resolve_funding_mark(event, candidates.get(boundary), config)
                if audit is not None:
                    audit.append(
                        {
                            k: str(v) if isinstance(v, Decimal) else v
                            for k, v in asdict(resolved).items()
                        }
                    )
            coverage["checks"].append("causal_funding_mark_assumptions")
        except (
            KeyError,
            OSError,
            TypeError,
            ValueError,
            ArithmeticError,
            pa.ArrowException,
        ) as exc:
            marks_complete = False
            issues.append(f"funding proxy unavailable: {symbol}: {exc}")
    else:
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


def _proxy_candidates(
    config: Config, root: Path, funding: list[dict], parts: list[dict]
) -> dict[int, Mark]:
    """Sparse lookup from already hash/schema-checked one-minute partitions."""
    required = {
        int(row["funding_time"]) // MINUTE * MINUTE
        for row in funding
        if row["settlement_mark_price"] is None
        and int(row["funding_time"]) >= timestamp(config.start)
    }
    result = {}
    for part in parts:
        if not any(int(part["start"]) <= t <= int(part["end"]) for t in required):
            continue
        for batch in pq.ParquetFile(root / part["path"]).iter_batches():
            for raw in batch.to_pylist():
                boundary = int(raw["open_time"]) + MINUTE
                if boundary not in required:
                    continue
                mark = Mark(
                    **{
                        k: Decimal(v) if k in {"open", "high", "low", "close"} else v
                        for k, v in raw.items()
                        if k in _REQUIRED_SCHEMAS["marks"]
                    }
                )
                if boundary in result and result[boundary] != mark:
                    raise ValueError(f"Conflicting proxy candles at {iso(boundary)}")
                result[boundary] = mark
    return result


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
    payload: dict = {}
    if not manifest_path.exists():
        issues.append("missing processed manifest")
    else:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        entries = payload.get("entries", [])
        issues.extend(f"normalization error: {item}" for item in payload.get("errors", []))
    manifest_kind = payload.get("kind") if manifest_path.exists() else None
    from .mark_gaps import verify_mark_derivation

    mark_gap_audit = []
    try:
        mark_gap_audit = verify_mark_derivation(config, root, payload)
    except (ValueError, KeyError, OSError, TypeError, pa.ArrowException) as exc:
        issues.append(f"invalid mark gap derivation: {exc}")
    closed_signals = getattr(config, "signal_price_model", "execution_default") == "closed_minute"
    minute_model = config.execution_model in {"minute_open", "next_minute_vwap"} or closed_signals
    if minute_model and manifest_kind != "minute_market_data":
        issues.append(
            f"incompatible processed dataset: {config.execution_model} requires minute_market_data"
        )
    if not minute_model and manifest_kind == "minute_market_data":
        issues.append(
            f"incompatible processed dataset: {config.execution_model} requires trade_market_data"
        )

    grouped: dict[tuple[str, str, str], list[dict]] = {}
    for entry in entries:
        if int(entry["start"]) > int(entry["end"]):
            issues.append(f"invalid partition bounds: {entry['path']}")
            continue
        grouped.setdefault((entry["dataset"], entry["symbol"], entry["market"]), []).append(entry)

    coverage: list[dict] = []
    verified_marks = {}
    funding_mark_audit = []
    verified_by_key: dict[tuple[str, str, str], list[dict]] = {}
    coverage_by_key: dict[tuple[str, str, str], dict] = {}
    effective = config.changed(start=iso(start), end=iso(end))
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
        if dataset in {"trades", "marks"} and manifest_kind != "minute_market_data":
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
        if dataset == "marks":
            verified_marks[symbol] = verified_parts
        if dataset == "funding" and parts:
            _validate_funding(
                effective,
                root,
                symbol,
                verified_parts,
                funding_start,
                end,
                row,
                issues,
                mark_parts=verified_marks.get(symbol, []),
                audit=funding_mark_audit,
            )
        verified_by_key[key] = verified_parts
        coverage_by_key[key] = row
        coverage.append(row)

    if config.execution_model == "minute_open":
        for symbol in config.symbols:
            for market in ("spot", "futures"):
                price_key = ("minute_prices", symbol, market)
                volume_key = ("minute_volumes", symbol, market)
                _validate_minute_pair(
                    root,
                    symbol,
                    market,
                    verified_by_key.get(price_key, []),
                    verified_by_key.get(volume_key, []),
                    start,
                    end,
                    coverage_by_key[price_key],
                    coverage_by_key[volume_key],
                    issues,
                )
    if config.execution_model == "next_minute_vwap" or closed_signals:
        for symbol in config.symbols:
            for market in ("spot", "futures"):
                key = ("minute_bars", symbol, market)
                _validate_minute_bars(
                    root,
                    symbol,
                    market,
                    verified_by_key.get(key, []),
                    start,
                    end,
                    coverage_by_key[key],
                    issues,
                )

    rules_path = root / config.rules_file
    research = config.analysis_mode == "prescribed_research"
    if not research and not rules_path.exists():
        issues.append("missing historical market rules")
    else:
        try:
            rulebook = prescribed_rules(effective) if research else RuleBook.load(rules_path)
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
        and not research
        and scope == "full"
        and start == timestamp(config.start)
        and end == timestamp(config.end)
    )
    result = {
        "status": status,
        "historical": True,
        "analysis_mode": config.analysis_mode,
        "historical_certified": status == "complete" and not research,
        "scope": scope,
        "start": start,
        "end": end,
        "funding_warmup_start": funding_start,
        "full_baseline_coverage": full_baseline,
        "issues": sorted(set(issues)),
        "coverage": coverage,
    }
    if minute_model:
        result["documented_closures"] = quality_closures(config.symbols, start, end)
    if research:
        result["research_assumptions"] = research_assumptions(effective)
        result["funding_mark_audit"] = funding_mark_audit
    if config.mark_gap_method != "strict":
        result["mark_gap_method"] = config.mark_gap_method
        result["mark_gap_audit"] = mark_gap_audit
        result["coverage_kind"] = (
            "completed_with_approximations" if status == "complete" else "incomplete_data"
        )

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
        f"Modo de análisis: **{config.analysis_mode}**. Las reglas prescritas no certifican reglas históricas.",
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
    if config.mark_gap_method != "strict":
        lines.extend(
            [
                "",
                f"Cobertura: **{result['coverage_kind']}**; método de mark: "
                f"`{config.mark_gap_method}`; {len(mark_gap_audit)} minutos estimados. "
                "Estas observaciones no son marks oficiales.",
            ]
        )
    documented = result.get("documented_closures", [])
    if documented:
        lines.extend(["", "## Cierres de mercado documentados", ""])
        lines.extend(
            f"- {item['market']} {', '.join(item['symbols'])}: "
            f"`{item['start_utc']}` a `{item['end_utc']}` ({item['minutes']} minutos). "
            f"Fuente primaria: {item['source_url']}"
            for item in documented
        )
    lines.extend(
        [
            "",
            "La ausencia de un archivo se trata como información desconocida, no como inactividad ni funding cero.",
        ]
    )
    (manifests / "data_quality_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return result
