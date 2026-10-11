"""Offline compact block-5 evidence verifier; no Git or original data path required."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
sys.dont_write_bytecode = True

from crypto_carry.config import Config, timestamp  # noqa: E402
from crypto_carry.serialization import encode  # noqa: E402
from scripts.return_capital.common import (  # noqa: E402
    parquet,
    read_csv,
    read_json,
    sha256,
    write_json,
)
from scripts.stress_counterfactual_audit import (  # noqa: E402
    audit_observation_population,
    record_digest,
)
from scripts.stress_counterfactual_contract import (  # noqa: E402
    BASES,
    CONTROLS,
    SCENARIOS,
    STRATEGIES,
    authenticate_approval,
    load_spec,
)
from scripts.stress_counterfactual_delivery import (  # noqa: E402
    EXPORT_FILES,
    canonical_rows,
    compact_compare,
    consolidate,
    contained,
    table_digest,
    verify_exports,
)
from scripts.stress_counterfactual_report import derive_portfolio  # noqa: E402
from scripts.stress_counterfactual_sources import verified_witness_sources  # noqa: E402


def verify_tables(folder, tables):
    inventory = read_json(folder / "catalogo.json")
    if set(inventory) != set(tables):
        raise ValueError("Derived table population differs from recomputation")
    for name, expected in tables.items():
        actual = parquet(folder / (name + ".parquet"))
        normalized = canonical_rows(expected)
        if actual != normalized or inventory[name]["semantic_sha256"] != table_digest(expected):
            raise ValueError("Table differs from recomputed evidence: " + name)
        if inventory[name]["rows"] != len(expected):
            raise ValueError("Derived table row count differs")
        if inventory[name]["csv_export"] and read_csv(folder / (name + ".csv")) != normalized:
            raise ValueError("CSV export differs from verified Parquet table: " + name)
    return len(tables)


def verify_seal(package, unsealed):
    manifest = package / "manifiesto_paquete.json"
    if not manifest.exists():
        if unsealed:
            return dict(sealed=False, members=None)
        raise ValueError("Final package is not sealed")
    if sha256(manifest) != (package / "manifiesto_paquete.sha256").read_text().strip():
        raise ValueError("Package seal identity mismatch")
    members = read_json(manifest)["members"]
    names = {r["path"] for r in members}
    actual = {p.relative_to(package).as_posix() for p in package.rglob("*") if p.is_file()}
    if len(names) != len(members) or actual != names | {"manifiesto_paquete.json", "manifiesto_paquete.sha256"}:
        raise ValueError("Sealed package membership differs")
    for row in members:
        path = contained(package, row["path"])
        if path.stat().st_size != row["bytes"] or sha256(path) != row["sha256"]:
            raise ValueError("Sealed package member changed: " + row["path"])
    return dict(sealed=True, members=len(members))


def verify_frozen(package):
    authenticate_approval(package)
    frozen = read_json(package / "protocolo_ejecucion.json")
    for name, expected in frozen["candidate_files"].items():
        if sha256(contained(package, name)) != expected:
            raise ValueError("Frozen approved candidate member changed: " + name)
    for mapping in (frozen["code_files"], frozen["project_files"]):
        for name, expected in mapping.items():
            snapshot = contained(package, frozen.get("code_snapshot", "codigo_ejecutado"))
            if sha256(contained(snapshot, name)) != expected:
                raise ValueError("Frozen economic source snapshot changed")
    return frozen


def verify_run_identity(package, item, base_config, frozen):
    if item["path"] != "evidencia/" + item["run_id"]:
        raise ValueError("Run path is not canonical authenticated evidence")
    expected_technical = item["scenario"] in CONTROLS or item["scenario"] == "BASE_CORREGIDA"
    if type(item["technical_control"]) is not bool or item["technical_control"] != expected_technical:
        raise ValueError("Scenario technical classification differs from closed matrix")
    run = contained(package, item["path"])
    manifest_path = run / "run_manifest.json"
    if sha256(manifest_path) != item["manifest_sha256"]:
        raise ValueError("Run manifest differs from declared identity")
    if (run / "run_manifest.sha256").read_text().strip() != item["manifest_sha256"]:
        raise ValueError("Original run manifest checksum differs")
    manifest = read_json(manifest_path)
    config = Config.load(run / "effective_config.toml")
    if manifest["config"] != config.to_dict() or config.to_dict() != base_config.to_dict():
        raise ValueError("Scenario configuration differs from BASE")
    if manifest["run_id"] != item["run_id"] or manifest["status"] != item["engine_status"]:
        raise ValueError("Run identity/status differs from evidence")
    if item["scenario"] in SCENARIOS + CONTROLS:
        scenario = item["scenario"]
        spec = load_spec(package, scenario)
        expected = dict(read_json(package / "input_hashes_etapa_b.json"),
            stress_protocol_sha256=sha256(package / "protocolo_ejecucion.json"),
            stress_scenario_sha256=record_digest(encode(spec)))
        if (manifest["code_hash"] != frozen["engine_code_hash"]
                or manifest["code_files"] != frozen["code_files"]
                or manifest["input_hashes"] != expected
                or manifest["label"] != "E4-estres-contrafactual-" + scenario
                or manifest["strategies"] != [dict(strategy=item["strategy"],
                    funding_filter_enabled=item["strategy"] == "conditional")]):
            raise ValueError("Run does not implement the approved frozen scenario")
        folder = package / "intervenciones" / item["run_id"]
        original = folder / "manifiesto_evidencia.json"
        if sha256(original) != item["evidence_manifest_sha256"]:
            raise ValueError("Intervention journal identity changed")
        evidence = read_json(original)
        if evidence["run_manifest_sha256"] != item["manifest_sha256"]:
            raise ValueError("Intervention journal belongs to another run")
        for name, digest in evidence["files"].items():
            if sha256(contained(folder, name)) != digest:
                raise ValueError("Intervention journal member changed: " + name)
        state = read_json(folder / "estado_capa.json")
        if state["scenario"] != encode(spec) or not state["no_randomness"]:
            raise ValueError("Final layer state differs from approved specification")
        if spec["kind"] == "counterfactual" and not state["anchor_verified"]:
            raise ValueError("Counterfactual anchor was not verified")
        if scenario in CONTROLS:
            if state["intervention_rows"] != 0 or parquet(folder / "intervenciones.parquet"):
                raise ValueError("Technical control unexpectedly intervened in market records")
            audit_observation_population(spec, state, parquet(folder / "observaciones_ventanas.parquet"),
                [json.loads(r["evidence_json"]) for r in parquet(folder / "oportunidad_ventanas.parquet")],
                timestamp(config.start),
                int(read_csv(run / "run_summary.csv")[0]["time_ns"]), config.symbols)
    return run


def verify(package, *, unsealed=False, partial=False):
    seal = verify_seal(package, unsealed)
    frozen = verify_frozen(package)
    batch = read_json(package / "indice_corridas.json")
    runs = batch["runs"]
    wanted = {(s, p) for s in ("BASE_E3", "BASE_CORREGIDA") + CONTROLS + SCENARIOS for p in STRATEGIES}
    actual = {(r["scenario"], r["strategy"]) for r in runs}
    if len(actual) != len(runs) or not actual <= wanted or not partial and (batch["partial"] or actual != wanted):
        raise ValueError("Closed scenario population is incomplete or changed")
    by_key = {(r["scenario"], r["strategy"]): r for r in runs}
    exports = read_json(package / "fuentes_exportadas.json")
    if {(r["run_id"], r["source_name"]) for r in exports} != {(r["run_id"], n) for r in runs for n in EXPORT_FILES}:
        raise ValueError("Required original artifact population changed")
    verify_exports(package, exports)
    references = read_json(package / "indice_referencias.json")["references"]
    configurations, controls = {}, []
    for ref in references:
        strategy = ref["strategy"]
        original = by_key["BASE_E3", strategy]
        corrected = by_key["BASE_CORREGIDA", strategy]
        if original["run_id"] != BASES[strategy] or original["manifest_sha256"] != ref["original_manifest_sha256"]:
            raise ValueError("Preserved original BASE identity changed")
        if corrected["manifest_sha256"] != ref["control_manifest_sha256"]:
            raise ValueError("Corrected reference identity changed")
        configurations[strategy] = Config.load(package / original["path"] / "effective_config.toml")
    for item in runs:
        verify_run_identity(package, item, configurations[item["strategy"]], frozen)
    for strategy in STRATEGIES:
        base = package / by_key["BASE_E3", strategy]["path"]
        corrected = package / by_key["BASE_CORREGIDA", strategy]["path"]
        controls.append(compact_compare(base, corrected))
        for scenario in CONTROLS:
            if (scenario, strategy) in by_key:
                controls.append(compact_compare(corrected, package / by_key[scenario, strategy]["path"]))
    if any(r["scenario"] in SCENARIOS for r in runs) and len(controls) != 6:
        raise ValueError("Economic results lack four complete compatibility controls")
    sources = {(r["symbol"], r["market"], int(r["open_time"])): r
               for r in parquet(package / "evidencia_mercado/fuentes_intervencion.parquet")}
    portfolios, h1_cache = [], {}
    for item in runs:
        if item["scenario"] in CONTROLS or item["scenario"] == "BASE_CORREGIDA":
            continue
        run = package / item["path"]
        base = package / by_key["BASE_E3", item["strategy"]]["path"]
        spec = load_spec(package, item["scenario"]) if item["scenario"] in SCENARIOS else dict(id="BASE_E3", kind="off")
        evidence = package / "intervenciones" / item["run_id"] if item.get("evidence_manifest") else None
        run_sources = dict(sources)
        if evidence:
            for row in verified_witness_sources(package, item, read_json(package / "input_hashes_etapa_b.json")):
                key = row["symbol"], row["market"], int(row["open_time"])
                if key in run_sources and run_sources[key] != row:
                    raise ValueError("Witness source differs from frozen intervention extract")
                run_sources[key] = row
        originals = read_json(package / "evidencia_mercado/ejecucion" / (item["run_id"] + ".json"))
        result = derive_portfolio(run, item, originals, run_sources, spec, evidence, base, h1_cache)
        portfolios.append(result)
        print("RECOMPUTED", item["scenario"], item["strategy"], flush=True)
    tables = consolidate(portfolios, configurations["conditional"])
    count = verify_tables(package / "resultados", tables)
    documents = None
    if not partial:
        from scripts.stress_counterfactual_docs import verify_report_documents
        documents = verify_report_documents(package, tables, batch)
    return dict(passed=True, **seal, partial=partial, runs=len(runs), economic_scenarios=3 if not partial else None,
        technical_portfolios=sum(r["scenario"] in CONTROLS for r in runs),
        exact_compatibility_artifact_comparisons=11 * len(controls), recomputed_tables=count,
        economic_replay=False, original_data_root_required=False, git_required=False, documents=documents,
        recomputed="accounting, eight inherited periods, execution, transformation formulas, window risk, H1/H2/H3 aggregates and window opportunity witnesses",
        authenticated_only="original minute partition membership outside included extracts; full minute H3 outside intervention witnesses; historical-source validity",
        shared_logic="builder and verifier share reporting/ledger/execution helpers; scenario transformation auditor is separate from replay implementation")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    parser.add_argument("--unsealed", action="store_true")
    parser.add_argument("--partial", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = verify(args.package.resolve(), unsealed=args.unsealed, partial=args.partial)
    if args.output:
        if args.output.resolve().is_relative_to(args.package.resolve()) and result["sealed"]:
            raise ValueError("Final audit must remain outside the seal")
        write_json(args.output, result)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
