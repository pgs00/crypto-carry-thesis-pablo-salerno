"""Acquire the six verified daily mark archives absent from monthly sources.

Run from the repository root after the minute download. Original monthly ZIPs
remain unchanged. Supplemental files and official checksums live on D:; their
provenance is attached to the monthly manifest entry for offline normalization.
"""

import argparse
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

from crypto_carry.config import Config, iso, timestamp
from crypto_carry.data.download import (
    VISION,
    _checksum_value,
    _response_bytes,
    _sha256,
    _write_raw_bytes,
    download_verified_archive,
)
from crypto_carry.data.minute_download import _save_manifest
from crypto_carry.data.normalize import _csv_rows

DAYS = {
    "2022_2023": ("2022-10-02", "2023-02-24"),
    "2025_2026": ("2026-06-29",),
}
SOURCE = "https://www.binance.com/en/blog/from-our-ceo/6789340645608890113"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("D:/Backtesting"))
    args = parser.parse_args()
    root = args.root.resolve()
    audit = {
        "retrieved_at": datetime.now(UTC).isoformat(),
        "reason": "Monthly official mark archives each omit one full day; exact official daily observations restore coverage",
        "original_raw_files_modified": False,
        "spot_closure": {
            "date": "2023-03-24",
            "reported_halt_start_utc": "11:27:00",
            "reported_resume_utc": "14:00:00",
            "source_url": SOURCE,
            "treatment": "Documented non-trading minutes are recorded as unavailable; no fabricated price or volume records",
        },
        "supplements": [],
    }
    with httpx.Client(timeout=60, follow_redirects=True) as client:
        for window, days in DAYS.items():
            config = Config.load(Path("configs") / f"download_minutes_{window}_d.toml")
            manifest_path = root / config.data_dir / "manifests/download.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            for day in days:
                for symbol in config.symbols:
                    parent = next(
                        row
                        for row in manifest["entries"]
                        if row["dataset"] == "marks"
                        and row["symbol"] == symbol
                        and row["start"].startswith(day[:7])
                    )
                    if _sha256(root / parent["path"]) != parent["sha256"]:
                        raise ValueError("Original monthly source checksum changed")
                    name = f"{symbol}-1m-{day}.zip"
                    url = f"{VISION}/futures/um/daily/markPriceKlines/{symbol}/1m/{name}"
                    destination = (root / parent["path"]).parent / "daily" / name
                    if (root / config.data_dir).resolve() not in destination.resolve().parents:
                        raise ValueError("Supplement destination escapes configured dataset")
                    checksum_body = _response_bytes(client, url + ".CHECKSUM")
                    expected = _checksum_value(checksum_body, url + ".CHECKSUM")
                    checksum_path = destination.with_suffix(".zip.CHECKSUM")
                    checksum = _write_raw_bytes(
                        checksum_path,
                        checksum_body,
                        root / "data/minutes",
                        config.data_budget_bytes,
                    )
                    outcome = download_verified_archive(
                        client,
                        url,
                        destination,
                        expected_sha256=expected,
                        budget_limit=config.data_budget_bytes,
                        data_root=root / "data/minutes",
                    )
                    rows = [row for row in _csv_rows(destination) if row and row[0].isdigit()]
                    begin = datetime.fromisoformat(day).replace(tzinfo=UTC)
                    first_ms = timestamp(begin.isoformat()) // 1_000_000
                    if [int(row[0]) for row in rows] != list(
                        range(first_ms, first_ms + 86_400_000, 60_000)
                    ):
                        raise ValueError(f"Daily source is not a complete minute grid: {url}")
                    supplement = {
                        **outcome,
                        "dataset": "marks",
                        "symbol": symbol,
                        "market": "futures",
                        "path": destination.relative_to(root).as_posix(),
                        "source_url": url,
                        "start": iso(timestamp(begin.isoformat())),
                        "end": iso(timestamp((begin + timedelta(days=1)).isoformat()) - 1),
                        "timestamp_unit": "ms",
                        "rows": len(rows),
                        "checksum_path": checksum_path.relative_to(root).as_posix(),
                        "checksum_file_sha256": checksum["sha256"],
                        "checksum_url": url + ".CHECKSUM",
                    }
                    previous = {row["path"]: row for row in parent.get("supplements", [])}
                    previous[supplement["path"]] = supplement
                    parent["supplements"] = list(previous.values())
                    audit["supplements"].append(
                        {"window": window, "parent": parent["path"], **supplement}
                    )
                    _save_manifest(
                        manifest_path, manifest, root / "data/minutes", config.data_budget_bytes
                    )
                    print(
                        f"{window} {symbol} {day}: 1440 official minute marks verified", flush=True
                    )
    output = Path(__file__).with_name("source-repair-audit.json")
    audit["script_sha256"] = _sha256(Path(__file__))
    output.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    print(output, flush=True)


if __name__ == "__main__":
    main()
