"""Download and audit official ETHUSDT trades around the 2023-03-24 outage.

This diagnostic does not alter normalized inputs or rerun the strategy.  It
keeps the two validation archives outside the historical raw-data trees and
compares individual source trades with the immutable early-window baseline.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import re
import urllib.request
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, getcontext
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

getcontext().prec = 40

DAY = "2023-03-24"
SYMBOL = "ETHUSDT"
MAX_DOWNLOAD_BYTES = 250_000_000
DATA_BUDGET_BYTES = 20_000_000_000
DEFAULT_OUTPUT_DIR = Path("D:/Backtesting/data/minutes/validation_20230324")
DEFAULT_BASELINE = Path("D:/Backtesting/outputs/run_8fb22fa8b377466cff981b99")
DEFAULT_REPORT = Path(__file__).with_name("outage-trades-validation.json")


@dataclass(frozen=True)
class Source:
    market: str
    dataset: str
    url: str
    columns: tuple[str, ...]
    boundary_utc: str

    @property
    def filename(self) -> str:
        return self.url.rsplit("/", 1)[-1]


SOURCES = (
    Source(
        market="spot",
        dataset="spot/daily/trades",
        url=(
            "https://data.binance.vision/data/spot/daily/trades/ETHUSDT/"
            "ETHUSDT-trades-2023-03-24.zip"
        ),
        columns=("id", "price", "qty", "quote_qty", "time", "is_buyer_maker", "is_best_match"),
        boundary_utc="2023-03-24T14:00:00Z",
    ),
    Source(
        market="futures",
        dataset="futures/um/daily/trades",
        url=(
            "https://data.binance.vision/data/futures/um/daily/trades/ETHUSDT/"
            "ETHUSDT-trades-2023-03-24.zip"
        ),
        columns=("id", "price", "qty", "quote_qty", "time", "is_buyer_maker"),
        boundary_utc="2023-03-24T11:59:00Z",
    ),
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def tree_bytes(path: Path) -> int:
    total = 0
    if not path.exists():
        return total
    for root, _, files in os.walk(path):
        for name in files:
            total += (Path(root) / name).stat().st_size
    return total


def request(url: str, method: str = "GET") -> urllib.request.Request:
    return urllib.request.Request(
        url,
        method=method,
        headers={"User-Agent": "crypto-carry-outage-trade-validation/1.0"},
    )


def head(source: Source) -> dict[str, Any]:
    with urllib.request.urlopen(request(source.url, "HEAD"), timeout=60) as response:
        if response.status != 200:
            raise ValueError(f"HEAD {source.url} returned {response.status}")
        return {
            "status": response.status,
            "content_length": int(response.headers["Content-Length"]),
            "etag": response.headers.get("ETag"),
            "last_modified": response.headers.get("Last-Modified"),
        }


def download(url: str, destination: Path) -> str:
    if destination.exists():
        return "reused"
    temporary = destination.with_name(destination.name + ".part")
    temporary.unlink(missing_ok=True)
    try:
        with (
            urllib.request.urlopen(request(url), timeout=120) as response,
            temporary.open("wb") as out,
        ):
            if response.status != 200:
                raise ValueError(f"GET {url} returned {response.status}")
            for block in iter(lambda: response.read(1024 * 1024), b""):
                out.write(block)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    return "downloaded"


def parse_official_checksum(path: Path, expected_filename: str) -> str:
    fields = path.read_text(encoding="ascii").strip().split()
    if len(fields) != 2 or not re.fullmatch(r"[0-9a-fA-F]{64}", fields[0]):
        raise ValueError(f"Malformed official checksum: {path}")
    if Path(fields[1].lstrip("*")).name != expected_filename:
        raise ValueError(f"Checksum filename does not match {expected_filename}: {fields[1]}")
    return fields[0].lower()


def to_ms(value: str) -> int:
    return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp() * 1000)


def iso_ms(value: int) -> str:
    return (
        datetime.fromtimestamp(value / 1000, tz=timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def decimal_string(value: Decimal | None) -> str | None:
    return None if value is None else format(value, "f")


def normalize_row(raw: list[str], columns: tuple[str, ...]) -> dict[str, Any]:
    if len(raw) != len(columns):
        raise ValueError(f"Expected {len(columns)} trade columns, found {len(raw)}")
    row = dict(zip(columns, raw, strict=True))
    time_value = int(row["time"])
    if time_value >= 10**15:
        if time_value % 1000:
            raise ValueError(
                f"Sub-millisecond source timestamp is outside this audit contract: {time_value}"
            )
        time_value //= 1000
    return {
        "id": int(row["id"]),
        "price": Decimal(row["price"]),
        "qty": Decimal(row["qty"]),
        "quote_qty": Decimal(row["quote_qty"]),
        "time_ms": time_value,
        "is_buyer_maker": row["is_buyer_maker"].lower() == "true",
    }


def trade_json(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "id": row["id"],
        "timestamp_utc": iso_ms(row["time_ms"]),
        "time_ms": row["time_ms"],
        "price": decimal_string(row["price"]),
        "quantity": decimal_string(row["qty"]),
        "quote_quantity": decimal_string(row["quote_qty"]),
        "is_buyer_maker": row["is_buyer_maker"],
    }


def id_time_audit(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ids = [row["id"] for row in rows]
    times = [row["time_ms"] for row in rows]
    deltas = [right - left for left, right in zip(ids, ids[1:])]
    time_deltas = [right - left for left, right in zip(times, times[1:])]
    return {
        "rows": len(rows),
        "first_id": ids[0] if ids else None,
        "last_id": ids[-1] if ids else None,
        "duplicate_id_count": sum(delta == 0 for delta in deltas),
        "nonmonotone_id_count": sum(delta < 0 for delta in deltas),
        "missing_id_count": sum(delta - 1 for delta in deltas if delta > 1),
        "timestamp_regression_count": sum(delta < 0 for delta in time_deltas),
        "max_intertrade_gap_ms": max(time_deltas, default=None),
    }


def window_stats(
    rows: Iterable[dict[str, Any]],
    boundary_ms: int,
    seconds: int,
    fill: dict[str, Any],
    first_price: Decimal,
) -> dict[str, Any]:
    selected = [row for row in rows if boundary_ms < row["time_ms"] <= boundary_ms + seconds * 1000]
    volume = sum((row["qty"] for row in selected), Decimal(0))
    notional = sum((row["price"] * row["qty"] for row in selected), Decimal(0))
    vwap = notional / volume if volume else None
    fill_price = Decimal(str(fill["price"]))
    if vwap is None:
        adverse_bps = None
        gross_pnl_delta = None
    elif fill["side"] == "BUY":
        adverse_bps = (fill_price - vwap) / vwap * Decimal(10_000)
        gross_pnl_delta = (fill_price - vwap) * Decimal(str(fill["quantity"]))
    else:
        adverse_bps = (vwap - fill_price) / vwap * Decimal(10_000)
        gross_pnl_delta = (vwap - fill_price) * Decimal(str(fill["quantity"]))
    prices = [row["price"] for row in selected]
    at_first = [row for row in selected if row["price"] == first_price]
    if fill["side"] == "BUY":
        at_or_better = [row for row in selected if row["price"] <= fill_price]
    else:
        at_or_better = [row for row in selected if row["price"] >= fill_price]
    at_or_better_volume = sum((row["qty"] for row in at_or_better), Decimal(0))
    return {
        "interval": f"({iso_ms(boundary_ms)}, {iso_ms(boundary_ms + seconds * 1000)}]",
        "trade_count": len(selected),
        "base_volume": decimal_string(volume),
        "quote_notional_from_price_quantity": decimal_string(notional),
        "vwap": decimal_string(vwap),
        "low": decimal_string(min(prices)) if prices else None,
        "high": decimal_string(max(prices)) if prices else None,
        "first_price_trade_count": len(at_first),
        "first_price_base_volume": decimal_string(
            sum((row["qty"] for row in at_first), Decimal(0))
        ),
        "first_price_minus_vwap_bps": decimal_string(
            (first_price - vwap) / vwap * Decimal(10_000) if vwap else None
        ),
        "first_price_is_window_high": first_price == max(prices) if prices else None,
        "source_volume_at_or_better_than_baseline_fill": decimal_string(at_or_better_volume),
        "baseline_quantity_over_at_or_better_volume": decimal_string(
            Decimal(str(fill["quantity"])) / at_or_better_volume if at_or_better_volume else None
        ),
        "baseline_quantity_over_window_volume": decimal_string(
            Decimal(str(fill["quantity"])) / volume if volume else None
        ),
        "baseline_fill_adverse_to_vwap_bps": decimal_string(adverse_bps),
        "gross_pnl_delta_if_vwap_replaced_baseline_fill_usdt": decimal_string(gross_pnl_delta),
    }


def analyze_zip(
    source: Source,
    archive: Path,
    fill: dict[str, Any],
) -> dict[str, Any]:
    boundary_ms = to_ms(source.boundary_utc)
    prior: dict[str, Any] | None = None
    first_after: dict[str, Any] | None = None
    first_different: dict[str, Any] | None = None
    same_price_until_change_count = 0
    same_price_until_change_volume = Decimal(0)
    target_rows: list[dict[str, Any]] = []
    day_rows = 0
    first_day: dict[str, Any] | None = None
    last_day: dict[str, Any] | None = None
    day_id_missing = day_id_duplicates = day_id_nonmonotone = time_regressions = 0
    previous_id: int | None = None
    previous_time: int | None = None

    with zipfile.ZipFile(archive) as zipped:
        members = [entry for entry in zipped.infolist() if not entry.is_dir()]
        if len(members) != 1 or not members[0].filename.endswith(".csv"):
            raise ValueError(
                f"Expected one CSV member in {archive}, found {[m.filename for m in members]}"
            )
        with (
            zipped.open(members[0]) as binary,
            io.TextIOWrapper(binary, encoding="utf-8", newline="") as text,
        ):
            reader = csv.reader(text)
            first_raw = next(reader, None)
            if first_raw is None:
                raise ValueError(f"Empty trade archive: {archive}")
            has_header = first_raw[0].strip().lower() == "id"
            raw_rows: Iterable[list[str]] = reader if has_header else _prepend(first_raw, reader)
            for raw in raw_rows:
                row = normalize_row(raw, source.columns)
                day_rows += 1
                first_day = first_day or row
                last_day = row
                if previous_id is not None:
                    delta = row["id"] - previous_id
                    day_id_duplicates += delta == 0
                    day_id_nonmonotone += delta < 0
                    day_id_missing += max(delta - 1, 0)
                    time_regressions += row["time_ms"] < previous_time
                previous_id, previous_time = row["id"], row["time_ms"]

                if row["time_ms"] <= boundary_ms:
                    prior = row
                elif first_after is None:
                    first_after = row

                if boundary_ms - 60_000 <= row["time_ms"] <= boundary_ms + 60_000:
                    target_rows.append(row)

                if (
                    first_after is not None
                    and first_different is None
                    and row["time_ms"] > boundary_ms
                ):
                    if row["price"] == first_after["price"]:
                        same_price_until_change_count += 1
                        same_price_until_change_volume += row["qty"]
                    else:
                        first_different = row

    if first_after is None:
        raise ValueError(f"No trade strictly after {source.boundary_utc} in {archive}")
    if first_day is None or last_day is None:
        raise ValueError(f"No trades in {archive}")

    member = members[0]
    boundary_gap = None
    if prior is not None:
        boundary_gap = {
            "last_at_or_before_boundary": trade_json(prior),
            "first_strictly_after_boundary": trade_json(first_after),
            "elapsed_ms": first_after["time_ms"] - prior["time_ms"],
            "id_delta": first_after["id"] - prior["id"],
            "missing_ids_between": max(first_after["id"] - prior["id"] - 1, 0),
        }
    reference = Decimal(str(fill["reference_price"]))
    fill_price = Decimal(str(fill["price"]))
    return {
        "zip_member": {
            "name": member.filename,
            "compressed_bytes": member.compress_size,
            "uncompressed_bytes": member.file_size,
            "crc32": f"{member.CRC:08x}",
        },
        "csv_header_present": has_header,
        "day": {
            "row_count": day_rows,
            "first_trade": trade_json(first_day),
            "last_trade": trade_json(last_day),
            "id_audit": {
                "duplicate_id_count": day_id_duplicates,
                "nonmonotone_id_count": day_id_nonmonotone,
                "missing_id_count": day_id_missing,
                "timestamp_regression_count": time_regressions,
            },
        },
        "boundary_utc": source.boundary_utc,
        "boundary_gap": boundary_gap,
        "first_trade_strictly_after_boundary": trade_json(first_after),
        "first_trade_vs_baseline": {
            "reference_price": decimal_string(reference),
            "fill_price": decimal_string(fill_price),
            "first_source_price": decimal_string(first_after["price"]),
            "reference_minus_first_source": decimal_string(reference - first_after["price"]),
            "fill_minus_first_source": decimal_string(fill_price - first_after["price"]),
            "absolute_fill_vs_first_source_bps": decimal_string(
                abs(fill_price - first_after["price"]) / first_after["price"] * Decimal(10_000)
            ),
        },
        "first_price_persistence": {
            "first_different_trade": trade_json(first_different),
            "milliseconds_until_different_price": (
                first_different["time_ms"] - first_after["time_ms"] if first_different else None
            ),
            "same_price_trade_count_until_change": same_price_until_change_count,
            "same_price_base_volume_until_change": decimal_string(same_price_until_change_volume),
            "baseline_quantity_over_same_price_volume_until_change": decimal_string(
                Decimal(str(fill["quantity"])) / same_price_until_change_volume
                if same_price_until_change_volume
                else None
            ),
            "ephemeral_under_one_second": (
                first_different is not None
                and first_different["time_ms"] - first_after["time_ms"] < 1000
            ),
        },
        "windows": {
            str(seconds): window_stats(
                target_rows, boundary_ms, seconds, fill, first_after["price"]
            )
            for seconds in (1, 5, 60)
        },
        "short_window_id_time_audit": id_time_audit(target_rows),
    }


def _prepend(first: list[str], rows: Iterable[list[str]]) -> Iterable[list[str]]:
    yield first
    yield from rows


def baseline_fills(path: Path) -> dict[str, dict[str, Any]]:
    manifest = json.loads((path / "run_manifest.json").read_text(encoding="utf-8"))
    if manifest.get("run_id") != path.name or manifest.get("status") != "complete":
        raise ValueError(f"Baseline is not a complete immutable run: {path}")
    fills = pd.read_parquet(path / "fills.parquet")
    orders = pd.read_parquet(path / "orders.parquet")
    selected = fills[
        (fills["strategy"] == "conditional")
        & (fills["symbol"] == SYMBOL)
        & fills["timestamp_utc"].astype(str).str.startswith(DAY)
    ]
    wanted = {
        "futures": ("2023-03-24T11:59:00.000000000Z", "close_perp"),
        "spot": ("2023-03-24T14:00:00.000000000Z", "close_spot"),
    }
    result: dict[str, dict[str, Any]] = {}
    for market, (timestamp, purpose) in wanted.items():
        rows = selected[
            (selected["market"] == market)
            & (selected["timestamp_utc"] == timestamp)
            & (selected["purpose"] == purpose)
        ]
        if len(rows) != 1:
            raise ValueError(
                f"Expected one {market} baseline fill at {timestamp}, found {len(rows)}"
            )
        row = rows.iloc[0]
        result[market] = {
            key: str(row[key])
            for key in (
                "fill_id",
                "order_id",
                "timestamp_utc",
                "market",
                "side",
                "quantity",
                "price",
                "reference_price",
                "trade_id",
                "fee_rate",
                "purpose",
            )
        }
        submitted = orders[
            (orders["order_id"] == row["order_id"])
            & (orders["strategy"] == "conditional")
            & (orders["action"] == "submitted")
        ]
        if len(submitted) != 1:
            raise ValueError(
                f"Expected one submission row for {row['order_id']}, found {len(submitted)}"
            )
        order = submitted.iloc[0]
        result[market]["submitted_at_utc"] = str(order["submitted_at_utc"])
        result[market]["deadline_utc"] = str(order["deadline_utc"])
        result[market]["submitted_seconds_before_fill"] = str(
            (int(row["time_ns"]) - int(order["submitted_at"])) / 1_000_000_000
        )
    result["run"] = {
        "path": str(path),
        "run_id": manifest["run_id"],
        "manifest_sha256": sha256_file(path / "run_manifest.json"),
        "fills_sha256": sha256_file(path / "fills.parquet"),
        "status": manifest["status"],
    }
    return result


def source_metadata(source: Source, output_dir: Path, header: dict[str, Any]) -> dict[str, Any]:
    source_dir = output_dir / source.market
    source_dir.mkdir(parents=True, exist_ok=True)
    archive = source_dir / source.filename
    checksum = source_dir / f"{source.filename}.CHECKSUM"
    archive_status = download(source.url, archive)
    checksum_status = download(f"{source.url}.CHECKSUM", checksum)
    if archive.stat().st_size != header["content_length"]:
        raise ValueError(f"Downloaded size does not match HEAD for {archive}")
    expected = parse_official_checksum(checksum, archive.name)
    actual = sha256_file(archive)
    if actual != expected:
        raise ValueError(f"Official SHA-256 mismatch for {archive}: {actual} != {expected}")
    with zipfile.ZipFile(archive) as zipped:
        bad_member = zipped.testzip()
    if bad_member is not None:
        raise ValueError(f"ZIP CRC failure in {archive}: {bad_member}")
    return {
        "market": source.market,
        "dataset": source.dataset,
        "source_url": source.url,
        "checksum_url": f"{source.url}.CHECKSUM",
        "path": str(archive),
        "checksum_path": str(checksum),
        "download_status": archive_status,
        "checksum_download_status": checksum_status,
        "bytes": archive.stat().st_size,
        "sha256": actual,
        "official_checksum_sha256": expected,
        "checksum_file_sha256": sha256_file(checksum),
        "checksum_verified": True,
        "zip_crc_verified": True,
        "http": header,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()

    if "raw" in {part.lower() for part in args.output_dir.parts}:
        raise ValueError("Validation downloads must not be stored in a raw-data tree")
    args.output_dir.mkdir(parents=True, exist_ok=True)

    headers = {source.market: head(source) for source in SOURCES}
    combined = sum(item["content_length"] for item in headers.values())
    if combined > MAX_DOWNLOAD_BYTES:
        raise ValueError(f"Combined official archives exceed the 250 MB cap: {combined}")
    data_root = args.output_dir.parent
    before_bytes = tree_bytes(data_root)
    missing_bytes = sum(
        headers[source.market]["content_length"]
        for source in SOURCES
        if not (args.output_dir / source.market / source.filename).exists()
    )
    if before_bytes + missing_bytes > DATA_BUDGET_BYTES:
        raise ValueError(
            f"Download would exceed the 20 GB minute-data budget: {before_bytes + missing_bytes}"
        )

    fills = baseline_fills(args.baseline)
    source_results: dict[str, Any] = {}
    for source in SOURCES:
        metadata = source_metadata(source, args.output_dir, headers[source.market])
        analysis = analyze_zip(source, Path(metadata["path"]), fills[source.market])
        source_results[source.market] = {**metadata, "analysis": analysis}

    after_bytes = tree_bytes(data_root)
    result = {
        "kind": "outage_trade_validation",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": {
            "symbol": SYMBOL,
            "date": DAY,
            "purpose": (
                "Sensitivity diagnosis of the immutable baseline's outage fills; no engine change, "
                "strategy rerun, synthetic continuity, or annual-return recomputation."
            ),
        },
        "limits": {
            "combined_archive_cap_bytes": MAX_DOWNLOAD_BYTES,
            "combined_archive_head_bytes": combined,
            "within_download_cap": True,
            "minute_data_budget_bytes": DATA_BUDGET_BYTES,
            "minute_data_tree_bytes_before": before_bytes,
            "minute_data_tree_bytes_after": after_bytes,
            "within_data_budget": after_bytes <= DATA_BUDGET_BYTES,
        },
        "baseline": fills,
        "sources": source_results,
        "findings": {
            "reference_prices_match_first_strict_source_trade": all(
                source_results[market]["analysis"]["first_trade_vs_baseline"][
                    "reference_minus_first_source"
                ]
                in ("0", "0.00", "0.00000000")
                for market in ("spot", "futures")
            ),
            "spot": {
                "halt_has_consecutive_boundary_trade_ids": (
                    source_results["spot"]["analysis"]["boundary_gap"]["id_delta"] == 1
                ),
                "first_trade_quantity_covers_baseline_fill": (
                    Decimal(
                        source_results["spot"]["analysis"]["first_trade_strictly_after_boundary"][
                            "quantity"
                        ]
                    )
                    >= Decimal(fills["spot"]["quantity"])
                ),
                "first_price_ephemeral_under_one_second": source_results["spot"]["analysis"][
                    "first_price_persistence"
                ]["ephemeral_under_one_second"],
                "interpretation": (
                    "The minute-open reference is an exact source trade and the first print alone is "
                    "larger than the baseline order. The price changes rapidly and is the high of each "
                    "restart window, so it is not representative of the subsequent 1/5/60-second "
                    "average. Trades establish prints and volume, but not resting depth or queue priority."
                ),
            },
            "scope_note": (
                "This validates source representativeness and execution sensitivity only; it is not a "
                "rerun or a revised annual return."
            ),
        },
        "definitions": {
            "strictly_after_boundary": "trade time_ms > boundary time_ms",
            "vwap_windows": "(boundary, boundary + seconds], weighted by source base quantity",
            "ephemeral_under_one_second": (
                "the first subsequent trade at a different price occurs less than 1000 ms after "
                "the first trade strictly after the boundary"
            ),
            "missing_id_count": "sum of positive gaps between consecutive source trade IDs",
            "gross_pnl_delta_if_vwap_replaced_baseline_fill_usdt": (
                "local price-times-quantity diagnostic before any fee change; positive means the VWAP "
                "would improve P&L versus the recorded fill. It is not a portfolio rerun."
            ),
        },
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.report.with_name(args.report.name + ".part")
    temporary.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(args.report)
    print(
        json.dumps(
            {
                "report": str(args.report),
                "combined_archive_bytes": combined,
                "minute_data_tree_bytes_after": after_bytes,
                "markets": list(source_results),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
