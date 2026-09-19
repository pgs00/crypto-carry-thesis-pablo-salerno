"""Seal the compact delivery, validate its contents, and verify the ZIP entries."""

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


def deliver():
    if TARGET.exists():
        raise FileExistsError(f"Refusing to overwrite a previous delivery: {TARGET}")
    provenance = json.loads((PACKAGE / "fuentes_originales.json").read_text(encoding="utf-8"))
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
        version=1,
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
    with zipfile.ZipFile(TARGET, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in paths:
            archive.write(path, "paquete_redaccion/" + path.relative_to(PACKAGE).as_posix())
    with zipfile.ZipFile(TARGET) as archive:
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
    TARGET.with_suffix(".zip.sha256").write_text(digest(TARGET) + "\n", encoding="ascii")
    print(
        json.dumps(
            dict(
                zip=str(TARGET),
                bytes=TARGET.stat().st_size,
                archivos=len(paths),
                sha256=digest(TARGET),
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    deliver()
