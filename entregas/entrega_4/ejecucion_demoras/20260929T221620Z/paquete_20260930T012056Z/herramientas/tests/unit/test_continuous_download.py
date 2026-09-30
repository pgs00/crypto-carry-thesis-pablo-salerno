"""A longer acquisition must preserve the verified annual source archives."""

import hashlib
import importlib.util
import io
import json
import zipfile
from pathlib import Path

import httpx
import pytest

from crypto_carry.config import Config
from crypto_carry.data.minute_download import download_minutes, minute_descriptors

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/download_continuous.py"


@pytest.fixture
def launcher():
    assert SCRIPT.is_file(), "Continuous download launcher is not implemented"
    spec = importlib.util.spec_from_file_location("continuous_download", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def config():
    return Config(
        history_start="2022-01-01T00:00:00Z",
        start="2022-01-01T00:00:00Z",
        end="2022-01-02T00:00:00Z",
        data_dir="data/minutes/2022_2026_continuous",
    )


def _archive(root, entry):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(zipfile.ZipInfo("fixture.csv", (2022, 1, 1, 0, 0, 0)), "1,2,3\n")
    content = buffer.getvalue()
    sha = hashlib.sha256(content).hexdigest()
    path = root / entry["path"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    checksum = (sha + "  " + path.name + "\n").encode()
    checksum_path = path.with_suffix(".zip.CHECKSUM")
    checksum_path.write_bytes(checksum)
    return dict(
        entry,
        status="downloaded",
        errors=[],
        sha256=sha,
        bytes=len(content),
        checksum_path=checksum_path.relative_to(root).as_posix(),
        checksum_file_sha256=hashlib.sha256(checksum).hexdigest(),
        checksum_url=entry["source_url"] + ".CHECKSUM",
        retrieved_at="2026-09-19T00:00:00+00:00",
    )


@pytest.fixture
def sources(tmp_path, config):
    old_config = config.changed(data_dir="data/minutes/2022_2023")
    job = next(job for job in minute_descriptors(old_config) if job["dataset"] == "marks")
    entry = _archive(tmp_path, job)
    supplement = dict(
        job,
        path=str(Path(job["path"]).parent / "daily/BTCUSDT-1m-2021-12-02.zip"),
        source_url=job["source_url"]
        .replace("/monthly/", "/daily/")
        .replace("2021-12.zip", "2021-12-02.zip"),
    )
    entry["supplements"] = [_archive(tmp_path, supplement)]
    funding = next(job for job in minute_descriptors(old_config) if job["dataset"] == "funding")
    manifest = tmp_path / old_config.data_dir / "manifests/download.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        json.dumps({"kind": "minute_market_data", "entries": [entry, funding]}), encoding="utf-8"
    )
    return entry, manifest


def test_reuses_verified_archives_and_daily_repairs_without_changing_originals(
    launcher, tmp_path, config, sources
):
    _, source_manifest = sources
    originals = {p: p.read_bytes() for p in source_manifest.parent.parent.rglob("*") if p.is_file()}
    copied = launcher.prepare_cache(config, tmp_path)
    assert copied == 1
    target = tmp_path / config.data_dir / "manifests/download.json"
    entries = json.loads(target.read_text(encoding="utf-8"))["entries"]
    assert len(entries) == 1  # Narrow annual funding API snapshots are not reused.
    entry = entries[0]
    for archive in (entry, *entry["supplements"]):
        assert archive["path"].startswith(config.data_dir + "/")
        assert archive["checksum_path"].startswith(config.data_dir + "/")
        assert (
            hashlib.sha256((tmp_path / archive["path"]).read_bytes()).hexdigest()
            == archive["sha256"]
        )
    assert all(path.read_bytes() == content for path, content in originals.items())


def test_rejects_damaged_cache_before_copying_it(launcher, tmp_path, config, sources):
    entry, _ = sources
    (tmp_path / entry["path"]).write_bytes(b"damaged archive")
    with pytest.raises(ValueError, match="SHA-256"):
        launcher.prepare_cache(config, tmp_path)
    assert not list((tmp_path / config.data_dir).rglob("*.zip"))


def test_resume_preserves_new_funding_provenance(launcher, tmp_path, config, sources):
    launcher.prepare_cache(config, tmp_path)
    path = tmp_path / config.data_dir / "manifests/download.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    funding = dict(
        next(job for job in minute_descriptors(config) if job["dataset"] == "funding"),
        status="cached",
        sha256="a" * 64,
        rows=5000,
        retrieved_at="2026-09-19T01:23:45+00:00",
    )
    manifest["entries"].append(funding)
    path.write_text(json.dumps(manifest), encoding="utf-8")
    assert launcher.prepare_cache(config, tmp_path) == 0
    resumed = json.loads(path.read_text(encoding="utf-8"))
    assert funding in resumed["entries"]
    assert resumed["entries"][0]["supplements"] == manifest["entries"][0]["supplements"]


def test_refuses_different_period_without_touching_cached_sources(
    launcher, tmp_path, config, sources
):
    launcher.prepare_cache(config, tmp_path)
    path = tmp_path / config.data_dir / "manifests/download.json"
    before = path.read_bytes()
    with pytest.raises(ValueError, match="different request"):
        launcher.prepare_cache(config.changed(end="2022-02-01T00:00:00Z"), tmp_path)
    assert path.read_bytes() == before


def test_plan_only_does_not_create_data_or_call_network(
    launcher, tmp_path, config, capsys, monkeypatch
):
    def unexpected_call(*args, **kwargs):
        pytest.fail("Planning must not invoke downloads")

    monkeypatch.setattr(launcher, "download_minutes", unexpected_call)
    config_path = tmp_path / "config.toml"
    config_path.write_text(config.to_toml(), encoding="utf-8")
    assert (
        launcher.main(["--root", str(tmp_path), "--config", str(config_path), "--plan-only"]) == 0
    )
    output = capsys.readouterr().out
    assert "16 ZIP" in output
    assert "2 consultas" in output
    assert not (tmp_path / "data").exists()


def test_progress_counts_failed_items_as_pending(launcher, capsys):
    launcher.show_progress(
        dict(
            verified=7,
            attempted=8,
            total=10,
            entry=dict(
                status="failed", market="spot", symbol="BTCUSDT", path="file.zip", errors=["bad"]
            ),
        )
    )
    output = capsys.readouterr().out
    assert "[7/10]" in output
    assert "70.00%" in output
    assert "faltan 3" in output
    assert "ERROR: bad" in output


def test_command_downloads_only_missing_zips_and_resumes_to_completion(
    launcher, tmp_path, config, sources, monkeypatch, capsys
):
    entry, source_manifest = sources
    original_manifest = source_manifest.read_bytes()
    content = (tmp_path / entry["path"]).read_bytes()
    calls = []

    def handle(request):
        calls.append(str(request.url))
        if request.url.path.endswith(".CHECKSUM"):
            name = request.url.path.rsplit("/", 1)[-1].removesuffix(".CHECKSUM")
            checksum = f"{entry['sha256']}  {name}\n".encode()
            return httpx.Response(200, content=checksum)
        if request.url.path.endswith(".zip"):
            return httpx.Response(200, content=content)
        return httpx.Response(
            200,
            json=[dict(fundingTime=int(request.url.params["startTime"]), fundingRate="0.0001")],
        )

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:

        def simulated_download(config, root, *, progress):
            return download_minutes(config, root, client=client, progress=progress)

        monkeypatch.setattr(launcher, "download_minutes", simulated_download)
        config_path = tmp_path / "config.toml"
        config_path.write_text(config.to_toml(), encoding="utf-8")
        args = ["--root", str(tmp_path), "--config", str(config_path)]
        assert launcher.main(args) == 0
        assert sum(url.endswith(".zip") for url in calls) == 15
        assert entry["source_url"] not in calls
        calls.clear()
        assert launcher.main(args) == 0
        assert not any(url.endswith(".zip") or "/fundingRate?" in url for url in calls)
    output = capsys.readouterr().out
    assert "DESCARGA COMPLETA: 18/18 (100%)" in output
    assert "faltan 0" in output
    assert source_manifest.read_bytes() == original_manifest
    target = tmp_path / config.data_dir / "manifests/download.json"
    repaired = next(
        row
        for row in json.loads(target.read_text(encoding="utf-8"))["entries"]
        if row["source_url"] == entry["source_url"]
    )
    assert repaired["supplements"][0]["sha256"] == entry["supplements"][0]["sha256"]
