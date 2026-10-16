"""Check that cached coverage still applies before an expensive replay."""

import hashlib
import json

from ..config import HOUR, timestamp
from .replay import _select_partitions


def _required_keys(config):
    datasets = ({"minute_bars"} if config.execution_model == "next_minute_vwap" else
                {"minute_prices", "minute_volumes"} if config.execution_model == "minute_open"
                else {"trades"})
    if config.signal_price_model == "closed_minute":
        datasets.add("minute_bars")
    for symbol in config.symbols:
        for dataset in sorted(datasets):
            for market in ("spot", "futures"):
                yield dataset, symbol, market
        yield "marks", symbol, "futures"
        yield "funding", symbol, "futures"


def verify_prepared_inputs(root, config, quality, inputs):
    """Reuse full validation only for covered streams and unchanged partitions.

    This checks the preparation contract, not market-source authenticity; the
    pinned source check and the historical validator remain separate steps.
    """
    start, end = timestamp(config.start), timestamp(config.end)
    warmup = start - (config.window_hours + 24) * HOUR
    recorded_warmup = quality.get("funding_warmup_start")
    if quality.get("scope") != "full":
        raise ValueError("Prepared coverage must use scope=full")
    if not isinstance(recorded_warmup, int) or recorded_warmup > warmup:
        raise ValueError("Prepared coverage has insufficient funding warmup")
    manifest_bytes = (root / config.data_dir / "manifests/processed.json").read_bytes()
    if quality.get("processed_manifest_sha256") != hashlib.sha256(manifest_bytes).hexdigest():
        raise ValueError("Prepared coverage is not bound to this manifest; repeat validation")
    manifest = json.loads(manifest_bytes)
    entries = manifest.get("entries", [])
    if not entries or manifest.get("errors"):
        raise ValueError("Prepared coverage requires an error-free, nonempty manifest")
    minute_model = (config.execution_model in {"minute_open", "next_minute_vwap"}
                    or config.signal_price_model == "closed_minute")
    if (manifest.get("kind") == "minute_market_data") != minute_model:
        raise ValueError("Prepared coverage dataset kind differs from the configuration")
    grouped, by_path = {}, {}
    for entry in entries:
        path = entry["path"]
        if path in by_path:
            raise ValueError(f"Duplicate prepared partition: {path}")
        by_path[path] = entry
        key = (entry["dataset"], entry["symbol"], entry["market"])
        grouped.setdefault(key, []).append(entry)
        # input_hashes already reads these files; compare instead of hashing twice.
        if not entry.get("sha256") or inputs.get(path) != entry["sha256"]:
            raise ValueError(f"Prepared input hash mismatch or missing file: {path}")
    coverage = {(row["dataset"], row["symbol"], row["market"]): row
                for row in quality.get("coverage", [])}
    for key in _required_keys(config):
        lower = warmup if key[0] == "funding" else start
        row = coverage.get(key, {})
        if (row.get("status") != "complete" or row.get("expected_start", lower + 1) > lower
                or row.get("expected_end", end - 1) < end):
            raise ValueError(f"Prepared coverage is missing or insufficient for {key}")
        selected = _select_partitions(grouped.get(key, []), lower, end)
        checks = set(row.get("checks", []))
        checked_paths = {check.removeprefix("sha256:") for check in checks
                         if check.startswith("sha256:")}
        if not selected or not checked_paths.issubset(by_path):
            raise ValueError(f"Prepared coverage references missing partitions for {key}")
        for entry in selected:
            path = entry["path"]
            if (f"sha256:{path}" not in checks or f"schema:{path}" not in checks
                    or not entry.get("complete") or entry.get("conflict_count", 0)):
                raise ValueError(f"Prepared coverage does not validate partition: {path}")
