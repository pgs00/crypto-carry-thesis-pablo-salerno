from __future__ import annotations

import hashlib
import io
import zipfile

import httpx
import pytest

from crypto_carry.data import download


def _archive_bytes(rows: int = 40_000) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr("sample.csv", b"1,100,0.001,1704067200000,true\n" * rows)
    return buffer.getvalue()


class FragmentedStream(httpx.SyncByteStream):
    def __init__(self, content: bytes, fragment_size: int = 16 * 1024):
        self.content = content
        self.fragment_size = fragment_size

    def __iter__(self):
        for start in range(0, len(self.content), self.fragment_size):
            yield self.content[start : start + self.fragment_size]


def _download(client, root, payload, *, budget, retries=1):
    return download.download_verified_archive(
        client,
        "https://example.invalid/archive.zip",
        root / "archive.zip",
        expected_sha256=hashlib.sha256(payload).hexdigest(),
        budget_limit=budget,
        data_root=root,
        retries=retries,
    )


def test_fragmented_transfer_does_not_scan_data_tree_for_every_network_fragment(
    tmp_path, monkeypatch
):
    payload = _archive_bytes()
    scans = 0
    original = download._data_bytes

    def count_scan(root):
        nonlocal scans
        scans += 1
        return original(root)

    monkeypatch.setattr(download, "_data_bytes", count_scan)

    def handle(_request):
        return httpx.Response(
            200,
            headers={"content-length": str(len(payload))},
            stream=FragmentedStream(payload),
        )

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        result = _download(client, tmp_path, payload, budget=len(payload))

    assert result["status"] == "downloaded"
    assert (tmp_path / "archive.zip").read_bytes() == payload
    # This archive arrives in 76 fragments; tree scans must remain bounded.
    assert scans <= 4


@pytest.mark.parametrize("declared_length", [True, False])
def test_fragmented_download_accepts_exact_remaining_budget(tmp_path, declared_length):
    payload = _archive_bytes(rows=200)
    (tmp_path / "existing.bin").write_bytes(b"existing data")

    def handle(_request):
        headers = {"content-length": str(len(payload))} if declared_length else {}
        return httpx.Response(200, headers=headers, stream=FragmentedStream(payload, 31))

    budget = len(b"existing data") + len(payload)
    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        result = _download(client, tmp_path, payload, budget=budget)

    assert result["bytes"] == len(payload)
    assert download._data_bytes(tmp_path) == budget
    assert (tmp_path / "existing.bin").read_bytes() == b"existing data"


@pytest.mark.parametrize("declared_length", [True, False])
def test_budget_rejects_one_byte_overrun_even_with_small_buffered_writes(tmp_path, declared_length):
    payload = _archive_bytes(rows=200)
    (tmp_path / "existing.bin").write_bytes(b"existing data")

    def handle(_request):
        headers = {"content-length": str(len(payload))} if declared_length else {}
        return httpx.Response(200, headers=headers, stream=FragmentedStream(payload, 31))

    budget = len(b"existing data") + len(payload) - 1
    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(download.DataBudgetExceeded):
            _download(client, tmp_path, payload, budget=budget)

    assert not (tmp_path / "archive.zip").exists()
    assert download._data_bytes(tmp_path) <= budget
    assert (tmp_path / "existing.bin").read_bytes() == b"existing data"


def test_resume_counts_partial_archive_once_and_preserves_its_bytes(tmp_path):
    payload = _archive_bytes()
    offset = 137 * 1024
    partial = tmp_path / "archive.zip.part"
    partial.write_bytes(payload[:offset])
    (tmp_path / "existing.bin").write_bytes(b"existing data")

    def handle(request):
        assert request.headers["range"] == f"bytes={offset}-"
        return httpx.Response(
            206,
            headers={
                "content-length": str(len(payload) - offset),
                "content-range": f"bytes {offset}-{len(payload) - 1}/{len(payload)}",
            },
            stream=FragmentedStream(payload[offset:]),
        )

    budget = len(b"existing data") + len(payload)
    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        result = _download(client, tmp_path, payload, budget=budget)

    assert result["status"] == "downloaded"
    assert (tmp_path / "archive.zip").read_bytes() == payload
    assert not partial.exists()
    assert download._data_bytes(tmp_path) == budget


@pytest.mark.parametrize("failure", ["checksum", "zip_crc"])
def test_streaming_checks_integrity_before_publishing_archive(tmp_path, failure):
    original = _archive_bytes(rows=200)
    damaged = bytearray(original)
    damaged[100] ^= 1
    payload = bytes(damaged)
    expected = original if failure == "checksum" else payload

    def handle(_request):
        return httpx.Response(200, stream=FragmentedStream(payload, 31))

    message = "SHA-256 mismatch" if failure == "checksum" else "ZIP integrity failure"
    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(ValueError, match=message):
            _download(client, tmp_path, expected, budget=len(payload))

    assert not (tmp_path / "archive.zip").exists()


def test_complete_partial_is_verified_and_published_without_requesting_range_at_eof(tmp_path):
    payload = _archive_bytes(rows=200)
    partial = tmp_path / "archive.zip.part"
    partial.write_bytes(payload)
    requests = []

    def handle(request):
        requests.append(request)
        return httpx.Response(416)

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        result = _download(client, tmp_path, payload, budget=len(payload))
    assert not requests
    assert result["status"] == "cached"
    assert (tmp_path / "archive.zip").read_bytes() == payload
    assert not partial.exists()


def test_complete_partial_requires_zip_crc_even_when_sha_matches(tmp_path):
    damaged = bytearray(_archive_bytes(rows=200))
    damaged[100] ^= 1
    payload = bytes(damaged)
    (tmp_path / "archive.zip.part").write_bytes(payload)
    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(416))) as client:
        with pytest.raises(ValueError, match="ZIP integrity"):
            _download(client, tmp_path, payload, budget=len(payload))
    assert not (tmp_path / "archive.zip").exists()
