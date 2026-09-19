"""Seal the compact delivery, validate its contents, and verify the ZIP entries."""

import argparse
import hashlib
import json
import subprocess
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
PACKAGE = PROJECT / "entregas/entrega_3/paquete_redaccion"
TARGET = PACKAGE.parent / "paquete_redaccion_entrega_3.zip"


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def verify_reference_sources(package, reference):
    """Anchor unchanged source bytes to a verified archive, without original drives."""
    checksum = digest(reference)
    if checksum != reference.with_suffix(reference.suffix + ".sha256").read_text().strip():
        raise ValueError("Reference ZIP checksum mismatch")
    prefix = "paquete_redaccion/"
    with zipfile.ZipFile(reference) as archive:
        manifest_bytes = archive.read(prefix + "manifiesto_paquete.json")
        manifest_hash = hashlib.sha256(manifest_bytes).hexdigest()
        if manifest_hash != archive.read(prefix + "manifiesto_paquete.sha256").decode().strip():
            raise ValueError("Reference manifest checksum mismatch")
        for item in json.loads(manifest_bytes)["archivos"]:
            if hashlib.sha256(archive.read(prefix + item["archivo"])).hexdigest() != item["sha256"]:
                raise ValueError(f"Reference artifact checksum mismatch: {item['archivo']}")
        original = archive.read(prefix + "fuentes_originales.json")
        if (package / "fuentes_originales.json").read_bytes() != original:
            raise ValueError("Original provenance changed")
        for item in json.loads(original)["files"]:
            if digest(package / item["archivo"]) != item["sha256"]:
                raise ValueError(f"Original source changed: {item['archivo']}")
    return dict(archivo=reference.name, sha256=checksum, manifiesto_sha256=manifest_hash)


def deliver(target=TARGET, reference=None):
    if target.exists():
        raise FileExistsError(f"Refusing to overwrite a previous delivery: {target}")
    provenance = json.loads((PACKAGE / "fuentes_originales.json").read_text(encoding="utf-8"))
    anchor = verify_reference_sources(PACKAGE, reference) if reference else None
    if not reference:
        for item in provenance["files"]:
            assert digest(Path(item["original"])) == item["sha256"], item["original"]
    paths = sorted(
        path
        for path in PACKAGE.rglob("*")
        if path.is_file()
        and "__pycache__" not in path.parts
        and path.suffix != ".pyc"
        and path.name not in {"manifiesto_paquete.json", "manifiesto_paquete.sha256"}
    )
    manifest = dict(
        version=2 if reference else 1,
        creado_utc=datetime.now(UTC).isoformat(),
        revision=provenance["revision"],
        auditoria=provenance["basis_audit"],
        escenario_principal="vwap_joint",
        nuevas_simulaciones=False,
        parametros_modificados=False,
        originales_verificados=len(provenance["files"]),
        hashes_artefactos_completos="evidencia/corridas/*/run_manifest.json; evidencia/revision/revision_manifest.json; evidencia/basis/basis_audit_manifest.json",
        exclusiones=[
            "datasets de mercado",
            "ZIP de mercado",
            "entornos",
            "caches",
            "Git",
            "secretos",
        ],
        archivos=[
            dict(
                archivo=path.relative_to(PACKAGE).as_posix(),
                bytes=path.stat().st_size,
                sha256=digest(path),
            )
            for path in paths
        ],
    )
    if anchor:
        manifest["referencia_zip_original"] = anchor
    path = PACKAGE / "manifiesto_paquete.json"
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (PACKAGE / "manifiesto_paquete.sha256").write_text(digest(path) + "\n", encoding="ascii")
    check = subprocess.run(
        [sys.executable, str(PACKAGE / "scripts/verificar_paquete.py")],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    print(check.stdout)
    paths += [path, PACKAGE / "manifiesto_paquete.sha256"]
    with zipfile.ZipFile(target, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in paths:
            archive.write(path, "paquete_redaccion/" + path.relative_to(PACKAGE).as_posix())
    with zipfile.ZipFile(target) as archive:
        assert archive.testzip() is None
        assert len(archive.namelist()) == len(paths)
        for path in paths:
            data = archive.read("paquete_redaccion/" + path.relative_to(PACKAGE).as_posix())
            assert hashlib.sha256(data).hexdigest() == digest(path)
        assert not any(
            part in {"__pycache__", ".git", ".venv", "node_modules"}
            for name in archive.namelist()
            for part in Path(name).parts
        )
    target.with_suffix(target.suffix + ".sha256").write_text(
        digest(target) + "\n", encoding="ascii"
    )
    print(
        json.dumps(
            dict(
                zip=str(target),
                bytes=target.stat().st_size,
                archivos=len(paths),
                sha256=digest(target),
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=TARGET)
    parser.add_argument("--reference-zip", type=Path)
    args = parser.parse_args()
    deliver(args.output, args.reference_zip)
