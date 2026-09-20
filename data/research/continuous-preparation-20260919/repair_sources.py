"""Reproduce the source investigation for continuous 2022-2026 minute history.

Only observed official daily rows can supplement monthly mark archives. Conflicting
overlaps abort; unresolved gaps are recorded and are never interpolated. The original
download manifest is snapshotted before attaching any additional daily source.
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
from crypto_carry.data.normalize import _merge_mark_rows, _verified_mark_supplement

TARGETS = (
    ("BTCUSDT", "2022-07-31"),
    ("ETHUSDT", "2022-07-12"),
    ("ETHUSDT", "2022-07-13"),
    ("BTCUSDT", "2024-08-12"),
    ("ETHUSDT", "2024-08-12"),
)
REPO = Path(__file__).resolve().parents[3]
MINUTE = 60_000_000_000


def investigate(root: Path, config: Config) -> dict:
    data_root = root / config.data_dir
    path = data_root / "manifests/download.json"
    original = path.read_bytes()
    original_hash = _sha256(path)
    manifest = json.loads(original)
    if manifest.get("kind") != "minute_market_data":
        raise ValueError("A completed minute download manifest is required")
    budget_root = root / "data/minutes"
    audit = dict(
        retrieved_at=datetime.now(UTC).isoformat(),
        script_sha256=_sha256(Path(__file__)),
        source_manifest_sha256_before=original_hash,
        original_archives_modified=False,
        entries=[],
        unresolved_minutes=[],
    )
    with httpx.Client(timeout=60, follow_redirects=True) as client:
        for symbol, day in TARGETS:
            parent = next(
                entry
                for entry in manifest["entries"]
                if entry["dataset"] == "marks"
                and entry["symbol"] == symbol
                and entry["start"].startswith(day[:7])
            )
            if _sha256(root / parent["path"]) != parent["sha256"]:
                raise ValueError("Original monthly source checksum changed")
            existing_paths = [root / parent["path"]] + [
                _verified_mark_supplement(root, parent, item)
                for item in parent.get("supplements", [])
            ]
            before = {row["open_time"] for row in _merge_mark_rows(existing_paths, symbol, {})}
            begin = datetime.fromisoformat(day).replace(tzinfo=UTC)
            lower = timestamp(begin.isoformat())
            upper = timestamp((begin + timedelta(days=1)).isoformat())
            expected_times = set(range(lower, upper, MINUTE))
            name = f"{symbol}-1m-{day}.zip"
            url = f"{VISION}/futures/um/daily/markPriceKlines/{symbol}/1m/{name}"
            destination = (root / parent["path"]).parent / "daily" / name
            content = _response_bytes(client, url + ".CHECKSUM")
            expected_hash = _checksum_value(content, url + ".CHECKSUM")
            checksum_path = destination.with_suffix(".zip.CHECKSUM")
            checksum = _write_raw_bytes(
                checksum_path, content, budget_root, config.data_budget_bytes
            )
            outcome = download_verified_archive(
                client,
                url,
                destination,
                expected_sha256=expected_hash,
                budget_limit=config.data_budget_bytes,
                data_root=budget_root,
            )
            supplement = dict(
                outcome,
                dataset="marks",
                symbol=symbol,
                market="futures",
                path=destination.relative_to(root).as_posix(),
                source_url=url,
                start=iso(lower),
                end=iso(upper - 1),
                timestamp_unit="ms",
                checksum_path=checksum_path.relative_to(root).as_posix(),
                checksum_file_sha256=checksum["sha256"],
                checksum_url=url + ".CHECKSUM",
            )
            verified_path = _verified_mark_supplement(root, parent, supplement)
            combined = list(dict.fromkeys([*existing_paths, verified_path]))
            after = {row["open_time"] for row in _merge_mark_rows(combined, symbol, {})}
            recovered = sorted((after - before) & expected_times)
            remaining = sorted(expected_times - after)
            if recovered:
                snapshot = path.with_name(f"download_before_repair_{original_hash[:16]}.json")
                _write_raw_bytes(snapshot, original, budget_root, config.data_budget_bytes)
                prior = {item["path"]: item for item in parent.get("supplements", [])}
                prior[supplement["path"]] = supplement
                parent["supplements"] = list(prior.values())
                _save_manifest(path, manifest, budget_root, config.data_budget_bytes)
            item = dict(
                parent=parent["path"],
                parent_sha256=parent["sha256"],
                symbol=symbol,
                day=day,
                daily_source=supplement,
                recovered_minutes=len(recovered),
                remaining_minutes=[iso(value) for value in remaining],
            )
            if remaining:
                params = dict(
                    symbol=symbol,
                    interval="1m",
                    startTime=remaining[0] // 1_000_000 - 60_000,
                    endTime=remaining[-1] // 1_000_000 + 119_999,
                    limit=1500,
                )
                response = client.get(
                    "https://fapi.binance.com/fapi/v1/markPriceKlines", params=params
                )
                response.raise_for_status()
                api_rows = response.json()
                found = {int(row[0]) * 1_000_000 for row in api_rows}
                item["api_probe"] = dict(
                    source_url=str(response.url),
                    status_code=response.status_code,
                    params=params,
                    response=api_rows,
                    recovered_minutes=[iso(value) for value in remaining if value in found],
                )
                audit["unresolved_minutes"].extend(
                    dict(symbol=symbol, open_time=iso(value), present_in_api=value in found)
                    for value in remaining
                )
            audit["entries"].append(item)
            print(
                f"{symbol} {day}: recuperados {len(recovered)}; "
                f"pendientes {len(remaining)} minutos de mark.",
                flush=True,
            )
    audit["source_manifest_sha256_after"] = _sha256(path)
    audit["status"] = "unresolved_gaps" if audit["unresolved_minutes"] else "complete"
    audit_path = (
        data_root
        / "manifests"
        / ("source_repair_" + datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ") + ".json")
    )
    _write_raw_bytes(
        audit_path,
        (json.dumps(audit, indent=2, sort_keys=True) + "\n").encode(),
        budget_root,
        config.data_budget_bytes,
    )
    print(f"Evidencia: {audit_path}", flush=True)
    return audit


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("D:/Backtesting"))
    parser.add_argument(
        "--config", type=Path, default=REPO / "configs/download_minutes_2022_2026_d.toml"
    )
    args = parser.parse_args()
    audit = investigate(args.root.resolve(), Config.load(args.config))
    return 0 if audit["status"] == "complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())
