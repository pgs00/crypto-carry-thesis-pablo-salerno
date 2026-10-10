"""Independent clocks and raw bars distinguish carry causes without a backtest."""

import hashlib
import importlib
import importlib.util
import json

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

MINUTE = 60_000_000_000
DAY = 86_400_000_000_000


def implementation():
    name = "scripts.intraday_risk_price_quality"
    assert importlib.util.find_spec(name) is not None, "price-quality annotator is missing"
    return importlib.import_module(name)


def prices(available, close, volume=None):
    result = {"available_at": np.array(available, dtype=np.int64), "close": np.array(close)}
    if volume is not None:
        result["base_volume"] = np.array(volume)
    return result


def test_missing_expected_bar_is_carry_until_available_reopening_without_future_lookup():
    raw = prices([0, 2 * MINUTE], [100.0, 103.0], [1.0, 1.0])
    times = np.array([0, MINUTE - 1, MINUTE, 2 * MINUTE - 1, 2 * MINUTE])
    result = implementation().quality_codes(raw, times, require_volume=True)
    assert result.tolist() == [0, 0, 2, 2, 0]
    assert result.dtype == np.uint8


def test_zero_volume_does_not_refresh_spot_but_volume_is_irrelevant_for_mark():
    raw = prices([0, MINUTE, 2 * MINUTE], [100.0, 90.0, 95.0], [1.0, 0.0, 1.0])
    times = np.array([MINUTE, MINUTE + 1, 2 * MINUTE])
    quality = implementation().quality_codes
    assert quality(raw, times, require_volume=True).tolist() == [3, 3, 0]
    assert quality(raw, times, require_volume=False).tolist() == [0, 0, 0]


@pytest.mark.parametrize("invalid", [np.nan, np.inf, 0.0, -1.0])
def test_invalid_close_has_its_own_reason_even_if_volume_is_zero(invalid):
    raw = prices([0, MINUTE], [100.0, invalid], [1.0, 0.0])
    result = implementation().quality_codes(raw, np.array([MINUTE]), require_volume=True)
    assert result.tolist() == [4]


@pytest.mark.parametrize("invalid", [np.nan, -1.0])
def test_invalid_volume_is_not_described_as_zero_volume(invalid):
    raw = prices([0, MINUTE], [100.0, 99.0], [1.0, invalid])
    result = implementation().quality_codes(raw, np.array([MINUTE]), require_volume=True)
    assert result.tolist() == [5]


def test_unavailable_reference_is_not_fabricated_from_a_future_or_invalid_bar():
    raw = prices([MINUTE, 2 * MINUTE], [0.0, 100.0], [1.0, 1.0])
    times = np.array([0, MINUTE, 2 * MINUTE - 1, 2 * MINUTE])
    assert implementation().quality_codes(raw, times, require_volume=True).tolist() == [1, 1, 1, 0]
    empty = prices([], [], [])
    assert implementation().quality_codes(empty, times, require_volume=True).tolist() == [1] * 4


def test_original_daily_timestamp_uses_last_available_minute_not_next_midnight():
    raw = prices([DAY - MINUTE, DAY], [100.0, 90.0], [1.0, 0.0])
    result = implementation().quality_codes(raw, np.array([DAY - 1, DAY]), require_volume=True)
    assert result.tolist() == [0, 3]


@pytest.mark.parametrize("available", [[MINUTE, 0], [0, 0], [0, MINUTE + 1]])
def test_ambiguous_or_nonminute_source_clock_fails_instead_of_inventing_a_reason(available):
    raw = prices(available, [100.0, 101.0], [1.0, 1.0])
    with pytest.raises(ValueError, match="availability"):
        implementation().quality_codes(raw, np.array([MINUTE]), require_volume=True)


def fixture_package(tmp_path):
    package, series_root, data_root = (tmp_path / name for name in ("package", "series", "data"))
    for folder in (package, series_root, data_root):
        folder.mkdir()
    base = 1_677_628_800_000_000_000  # 2023-03-01 00:00 UTC.
    entries = []
    for symbol in ("BTCUSDT", "ETHUSDT"):
        for label in ("spot", "mark", "futures"):
            raw = {
                "available_at": [base + MINUTE, base + 2 * MINUTE],
                "open_time": [base, base + MINUTE],
                "close": ["100", "99"],
            }
            if label == "mark":
                raw["close_time"] = [base + MINUTE - 1_000_000, base + 2 * MINUTE - 1_000_000]
            else:
                raw["end_time"] = raw["available_at"]
                raw["base_volume"] = ["1", "0" if symbol == "BTCUSDT" and label == "spot" else "1"]
            path = data_root / f"{symbol}_{label}.parquet"
            pq.write_table(pa.table(raw), path)
            entries.append(
                {
                    "symbol": symbol,
                    "market": "spot" if label == "spot" else "futures",
                    "dataset": "marks" if label == "mark" else "minute_bars",
                    "date": "2023-03",
                    "path": path.name,
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                }
            )
    manifest = (
        data_root
        / "data/minutes/2022_2026_continuous/derived_marks/futures_scaled/manifests/processed.json"
    )
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({"entries": entries}), encoding="utf-8")
    sources = {
        "manifest_path": str(manifest),
        "manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
        "entries": [dict(entry, source_id=i) for i, entry in enumerate(entries)],
    }
    (package / "fuentes_precios.json").write_text(json.dumps(sources), encoding="utf-8")
    series_entries = []
    for i in range(4):
        times = [base, base + MINUTE, base + MINUTE, base + 2 * MINUTE]
        if i == 1:
            times = [base, base + MINUTE + 1, base + 2 * MINUTE]
        path = series_root / f"run_{i}" / "2023-03.parquet"
        path.parent.mkdir()
        pq.write_table(pa.table({"time_ns": times}), path)
        series_entries.append(
            {
                "run_id": f"run_{i}",
                "path": path.relative_to(series_root).as_posix(),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "rows": len(times),
                "start_ns": base,
                "end_exclusive_ns": base + 3 * MINUTE,
            }
        )
    (package / "series_locales.json").write_text(
        json.dumps({"entries": series_entries}), encoding="utf-8"
    )
    return package, series_root, data_root


def test_shared_annotation_covers_all_four_portfolios_and_duplicate_phases_without_mutation(
    tmp_path,
):
    package, series_root, data_root = fixture_package(tmp_path)
    before = {
        p: p.read_bytes()
        for root in (package, series_root, data_root)
        for p in root.rglob("*")
        if p.is_file()
    }
    record = implementation().annotate_package(package, series_root, data_root)
    table = pq.ParquetFile(package / "evidencia/calidad_precios.parquet").read()
    assert table.num_rows == 4
    assert table["BTCUSDT_spot_reason_code"].to_pylist() == [1, 0, 0, 3]
    assert table["BTCUSDT_mark_reason_code"].to_pylist() == [1, 0, 0, 0]
    assert len(record["coverage"]) == 4
    assert sum(row["matched_observations"] for row in record["coverage"]) == 15
    assert all(row["missing_observations"] == 0 for row in record["coverage"])
    assert all(path.read_bytes() == data for path, data in before.items())


def test_changed_price_partition_is_rejected_before_annotation_is_published(tmp_path):
    package, series_root, data_root = fixture_package(tmp_path)
    with (data_root / "BTCUSDT_spot.parquet").open("ab") as stream:
        stream.write(b"changed")
    with pytest.raises(ValueError, match="hash"):
        implementation().annotate_package(package, series_root, data_root)
    assert not (package / "evidencia/calidad_precios.parquet").exists()
