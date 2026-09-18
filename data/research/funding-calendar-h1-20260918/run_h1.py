"""Independent observed-rate H1 audit; does not mutate the backtest pipeline."""

from __future__ import annotations

import bisect
import concurrent.futures
import csv
import gzip
import hashlib
import io
import json
import sys
import threading
import time
import urllib.request
import zipfile
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))
from crypto_carry.config import Config, HOUR, SECOND, iso, timestamp
from crypto_carry.data.normalize import _funding_calendar_times, funding_records
from crypto_carry.evaluation import forecast_evaluation, h1_summary
from crypto_carry.forecast import forecast

HERE = Path(__file__).resolve().parent
BUDGET = 2_000_000
LOCK = threading.Lock()
TRANSFER = 0


def digest(data):
    return hashlib.sha256(data).hexdigest()


def save_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def fetch(url):
    global TRANSFER
    for attempt in range(3):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "academic-funding-audit/1.0"})
            with urllib.request.urlopen(request, timeout=25) as response:
                data = response.read(100_001)
                if len(data) > 100_000:
                    raise ValueError("Unexpectedly large funding calendar response")
                with LOCK:
                    TRANSFER += len(data)
                    if TRANSFER > BUDGET:
                        raise ValueError("Funding calendar transfer budget exceeded")
                return data
        except Exception:
            if attempt == 2:
                raise
            time.sleep(0.25 * (attempt + 1))


def download(item):
    symbol, month = item
    name = f"{symbol}-fundingRate-{month}.zip"
    url = f"https://data.binance.vision/data/futures/um/monthly/fundingRate/{symbol}/{name}"
    target = HERE / name
    candidates = [target, ROOT / "data/raw/futures/fundingRate" / symbol / name]
    for candidate in candidates:
        checksum_path = candidate.with_name(candidate.name + ".CHECKSUM")
        if candidate.exists() and checksum_path.exists():
            content, checksum = candidate.read_bytes(), checksum_path.read_bytes()
            if digest(content) == checksum.decode().split()[0]:
                break
    else:
        checksum = fetch(url + ".CHECKSUM")
        content = fetch(url)
        if digest(content) != checksum.decode().split()[0]:
            raise ValueError(f"Checksum mismatch: {name}")
        candidate = target
        target.write_bytes(content)
        target.with_name(target.name + ".CHECKSUM").write_bytes(checksum)
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        if archive.testzip() is not None:
            raise ValueError(f"CRC mismatch: {name}")
    return {
        "symbol": symbol, "month": month, "source_url": url,
        "checksum_url": url + ".CHECKSUM", "path": candidate.relative_to(ROOT).as_posix(),
        "sha256": digest(content), "bytes": len(content), "checksum_sha256": digest(checksum),
        "checksum_path": checksum_path.relative_to(ROOT).as_posix() if candidate != target else (target.with_name(name + ".CHECKSUM")).relative_to(ROOT).as_posix(),
        "retrieved_or_verified_at": datetime.now(timezone.utc).isoformat(),
    }


def main():
    began = time.monotonic()
    config = Config.load(ROOT / "configs/base.toml")
    months = [f"{year}-{month:02}" for year in range(2021, 2027) for month in range(1, 13)
              if "2021-12" <= f"{year}-{month:02}" <= "2026-08"]
    jobs = [(symbol, month) for symbol in config.symbols for month in months]
    entries, errors = [], []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(download, item): item for item in jobs}
        for future in concurrent.futures.as_completed(futures):
            try:
                entries.append(future.result())
            except Exception as exc:
                errors.append({"item": futures[future], "error": repr(exc)})
            if (len(entries) + len(errors)) % 20 == 0:
                print(f"calendars {len(entries)}/{len(jobs)}, errors {len(errors)}", flush=True)
    manifest = {"created_at": datetime.now(timezone.utc).isoformat(), "entries": sorted(entries, key=lambda x: (x["symbol"], x["month"])), "errors": errors, "network_bytes": TRANSFER}
    save_json(HERE / "manifest.json", manifest)
    if errors:
        raise RuntimeError(f"Calendar download failed; see {HERE / 'manifest.json'}")

    api_manifest = json.loads((ROOT / "docs/research/funding_api_coverage.json").read_text(encoding="utf-8"))
    raw = {symbol: [] for symbol in config.symbols}
    api_sources = []
    for page in api_manifest["pages"]:
        path = ROOT / page["path"]
        content = path.read_bytes()
        if digest(content) != page["sha256"]:
            raise ValueError(f"API raw hash mismatch: {path}")
        for row in json.loads(content):
            raw[row["symbol"]].append(row)
        api_sources.append(page)

    funding, signals, coverage = [], [], {}
    lower_ms = timestamp("2021-12-01T00:00:00Z") // 1_000_000
    upper_ms = timestamp(config.end) // 1_000_000
    start = timestamp(config.start)
    for symbol in config.symbols:
        calendar = {}
        duplicate_calendar = 0
        for entry in entries:
            if entry["symbol"] != symbol:
                continue
            for key, item in _funding_calendar_times(ROOT / entry["path"]).items():
                if key in calendar:
                    if calendar[key] != item:
                        raise ValueError(f"Calendar conflict: {symbol}/{key}")
                    duplicate_calendar += 1
                calendar[key] = item
        rows = sorted((row for row in raw[symbol] if lower_ms <= int(row["fundingTime"]) < upper_ms), key=lambda row: int(row["fundingTime"]))
        keys = {int(row["fundingTime"]) for row in rows}
        missing_api = sorted(set(calendar) - keys)
        missing_calendar = sorted(keys - set(calendar))
        conflicts = [key for key in keys & set(calendar)
                     if any(Decimal(row["fundingRate"]) != calendar[key][1] for row in rows if int(row["fundingTime"]) == key)]
        if missing_api or missing_calendar or conflicts:
            coverage[symbol] = {"missing_api": missing_api, "missing_calendar": missing_calendar, "rate_conflicts": conflicts}
            save_json(HERE / "coverage_failure.json", coverage)
            raise ValueError(f"Source comparison failed for {symbol}")
        records = funding_records(rows, symbol=symbol, source_file="funding_api_coverage.json:verified_pages", expected_times_ms=set(calendar), expected_intervals={k: v[0] for k, v in calendar.items()}, expected_rates={k: v[1] for k, v in calendar.items()})
        funding.extend(records)
        times = [r.funding_time for r in records]
        unverified = [iso(r.funding_time) for r in records if not r.interval_verified]
        coverage[symbol] = {
            "raw_api_rows_all": len(raw[symbol]), "api_rows_in_calendar_window": len(rows),
            "calendar_events": len(calendar), "api_duplicate_timestamps": len(rows) - len(keys),
            "identical_calendar_duplicates": duplicate_calendar, "missing_api": missing_api,
            "missing_calendar": missing_calendar, "rate_conflicts": conflicts,
            "unverified_intervals": unverified, "first_event": iso(times[0]), "last_event": iso(times[-1]),
            "economic_events": sum(start <= r.funding_time < timestamp(config.end) for r in records),
            "economic_missing_settlement_mark": sum(start <= r.funding_time < timestamp(config.end) and r.settlement_mark_price is None for r in records),
        }
        for i, record in enumerate(records):
            decision_time = record.funding_time + config.signal_delay_seconds * SECOND
            if not start <= decision_time < timestamp(config.end):
                continue
            first = bisect.bisect_right(times, record.funding_time - config.window_hours * HOUR)
            window = records[max(0, first - 1): i + 1]
            prediction = forecast(window, record.funding_time, decision_time, config)
            signals.append({"symbol": symbol, "time_ns": decision_time, "anchor": prediction.anchor,
                            "history_start": prediction.history_start, "forecast": str(prediction.value),
                            "no_change": str(prediction.no_change), "valid": prediction.valid,
                            "reason": prediction.reason, "available_at": prediction.available_at})
        print(f"{symbol}: verified calendar {len(calendar)}, signals {len(signals)} cumulative", flush=True)
    frame = forecast_evaluation(signals, funding, config)
    summary_frame = h1_summary(frame, config)
    summary_rows = json.loads(summary_frame.to_json(orient="records", double_precision=15))
    for row in summary_rows:
        row["mae_ewma_bps"] = row["mae_ewma"] * 10_000 if row["mae_ewma"] is not None else None
        row["mae_no_change_bps"] = row["mae_no_change"] * 10_000 if row["mae_no_change"] is not None else None
        row["relative_mae_reduction"] = 1 - row["mae_ewma"] / row["mae_no_change"] if row["mae_no_change"] else None
    signals_path = HERE / "signals.json.gz"
    signals_path.write_bytes(gzip.compress(json.dumps(signals, separators=(",", ":")).encode(), mtime=0))
    evaluation_path = HERE / "forecast_evaluation.json.gz"
    evaluation_path.write_bytes(gzip.compress(frame.to_json(orient="records", double_precision=15).encode(), mtime=0))
    summary_path = HERE / "h1_summary.json"
    save_json(summary_path, summary_rows)
    artifacts = [{"path": p.relative_to(ROOT).as_posix(), "sha256": digest(p.read_bytes()), "bytes": p.stat().st_size} for p in (signals_path, evaluation_path, summary_path, HERE / "manifest.json")]
    source_code = [{"path": p, "sha256": digest((ROOT / p).read_bytes())} for p in ("src/crypto_carry/forecast.py", "src/crypto_carry/evaluation.py", "src/crypto_carry/data/normalize.py", "src/crypto_carry/config.py", "src/crypto_carry/models.py")]
    result = {
        "created_at": datetime.now(timezone.utc).isoformat(), "status": "observed_funding_h1_complete",
        "scope": "H1 only; not portfolio backtest, H2, or composite H3", "configuration": config.to_dict(),
        "config_path": "configs/base.toml", "config_sha256": digest((ROOT / "configs/base.toml").read_bytes()),
        "source_code": source_code, "research_script": {"path": Path(__file__).relative_to(ROOT).as_posix(), "sha256": digest(Path(__file__).read_bytes())},
        "calendar_months_per_asset": len(months), "calendar_archive_count": len(entries), "coverage": coverage,
        "api_sources": api_sources, "signal_count": len(signals), "invalid_forecasts": dict(Counter(s["reason"] for s in signals if not s["valid"])),
        "evaluation_exclusion_reasons": frame.loc[~frame.horizon_valid, "reason"].value_counts().to_dict(),
        "summary": summary_rows, "artifacts": artifacts, "elapsed_seconds": round(time.monotonic() - began, 3),
        "downloaded_network_bytes": TRANSFER,
        "folder_bytes": sum(p.stat().st_size for p in HERE.rglob("*") if p.is_file()),
        "limitations": ["Overlapping horizons are not independent observations", "Common official API/archive sources do not exclude common-mode omissions", "No funding settlement marks were imputed", "H1 does not establish portfolio profitability or composite H3", "First December interval lacks an antecedent but lies outside all evaluated forecast histories", "Terminal horizons and unverified terminal calendar boundaries are excluded by the unchanged evaluation function"],
    }
    save_json(ROOT / "docs/research/funding_h1_preliminary_20260918.json", result)
    print(json.dumps({key: result[key] for key in ("status", "coverage", "evaluation_exclusion_reasons", "summary", "elapsed_seconds", "folder_bytes")}, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
