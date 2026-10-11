"""Archive verified distributions with exact bytes and protected destinations."""

import hashlib
import subprocess
import zipfile

import pytest

from scripts import package_independent_windows as packager


@pytest.fixture
def reference(tmp_path):
    package = tmp_path / "ventanas_independientes"
    verifier = package / "scripts/verificar_paquete.py"
    verifier.parent.mkdir(parents=True)
    payload = b"amount\r\n100.00\r\n"
    (package / "source.csv").write_bytes(payload)
    expected = hashlib.sha256(payload).hexdigest()
    verifier.write_text(
        "import hashlib\nfrom pathlib import Path\n"
        "p = Path(__file__).resolve().parents[1] / 'source.csv'\n"
        f"assert hashlib.sha256(p.read_bytes()).hexdigest() == '{expected}'\n",
        encoding="utf-8",
    )
    return package, tmp_path / "export.zip"


def test_archive_preserves_every_verified_source_byte(reference):
    package, target = reference
    before = {p.relative_to(package): p.read_bytes() for p in package.rglob("*") if p.is_file()}
    packager.deliver(package, target)
    with zipfile.ZipFile(target) as archive:
        assert archive.testzip() is None
        assert set(archive.namelist()) == {package.name + "/" + p.as_posix() for p in before}
        for relative, content in before.items():
            assert archive.read(package.name + "/" + relative.as_posix()) == content
            assert (package / relative).read_bytes() == content
    checksum = hashlib.sha256(target.read_bytes()).hexdigest()
    assert target.with_suffix(".zip.sha256").read_text().strip() == checksum


@pytest.mark.parametrize("payload", [b"amount\n100.00\n", b"amount\r\n200.00\r\n"])
def test_changed_scientific_bytes_fail_before_archive_creation(reference, payload):
    package, target = reference
    (package / "source.csv").write_bytes(payload)
    with pytest.raises(subprocess.CalledProcessError):
        packager.deliver(package, target)
    assert not target.exists()
    assert not target.with_suffix(".zip.sha256").exists()


@pytest.mark.parametrize("existing", ["archive", "sidecar", "inside", "source_itself"])
def test_existing_and_protected_destinations_are_rejected(reference, existing):
    package, target = reference
    if existing == "inside":
        target = package / "new.zip"
    elif existing == "source_itself":
        target = package
    else:
        protected = target if existing == "archive" else target.with_suffix(".zip.sha256")
        protected.write_bytes(b"existing bytes")
    with pytest.raises(ValueError, match="new archive outside"):
        packager.deliver(package, target)
    if existing in {"archive", "sidecar"}:
        assert protected.read_bytes() == b"existing bytes"
