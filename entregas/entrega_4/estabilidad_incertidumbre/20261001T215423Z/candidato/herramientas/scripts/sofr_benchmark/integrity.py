"""Portable binary sealing helpers, without importing prior diagnostics."""

import json
from datetime import UTC, datetime
from pathlib import Path

from scripts.return_capital.common import read_json, sha256, write_json


def new_destination(destination, protected):
    destination = Path(destination).resolve()
    if destination.exists():
        raise ValueError("Destination already exists; choose a new version")
    for root in protected:
        root = Path(root).resolve()
        if destination.is_relative_to(root) or root.is_relative_to(destination):
            raise ValueError("Destination overlaps a protected input")
    return destination


def same_rows(actual, expected, label):
    def cell(value):
        if value is None:
            return ""
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        return str(value)

    if len(actual) != len(expected):
        raise ValueError(label + ": row count changed")
    for ordinal, (a, b) in enumerate(zip(actual, expected)):
        if any(cell(a.get(k)) != cell(b.get(k)) for k in a.keys() | b.keys()):
            raise ValueError(f"{label}/{ordinal}: value changed")


def check_manifest(package):
    package = Path(package).resolve()
    manifest = read_json(package / "manifiesto_paquete.json")
    if (package / "manifiesto_paquete.sha256").read_text().split()[0] != sha256(
        package / "manifiesto_paquete.json"
    ):
        raise ValueError("Manifest hash mismatch")
    expected = {"manifiesto_paquete.json", "manifiesto_paquete.sha256"}
    for row in manifest["members"]:
        path = (package / row["path"]).resolve()
        if not path.is_relative_to(package) or row["path"] in expected:
            raise ValueError("Unsafe or duplicate manifest path")
        if path.stat().st_size != row["bytes"] or sha256(path) != row["sha256"]:
            raise ValueError("Member hash mismatch: " + row["path"])
        expected.add(row["path"])
    if expected != {p.relative_to(package).as_posix() for p in package.rglob("*") if p.is_file()}:
        raise ValueError("Manifest membership differs")
    return manifest


def seal(package):
    package = Path(package)
    if (package / "manifiesto_paquete.json").exists():
        raise ValueError("Cannot reseal an existing package")
    members = [
        dict(path=p.relative_to(package).as_posix(), bytes=p.stat().st_size, sha256=sha256(p))
        for p in sorted(package.rglob("*"))
        if p.is_file()
    ]
    write_json(
        package / "manifiesto_paquete.json",
        dict(schema="sofr_benchmark_v1", created_at=datetime.now(UTC).isoformat(), members=members),
    )
    (package / "manifiesto_paquete.sha256").write_text(
        sha256(package / "manifiesto_paquete.json") + "  manifiesto_paquete.json\n",
        encoding="utf-8",
    )
