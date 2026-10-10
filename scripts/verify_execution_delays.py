"""Read-only portable block-4 verifier; shared postprocessing, no engine replay."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT/"src"))

from crypto_carry.config import DAY, Config, iso  # noqa: E402
from scripts.build_execution_delays import FILES  # noqa: E402
from scripts.distribution_integrity import verify_distribution, verify_frozen_document  # noqa: E402
from scripts.execution_delays import BASES, CHANGES, validate_variant  # noqa: E402
from scripts.execution_delays_incidents import (  # noqa: E402
    attach_cases,
    extract_case_sources,
    select_cases,
)
from scripts.execution_delays_report import (  # noqa: E402
    consolidate,
    derive_portfolio,
    h3_replay_invariance,
)
from scripts.execution_delays_sources import forecast_bytes  # noqa: E402
from scripts.return_capital.common import (  # noqa: E402
    parquet,
    read_csv,
    read_json,
    sha256,
    write_json,
)
from scripts.rules_sensitivity_h2 import validate_h2_rows  # noqa: E402
from scripts.signal_sensitivity_hypotheses import summarize_h3  # noqa: E402
from scripts.signal_sensitivity_integrity import (  # noqa: E402
    digest,
    economic_identity,
    reject_overlaps,
    reject_sealed_ancestor,
)
from scripts.verify_rules_sensitivity_package import (  # noqa: E402
    periods,
    safe_path,
)


def same_rows(actual, expected, label):
    def cell(value):
        if value is None:
            return ""
        if isinstance(value, (list, dict)):
            return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)
        return str(value)
    if len(actual) != len(expected):
        raise ValueError(label+": row count differs")
    for i, (a, b) in enumerate(zip(actual, expected)):
        for key in a.keys() | b.keys():
            if cell(a.get(key)) != cell(b.get(key)):
                raise ValueError(f"{label}/{i}/{key}: value differs")


def verify_preserved_base(package, strategy, run_id, manifest_sha256):
    originals=read_json(package/'documentos/verificacion_base_previa.json')['runs']
    matching=[r for r in originals if r['strategy']==strategy]
    if (len(matching)!=1 or run_id!=BASES[strategy] or matching[0]['run_id']!=run_id or
            matching[0]['manifest_sha256']!=manifest_sha256):
        raise ValueError('Preserved BASE identity differs from frozen original authentication')
    return matching[0]


def verify_reused_hypotheses(package):
    reference_file=package/'referencias/manifiesto_bloque2.json'
    prior=read_json(package/'documentos/autenticacion_referencias.json')
    wanted=next(r['manifest_sha256'] for r in prior if r['dependency']=='block2')
    if sha256(reference_file)!=wanted:
        raise ValueError('Authenticated block-2 reference manifest changed')
    prefix='hipotesis/BASE_E3/'
    expected={m['path'][len(prefix):]:m['sha256']
              for m in read_json(reference_file)['members'] if m['path'].startswith(prefix)}
    folder=package/'hipotesis_base'
    actual={p.relative_to(folder).as_posix() for p in folder.rglob('*') if p.is_file()}
    if actual!=set(expected) or not {'h1_observaciones.csv','h1_resumen.csv'}<=actual:
        raise ValueError('Reused H1/H3 population differs from authenticated original manifest')
    for name,wanted in expected.items():
        if sha256(safe_path(folder,name))!=wanted:
            raise ValueError('Reused H1/H3 BASE evidence changed')
    return len(read_csv(folder/'h1_observaciones.csv'))


def verify_identity(package, item, base, inputs, protocols):
    run = safe_path(package, item["path"])
    manifest = read_json(run/"run_manifest.json")
    if sha256(run/"run_manifest.json") != item["manifest_sha256"]:
        raise ValueError("Run manifest identity changed")
    if (run/"run_manifest.sha256").read_text().strip() != item["manifest_sha256"]:
        raise ValueError("Run manifest sidecar changed")
    strategy, scenario = item["strategy"], item["scenario"]
    if manifest["strategies"] != [dict(strategy=strategy, funding_filter_enabled=strategy == "conditional")]:
        raise ValueError("Portfolio strategy/filter mismatch")
    if item["engine_status"] != manifest["status"] or manifest["status"] not in {"complete", "insolvent"}:
        raise ValueError("Economic completion status changed")
    config = Config.load(run/"effective_config.toml")
    if config.to_dict() != manifest["config"]:
        raise ValueError("Effective configuration differs from run")
    identity = {k: manifest[k] for k in ("config", "code_hash", "input_hashes", "strategies", "data_kind", "label")}
    if "run_"+digest(identity)[:24] != item["run_id"] or item["run_id"] != manifest["run_id"]:
        raise ValueError("Run identifier differs from economic identity")
    original_inputs = dict(manifest["input_hashes"])
    protocol_sha = original_inputs.pop("execution_delays_protocol_sha256", None)
    if original_inputs != inputs:
        raise ValueError("Market input identities differ from authenticated BASE")
    if scenario == "BASE_E3":
        verify_preserved_base(package,strategy,item['run_id'],item['manifest_sha256'])
        if item["run_id"] != BASES[strategy] or item["status"] != "reutilizado_verificado":
            raise ValueError("BASE reuse relabelled")
        if config.to_dict() != base.to_dict():
            raise ValueError("BASE configurations differ")
        source_code = package/"codigo_referencia_base"
    else:
        validate_variant(base, scenario, config)
        if item["status"] != "ejecutado" or manifest["label"] != "E4-ejecucion-demoras-"+scenario:
            raise ValueError("Scenario execution identity changed")
        if protocol_sha not in protocols:
            raise ValueError("Unknown frozen runner protocol")
        if item["input_protocol_sha256"] != protocol_sha:
            raise ValueError("Execution record protocol differs from manifest")
        if manifest["code_hash"] != protocols[protocol_sha]["engine_code_hash"]:
            raise ValueError("Run uses incompatible economic code")
        source_code = package/"codigo_ejecutado"
    for name, wanted in manifest["code_files"].items():
        if sha256(safe_path(source_code, name)) != wanted:
            raise ValueError("Frozen economic source changed: "+name)
    for name in FILES:
        if name in {"run_manifest.json", "run_manifest.sha256"}:
            continue
        actual_sha = hashlib.sha256(forecast_bytes(run)).hexdigest() if name == "forecast_evaluation.csv" else sha256(run/name)
        if actual_sha != manifest["output_hashes"][name]:
            raise ValueError("Original included run artifact changed: "+name)
    return run, config


def verify_controls(package,base,inputs,protocols):
    from scripts.check_execution_delays_base import FILES as CONTROL_FILES
    from scripts.check_execution_delays_base import ordered_economic_digest

    evidence=read_json(package/'documentos/control_compatibilidad_base_completa.json')
    if not evidence['passed'] or len(evidence['comparisons'])!=2:
        raise ValueError('Complete BASE compatibility control missing')
    strategies=[r['strategy'] for r in evidence['comparisons']]
    if len(set(strategies))!=2 or set(strategies)!=set(BASES):
        raise ValueError('Complete BASE control strategy coverage differs')
    for result in evidence['comparisons']:
        reference=package/'evidencia'/BASES[result['strategy']]
        verify_preserved_base(package,result['strategy'],result['original_run_id'],
                              result['original_manifest_sha256'])
        if not result['passed'] or sha256(reference/'run_manifest.json')!=result['original_manifest_sha256']:
            raise ValueError('Preserved BASE control reference changed')
        state=read_json(package/'controles_base'/('CONTROL_BASE__'+result['strategy']+'.json'))
        if (state['status']!='ejecutado' or state['strategy']!=result['strategy'] or
                state['run_id']!=result['control_run_id'] or
                state['manifest_sha256']!=result['control_manifest_sha256']):
            raise ValueError('Complete BASE control execution record differs')
        control=package/'evidencia_control'/result['control_run_id']
        manifest=read_json(control/'run_manifest.json')
        if sha256(control/'run_manifest.json')!=result['control_manifest_sha256'] or (
            control/'run_manifest.sha256').read_text().strip()!=result['control_manifest_sha256']:
            raise ValueError('Control manifest authentication failed')
        config=Config.load(control/'effective_config.toml')
        if config.to_dict()!=base.to_dict() or manifest['config']!=base.to_dict():
            raise ValueError('Control BASE configuration differs')
        identity={k:manifest[k] for k in ('config','code_hash','input_hashes','strategies','data_kind','label')}
        if 'run_'+digest(identity)[:24]!=result['control_run_id'] or manifest['run_id']!=result['control_run_id']:
            raise ValueError('Control run identity differs')
        if manifest['label']!='E4-ejecucion-demoras-CONTROL_BASE' or manifest['strategies']!=[
                dict(strategy=result['strategy'],funding_filter_enabled=result['strategy']=='conditional')]:
            raise ValueError('Control strategy identity differs')
        actual=dict(manifest['input_hashes'])
        protocol=actual.pop('execution_delays_protocol_sha256',None)
        if actual!=inputs or protocol not in protocols or manifest['code_hash']!=protocols[protocol]['engine_code_hash']:
            raise ValueError('Control economic identity differs')
        for name in FILES:
            if name in {'run_manifest.json','run_manifest.sha256'}:
                continue
            wanted=manifest['output_hashes'][name]
            value=hashlib.sha256(forecast_bytes(control)).hexdigest() if name=='forecast_evaluation.csv' else sha256(control/name)
            if value!=wanted:
                raise ValueError('Control artifact authentication failed')
        rows=[]
        for name in CONTROL_FILES:
            def records(folder):
                if name=='forecast_evaluation.csv':
                    from scripts.execution_delays_sources import forecast_rows
                    return forecast_rows(folder)
                return parquet(folder/name) if name.endswith('.parquet') else read_csv(folder/name)
            old,new=records(reference),records(control)
            a,b=(ordered_economic_digest(r,ignored=('run_id','units')) for r in (old,new))
            rows.append(dict(file=name,original_rows=len(old),control_rows=len(new),original_digest=a,
                control_digest=b,exact_equal=a==b,ignored_fields=['run_id','units'],row_order='original_persisted'))
        same_rows(result['comparisons'],rows,'Complete BASE controls')
        if not all(r['exact_equal'] for r in rows):
            raise ValueError('Full BASE controls differ from preserved references')
    return len(evidence['comparisons'])


def validate_transfer_population(rows,runs):
    expected={(r['run_id'],name):(r['path']+'/'+name+('.gz' if name=='forecast_evaluation.csv' else ''),
              'lossless_gzip' if name=='forecast_evaluation.csv' else 'exact_bytes')
              for r in runs for name in FILES}
    keys=[(r['run_id'],r['source_name']) for r in rows]
    if len(keys)!=len(expected) or set(keys)!=set(expected):
        raise ValueError('Original transfer catalog population differs')
    for row,key in zip(rows,keys):
        if (row['package_path'],row['transfer'])!=expected[key]:
            raise ValueError('Original transfer catalog path or transfer convention differs')


def verify(package, *, unsealed=False, data_root=None):
    package = Path(package).resolve()
    verify_distribution(package)
    manifest_file = package/"manifiesto_paquete.json"
    members_checked = 0
    if not unsealed:
        manifest = read_json(manifest_file)
        if manifest["schema"] != "execution_delays_sensitivity_v1":
            raise ValueError("Wrong package schema")
        if sha256(manifest_file) != (package/"manifiesto_paquete.sha256").read_text().strip():
            raise ValueError("Package sidecar mismatch")
        listed = set()
        for member in manifest["members"]:
            if member["path"] in listed:
                raise ValueError("Duplicate package member")
            listed.add(member["path"])
            p = safe_path(package, member["path"])
            if p.stat().st_size != member["bytes"] or sha256(p) != member["sha256"]:
                raise ValueError("Package member changed: "+member["path"])
            members_checked += 1
        actual = {p.relative_to(package).as_posix() for p in package.rglob("*") if p.is_file()}
        if actual != listed | {"manifiesto_paquete.json", "manifiesto_paquete.sha256"}:
            raise ValueError("Unlisted or missing package members")
    index = read_json(package/"indice_corridas.json")
    runs = index["runs"]
    keys = {(r["scenario"], r["strategy"]) for r in runs}
    expected = {(s, t) for s in ("BASE_E3", *CHANGES) for t in BASES}
    if len(keys) != len(runs) or (keys != expected and not (unsealed and index.get("partial"))):
        raise ValueError("Closed 14-result matrix changed")
    if len({r["run_id"] for r in runs}) != len(runs):
        raise ValueError("Duplicate run identity")
    if not unsealed and index.get("partial"):
        raise ValueError("Sealed result cannot be partial")
    base = Config.load(package/"evidencia"/BASES["conditional"]/"effective_config.toml")
    source_base = read_json(package/"documentos/verificacion_base_previa.json")["runs"][0]
    if base.to_dict() != source_base["config"] or base.digest() != source_base["config_digest"]:
        raise ValueError("Authenticated original BASE config changed")
    inputs = read_json(package/"documentos/input_hashes.json")
    protocols = {sha256(p): read_json(p) for p in (package/"documentos").glob("protocolo_previo*.json")}
    economic_codes = {p["engine_code_hash"] for p in protocols.values()}
    if len(economic_codes) != 1 or economic_identity(package/"herramientas") not in economic_codes:
        raise ValueError("Packaged executor economic code mismatch")
    for protocol in protocols.values():
        previous = protocol.get("previous_protocol_sha256")
        if previous and previous not in protocols:
            raise ValueError("Missing prior technical protocol")
        revision = protocol.get("technical_revision", 1)
        for name, wanted in protocol["project_files"].items():
            frozen = safe_path(package/f"codigo_runner_v{revision}", name)
            if not frozen.is_file():
                frozen = safe_path(package/"codigo_ejecutado", name)
            if sha256(frozen) != wanted:
                raise ValueError("Frozen runner source changed: "+name)
        for name, wanted in protocol["package_files"].items():
            verify_frozen_document(package, "documentos/" + name, wanted)
    h1_observations=verify_reused_hypotheses(package)
    controls=verify_controls(package,base,inputs,protocols)
    metrics = read_csv(package/"tablas/metricas.csv")
    period_map = {name: (lower, upper) for name, lower, upper in periods(base.to_dict())}
    metric_keys = {(r["scenario"], r["strategy"], r["period"]) for r in metrics}
    if len(metric_keys) != len(metrics) or metric_keys != {(s, t, p) for s, t in keys for p in period_map}:
        raise ValueError("Financial period identities changed")
    for row in metrics:
        lower, upper = period_map[row["period"]]
        if row["start_utc"] != iso(lower) or row["end_exclusive_utc"] != iso(upper):
            raise ValueError("Financial period boundaries changed")
        if row["coverage_complete"] == "True" and int(row["days"]) != (upper-lower)//DAY:
            raise ValueError("Financial period denominator changed")
    validate_h2_rows(read_csv(package/"tablas/h2.csv"), metrics)
    early_h3 = []
    for scenario in dict.fromkeys(r["scenario"] for r in metrics):
        early_h3.extend(dict(scenario=scenario, **r) for r in summarize_h3(
            read_csv(package/"hipotesis_base/h3_diario.csv"), base,
            [r for r in metrics if r["scenario"] == scenario]))
    same_rows(read_csv(package/"tablas/h3_resumen.csv"), early_h3, "H3 contract")
    portfolios = []
    for item in runs:
        run, config = verify_identity(package, item, base, inputs, protocols)
        windows = read_json(package/"fuentes/volumen"/(item["run_id"]+".json"))
        for window in windows:
            if window["present"] and inputs.get(window["source_path"]) != window["source_sha256"]:
                raise ValueError("Volume provenance differs from authenticated data identity")
        if data_root is not None:
            from scripts.execution_delays_sources import extract_windows
            actual = extract_windows(data_root, config, parquet(run/"orders.parquet"), inputs)
            same_rows(windows, actual, "execution source windows")
        result=derive_portfolio(run,item,windows,package/'evidencia'/BASES[item['strategy']])
        if item['scenario']!='BASE_E3':
            control=read_json(package/'controles_base'/('CONTROL_BASE__'+item['strategy']+'.json'))
            path=package/'fuentes/h3_replay'/(item['run_id']+'.csv')
            original=package/'evidencia_control'/control['run_id']/'h3_replay.csv'
            if sha256(path)!=item['h3_sha256'] or sha256(original)!=control['h3_sha256']:
                raise ValueError('Replay H3 export authentication failed')
            result['invariancias'][0].update(h3_replay_invariance(read_csv(path),read_csv(original),
                result['invariancias'][0]['full_observed_coverage']))
        case_sources=parquet(package/'fuentes/incidentes'/(item['run_id']+'.parquet'))
        for row in case_sources:
            if inputs.get(row['source_path'])!=row['source_sha256']:
                raise ValueError('Incident price provenance differs from authenticated input')
        if data_root is not None:
            cases=select_cases(result['episodios_descubiertos'],result['exposicion_intervalos'],config)
            actual=extract_case_sources(data_root,config,cases,inputs)
            same_rows(case_sources,actual,'incident source extracts')
        portfolios.append(attach_cases(result,run,item,case_sources))
        print("VERIFIED", item["scenario"], item["strategy"], flush=True)
    tables = consolidate(portfolios, read_csv(package/"hipotesis_base/h3_diario.csv"), base)
    for name, rows in tables.items():
        saved = parquet(package/"tablas"/(name+".parquet")) if name == "decisiones" else read_csv(package/"tablas"/(name+".csv"))
        same_rows(saved, rows, "table "+name)
        same_rows(parquet(package/'tablas'/(name+'.parquet')),rows,'Parquet table '+name)
    transfers=read_csv(package/"fuentes/archivos_originales.csv")
    validate_transfer_population(transfers,runs)
    for row in transfers:
        p = safe_path(package, row["package_path"])
        if p.stat().st_size != int(row["bytes"]) or sha256(p) != row["sha256"]:
            raise ValueError("Original byte transfer record mismatch")
        if row.get("transfer") == "lossless_gzip":
            raw = gzip.decompress(p.read_bytes())
            if len(raw) != int(row["source_bytes"]) or hashlib.sha256(raw).hexdigest() != row["source_sha256"]:
                raise ValueError("Lossless original diagnostic transfer mismatch")
        elif row.get("source_sha256") and (row["source_sha256"] != row["sha256"] or row["source_bytes"] != row["bytes"]):
            raise ValueError("Exact original transfer identity mismatch")
    return dict(passed=True, complete_matrix=keys == expected, runs_checked=len(runs),
        members_checked=members_checked, daily_closes=len(tables["diario"]),
        financial_periods=len(tables["metricas"]), orders=len(tables["ordenes"]),
        full_base_controls=controls,local_incident_cases=len(tables['incidentes_resumen']),
        local_incident_observations=len(tables['incidentes_detalle']),
        fills=len(tables["fills_conciliados"]), capacity_keys=len(tables["capacidad"]),
        h1_observations_reused_once=h1_observations, economic_replay=False,
        volume_scope="re-extracted from local sources" if data_root else "recalculated from included authenticated windows; massive source files not read",
        shared_builder_verifier_logic=True, tool_root=str(ROOT),
        config_module_file=str(Path(sys.modules[Config.__module__].__file__).resolve()),
        package_manifest_sha256=sha256(manifest_file) if manifest_file.exists() else None)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--package", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--data-root", type=Path)
    p.add_argument("--unsealed", action="store_true")
    a = p.parse_args()
    reject_sealed_ancestor(a.output)
    reject_overlaps(a.output, [a.package]+([a.data_root] if a.data_root else []))
    if a.output.exists():
        raise FileExistsError("Audit output must be new and external")
    result = verify(a.package, unsealed=a.unsealed, data_root=a.data_root)
    write_json(a.output, result)
    print(json.dumps(result))
