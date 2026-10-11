from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from crypto_carry.config import SECOND, Config, timestamp
from crypto_carry.data.market_calendar import BINANCE_SPOT_HALT_SOURCE, quality_closures
from crypto_carry.data.validate import (
    _required_keys,
    _validate_minute_bars,
    _validate_minute_pair,
    validate_data,
)


def _part(root: Path, name: str, rows: list[dict], time_field: str) -> dict:
    path = root / f"data/processed/{name}.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(rows), path)
    return {
        "path": path.relative_to(root).as_posix(),
        "start": rows[0][time_field],
        "end": rows[-1][time_field],
        "rows": len(rows),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def _price(symbol: str, market: str, minute: int) -> dict:
    return {
        "symbol": symbol,
        "market": market,
        "reference_id": f"bar:{symbol}:{market}:{minute}",
        "event_time": minute,
        "available_at": minute,
        "price": "100",
        "source_file": "fixture.zip",
    }


def _volume(symbol: str, market: str, minute: int, count: int = 1) -> dict:
    return {
        "symbol": symbol,
        "market": market,
        "open_time": minute,
        "close_time": minute + 60 * SECOND - 1_000_000,
        "available_at": minute + 60 * SECOND,
        "quantity": "1" if count else "0",
        "trade_count": count,
        "source_file": "fixture.zip",
    }


def _early_zero_volume(symbol: str, minute: int, close_time: int) -> dict:
    row = _volume(symbol, "spot", minute, count=0)
    row["close_time"] = close_time
    row["available_at"] = close_time + 1_000_000
    return row


def _bar(
    symbol: str,
    market: str,
    open_time: int,
    *,
    base_volume: str = "2",
    quote_volume: str = "200",
    low: str = "99",
    high: str = "101",
    count: int = 2,
) -> dict:
    return {
        "symbol": symbol,
        "market": market,
        "open_time": open_time,
        "end_time": open_time + 60 * SECOND,
        "available_at": open_time + 60 * SECOND,
        "open": "100",
        "high": high,
        "low": low,
        "close": "100",
        "base_volume": base_volume,
        "quote_volume": quote_volume,
        "trade_count": count,
        "source_file": "fixture.zip",
    }


def test_minute_model_keeps_funding_and_marks_protections():
    config = SimpleNamespace(symbols=("BTCUSDT",), execution_model="minute_open")

    assert list(_required_keys(config)) == [
        ("minute_prices", "BTCUSDT", "spot"),
        ("minute_volumes", "BTCUSDT", "spot"),
        ("minute_prices", "BTCUSDT", "futures"),
        ("minute_volumes", "BTCUSDT", "futures"),
        ("marks", "BTCUSDT", "futures"),
        ("funding", "BTCUSDT", "futures"),
    ]


def test_next_minute_vwap_requires_shared_closed_bars_marks_and_funding():
    config = SimpleNamespace(symbols=("BTCUSDT",), execution_model="next_minute_vwap")

    assert list(_required_keys(config)) == [
        ("minute_bars", "BTCUSDT", "spot"),
        ("minute_bars", "BTCUSDT", "futures"),
        ("marks", "BTCUSDT", "futures"),
        ("funding", "BTCUSDT", "futures"),
    ]


def test_closed_minute_signal_bridge_requires_bars_alongside_legacy_minute_inputs():
    config = SimpleNamespace(
        symbols=("BTCUSDT",),
        execution_model="minute_open",
        signal_price_model="closed_minute",
    )

    assert list(_required_keys(config)) == [
        ("minute_prices", "BTCUSDT", "spot"),
        ("minute_volumes", "BTCUSDT", "spot"),
        ("minute_prices", "BTCUSDT", "futures"),
        ("minute_volumes", "BTCUSDT", "futures"),
        ("minute_bars", "BTCUSDT", "spot"),
        ("minute_bars", "BTCUSDT", "futures"),
        ("marks", "BTCUSDT", "futures"),
        ("funding", "BTCUSDT", "futures"),
    ]


def test_closed_bar_validation_accepts_vwap_at_ohlc_tolerance_and_initial_antecedent(tmp_path):
    start = timestamp("2025-09-01T00:01:00Z")
    end = start + 2 * 60 * SECOND
    rows = [
        _bar("BTCUSDT", "spot", start - 60 * SECOND, quote_volume="202.00000002", high="101"),
        _bar("BTCUSDT", "spot", start),
        _bar("BTCUSDT", "spot", start + 60 * SECOND),
    ]
    part = _part(tmp_path, "bars", rows, "available_at")
    coverage = {"status": "complete", "checks": []}
    issues: list[str] = []

    _validate_minute_bars(tmp_path, "BTCUSDT", "spot", [part], start, end, coverage, issues)

    assert issues == []
    assert "complete_closed_bar_coverage" in coverage["checks"]
    assert "closed_bar_vwap_within_ohlc" in coverage["checks"]


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"base_volume": "0", "quote_volume": "1", "trade_count": 0}, "volume mismatch"),
        ({"base_volume": "1", "quote_volume": "0"}, "volume mismatch"),
        ({"base_volume": "2", "quote_volume": "204"}, "VWAP outside OHLC"),
        ({"available_at_delta": 1}, "invalid closed minute bar"),
    ],
)
def test_closed_bar_validation_rejects_volume_vwap_and_availability_errors(
    tmp_path, changes, message
):
    start = timestamp("2025-09-01T00:01:00Z")
    row = _bar("BTCUSDT", "spot", start - 60 * SECOND)
    delta = changes.pop("available_at_delta", None)
    row.update(changes)
    if delta is not None:
        row["available_at"] += delta
    part = _part(tmp_path, "bars", [row], "available_at")
    coverage = {"status": "complete", "checks": []}
    issues: list[str] = []

    _validate_minute_bars(
        tmp_path, "BTCUSDT", "spot", [part], start, start + 60 * SECOND, coverage, issues
    )

    assert coverage["status"] == "invalid"
    assert any(message in issue for issue in issues)


def test_closed_bar_validation_distinguishes_zero_volume_from_missing_bar(tmp_path):
    start = timestamp("2025-09-01T00:01:00Z")
    zero = _bar(
        "BTCUSDT",
        "spot",
        start - 60 * SECOND,
        base_volume="0",
        quote_volume="0",
        count=0,
    )
    part = _part(tmp_path, "bars", [zero], "available_at")
    zero_coverage = {"status": "complete", "checks": []}
    zero_issues: list[str] = []
    _validate_minute_bars(
        tmp_path,
        "BTCUSDT",
        "spot",
        [part],
        start,
        start + 60 * SECOND,
        zero_coverage,
        zero_issues,
    )

    missing_coverage = {"status": "complete", "checks": []}
    missing_issues: list[str] = []
    _validate_minute_bars(
        tmp_path,
        "BTCUSDT",
        "spot",
        [],
        start,
        start + 60 * SECOND,
        missing_coverage,
        missing_issues,
    )

    assert zero_coverage["status"] == "complete"
    assert zero_issues == []
    assert missing_coverage["status"] == "unknown"
    assert any("missing closed minute bar" in issue for issue in missing_issues)


def test_streaming_minute_validation_accepts_exact_volume_and_price_membership(tmp_path):
    start = timestamp("2025-09-01T00:00:00Z")
    end = start + 3 * 60 * SECOND
    volumes = [_volume("BTCUSDT", "spot", start + i * 60 * SECOND, count=i % 2) for i in range(3)]
    prices = [_price("BTCUSDT", "spot", start + 60 * SECOND)]
    price_part = _part(tmp_path, "prices", prices, "available_at")
    volume_part = _part(tmp_path, "volumes", volumes, "available_at")
    price_coverage = {"status": "complete", "checks": []}
    volume_coverage = {"status": "complete", "checks": []}
    issues: list[str] = []

    _validate_minute_pair(
        tmp_path,
        "BTCUSDT",
        "spot",
        [price_part],
        [volume_part],
        start,
        end,
        price_coverage,
        volume_coverage,
        issues,
    )

    assert issues == []
    assert "complete_minute_volume_coverage" in volume_coverage["checks"]
    assert "price_volume_membership" in price_coverage["checks"]


def test_streaming_minute_validation_reports_gap_and_price_without_positive_count(tmp_path):
    start = timestamp("2025-09-01T00:00:00Z")
    end = start + 3 * 60 * SECOND
    volumes = [
        _volume("BTCUSDT", "spot", start, count=1),
        _volume("BTCUSDT", "spot", start + 2 * 60 * SECOND, count=0),
    ]
    prices = [_price("BTCUSDT", "spot", start), _price("BTCUSDT", "spot", start + 2 * 60 * SECOND)]
    price_part = _part(tmp_path, "prices", prices, "available_at")
    volume_part = _part(tmp_path, "volumes", volumes, "available_at")
    price_coverage = {"status": "complete", "checks": []}
    volume_coverage = {"status": "complete", "checks": []}
    issues: list[str] = []

    _validate_minute_pair(
        tmp_path,
        "BTCUSDT",
        "spot",
        [price_part],
        [volume_part],
        start,
        end,
        price_coverage,
        volume_coverage,
        issues,
    )

    assert price_coverage["status"] == "invalid"
    assert volume_coverage["status"] == "unknown"
    assert any("missing minute volume" in issue for issue in issues)
    assert any("price-volume membership mismatch" in issue for issue in issues)


def test_streaming_minute_validation_rejects_an_unaligned_volume_event(tmp_path):
    start = timestamp("2025-09-01T00:00:00Z")
    end = start + 60 * SECOND
    bad_open = start + 30 * SECOND
    volume_part = _part(
        tmp_path,
        "volumes",
        [_volume("BTCUSDT", "spot", bad_open, count=0)],
        "available_at",
    )
    price_coverage = {"status": "complete", "checks": []}
    volume_coverage = {"status": "complete", "checks": []}
    issues: list[str] = []

    _validate_minute_pair(
        tmp_path,
        "BTCUSDT",
        "spot",
        [],
        [volume_part],
        start,
        end,
        price_coverage,
        volume_coverage,
        issues,
    )

    assert volume_coverage["status"] == "invalid"
    assert any("invalid minute volume" in issue for issue in issues)


def test_streaming_minute_validation_reports_an_unreadable_first_price_batch(tmp_path):
    start = timestamp("2025-09-01T00:00:00Z")
    end = start + 60 * SECOND
    price_part = _part(tmp_path, "prices", [{"unexpected": 1}], "unexpected")
    (tmp_path / price_part["path"]).unlink()
    volume_part = _part(
        tmp_path,
        "volumes",
        [_volume("BTCUSDT", "spot", start, count=0)],
        "available_at",
    )
    price_coverage = {"status": "complete", "checks": []}
    volume_coverage = {"status": "complete", "checks": []}
    issues: list[str] = []

    _validate_minute_pair(
        tmp_path,
        "BTCUSDT",
        "spot",
        [price_part],
        [volume_part],
        start,
        end,
        price_coverage,
        volume_coverage,
        issues,
    )

    assert price_coverage["status"] == "invalid"
    assert volume_coverage["status"] == "invalid"
    assert any("unreadable minute rows" in issue for issue in issues)


def test_documented_spot_closure_excludes_only_closed_gap_and_accepts_recovery(tmp_path):
    start = timestamp("2023-03-24T11:27:00Z")
    closed = timestamp("2023-03-24T11:28:00Z")
    recovery = timestamp("2023-03-24T14:00:00Z")
    end = recovery + 60 * SECOND
    volumes = [
        _volume("BTCUSDT", "spot", start, count=0),
        _early_zero_volume("BTCUSDT", closed, closed + 41 * SECOND),
        _volume("BTCUSDT", "spot", recovery, count=1),
    ]
    prices = [_price("BTCUSDT", "spot", recovery)]
    price_part = _part(tmp_path, "prices", prices, "available_at")
    volume_part = _part(tmp_path, "volumes", volumes, "available_at")
    price_coverage = {"status": "complete", "checks": []}
    volume_coverage = {"status": "complete", "checks": []}
    issues: list[str] = []

    _validate_minute_pair(
        tmp_path,
        "BTCUSDT",
        "spot",
        [price_part],
        [volume_part],
        start,
        end,
        price_coverage,
        volume_coverage,
        issues,
    )

    assert issues == []
    assert "documented_market_closure" in volume_coverage["checks"]
    assert "complete_minute_volume_coverage" in volume_coverage["checks"]
    assert "price_volume_membership" in price_coverage["checks"]


def test_documented_spot_closure_rejects_positive_count_inside_closed_minute(tmp_path):
    closed = timestamp("2023-03-24T11:28:00Z")
    end = closed + 60 * SECOND
    price_part = _part(
        tmp_path,
        "prices",
        [_price("BTCUSDT", "spot", closed)],
        "available_at",
    )
    volume_part = _part(
        tmp_path,
        "volumes",
        [_volume("BTCUSDT", "spot", closed, count=1)],
        "available_at",
    )
    price_coverage = {"status": "complete", "checks": []}
    volume_coverage = {"status": "complete", "checks": []}
    issues: list[str] = []

    _validate_minute_pair(
        tmp_path,
        "BTCUSDT",
        "spot",
        [price_part],
        [volume_part],
        closed,
        end,
        price_coverage,
        volume_coverage,
        issues,
    )

    assert volume_coverage["status"] == "invalid"
    assert any("invalid minute volume" in issue for issue in issues)


def test_documented_closure_quality_discloses_exact_window_and_primary_source():
    start = timestamp("2023-03-24T11:00:00Z")
    end = timestamp("2023-03-24T15:00:00Z")

    closures = quality_closures(("BTCUSDT", "ETHUSDT"), start, end)

    assert closures == [
        {
            "symbols": ["BTCUSDT", "ETHUSDT"],
            "market": "spot",
            "start": timestamp("2023-03-24T11:28:00Z"),
            "end": timestamp("2023-03-24T14:00:00Z"),
            "start_utc": "2023-03-24T11:28:00.000000000Z",
            "end_utc": "2023-03-24T14:00:00.000000000Z",
            "minutes": 152,
            "source_url": BINANCE_SPOT_HALT_SOURCE,
            "description": "Binance spot trading halt; full unavailable minutes after the 11:27 partial minute",
        }
    ]


def test_validation_uses_documented_closures_quality_interface(tmp_path):
    config = Config(
        history_start="2023-03-24T11:00:00Z",
        start="2023-03-24T11:00:00Z",
        end="2023-03-25T00:00:00Z",
        sample_start="2023-03-24T11:00:00Z",
        sample_end="2023-03-24T15:00:00Z",
        execution_model="minute_open",
        order_timeout_seconds=120,
        analysis_mode="prescribed_research",
        fee_profile="prescribed_fixed_no_discounts",
    )
    manifests = tmp_path / config.data_dir / "manifests"
    manifests.mkdir(parents=True)
    (manifests / "processed.json").write_text(
        '{"kind":"minute_market_data","entries":[]}', encoding="utf-8"
    )

    result = validate_data(config, tmp_path, scope="sample")

    assert result["documented_closures"][0]["source_url"] == BINANCE_SPOT_HALT_SOURCE
    assert "documented_market_closures" not in result
    report = (manifests / "data_quality_report.md").read_text(encoding="utf-8")
    assert BINANCE_SPOT_HALT_SOURCE in report
