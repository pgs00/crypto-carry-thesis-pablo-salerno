"""Update the single unsealed block-5 candidate from authenticated completed runs."""

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from crypto_carry.config import Config  # noqa: E402
from crypto_carry.reporting import verify_run  # noqa: E402
from scripts.execution_delays_sources import extract_windows  # noqa: E402
from scripts.return_capital.common import parquet, read_json, sha256, write_json  # noqa: E402
from scripts.stress_counterfactual_contract import (  # noqa: E402
    BASES,
    CONTROLS,
    SCENARIOS,
    STRATEGIES,
    authenticate_approval,
    authenticated_references,
    load_spec,
)
from scripts.stress_counterfactual_delivery import (  # noqa: E402
    compact_compare,
    consolidate,
    load_tables,
    save_tables,
    transfer_interventions,
    transfer_run,
    verify_exports,
)
from scripts.stress_counterfactual_report import derive_portfolio  # noqa: E402
from scripts.stress_counterfactual_sources import extract_witness_sources  # noqa: E402


def collect(candidate, data, partial):
    references = authenticated_references(candidate, data)
    output = []
    for scenario in ("BASE_E3", "BASE_CORREGIDA"):
        for ref in references:
            run = data / "outputs" / BASES[ref["strategy"]] if scenario == "BASE_E3" else Path(ref["original_control_path"])
            manifest = read_json(run / "run_manifest.json")
            output.append(dict(scenario=scenario, strategy=ref["strategy"], run_id=run.name,
                path=str(run), status="referencia_preservada", engine_status=manifest["status"],
                manifest_sha256=sha256(run / "run_manifest.json"), technical_control=scenario != "BASE_E3"))
    for scenario in CONTROLS + SCENARIOS:
        for strategy in STRATEGIES:
            path = candidate / "ejecuciones" / f"{scenario}__{strategy}.json"
            item = read_json(path) if path.exists() else {}
            if item.get("status") != "ejecutado":
                if partial:
                    continue
                raise ValueError("Required portfolio is unfinished: " + scenario + "/" + strategy)
            output.append(item)
    return output


def report_identity():
    files = {p.relative_to(ROOT).as_posix(): sha256(p)
             for p in sorted((ROOT / "scripts").rglob("*.py"))}
    return hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()


def build(candidate, data, cache, partial=False):
    if (candidate / "manifiesto_paquete.json").exists():
        raise ValueError("Cannot edit a sealed package")
    authenticate_approval(candidate)
    runs = collect(candidate, data, partial)
    inputs = read_json(candidate / "input_hashes_etapa_b.json")
    sources = {(r["symbol"], r["market"], int(r["open_time"])): r
               for r in parquet(candidate / "evidencia_mercado/fuentes_intervencion.parquet")}
    exports, index = [], []
    for item in runs:
        original = Path(item["path"])
        if sha256(original / "run_manifest.json") != item["manifest_sha256"] or not verify_run(original)["valid"]:
            raise ValueError("Source run failed authentication")
        exports.extend(transfer_run(candidate, original, item))
        if item.get("evidence_manifest"):
            transfer_interventions(candidate, item)
        index.append(dict(item, original_path_hint=str(original), path="evidencia/" + item["run_id"]))
    verify_exports(candidate, exports)
    write_json(candidate / "fuentes_exportadas.json", exports)
    write_json(candidate / "indice_corridas.json", dict(partial=partial, runs=index,
        economic_runs=sum(r["scenario"] in SCENARIOS for r in index),
        technical_runs=sum(r["scenario"] in CONTROLS for r in index), preserved_references=4))
    controls = []
    by_key = {(r["scenario"], r["strategy"]): r for r in index}
    for strategy in STRATEGIES:
        base = candidate / by_key["BASE_E3", strategy]["path"]
        corrected = candidate / by_key["BASE_CORREGIDA", strategy]["path"]
        controls.append(dict(scenario="BASE_CORREGIDA", strategy=strategy, **compact_compare(base, corrected)))
        for scenario in CONTROLS:
            item = by_key.get((scenario, strategy))
            if item:
                controls.append(dict(scenario=scenario, strategy=strategy,
                                     **compact_compare(corrected, candidate / item["path"])))
    if any(r["scenario"] in SCENARIOS for r in index) and len(controls) != 6:
        raise ValueError("Economic interpretation requires all four continuous technical controls")
    write_json(candidate / "controles/compatibilidad_etapa_b_portable.json", dict(passed=True, comparisons=controls))
    portfolios, h1_cache = [], {}
    report_hash = report_identity()
    for item in index:
        if item["technical_control"]:
            continue
        run = candidate / item["path"]
        base = candidate / by_key["BASE_E3", item["strategy"]]["path"]
        spec = load_spec(candidate, item["scenario"]) if item["scenario"] in SCENARIOS else dict(id="BASE_E3", kind="off")
        config = Config.load(run / "effective_config.toml")
        destination = cache / report_hash / item["run_id"]
        identity_path = destination / "identidad.json"
        evidence = candidate / "intervenciones" / item["run_id"] if item.get("evidence_manifest") else None
        run_sources = dict(sources)
        if evidence:
            for row in extract_witness_sources(candidate, item, data, config, inputs):
                key = row["symbol"], row["market"], int(row["open_time"])
                if key in run_sources and run_sources[key] != row:
                    raise ValueError("Witness source differs from frozen intervention extract")
                run_sources[key] = row
        source_path = candidate / "evidencia_mercado/ejecucion" / (item["run_id"] + ".json")
        if source_path.exists():
            windows = read_json(source_path)
        else:
            windows = extract_windows(data, config, parquet(run / "orders.parquet"), inputs)
            write_json(source_path, windows)
        identity = dict(manifest_sha256=item["manifest_sha256"], report_code_sha256=report_hash,
                        execution_sources_sha256=sha256(source_path),
                        evidence_manifest_sha256=item.get("evidence_manifest_sha256"))
        if identity_path.exists():
            if read_json(identity_path) != identity:
                raise ValueError("Cached diagnostic identity changed")
            result = load_tables(destination)
        else:
            result = derive_portfolio(run, item, windows, run_sources, spec, evidence, base, h1_cache)
            save_tables(destination, result)
            write_json(identity_path, identity)
        portfolios.append(result)
        print("DERIVED", item["scenario"], item["strategy"], flush=True)
    config = Config.load(candidate / by_key["BASE_E3", "conditional"]["path"] / "effective_config.toml")
    tables = consolidate(portfolios, config)
    inventory = save_tables(candidate / "resultados", tables)
    write_json(candidate / "controles/postproceso_etapa_b.json", dict(passed=True, partial=partial,
        report_code_sha256=report_hash, table_count=len(inventory), portfolios=len(portfolios),
        interpreted_scenarios=list(dict.fromkeys(r["scenario"] for r in tables["metricas"])),
        economic_replay=False, raw_runs_preserved=True,
        common_builder_verifier_logic="scripts/stress_counterfactual_report.py and delivery.py"))
    return inventory


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, default=Path("D:/Backtesting"))
    parser.add_argument("--cache-root", type=Path, required=True)
    parser.add_argument("--partial", action="store_true")
    args = parser.parse_args()
    result = build(args.candidate.resolve(), args.data_root.resolve(), args.cache_root.resolve(), args.partial)
    print(json.dumps(dict(tables=len(result), partial=args.partial)))


if __name__ == "__main__":
    main()
