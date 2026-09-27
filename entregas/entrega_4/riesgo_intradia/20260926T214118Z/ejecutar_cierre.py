"""One-time closure for this delivery; never edits an existing sealed package.

All command outputs live beside this script, outside the compact package.
The actual read-only verifier is herramientas/scripts/verify_intraday_risk.py.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[3]
PACKAGE = BASE / "paquete_20260926T220400Z"
PARENT = ROOT / "entregas/entrega_4/reglas_historicas/20260925T005436Z"
CORRECTION = ROOT / (
    "entregas/entrega_4/reglas_historicas/"
    "correccion_exposicion_h2_20260925T150139Z/paquete_20260926T204312Z"
)
SERIES = Path("D:/Backtesting/outputs/riesgo_intradia_20260926T214118Z/completa")
DATA = Path("D:/Backtesting")
MANIFEST = "manifiesto_paquete.json"
SIDECAR = "manifiesto_paquete.sha256"


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_new(path, value):
    with Path(path).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def tree(root):
    return {
        p.relative_to(root).as_posix(): {"bytes": p.stat().st_size, "sha256": digest(p)}
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def command(label, args, cwd, records):
    record = {"label": label, "argv": [str(x) for x in args], "cwd": str(cwd)}
    record["started_at_utc"] = datetime.now(UTC).isoformat()
    start = time.perf_counter()
    log = BASE / (label + ".log")
    with log.open("x", encoding="utf-8", newline="\n") as stream:
        result = subprocess.run(args, cwd=cwd, stdout=stream, stderr=subprocess.STDOUT)
    record.update(
        finished_at_utc=datetime.now(UTC).isoformat(),
        seconds=time.perf_counter() - start,
        exit_code=result.returncode,
        log=log.name,
        log_sha256=digest(log),
    )
    records.append(record)
    write_new(BASE / (label + "_comando.json"), record)
    print(json.dumps(record), flush=True)
    if result.returncode:
        raise RuntimeError(f"{label} failed: inspect {log}")


def main():
    if (PACKAGE / MANIFEST).exists() or (PACKAGE / SIDECAR).exists():
        raise ValueError("refusing to modify a sealed package")
    if not (ROOT / "pyproject.toml").is_file():
        raise ValueError("unexpected repository root")
    initial = read(BASE / "estado_inicial.json")
    content = tree(PACKAGE)
    if any("__pycache__" in name or name.endswith(".pyc") for name in content):
        raise ValueError("unexpected package bytecode before verification")

    # A temporary copy tests relocation without duplicating the massive inputs.
    temporary_root = Path(tempfile.mkdtemp(prefix="riesgo_intradia_cierre_"))
    moved = temporary_root / "paquete"
    shutil.copytree(PACKAGE, moved)
    if tree(moved) != content:
        raise ValueError("relocation changed bytes")
    manifest = {
        "schema": "intraday_risk_package_v1",
        "created_at_utc": datetime.now(UTC).isoformat(),
        "parent_manifest_sha256": digest(PARENT / MANIFEST),
        "correction_manifest_sha256": digest(CORRECTION / MANIFEST),
        "full_series_in_compact_package": False,
        "files": [dict(path=name, **record) for name, record in content.items()],
    }
    write_new(moved / MANIFEST, manifest)
    with (moved / SIDECAR).open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(digest(moved / MANIFEST) + "  " + MANIFEST + "\n")
    sealed_tree = tree(moved)
    protected_roots = (PARENT, CORRECTION, ROOT / "Paquete de evidencia")
    before_names = {str(p): sorted(tree(p)) for p in protected_roots}
    write_new(BASE / "copia_verificacion_reubicada.json", {
        "created_at_utc": datetime.now(UTC).isoformat(),
        "temporary_package": str(moved),
        "original_package": str(PACKAGE),
        "manifest_sha256": digest(moved / MANIFEST),
        "members": len(content),
        "bytes_without_manifest": sum(row["bytes"] for row in content.values()),
        "commands_write_outside_package": True,
        "tree_before": sealed_tree,
    })
    records = []
    command("pytest_paquete_reubicado", [
        sys.executable, "-B", "-m", "pytest", "-p", "no:cacheprovider",
        moved / "herramientas/tests",
    ], moved / "herramientas", records)
    verifier = moved / "herramientas/scripts/verify_intraday_risk.py"
    common = [
        sys.executable, "-X", "utf8", verifier, "--package", moved,
        "--parent", PARENT, "--correction", CORRECTION,
    ]
    # Deliberately omit -B: the verifier itself must avoid bytecode writes.
    command("verificacion_compacta_reubicada", common + [
        "--scope", "compact", "--output", BASE / "verificacion_compacta_reubicada.json",
    ], temporary_root, records)
    command("verificacion_completa_reubicada", common + [
        "--scope", "complete", "--series-root", SERIES, "--data-root", DATA,
        "--output", BASE / "verificacion_completa_reubicada.json",
    ], temporary_root, records)

    # Verify preservation by bytes, with no dependency on Git publication state.
    failures = []
    for relative, record in initial["tracked_files"].items():
        if relative == ".gitattributes":
            continue
        if digest(ROOT / relative) != record["sha256"]:
            failures.append("tracked/" + relative)
    for root, index in ((DATA, read(PACKAGE / "fuentes_precios.json")),
                        (SERIES, read(PACKAGE / "series_locales.json"))):
        for record in index["entries"]:
            if digest(root / record["path"]) != record["sha256"]:
                failures.append(str(root / record["path"]))
    prices = read(PACKAGE / "fuentes_precios.json")
    price_manifest = DATA / (
        "data/minutes/2022_2026_continuous/derived_marks/"
        "futures_scaled/manifests/processed.json"
    )
    if digest(price_manifest) != prices["manifest_sha256"]:
        failures.append(str(price_manifest))
    after_names = {str(p): sorted(tree(p)) for p in protected_roots}
    package_unchanged = tree(moved) == sealed_tree
    readonly_passed = package_unchanged and before_names == after_names
    index_hash = digest(initial["index_path"])
    head = subprocess.check_output(
        ["git", "--no-optional-locks", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    preservation = {
        "checked_at_utc": datetime.now(UTC).isoformat(),
        "status": "passed" if (not failures and readonly_passed
                                and head == initial["head"]
                                and index_hash == initial["index_sha256"]) else "failed",
        "tracked_original_files_checked": len(initial["tracked_files"]) - 1,
        "intentional_old_file_change": ".gitattributes (new evidence tree only)",
        "local_price_files_checked": len(read(PACKAGE / "fuentes_precios.json")["entries"]),
        "local_series_files_checked": len(read(PACKAGE / "series_locales.json")["entries"]),
        "changed_original_or_local_files": failures,
        "relocated_package_tree_unchanged": package_unchanged,
        "protected_directories_have_no_new_members": before_names == after_names,
        "head_unchanged": head == initial["head"],
        "head": head,
        "index_unchanged": index_hash == initial["index_sha256"],
        "index_sha256": index_hash,
        "verification_command_omitted_bytecode_flag": True,
        "manifest_sha256": digest(moved / MANIFEST),
    }
    write_new(BASE / "preservacion_final.json", preservation)
    if (preservation["status"] != "passed" or not preservation["head_unchanged"]
            or not preservation["index_unchanged"]):
        raise ValueError("preservation failed; original package remains unsealed")
    if tree(PACKAGE) != content:
        raise ValueError("package changed during verification; refusing to seal")
    # These exact manifest bytes refer to the content verified at the other path.
    shutil.copyfile(moved / MANIFEST, PACKAGE / MANIFEST)
    shutil.copyfile(moved / SIDECAR, PACKAGE / SIDECAR)
    if tree(PACKAGE) != sealed_tree:
        raise ValueError("sealed original differs from verified copy")
    command("verificacion_compacta_final", [
        sys.executable, "-X", "utf8", PACKAGE / "herramientas/scripts/verify_intraday_risk.py",
        "--package", PACKAGE, "--scope", "compact", "--parent", PARENT,
        "--correction", CORRECTION, "--output", BASE / "verificacion_compacta_final.json",
    ], temporary_root, records)
    if tree(PACKAGE) != sealed_tree:
        raise ValueError("final verification wrote to its sealed package")
    write_new(BASE / "cierre_ejecutado.json", {
        "status": "passed",
        "finished_at_utc": datetime.now(UTC).isoformat(),
        "manifest_sha256": digest(PACKAGE / MANIFEST),
        "package_identical_to_fully_verified_relocated_copy": True,
        "main_package_unchanged_by_final_verification": True,
        "commands": records,
        "full_reconstruction_replayed_engine": False,
    })
    print("Closure passed; package sealed with the tested bytes.", flush=True)


if __name__ == "__main__":
    main()
