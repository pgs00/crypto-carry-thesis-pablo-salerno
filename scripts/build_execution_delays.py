"""Build block-4 compact evidence in a new destination; never overwrites a package."""

from __future__ import annotations

import argparse
import gzip
import json
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT/"src"))

from crypto_carry.config import Config  # noqa: E402
from crypto_carry.reporting import verify_run  # noqa: E402
from scripts.build_signal_sensitivity import RAW_FILES, snapshot_tools  # noqa: E402
from scripts.build_signal_sensitivity import write_table as write_raw_table  # noqa: E402
from scripts.distribution_integrity import original_manifest_path  # noqa: E402
from scripts.execution_delays import BASES, CHANGES, validate_variant  # noqa: E402
from scripts.execution_delays_incidents import (  # noqa: E402
    attach_cases,
    extract_case_sources,
    select_cases,
    write_sources,
)
from scripts.execution_delays_report import (  # noqa: E402
    consolidate,
    derive_portfolio,
    h3_replay_invariance,
)
from scripts.execution_delays_sources import extract_windows  # noqa: E402
from scripts.report_historical_rules_sensitivity import write_csv  # noqa: E402
from scripts.return_capital.common import (  # noqa: E402
    parquet,
    read_csv,
    read_json,
    sha256,
    write_json,
)
from scripts.signal_sensitivity_integrity import (  # noqa: E402
    reject_overlaps,
    reject_sealed_ancestor,
)

PREVIOUS = ROOT/"entregas/entrega_4/senal_entradas/20260927T170230Z/distribucion_20261010"
FILES = RAW_FILES + ("forecast_evaluation.csv",)


def write_table(package, name, rows):
    # CSV must use the same explicit nested-value format as Parquet and verifier.
    normalized = [{k: json.dumps(v, ensure_ascii=False, separators=(",", ":"), default=str)
                   if isinstance(v, (list, dict)) else v for k, v in row.items()}
                  for row in rows]
    write_raw_table(package, name, normalized)
    if name != 'decisiones':
        import pyarrow as pa
        import pyarrow.parquet as pq
        columns=list(dict.fromkeys(k for r in normalized for k in r))
        values=[{k:'' if r.get(k) is None else str(r[k]) for k in columns} for r in normalized]
        pq.write_table(pa.Table.from_pylist(values,schema=pa.schema([(k,pa.string()) for k in columns])),
                       package/'tablas'/(name+'.parquet'),compression='zstd')


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
            from scripts.execution_delays import STAGES
            stage = next(k for k, names in STAGES.items() if scenario in names)
            if not read_json(work/('control_etapa_'+stage+'.json'))['passed']:
                raise ValueError('Scenario stage audit has not passed')
            batch = read_json(work/('etapa_'+stage+'.json'))
            execution = next(r for r in batch['runs'] if r['scenario']==scenario and r['strategy']==strategy)
            if execution['run_id'] != state['run_id'] or execution['exit_code'] != 0:
                raise ValueError('Batch identity differs from execution state')
            state.update({k:execution[k] for k in ('command','log','exit_code')})
            runs.append(state)
    return runs


def snapshot(destination):
    snapshot_tools(destination)
    # Include helper dependencies and tiny test fixtures, not previous packages.
    for folder in ('scripts','tests'):
        for p in (ROOT/folder).rglob('*'):
            if p.is_file() and '__pycache__' not in p.parts and p.suffix in {'.py','.json','.csv','.toml','.yaml','.yml'}:
                target = destination/'herramientas'/p.relative_to(ROOT)
                target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(p,target)
    for p in (ROOT/"configs").rglob("*.toml"):
        target = destination/"herramientas"/p.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(p, target)


def seal(destination):
    reject_sealed_ancestor(destination)
    manifest = destination/"manifiesto_paquete.json"
    if manifest.exists():
        raise FileExistsError("Already sealed")
    index = read_json(destination/"indice_corridas.json")
    if len(index["runs"]) != 14 or index.get("partial"):
        raise ValueError("Only all 14 required results can be sealed")
    members = [dict(path=p.relative_to(destination).as_posix(), bytes=p.stat().st_size, sha256=sha256(p))
               for p in sorted(destination.rglob("*")) if p.is_file()]
    write_json(manifest, dict(schema="execution_delays_sensitivity_v1", created_at=datetime.now(UTC).isoformat(),
        economic_replays=12, economic_replay_scope='six-scenario matrix only',
        separate_base_control_replays=2, reused_results=2, members=members,
        scope="Persisted accounting/execution/hypotheses; no replay, no claims about Git publication"))
    (destination/"manifiesto_paquete.sha256").write_text(sha256(manifest)+"\n", encoding="ascii")


def build(work, data, destination, partial=False):
    from scripts.execution_delays_docs import write_docs

    if destination.exists():
        raise FileExistsError("Choose a new version")
    reject_sealed_ancestor(destination)
    runs = collect_runs(work, data, partial)
    dependencies = read_json(work/"autenticacion_referencias.json")
    reject_overlaps(destination, [r["path"] for r in runs+dependencies]+[data/"data"])
    destination.mkdir(parents=True)
    references = destination/"hipotesis_base"
    shutil.copytree(PREVIOUS/"hipotesis/BASE_E3", references)
    (destination/"referencias").mkdir()
    shutil.copyfile(original_manifest_path(PREVIOUS), destination/"referencias/manifiesto_bloque2.json")
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
            compressed = name == "forecast_evaluation.csv"
            saved = target/(name+".gz" if compressed else name)
            if compressed:
                saved.write_bytes(gzip.compress((run/name).read_bytes(), mtime=0))
            else:
                shutil.copyfile(run/name, saved)
            sources.append(dict(run_id=item["run_id"], source_name=name,
                package_path=saved.relative_to(destination).as_posix(),
                sha256=sha256(saved), bytes=saved.stat().st_size,
                source_sha256=sha256(run/name), source_bytes=(run/name).stat().st_size,
                transfer="lossless_gzip" if compressed else "exact_bytes"))
        windows = extract_windows(data, config, parquet(run/"orders.parquet"), inputs)
        write_json(destination/"fuentes/volumen"/(item["run_id"]+".json"), windows)
        record = dict(item, original_path_hint=str(run), path=target.relative_to(destination).as_posix())
        manifest = read_json(run/"run_manifest.json")
        record["input_protocol_sha256"] = manifest["input_hashes"].get("execution_delays_protocol_sha256")
        result=derive_portfolio(target, record, windows,destination/"evidencia"/BASES[item["strategy"]])
        if item['scenario']!='BASE_E3':
            control=read_json(work/'controles_base'/('CONTROL_BASE__'+item['strategy']+'.json'))
            if sha256(Path(item['h3_path']))!=item['h3_sha256']:
                raise ValueError('Replay H3 export changed')
            saved=destination/'fuentes/h3_replay'/(item['run_id']+'.csv')
            saved.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(item['h3_path'],saved)
            result['invariancias'][0].update(h3_replay_invariance(read_csv(saved),read_csv(Path(control['h3_path'])),
                result['invariancias'][0]['full_observed_coverage']))
        cases=select_cases(result['episodios_descubiertos'],result['exposicion_intervalos'],config)
        case_sources=extract_case_sources(data,config,cases,inputs)
        write_sources(destination/'fuentes/incidentes'/(item['run_id']+'.parquet'),case_sources)
        table_sets.append(attach_cases(result,target,record,case_sources))
        index.append(record)
        print("CONCILIADO", item["scenario"], item["strategy"], flush=True)
    tables = consolidate(table_sets, read_csv(references/"h3_diario.csv"), base_config)
    for name, rows in tables.items():
        write_table(destination, name, rows)
    write_json(destination/"indice_corridas.json", dict(schema="execution_delays_batch_v1", partial=partial, runs=index))
    write_csv(destination/"fuentes/archivos_originales.csv", sources)
    docs = destination/"documentos"
    docs.mkdir()
    for name in ("protocolo.md", "protocolo_previo.json",
                 "preservacion_previa.json", "input_hashes.json",
                 "control_compatibilidad.json", "control_compatibilidad_base_completa.json",
                 "autenticacion_referencias.json", "verificacion_datos.json",
                 "verificacion_base_previa.json", "registro_escenarios_previo.json", "recursos_antes.json",
                 "recursos_concurrencia.json", "coordinacion_etapas.json"):
        shutil.copyfile(work/name, docs/name)
    for p in work.glob("protocolo_previo_v*.json"):
        shutil.copyfile(p, docs/p.name)
    for name in ("gitattributes_original.bin", "gitattributes_adicion.txt"):
        if (work/name).exists():
            shutil.copyfile(work/name, docs/name)
    shutil.copytree(work/"configuraciones", docs/"configuraciones")
    shutil.copytree(work/"controles", docs/"controles")
    shutil.copytree(work/"controles_base", destination/"controles_base")
    for state_path in (work/'controles_base').glob('CONTROL_BASE__*.json'):
        state=read_json(state_path)
        if state['status']!='ejecutado':
            raise ValueError('Incomplete BASE control')
        folder=destination/'evidencia_control'/state['run_id']
        folder.mkdir(parents=True)
        if sha256(Path(state['h3_path']))!=state['h3_sha256']:
            raise ValueError('Control H3 export changed')
        shutil.copyfile(state['h3_path'],folder/'h3_replay.csv')
        for name in FILES:
            original=Path(state['path'])/name
            if name=='forecast_evaluation.csv':
                (folder/(name+'.gz')).write_bytes(gzip.compress(original.read_bytes(),mtime=0))
            else:
                shutil.copyfile(original,folder/name)
    folders = ["codigo_previo", "codigo_ejecutado", "pruebas", "controles"]
    if (work/'logs_originales_binarios').is_dir():
        folders.append('logs_originales_binarios')
    folders.extend(p.name for p in sorted(work.glob("codigo_runner_v*")) if p.is_dir())
    for folder in folders:
        shutil.copytree(work/folder, destination/folder,
                        ignore=shutil.ignore_patterns('__pycache__','.ruff_cache','.pytest_cache'))
    execution = destination/"ejecucion"
    execution.mkdir()
    for name in ("ejecuciones", "logs_corridas"):
        shutil.copytree(work/name, execution/name)
    for p in work.glob("*etapa*.*"):
        shutil.copyfile(p, execution/p.name)
    write_json(destination/"dependencias.json", dict(previous=read_json(work/"autenticacion_referencias.json"),
        data_root_hint=str(data), included="Selected original run bytes, separate full BASE controls, eligible execution windows and bounded incident price extracts",
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
