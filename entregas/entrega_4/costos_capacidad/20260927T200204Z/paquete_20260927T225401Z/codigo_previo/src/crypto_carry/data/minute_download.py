"""Download the approved minute study without changing the execution engine.

Run as a separate module. Config paths are relative to the current shell directory;
raw paths are relative to --root. Download integrity is not economic data validation.
"""

from __future__ import annotations

import argparse
import json
import sys
import zipfile
from collections import Counter
from contextlib import nullcontext
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Callable

import httpx

from ..config import HOUR, Config, iso, timestamp
from .download import (
    FUNDING_API,
    VISION,
    DataBudgetExceeded,
    _checksum_value,
    _data_bytes,
    _ensure_budget,
    _months,
    _response_bytes,
    _sha256,
    _write_json_raw,
    _write_raw_bytes,
    download_verified_archive,
    fetch_funding_pages,
)


def _bounds(config: Config) -> tuple[int, int, int]:
    start, end = timestamp(config.start), timestamp(config.end)
    # Include the 28-day robustness lookback plus two antecedent days.
    return start, end, start - (max(672, config.window_hours) + 48) * HOUR


def minute_descriptors(config: Config) -> list[dict]:
    """Monthly OHLCV, closed marks, funding calendars and public API snapshots."""
    _, end_ns, request_ns = _bounds(config)
    first = datetime.fromtimestamp(request_ns // 1_000_000_000, UTC)
    end = datetime.fromtimestamp(end_ns // 1_000_000_000, UTC)
    jobs = []
    for month in _months(first, end):
        month_start = datetime.fromisoformat(month + "-01T00:00:00+00:00")
        next_month = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)
        for symbol in config.symbols:
            for dataset, market, folder in (
                ("klines", "spot", "klines"),
                ("klines", "futures", "klines"),
                ("marks", "futures", "markPriceKlines"),
                ("funding_calendar", "futures", "fundingRate"),
            ):
                is_kline = dataset != "funding_calendar"
                name = f"{symbol}-{'1m' if is_kline else 'fundingRate'}-{month}.zip"
                prefix = "spot" if market == "spot" else "futures/um"
                interval_path = "1m/" if is_kline else ""
                jobs.append(
                    dict(
                        dataset=dataset,
                        symbol=symbol,
                        market=market,
                        source_url=f"{VISION}/{prefix}/monthly/{folder}/{symbol}/{interval_path}{name}",
                        path=f"{config.data_dir}/raw/{market}/{folder}/{symbol}/{name}",
                        start=month_start.isoformat().replace("+00:00", "Z"),
                        end=iso(timestamp(next_month.isoformat()) - 1),
                        timestamp_unit="us" if market == "spot" and month >= "2025-01" else "ms",
                    )
                )
    for symbol in config.symbols:
        jobs.append(
            dict(
                dataset="funding",
                symbol=symbol,
                market="futures",
                source_url=FUNDING_API,
                path=(
                    f"{config.data_dir}/raw/futures/funding_api/{symbol}/"
                    f"funding-{request_ns // 1_000_000}-{(end_ns - 1) // 1_000_000}.json"
                ),
                start=request_ns,
                end=end_ns - 1,
                timestamp_unit="ms",
            )
        )
    return jobs


def _paths(config: Config, root: Path) -> tuple[Path, Path]:
    budget_root = (root / "data/minutes").resolve()
    data_root = (root / config.data_dir).resolve()
    if root not in budget_root.parents or data_root.parent != budget_root:
        raise ValueError("Minute data_dir must be a direct child of data/minutes under --root")
    return data_root, budget_root


def _save_manifest(path: Path, manifest: dict, budget_root: Path, budget: int) -> None:
    manifest["bytes_used"] = _data_bytes(path.parent.parent)
    manifest["aggregate_bytes_used"] = _data_bytes(budget_root)
    encoded = json.dumps(manifest, indent=2, sort_keys=True).encode()
    _ensure_budget(budget_root, budget, len(encoded))
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.part")
    temporary.write_bytes(encoded)
    temporary.replace(path)


def download_minutes(
    config: Config,
    root: Path,
    *,
    client: httpx.Client | None = None,
    progress: Callable[[dict], None] | None = None,
) -> dict:
    """Verify/reuse complete files and persist progress after every attempted item."""
    root = Path(root).resolve()
    data_root, budget_root = _paths(config, root)
    _ensure_budget(budget_root, config.data_budget_bytes)
    jobs = minute_descriptors(config)
    start, end, request_start = _bounds(config)
    path = data_root / "manifests/download.json"
    previous = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    if previous and (
        previous.get("kind") != "minute_market_data"
        or previous.get("requested_start") != start
        or previous.get("requested_end") != end
        or previous.get("funding_request_start") != request_start
    ):
        raise ValueError(
            "Existing minute manifest describes a different request; use a new data_dir"
        )
    cached = {entry["path"]: entry for entry in previous.get("entries", [])}
    # Keep provenance for jobs not revisited yet, including immutable API snapshots.
    # A second interruption must not erase a previously completed download's metadata.
    current = {job["path"]: cached[job["path"]] for job in jobs if job["path"] in cached}
    manifest = dict(
        version=1,
        kind="minute_market_data",
        scope="full",
        status="in_progress",
        requested_start=start,
        requested_end=end,
        funding_request_start=request_start,
        funding_warmup_start=request_start + 24 * HOUR,
        interval="1m",
        coverage_certified=False,
        budget_bytes=config.data_budget_bytes,
        budget_root="data/minutes",
        retrieved_at=datetime.now(UTC).isoformat(),
        total_items=len(jobs),
        entries=list(current.values()),
    )
    _save_manifest(path, manifest, budget_root, config.data_budget_bytes)
    context = (
        nullcontext(client)
        if client is not None
        else httpx.Client(
            timeout=httpx.Timeout(60, connect=20),
            follow_redirects=True,
            headers={"User-Agent": "crypto-carry-research/0.1"},
        )
    )
    verified = 0
    with context as connection:
        for attempted, job in enumerate(jobs, start=1):
            entry = dict(
                job, status="failed", errors=[], retrieved_at=datetime.now(UTC).isoformat()
            )
            # Daily source repairs remain attached when the primary monthly
            # archives are verified again. Normalization verifies these inputs.
            if "supplements" in cached.get(job["path"], {}):
                entry["supplements"] = cached[job["path"]]["supplements"]
            destination = (root / entry["path"]).resolve()
            if data_root not in destination.parents:
                raise ValueError("Raw destination escapes minute data directory")
            try:
                if job["dataset"] == "funding":
                    prior = cached.get(entry["path"], {})
                    if destination.exists() and prior.get("status") in {"downloaded", "cached"}:
                        if _sha256(destination) != prior["sha256"]:
                            raise ValueError(f"Cached funding checksum mismatch: {destination}")
                        entry.update(
                            status="cached",
                            sha256=prior["sha256"],
                            bytes=destination.stat().st_size,
                            rows=prior["rows"],
                            retrieved_at=prior["retrieved_at"],
                        )
                    else:
                        rows = fetch_funding_pages(
                            connection,
                            job["symbol"],
                            job["start"] // 1_000_000,
                            job["end"] // 1_000_000,
                        )
                        if not rows:
                            raise ValueError("Funding API returned no observations")
                        entry.update(
                            _write_json_raw(
                                destination, rows, budget_root, config.data_budget_bytes
                            ),
                            rows=len(rows),
                        )
                else:
                    checksum_url = job["source_url"] + ".CHECKSUM"
                    content = _response_bytes(connection, checksum_url)
                    expected = _checksum_value(content, checksum_url)
                    checksum_path = destination.with_suffix(".zip.CHECKSUM")
                    checksum = _write_raw_bytes(
                        checksum_path, content, budget_root, config.data_budget_bytes
                    )
                    outcome = download_verified_archive(
                        connection,
                        job["source_url"],
                        destination,
                        expected_sha256=expected,
                        budget_limit=config.data_budget_bytes,
                        data_root=budget_root,
                    )
                    entry.update(
                        outcome,
                        checksum_url=checksum_url,
                        checksum_path=checksum_path.relative_to(root).as_posix(),
                        checksum_file_sha256=checksum["sha256"],
                    )
            except DataBudgetExceeded:
                raise
            except (httpx.HTTPError, OSError, TypeError, ValueError, zipfile.BadZipFile) as exc:
                entry["errors"].append(f"{type(exc).__name__}: {exc}")
            current[entry["path"]] = entry
            manifest["entries"] = [current[job["path"]] for job in jobs if job["path"] in current]
            verified += entry["status"] in {"downloaded", "cached"}
            _save_manifest(path, manifest, budget_root, config.data_budget_bytes)
            if progress:
                progress(
                    dict(
                        verified=verified,
                        attempted=attempted,
                        total=len(jobs),
                        percent=100 * verified / len(jobs),
                        entry=entry,
                    )
                )
    manifest["status"] = "download_complete" if verified == len(jobs) else "incomplete"
    _save_manifest(path, manifest, budget_root, config.data_budget_bytes)
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Descarga publica por minuto; no ejecuta backtests"
    )
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument(
        "--config",
        type=Path,
        nargs="+",
        required=True,
        help="TOML paths relative to the current shell directory",
    )
    parser.add_argument(
        "--plan-only", action="store_true", help="Show file list without downloading"
    )
    args = parser.parse_args(argv)
    try:
        configs = [Config.load(path) for path in args.config]
        root = args.root.resolve()
        destinations = [_paths(config, root)[0] for config in configs]
        if len(set(destinations)) != len(destinations):
            raise ValueError("Configurations must use distinct data directories")
        if len({config.data_budget_bytes for config in configs}) != 1:
            raise ValueError("Configurations must share the same aggregate data budget")
        jobs = [job for config in configs for job in minute_descriptors(config)]
        total = len(jobs)
        if args.plan_only:
            print(
                json.dumps(
                    dict(
                        total_items=total,
                        zip_archives=sum(j["dataset"] != "funding" for j in jobs),
                        root=str(root),
                        budget_bytes=configs[0].data_budget_bytes,
                        entries=jobs,
                    ),
                    indent=2,
                )
            )
            return 0
        print(
            f"DESCARGA POR MINUTO: {total} archivos/respuestas. Porcentaje de archivos verificados.",
            flush=True,
        )
        completed, attempts = 0, 0
        for config in configs:
            print(
                f"Ventana {config.start[:10]} a {config.end[:10]} (fin excluido). "
                f"Destino: {root / config.data_dir}",
                flush=True,
            )

            def show(update):
                entry = update["entry"]
                count = completed + update["verified"]
                processed = attempts + update["attempted"]
                print(
                    f"[{count}/{total}] {100 * count / total:6.2f}% verificado | "
                    f"revisados {processed}/{total} | {entry['status']} | "
                    f"{entry['market']}/{entry['symbol']}/{Path(entry['path']).name}",
                    flush=True,
                )
                if entry["errors"]:
                    print("  ERROR: " + "; ".join(entry["errors"]), flush=True)

            result = download_minutes(config, root, progress=show)
            counts = Counter(entry["status"] for entry in result["entries"])
            completed += counts["downloaded"] + counts["cached"]
            attempts += len(result["entries"])
        if completed == total:
            print(
                f"DESCARGA COMPLETA: {completed}/{total} (100%). "
                "Integridad verificada; cobertura y normalizacion pendientes.",
                flush=True,
            )
            return 0
        print(
            f"DESCARGA INCOMPLETA: {total - completed} pendientes. "
            "Repetir el mismo comando para reintentar.",
            flush=True,
        )
        return 1
    except KeyboardInterrupt:
        print("\nDESCARGA INTERRUMPIDA. Repetir el mismo comando para reanudar.", flush=True)
        return 130
    except (OSError, ValueError, DataBudgetExceeded) as exc:
        print(f"ERROR: {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
