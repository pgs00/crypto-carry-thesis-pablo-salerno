"""Prepared-data checks and a ten-minute replay through the public CLI."""

import hashlib
import json
from dataclasses import asdict
from decimal import Decimal

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from conftest import warmup
from test_next_minute_vwap import bars, config

from crypto_carry.cli import main
from crypto_carry.config import HOUR, timestamp
from crypto_carry.events import event_time
from crypto_carry.models import Funding, Mark


@pytest.fixture
def prepared(tmp_path, start):
    settings = config(start, data_dir="data", signal_price_model="closed_minute")
    (tmp_path / "config.toml").write_text(settings.to_toml())
    grouped = {}
    for record in warmup(start) + bars(start):
        dataset = ("funding" if isinstance(record, Funding) else
                   "marks" if isinstance(record, Mark) else "minute_bars")
        key = (dataset, record.symbol, getattr(record, "market", "futures"))
        grouped.setdefault(key, []).append(record)
    entries, coverage = [], []
    for (dataset, symbol, market), records in grouped.items():
        name = f"{dataset}_{symbol}_{market}.parquet"
        rows = [{k: str(v) if isinstance(v, Decimal) else v
                 for k, v in asdict(record).items()} for record in records]
        pq.write_table(pa.Table.from_pylist(rows), tmp_path / name)
        entry = dict(dataset=dataset, symbol=symbol, market=market, path=name,
                     start=min(map(event_time, records)), end=max(map(event_time, records)),
                     rows=len(rows), complete=True, conflict_count=0,
                     sha256=hashlib.sha256((tmp_path / name).read_bytes()).hexdigest())
        entries.append(entry)
        coverage.append(dict(
            dataset=dataset, symbol=symbol, market=market, status="complete",
            expected_start=start - (settings.window_hours + 24) * HOUR
            if dataset == "funding" else start,
            expected_end=timestamp(settings.end),
            checks=[f"sha256:{name}", f"schema:{name}"],
        ))
    directory = tmp_path / "data/manifests"
    directory.mkdir(parents=True)
    manifest = dict(kind="minute_market_data", entries=entries, errors=[])
    quality = dict(status="complete", issues=[], scope="full", start=start,
                   end=timestamp(settings.end), analysis_mode=settings.analysis_mode,
                   funding_warmup_start=start - (settings.window_hours + 24) * HOUR,
                   coverage=coverage)
    (directory / "processed.json").write_text(json.dumps(manifest))
    quality["processed_manifest_sha256"] = hashlib.sha256(
        (directory / "processed.json").read_bytes()).hexdigest()
    (directory / "coverage.json").write_text(json.dumps(quality))
    return tmp_path, settings, manifest, quality


def replay(root):
    return main(["--root", str(root), "backtest", "--config", "config.toml",
                 "--output", str(root / "runs")])


def test_prepared_replay_runs_both_strategies_and_verifies_artifacts(prepared, capsys):
    root, _, _, _ = prepared
    assert replay(root) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["valid"] and result["status"] == "complete"
    run = next((root / "runs").glob("run_*"))
    fills = pq.read_table(run / "fills.parquet").to_pylist()
    assert {row["strategy"] for row in fills} == {"conditional", "permanent"}
    assert len(fills) == 8


@pytest.mark.parametrize("dataset", ["minute_bars", "funding", "marks"])
def test_replay_rejects_changed_prepared_partition(prepared, capsys, dataset):
    root, _, manifest, _ = prepared
    name = next(entry["path"] for entry in manifest["entries"] if entry["dataset"] == dataset)
    rows = pq.read_table(root / name).to_pylist()
    field = "funding_rate" if dataset == "funding" else "close"
    rows[0][field] = str(Decimal(rows[0][field]) * Decimal("1.001"))
    pq.write_table(pa.Table.from_pylist(rows), root / name)
    assert replay(root) == 1
    assert "hash mismatch" in capsys.readouterr().err
    assert not (root / "runs").exists()


def test_replay_rejects_coverage_for_shorter_forecast_warmup(prepared, capsys):
    root, settings, _, _ = prepared
    (root / "config.toml").write_text(settings.changed(window_hours=672).to_toml())
    assert replay(root) == 1
    assert "warmup" in capsys.readouterr().err
    assert not (root / "runs").exists()


@pytest.mark.parametrize("change", [
    "sample", "missing_group", "missing_check", "missing_warmup", "missing_binding",
])
def test_replay_rejects_inapplicable_coverage(prepared, capsys, change):
    root, _, _, quality = prepared
    if change == "sample":
        quality["scope"] = "sample"
    elif change == "missing_group":
        quality["coverage"].pop()
    elif change == "missing_check":
        quality["coverage"][0]["checks"] = []
    elif change == "missing_warmup":
        quality.pop("funding_warmup_start")
    else:
        quality.pop("processed_manifest_sha256")
    (root / "data/manifests/coverage.json").write_text(json.dumps(quality))
    assert replay(root) == 1
    assert "coverage" in capsys.readouterr().err.lower()
    assert not (root / "runs").exists()


def test_replay_rejects_regenerated_manifest_with_old_coverage(prepared, capsys):
    root, _, manifest, _ = prepared
    entry = manifest["entries"][0]
    path = root / entry["path"]
    rows = pq.read_table(path).to_pylist()
    rows[0]["funding_rate"] = "0.002"
    pq.write_table(pa.Table.from_pylist(rows), path)
    entry["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    (root / "data/manifests/processed.json").write_text(json.dumps(manifest))
    assert replay(root) == 1
    assert "coverage" in capsys.readouterr().err.lower()
    assert not (root / "runs").exists()


def test_replay_rejects_removed_partition_even_if_manifest_is_updated(prepared, capsys):
    root, _, manifest, _ = prepared
    removed = manifest["entries"].pop()
    (root / removed["path"]).unlink()
    (root / "data/manifests/processed.json").write_text(json.dumps(manifest))
    assert replay(root) == 1
    assert "coverage" in capsys.readouterr().err.lower()
    assert not (root / "runs").exists()
