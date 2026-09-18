import hashlib
import json

import pytest

from crypto_carry.cli import main
from crypto_carry.config import Config, timestamp
from crypto_carry.data.rules import synthetic_rules


def _setup(tmp_path):
    config = Config(
        history_start="2024-01-01T00:00:00Z",
        start="2024-01-01T00:00:00Z",
        end="2024-01-02T00:00:00Z",
    )
    config_file = tmp_path / "config.toml"
    config_file.write_text(config.to_toml(), encoding="utf-8")
    return config, config_file


def _download_fixture(root):
    entries = []
    for symbol in ("BTCUSDT", "ETHUSDT"):
        paths = [
            f"raw/spot/trades/{symbol}/{symbol}-trades-2024-01-01.zip",
            f"raw/futures/trades/{symbol}/{symbol}-trades-2024-01-01.zip",
            f"raw/futures/markPriceKlines/{symbol}/{symbol}-1m-2023-12-31.zip",
            f"raw/futures/markPriceKlines/{symbol}/{symbol}-1m-2024-01-01.zip",
            f"raw/futures/fundingRate/{symbol}/{symbol}-fundingRate-2023-12.zip",
            f"raw/futures/fundingRate/{symbol}/{symbol}-fundingRate-2024-01.zip",
            f"raw/futures/funding_api/{symbol}/funding-1702684800000-1704153599999.json",
        ]
        for name in paths:
            path = root / "data" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            # Deliberately not a valid ZIP: preflight is metadata-only, not certification.
            path.write_bytes(b"raw")
            entry = {
                "path": "data/" + name,
                "status": "downloaded",
                "bytes": 3,
                "sha256": hashlib.sha256(b"raw").hexdigest(),
            }
            if path.suffix == ".zip":
                checksum = path.with_suffix(".zip.CHECKSUM")
                checksum.write_text("fixture checksum", encoding="utf-8")
                entry["checksum_path"] = entry["path"] + ".CHECKSUM"
                entry["checksum_file_sha256"] = hashlib.sha256(checksum.read_bytes()).hexdigest()
            entries.append(entry)
    manifest = {
        "scope": "full",
        "requested_start": 1704067200000000000,
        "requested_end": 1704153600000000000,
        "funding_request_start": 1702684800000000000,
        "entries": entries,
    }
    path = root / "data/manifests/download.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path, manifest


def _rules_fixture(root, config, *, gap=False, synthetic=False):
    records = synthetic_rules(config).records
    for record in records:
        record["evidence_status"] = "synthetic" if synthetic else "verified"
        record["source_url"] = "https://example.invalid/controlled-test-fixture"
        record["valid_from"] = timestamp(config.start)
        record["valid_to"] = timestamp(config.end)
    if gap:
        second = dict(records[0])
        records[0]["valid_to"] = timestamp("2024-01-01T01:00:00Z")
        second["valid_from"] = timestamp("2024-01-01T02:00:00Z")
        records.append(second)
    path = root / config.rules_file
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"records": records}), encoding="utf-8")


def _run(root, config_file, capsys):
    before = {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    code = main(["--root", str(root), "preflight", "--config", str(config_file)])
    output = json.loads(capsys.readouterr().out)
    after = {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    assert before == after
    assert output["historical_certified"] is False
    assert output["integrity_verified"] is False
    return code, output


def test_preflight_missing_inputs_reports_blockers_without_creating_files(tmp_path, capsys):
    _, config_file = _setup(tmp_path)
    code, result = _run(tmp_path, config_file, capsys)
    assert code == 2
    assert result["download"]["ready"] is False
    assert result["rules"]["ready"] is False


def test_preflight_complete_metadata_only_allows_validation_not_certification(tmp_path, capsys):
    config, config_file = _setup(tmp_path)
    _download_fixture(tmp_path)
    _rules_fixture(tmp_path, config)
    code, result = _run(tmp_path, config_file, capsys)
    assert code == 0
    assert result["status"] == "ready_for_validation"
    assert result["download"]["expected_files"] == 14


@pytest.mark.parametrize(
    "mutation", ["missing_entry", "failed", "truncated", "scope", "range", "duplicate", "checksum"]
)
def test_preflight_blocks_incomplete_or_stale_download(tmp_path, capsys, mutation):
    config, config_file = _setup(tmp_path)
    path, manifest = _download_fixture(tmp_path)
    _rules_fixture(tmp_path, config)
    entry = manifest["entries"][0]
    if mutation == "missing_entry":
        manifest["entries"].pop(0)
    elif mutation == "failed":
        entry["status"] = "failed"
    elif mutation == "truncated":
        (tmp_path / entry["path"]).write_bytes(b"r")
    elif mutation == "scope":
        manifest["scope"] = "sample"
    elif mutation == "range":
        manifest["requested_end"] -= 1
    elif mutation == "duplicate":
        manifest["entries"].append(dict(entry))
    elif mutation == "checksum":
        (tmp_path / entry["checksum_path"]).unlink()
    path.write_text(json.dumps(manifest), encoding="utf-8")
    code, result = _run(tmp_path, config_file, capsys)
    assert code == 2
    assert result["download"]["ready"] is False


@pytest.mark.parametrize("kind", ["gap", "synthetic", "empty"])
def test_preflight_requires_historical_rules_for_entire_evaluation(tmp_path, capsys, kind):
    config, config_file = _setup(tmp_path)
    _download_fixture(tmp_path)
    _rules_fixture(tmp_path, config, gap=kind == "gap", synthetic=kind == "synthetic")
    if kind == "empty":
        (tmp_path / config.rules_file).write_text('{"records": []}', encoding="utf-8")
    code, result = _run(tmp_path, config_file, capsys)
    assert code == 2
    assert result["download"]["ready"] is True
    assert result["rules"]["ready"] is False


@pytest.mark.parametrize("corruption", ["record", "decimal"])
def test_preflight_reports_malformed_rule_record_without_crashing(tmp_path, capsys, corruption):
    config, config_file = _setup(tmp_path)
    _download_fixture(tmp_path)
    _rules_fixture(tmp_path, config)
    path = tmp_path / config.rules_file
    payload = json.loads(path.read_text(encoding="utf-8"))
    if corruption == "record":
        payload["records"] = [1]
    else:
        payload["records"][0]["values"]["step"] = "bad"
    path.write_text(json.dumps(payload), encoding="utf-8")
    code, result = _run(tmp_path, config_file, capsys)
    assert code == 2
    assert result["rules"]["ready"] is False


def test_preflight_keeps_archive_day_included_by_fractional_end(tmp_path, capsys):
    config, config_file = _setup(tmp_path)
    config = config.changed(end="2024-01-02T00:00:00.500Z")
    config_file.write_text(config.to_toml(), encoding="utf-8")
    path, manifest = _download_fixture(tmp_path)
    _rules_fixture(tmp_path, config)
    manifest["requested_end"] = 1704153600500000000
    for entry in manifest["entries"]:
        if "funding_api/" in entry["path"]:
            old = tmp_path / entry["path"]
            entry["path"] = entry["path"].replace("1704153599999", "1704153600499")
            old.rename(tmp_path / entry["path"])
    path.write_text(json.dumps(manifest), encoding="utf-8")
    code, result = _run(tmp_path, config_file, capsys)
    assert code == 2  # Six daily ZIPs for January 2 are absent.
    assert result["download"]["expected_files"] == 20


@pytest.mark.parametrize("data_dir", ["./data", "data/", "data\\rawdata"])
def test_preflight_accepts_downloader_normalized_checksum_paths(tmp_path, capsys, data_dir):
    config, config_file = _setup(tmp_path)
    config = config.changed(data_dir=data_dir)
    config_file.write_text(config.to_toml(), encoding="utf-8")
    path, manifest = _download_fixture(tmp_path)
    _rules_fixture(tmp_path, config)
    original_files = []
    for entry in manifest["entries"]:
        source = tmp_path / entry["path"]
        entry["path"] = f"{data_dir}/{entry['path'][5:]}"
        target = tmp_path / entry["path"]
        original_files.append((source, target, source.read_bytes()))
        if "checksum_path" in entry:
            checksum_bytes = (tmp_path / entry["checksum_path"]).read_bytes()
            checksum = target.with_suffix(".zip.CHECKSUM")
            original_files.append((tmp_path / entry["checksum_path"], checksum, checksum_bytes))
            entry["checksum_path"] = checksum.relative_to(tmp_path).as_posix()
    for _, target, content in original_files:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    manifest_path = tmp_path / data_dir / "manifests/download.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    code, result = _run(tmp_path, config_file, capsys)
    assert code == 0
    assert result["download"]["ready"] is True
