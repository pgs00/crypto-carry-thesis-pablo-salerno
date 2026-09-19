from __future__ import annotations

import hashlib
import json
import zipfile
from decimal import Decimal
from pathlib import Path

import pyarrow.parquet as pq
import pytest

from crypto_carry.config import SECOND, Config, timestamp
from crypto_carry.data import normalize
from crypto_carry.data.market_calendar import BINANCE_SPOT_HALT_SOURCE
from crypto_carry.models import MinuteBar
from crypto_carry.serialization import decode, encode


def _write_kline_zip(path: Path, rows: list[list[str]], *, header: bool = True) -> None:
    columns = [
        "open_time",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "close_time",
        "quote_volume",
        "count",
        "taker_buy_volume",
        "taker_buy_quote_volume",
        "ignore",
    ]
    lines = [",".join(columns)] if header else []
    lines.extend(",".join(row) for row in rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(path.with_suffix(".csv").name, "\n".join(lines) + "\n")


def _row(
    open_time: int,
    *,
    unit: str,
    count: int = 3,
    volume: str = "2.5",
    quote_volume: str | None = None,
) -> list[str]:
    width = 60_000_000 if unit == "us" else 60_000
    quote_volume = ("0" if volume == "0" else "250") if quote_volume is None else quote_volume
    return [
        str(open_time),
        "100",
        "110",
        "90",
        "105",
        volume,
        str(open_time + width - 1),
        quote_volume,
        str(count),
        "1",
        "100",
        "0",
    ]


def _write_checksum(path: Path, archive: Path) -> str:
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    path.write_text(f"{digest}  {archive.name}\n", encoding="utf-8")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_kline_records_publish_open_price_immediately_and_volume_after_close(tmp_path):
    open_ns = timestamp("2025-09-01T00:00:00Z")
    open_us = open_ns // 1_000
    path = tmp_path / "BTCUSDT-1m-2025-09.zip"
    _write_kline_zip(
        path,
        [
            _row(open_us, unit="us"),
            _row(open_us + 60_000_000, unit="us", count=0, volume="0"),
        ],
    )
    stats: dict = {}

    records = list(
        normalize._kline_records(
            path,
            "BTCUSDT",
            "spot",
            timestamp_unit="us",
            source_start="2025-09-01T00:00:00Z",
            stats=stats,
        )
    )

    assert records[0][0] == {
        "symbol": "BTCUSDT",
        "market": "spot",
        "reference_id": f"bar:BTCUSDT:spot:{open_ns}",
        "event_time": open_ns,
        "available_at": open_ns,
        "price": "100",
        "source_file": path.name,
    }
    assert records[0][1]["available_at"] == open_ns + 60 * SECOND
    assert records[0][1]["quantity"] == "2.5"
    assert records[0][1]["trade_count"] == 3
    assert records[0][2] == {
        "symbol": "BTCUSDT",
        "market": "spot",
        "open_time": open_ns,
        "end_time": open_ns + 60 * SECOND,
        "available_at": open_ns + 60 * SECOND,
        "open": "100",
        "high": "110",
        "low": "90",
        "close": "105",
        "base_volume": "2.5",
        "quote_volume": "250",
        "trade_count": 3,
        "source_file": path.name,
    }
    assert records[1][0] is None
    assert records[1][1]["quantity"] == "0"
    assert records[1][1]["trade_count"] == 0
    assert records[1][2]["base_volume"] == records[1][2]["quote_volume"] == "0"
    assert stats["minute_coverage_complete"] is True


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({1: "NaN"}, "finite positive OHLC"),
        ({3: "106"}, "OHLC ordering"),
        ({5: "-1"}, "non-negative volume"),
        ({8: "-1"}, "non-negative trade count"),
        ({5: "1", 8: "0"}, "zero trades require zero volume"),
        ({5: "0", 7: "1", 8: "0"}, "base and quote volumes must both be zero"),
        ({5: "1", 7: "0"}, "positive base volume requires positive quote volume"),
        ({5: "1", 7: "111"}, "VWAP must lie within OHLC"),
        ({6: "1756684859998"}, "exact one-minute interval"),
    ],
)
def test_kline_records_reject_malformed_candles(tmp_path, changes, message):
    open_ms = timestamp("2025-09-01T00:00:00Z") // 1_000_000
    values = _row(open_ms, unit="ms")
    for index, value in changes.items():
        values[index] = value
    path = tmp_path / "BTCUSDT-1m-2025-09.zip"
    _write_kline_zip(path, [values], header=False)

    with pytest.raises(ValueError, match=message):
        list(
            normalize._kline_records(
                path,
                "BTCUSDT",
                "futures",
                timestamp_unit="ms",
                source_start="2025-09-01T00:00:00Z",
                stats={},
            )
        )


def test_kline_records_reject_wrong_unit_and_duplicate_but_retain_gap(tmp_path):
    open_ns = timestamp("2025-09-01T00:00:00Z")
    open_us = open_ns // 1_000
    path = tmp_path / "BTCUSDT-1m-2025-09.zip"
    _write_kline_zip(path, [_row(open_us, unit="us")])
    with pytest.raises(ValueError, match="timestamp unit"):
        list(
            normalize._kline_records(
                path,
                "BTCUSDT",
                "spot",
                timestamp_unit="ms",
                source_start="2025-09-01T00:00:00Z",
                stats={},
            )
        )

    _write_kline_zip(path, [_row(open_us, unit="us"), _row(open_us, unit="us")])
    with pytest.raises(ValueError, match="strictly chronological"):
        list(
            normalize._kline_records(
                path,
                "BTCUSDT",
                "spot",
                timestamp_unit="us",
                source_start="2025-09-01T00:00:00Z",
                stats={},
            )
        )

    stats: dict = {}
    _write_kline_zip(path, [_row(open_us, unit="us"), _row(open_us + 120_000_000, unit="us")])
    assert (
        len(
            list(
                normalize._kline_records(
                    path,
                    "BTCUSDT",
                    "spot",
                    timestamp_unit="us",
                    source_start="2025-09-01T00:00:00Z",
                    stats=stats,
                )
            )
        )
        == 2
    )
    assert stats["minute_coverage_complete"] is False


def test_kline_records_reject_a_non_binance_header(tmp_path):
    open_ms = timestamp("2024-09-01T00:00:00Z") // 1_000_000
    path = tmp_path / "BTCUSDT-1m-2024-09.zip"
    _write_kline_zip(path, [_row(open_ms, unit="ms")])
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "fixture.csv",
            "open_time,close,high,low,open,volume,close_time,quote_volume,count,"
            "taker_buy_volume,taker_buy_quote_volume,ignore\n"
            + ",".join(_row(open_ms, unit="ms"))
            + "\n",
        )

    with pytest.raises(ValueError, match="Binance 12-field kline header"):
        list(
            normalize._kline_records(
                path,
                "BTCUSDT",
                "spot",
                timestamp_unit="ms",
                source_start="2024-09-01T00:00:00Z",
                stats={},
            )
        )


def test_minute_manifest_adds_shared_closed_bars_without_replacing_legacy_datasets(tmp_path):
    config = Config(
        data_dir="data/minutes/window",
        analysis_mode="prescribed_research",
        fee_profile="prescribed_fixed_no_discounts",
    )
    open_ns = timestamp("2025-09-01T00:00:00Z")
    path = tmp_path / config.data_dir / "raw/spot/klines/BTCUSDT/BTCUSDT-1m-2025-09.zip"
    _write_kline_zip(path, [_row(open_ns // 1_000, unit="us")])
    manifest_path = tmp_path / config.data_dir / "manifests/download.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(
        json.dumps(
            {
                "kind": "minute_market_data",
                "entries": [
                    {
                        "dataset": "klines",
                        "symbol": "BTCUSDT",
                        "market": "spot",
                        "path": path.relative_to(tmp_path).as_posix(),
                        "status": "downloaded",
                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                        "timestamp_unit": "us",
                        "start": "2025-09-01T00:00:00Z",
                        "end": "2025-09-30T23:59:59.999999999Z",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    result = normalize.normalize(config, tmp_path)

    assert result["kind"] == "minute_market_data"
    assert result["errors"] == []
    assert {entry["dataset"] for entry in result["entries"]} == {
        "minute_bars",
        "minute_prices",
        "minute_volumes",
    }
    bar_entry = next(e for e in result["entries"] if e["dataset"] == "minute_bars")
    price_entry = next(e for e in result["entries"] if e["dataset"] == "minute_prices")
    volume_entry = next(e for e in result["entries"] if e["dataset"] == "minute_volumes")
    price = pq.read_table(tmp_path / price_entry["path"]).to_pylist()[0]
    volume = pq.read_table(tmp_path / volume_entry["path"]).to_pylist()[0]
    bar = pq.read_table(tmp_path / bar_entry["path"]).to_pylist()[0]
    assert price_entry["start"] == price_entry["end"] == open_ns
    assert volume_entry["start"] == volume_entry["end"] == open_ns + 60 * SECOND
    assert bar_entry["start"] == bar_entry["end"] == open_ns + 60 * SECOND
    assert bar["end_time"] == bar["available_at"] == open_ns + 60 * SECOND
    assert (bar["open"], bar["high"], bar["low"], bar["close"]) == (
        "100",
        "110",
        "90",
        "105",
    )
    assert (bar["base_volume"], bar["quote_volume"], bar["trade_count"]) == (
        "2.5",
        "250",
        3,
    )
    assert price["source_file"] == volume["source_file"] == path.name


def test_minute_bar_contract_is_closed_causal_and_checkpoint_safe():
    bar = MinuteBar(
        symbol="BTCUSDT",
        market="spot",
        open_time=0,
        end_time=60 * SECOND,
        available_at=60 * SECOND,
        open=Decimal("99"),
        high=Decimal("101"),
        low=Decimal("98"),
        close=Decimal("100"),
        base_volume=Decimal("2"),
        quote_volume=Decimal("200"),
        trade_count=4,
        source_file="fixture.zip",
    )

    assert bar.event_time == bar.available_at == bar.end_time
    assert bar.price == Decimal("100")
    assert bar.reference_id == "bar:BTCUSDT:spot:0"
    assert decode(encode(bar)) == bar


def test_funding_partition_keeps_nullable_string_schema_when_all_marks_are_missing(tmp_path):
    config = Config(
        data_dir="data/minutes/window",
        analysis_mode="prescribed_research",
        fee_profile="prescribed_fixed_no_discounts",
    )
    raw_path = tmp_path / config.data_dir / "raw/futures/funding_api/BTCUSDT/funding.json"
    raw_path.parent.mkdir(parents=True)
    raw_path.write_text(
        json.dumps(
            [{"fundingTime": index * 8 * 3600_000, "fundingRate": "0.0001"} for index in range(3)]
        ),
        encoding="utf-8",
    )
    manifest_path = tmp_path / config.data_dir / "manifests/download.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(
        json.dumps(
            {
                "kind": "minute_market_data",
                "entries": [
                    {
                        "dataset": "funding",
                        "symbol": "BTCUSDT",
                        "market": "futures",
                        "path": raw_path.relative_to(tmp_path).as_posix(),
                        "status": "downloaded",
                        "sha256": hashlib.sha256(raw_path.read_bytes()).hexdigest(),
                        "start": 0,
                        "end": 16 * 3600 * SECOND,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    result = normalize.normalize(config, tmp_path)

    assert result["errors"] == []
    funding = next(entry for entry in result["entries"] if entry["dataset"] == "funding")
    path = tmp_path / funding["path"]
    assert str(pq.read_schema(path).field("settlement_mark_price").type) == "string"
    assert [row["settlement_mark_price"] for row in pq.read_table(path).to_pylist()] == [
        None,
        None,
    ]


def test_spot_halt_allows_only_observed_early_zero_bar_and_documented_missing_minutes(tmp_path):
    before = timestamp("2023-03-24T11:27:00Z") // 1_000_000
    closed = timestamp("2023-03-24T11:28:00Z") // 1_000_000
    recovery = timestamp("2023-03-24T14:00:00Z") // 1_000_000
    early = _row(closed, unit="ms", count=0, volume="0")
    early[6] = str(closed + 20_000)
    path = tmp_path / "BTCUSDT-1m-2023-03.zip"
    _write_kline_zip(
        path,
        [_row(before, unit="ms", count=0, volume="0"), early, _row(recovery, unit="ms")],
        header=False,
    )
    stats: dict = {}

    records = list(
        normalize._kline_records(
            path,
            "BTCUSDT",
            "spot",
            timestamp_unit="ms",
            source_start="2023-03-01T00:00:00Z",
            stats=stats,
        )
    )

    assert records[1][0] is None
    assert records[1][1]["available_at"] == (closed + 20_001) * 1_000_000
    assert stats["documented_missing_minutes"] == 151
    assert stats["minute_coverage_complete"] is True


def test_spot_halt_rejects_positive_count_and_early_close_outside_documented_window(tmp_path):
    closed = timestamp("2023-03-24T11:28:00Z") // 1_000_000
    path = tmp_path / "BTCUSDT-1m-2023-03.zip"
    _write_kline_zip(path, [_row(closed, unit="ms")], header=False)
    with pytest.raises(ValueError, match="positive trades during documented closure"):
        list(
            normalize._kline_records(
                path,
                "BTCUSDT",
                "spot",
                timestamp_unit="ms",
                source_start="2023-03-01T00:00:00Z",
                stats={},
            )
        )

    outside = timestamp("2023-03-24T14:00:00Z") // 1_000_000
    early = _row(outside, unit="ms", count=0, volume="0")
    early[6] = str(outside + 20_000)
    _write_kline_zip(path, [early], header=False)
    with pytest.raises(ValueError, match="exact one-minute interval"):
        list(
            normalize._kline_records(
                path,
                "BTCUSDT",
                "spot",
                timestamp_unit="ms",
                source_start="2023-03-01T00:00:00Z",
                stats={},
            )
        )


def test_minute_manifest_completeness_counts_only_documented_missing_closure_minutes(tmp_path):
    config = Config(
        data_dir="data/minutes/window",
        analysis_mode="prescribed_research",
        fee_profile="prescribed_fixed_no_discounts",
    )
    before = timestamp("2023-03-24T11:27:00Z") // 1_000_000
    closed = timestamp("2023-03-24T11:28:00Z") // 1_000_000
    recovery = timestamp("2023-03-24T14:00:00Z") // 1_000_000
    early = _row(closed, unit="ms", count=0, volume="0")
    early[6] = str(closed + 41_646)
    path = tmp_path / config.data_dir / "raw/spot/klines/BTCUSDT/BTCUSDT-1m-2023-03.zip"
    _write_kline_zip(
        path,
        [_row(before, unit="ms", count=0, volume="0"), early, _row(recovery, unit="ms")],
        header=False,
    )
    manifest = tmp_path / config.data_dir / "manifests/download.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        json.dumps(
            {
                "kind": "minute_market_data",
                "entries": [
                    {
                        "dataset": "klines",
                        "symbol": "BTCUSDT",
                        "market": "spot",
                        "path": path.relative_to(tmp_path).as_posix(),
                        "status": "downloaded",
                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                        "timestamp_unit": "ms",
                        "start": "2023-03-24T11:27:00Z",
                        "end": "2023-03-24T14:00:59.999999999Z",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    result = normalize.normalize(config, tmp_path)

    assert result["errors"] == []
    assert len(result["entries"]) == 3
    assert all(entry["complete"] is True for entry in result["entries"])
    assert all(entry["source_rows"] == 3 for entry in result["entries"])
    assert all(entry["documented_missing_minutes"] == 151 for entry in result["entries"])


def _mark_supplement_manifest(
    tmp_path: Path,
    *,
    conflicting: bool = False,
    bad_hash: bool = False,
    bad_checksum_hash: bool = False,
    bad_official_digest: bool = False,
    bad_checksum_name: bool = False,
    malformed_mark: bool = False,
    supplement_symbol: str = "BTCUSDT",
    supplement_market: str = "futures",
):
    config = Config(
        data_dir="data/minutes/window",
        analysis_mode="prescribed_research",
        fee_profile="prescribed_fixed_no_discounts",
    )
    start_ns = timestamp("2022-10-02T00:00:00Z")
    start_ms = start_ns // 1_000_000
    monthly = tmp_path / config.data_dir / "raw/futures/markPriceKlines/BTCUSDT/monthly.zip"
    daily = tmp_path / config.data_dir / "raw/futures/markPriceKlines/BTCUSDT/daily.zip"
    _write_kline_zip(
        monthly,
        [_row(start_ms, unit="ms"), _row(start_ms + 120_000, unit="ms")],
        header=False,
    )
    if malformed_mark:
        malformed = _row(start_ms, unit="ms")
        malformed[1] = "not-a-decimal"
        _write_kline_zip(monthly, [malformed], header=False)
    supplement_rows = [_row(start_ms, unit="ms"), _row(start_ms + 60_000, unit="ms")]
    if conflicting:
        supplement_rows[0][1] = "999"
        supplement_rows[0][2] = "999"
        supplement_rows[0][4] = "999"
    _write_kline_zip(daily, supplement_rows, header=False)
    checksum_path = daily.with_suffix(".zip.CHECKSUM")
    checksum_sha = _write_checksum(checksum_path, daily)
    if bad_official_digest or bad_checksum_name:
        digest = "0" * 64 if bad_official_digest else hashlib.sha256(daily.read_bytes()).hexdigest()
        name = "wrong-file.zip" if bad_checksum_name else daily.name
        checksum_path.write_text(f"{digest}  {name}\n", encoding="utf-8")
        checksum_sha = hashlib.sha256(checksum_path.read_bytes()).hexdigest()
    manifest_path = tmp_path / config.data_dir / "manifests/download.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(
        json.dumps(
            {
                "kind": "minute_market_data",
                "entries": [
                    {
                        "dataset": "marks",
                        "symbol": "BTCUSDT",
                        "market": "futures",
                        "path": monthly.relative_to(tmp_path).as_posix(),
                        "status": "downloaded",
                        "sha256": hashlib.sha256(monthly.read_bytes()).hexdigest(),
                        "start": "2022-10-02T00:00:00Z",
                        "end": "2022-10-02T00:02:59.999999999Z",
                        "supplements": [
                            {
                                "status": "downloaded",
                                "dataset": "marks",
                                "symbol": supplement_symbol,
                                "market": supplement_market,
                                "timestamp_unit": "ms",
                                "path": daily.relative_to(tmp_path).as_posix(),
                                "source_url": "https://data.binance.vision/daily.zip",
                                "sha256": "0" * 64
                                if bad_hash
                                else hashlib.sha256(daily.read_bytes()).hexdigest(),
                                "bytes": daily.stat().st_size,
                                "checksum_path": checksum_path.relative_to(tmp_path).as_posix(),
                                "checksum_file_sha256": "0" * 64
                                if bad_checksum_hash
                                else checksum_sha,
                                "start": "2022-10-02T00:00:00Z",
                                "end": "2022-10-02T00:02:59.999999999Z",
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return config, monthly.name


def test_mark_supplement_fills_gap_and_monthly_wins_identical_overlap(tmp_path):
    config, monthly_name = _mark_supplement_manifest(tmp_path)

    result = normalize.normalize(config, tmp_path)

    assert result["errors"] == []
    mark = next(entry for entry in result["entries"] if entry["dataset"] == "marks")
    assert mark["complete"] is True
    assert mark["rows"] == 3
    assert mark["duplicate_count"] == 1
    assert len(mark["source_supplements"]) == 1
    rows = pq.read_table(tmp_path / mark["path"]).to_pylist()
    assert [row["open_time"] for row in rows] == [
        timestamp("2022-10-02T00:00:00Z"),
        timestamp("2022-10-02T00:01:00Z"),
        timestamp("2022-10-02T00:02:00Z"),
    ]
    assert rows[0]["source_file"] == monthly_name


def test_mark_supplement_rejects_conflicting_overlap(tmp_path):
    config, _ = _mark_supplement_manifest(tmp_path, conflicting=True)

    result = normalize.normalize(config, tmp_path)

    assert result["entries"] == []
    assert any("Conflicting mark overlap" in error for error in result["errors"])


def test_mark_supplement_rejects_hash_mismatch(tmp_path):
    config, _ = _mark_supplement_manifest(tmp_path, bad_hash=True)

    result = normalize.normalize(config, tmp_path)

    assert result["entries"] == []
    assert any("Supplement raw hash mismatch" in error for error in result["errors"])
    assert BINANCE_SPOT_HALT_SOURCE.startswith("https://www.binance.com/")


def test_mark_supplement_rejects_checksum_file_hash_mismatch(tmp_path):
    config, _ = _mark_supplement_manifest(tmp_path, bad_checksum_hash=True)

    result = normalize.normalize(config, tmp_path)

    assert result["entries"] == []
    assert any("Supplement checksum hash mismatch" in error for error in result["errors"])


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"supplement_symbol": "ETHUSDT"}, "Supplement symbol mismatch"),
        ({"supplement_market": "spot"}, "Supplement market mismatch"),
    ],
)
def test_mark_supplement_rejects_wrong_parent_identity(tmp_path, overrides, message):
    config, _ = _mark_supplement_manifest(tmp_path, **overrides)

    result = normalize.normalize(config, tmp_path)

    assert result["entries"] == []
    assert any(message in error for error in result["errors"])


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"bad_official_digest": True}, "Official supplement checksum mismatch"),
        ({"bad_checksum_name": True}, "Supplement checksum filename mismatch"),
    ],
)
def test_mark_supplement_binds_official_checksum_to_archive(tmp_path, overrides, message):
    config, _ = _mark_supplement_manifest(tmp_path, **overrides)

    result = normalize.normalize(config, tmp_path)

    assert result["entries"] == []
    assert any(message in error for error in result["errors"])


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"status": "failed"}, "Supplement status is not successful"),
        ({"dataset": "klines"}, "Supplement dataset mismatch"),
        ({"timestamp_unit": "us"}, "Supplement timestamp unit mismatch"),
        ({"start": "2022-10-01T23:59:00Z"}, "Supplement time bounds escape parent archive"),
    ],
)
def test_mark_supplement_rejects_incompatible_metadata(tmp_path, changes, message):
    config, _ = _mark_supplement_manifest(tmp_path)
    manifest_path = tmp_path / config.data_dir / "manifests/download.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["entries"][0]["supplements"][0].update(changes)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = normalize.normalize(config, tmp_path)

    assert result["entries"] == []
    assert any(message in error for error in result["errors"])


def test_malformed_mark_decimal_is_recorded_as_normalization_error(tmp_path):
    config, _ = _mark_supplement_manifest(tmp_path, malformed_mark=True)

    result = normalize.normalize(config, tmp_path)

    assert result["entries"] == []
    assert any("InvalidOperation" in error for error in result["errors"])
