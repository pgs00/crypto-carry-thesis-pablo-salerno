"""Raw minute downloads must be resumable, bounded and honestly labelled."""

import hashlib
import importlib.util
import io
import json
import zipfile
from collections import Counter

import httpx
import pytest

from crypto_carry.config import HOUR, Config, timestamp


def _module():
    name = "crypto_carry.data.minute_download"
    assert importlib.util.find_spec(name) is not None, "Minute downloader is not implemented"
    return __import__(name, fromlist=["download_minutes"])


def _config(**changes):
    return Config(
        history_start="2022-09-01T00:00:00Z",
        start="2022-09-01T00:00:00Z",
        end="2023-09-01T00:00:00Z",
        data_dir="data/minutes/2022_2023",
    ).changed(**changes)


def _transport(*, bad_checksum=False, interrupt_at=None):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        # Stable ZIP metadata: a rerun must serve the same source bytes even when
        # the test crosses the ZIP format's two-second timestamp boundary.
        archive.writestr(zipfile.ZipInfo("fixture.csv", (2024, 1, 1, 0, 0, 0)), "1,2,3\n")
    payload = buffer.getvalue()
    calls = []

    def handle(request):
        calls.append(str(request.url))
        if interrupt_at and len(calls) == interrupt_at:
            raise KeyboardInterrupt
        if request.url.path.endswith(".CHECKSUM"):
            checksum = "0" * 64 if bad_checksum else hashlib.sha256(payload).hexdigest()
            return httpx.Response(200, content=(checksum + " archive.zip\n").encode())
        if request.url.path.endswith(".zip"):
            return httpx.Response(200, content=payload)
        return httpx.Response(
            200,
            json=[
                dict(
                    symbol=request.url.params["symbol"],
                    fundingTime=int(request.url.params["startTime"]),
                    fundingRate="0.0001",
                    markPrice="",
                )
            ],
        )

    return httpx.MockTransport(handle), calls


def test_plan_contains_both_annual_windows_and_full_warmup_without_trades():
    module = _module()
    early = _config()
    late = early.changed(
        history_start="2025-09-01T00:00:00Z",
        start="2025-09-01T00:00:00Z",
        end="2026-09-01T00:00:00Z",
        data_dir="data/minutes/2025_2026",
    )
    jobs = module.minute_descriptors(early) + module.minute_descriptors(late)
    assert len(jobs) == 212
    assert Counter(job["dataset"] for job in jobs) == {
        "klines": 104,
        "marks": 52,
        "funding_calendar": 52,
        "funding": 4,
    }
    assert len({job["path"] for job in jobs}) == len(jobs)
    assert all("/trades/" not in job["source_url"] for job in jobs)
    early_funding = [job for job in jobs if job["dataset"] == "funding"][0]
    assert early_funding["start"] == timestamp(early.start) - 720 * HOUR
    assert early_funding["end"] == timestamp(early.end) - 1
    assert any("2022-08.zip" in job["path"] for job in jobs)
    assert not any("2023-09.zip" in job["path"] for job in jobs)
    spot_late = next(job for job in jobs if "/spot/" in job["path"] and "2025-09" in job["path"])
    assert spot_late["timestamp_unit"] == "us"


def test_download_checks_integrity_and_resumes_without_downloading_zip_again(tmp_path):
    module = _module()
    config = _config(end="2022-09-02T00:00:00Z")
    transport, calls = _transport()
    updates = []
    with httpx.Client(transport=transport) as client:
        result = module.download_minutes(config, tmp_path, client=client, progress=updates.append)
        first_zip_calls = sum(url.endswith(".zip") for url in calls)
        again = module.download_minutes(config, tmp_path, client=client)
    assert result["status"] == again["status"] == "download_complete"
    assert result["coverage_certified"] is False
    assert updates[-1]["verified"] == updates[-1]["total"]
    assert updates[-1]["percent"] == 100
    assert sum(url.endswith(".zip") for url in calls) == first_zip_calls
    assert all(entry["status"] == "cached" for entry in again["entries"])
    saved = json.loads((tmp_path / config.data_dir / "manifests/download.json").read_text())
    assert saved["kind"] == "minute_market_data"
    assert all("sha256" in entry for entry in saved["entries"])
    assert not (tmp_path / "data/raw").exists()


def test_bad_checksum_never_reaches_success_or_publishes_a_zip(tmp_path, monkeypatch):
    module = _module()
    monkeypatch.setattr("crypto_carry.data.download.time.sleep", lambda _: None)
    config = _config(end="2022-09-02T00:00:00Z")
    transport, _ = _transport(bad_checksum=True)
    updates = []
    with httpx.Client(transport=transport) as client:
        result = module.download_minutes(config, tmp_path, client=client, progress=updates.append)
    assert result["status"] == "incomplete"
    assert updates[-1]["percent"] < 100
    assert any(entry["status"] == "failed" for entry in result["entries"])
    assert not list(tmp_path.rglob("*.zip"))


def test_interrupt_preserves_incremental_manifest_and_finished_files(tmp_path):
    module = _module()
    config = _config(end="2022-09-02T00:00:00Z")
    transport, _ = _transport(interrupt_at=3)
    with httpx.Client(transport=transport) as client, pytest.raises(KeyboardInterrupt):
        module.download_minutes(config, tmp_path, client=client)
    saved = json.loads((tmp_path / config.data_dir / "manifests/download.json").read_text())
    assert saved["status"] == "in_progress"
    assert len(saved["entries"]) == 1
    assert saved["entries"][0]["status"] == "downloaded"
    assert len(list(tmp_path.rglob("*.zip"))) == 1


def test_refuses_old_data_directory_before_network_or_writes(tmp_path):
    module = _module()
    with pytest.raises(ValueError, match="data/minutes"):
        module.download_minutes(_config(data_dir="data"), tmp_path)
    assert not list(tmp_path.iterdir())


def test_budget_applies_to_both_windows_together(tmp_path):
    module = _module()
    from crypto_carry.data.download import DataBudgetExceeded

    other = tmp_path / "data/minutes/2025_2026/existing.bin"
    other.parent.mkdir(parents=True)
    other.write_bytes(b"x" * 100)
    with pytest.raises(DataBudgetExceeded):
        module.download_minutes(_config(data_budget_bytes=99), tmp_path)
    assert not (tmp_path / "data/minutes/2022_2023").exists()


def test_cli_preview_does_not_access_network_or_create_data(tmp_path, capsys):
    module = _module()
    path = tmp_path / "download.toml"
    path.write_text(_config().to_toml())
    assert module.main(["--root", str(tmp_path), "--config", str(path), "--plan-only"]) == 0
    plan = json.loads(capsys.readouterr().out)
    assert plan["total_items"] == 106
    assert plan["zip_archives"] == 104
    assert not (tmp_path / "data").exists()


def test_interrupted_rerun_retains_prior_api_provenance_and_remains_resumable(tmp_path):
    module = _module()
    config = _config(end="2022-09-02T00:00:00Z")
    transport, _ = _transport()
    with httpx.Client(transport=transport) as client:
        before = module.download_minutes(config, tmp_path, client=client)
    interrupted, _ = _transport(interrupt_at=1)
    with httpx.Client(transport=interrupted) as client, pytest.raises(KeyboardInterrupt):
        module.download_minutes(config, tmp_path, client=client)
    saved = json.loads((tmp_path / config.data_dir / "manifests/download.json").read_text())
    assert saved["entries"] == before["entries"]
    resumed, calls = _transport()
    with httpx.Client(transport=resumed) as client:
        after = module.download_minutes(config, tmp_path, client=client)
    assert after["status"] == "download_complete"
    assert all("/fapi/" not in call for call in calls)


def test_non_ascii_checksum_records_failure_and_continues_other_jobs(tmp_path):
    module = _module()
    transport = httpx.MockTransport(lambda request: httpx.Response(200, content=b"\xff"))
    updates = []
    with httpx.Client(transport=transport) as client:
        result = module.download_minutes(
            _config(end="2022-09-02T00:00:00Z"),
            tmp_path,
            client=client,
            progress=updates.append,
        )
    assert result["status"] == "incomplete"
    assert len(result["entries"]) == result["total_items"]
    assert all(entry["status"] == "failed" for entry in result["entries"])


def test_redownload_preserves_daily_supplement_provenance(tmp_path):
    module = _module()
    config = _config(end="2022-09-02T00:00:00Z")
    transport, _ = _transport()
    with httpx.Client(transport=transport) as client:
        original = module.download_minutes(config, tmp_path, client=client)
    parent = next(entry for entry in original["entries"] if entry["dataset"] == "marks")
    supplement = {"path": "daily-supplement.zip", "sha256": "verified-daily-source"}
    parent["supplements"] = [supplement]
    path = tmp_path / config.data_dir / "manifests/download.json"
    path.write_text(json.dumps(original))
    with httpx.Client(transport=transport) as client:
        repeated = module.download_minutes(config, tmp_path, client=client)
    replay_parent = next(entry for entry in repeated["entries"] if entry["path"] == parent["path"])
    assert replay_parent["supplements"] == [supplement]
