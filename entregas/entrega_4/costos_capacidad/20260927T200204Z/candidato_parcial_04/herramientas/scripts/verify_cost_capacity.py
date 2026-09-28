"""Read-only portable block-3 verifier; shared postprocessing, no engine replay."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT/"src"))

from crypto_carry.config import DAY, Config, iso  # noqa: E402
from scripts.build_cost_capacity import FILES  # noqa: E402
from scripts.cost_capacity import BASES, CHANGES, validate_variant  # noqa: E402
from scripts.cost_capacity_report import consolidate, derive_portfolio  # noqa: E402
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
from scripts.verify_rules_sensitivity_package import periods, safe_path  # noqa: E402


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
    protocol_sha = original_inputs.pop("cost_capacity_protocol_sha256", None)
    if original_inputs != inputs:
        raise ValueError("Market input identities differ from authenticated BASE")
    if scenario == "BASE_E3":
        if item["run_id"] != BASES[strategy] or item["status"] != "reutilizado_verificado":
            raise ValueError("BASE reuse relabelled")
        if config.to_dict() != base.to_dict():
            raise ValueError("BASE configurations differ")
        source_code = package/"codigo_referencia_base"
    else:
        validate_variant(base, scenario, config)
        if item["status"] != "ejecutado" or manifest["label"] != "E4-costos-capacidad-"+scenario:
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
        if sha256(run/name) != manifest["output_hashes"][name]:
            raise ValueError("Original included run artifact changed: "+name)
    return run, config


def verify(package, *, unsealed=False, data_root=None):
    package = Path(package).resolve()
    manifest_file = package/"manifiesto_paquete.json"
    members_checked = 0
    if not unsealed:
        manifest = read_json(manifest_file)
        if manifest["schema"] != "cost_capacity_sensitivity_v1":
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
        raise ValueError("Closed 18-result matrix changed")
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
            if sha256(safe_path(package/"documentos", name)) != wanted:
                raise ValueError("Frozen protocol input changed: "+name)
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
            from scripts.cost_capacity_sources import extract_windows
            actual = extract_windows(data_root, config, parquet(run/"orders.parquet"), inputs)
            same_rows(windows, actual, "execution source windows")
        portfolios.append(derive_portfolio(run, item, windows,
                          package/"evidencia"/BASES[item["strategy"]]))
        print("VERIFIED", item["scenario"], item["strategy"], flush=True)
    reference_file = package/"referencias/manifiesto_bloque2.json"
    prior = read_json(package/"documentos/autenticacion_referencias.json")
    wanted = next(r["manifest_sha256"] for r in prior if r["dependency"] == "block2")
    if sha256(reference_file) != wanted:
        raise ValueError("Authenticated block-2 reference manifest changed")
    block2_manifest = read_json(reference_file)
    reference_hashes = {m["path"]: m["sha256"] for m in block2_manifest["members"]}
    for p in (package/"hipotesis_base").iterdir():
        if sha256(p) != reference_hashes["hipotesis/BASE_E3/"+p.name]:
            raise ValueError("Reused H1/H3 BASE evidence changed")
    tables = consolidate(portfolios, read_csv(package/"hipotesis_base/h3_diario.csv"), base)
    for name, rows in tables.items():
        saved = parquet(package/"tablas"/(name+".parquet")) if name == "decisiones" else read_csv(package/"tablas"/(name+".csv"))
        same_rows(saved, rows, "table "+name)
    for row in read_csv(package/"fuentes/archivos_originales.csv"):
        p = safe_path(package, row["package_path"])
        if p.stat().st_size != int(row["bytes"]) or sha256(p) != row["sha256"]:
            raise ValueError("Original byte transfer record mismatch")
    return dict(passed=True, complete_matrix=keys == expected, runs_checked=len(runs),
        members_checked=members_checked, daily_closes=len(tables["diario"]),
        financial_periods=len(tables["metricas"]), orders=len(tables["ordenes"]),
        fills=len(tables["fills_conciliados"]), capacity_keys=len(tables["capacidad"]),
        h1_observations_reused_once=10224, economic_replay=False,
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
