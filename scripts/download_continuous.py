"""Download continuous minute history, reusing verified annual ZIPs on the same disk.

This launcher only acquires raw data. It neither normalizes it nor runs a backtest.
Original annual archives, API snapshots and repair manifests remain untouched.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from crypto_carry.config import HOUR, Config
from crypto_carry.data.download import (
    DataBudgetExceeded,
    _checksum_value,
    _ensure_budget,
    _write_raw_bytes,
)
from crypto_carry.data.minute_download import (
    _bounds,
    _paths,
    _save_manifest,
    download_minutes,
    minute_descriptors,
)

DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / "configs/download_minutes_2022_2026_d.toml"
SOURCE_FOLDERS = ("2022_2023", "2025_2026")


def cache_candidates(config: Config, root: Path) -> dict:
    """Match whole monthly archives by source URL, never by filename alone."""
    jobs = {job["source_url"] for job in minute_descriptors(config) if job["dataset"] != "funding"}
    _, budget_root = _paths(config, root)
    candidates = {}
    for name in SOURCE_FOLDERS:
        source_root = (budget_root / name).resolve()
        if source_root.parent != budget_root:
            raise ValueError("Source directory escapes data/minutes")
        path = source_root / "manifests/download.json"
        if not path.exists():
            continue
        manifest = json.loads(path.read_text(encoding="utf-8"))
        if manifest.get("kind") != "minute_market_data":
            raise ValueError(f"Unrecognized minute source manifest: {path}")
        for entry in manifest["entries"]:
            if entry.get("source_url") in jobs and entry.get("status") in {"downloaded", "cached"}:
                source = (root / entry["path"]).resolve()
                if source_root not in source.parents:
                    raise ValueError("Source archive escapes its data directory")
                if source.is_file():
                    candidates.setdefault(entry["source_url"], (source_root, entry))
    return candidates


def _manifest(config: Config, root: Path) -> tuple[Path, dict]:
    data_root, _ = _paths(config, root)
    path = data_root / "manifests/download.json"
    start, end, request_start = _bounds(config)
    if path.exists():
        previous = json.loads(path.read_text(encoding="utf-8"))
        if (
            previous.get("kind") != "minute_market_data"
            or previous.get("requested_start") != start
            or previous.get("requested_end") != end
            or previous.get("funding_request_start") != request_start
        ):
            raise ValueError("Existing minute manifest describes a different request")
        return path, previous
    return path, dict(
        version=1,
        kind="minute_market_data",
        scope="full",
        status="cache_prepared",
        requested_start=start,
        requested_end=end,
        funding_request_start=request_start,
        funding_warmup_start=request_start + 24 * HOUR,
        interval="1m",
        coverage_certified=False,
        budget_bytes=config.data_budget_bytes,
        budget_root="data/minutes",
        retrieved_at=datetime.now(UTC).isoformat(),
        total_items=len(minute_descriptors(config)),
        entries=[],
    )


def _copy_archive(entry: dict, source_root: Path, config: Config, root: Path) -> dict:
    data_root, budget_root = _paths(config, root)
    source = (root / entry["path"]).resolve()
    checksum_source = (root / entry["checksum_path"]).resolve()
    if source_root not in source.parents or source_root not in checksum_source.parents:
        raise ValueError("Source archive or checksum escapes its data directory")
    content, checksum = source.read_bytes(), checksum_source.read_bytes()
    if (
        hashlib.sha256(content).hexdigest() != entry["sha256"]
        or hashlib.sha256(checksum).hexdigest() != entry["checksum_file_sha256"]
        or _checksum_value(checksum, str(checksum_source)) != entry["sha256"]
    ):
        raise ValueError(f"SHA-256 mismatch in original cache: {source}")
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        if archive.testzip() is not None:
            raise ValueError(f"CRC mismatch in original cache: {source}")
    destination = (data_root / source.relative_to(source_root)).resolve()
    checksum_path = destination.with_suffix(".zip.CHECKSUM")
    if data_root not in destination.parents or data_root not in checksum_path.resolve().parents:
        raise ValueError("Cache destination escapes its data directory")
    # Independent copies keep the original evidence immutable if the new study changes.
    _write_raw_bytes(checksum_path, checksum, budget_root, config.data_budget_bytes)
    _write_raw_bytes(destination, content, budget_root, config.data_budget_bytes)
    copied = dict(
        entry,
        path=destination.relative_to(root).as_posix(),
        checksum_path=checksum_path.relative_to(root).as_posix(),
        status="cached",
        errors=[],
    )
    if "supplements" in entry:
        copied["supplements"] = [
            _copy_archive(item, source_root, config, root) for item in entry["supplements"]
        ]
    return copied


def prepare_cache(config: Config, root: Path) -> int:
    """Copy checked sources and daily repairs; preserve an interrupted destination manifest."""
    root = root.resolve()
    _, budget_root = _paths(config, root)
    path, manifest = _manifest(config, root)
    candidates = cache_candidates(config, root)
    _ensure_budget(budget_root, config.data_budget_bytes)
    entries = {entry["path"]: entry for entry in manifest["entries"]}
    jobs = minute_descriptors(config)
    pending = [
        job for job in jobs if job["path"] not in entries and job["source_url"] in candidates
    ]
    for count, job in enumerate(pending, 1):
        source_root, entry = candidates[job["source_url"]]
        copied = _copy_archive(entry, source_root, config, root)
        if copied["path"] != job["path"]:
            raise ValueError("Cached archive does not match its planned destination")
        entries[job["path"]] = dict(copied, **job)
        manifest["entries"] = list(entries.values())
        _save_manifest(path, manifest, budget_root, config.data_budget_bytes)
        print(
            f"CACHE LOCAL [{count}/{len(pending)}] verificado y copiado | "
            f"{job['market']}/{job['symbol']}/{Path(job['path']).name}",
            flush=True,
        )
    return len(pending)


def show_progress(update: dict) -> None:
    verified, total = update["verified"], update["total"]
    entry = update["entry"]
    print(
        f"[{verified}/{total}] {100 * verified / total:6.2f}% verificado | "
        f"faltan {total - verified} | {entry['status']} | "
        f"{entry['market']}/{entry['symbol']}/{Path(entry['path']).name}",
        flush=True,
    )
    if entry["errors"]:
        print("  ERROR: " + "; ".join(entry["errors"]), flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Descarga continua por minuto con contador")
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--plan-only", action="store_true", help="No escribe ni usa la red")
    args = parser.parse_args(argv)
    try:
        config, root = Config.load(args.config), args.root.resolve()
        _manifest(config, root)  # Validate the destination before writing anything.
        jobs = minute_descriptors(config)
        archives = [job for job in jobs if job["dataset"] != "funding"]
        candidates = cache_candidates(config, root)
        local = sum(
            job["source_url"] in candidates or (root / job["path"]).is_file() for job in archives
        )
        print(
            f"PERIODO: {config.start[:10]} a {config.end[:10]} (fin excluido), "
            "mas calentamiento previo.\n"
            f"PLAN: {len(archives)} ZIP + {len(jobs) - len(archives)} consultas de funding.\n"
            f"ZIP locales para verificar/reutilizar: {local}; sin copia local: "
            f"{len(archives) - local}.\n"
            f"DESTINO: {root / config.data_dir}\n"
            f"Limite compartido: {config.data_budget_bytes / 1e9:g} GB.\n"
            "El porcentaje cuenta archivos/respuestas verificados, no bytes ni tiempo.",
            flush=True,
        )
        if args.plan_only:
            return 0
        prepare_cache(config, root)
        print("DESCARGANDO / VERIFICANDO. cached = reutilizado, sin bajar el ZIP.", flush=True)
        result = download_minutes(config, root, progress=show_progress)
        verified = sum(entry["status"] in {"downloaded", "cached"} for entry in result["entries"])
        if result["status"] == "download_complete":
            print(
                f"DESCARGA COMPLETA: {verified}/{len(jobs)} (100%). "
                "Integridad verificada; cobertura y normalizacion pendientes.",
                flush=True,
            )
            return 0
        print(
            f"DESCARGA INCOMPLETA: faltan {len(jobs) - verified}. "
            "Repetir el mismo comando para reintentar.",
            flush=True,
        )
        return 1
    except KeyboardInterrupt:
        print("\nDESCARGA INTERRUMPIDA. Repetir el mismo comando para reanudar.", flush=True)
        return 130
    except (OSError, ValueError, KeyError, zipfile.BadZipFile, DataBudgetExceeded) as exc:
        print(f"ERROR: {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
