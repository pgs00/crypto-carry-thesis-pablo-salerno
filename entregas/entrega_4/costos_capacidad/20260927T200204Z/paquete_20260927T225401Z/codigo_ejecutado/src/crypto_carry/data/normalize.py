"""Streaming normalization from Binance archives into partitioned Parquet."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import zipfile
from collections.abc import Iterable, Iterator
from decimal import Decimal, InvalidOperation
from heapq import merge
from itertools import chain
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from ..config import HOUR, SECOND, Config, iso, timestamp
from ..models import Funding
from .download import DataBudgetExceeded, _checksum_value, _data_bytes
from .market_calendar import closed_minute_count, closure_for_minute

MINUTE = 60 * SECOND
VWAP_OHLC_REL_TOLERANCE = Decimal("1e-8")
_KLINE_HEADER = (
    "open_time",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "close_time",
    "quote_volume",
    "count",
    "taker_buy_volume",
    "taker_buy_quote_volume",
    "ignore",
)
_FUNDING_SCHEMA = pa.schema(
    [
        pa.field("symbol", pa.string()),
        pa.field("funding_time", pa.int64()),
        pa.field("available_at", pa.int64()),
        pa.field("funding_rate", pa.string()),
        pa.field("interval_hours", pa.string()),
        pa.field("settlement_mark_price", pa.string()),
        pa.field("source_file", pa.string()),
        pa.field("interval_verified", pa.bool_()),
    ]
)


def source_timestamp_ns(value: int | str, market: str, source_date: str) -> int:
    """Apply Binance's 2025 microsecond switch only to spot archive timestamps."""
    integer = int(value)
    year = int(source_date[:4])
    multiplier = 1_000 if market == "spot" and year >= 2025 else 1_000_000
    return integer * multiplier


def deduplicate_rows(rows: Iterable[dict], key_fields: tuple[str, ...]) -> tuple[list[dict], int]:
    unique: dict[tuple, dict] = {}
    duplicate_count = 0
    for row in rows:
        key = tuple(row[field] for field in key_fields)
        previous = unique.get(key)
        if previous is None:
            unique[key] = row
        elif previous == row:
            duplicate_count += 1
        else:
            raise ValueError(f"Conflicting duplicate for key {key}")
    return list(unique.values()), duplicate_count


def funding_records(
    rows: Iterable[dict],
    *,
    symbol: str,
    source_file: str,
    expected_times_ms: set[int] | None = None,
    expected_intervals: dict[int, Decimal] | None = None,
    expected_rates: dict[int, Decimal] | None = None,
) -> list[Funding]:
    ordered, _ = deduplicate_rows(
        sorted(rows, key=lambda row: int(row["fundingTime"])), ("fundingTime",)
    )
    records: list[Funding] = []
    previous_ns: int | None = None
    for row in ordered:
        funding_ms = int(row["fundingTime"])
        funding_ns = funding_ms * 1_000_000
        if previous_ns is None:
            interval = Decimal(str(row.get("fundingIntervalHours", "0")))
        else:
            interval = Decimal(funding_ns - previous_ns) / Decimal(HOUR)
        verified = False
        if previous_ns is not None and expected_times_ms is not None:
            previous_ms = previous_ns // 1_000_000
            between = sorted(
                value for value in expected_times_ms if previous_ms < value <= funding_ms
            )
            verified = (
                previous_ms in expected_times_ms
                and between == [funding_ms]
                and expected_intervals is not None
                # Data Vision publishes nominal whole-hour schedules; actual
                # settlement timestamps retain their millisecond offsets below.
                # Comparing UTC hour boundaries detects a missing scheduled
                # payment without rounding the effective EWMA duration.
                and expected_intervals.get(funding_ms)
                == Decimal(funding_ms // 3_600_000 - previous_ms // 3_600_000)
            )
        if expected_rates is not None and funding_ms in expected_rates:
            if Decimal(str(row["fundingRate"])) != expected_rates[funding_ms]:
                raise ValueError(
                    f"Conflicting funding rate across official sources at {funding_ms}"
                )
        mark_text = row.get("markPrice")
        mark = None if mark_text in (None, "", "null") else Decimal(str(mark_text))
        records.append(
            Funding(
                symbol=symbol,
                funding_time=funding_ns,
                available_at=funding_ns + 60 * SECOND,
                funding_rate=Decimal(str(row["fundingRate"])),
                interval_hours=interval,
                settlement_mark_price=mark,
                source_file=source_file,
                interval_verified=verified,
            )
        )
        previous_ns = funding_ns
    return records


def _csv_rows(path: Path) -> Iterator[list[str]]:
    with zipfile.ZipFile(path) as archive:
        names = [name for name in archive.namelist() if not name.endswith("/")]
        if len(names) != 1:
            raise ValueError(f"Expected exactly one CSV in {path}")
        with archive.open(names[0]) as binary:
            text = io.TextIOWrapper(binary, encoding="utf-8", newline="")
            yield from csv.reader(text)


def _has_header(row: list[str]) -> bool:
    try:
        int(row[0])
        return False
    except ValueError:
        return True


def _archive_date(path: Path) -> str:
    return path.stem[-10:]


def _kline_records(
    path: Path,
    symbol: str,
    market: str,
    *,
    timestamp_unit: str,
    source_start: str,
    stats: dict,
    minimum_open_time: int | None = None,
) -> Iterator[tuple[dict | None, dict, dict]]:
    """Yield causal open-price and closed-volume records from Binance 1m klines."""
    expected_unit = "us" if market == "spot" and source_start[:4] >= "2025" else "ms"
    if timestamp_unit != expected_unit:
        raise ValueError(
            f"Incorrect timestamp unit for {market} {source_start[:7]}: "
            f"expected {expected_unit}, got {timestamp_unit}"
        )
    unit_ns = 1_000 if timestamp_unit == "us" else 1_000_000
    minute_units = 60_000_000 if timestamp_unit == "us" else 60_000
    rows = _csv_rows(path)
    first = next(rows, None)
    stats.update(
        minute_coverage_complete=True,
        source_row_count=0,
        documented_missing_minutes=0,
        first_open_time=None,
        last_open_time=None,
        excluded_before_start=0,
    )
    if first is None:
        stats["minute_coverage_complete"] = False
        return
    has_header = _has_header(first)
    iterator = rows if has_header else chain([first], rows)
    if len(first) != 12:
        raise ValueError(f"Expected Binance 12-field kline schema in {path}")
    if has_header:
        normalized_header = tuple(value.strip().lower().replace(" ", "_") for value in first)
        if normalized_header != _KLINE_HEADER:
            raise ValueError(f"Expected Binance 12-field kline header in {path}")
    previous_open: int | None = None
    for values in iterator:
        if len(values) != 12:
            raise ValueError(f"Expected Binance 12-field kline schema in {path}")
        try:
            open_raw = int(values[0])
            if minimum_open_time is not None and open_raw * unit_ns < minimum_open_time:
                stats["excluded_before_start"] += 1
                continue
            close_raw = int(values[6])
            prices = tuple(Decimal(values[index]) for index in (1, 2, 3, 4))
            quantity = Decimal(values[5])
            quote_quantity = Decimal(values[7])
            trade_count = int(values[8])
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ValueError(f"Malformed kline value in {path}") from exc
        open_price, high, low, close_price = prices
        if any(not value.is_finite() or value <= 0 for value in prices):
            raise ValueError(f"Kline requires finite positive OHLC in {path}")
        if not low <= open_price <= high or not low <= close_price <= high or low > high:
            raise ValueError(f"Invalid OHLC ordering in {path}")
        if not quantity.is_finite() or quantity < 0:
            raise ValueError(f"Kline requires non-negative volume in {path}")
        if not quote_quantity.is_finite() or quote_quantity < 0:
            raise ValueError(f"Kline requires non-negative quote volume in {path}")
        if trade_count < 0:
            raise ValueError(f"Kline requires non-negative trade count in {path}")
        if trade_count == 0 and quantity != 0:
            raise ValueError(f"Kline zero trades require zero volume in {path}")
        if quantity == 0 and quote_quantity != 0:
            raise ValueError(f"Kline base and quote volumes must both be zero in {path}")
        if quantity > 0 and quote_quantity <= 0:
            raise ValueError(f"Kline positive base volume requires positive quote volume in {path}")
        if quantity > 0:
            vwap = quote_quantity / quantity
            tolerance = max(abs(low), abs(high), Decimal(1)) * VWAP_OHLC_REL_TOLERANCE
            if not low - tolerance <= vwap <= high + tolerance:
                raise ValueError(f"Kline VWAP must lie within OHLC tolerance in {path}")
        open_ns = open_raw * unit_ns
        closure = closure_for_minute(symbol, market, open_ns)
        if closure is not None and trade_count > 0:
            raise ValueError(f"Kline has positive trades during documented closure in {path}")
        normal_close = open_raw + minute_units - 1
        early_closed_zero = (
            closure is not None
            and trade_count == 0
            and quantity == 0
            and open_raw <= close_raw < normal_close
        )
        if open_raw % minute_units or (close_raw != normal_close and not early_closed_zero):
            raise ValueError(f"Kline requires an aligned exact one-minute interval in {path}")
        if previous_open is not None:
            if open_raw <= previous_open:
                raise ValueError(f"Klines must be strictly chronological and unique in {path}")
            if open_raw != previous_open + minute_units:
                missing = (open_raw - previous_open) // minute_units - 1
                lower = (previous_open + minute_units) * unit_ns
                documented = closed_minute_count(symbol, market, lower, open_ns)
                stats["documented_missing_minutes"] += documented
                if documented != missing:
                    stats["minute_coverage_complete"] = False
        close_ns = close_raw * unit_ns
        price = None
        if trade_count > 0:
            price = {
                "symbol": symbol,
                "market": market,
                "reference_id": f"bar:{symbol}:{market}:{open_ns}",
                "event_time": open_ns,
                "available_at": open_ns,
                "price": values[1],
                "source_file": path.name,
            }
        volume = {
            "symbol": symbol,
            "market": market,
            "open_time": open_ns,
            "close_time": close_ns,
            "available_at": close_ns + unit_ns,
            "quantity": values[5],
            "trade_count": trade_count,
            "source_file": path.name,
        }
        bar = {
            "symbol": symbol,
            "market": market,
            "open_time": open_ns,
            "end_time": open_ns + MINUTE,
            "available_at": open_ns + MINUTE,
            "open": values[1],
            "high": values[2],
            "low": values[3],
            "close": values[4],
            "base_volume": values[5],
            "quote_volume": values[7],
            "trade_count": trade_count,
            "source_file": path.name,
        }
        if stats["first_open_time"] is None:
            stats["first_open_time"] = open_ns
        stats["last_open_time"] = open_ns
        stats["source_row_count"] += 1
        previous_open = open_raw
        yield price, volume, bar


def _trade_rows(path: Path, symbol: str, market: str, stats: dict) -> Iterator[dict]:
    rows = _csv_rows(path)
    first = next(rows, None)
    if first is None:
        return
    if _has_header(first):
        header = first
        iterator = rows
    else:
        header = ["id", "price", "qty", "quote_qty", "time", "is_buyer_maker", "is_best_match"]
        iterator = chain([first], rows)
    names = {name.strip(): index for index, name in enumerate(header)}
    id_column = "id" if "id" in names else "trade_id"
    qty_column = "qty" if "qty" in names else "quantity"
    time_column = "time" if "time" in names else "timestamp"
    source_date = _archive_date(path)
    previous: dict | None = None
    previous_id: int | None = None
    stats.update(duplicate_count=0, conflict_count=0, trade_id_continuous=True)
    for values in iterator:
        record = {
            "symbol": symbol,
            "market": market,
            "trade_id": str(values[names[id_column]]),
            "event_time": source_timestamp_ns(values[names[time_column]], market, source_date),
            "available_at": source_timestamp_ns(values[names[time_column]], market, source_date),
            "price": values[names["price"]],
            "quantity": values[names[qty_column]],
            "source_file": path.name,
        }
        if Decimal(record["price"]) <= 0 or Decimal(record["quantity"]) <= 0:
            raise ValueError(f"Non-positive trade value in {path}")
        if previous is not None and record["trade_id"] == previous["trade_id"]:
            if record == previous:
                stats["duplicate_count"] += 1
                continue
            stats["conflict_count"] += 1
            raise ValueError(f"Conflicting duplicate trade {record['trade_id']} in {path}")
        try:
            current_id = int(record["trade_id"])
        except ValueError:
            stats["trade_id_continuous"] = False
        else:
            if previous_id is not None and current_id != previous_id + 1:
                stats["trade_id_continuous"] = False
            previous_id = current_id
        yield record
        previous = record


def _mark_rows(path: Path, symbol: str, stats: dict) -> Iterator[dict]:
    rows = _csv_rows(path)
    first = next(rows, None)
    if first is None:
        return
    if _has_header(first):
        header = first
        iterator = rows
    else:
        header = [
            "open_time",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "close_time",
            "quote_volume",
            "count",
            "taker_buy_volume",
            "taker_buy_quote_volume",
            "ignore",
        ]
        iterator = chain([first], rows)
    names = {name.strip().lower().replace(" ", "_"): index for index, name in enumerate(header)}
    previous_open: int | None = None
    stats.update(
        minute_coverage_complete=True,
        source_row_count=0,
        first_open_time=None,
        last_open_time=None,
    )
    for values in iterator:
        if len(values) != 12:
            raise ValueError(f"Expected Binance 12-field mark kline schema in {path}")
        open_ms = int(values[names["open_time"]])
        close_ms = int(values[names["close_time"]])
        record = {
            "symbol": symbol,
            "open_time": open_ms * 1_000_000,
            "close_time": close_ms * 1_000_000,
            "available_at": close_ms * 1_000_000 + 1_000_000,
            "open": values[names["open"]],
            "high": values[names["high"]],
            "low": values[names["low"]],
            "close": values[names["close"]],
            "source_file": path.name,
        }
        prices = tuple(Decimal(record[key]) for key in ("open", "high", "low", "close"))
        if any(not value.is_finite() or value <= 0 for value in prices):
            raise ValueError(f"Non-positive or non-finite mark value in {path}")
        open_price, high, low, close_price = prices
        if not low <= open_price <= high or not low <= close_price <= high or low > high:
            raise ValueError(f"Invalid mark OHLC ordering in {path}")
        if open_ms % 60_000 or close_ms != open_ms + 59_999:
            raise ValueError(f"Mark kline requires an aligned exact one-minute interval in {path}")
        if previous_open is not None:
            if open_ms <= previous_open:
                raise ValueError(f"Mark klines must be strictly chronological and unique in {path}")
            if open_ms != previous_open + 60_000:
                stats["minute_coverage_complete"] = False
        if stats["first_open_time"] is None:
            stats["first_open_time"] = record["open_time"]
        stats["last_open_time"] = record["open_time"]
        previous_open = open_ms
        stats["source_row_count"] += 1
        yield record
    if stats["source_row_count"] == 0:
        stats["minute_coverage_complete"] = False


def _merge_mark_rows(paths: list[Path], symbol: str, stats: dict) -> Iterator[dict]:
    """Merge observed mark sources, preferring the monthly row on identical overlap."""
    iterators = [_mark_rows(path, symbol, {}) for path in paths]
    rows = merge(*iterators, key=lambda row: int(row["open_time"]))
    stats.update(
        duplicate_count=0,
        conflict_count=0,
        minute_coverage_complete=True,
        source_row_count=0,
        first_open_time=None,
        last_open_time=None,
    )
    previous: dict | None = None
    for record in rows:
        if previous is not None and record["open_time"] == previous["open_time"]:
            same_observation = (
                record["symbol"] == previous["symbol"]
                and all(
                    int(record[field]) == int(previous[field])
                    for field in ("open_time", "close_time", "available_at")
                )
                and all(
                    Decimal(record[field]) == Decimal(previous[field])
                    for field in ("open", "high", "low", "close")
                )
            )
            if not same_observation:
                stats["conflict_count"] += 1
                raise ValueError(f"Conflicting mark overlap at {record['open_time']}")
            stats["duplicate_count"] += 1
            continue
        if previous is not None:
            if int(record["open_time"]) != int(previous["open_time"]) + MINUTE:
                stats["minute_coverage_complete"] = False
            yield previous
        else:
            stats["first_open_time"] = int(record["open_time"])
        previous = record
        stats["last_open_time"] = int(record["open_time"])
        stats["source_row_count"] += 1
    if previous is None:
        stats["minute_coverage_complete"] = False
    else:
        yield previous


def _funding_calendar_times(path: Path) -> dict[int, tuple[Decimal, Decimal]]:
    rows = _csv_rows(path)
    first = next(rows, None)
    if first is None:
        return {}
    if _has_header(first):
        header = [value.strip() for value in first]
        iterator = rows
    else:
        header = ["calc_time", "funding_interval_hours", "last_funding_rate"]
        iterator = chain([first], rows)
    names = {name: index for index, name in enumerate(header)}
    time_name = next(
        (name for name in ("fundingTime", "calc_time", "funding_time") if name in names), None
    )
    if time_name is None:
        raise ValueError(f"Unknown funding calendar schema in {path}")
    result = {}
    for values in iterator:
        key = int(values[names[time_name]])
        item = (
            Decimal(values[names["funding_interval_hours"]]),
            Decimal(values[names["last_funding_rate"]]),
        )
        if key in result and result[key] != item:
            raise ValueError(f"Conflicting funding calendar duplicate at {key}")
        result[key] = item
    return result


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _manifest_time_ns(value: int | str) -> int:
    return timestamp(value) if isinstance(value, str) else int(value)


def _verified_mark_supplement(root: Path, parent: dict, supplement: dict) -> Path:
    """Bind an immutable daily mark archive to its declared monthly parent."""
    if supplement.get("status") not in {"cached", "downloaded"}:
        raise ValueError("Supplement status is not successful")
    if supplement.get("dataset") != "marks":
        raise ValueError("Supplement dataset mismatch")
    if supplement.get("symbol") != parent["symbol"]:
        raise ValueError("Supplement symbol mismatch")
    if supplement.get("market") != parent["market"]:
        raise ValueError("Supplement market mismatch")
    if supplement.get("timestamp_unit") != "ms":
        raise ValueError("Supplement timestamp unit mismatch")
    parent_start = _manifest_time_ns(parent["start"])
    parent_end = _manifest_time_ns(parent["end"])
    supplement_start = _manifest_time_ns(supplement["start"])
    supplement_end = _manifest_time_ns(supplement["end"])
    if not parent_start <= supplement_start <= supplement_end <= parent_end:
        raise ValueError("Supplement time bounds escape parent archive")

    path = root / supplement["path"]
    if _hash(path) != supplement["sha256"]:
        raise ValueError(f"Supplement raw hash mismatch: {supplement['path']}")
    checksum_path = root / supplement["checksum_path"]
    checksum_content = checksum_path.read_bytes()
    if hashlib.sha256(checksum_content).hexdigest() != supplement["checksum_file_sha256"]:
        raise ValueError(f"Supplement checksum hash mismatch: {supplement['checksum_path']}")
    checksum_source = supplement.get("checksum_url", supplement["checksum_path"])
    official_digest = _checksum_value(checksum_content, checksum_source)
    if official_digest != supplement["sha256"].lower():
        raise ValueError(f"Official supplement checksum mismatch: {supplement['path']}")
    fields = checksum_content.decode("ascii", errors="strict").split()
    listed_name = Path(fields[1].lstrip("*")).name if len(fields) >= 2 else ""
    if listed_name != path.name:
        raise ValueError(f"Supplement checksum filename mismatch: {supplement['path']}")
    return path


def _write_partition(
    rows: Iterable[dict],
    destination: Path,
    *,
    data_root: Path,
    budget: int,
    chunk_size: int = 100_000,
    schema: pa.Schema | None = None,
) -> list[dict]:
    destination.mkdir(parents=True, exist_ok=True)
    entries = []
    chunk: list[dict] = []
    part_number = 0

    def flush(values: list[dict], number: int):
        if not values:
            return
        target = destination / f"part-{number:05d}.parquet"
        temporary = destination / f".part-{number:05d}.parquet.tmp"
        buffer = pa.BufferOutputStream()
        table = pa.Table.from_pylist(values, schema=schema)
        pq.write_table(table, buffer, compression="zstd")
        encoded = buffer.getvalue()
        digest = hashlib.sha256(encoded).hexdigest()
        cached = target.exists() and _hash(target) == digest
        projected = _data_bytes(data_root) + (0 if cached else encoded.size)
        if projected > budget:
            raise DataBudgetExceeded(f"Processed write would exceed {budget} bytes")
        if not cached:
            temporary.write_bytes(encoded.to_pybytes())
        if target.exists():
            if _hash(target) == digest:
                temporary.unlink(missing_ok=True)
            else:
                target = destination / f"part-{number:05d}-{digest[:12]}.parquet"
                if target.exists() and _hash(target) != digest:
                    raise ValueError(f"Processed version collision: {target}")
                if target.exists():
                    temporary.unlink()
                else:
                    temporary.replace(target)
        else:
            temporary.replace(target)
        entries.append(
            {
                "path": target,
                "sha256": digest,
                "bytes": target.stat().st_size,
                "rows": len(values),
                "start": min(_physical_time(row) for row in values),
                "end": max(_physical_time(row) for row in values),
                "schema": {field.name: str(field.type) for field in table.schema},
                "first_trade_id": values[0].get("trade_id"),
                "last_trade_id": values[-1].get("trade_id"),
            }
        )

    for row in rows:
        chunk.append(row)
        if len(chunk) >= chunk_size:
            flush(chunk, part_number)
            part_number += 1
            chunk = []
    flush(chunk, part_number)
    return entries


def _physical_time(row: dict) -> int:
    for field in ("event_time", "funding_time", "available_at"):
        if field in row:
            return int(row[field])
    raise ValueError("Normalized row has no physical timestamp")


def _funding_dict(record: Funding) -> dict:
    return {
        "symbol": record.symbol,
        "funding_time": record.funding_time,
        "available_at": record.available_at,
        "funding_rate": str(record.funding_rate),
        "interval_hours": str(record.interval_hours),
        "settlement_mark_price": None
        if record.settlement_mark_price is None
        else str(record.settlement_mark_price),
        "source_file": record.source_file,
        "interval_verified": record.interval_verified,
    }


def normalize(config: Config, root: Path, *, clip_price_warmup: bool = False) -> dict:
    """Normalize all successful raw-manifest entries without materializing full histories."""
    if config.mark_gap_method != "strict":
        raise ValueError("Cannot normalize over a derived mark layer; use prepare-mark-gaps")
    root = Path(root).resolve()
    data_root = root / config.data_dir
    download_path = data_root / "manifests" / "download.json"
    manifest = json.loads(download_path.read_text(encoding="utf-8"))
    manifest_kind = manifest.get("kind", "trade_market_data")
    price_start = None
    if clip_price_warmup:
        if manifest_kind != "minute_market_data":
            raise ValueError("Price warmup scoping requires minute_market_data")
        # Prices need the closed-bar antecedent and the participation lookback.
        # Funding and mark histories retain their full requested warmup.
        lookback_minutes = max(1, (config.participation_seconds + 59) // 60)
        price_start = (timestamp(config.start) // MINUTE - lookback_minutes) * MINUTE
    budget_root = root / "data" / "minutes" if manifest_kind == "minute_market_data" else data_root
    successful = [
        entry for entry in manifest["entries"] if entry["status"] in {"cached", "downloaded"}
    ]
    calendar: dict[str, dict] = {symbol: {} for symbol in config.symbols}
    errors: list[str] = []
    for entry in successful:
        if entry["dataset"] != "funding_calendar":
            continue
        try:
            source = root / entry["path"]
            if _hash(source) != entry["sha256"]:
                raise ValueError("Funding calendar raw hash mismatch")
            for key, item in _funding_calendar_times(source).items():
                previous = calendar[entry["symbol"]].get(key)
                if previous is not None and previous != item:
                    raise ValueError(f"Conflicting funding calendar duplicate at {key}")
                calendar[entry["symbol"]][key] = item
        except (
            csv.Error,
            KeyError,
            OSError,
            TypeError,
            UnicodeError,
            ValueError,
            zipfile.BadZipFile,
        ) as exc:
            errors.append(f"{entry['path']}: {type(exc).__name__}: {exc}")

    processed_entries: list[dict] = []
    for entry in successful:
        dataset = entry["dataset"]
        if dataset == "funding_calendar":
            continue
        raw_path = root / entry["path"]
        symbol = entry["symbol"]
        market = entry["market"]
        stats: dict = {"duplicate_count": 0, "conflict_count": 0}
        try:
            if _hash(raw_path) != entry["sha256"]:
                raise ValueError("Raw input hash mismatch")
            if dataset == "klines" and manifest_kind == "minute_market_data":
                source_start = (
                    entry["start"] if isinstance(entry["start"], str) else iso(int(entry["start"]))
                )
                date = source_start[:7]
                for output_dataset, position in (
                    ("minute_volumes", 1),
                    ("minute_prices", 0),
                    ("minute_bars", 2),
                ):
                    output_stats: dict = {"duplicate_count": 0, "conflict_count": 0}
                    pairs = _kline_records(
                        raw_path,
                        symbol,
                        market,
                        timestamp_unit=entry["timestamp_unit"],
                        source_start=source_start,
                        stats=output_stats,
                        minimum_open_time=price_start,
                    )
                    rows = (pair[position] for pair in pairs if pair[position] is not None)
                    destination = (
                        data_root
                        / "processed"
                        / f"dataset={output_dataset}"
                        / f"symbol={symbol}"
                        / f"market={market}"
                        / f"month={date}"
                    )
                    outputs = _write_partition(
                        rows,
                        destination,
                        data_root=budget_root,
                        budget=config.data_budget_bytes,
                    )
                    source_end = (
                        timestamp(entry["end"])
                        if isinstance(entry["end"], str)
                        else int(entry["end"])
                    )
                    source_start_ns = timestamp(source_start)
                    if price_start is not None:
                        source_start_ns = max(source_start_ns, price_start)
                    expected_rows = (source_end - source_start_ns) // MINUTE + 1
                    complete = (
                        output_stats.get("minute_coverage_complete") is True
                        and output_stats.get("source_row_count", 0)
                        + output_stats.get("documented_missing_minutes", 0)
                        == expected_rows
                        and output_stats.get("first_open_time") == source_start_ns
                        and output_stats.get("last_open_time")
                        == source_start_ns + (expected_rows - 1) * MINUTE
                    )
                    for output in outputs:
                        processed_entries.append(
                            {
                                "dataset": output_dataset,
                                "symbol": symbol,
                                "market": market,
                                "date": date,
                                "path": str(output["path"].relative_to(root)).replace("\\", "/"),
                                "sha256": output["sha256"],
                                "bytes": output["bytes"],
                                "rows": output["rows"],
                                "start": output["start"],
                                "end": output["end"],
                                "schema": output["schema"],
                                "duplicate_count": 0,
                                "conflict_count": 0,
                                "complete": complete,
                                "minute_coverage_complete": complete,
                                "source_rows": output_stats.get("source_row_count", 0),
                                "documented_missing_minutes": output_stats.get(
                                    "documented_missing_minutes", 0
                                ),
                                "source_dataset": "klines",
                                "source_path": entry["path"],
                                "source_sha256": entry["sha256"],
                                "timestamp_unit": entry["timestamp_unit"],
                                "first_trade_id": None,
                                "last_trade_id": None,
                                **(
                                    dict(
                                        source_scope_start=source_start_ns,
                                        excluded_before_start=output_stats["excluded_before_start"],
                                    )
                                    if price_start is not None
                                    else {}
                                ),
                            }
                        )
                continue
            if dataset == "trades":
                date = _archive_date(raw_path)
                rows = _trade_rows(raw_path, symbol, market, stats)
                destination = (
                    data_root
                    / "processed"
                    / "dataset=trades"
                    / f"symbol={symbol}"
                    / f"market={market}"
                    / f"date={date}"
                )
            elif dataset == "marks":
                date = (
                    str(entry["start"])[:7]
                    if manifest_kind == "minute_market_data"
                    else _archive_date(raw_path)
                )
                mark_paths = [raw_path]
                for supplement in entry.get("supplements", []):
                    mark_paths.append(_verified_mark_supplement(root, entry, supplement))
                rows = _merge_mark_rows(mark_paths, symbol, stats)
                destination = (
                    data_root
                    / "processed"
                    / "dataset=marks"
                    / f"symbol={symbol}"
                    / "market=futures"
                    / (f"month={date}" if manifest_kind == "minute_market_data" else f"date={date}")
                )
            elif dataset == "funding":
                api_rows = json.loads(raw_path.read_text(encoding="utf-8"))
                all_records = funding_records(
                    api_rows,
                    symbol=symbol,
                    source_file=raw_path.name,
                    expected_times_ms=set(calendar[symbol]) or None,
                    expected_intervals={k: v[0] for k, v in calendar[symbol].items()},
                    expected_rates={k: v[1] for k, v in calendar[symbol].items()},
                )
                # The first API observation has no prior settlement from which to derive an
                # interval. The downloader requests an extra day so dropping it still leaves
                # the antecedent needed by the configured warmup.
                records = [record for record in all_records if record.interval_hours > 0]
                covered_times = {r.funding_time // 1_000_000 for r in records}
                expected_times = {
                    t
                    for t in calendar[symbol]
                    if records
                    and records[0].funding_time // 1_000_000 <= t <= int(entry["end"]) // 1_000_000
                }
                funding_calendar_complete = (
                    bool(records)
                    and covered_times == expected_times
                    and all(r.interval_verified for r in records)
                )
                rows = (_funding_dict(record) for record in records)
                date = "all"
                destination = (
                    data_root
                    / "processed"
                    / "dataset=funding"
                    / f"symbol={symbol}"
                    / "market=futures"
                    / "date=all"
                )
            else:
                continue
            outputs = _write_partition(
                rows,
                destination,
                data_root=budget_root,
                budget=config.data_budget_bytes,
                schema=_FUNDING_SCHEMA if dataset == "funding" else None,
            )
            mark_complete = None
            if dataset == "marks":
                source_start_ns = (
                    timestamp(entry["start"])
                    if isinstance(entry["start"], str)
                    else int(entry["start"])
                )
                source_end_ns = (
                    timestamp(entry["end"]) if isinstance(entry["end"], str) else int(entry["end"])
                )
                expected_rows = (source_end_ns - source_start_ns) // MINUTE + 1
                mark_complete = (
                    stats.get("minute_coverage_complete") is True
                    and stats.get("source_row_count") == expected_rows
                    and stats.get("first_open_time") == source_start_ns
                    and stats.get("last_open_time")
                    == source_start_ns + (expected_rows - 1) * MINUTE
                )
            for output_index, output in enumerate(outputs):
                processed_entries.append(
                    {
                        "dataset": dataset,
                        "symbol": symbol,
                        "market": market,
                        "date": date,
                        "path": str(output["path"].relative_to(root)).replace("\\", "/"),
                        "sha256": output["sha256"],
                        "bytes": output["bytes"],
                        "rows": output["rows"],
                        "start": output["start"],
                        "end": output["end"],
                        "schema": output["schema"],
                        "duplicate_count": stats.get("duplicate_count", 0)
                        if output_index == 0
                        else 0,
                        "conflict_count": stats.get("conflict_count", 0)
                        if output_index == 0
                        else 0,
                        "complete": mark_complete if dataset == "marks" else True,
                        "trade_id_continuous": stats.get("trade_id_continuous")
                        if dataset == "trades"
                        else None,
                        "minute_coverage_complete": mark_complete if dataset == "marks" else None,
                        "source_path": entry["path"],
                        "source_sha256": entry["sha256"],
                        "source_supplements": entry.get("supplements", [])
                        if dataset == "marks"
                        else None,
                        "funding_calendar_complete": (
                            funding_calendar_complete if dataset == "funding" else None
                        ),
                        "settlement_marks_complete": all(
                            record.settlement_mark_price is not None for record in records
                        )
                        if dataset == "funding"
                        else None,
                        "first_trade_id": output["first_trade_id"],
                        "last_trade_id": output["last_trade_id"],
                    }
                )
        except (
            csv.Error,
            KeyError,
            OSError,
            TypeError,
            UnicodeError,
            ValueError,
            InvalidOperation,
            zipfile.BadZipFile,
            pa.ArrowException,
        ) as exc:
            errors.append(f"{entry['path']}: {type(exc).__name__}: {exc}")

    result = {
        "version": 1,
        "kind": manifest_kind,
        "source_manifest_sha256": _hash(download_path),
        "entries": processed_entries,
        "errors": errors,
    }
    if price_start is not None:
        result["normalization_scope"] = dict(
            price_start=price_start,
            price_start_utc=iso(price_start),
            reason="Evaluation prices with closed-bar and participation antecedents",
            funding_and_marks_clipped=False,
        )
    output_path = data_root / "manifests" / "processed.json"
    encoded = json.dumps(result, indent=2, sort_keys=True).encode()
    if _data_bytes(budget_root) + len(encoded) > config.data_budget_bytes:
        raise DataBudgetExceeded("Processed manifest would exceed data budget")
    temporary = output_path.with_suffix(".json.part")
    temporary.write_bytes(encoded)
    temporary.replace(output_path)
    return result
