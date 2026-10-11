"""Authenticate the final layout and its unchanged scientific packages offline."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
CATALOG = "docs/procedencia/producto.json"


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def safe_path(root, name):
    pure = PurePosixPath(name)
    if pure.is_absolute() or ".." in pure.parts or "\\" in name or ":" in name:
        raise ValueError("Unsafe product path: " + name)
    path = root / pure
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("Unsafe product path: " + name)
    return path


def check_file(root, row):
    path = safe_path(root, row["path"])
    if not path.is_file() or sha256(path) != row["sha256"]:
        raise ValueError("Member changed: " + row["path"])
    size = row.get("bytes", row.get("size"))
    if size is not None and path.stat().st_size != size:
        raise ValueError("Member changed: " + row["path"])


def verify(root=ROOT, catalog=None):
    root = Path(root).resolve()
    if catalog is None:
        catalog = json.loads((root / CATALOG).read_text(encoding="utf8"))
    if catalog["schema"] != "tesina_product_v1":
        raise ValueError("Unknown product schema")
    for old in ("entregas/entrega_3", "entregas/entrega_4", "docs/entrega_4"):
        if (root / old).exists():
            raise ValueError("Retired layout is still present: " + old)
    count = 0
    for package in catalog["packages"]:
        folder = safe_path(root, package["path"])
        manifest = safe_path(folder, package["manifest"])
        if sha256(manifest) != package["manifest_sha256"]:
            raise ValueError("Package identity changed: " + package["path"])
        sidecar = manifest.with_suffix(".sha256")
        if sha256(sidecar) != package["sidecar_sha256"]:
            raise ValueError("Package sidecar changed: " + package["path"])
        if sidecar.read_text(encoding="utf-8-sig").split()[0] != sha256(manifest):
            raise ValueError("Package sidecar changed: " + package["path"])
        payload = json.loads(manifest.read_text(encoding="utf-8-sig"))
        if "file_hashes" in payload:
            members = [{"path": name, "sha256": digest}
                       for name, digest in payload["file_hashes"].items()]
        else:
            members = payload.get("members", payload.get("files", payload.get("archivos")))
        if not isinstance(members, list):
            raise ValueError("Unsupported package inventory")
        expected = {manifest.name, sidecar.name}
        for member in members:
            row = dict(member)
            row["path"] = row.get("path", row.get("archivo"))
            if row["path"] in expected:
                raise ValueError("Duplicate package membership")
            check_file(folder, row)
            expected.add(row["path"])
        actual = {p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file()}
        if expected != actual:
            raise ValueError("Package membership changed: " + package["path"])
        count += len(members)
    for group in ("preserved_files", "editorial_files"):
        for row in catalog[group]:
            check_file(root, row)
    return {"status": "verified", "packages": len(catalog["packages"]),
            "scientific_members": count, "preserved_files": len(catalog["preserved_files"]),
            "editorial_files": len(catalog["editorial_files"]),
            "engine_replay": False, "market_downloads": False,
            "scope": "Current layout, original package identities and member bytes; scientific semantics use each package verifier."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    print(json.dumps(verify(args.root), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
