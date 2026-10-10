"""Opt-in, reproducible estimates for the fifteen documented missing mark candles.

The allowlist is deliberately code-pinned: editing a CSV cannot authorize another
gap. Original partitions are never modified. All non-mark inputs remain identical.
"""

from __future__ import annotations

import json
from collections import defaultdict
from decimal import Decimal as D
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from ..config import Config, iso, timestamp
from .replay import _sha256

MINUTE = 60_000_000_000
METHODS = ("futures_scaled", "last_official")
OHLC = ("open", "high", "low", "close")
# Source: continuous-preparation-20260919/unresolved_mark_minutes.csv.
APPROVED_MINUTES = frozenset(
    [
        ("ETHUSDT", timestamp(f"2022-07-12T{t}:00Z"))
        for t in (
            "12:57",
            "13:07",
            "13:15",
            "13:16",
            "13:17",
            "13:18",
            "13:19",
            "13:20",
            "13:21",
            "13:52",
        )
    ]
    + [("ETHUSDT", timestamp("2022-07-13T06:59:00Z"))]
    + [
        (s, timestamp(f"2024-08-12T10:{m}:00Z"))
        for s in ("BTCUSDT", "ETHUSDT")
        for m in ("02", "03")
    ]
)


def official_anchor(symbol: str, t: int) -> int:
    anchor = t - MINUTE
    while (symbol, anchor) in APPROVED_MINUTES:
        anchor -= MINUTE
    return anchor


def _closed(row: dict, symbol: str, t: int, *, mark: bool) -> None:
    expected = t + MINUTE
    if row["symbol"] != symbol or row["open_time"] != t or row["available_at"] != expected:
        raise ValueError(f"Unavailable closed candle: {symbol} {iso(t)}")
    if (
        (row.get("close_time") != expected - 1_000_000)
        if mark
        else (row.get("end_time") != expected or row.get("market") != "futures")
    ):
        raise ValueError("Invalid closed-candle interval")
    values = {k: D(row[k]) for k in OHLC}
    if any(not v.is_finite() or v <= 0 for v in values.values()) or not (
        values["low"]
        <= min(values["open"], values["close"])
        <= max(values["open"], values["close"])
        <= values["high"]
    ):
        raise ValueError("Invalid candle OHLC")
    if mark and row.get("estimation_method", "official") != "official":
        raise ValueError("Anchor must be an official mark")


def estimate_gap(symbol, missing, marks, futures, method) -> tuple[list[dict], list[dict]]:
    """Use only the fixed official antecedent and the currently closed future bar."""
    if method not in METHODS or not missing or len(set(missing)) != len(missing):
        raise ValueError("Invalid explicit mark estimation request")
    missing = sorted(missing)
    if any((symbol, t) not in APPROVED_MINUTES or t in marks for t in missing):
        raise ValueError("Only absent, documented mark minutes may be estimated")
    rows, audit = [], []
    anchor = None
    previous = None
    for t in missing:
        if previous is None or t != previous + MINUTE:
            anchor = t - MINUTE
        if anchor not in marks:
            raise ValueError(f"Missing official mark anchor: {symbol} {iso(anchor)}")
        official = marks[anchor]
        _closed(official, symbol, anchor, mark=True)
        factor = None
        needed = {}
        if method == "futures_scaled":
            for label, when in (("anchor_future", anchor), ("current_future", t)):
                if when not in futures:
                    raise ValueError(f"Missing required futures candle: {symbol} {iso(when)}")
                _closed(futures[when], symbol, when, mark=False)
                needed[label] = dict(futures[when])
            factor = D(official["close"]) / D(futures[anchor]["close"])
            values = {k: str(D(futures[t][k]) * factor) for k in OHLC}
        else:
            values = {k: str(D(official["close"])) for k in OHLC}
        row = dict(
            symbol=symbol,
            open_time=t,
            close_time=t + MINUTE - 1_000_000,
            available_at=t + MINUTE,
            **values,
            source_file=f"estimated:{method}:{symbol}:{t}:anchor={anchor}",
            estimation_method=method,
            anchor_open_time=anchor,
        )
        rows.append(row)
        audit.append(
            dict(
                **row,
                open_time_utc=iso(t),
                available_at_utc=iso(t + MINUTE),
                anchor_open_time_utc=iso(anchor),
                anchor_mark=dict(official),
                factor=str(factor) if factor is not None else None,
                **needed,
            )
        )
        previous = t
    return rows, audit


def _inside(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if path == root or root not in path.parents:
        raise ValueError("Derived data paths must remain within the data root")
    return path


def _checked_rows(root: Path, entry: dict) -> list[dict]:
    path = _inside(root, entry["path"])
    if _sha256(path) != entry["sha256"]:
        raise ValueError(f"Original source hash mismatch: {entry['path']}")
    rows = pq.ParquetFile(path).read().to_pylist()
    if len(rows) != entry["rows"]:
        raise ValueError("Original source row count mismatch")
    return rows


def _replacement_plan(root: Path, source: dict, method: str):
    if source.get("mark_gap_derivation") or source.get("errors"):
        raise ValueError("Estimates require original, error-free normalized sources")
    groups = defaultdict(list)
    for symbol, t in sorted(APPROVED_MINUTES):
        groups[symbol, iso(t)[:7]].append(t)
    replacements, audit = {}, []
    for (symbol, month), missing in groups.items():

        def select(dataset):
            matches = [
                e
                for e in source["entries"]
                if e["dataset"] == dataset
                and e["symbol"] == symbol
                and e["market"] == "futures"
                and e.get("date") == month
            ]
            if len(matches) != 1:
                raise ValueError(
                    f"Missing or ambiguous original partition: {symbol}/{month}/{dataset}"
                )
            return matches[0]

        entry = select("marks")
        original = _checked_rows(root, entry)
        marks = {r["open_time"]: r for r in original}
        expected = set(range(entry["start"] - MINUTE, entry["end"], MINUTE))
        if (
            len(marks) != len(original)
            or expected - marks.keys() != set(missing)
            or marks.keys() - expected
        ):
            raise ValueError("Original mark gaps differ from the documented allowlist")
        if any(r.get("estimation_method", "official") != "official" for r in original):
            raise ValueError("Original mark partitions must contain only official observations")
        futures = {}
        future_entry = None
        if method == "futures_scaled":
            future_entry = select("minute_bars")
            future_rows = _checked_rows(root, future_entry)
            futures = {r["open_time"]: r for r in future_rows}
            if len(futures) != len(future_rows):
                raise ValueError("Duplicate futures candles")
        estimates, evidence = estimate_gap(symbol, missing, marks, futures, method)
        for row in evidence:
            row.update(
                original_mark_path=entry["path"],
                original_mark_sha256=entry["sha256"],
                futures_path=future_entry["path"] if future_entry else None,
                futures_sha256=future_entry["sha256"] if future_entry else None,
            )
        audit.extend(evidence)
        merged = [dict(r, estimation_method="official", anchor_open_time=None) for r in original]
        merged.extend(estimates)
        merged.sort(key=lambda r: r["open_time"])
        replacements[entry["path"]] = merged
    return replacements, audit


def _immutable(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != content:
            raise ValueError(f"Immutable derived artifact differs: {path}")
    else:
        path.write_bytes(content)


def _json(value) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def prepare_mark_gaps(config: Config, root: Path, method: str) -> Config:
    """Write three replacement partitions and reference every other original input."""
    root = Path(root).resolve()
    if config.mark_gap_method != "strict" or method not in METHODS:
        raise ValueError("Preparation requires strict original inputs and an explicit method")
    target = config.changed(
        mark_gap_method=method, data_dir=f"{config.data_dir}/derived_marks/{method}"
    )
    base = _inside(root, config.data_dir) / "manifests"
    source = json.loads((base / "processed.json").read_text(encoding="utf-8"))
    replacements, audit = _replacement_plan(root, source, method)
    destination = _inside(root, target.data_dir)
    manifests = destination / "manifests"
    entries = []
    for entry in source["entries"]:
        if entry["path"] not in replacements:
            entries.append(entry)
            continue
        rows = replacements[entry["path"]]
        table = pa.Table.from_pylist(rows)
        path = destination / "processed" / f"{entry['symbol']}-{entry['date']}-marks.parquet"
        sink = pa.BufferOutputStream()
        pq.write_table(table, sink, compression="zstd")
        _immutable(path, sink.getvalue().to_pybytes())
        entries.append(
            dict(
                entry,
                path=path.relative_to(root).as_posix(),
                sha256=_sha256(path),
                bytes=path.stat().st_size,
                rows=len(rows),
                complete=True,
                minute_coverage_complete=True,
                schema={f.name: str(f.type) for f in table.schema},
                original_partition=entry["path"],
            )
        )
    _immutable(manifests / "original_processed.json", (base / "processed.json").read_bytes())
    _immutable(manifests / "download.json", (base / "download.json").read_bytes())
    _immutable(manifests / "mark_gap_audit.json", _json(audit))
    derivation = dict(
        method=method,
        coverage_kind="completed_with_approximations",
        estimated_minutes=15,
        original_manifest=(manifests / "original_processed.json").relative_to(root).as_posix(),
        original_manifest_sha256=_sha256(base / "processed.json"),
        original_download_sha256=_sha256(base / "download.json"),
        original_config=config.to_dict(),
        audit_path=(manifests / "mark_gap_audit.json").relative_to(root).as_posix(),
        audit_sha256=_sha256(manifests / "mark_gap_audit.json"),
    )
    derived = dict(source, entries=entries, mark_gap_derivation=derivation)
    _immutable(manifests / "processed.json", _json(derived))
    _immutable(manifests / "effective_config.toml", target.to_toml().encode())
    verify_mark_derivation(target, root, derived)
    return target


def verify_mark_derivation(config: Config, root: Path, manifest: dict) -> list[dict]:
    """Recompute all estimates and prove every other normalized row is unchanged."""
    root = Path(root).resolve()
    derivation = manifest.get("mark_gap_derivation")
    if config.mark_gap_method == "strict":
        if derivation or any(
            e.get("original_partition") or "estimation_method" in e.get("schema", {})
            for e in manifest.get("entries", [])
        ):
            raise ValueError("Strict validation refuses estimated mark inputs")
        return []
    if not derivation or derivation.get("method") != config.mark_gap_method:
        raise ValueError("Explicit mark method does not match a verified derived layer")
    if (
        derivation.get("coverage_kind") != "completed_with_approximations"
        or derivation.get("estimated_minutes") != 15
    ):
        raise ValueError("Invalid approximation coverage description")
    source_path = _inside(root, derivation["original_manifest"])
    audit_path = _inside(root, derivation["audit_path"])
    download_path = root / config.data_dir / "manifests/download.json"
    for path, digest in (
        (source_path, derivation["original_manifest_sha256"]),
        (audit_path, derivation["audit_sha256"]),
        (download_path, derivation["original_download_sha256"]),
    ):
        if _sha256(path) != digest:
            raise ValueError(f"Derived provenance hash mismatch: {path.name}")
    source = json.loads(source_path.read_text(encoding="utf-8"))
    replacements, audit = _replacement_plan(root, source, config.mark_gap_method)
    if json.loads(audit_path.read_text(encoding="utf-8")) != audit or len(audit) != 15:
        raise ValueError("Mark estimates differ from reproducible source evidence")
    if len(manifest["entries"]) != len(source["entries"]):
        raise ValueError("Derived manifest adds or removes original partitions")
    for original, derived in zip(source["entries"], manifest["entries"], strict=True):
        if original["path"] not in replacements:
            if original != derived:
                raise ValueError("Non-estimated source partition changed")
            continue
        if derived.get("original_partition") != original["path"]:
            raise ValueError("Derived partition has a different original source")
        if _checked_rows(root, derived) != replacements[original["path"]]:
            raise ValueError("Derived partition differs from original rows plus approved estimates")
        allowed_changes = {
            "path",
            "sha256",
            "bytes",
            "rows",
            "complete",
            "minute_coverage_complete",
            "schema",
            "original_partition",
        }
        if {k: v for k, v in derived.items() if k not in allowed_changes} != {
            k: v for k, v in original.items() if k not in allowed_changes
        }:
            raise ValueError("Derived partition changed original source metadata")
    return audit
