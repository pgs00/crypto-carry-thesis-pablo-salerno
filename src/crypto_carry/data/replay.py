"""Incremental chronological replay of normalized Parquet partitions."""

from __future__ import annotations

import hashlib
import heapq
import json
from collections.abc import Iterable, Iterator
from decimal import Decimal
from pathlib import Path

import pyarrow.parquet as pq

from ..config import HOUR
from ..events import DataGap, event_key, event_time
from ..models import Funding, Mark, MinuteBar, MinutePrice, MinuteVolume, Trade


def _records(
    path: Path, dataset: str
) -> Iterator[Trade | Funding | Mark | MinuteBar | MinutePrice | MinuteVolume | DataGap]:
    parquet = pq.ParquetFile(path)
    for batch in parquet.iter_batches(batch_size=65_536):
        for row in batch.to_pylist():
            if dataset == "trades":
                yield Trade(
                    symbol=row["symbol"],
                    market=row["market"],
                    trade_id=str(row["trade_id"]),
                    event_time=int(row["event_time"]),
                    available_at=int(row["available_at"]),
                    price=Decimal(str(row["price"])),
                    quantity=Decimal(str(row["quantity"])),
                    source_file=row["source_file"],
                )
            elif dataset == "minute_prices":
                yield MinutePrice(
                    symbol=row["symbol"],
                    market=row["market"],
                    reference_id=row["reference_id"],
                    event_time=int(row["event_time"]),
                    available_at=int(row["available_at"]),
                    price=Decimal(str(row["price"])),
                    source_file=row["source_file"],
                )
            elif dataset == "minute_volumes":
                yield MinuteVolume(
                    symbol=row["symbol"],
                    market=row["market"],
                    open_time=int(row["open_time"]),
                    close_time=int(row["close_time"]),
                    available_at=int(row["available_at"]),
                    quantity=Decimal(str(row["quantity"])),
                    trade_count=int(row["trade_count"]),
                    source_file=row["source_file"],
                )
            elif dataset == "minute_bars":
                yield MinuteBar(
                    symbol=row["symbol"],
                    market=row["market"],
                    open_time=int(row["open_time"]),
                    end_time=int(row["end_time"]),
                    available_at=int(row["available_at"]),
                    open=Decimal(str(row["open"])),
                    high=Decimal(str(row["high"])),
                    low=Decimal(str(row["low"])),
                    close=Decimal(str(row["close"])),
                    base_volume=Decimal(str(row["base_volume"])),
                    quote_volume=Decimal(str(row["quote_volume"])),
                    trade_count=int(row["trade_count"]),
                    source_file=row["source_file"],
                )
            elif dataset == "funding":
                yield Funding(
                    symbol=row["symbol"],
                    funding_time=int(row["funding_time"]),
                    available_at=int(row["available_at"]),
                    funding_rate=Decimal(str(row["funding_rate"])),
                    interval_hours=Decimal(str(row["interval_hours"])),
                    settlement_mark_price=None
                    if row["settlement_mark_price"] is None
                    else Decimal(str(row["settlement_mark_price"])),
                    source_file=row["source_file"],
                    interval_verified=bool(row["interval_verified"]),
                )
            elif dataset == "marks":
                yield Mark(
                    symbol=row["symbol"],
                    open_time=int(row["open_time"]),
                    close_time=int(row["close_time"]),
                    available_at=int(row["available_at"]),
                    open=Decimal(str(row["open"])),
                    high=Decimal(str(row["high"])),
                    low=Decimal(str(row["low"])),
                    close=Decimal(str(row["close"])),
                    source_file=row["source_file"],
                )
            elif dataset == "gaps":
                yield DataGap(
                    symbol=row["symbol"],
                    available_at=int(row["available_at"]),
                    reason=row["reason"],
                    resolved=bool(row.get("resolved", False)),
                )


def _partition_bounds(entry: dict) -> tuple[int, int] | None:
    """Manifest bounds are inclusive; legacy entries may omit them."""
    if entry.get("start") is None or entry.get("end") is None:
        return None
    first, last = int(entry["start"]), int(entry["end"])
    if first > last:
        raise ValueError(f"Invalid partition bounds: {entry['path']}")
    return first, last


def _select_partitions(entries: list[dict], lower: int, end: int) -> list[dict]:
    bounded = [(entry, _partition_bounds(entry)) for entry in entries]
    prior_end = max(
        (bounds[1] for _, bounds in bounded if bounds is not None and bounds[1] < lower),
        default=None,
    )
    crossing_start = max(
        (
            bounds[0]
            for _, bounds in bounded
            if bounds is not None and bounds[0] < lower <= bounds[1]
        ),
        default=None,
    )
    # A crossing partition proves a newer antecedent exists. Equal timestamps
    # must still be merged to select the last observation by the full event key.
    if prior_end is not None and crossing_start is not None and prior_end < crossing_start:
        prior_end = None
    return [
        entry
        for entry, bounds in bounded
        if bounds is None or (bounds[0] < end and (bounds[1] >= lower or bounds[1] == prior_end))
    ]


def _ordered_records(root: Path, entry: dict, bounds: tuple[int, int] | None) -> Iterator:
    previous = None
    first = None
    count = 0
    for record in _records(root / entry["path"], entry["dataset"]):
        key = event_key(record)
        if previous is not None and key < previous:
            raise ValueError(f"Partition is not chronologically ordered: {entry['path']}")
        if bounds is not None and not bounds[0] <= key[0] <= bounds[1]:
            raise ValueError(f"Record outside partition bounds: {entry['path']}")
        first = key[0] if first is None else first
        previous = key
        count += 1
        yield key, record
    if bounds is not None and (first, previous[0] if previous else None) != bounds:
        raise ValueError(f"Records differ from partition bounds: {entry['path']}")
    if entry.get("rows") is not None and count != int(entry["rows"]):
        raise ValueError(f"Records differ from partition rows: {entry['path']}")


def _partition_chain(root: Path, entries: list[dict]) -> Iterator:
    """Merge overlaps, opening only partitions that can supply the next event."""
    ordered = sorted(
        ((_partition_bounds(entry), entry) for entry in entries),
        key=lambda item: (
            item[0] is not None,
            item[0][0] if item[0] is not None else 0,
            item[1]["path"],
        ),
    )
    active = []
    index = 0
    while index < len(ordered) or active:
        if index < len(ordered):
            bounds, entry = ordered[index]
            if not active or bounds is None or bounds[0] <= active[0][0][0]:
                records = _ordered_records(root, entry, bounds)
                item = next(records, None)
                if item is not None:
                    key, record = item
                    heapq.heappush(active, (key, index, record, records))
                index += 1
                continue
        _, partition_index, record, records = heapq.heappop(active)
        yield record
        item = next(records, None)
        if item is not None:
            key, record = item
            heapq.heappush(active, (key, partition_index, record, records))


def _windowed(
    records: Iterable, lower: int, end: int, *, prefer_boundary: bool = False
) -> Iterator:
    """Keep one antecedent and the requested half-open time range."""
    antecedent = None
    for record in records:
        value = event_time(record)
        if value < lower:
            antecedent = record
            continue
        if antecedent is not None:
            if not (prefer_boundary and value == lower):
                yield antecedent
            antecedent = None
        if value >= end:
            return
        yield record
    if antecedent is not None:
        yield antecedent


def iter_records(
    root: Path,
    start: int,
    end: int,
    warmup_hours: int = 336,
    *,
    data_dir: str = "data",
    execution_model: str | None = None,
    include_closed_bars: bool = False,
):
    """Merge dataset/symbol streams while retaining required prior observations."""
    if start >= end or warmup_hours < 0:
        raise ValueError("Invalid replay range")
    root = Path(root).resolve()
    manifest_path = root / data_dir / "manifests" / "processed.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    grouped: dict[tuple[str, str, str], list[dict]] = {}
    for entry in manifest.get("entries", []):
        grouped.setdefault(
            (entry["dataset"], entry.get("symbol", ""), entry.get("market", "")), []
        ).append(entry)
    streams = []
    for (dataset, _symbol, _market), entries in grouped.items():
        if execution_model == "next_minute_vwap":
            if dataset not in {"minute_bars", "marks", "funding", "gaps"}:
                continue
        elif dataset == "minute_bars" and not include_closed_bars:
            continue
        lower = start - warmup_hours * HOUR if dataset == "funding" else start
        selected = _select_partitions(entries, lower, end)
        streams.append(
            _windowed(
                _partition_chain(root, selected),
                lower,
                end,
                prefer_boundary=dataset == "minute_bars",
            )
        )
    yield from heapq.merge(*streams, key=event_key)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def input_hashes(root: Path, config=None) -> dict[str, str]:
    """Return hashes for replay inputs and the manifests that make them usable."""
    root = Path(root).resolve()
    data_dir = config.data_dir if config else "data"
    rules_file = config.rules_file if config else "data/rules/history.json"
    paths = [root / rules_file]
    processed = root / data_dir / "manifests" / "processed.json"
    result = {}
    if processed.exists():
        manifest = json.loads(processed.read_text(encoding="utf-8"))
        paths.extend(root / entry["path"] for entry in manifest.get("entries", []))
        semantic = {k: v for k, v in manifest.items() if k != "source_manifest_sha256"}
        result["processed_manifest_semantics"] = hashlib.sha256(
            json.dumps(semantic, sort_keys=True).encode()
        ).hexdigest()
    raw_manifest = root / data_dir / "manifests" / "download.json"
    if raw_manifest.exists():
        for entry in json.loads(raw_manifest.read_text(encoding="utf-8")).get("entries", []):
            if entry.get("status") in {"cached", "downloaded"}:
                paths.append(root / entry["path"])
                if entry.get("checksum_path"):
                    paths.append(root / entry["checksum_path"])
                for supplement in entry.get("supplements", []):
                    paths.append(root / supplement["path"])
                    if supplement.get("checksum_path"):
                        paths.append(root / supplement["checksum_path"])
    result.update(
        {
            str(path.relative_to(root)).replace("\\", "/"): _sha256(path)
            for path in paths
            if path.exists()
        }
    )
    return result
