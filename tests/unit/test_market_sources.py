"""Reject changed or missing market inputs before replaying published results."""

import hashlib

import pytest

from scripts.check_market_sources import verify_sources


@pytest.fixture
def sources(tmp_path):
    contents = {
        "data/month.zip": b"original monthly observations",
        "data/month.zip.CHECKSUM": b"original monthly checksum",
        "data/day.zip": b"original daily supplement",
        "data/day.zip.CHECKSUM": b"original daily checksum",
        "data/funding.json": b'[{"fundingRate":"0.0001"}]',
    }
    hashes = {}
    for name, body in contents.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
        hashes[name] = hashlib.sha256(body).hexdigest()

    def record(name, checksum=False):
        entry = {"path": name, "sha256": hashes[name]}
        if checksum:
            entry.update(checksum_path=name + ".CHECKSUM",
                         checksum_file_sha256=hashes[name + ".CHECKSUM"])
        return entry

    monthly = record("data/month.zip", True)
    monthly["supplements"] = [record("data/day.zip", True)]
    return tmp_path, {"entries": [monthly, record("data/funding.json")]}


def test_checks_archives_api_snapshot_supplements_and_checksums(sources):
    root, reference = sources
    assert verify_sources(root, reference) == {"checked_files": 5, "failures": []}


@pytest.mark.parametrize("name", [
    "month.zip", "month.zip.CHECKSUM", "day.zip", "day.zip.CHECKSUM", "funding.json",
])
def test_changed_source_is_rejected_even_if_local_manifest_accepts_it(sources, name):
    root, reference = sources
    (root / "data" / name).write_bytes(b"changed")
    (root / "data/download.json").write_text('{"status":"download_complete"}')
    result = verify_sources(root, reference)
    assert result["failures"] == [{"path": "data/" + name, "reason": "sha256_mismatch"}]


def test_missing_supplement_is_reported(sources):
    root, reference = sources
    (root / "data/day.zip").unlink()
    assert verify_sources(root, reference)["failures"] == [
        {"path": "data/day.zip", "reason": "missing"},
    ]


@pytest.mark.parametrize("path", ["../outside", "/outside", "D:/outside", "data\\outside"])
def test_reference_cannot_escape_data_root(sources, path):
    root, reference = sources
    reference["entries"][0]["path"] = path
    with pytest.raises(ValueError, match="Unsafe"):
        verify_sources(root, reference)


def test_symlink_cannot_escape_data_root(sources, tmp_path):
    root, reference = sources
    (root / "data/month.zip").unlink()
    (root / "data/month.zip").symlink_to(root.parent / "outside")
    with pytest.raises(ValueError, match="Unsafe"):
        verify_sources(root, reference)


def test_conflicting_hashes_are_rejected(sources):
    root, reference = sources
    reference["entries"].append({"path": "data/month.zip", "sha256": "0" * 64})
    with pytest.raises(ValueError, match="Conflicting"):
        verify_sources(root, reference)


def test_empty_reference_is_not_success(sources):
    root, _ = sources
    with pytest.raises(ValueError, match="empty"):
        verify_sources(root, {"entries": []})
