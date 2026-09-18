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
from ..models import Funding, Mark, Trade


def _records(path: Path, dataset: str) -> Iterator[Trade | Funding | Mark | DataGap]:
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


def _partition_chain(root: Path, entries: list[dict]) -> Iterator:
    for entry in sorted(entries, key=lambda value: (int(value.get("start", 0)), value["path"])):
        yield from _records(root / entry["path"], entry["dataset"])


def _windowed(records: Iterable, lower: int, end: int) -> Iterator:
    """Keep one antecedent and the requested half-open time range."""
    antecedent = None
    for record in records:
        value = event_time(record)
        if value < lower:
            antecedent = record
            continue
        if antecedent is not None:
            yield antecedent
            antecedent = None
        if value >= end:
            return
        yield record


def iter_records(
    root: Path, start: int, end: int, warmup_hours: int = 336, *, data_dir: str = "data"
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
        lower = start - warmup_hours * HOUR if dataset == "funding" else start
        streams.append(_windowed(_partition_chain(root, entries), lower, end))
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
    result.update(
        {
            str(path.relative_to(root)).replace("\\", "/"): _sha256(path)
            for path in paths
            if path.exists()
        }
    )
    return result
