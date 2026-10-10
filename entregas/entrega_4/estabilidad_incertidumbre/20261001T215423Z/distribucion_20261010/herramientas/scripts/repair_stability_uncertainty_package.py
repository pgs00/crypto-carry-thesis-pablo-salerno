"""Repair the diagnosed B6 lockfile omission; preserve the failed seal and all results."""

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

for _key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_key] = "1"
os.environ.update(PYTHONDONTWRITEBYTECODE="1", MPLBACKEND="Agg", PYTHONIOENCODING="utf-8")
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from scripts.coordinate_stability_uncertainty import existing_jobs, resources  # noqa: E402
from scripts.package_stability_uncertainty import (  # noqa: E402
    copy_final,
    execute,
    snapshot_tools,
    update_indices,
)
from scripts.stability_uncertainty_contract import read, save, sha, verify_contract  # noqa: E402
from scripts.verify_stability_uncertainty import seal, verify_seal  # noqa: E402


def repair(candidate, data_root):
    import msvcrt

    candidate = candidate.resolve()
    base = candidate.parent
    previous = base / "paquete_final"
    final = base / "paquete_final_verificado"
    audit = base / "controles_finales_corregidos"
    record = candidate / "controles/reparacion_exportacion"
    closure = base / "cierre_actual.json"
    lock_path = Path(tempfile.gettempdir()) / (
        "b6-" + hashlib.sha256(str(candidate).casefold().encode()).hexdigest()[:16] + ".lock"
    )
    lock = lock_path.open("a+b")
    if lock.tell() == 0:
        lock.write(b"0")
        lock.flush()
    lock.seek(0)
    msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
    started = time.monotonic()
    try:
        if existing_jobs(resources(data_root)["processes"]):
            raise RuntimeError("Another B6 job is active; preserve it")
        if final.exists() or audit.exists() or record.exists():
            raise FileExistsError("Repair destination already exists; never overwrite/retry a seal")
        previous_seal = verify_seal(previous)
        protocol = verify_contract(candidate)
        if sha(ROOT / ".git/index") != protocol["index_sha256"]:
            raise ValueError("User index changed; do not modify it")
        # This operation is restricted to the demonstrated, otherwise byte-identical omission.
        for folder in ("herramientas", "codigo_ejecutado"):
            differences = [
                name
                for name, digest in protocol["code_files"].items()
                if not (previous / folder / name).is_file()
                or sha(previous / folder / name) != digest
            ]
            if differences != ["uv.lock"]:
                raise ValueError(
                    f"Repair scope differs from diagnosed omission: {folder}/{differences}"
                )
        record.mkdir(parents=True)
        audit.mkdir()
        for source, name in (
            (closure, "cierre_bloqueado.json"),
            (candidate / "progreso_local.json", "progreso_bloqueado.json"),
            (previous / "manifiesto_paquete.json", "sello_intento_fallido.json"),
            (base / "controles_finales/verificacion_offline.txt", "fallo_offline.txt"),
        ):
            shutil.copyfile(source, record / name)
        original = read(previous / "manifiesto_paquete.json")
        preserved = {
            r["path"]: r["sha256"]
            for r in original["members"]
            if r["path"].startswith(
                ("tablas/", "estadistica/", "evidencia/", "figuras/", "resultados/")
            )
            or r["path"] in {"reporte.md", "reporte.html", "sintesis.md", "indice_corridas.json"}
        }
        for name, digest in preserved.items():
            if sha(candidate / name) != digest:
                raise ValueError("Analytical result changed before packaging repair: " + name)
        save(
            record / "diagnostico.json",
            dict(
                utc=datetime.now(UTC).isoformat(),
                cause="Exporter excluded every .lock file, including uv.lock",
                fix="Exclude runtime locks under ejecuciones only; check complete exported code before sealing",
                previous_package=str(previous),
                previous_manifest_sha256=previous_seal["manifest_sha256"],
                previous_status="intento_fallido_no_vigente",
                unique_final_target=str(final),
                code_identity=protocol["engine_code_hash"],
                required_code_files=len(protocol["code_files"]),
                restored_members=["herramientas/uv.lock", "codigo_ejecutado/uv.lock"],
                economic_replays=0,
                bootstrap_recalculations_for_changed_economics=0,
                preserved_analytical_members=preserved,
                tests=dict(
                    command=".venv/Scripts/python.exe -B -X utf8 -m pytest tests/unit/test_stability_delivery.py -q -p no:cacheprovider",
                    before="3 failed, 11 passed",
                    after="14 passed",
                    ruff="All checks passed",
                ),
                repair_script_sha256=sha(Path(__file__)),
                changed_files={
                    n: sha(ROOT / n)
                    for n in (
                        "scripts/package_stability_uncertainty.py",
                        "tests/unit/test_stability_delivery.py",
                    )
                },
                offline_scope="Prior attempt aborted before any financial/bootstrap recomputation; one complete corrected verification follows",
            ),
        )
        snapshot_tools(candidate)
        readme = candidate / "README.md"
        text = readme.read_text(encoding="utf-8").replace(
            "../controles_finales/verificacion_offline.json",
            "../controles_finales_corregidos/verificacion_offline.json",
        )
        text += (
            "\nLa exportación corregida conserva `uv.lock` en ambos snapshots de código. "
            "El intento anterior, que falló antes del recálculo offline, permanece intacto y no vigente. "
            "El diagnóstico y la identidad de sus resultados están en "
            "`controles/reparacion_exportacion/diagnostico.json`.\n"
        )
        readme.write_text(text, encoding="utf-8", newline="\n")
        copy_final(candidate, final)
        for name, digest in preserved.items():
            if sha(final / name) != digest:
                raise ValueError("Analytical bytes differ after export: " + name)
        seal(final)
        offline_root = Path(tempfile.gettempdir()) / ("b6_offline_" + base.name + "_corregido")
        offline = offline_root / "paquete"
        if offline.exists():
            raise FileExistsError(
                "Corrected offline copy already exists; no duplicate verification"
            )
        shutil.copytree(final, offline)
        output = offline_root / "verificacion_offline.json"
        timing = execute(
            [
                sys.executable,
                "-B",
                "-I",
                "-X",
                "utf8",
                str(offline / "herramientas/scripts/verify_stability_uncertainty.py"),
                "--candidate",
                str(offline),
                "--output",
                str(output),
                "--forbid-root",
                str(data_root),
                "--forbid-root",
                str(ROOT),
            ],
            audit / "verificacion_offline.txt",
            cwd=offline_root,
        )
        result = read(output)
        if result.get("passed") is not True or result["sealed"]["manifest_sha256"] != sha(
            final / "manifiesto_paquete.json"
        ):
            raise ValueError("Corrected final offline verification did not pass")
        shutil.copyfile(output, audit / "verificacion_offline.json")
        save(
            audit / "tiempos_verificacion.json",
            dict(
                **timing,
                offline_copy=str(offline),
                successful_full_offline_runs=1,
                prior_aborted_preflight=1,
            ),
        )
        if verify_seal(previous)["manifest_sha256"] != previous_seal["manifest_sha256"]:
            raise ValueError("Prior seal changed during repair")
        if sha(ROOT / ".git/index") != protocol["index_sha256"]:
            raise ValueError("User index changed; stop closure without touching it")
        save(
            audit / "preservacion.json",
            dict(
                passed=True,
                previous_manifest_sha256=previous_seal["manifest_sha256"],
                analytical_members_unchanged=len(preserved),
                index_sha256=protocol["index_sha256"],
                engine_code_hash=protocol["engine_code_hash"],
                economic_replays=0,
            ),
        )
        update_indices(candidate, final, audit)
        result = dict(
            status="completado",
            passed=True,
            final_package=str(final),
            candidate=str(candidate),
            audit=str(audit),
            pid=None,
            completed_utc=datetime.now(UTC).isoformat(),
            manifest_sha256=sha(final / "manifiesto_paquete.json"),
            previous_attempt=str(previous),
            previous_attempt_status="fallido_preservado_no_vigente",
            transversal_review="pendiente",
            word_pdf="pendiente",
        )
        save(closure, result)
        progress = read(candidate / "progreso_local.json")
        progress.update(
            status="completado",
            pid=None,
            active=[],
            stage_pid=None,
            finished_utc=result["completed_utc"],
            final_package=str(final),
        )
        progress.pop("reason", None)
        progress["stages"].append(
            dict(
                stage="repair_export_and_verify",
                exit_code=0,
                seconds=time.monotonic() - started,
                audit=str(audit),
            )
        )
        save(candidate / "progreso_local.json", progress)
        save(
            base / "estado_intentos.json",
            dict(
                unique_final=str(final),
                final_status="verificado",
                preserved_failed_attempt=str(previous),
                previous_seal_unchanged=True,
                no_cleanup=True,
                no_archiving=True,
            ),
        )
        print(json.dumps(result, ensure_ascii=False), flush=True)
    finally:
        lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
        lock.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, default=Path("D:/Backtesting"))
    args = parser.parse_args()
    repair(args.candidate, args.data_root)
