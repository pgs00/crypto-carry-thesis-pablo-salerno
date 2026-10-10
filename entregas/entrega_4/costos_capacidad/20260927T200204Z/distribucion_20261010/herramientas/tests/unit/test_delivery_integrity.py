"""Keep original source bytes anchored when revising delivery documentation."""

import hashlib
import importlib.util
import json
import zipfile
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "entregas/entrega_3/archivo/empaquetar.py"
SPEC = importlib.util.spec_from_file_location("delivery_packager", SCRIPT)
packager = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(packager)


@pytest.fixture
def reference(tmp_path):
    package = tmp_path / "paquete_redaccion"
    package.mkdir()
    evidence = b"amount\r\n100.00\r\n"
    provenance = json.dumps(
        {
            "files": [
                {
                    "archivo": "source.csv",
                    "original": "missing-drive/source.csv",
                    "sha256": hashlib.sha256(evidence).hexdigest(),
                }
            ]
        }
    ).encode()
    files = {
        "source.csv": evidence,
        "fuentes_originales.json": provenance,
        "convenciones.md": b"Original documentation\n",
    }
    manifest = json.dumps(
        {
            "archivos": [
                {"archivo": name, "sha256": hashlib.sha256(data).hexdigest()}
                for name, data in files.items()
            ]
        }
    ).encode()
    files["manifiesto_paquete.json"] = manifest
    files["manifiesto_paquete.sha256"] = hashlib.sha256(manifest).hexdigest().encode()
    archive = tmp_path / "original.zip"
    with zipfile.ZipFile(archive, "w") as stream:
        for name, data in files.items():
            stream.writestr("paquete_redaccion/" + name, data)
            (package / name).write_bytes(data)
    archive.with_suffix(".zip.sha256").write_text(hashlib.sha256(archive.read_bytes()).hexdigest())
    return package, archive


def test_revised_document_keeps_sources_without_original_drives(reference):
    package, archive = reference
    (package / "convenciones.md").write_text("Corrected documentation\n")
    result = packager.verify_reference_sources(package, archive)
    assert result["sha256"] == hashlib.sha256(archive.read_bytes()).hexdigest()


def test_line_ending_normalization_is_not_silently_accepted(reference):
    package, archive = reference
    (package / "source.csv").write_bytes(b"amount\n100.00\n")
    with pytest.raises(ValueError, match="Original source changed"):
        packager.verify_reference_sources(package, archive)


def test_source_hashes_cannot_be_replaced_to_hide_changes(reference):
    package, archive = reference
    data = b"amount\r\n200.00\r\n"
    (package / "source.csv").write_bytes(data)
    path = package / "fuentes_originales.json"
    provenance = json.loads(path.read_bytes())
    provenance["files"][0]["sha256"] = hashlib.sha256(data).hexdigest()
    path.write_text(json.dumps(provenance))
    with pytest.raises(ValueError, match="Original provenance changed"):
        packager.verify_reference_sources(package, archive)


def test_reference_archive_checksum_is_required(reference):
    package, archive = reference
    archive.with_suffix(".zip.sha256").write_text("0" * 64)
    with pytest.raises(ValueError, match="Reference ZIP checksum mismatch"):
        packager.verify_reference_sources(package, archive)
