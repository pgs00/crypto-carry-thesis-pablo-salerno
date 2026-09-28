from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from test_data import _write_complete_sample_manifest

from crypto_carry.config import DAY, HOUR, SECOND, Config, iso, timestamp
from crypto_carry.data.replay import iter_records
from crypto_carry.data.validate import validate_data


def _case(root: Path):
    config = Config()
    _write_complete_sample_manifest(root, config)
    manifest = json.loads((root / "data/manifests/processed.json").read_text(encoding="utf-8"))
    return config, manifest


def _save(root: Path, manifest: dict):
    (root / "data/manifests/processed.json").write_text(json.dumps(manifest), encoding="utf-8")


def _entry(manifest: dict, dataset: str):
    return next(
        entry
        for entry in manifest["entries"]
        if entry["dataset"] == dataset and entry["symbol"] == "BTCUSDT"
    )


def _rows(root: Path, entry: dict):
    return pq.ParquetFile(root / entry["path"]).read().to_pylist()


def _write_rows(root: Path, entry: dict, rows: list[dict]):
    path = root / entry["path"]
    pq.write_table(pa.Table.from_pylist(rows), path)
    field = {"trades": "event_time", "marks": "available_at", "funding": "funding_time"}[
        entry["dataset"]
    ]
    entry.update(
        sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        rows=len(rows),
        start=min(row[field] for row in rows),
        end=max(row[field] for row in rows),
    )


@pytest.mark.parametrize("scope", ["sample", "full"])
@pytest.mark.parametrize("dataset", ["trades", "marks", "funding"])
def test_unrelated_partitions_do_not_block_the_requested_range(tmp_path, scope, dataset):
    config, manifest = _case(tmp_path)
    config = config.changed(start=config.sample_start, end=config.sample_end)
    selected = _entry(manifest, dataset)
    start = timestamp(config.sample_start)
    end = timestamp(config.sample_end)
    if dataset == "trades":
        # Replay consumes the nearest prior trade; an older file is irrelevant.
        antecedent = dict(selected, path="data/processed/trade-antecedent.parquet")
        rows = _rows(tmp_path, selected)
        prior = dict(rows[0], trade_id="0", event_time=start - SECOND, available_at=start - SECOND)
        _write_rows(tmp_path, antecedent, [prior])
        antecedent.update(date=iso(start - SECOND)[:10], first_trade_id="0", last_trade_id="0")
        selected.update(first_trade_id="1", last_trade_id="1")
        manifest["entries"].append(antecedent)
    elif dataset == "marks":
        antecedent = dict(selected, path="data/processed/mark-antecedent.parquet")
        prior = dict(
            _rows(tmp_path, selected)[0],
            open_time=start - 120 * SECOND,
            close_time=start - 60 * SECOND - 1,
            available_at=start - 60 * SECOND,
        )
        _write_rows(tmp_path, antecedent, [prior])
        antecedent["date"] = iso(start - SECOND)[:10]
        manifest["entries"].append(antecedent)
    for time_ns in (start - 500 * DAY, end + 500 * DAY):
        manifest["entries"].append(
            dict(
                selected,
                path=f"data/processed/unrelated-{time_ns}.parquet",
                date=iso(time_ns)[:10],
                start=time_ns,
                end=time_ns,
                complete=False,
                conflict_count=1,
                trade_id_continuous=False,
                minute_coverage_complete=False,
                funding_calendar_complete=False,
                settlement_marks_complete=False,
            )
        )
    _save(tmp_path, manifest)

    result = validate_data(config, tmp_path, scope)

    assert result["status"] == "complete", result["issues"]
    assert not any("unrelated" in check for row in result["coverage"] for check in row["checks"])


def test_full_history_funding_flags_are_rechecked_only_for_relevant_rows(tmp_path):
    config, manifest = _case(tmp_path)
    entry = _entry(manifest, "funding")
    rows = _rows(tmp_path, entry)
    earlier = dict(
        rows[0],
        funding_time=timestamp("2020-09-01T00:00:00Z"),
        available_at=timestamp("2020-09-01T00:01:00Z"),
        settlement_mark_price=None,
        interval_verified=False,
    )
    later = dict(
        earlier,
        funding_time=timestamp(config.sample_end) + 8 * HOUR,
        available_at=timestamp(config.sample_end) + 8 * HOUR + 60 * SECOND,
    )
    _write_rows(tmp_path, entry, [earlier, *rows, later])
    entry.update(funding_calendar_complete=False, settlement_marks_complete=False)
    _save(tmp_path, manifest)

    result = validate_data(config, tmp_path)

    assert result["status"] == "complete", result["issues"]


def test_overlapping_funding_file_does_not_hide_a_newer_antecedent_partition(tmp_path):
    config, manifest = _case(tmp_path)
    entry = _entry(manifest, "funding")
    rows = _rows(tmp_path, entry)
    antecedent = dict(entry, path="data/processed/funding-antecedent.parquet")
    _write_rows(tmp_path, antecedent, [rows[0]])
    earlier = dict(
        rows[0],
        funding_time=rows[0]["funding_time"] - 8 * HOUR,
        available_at=rows[0]["available_at"] - 8 * HOUR,
    )
    _write_rows(tmp_path, entry, [earlier, *rows[1:]])
    manifest["entries"].append(antecedent)
    _save(tmp_path, manifest)

    result = validate_data(config, tmp_path)

    assert result["status"] == "complete", result["issues"]


@pytest.mark.parametrize(
    ("defect", "issue"),
    [
        ("mark", "funding settlement mark missing"),
        ("warmup_mark", "funding settlement mark missing"),
        ("unverified", "funding calendar unverified"),
        ("rate", "funding calendar unverified"),
        ("interior_gap", "funding calendar unverified"),
        ("tail_gap", "funding calendar unverified"),
        ("warmup", "funding warmup or antecedent missing"),
    ],
)
def test_complete_flags_do_not_hide_funding_defects_in_scope(tmp_path, defect, issue):
    config, manifest = _case(tmp_path)
    entry = _entry(manifest, "funding")
    rows = _rows(tmp_path, entry)
    if defect == "mark":
        rows[-1]["settlement_mark_price"] = None
    elif defect == "warmup_mark":
        rows[0]["settlement_mark_price"] = None
    elif defect == "unverified":
        rows[-1]["interval_verified"] = False
    elif defect == "rate":
        rows[-1]["funding_rate"] = "0.25"
    elif defect == "interior_gap":
        rows.pop(3)
    elif defect == "tail_gap":
        rows.pop()
    else:
        rows = rows[2:]
    _write_rows(tmp_path, entry, rows)
    if defect == "warmup":
        # Stale metadata must not invent observations that are absent from the file.
        entry["start"] = timestamp(config.sample_start) - 400 * HOUR
    _save(tmp_path, manifest)

    result = validate_data(config, tmp_path)

    assert result["status"] == "incomplete_data"
    assert any(issue in item for item in result["issues"]), result["issues"]


@pytest.mark.parametrize("defect", ["missing", "hash", "missing_month"])
def test_funding_requires_verified_independent_calendar_for_requested_months(tmp_path, defect):
    config, _manifest = _case(tmp_path)
    path = tmp_path / "data/manifests/download.json"
    calendar = json.loads(path.read_text(encoding="utf-8"))
    january = next(
        entry
        for entry in calendar["entries"]
        if entry["symbol"] == "BTCUSDT" and entry["start"] == "2024-01-01T00:00:00Z"
    )
    if defect == "missing":
        path.unlink()
    elif defect == "hash":
        (tmp_path / january["path"]).write_bytes(b"corrupt calendar")
    else:
        calendar["entries"].remove(january)
        path.write_text(json.dumps(calendar), encoding="utf-8")

    result = validate_data(config, tmp_path)

    assert result["status"] == "incomplete_data"
    assert any("funding calendar" in item for item in result["issues"]), result["issues"]


@pytest.mark.parametrize("missing_index", [0, 600])
def test_requested_mark_minute_and_initial_closed_mark_remain_required(tmp_path, missing_index):
    config, manifest = _case(tmp_path)
    entry = _entry(manifest, "marks")
    rows = _rows(tmp_path, entry)
    rows.pop(missing_index)
    _write_rows(tmp_path, entry, rows)
    _save(tmp_path, manifest)

    result = validate_data(config, tmp_path)

    assert result["status"] == "incomplete_data"
    assert any(
        "missing closed mark minute or initial antecedent" in item for item in result["issues"]
    )


def test_previous_day_mark_partition_can_supply_the_initial_closed_minute(tmp_path):
    config, manifest = _case(tmp_path)
    entry = _entry(manifest, "marks")
    rows = _rows(tmp_path, entry)
    antecedent = dict(entry, path="data/processed/mark-antecedent.parquet", date="2023-12-31")
    _write_rows(tmp_path, antecedent, [rows[0]])
    _write_rows(tmp_path, entry, rows[1:])
    manifest["entries"].append(antecedent)
    _save(tmp_path, manifest)

    result = validate_data(config, tmp_path)

    assert result["status"] == "complete", result["issues"]


def test_unresolved_trade_ids_in_the_requested_range_remain_blocking(tmp_path):
    config, manifest = _case(tmp_path)
    _entry(manifest, "trades")["trade_id_continuous"] = False
    _save(tmp_path, manifest)

    result = validate_data(config, tmp_path)

    assert result["status"] == "incomplete_data"
    assert any("unresolved trade-id discontinuity" in item for item in result["issues"])


def test_funding_availability_cannot_precede_the_normalized_delay(tmp_path):
    config, manifest = _case(tmp_path)
    entry = _entry(manifest, "funding")
    rows = _rows(tmp_path, entry)
    rows[-1]["available_at"] = rows[-1]["funding_time"]
    _write_rows(tmp_path, entry, rows)
    _save(tmp_path, manifest)

    result = validate_data(config, tmp_path)

    assert result["status"] == "incomplete_data"
    assert any("funding availability mismatch" in item for item in result["issues"])


def test_missing_mark_antecedent_consumed_by_replay_remains_blocking(tmp_path):
    config, manifest = _case(tmp_path)
    start = timestamp(config.sample_start)
    manifest["entries"].append(
        dict(
            _entry(manifest, "marks"),
            path="data/processed/missing-mark-antecedent.parquet",
            start=start - 60 * SECOND,
            end=start - 60 * SECOND,
            date="2023-12-31",
        )
    )
    _save(tmp_path, manifest)

    result = validate_data(config, tmp_path)

    assert result["status"] == "incomplete_data"
    assert any("missing-mark-antecedent.parquet" in item for item in result["issues"])


def test_unscoped_normalization_errors_remain_blocking(tmp_path):
    config, manifest = _case(tmp_path)
    manifest["errors"] = ["source.zip: ValueError: unknown provenance"]
    _save(tmp_path, manifest)

    result = validate_data(config, tmp_path)

    assert result["status"] == "incomplete_data"
    assert any("normalization error" in item for item in result["issues"])


@pytest.mark.parametrize("offset_days", [-500, 500])
def test_invalid_partition_bounds_cannot_be_hidden_outside_requested_range(tmp_path, offset_days):
    config, manifest = _case(tmp_path)
    start = timestamp(config.sample_start)
    end = timestamp(config.sample_end)
    lower = start - (config.window_hours + 24) * HOUR
    manifest["entries"].append(
        dict(
            _entry(manifest, "funding"),
            path="data/processed/invalid-bounds.parquet",
            start=lower + offset_days * DAY,
            end=lower + (offset_days - 1) * DAY,
        )
    )
    _save(tmp_path, manifest)
    with pytest.raises(ValueError, match="Invalid partition bounds"):
        list(iter_records(tmp_path, start, end, config.window_hours + 24))

    result = validate_data(config, tmp_path)

    assert result["status"] == "incomplete_data"
    assert any("invalid partition bounds" in item for item in result["issues"])
