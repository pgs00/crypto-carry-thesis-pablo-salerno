"""Bounded downloads from official Binance public endpoints."""

from __future__ import annotations

import hashlib
import json
import time
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx

from ..config import HOUR, Config, timestamp

VISION = "https://data.binance.vision/data"
FUNDING_API = "https://fapi.binance.com/fapi/v1/fundingRate"


class DataBudgetExceeded(RuntimeError):
    """Raised before a write would exceed the configured aggregate data budget."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _data_bytes(data_root: Path) -> int:
    return sum(path.stat().st_size for path in data_root.rglob("*") if path.is_file())


def _ensure_budget(data_root: Path, budget_limit: int, additional: int = 0) -> None:
    used = _data_bytes(data_root) if data_root.exists() else 0
    if used + max(0, additional) > budget_limit:
        raise DataBudgetExceeded(
            f"Data budget exceeded: {used} existing + {additional} prospective > {budget_limit}"
        )


def fetch_funding_pages(
    client: httpx.Client,
    symbol: str,
    start_ms: int,
    end_ms: int,
    *,
    limit: int = 1000,
) -> list[dict]:
    """Fetch an inclusive API range while advancing past the last returned millisecond."""
    rows: list[dict] = []
    seen: dict[int, dict] = {}
    cursor = start_ms
    while cursor <= end_ms:
        response = client.get(
            FUNDING_API,
            params={"symbol": symbol, "startTime": cursor, "endTime": end_ms, "limit": limit},
        )
        response.raise_for_status()
        page = response.json()
        if not isinstance(page, list):
            raise TypeError("Funding endpoint did not return a list")
        page = sorted(page, key=lambda row: int(row["fundingTime"]))
        for row in page:
            event_ms = int(row["fundingTime"])
            if event_ms in seen and seen[event_ms] != row:
                raise ValueError(f"Conflicting funding duplicate: {symbol}/{event_ms}")
            if start_ms <= event_ms <= end_ms and event_ms not in seen:
                rows.append(row)
                seen[event_ms] = row
        if len(page) < limit:
            break
        next_cursor = int(page[-1]["fundingTime"]) + 1
        if next_cursor <= cursor:
            raise ValueError("Funding pagination did not advance")
        cursor = next_cursor
        time.sleep(0.05)
    return rows


def _response_bytes(client: httpx.Client, url: str, retries: int = 3) -> bytes:
    error: Exception | None = None
    for attempt in range(retries):
        try:
            response = client.get(url)
            response.raise_for_status()
            return response.content
        except httpx.HTTPError as exc:
            error = exc
            if attempt + 1 < retries:
                time.sleep(0.25 * (2**attempt))
    assert error is not None
    raise error


def download_verified_archive(
    client: httpx.Client,
    url: str,
    destination: Path,
    *,
    expected_sha256: str,
    budget_limit: int,
    data_root: Path,
    retries: int = 3,
) -> dict[str, Any]:
    """Resume one archive and atomically publish it only after SHA and ZIP checks."""
    expected_sha256 = expected_sha256.lower()
    if destination.exists():
        actual = _sha256(destination)
        if actual == expected_sha256:
            with zipfile.ZipFile(destination) as archive:
                if archive.testzip() is not None:
                    raise ValueError(f"Corrupt cached ZIP: {destination}")
            return {"status": "cached", "sha256": actual, "bytes": destination.stat().st_size}
        raise ValueError(f"Existing raw file has unexpected checksum: {destination}")

    destination.parent.mkdir(parents=True, exist_ok=True)
    part = destination.with_suffix(destination.suffix + ".part")
    offset = part.stat().st_size if part.exists() else 0
    error: Exception | None = None
    for attempt in range(retries):
        try:
            headers = {"Range": f"bytes={offset}-"} if offset else {}
            with client.stream("GET", url, headers=headers) as response:
                response.raise_for_status()
                if offset and response.status_code != 206:
                    # A server that ignores Range cannot safely append to a partial archive.
                    part.unlink()
                    offset = 0
                    continue
                if offset:
                    content_range = response.headers.get("content-range", "")
                    if not content_range.startswith(f"bytes {offset}-"):
                        raise ValueError(f"Invalid Content-Range while resuming {url}")
                content_length = int(response.headers.get("content-length", "0"))
                _ensure_budget(data_root, budget_limit, content_length)
                mode = "ab" if offset else "wb"
                with part.open(mode) as stream:
                    for chunk in response.iter_bytes():
                        _ensure_budget(data_root, budget_limit, len(chunk))
                        stream.write(chunk)
            actual = _sha256(part)
            if actual != expected_sha256:
                part.unlink()
                raise ValueError(f"SHA-256 mismatch for {url}: {actual} != {expected_sha256}")
            with zipfile.ZipFile(part) as archive:
                broken = archive.testzip()
                if broken is not None:
                    part.unlink()
                    raise ValueError(f"ZIP integrity failure in {broken}")
            part.replace(destination)
            return {"status": "downloaded", "sha256": actual, "bytes": destination.stat().st_size}
        except DataBudgetExceeded:
            raise
        except (httpx.HTTPError, OSError, ValueError, zipfile.BadZipFile) as exc:
            error = exc
            offset = part.stat().st_size if part.exists() else 0
            if attempt + 1 < retries:
                time.sleep(0.25 * (2**attempt))
    assert error is not None
    raise error


def _checksum_value(content: bytes, url: str) -> str:
    text = content.decode("ascii", errors="strict")
    value = text.split()[0].strip().lower()
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError(f"Invalid official checksum for {url}")
    return value


def _write_raw_bytes(path: Path, content: bytes, data_root: Path, budget: int) -> dict:
    digest = hashlib.sha256(content).hexdigest()
    if path.exists():
        if _sha256(path) != digest:
            raise ValueError(f"Refusing to overwrite different raw file: {path}")
        return {"status": "cached", "sha256": digest, "bytes": path.stat().st_size}
    _ensure_budget(data_root, budget, len(content))
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".part")
    temporary.write_bytes(content)
    temporary.replace(path)
    return {"status": "downloaded", "sha256": digest, "bytes": len(content)}


def _dates(start: datetime, end: datetime):
    current = start
    while current < end:
        yield current.date().isoformat()
        current += timedelta(days=1)


def _months(start: datetime, end: datetime):
    current = start.replace(day=1)
    while current < end:
        yield current.strftime("%Y-%m")
        current = (current.replace(day=28) + timedelta(days=4)).replace(day=1)


def _archive_descriptors(config: Config, start: datetime, end: datetime, funding_start: datetime):
    for symbol in config.symbols:
        previous = (start - timedelta(days=1)).date().isoformat()
        name = f"{symbol}-1m-{previous}.zip"
        yield {
            "dataset": "marks",
            "symbol": symbol,
            "market": "futures",
            "start": f"{previous}T00:00:00Z",
            "end": f"{previous}T23:59:59.999999999Z",
            "url": f"{VISION}/futures/um/daily/markPriceKlines/{symbol}/1m/{name}",
            "relative": f"raw/futures/markPriceKlines/{symbol}/{name}",
        }
        for day in _dates(start, end):
            for market, prefix in (("spot", "spot"), ("futures", "futures/um")):
                name = f"{symbol}-trades-{day}.zip"
                yield {
                    "dataset": "trades",
                    "symbol": symbol,
                    "market": market,
                    "start": f"{day}T00:00:00Z",
                    "end": f"{day}T23:59:59.999999999Z",
                    "url": f"{VISION}/{prefix}/daily/trades/{symbol}/{name}",
                    "relative": f"raw/{market}/trades/{symbol}/{name}",
                }
            name = f"{symbol}-1m-{day}.zip"
            yield {
                "dataset": "marks",
                "symbol": symbol,
                "market": "futures",
                "start": f"{day}T00:00:00Z",
                "end": f"{day}T23:59:59.999999999Z",
                "url": f"{VISION}/futures/um/daily/markPriceKlines/{symbol}/1m/{name}",
                "relative": f"raw/futures/markPriceKlines/{symbol}/{name}",
            }
        for month in _months(funding_start, end):
            name = f"{symbol}-fundingRate-{month}.zip"
            yield {
                "dataset": "funding_calendar",
                "symbol": symbol,
                "market": "futures",
                "start": f"{month}-01T00:00:00Z",
                "end": None,
                "url": f"{VISION}/futures/um/monthly/fundingRate/{symbol}/{name}",
                "relative": f"raw/futures/fundingRate/{symbol}/{name}",
            }


def _write_json_raw(path: Path, payload: Any, data_root: Path, budget: int) -> dict:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    digest = hashlib.sha256(encoded).hexdigest()
    if path.exists():
        if _sha256(path) != digest:
            raise ValueError(f"Refusing to overwrite different raw response: {path}")
        return {"status": "cached", "sha256": digest, "bytes": path.stat().st_size}
    _ensure_budget(data_root, budget, len(encoded))
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_suffix(path.suffix + ".part")
    part.write_bytes(encoded)
    part.replace(path)
    return {"status": "downloaded", "sha256": digest, "bytes": len(encoded)}


def download(config: Config, root: Path, scope: str = "sample") -> dict:
    """Download a bounded sample or configured full range and persist exact provenance."""
    if scope not in {"sample", "full"}:
        raise ValueError("scope must be 'sample' or 'full'")
    root = Path(root).resolve()
    data_root = (root / config.data_dir).resolve()
    if root not in data_root.parents:
        raise ValueError("data_dir must remain inside the project root")
    _ensure_budget(data_root, config.data_budget_bytes)

    start_ns = timestamp(config.sample_start if scope == "sample" else config.history_start)
    end_ns = timestamp(config.sample_end if scope == "sample" else config.end)
    funding_start_ns = start_ns - (config.window_hours + 24) * HOUR
    # Request one more day so normalization can preserve the antecedent observation.
    funding_request_ns = funding_start_ns - 24 * HOUR
    start = datetime.fromtimestamp(start_ns / 1_000_000_000, UTC)
    end = datetime.fromtimestamp(end_ns / 1_000_000_000, UTC)
    funding_start = datetime.fromtimestamp(funding_request_ns / 1_000_000_000, UTC)
    retrieved_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    entries: list[dict] = []

    timeout = httpx.Timeout(60, connect=20)
    with httpx.Client(
        timeout=timeout, follow_redirects=True, headers={"User-Agent": "crypto-carry-research/0.1"}
    ) as client:
        for descriptor in _archive_descriptors(config, start, end, funding_start):
            entry = {
                "source_url": descriptor["url"],
                "path": f"{config.data_dir}/{descriptor['relative']}",
                "dataset": descriptor["dataset"],
                "symbol": descriptor["symbol"],
                "market": descriptor["market"],
                "start": descriptor["start"],
                "end": descriptor["end"],
                "retrieved_at": retrieved_at,
                "status": "failed",
                "errors": [],
            }
            try:
                checksum_content = _response_bytes(client, descriptor["url"] + ".CHECKSUM")
                expected = _checksum_value(checksum_content, descriptor["url"])
                checksum_path = root / (entry["path"] + ".CHECKSUM")
                checksum_outcome = _write_raw_bytes(
                    checksum_path, checksum_content, data_root, config.data_budget_bytes
                )
                outcome = download_verified_archive(
                    client,
                    descriptor["url"],
                    root / entry["path"],
                    expected_sha256=expected,
                    budget_limit=config.data_budget_bytes,
                    data_root=data_root,
                )
                entry.update(outcome)
                entry["checksum_url"] = descriptor["url"] + ".CHECKSUM"
                entry["checksum_path"] = str(checksum_path.relative_to(root)).replace("\\", "/")
                entry["checksum_file_sha256"] = checksum_outcome["sha256"]
            except DataBudgetExceeded:
                raise
            except (
                httpx.HTTPError,
                OSError,
                TypeError,
                UnicodeError,
                ValueError,
                zipfile.BadZipFile,
            ) as exc:
                entry["errors"].append(f"{type(exc).__name__}: {exc}")
            entries.append(entry)

        for symbol in config.symbols:
            entry = {
                "source_url": FUNDING_API,
                "path": (
                    f"{config.data_dir}/raw/futures/funding_api/{symbol}/"
                    f"funding-{funding_request_ns // 1_000_000}-{(end_ns - 1) // 1_000_000}.json"
                ),
                "dataset": "funding",
                "symbol": symbol,
                "market": "futures",
                "start": funding_request_ns,
                "end": end_ns - 1,
                "retrieved_at": retrieved_at,
                "status": "failed",
                "errors": [],
            }
            try:
                rows = fetch_funding_pages(
                    client,
                    symbol,
                    funding_request_ns // 1_000_000,
                    (end_ns - 1) // 1_000_000,
                )
                outcome = _write_json_raw(
                    root / entry["path"], rows, data_root, config.data_budget_bytes
                )
                entry.update(outcome)
                entry["rows"] = len(rows)
            except DataBudgetExceeded:
                raise
            except (httpx.HTTPError, OSError, TypeError, ValueError) as exc:
                entry["errors"].append(f"{type(exc).__name__}: {exc}")
            entries.append(entry)

    manifest = {
        "version": 1,
        "scope": scope,
        "requested_start": start_ns,
        "requested_end": end_ns,
        "funding_warmup_start": funding_start_ns,
        "funding_request_start": funding_request_ns,
        "budget_bytes": config.data_budget_bytes,
        "bytes_used": _data_bytes(data_root),
        "retrieved_at": retrieved_at,
        "entries": entries,
    }
    manifest_path = data_root / "manifests" / "download.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(manifest, indent=2, sort_keys=True).encode()
    _ensure_budget(data_root, config.data_budget_bytes, len(encoded))
    temp = manifest_path.with_suffix(".json.part")
    temp.write_bytes(encoded)
    temp.replace(manifest_path)
    return manifest
