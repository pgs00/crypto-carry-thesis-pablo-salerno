"""Streaming normalization from Binance archives into partitioned Parquet."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import zipfile
from collections.abc import Iterable, Iterator
from decimal import Decimal
from itertools import chain
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from ..config import HOUR, SECOND, Config
from ..models import Funding
from .download import DataBudgetExceeded, _data_bytes


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
    count = 0
    stats["minute_coverage_complete"] = True
    for values in iterator:
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
        if any(Decimal(record[key]) <= 0 for key in ("open", "high", "low", "close")):
            raise ValueError(f"Non-positive mark value in {path}")
        if previous_open is not None and open_ms != previous_open + 60_000:
            stats["minute_coverage_complete"] = False
        previous_open = open_ms
        count += 1
        yield record
    if count != 1440:
        stats["minute_coverage_complete"] = False


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


def _write_partition(
    rows: Iterable[dict],
    destination: Path,
    *,
    data_root: Path,
    budget: int,
    chunk_size: int = 100_000,
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
        pq.write_table(pa.Table.from_pylist(values), buffer, compression="zstd")
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
                "schema": {
                    field.name: str(field.type) for field in pa.Table.from_pylist(values).schema
                },
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


def normalize(config: Config, root: Path) -> dict:
    """Normalize all successful raw-manifest entries without materializing full histories."""
    root = Path(root).resolve()
    data_root = root / config.data_dir
    download_path = data_root / "manifests" / "download.json"
    manifest = json.loads(download_path.read_text(encoding="utf-8"))
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
                date = _archive_date(raw_path)
                rows = _mark_rows(raw_path, symbol, stats)
                destination = (
                    data_root
                    / "processed"
                    / "dataset=marks"
                    / f"symbol={symbol}"
                    / "market=futures"
                    / f"date={date}"
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
                rows, destination, data_root=data_root, budget=config.data_budget_bytes
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
                        "complete": True,
                        "trade_id_continuous": stats.get("trade_id_continuous")
                        if dataset == "trades"
                        else None,
                        "minute_coverage_complete": stats.get("minute_coverage_complete")
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
            zipfile.BadZipFile,
            pa.ArrowException,
        ) as exc:
            errors.append(f"{entry['path']}: {type(exc).__name__}: {exc}")

    result = {
        "version": 1,
        "source_manifest_sha256": _hash(download_path),
        "entries": processed_entries,
        "errors": errors,
    }
    output_path = data_root / "manifests" / "processed.json"
    encoded = json.dumps(result, indent=2, sort_keys=True).encode()
    if _data_bytes(data_root) + len(encoded) > config.data_budget_bytes:
        raise DataBudgetExceeded("Processed manifest would exceed data budget")
    temporary = output_path.with_suffix(".json.part")
    temporary.write_bytes(encoded)
    temporary.replace(output_path)
    return result
