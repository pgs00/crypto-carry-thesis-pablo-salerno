"""Documentary packaging cannot waive scientific evidence or original identity."""

import json
from pathlib import Path

import pytest

from scripts import distribution_integrity as integrity

ROOT = Path(__file__).resolve().parents[2]
PACKAGES = sorted({p.parent.parent for p in (ROOT / "entregas").rglob("procedencia/derivacion.json")})


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, sort_keys=True) + "\n", encoding="utf8")


def row(path, package):
    return {"path": path.relative_to(package).as_posix(), "sha256": integrity.sha256(path),
            "bytes": path.stat().st_size}


def renew_outer_seal(package):
    members = [row(p, package) for p in package.rglob("*") if p.is_file()
               and p.relative_to(package).as_posix() not in {
                   "manifiesto_paquete.json", "manifiesto_paquete.sha256"}]
    manifest = package / "manifiesto_paquete.json"
    write_json(manifest, {"members": members})
    (package / "manifiesto_paquete.sha256").write_text(integrity.sha256(manifest), encoding="ascii")


@pytest.fixture
def distribution(tmp_path, monkeypatch):
    scientific = tmp_path / "evidencia/run_demo/effective_config.toml"
    scientific.parent.mkdir(parents=True)
    scientific.write_text('capital = "10000"\n', encoding="utf8")
    scientific_row = row(scientific, tmp_path)
    original = tmp_path / integrity.ORIGINAL
    prompt_row = {"path": "documentos/encargo_usuario.md", "sha256": "a" * 64, "bytes": 37}
    write_json(original, {"members": [scientific_row, prompt_row]})
    original_hash = integrity.sha256(original)
    sidecar = tmp_path / integrity.ORIGINAL_SIDECAR
    sidecar.write_text(original_hash, encoding="ascii")
    monkeypatch.setitem(integrity.POLICIES, original_hash, {
        "omitted": {prompt_row["path"]}, "adapted": set(),
        "added": {integrity.ORIGINAL, integrity.ORIGINAL_SIDECAR},
    })
    write_json(tmp_path / integrity.DERIVATION, {
        "schema": "documentary_distribution_v1", "distribution_id": "distribucion_20261010",
        "original_manifest_sha256": original_hash, "omitted": [prompt_row], "adapted": [],
        "added": [row(original, tmp_path), row(sidecar, tmp_path)],
    })
    renew_outer_seal(tmp_path)
    assert integrity.verify_distribution(tmp_path)["preserved_members"] == 1
    return tmp_path, scientific, scientific_row, prompt_row


@pytest.mark.parametrize("package", PACKAGES, ids=lambda p: p.parent.name + "/" + p.name)
def test_real_distributions_preserve_original_scientific_members(package):
    result = integrity.verify_distribution(package)
    assert result is not None
    assert result["preserved_members"] > 0


def test_scientific_omission_rejected_after_descriptor_and_outer_seal_renewal(distribution):
    package, scientific, scientific_row, _ = distribution
    descriptor = integrity.read_json(package / integrity.DERIVATION)
    descriptor["omitted"].append(scientific_row)
    write_json(package / integrity.DERIVATION, descriptor)
    scientific.unlink()
    renew_outer_seal(package)
    with pytest.raises(ValueError, match="Unauthorized documentary disposition"):
        integrity.verify_distribution(package)


def test_scientific_change_rejected_after_outer_seal_renewal(distribution):
    package, scientific, _, _ = distribution
    scientific.write_text('capital = "50000"\n', encoding="utf8")
    renew_outer_seal(package)
    with pytest.raises(ValueError, match="Distribution member changed"):
        integrity.verify_distribution(package)


def test_extra_member_rejected_after_outer_seal_renewal(distribution):
    package, _, _, _ = distribution
    (package / "extra.txt").write_text("unlisted content", encoding="utf8")
    renew_outer_seal(package)
    with pytest.raises(ValueError, match="Unexpected distribution file population"):
        integrity.verify_distribution(package)


def test_original_manifest_cannot_be_replaced_with_updated_descriptor(distribution):
    package, _, _, _ = distribution
    original = package / integrity.ORIGINAL
    original.write_bytes(original.read_bytes() + b"\n")
    descriptor = integrity.read_json(package / integrity.DERIVATION)
    descriptor["original_manifest_sha256"] = integrity.sha256(original)
    write_json(package / integrity.DERIVATION, descriptor)
    renew_outer_seal(package)
    with pytest.raises(ValueError, match="Unauthenticated original package identity"):
        integrity.verify_distribution(package)


def test_frozen_document_exception_is_exact_and_does_not_cover_science(distribution):
    package, scientific, scientific_row, prompt_row = distribution
    assert integrity.verify_frozen_document(package, prompt_row["path"], prompt_row["sha256"])
    assert integrity.verify_frozen_document(package, scientific_row["path"], scientific_row["sha256"])
    with pytest.raises(ValueError, match="Frozen protocol differs"):
        integrity.verify_frozen_document(package, prompt_row["path"], "b" * 64)
    scientific.write_bytes(scientific.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="Distribution member changed"):
        integrity.verify_frozen_document(package, scientific_row["path"], scientific_row["sha256"])


def test_frozen_legacy_document_still_requires_exact_bytes(tmp_path):
    path = tmp_path / "protocolo.json"
    path.write_text('{"tolerance":"1E-8"}', encoding="utf8")
    wanted = integrity.sha256(path)
    assert integrity.verify_frozen_document(tmp_path, "protocolo.json", wanted)
    path.write_text('{"tolerance":"1E-4"}', encoding="utf8")
    with pytest.raises(ValueError, match="Frozen protocol input changed"):
        integrity.verify_frozen_document(tmp_path, "protocolo.json", wanted)


@pytest.mark.parametrize("name", ["manifiesto_paquete.json", "manifiesto_paquete.sha256"])
def test_distribution_dependency_requires_its_current_seal(distribution, name):
    package, _, _, _ = distribution
    (package / name).write_text("BROKEN SEAL", encoding="ascii")
    with pytest.raises(ValueError, match="Current distribution manifest sidecar mismatch"):
        integrity.verify_distribution(package)
