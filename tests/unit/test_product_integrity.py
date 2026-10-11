"""The final layout authenticates relocated evidence without old directories."""

import hashlib
import importlib
import json

import pytest


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def product(tmp_path):
    package = tmp_path / "results/base/evidencia"
    package.mkdir(parents=True)
    scientific = package / "table.csv"
    scientific.write_bytes(b"equity\n10000\n")
    manifest = package / "manifiesto_paquete.json"
    manifest.write_text(json.dumps({"members": [{
        "path": "table.csv", "sha256": digest(scientific),
        "bytes": scientific.stat().st_size,
    }]}), encoding="utf8")
    (package / "manifiesto_paquete.sha256").write_text(digest(manifest), encoding="ascii")
    catalog = {
        "schema": "tesina_product_v1",
        "packages": [{"path": "results/base/evidencia", "manifest": manifest.name,
                      "manifest_sha256": digest(manifest),
                      "sidecar_sha256": digest(manifest.with_suffix(".sha256"))}],
        "preserved_files": [], "editorial_files": [],
    }
    return tmp_path, catalog, scientific, manifest


def test_relocated_package_verifies_without_delivery_directories(product):
    root, catalog, _, _ = product
    module = importlib.import_module("scripts.verify_product")
    assert module.verify(root, catalog)["scientific_members"] == 1


def test_resealed_scientific_change_does_not_replace_authenticated_identity(product):
    root, catalog, scientific, manifest = product
    scientific.write_bytes(b"equity\n99999\n")
    content = json.loads(manifest.read_text(encoding="utf8"))
    content["members"][0]["sha256"] = digest(scientific)
    manifest.write_text(json.dumps(content), encoding="utf8")
    manifest.with_suffix(".sha256").write_text(digest(manifest), encoding="ascii")
    module = importlib.import_module("scripts.verify_product")
    with pytest.raises(ValueError, match="Package identity changed"):
        module.verify(root, catalog)


def test_scientific_member_corruption_is_rejected(product):
    root, catalog, scientific, _ = product
    scientific.write_bytes(b"equity\n99999\n")
    module = importlib.import_module("scripts.verify_product")
    with pytest.raises(ValueError, match="Member changed"):
        module.verify(root, catalog)


def test_sidecar_requires_original_bytes_not_only_matching_checksum(product):
    root, catalog, _, manifest = product
    sidecar = manifest.with_suffix(".sha256")
    sidecar.write_text(digest(manifest) + "  renamed.json\n", encoding="ascii")
    module = importlib.import_module("scripts.verify_product")
    with pytest.raises(ValueError, match="Package sidecar changed"):
        module.verify(root, catalog)


def test_extra_member_and_path_traversal_are_rejected(product):
    root, catalog, scientific, _ = product
    (scientific.parent / "unlisted.txt").write_text("extra", encoding="utf8")
    module = importlib.import_module("scripts.verify_product")
    with pytest.raises(ValueError, match="membership"):
        module.verify(root, catalog)
    catalog["packages"][0]["path"] = "../outside"
    with pytest.raises(ValueError, match="Unsafe"):
        module.verify(root, catalog)
