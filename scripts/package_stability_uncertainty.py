"""Finish B6 locally after the four jobs: QA, one seal, one clean offline verification."""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path

for _key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_key] = "1"
os.environ.update(PYTHONDONTWRITEBYTECODE="1", MPLBACKEND="Agg", PYTHONIOENCODING="utf-8")
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from scripts.stability_uncertainty_contract import (  # noqa: E402
    BASES,
    TASKS,
    read,
    save,
    sha,
    verify_contract,
)
from scripts.verify_stability_uncertainty import seal, verify_seal  # noqa: E402


def execute(command, log, cwd=ROOT):
    started = time.monotonic()
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("w", encoding="utf-8") as stream:
        result = subprocess.run(
            command,
            cwd=cwd,
            stdout=stream,
            stderr=subprocess.STDOUT,
            env=os.environ.copy(),
            creationflags=subprocess.CREATE_NO_WINDOW,
            check=False,
        )
    if result.returncode:
        raise RuntimeError(f"Command failed ({result.returncode}); inspect {log}")
    return dict(command=command, exit_code=0, seconds=time.monotonic() - started, log=str(log))


def snapshot_tools(candidate):
    """Local existing Python helpers plus complete economic source identity; no data packages."""
    target = candidate / "herramientas"
    for folder in ("src", "scripts"):
        for source in sorted((ROOT / folder).rglob("*.py")):
            if "__pycache__" in source.parts:
                continue
            out = target / source.relative_to(ROOT)
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, out)
    for name in ("pyproject.toml", "uv.lock"):
        shutil.copyfile(ROOT / name, target / name)
    for source in sorted((ROOT / "tests/unit").glob("test_stability*.py")):
        out = target / "tests/unit" / source.name
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, out)
    for name in ("tests/conftest.py", "scripts/Start-B6.ps1"):
        out = target / name
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, out)


def documents(candidate, states, checks):
    from scripts.continuous_delivery.common import write_rows
    from scripts.stability_uncertainty_report import render_report

    render_report(candidate)
    resource_path = candidate / "controles/coordinacion_local/recursos.jsonl"
    resources = [
        json.loads(line) for line in resource_path.read_text(encoding="utf-8").splitlines() if line
    ]
    rows = [
        dict(
            stage="replay",
            scenario=s["scenario"],
            strategy=s["strategy"],
            run_id=s["run_id"],
            seconds=s["replay_seconds"],
            total_seconds=s["total_seconds"],
            peak_memory_gib=s["peak_process_bytes"] / 2**30,
            start=s["started_utc"],
            end=s["finished_utc"],
        )
        for s in states
    ]
    write_rows(candidate / "tablas/tiempos_corridas.csv", rows)
    summary = dict(
        physical_cores=resources[0]["physical"],
        logical_cores=resources[0]["logical"],
        observed_total_gib=resources[0]["total_gib"],
        max_simultaneous_portfolios=max(len(r["active"]) for r in resources),
        min_available_gib=min(r["available_gib"] for r in resources),
        max_cpu_percent=max(r["cpu"] or 0 for r in resources),
        max_paging_mbps=max(r["paging_mbps"] or 0 for r in resources),
        min_disk_free_gib=min(r["disk_free_gib"] for r in resources),
        worker_budget_gib=4,
        reserve_gib=6,
        thread_count_per_pool=1,
        samples=len(resources),
        measurement="Observed while useful portfolios advanced; no profiling replay",
        development=read(candidate / "controles/desarrollo_listo.json"),
        checks=checks,
        offline_verification_timing="Recorded externally after final seal",
    )
    save(candidate / "controles/recursos_y_tiempos.json", summary)
    compliance = [
        (
            "matrix",
            "Four portfolios only, I2023/I2024 x both strategies",
            "indice_corridas.json",
            "verificado",
        ),
        (
            "economic_identity",
            "Corrected engine; only start changed",
            "protocolo_ejecucion.json",
            "verificado",
        ),
        (
            "initial_state",
            "Cash restart, 360h preload, causal funding and exclusive end",
            "controles/puerta_pruebas.json",
            "verificado",
        ),
        (
            "accounting",
            "Ledger, funding, fees, positions, daily and period reconciliation 1E-8",
            "resultados/financiero.json",
            "verificado",
        ),
        (
            "execution",
            "VWAP windows, quantity and participation with compact witnesses",
            "evidencia/financiera/indice.json",
            "verificado",
        ),
        (
            "statistics",
            "BASE only, 5000 per length, paired circular yearly segments",
            "estadistica",
            "recalculo_offline_externo",
        ),
        (
            "synthesis",
            "Historical exceptions and targeted B2/B3 diagnosis",
            "sintesis.md",
            "evidencia_con_alcance_declarado",
        ),
        (
            "offline",
            "One clean final copy; accounting and bootstrap recalculated",
            "../controles_finales/verificacion_offline.json",
            "resultado_externo",
        ),
        (
            "index",
            "No Git index, commits, pushes or cleanup",
            "controles/preservacion_pre_sello.json",
            "verificado",
        ),
        (
            "transversal",
            "Cross-version review and Word/PDF remain pending",
            "sintesis.md",
            "pendiente",
        ),
    ]
    write_rows(
        candidate / "matriz_cumplimiento.csv",
        [dict(requirement=a, scope=b, evidence=c, status=d) for a, b, c, d in compliance],
    )
    text = """# B6: estabilidad temporal e incertidumbre

Este candidato mantiene cuatro cuentas nuevas I2023/I2024 y evidencia compacta de BASE continua.
El reporte distingue cuentas nuevas y tramos heredados; los inicios alternativos no son fuera de muestra.

- [Reporte](reporte.md) y [versión HTML](reporte.html).
- [Síntesis](sintesis.md), [cumplimiento](matriz_cumplimiento.csv) y [corridas](indice_corridas.json).
- [Protocolo previo](protocolo_ejecucion.json).
- [Recursos y tiempos](controles/recursos_y_tiempos.json).
- La certificación final independiente se escribe en `../controles_finales/verificacion_offline.json`.

No se repitieron BASE ni B1-B5; no se ejecutó el motor en el bootstrap. Las 28/14/56 jornadas,
5.000 réplicas, semilla y estratificación anual son decisiones del estudio fijadas en el protocolo.
El paquete conserva los bytes de entradas compactas y el código compartido del cálculo/verificación.
Las particiones masivas de mercado y archivos de descarga quedan identificados en el inventario;
no se vuelven a leer offline. Se incluyen las ventanas mínimas necesarias para auditar fills.

Verificación autónoma con el intérprete fijado del proyecto (Python 3.14, versiones de `uv.lock`),
desde cualquier directorio, sin red ni D:/Backtesting:

```powershell
& 'C:/Users/pablo/Documentos/UCEMA/Tesina/Backtesting/.venv/Scripts/python.exe' -B -I -X utf8 '<paquete>/herramientas/scripts/verify_stability_uncertainty.py' --candidate '<paquete>' --output '<ruta externa>/verificacion.json'
```

El sello cubre cada archivo incluido. La verificación externa queda fuera del propio sello para no
crear una dependencia circular ni sobrescribirlo. Su JSON identifica el SHA-256 del manifiesto.
No se modificó el índice de Git ni se publicó el trabajo. Revisión transversal y Word/PDF pendientes.
"""
    (candidate / "README.md").write_text(text, encoding="utf-8", newline="\n")


def verify_exported_code(package):
    """Require both exported snapshots to retain the entire recorded code identity."""
    protocol = read(package / "protocolo_ejecucion.json")
    for folder in ("herramientas", "codigo_ejecutado"):
        for name, expected in protocol["code_files"].items():
            path = package / folder / name
            if not path.is_file() or sha(path) != expected:
                raise ValueError(f"Exported code missing or changed before seal: {folder}/{name}")


def copy_final(candidate, final):
    if (final / "manifiesto_paquete.json").exists():
        raise FileExistsError("A final seal already exists; it will not be overwritten")
    final.mkdir(parents=True, exist_ok=True)
    for source in sorted(candidate.rglob("*")):
        if not source.is_file():
            continue
        rel = source.relative_to(candidate)
        if (
            source.suffix == ".tmp"
            or (source.suffix == ".lock" and rel.parts[0] == "ejecuciones")
            or "__pycache__" in rel.parts
            or rel.as_posix()
            in {"progreso_local.json", "coordinador_stdout.txt", "coordinador_stderr.txt"}
            or source.name.startswith("finalize__")
        ):
            continue
        out = final / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        if out.exists() and sha(out) != sha(source):
            raise ValueError("Unsealed partial final differs; preserve and inspect: " + str(out))
        if not out.exists():
            shutil.copyfile(source, out)
    if (final / "protocolo_ejecucion.json").is_file():
        verify_exported_code(final)


def update_indices(candidate, final, audit):
    matrix = ROOT / "docs/entrega_4/matriz_avance.csv"
    with matrix.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fields = reader.fieldnames
        rows = list(reader)
    backup = audit / "matriz_avance_previa.csv"
    if not backup.exists():
        shutil.copyfile(matrix, backup)
    final_relative = final.relative_to(ROOT).as_posix()
    synthesis = read(candidate / "fuentes/sintesis_estado.json")
    for row in rows:
        if row["id"] == "B6":
            row.update(
                estado="ejecutado",
                paquete_vigente=final_relative,
                evidencia=final_relative
                + "/reporte.md; "
                + final_relative
                + "/sintesis.md; "
                + (audit / "verificacion_offline.json").relative_to(ROOT).as_posix(),
                limitacion="Inicios retrospectivos; bootstrap marginal con supuestos por año; revisión transversal y Word/PDF pendientes",
                actualizado_utc=datetime.now(UTC).isoformat(),
                publicacion="local; sin commit/push ni cambios del índice",
            )
        elif row["id"] == "ALCANCE_REPARACION_B2_B3":
            pending = synthesis["diagnostic_pending_run_ids"]
            excluded = synthesis["diagnostic_statuses"].get("rama_no_activada", 0)
            row.update(
                estado="ejecutado" if excluded == 28 and not pending else "pendiente",
                paquete_vigente=final_relative,
                evidencia=final_relative
                + "/tablas/diagnostico_b2_b3_corridas.csv; "
                + final_relative
                + "/sintesis.md",
                limitacion=(
                    "Sólo 28 variantes B2/B3 autenticadas; precondición liquidation_pending "
                    "excluida por registros completos y código; no equivalencia universal ni replay"
                    if excluded == 28 and not pending
                    else "Diagnóstico limitado a registros incluidos; corridas pendientes: "
                    + "; ".join(pending)
                ),
                actualizado_utc=datetime.now(UTC).isoformat(),
                publicacion="local; diagnóstico sin nuevas corridas",
            )
    temp = matrix.with_name(matrix.name + ".b6.tmp")
    with temp.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temp, matrix)
    index = ROOT / "entregas/entrega_4/estabilidad_incertidumbre/indice_versiones.json"
    if index.exists():
        shutil.copyfile(index, audit / "indice_versiones_previo.json")
    save(
        index,
        dict(
            status="ejecutado",
            candidate=str(candidate),
            final_package=str(final),
            verification=str(audit / "verificacion_offline.json"),
            manifest_sha256=sha(final / "manifiesto_paquete.json"),
            transversal_review="pendiente",
            word_pdf="pendiente",
            utc=datetime.now(UTC).isoformat(),
        ),
    )


def finalize(candidate, data_root):
    candidate = candidate.resolve()
    final = candidate.parent / "paquete_final"
    audit = candidate.parent / "controles_finales"
    closure = candidate.parent / "cierre_actual.json"
    if closure.is_file() and read(closure).get("status") == "completado":
        closed = read(closure)
        final = Path(closed.get("final_package", final)).resolve()
        audit = Path(closed.get("audit", audit)).resolve()
        if final.parent != candidate.parent or audit.parent != candidate.parent:
            raise ValueError("Completed closure points outside this B6 delivery")
    audit.mkdir(exist_ok=True)
    if final.exists() and (final / "manifiesto_paquete.json").exists():
        if (audit / "verificacion_offline.json").exists() and read(
            audit / "verificacion_offline.json"
        )["passed"]:
            sealed = verify_seal(final)
            external = read(audit / "verificacion_offline.json")
            if (
                external.get("passed") is not True
                or external.get("sealed", {}).get("manifest_sha256") != sealed["manifest_sha256"]
            ):
                raise ValueError("Existing audit does not authenticate this final seal")
            closed = read(closure)
            if (
                closed.get("status") != "completado"
                or closed.get("passed") is not True
                or closed.get("manifest_sha256") != sealed["manifest_sha256"]
            ):
                raise ValueError(
                    "Existing closure is incomplete/blocked; no false success or second offline run"
                )
            return closed
        raise ValueError(
            "Existing final seal without passed offline control; do not overwrite or repeat automatically"
        )
    try:
        gate = read(candidate / "controles/desarrollo_listo.json")
        if not gate["passed"]:
            raise ValueError("Development/review gate incomplete")
        for name, expected in gate["files"].items():
            if sha(ROOT / name) != expected:
                raise ValueError("Reviewed B6 implementation changed: " + name)
        protocol = verify_contract(candidate)
        if sha(ROOT / ".git/index") != protocol["index_sha256"]:
            raise ValueError("Git index changed during work; preserve user changes, stop closure")
        states = [read(candidate / "ejecuciones" / ("__".join(t) + ".json")) for t in TASKS]
        from scripts.run_stability_uncertainty import validate_completed

        for task, state in zip(TASKS, states):
            validate_completed(state, candidate, data_root, *task)
            target = candidate / "fuentes/corridas" / ("__".join(task)) / "run_manifest.json"
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(Path(state["path"]) / "run_manifest.json", target)
        save(candidate / "indice_corridas.json", states)
        for strategy, rid in BASES.items():
            shutil.copyfile(
                data_root / "outputs" / rid / "run_manifest.json",
                candidate / "fuentes" / f"BASE_manifest_{strategy}.json",
            )
        shutil.copyfile(
            data_root / "outputs" / BASES["conditional"] / "effective_config.toml",
            candidate / "fuentes/base_config.toml",
        )
        tests = sorted(
            p.relative_to(ROOT).as_posix() for p in (ROOT / "tests/unit").glob("test_stability*.py")
        )
        tests += [
            "tests/unit/test_rules_sensitivity_h2.py",
            "tests/unit/test_cost_capacity_ledger.py",
            "tests/unit/test_execution_delays_audit.py",
        ]
        python = [sys.executable, "-B", "-X", "utf8"]
        qa_dir = candidate / "controles"
        junit = qa_dir / "regresion_final.xml"
        checks = [
            execute(
                [
                    *python,
                    "-m",
                    "pytest",
                    *tests,
                    "-q",
                    "-p",
                    "no:cacheprovider",
                    "--junitxml",
                    str(junit),
                ],
                qa_dir / "regresion_final.txt",
            )
        ]
        xml = ET.parse(junit)
        counts = {
            key: sum(int(s.get(key, 0)) for s in xml.getroot().iter("testsuite"))
            for key in ("tests", "failures", "errors", "skipped")
        }
        if counts["failures"] or counts["errors"]:
            raise ValueError("Regression failed")
        paths = [n for n in gate["files"] if n.endswith(".py")]
        checks.append(
            execute(
                [*python, "-m", "ruff", "check", "--no-cache", *paths], qa_dir / "ruff_final.txt"
            )
        )
        save(
            qa_dir / "regresion_final.json",
            dict(
                passed=True,
                counts=counts,
                checks=checks,
                note="Skipped tests are not passes; suites from prior sealed blocks not rerun",
            ),
        )
        save(
            qa_dir / "preservacion_pre_sello.json",
            dict(
                passed=True,
                index_sha256=sha(ROOT / ".git/index"),
                expected_index_sha256=protocol["index_sha256"],
                engine_code_hash=protocol["engine_code_hash"],
                base_replays=0,
                cleanup=False,
                commit=False,
                push=False,
            ),
        )
        documents(candidate, states, checks)
        snapshot_tools(candidate)
        save(
            qa_dir / "coordinacion_local/estado_al_sellar.json",
            read(candidate / "progreso_local.json"),
        )
        copy_final(candidate, final)
        seal(final)
        save(
            closure,
            dict(
                status="verificacion_offline",
                pid=os.getpid(),
                candidate=str(candidate),
                final_package=str(final),
                audit=str(audit),
            ),
        )
        # Exactly one full independent copy; preserve it and its outputs even on failure.
        offline_root = Path(tempfile.gettempdir()) / ("b6_offline_" + candidate.parent.name)
        offline = offline_root / "paquete"
        if offline.exists():
            raise FileExistsError(
                "Offline destination already exists; preserve it without an automatic second full run"
            )
        shutil.copytree(final, offline)
        output = offline_root / "verificacion_offline.json"
        command = [
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
        ]
        timing = execute(command, audit / "verificacion_offline.txt", cwd=offline_root)
        result = read(output)
        if not result["passed"] or result["sealed"]["manifest_sha256"] != sha(
            final / "manifiesto_paquete.json"
        ):
            raise ValueError("Offline final verification did not pass")
        shutil.copyfile(output, audit / "verificacion_offline.json")
        save(
            audit / "tiempos_verificacion.json",
            dict(**timing, offline_copy=str(offline), full_offline_runs=1),
        )
        if sha(ROOT / ".git/index") != protocol["index_sha256"]:
            raise ValueError("User index drifted; verification preserved, global update stopped")
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
            transversal_review="pendiente",
            word_pdf="pendiente",
        )
        save(closure, result)
        return result
    except Exception as exc:
        save(
            closure,
            dict(
                status="bloqueado",
                passed=False,
                candidate=str(candidate),
                final_package=str(final),
                pid=None,
                reason=f"{type(exc).__name__}: {exc}",
                utc=datetime.now(UTC).isoformat(),
            ),
        )
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--data-root", default=Path("D:/Backtesting"), type=Path)
    args = parser.parse_args()
    print(json.dumps(finalize(args.candidate, args.data_root), ensure_ascii=False))
