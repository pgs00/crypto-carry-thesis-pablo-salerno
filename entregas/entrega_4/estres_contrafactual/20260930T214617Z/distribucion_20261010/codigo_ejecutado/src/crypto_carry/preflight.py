"""Fast, read-only preparation checks; never certify historical data or economics."""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from .config import HOUR, Config, iso, timestamp
from .data.download import _archive_descriptors
from .data.prescribed import prescribed_rules
from .data.rules import RuleBook


def _local(root: Path, relative: str) -> Path:
    value = Path(relative)
    path = (root / value).resolve()
    if value.is_absolute() or ".." in value.parts or root not in path.parents:
        raise ValueError(f"Path outside data root: {relative}")
    return path


def _download_check(config: Config, root: Path) -> dict:
    start, end = timestamp(config.history_start), timestamp(config.end)
    funding_start = start - (config.window_hours + 48) * HOUR
    minute_model = config.execution_model in ("minute_open", "next_minute_vwap")
    if minute_model:
        from .data.minute_download import _bounds, minute_descriptors

        start, end, funding_start = _bounds(config)
        expected = {
            item["path"]: item["dataset"] != "funding" for item in minute_descriptors(config)
        }
    else:
        expected = {
            f"{config.data_dir}/{item['relative']}": True
            for item in _archive_descriptors(
                config,
                datetime.fromtimestamp(start / 1_000_000_000, UTC),
                datetime.fromtimestamp(end / 1_000_000_000, UTC),
                datetime.fromtimestamp(funding_start / 1_000_000_000, UTC),
            )
        }
        for symbol in config.symbols:
            expected[
                f"{config.data_dir}/raw/futures/funding_api/{symbol}/"
                f"funding-{funding_start // 1_000_000}-{(end - 1) // 1_000_000}.json"
            ] = False
    result = {"ready": False, "expected_files": len(expected), "issues": []}
    issues = result["issues"]
    try:
        manifest_path = _local(root, f"{config.data_dir}/manifests/download.json")
        if not manifest_path.is_file():
            issues.append("Missing final download manifest; download may still be running")
            result["issue_count"] = 1
            return result
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or not isinstance(payload.get("entries"), list):
            raise ValueError("Invalid download manifest")
        if (
            (not minute_model and payload.get("scope") != "full")
            or (minute_model and payload.get("kind") != "minute_market_data")
            or payload.get("requested_start") != start
            or payload.get("requested_end") != end
            or payload.get("funding_request_start") != funding_start
        ):
            issues.append("Download manifest does not match configured full download range")
        entries = payload["entries"]
        paths = [entry["path"] for entry in entries]
        if len(set(paths)) != len(paths):
            issues.append("Duplicate paths in download manifest")
        by_path = {entry["path"]: entry for entry in entries}
        result["recorded_files"] = len(entries)
        result["statuses"] = dict(Counter(entry.get("status", "unknown") for entry in entries))
        for relative, needs_checksum in expected.items():
            entry = by_path.get(relative)
            if entry is None:
                issues.append(f"Missing planned entry: {relative}")
                continue
            if entry.get("status") not in {"downloaded", "cached"} or entry.get("errors"):
                issues.append(f"Download not successful: {relative}")
                continue
            path = _local(root, relative)
            if not path.is_file() or path.stat().st_size != entry.get("bytes"):
                issues.append(f"Missing file or changed size: {relative}")
            if not re.fullmatch(r"[0-9a-fA-F]{64}", str(entry.get("sha256", ""))):
                issues.append(f"Missing recorded SHA-256: {relative}")
            if needs_checksum:
                checksum = entry.get("checksum_path", "")
                checksum_path = _local(root, checksum) if checksum else None
                if (
                    checksum_path != _local(root, relative + ".CHECKSUM")
                    or not checksum_path.is_file()
                ):
                    issues.append(f"Missing checksum file: {relative}")
                if not re.fullmatch(r"[0-9a-fA-F]{64}", str(entry.get("checksum_file_sha256", ""))):
                    issues.append(f"Missing checksum identity: {relative}")
        result["ready"] = not issues
    except (OSError, ValueError, TypeError, KeyError) as exc:
        issues.append(f"Invalid download preparation: {exc}")
    # Keep terminal output bounded even if thousands of planned files are absent.
    result["issue_count"] = len(issues)
    result["issues"] = issues[:20]
    return result


def _rules_check(config: Config, root: Path) -> dict:
    result = {"ready": False, "issues": [], "analysis_mode": config.analysis_mode}
    try:
        path = _local(root, config.rules_file)
        research = config.analysis_mode == "prescribed_research"
        if not research and not path.is_file():
            result["issues"].append(f"Missing historical rules: {config.rules_file}")
            return result
        rulebook = prescribed_rules(config) if research else RuleBook.load(path)
        start, end = timestamp(config.start), timestamp(config.end)
        boundaries = sorted({start, end - 1, *rulebook.transition_times(start, end - 1)})
        result["records"] = len(rulebook.records)
        for symbol in config.symbols:
            for market in ("spot", "futures"):
                missing = next(
                    (t for t in boundaries if rulebook.get(symbol, market, t) is None), None
                )
                if missing is not None:
                    result["issues"].append(
                        f"Rule coverage gap: {symbol}/{market} at {iso(missing)}"
                    )
        result["ready"] = not result["issues"]
    except (OSError, ValueError, TypeError, KeyError, AttributeError, ArithmeticError) as exc:
        result["issues"].append(f"Invalid historical rules: {exc}")
    return result


def preflight(config: Config, root: Path) -> dict:
    """Inspect full-download metadata and rule coverage without reading large data.

    A successful result permits starting validation, not backtesting. Raw hashes,
    schemas, row coverage and economic validity are deliberately not certified.
    No file is written and no engine, normalization or download is started.
    """
    root = Path(root).resolve()
    download = _download_check(config, root)
    rules = _rules_check(config, root)
    return {
        "status": "ready_for_validation" if download["ready"] and rules["ready"] else "blocked",
        "root": str(root),
        "config_hash": config.digest(),
        "historical_certified": False,
        "integrity_verified": False,
        "download": download,
        "rules": rules,
        "next_step": "validate-data --scope full; actual integrity and coverage checks are still required",
        "limitation": "Metadata-only snapshot. Same-size corruption and concurrent changes are not detected.",
    }
