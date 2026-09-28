"""Build block-3 compact evidence in a new destination; never overwrites a package."""

from __future__ import annotations

import argparse
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT/"src"))

from crypto_carry.config import Config  # noqa: E402
from crypto_carry.reporting import verify_run  # noqa: E402
from scripts.build_signal_sensitivity import RAW_FILES, snapshot_tools, write_table  # noqa: E402
from scripts.cost_capacity import BASES, CHANGES, validate_variant  # noqa: E402
from scripts.cost_capacity_report import consolidate, derive_portfolio  # noqa: E402
from scripts.cost_capacity_sources import extract_windows  # noqa: E402
from scripts.report_historical_rules_sensitivity import write_csv  # noqa: E402
from scripts.return_capital.common import (  # noqa: E402
    parquet,
    read_csv,
    read_json,
    sha256,
    write_json,
)
from scripts.signal_sensitivity_integrity import reject_overlaps  # noqa: E402

PREVIOUS = ROOT/"entregas/entrega_4/senal_entradas/20260927T170230Z/paquete_20260927T185305Z"
FILES = RAW_FILES + ("forecast_evaluation.csv",)


def collect_runs(work, data, partial=False):
    runs = []
    for strategy, rid in BASES.items():
        run = data/"outputs"/rid
        manifest = read_json(run/"run_manifest.json")
        runs.append(dict(scenario="BASE_E3", strategy=strategy, run_id=rid, path=str(run),
            status="reutilizado_verificado", engine_status=manifest["status"],
            code_hash=manifest["code_hash"], manifest_sha256=sha256(run/"run_manifest.json")))
    for scenario in CHANGES:
        for strategy in BASES:
            path = work/"ejecuciones"/f"{scenario}__{strategy}.json"
            state = read_json(path) if path.exists() else {}
            if state.get("status") != "ejecutado":
                if partial:
                    continue
                raise ValueError(f"Unfinished scenario retained: {scenario}/{strategy}")
            runs.append(state)
    return runs


def snapshot(destination):
    snapshot_tools(destination)
    names = ["cost_capacity.py", "cost_capacity_guards.py", "cost_capacity_audit.py",
             "cost_capacity_sources.py", "cost_capacity_report.py", "cost_capacity_docs.py",
             "run_cost_capacity.py", "prepare_cost_capacity.py", "check_cost_capacity_compatibility.py",
             "audit_cost_capacity_stage.py", "build_cost_capacity.py", "verify_cost_capacity.py"]
    for name in names:
        shutil.copyfile(ROOT/"scripts"/name, destination/"herramientas/scripts"/name)
    for p in (ROOT/"tests").rglob("*.py"):
        target = destination/"herramientas"/p.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(p, target)
    for p in (ROOT/"configs").rglob("*.toml"):
        target = destination/"herramientas"/p.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(p, target)


def seal(destination):
    manifest = destination/"manifiesto_paquete.json"
    if manifest.exists():
        raise FileExistsError("Already sealed")
    index = read_json(destination/"indice_corridas.json")
    if len(index["runs"]) != 18 or index.get("partial"):
        raise ValueError("Only all 18 required results can be sealed")
    members = [dict(path=p.relative_to(destination).as_posix(), bytes=p.stat().st_size, sha256=sha256(p))
               for p in sorted(destination.rglob("*")) if p.is_file()]
    write_json(manifest, dict(schema="cost_capacity_sensitivity_v1", created_at=datetime.now(UTC).isoformat(),
        economic_replays=16, reused_results=2, members=members,
        scope="Persisted accounting/execution/hypotheses; no replay, no claims about Git publication"))
    (destination/"manifiesto_paquete.sha256").write_text(sha256(manifest)+"\n", encoding="ascii")


def build(work, data, destination, partial=False):
    from scripts.cost_capacity_docs import write_docs

    if destination.exists():
        raise FileExistsError("Choose a new version")
    runs = collect_runs(work, data, partial)
    reject_overlaps(destination, [r["path"] for r in runs]+[data/"data", PREVIOUS])
    destination.mkdir(parents=True)
    references = destination/"hipotesis_base"
    shutil.copytree(PREVIOUS/"hipotesis/BASE_E3", references)
    (destination/"referencias").mkdir()
    shutil.copyfile(PREVIOUS/"manifiesto_paquete.json", destination/"referencias/manifiesto_bloque2.json")
    shutil.copytree(PREVIOUS/"codigo_referencia", destination/"codigo_referencia_base")
    inputs = read_json(work/"input_hashes.json")
    base_config = Config.load(data/"outputs"/BASES["conditional"]/"effective_config.toml")
    table_sets, index, sources = [], [], []
    for item in runs:
        run = Path(item["path"])
        if not verify_run(run)["valid"] or sha256(run/"run_manifest.json") != item["manifest_sha256"]:
            raise ValueError("Original run authentication failed")
        config = Config.load(run/"effective_config.toml")
        if item["scenario"] != "BASE_E3":
            validate_variant(base_config, item["scenario"], config)
        target = destination/"evidencia"/item["run_id"]
        target.mkdir(parents=True)
        for name in FILES:
            shutil.copyfile(run/name, target/name)
            sources.append(dict(run_id=item["run_id"], source_name=name,
                package_path=(target/name).relative_to(destination).as_posix(),
                sha256=sha256(run/name), bytes=(run/name).stat().st_size, transfer="exact_bytes"))
        windows = extract_windows(data, config, parquet(run/"orders.parquet"), inputs)
        write_json(destination/"fuentes/volumen"/(item["run_id"]+".json"), windows)
        record = dict(item, original_path_hint=str(run), path=target.relative_to(destination).as_posix())
        manifest = read_json(run/"run_manifest.json")
        record["input_protocol_sha256"] = manifest["input_hashes"].get("cost_capacity_protocol_sha256")
        table_sets.append(derive_portfolio(target, record, windows,
            destination/"evidencia"/BASES[item["strategy"]]))
        index.append(record)
        print("CONCILIADO", item["scenario"], item["strategy"], flush=True)
    tables = consolidate(table_sets, read_csv(references/"h3_diario.csv"), base_config)
    for name, rows in tables.items():
        write_table(destination, name, rows)
    write_json(destination/"indice_corridas.json", dict(schema="cost_capacity_batch_v1", partial=partial, runs=index))
    write_csv(destination/"fuentes/archivos_originales.csv", sources)
    docs = destination/"documentos"
    docs.mkdir()
    for name in ("encargo_usuario.md", "protocolo.md", "plan.md", "progreso.md", "protocolo_previo.json",
                 "protocolo_previo_v1.json", "preservacion_previa.json", "input_hashes.json",
                 "control_compatibilidad.json", "autenticacion_referencias.json", "verificacion_datos.json",
                 "verificacion_base_previa.json", "registro_escenarios_previo.json", "recursos_antes.json"):
        shutil.copyfile(work/name, docs/name)
    shutil.copytree(work/"configuraciones", docs/"configuraciones")
    for folder in ("codigo_previo", "codigo_ejecutado", "codigo_runner_v2", "pruebas", "controles"):
        shutil.copytree(work/folder, destination/folder)
    execution = destination/"ejecucion"
    execution.mkdir()
    for name in ("ejecuciones", "logs_corridas"):
        shutil.copytree(work/name, execution/name)
    for p in work.glob("*etapa*.*"):
        shutil.copyfile(p, execution/p.name)
    write_json(destination/"dependencias.json", dict(previous=read_json(work/"autenticacion_referencias.json"),
        data_root_hint=str(data), included="Selected exact raw run files and requested execution-volume windows",
        excluded="Massive minute sources, complete raw outputs and prior packages",
        shared_builder_verifier_logic=True, new_intraday_series=False,
        historical_inventory_config_mismatch="Preexisting documented exception; new extension diff tracked separately"))
    snapshot(destination)
    write_docs(destination, tables, index, partial=partial)
    return destination


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--work", type=Path)
    p.add_argument("--data-root", type=Path, default=Path("D:/Backtesting"))
    p.add_argument("--destination", type=Path, required=True)
    p.add_argument("--partial", action="store_true")
    p.add_argument("--seal-only", action="store_true")
    a = p.parse_args()
    if a.seal_only:
        seal(a.destination.resolve())
    else:
        print(build(a.work.resolve(), a.data_root.resolve(), a.destination.resolve(), a.partial))
