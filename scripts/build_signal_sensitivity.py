"""Build a new, portable block-2 evidence package from completed immutable portfolios."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal as D
from pathlib import Path

sys.dont_write_bytecode = True
TOOLS_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_ROOT))
sys.path.insert(0, str(TOOLS_ROOT/"src"))

from crypto_carry.config import Config  # noqa: E402
from crypto_carry.reporting import verify_run  # noqa: E402
from scripts import verify_rules_sensitivity_package as core  # noqa: E402
from scripts.report_historical_rules_sensitivity import write_csv  # noqa: E402
from scripts.return_capital.common import parquet, read_csv, read_json, write_json  # noqa: E402
from scripts.rules_sensitivity_h2 import h2_comparison  # noqa: E402
from scripts.signal_sensitivity import BASES, CHANGES, validate_variant  # noqa: E402
from scripts.signal_sensitivity_hypotheses import (  # noqa: E402
    funding_rows_from_run,
    prepare_hypotheses,
    summarize_h3,
)
from scripts.signal_sensitivity_integrity import (  # noqa: E402
    reject_overlaps,
    validate_protocol,
    validate_run_identity,
)
from scripts.signal_sensitivity_report import portfolio_tables  # noqa: E402

RAW_FILES = (
    "effective_config.toml", "run_manifest.json", "run_manifest.sha256", "equity_daily.csv",
    "signals.parquet", "renewal_diagnostics.parquet", "positions.parquet", "fills.parquet",
    "orders.parquet", "risk_events.parquet", "ledger.parquet", "funding_payments.parquet",
    "research_assumptions.json", "metrics.csv", "opportunity_daily.csv", "run_summary.csv",
)
ECONOMIC_FILES = ("equity_daily.csv", "positions.parquet", "fills.parquet", "orders.parquet",
                   "risk_events.parquet", "ledger.parquet", "funding_payments.parquet")
FORECAST_FIELDS = ("symbol", "time_ns", "anchor", "history_start", "forecast", "no_change", "valid")


def write_table(package, name, rows):
    if name != "decisiones":
        write_csv(package/"tablas"/f"{name}.csv", rows)
        return
    import pyarrow as pa
    import pyarrow.parquet as pq

    # Preserve textual evidence exactly while avoiding a >100 MiB repeated CSV.
    columns = list(dict.fromkeys(k for r in rows for k in r))
    def cell(value):
        if value is None:
            return ""
        return json.dumps(value, ensure_ascii=False, separators=(",", ":")) if isinstance(value, (dict, list)) else str(value)
    values = [{k: cell(row.get(k)) for k in columns} for row in rows]
    target = package/"tablas"/f"{name}.parquet"
    target.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(values, schema=pa.schema([(k, pa.string()) for k in columns])),
                   target, compression="zstd")


def read_table(package, name):
    if name != "decisiones":
        return read_csv(package/"tablas"/f"{name}.csv")
    import pyarrow.parquet as pq

    return pq.read_table(package/"tablas"/f"{name}.parquet").to_pylist()


def collect_runs(work, data_root):
    runs = []
    for strategy, rid in BASES.items():
        run = data_root/"outputs"/rid
        manifest = read_json(run/"run_manifest.json")
        runs.append(dict(scenario="BASE_E3", strategy=strategy, run_id=rid, path=str(run),
                         status="reutilizado_verificado", engine_status=manifest["status"], code_hash=manifest["code_hash"],
                         manifest_sha256=core.sha256(run/"run_manifest.json")))
    for scenario in CHANGES:
        for strategy in BASES:
            record = read_json(work/"ejecuciones"/f"{scenario}__{strategy}.json")
            if record["status"] != "ejecutado":
                raise ValueError(f"Unfinished scenario retained in execution registry: {scenario}/{strategy}")
            stage = read_json(work/f"etapa_{scenario[0]}.json")
            execution = next(r for r in stage["runs"] if r["scenario"] == scenario and r["strategy"] == strategy)
            if execution["run_id"] != record["run_id"] or execution["exit_code"] != 0:
                raise ValueError("Stage execution record differs from completed portfolio")
            record.update({k: execution[k] for k in ("command", "log", "exit_code")})
            runs.append(record)
    return runs


def table_rows(run, name):
    return parquet(run/name) if name.endswith(".parquet") else read_csv(run/name)


def projection_digest(rows, fields):
    return core.economic_digest([{k: row.get(k) for k in fields} for row in rows], ignored=())


def invariances(runs, package):
    by_key = {(r["scenario"], r["strategy"]): r for r in runs}
    output = []
    for scenario in CHANGES:
        for strategy in BASES:
            item, base = by_key[scenario, strategy], by_key["BASE_E3", strategy]
            a, b = package/item["path"], package/base["path"]
            row = dict(scenario=scenario, strategy=strategy, run_id=item["run_id"],
                       comparator_run_id=base["run_id"])
            for filename in (*ECONOMIC_FILES, "signals.parquet", "renewal_diagnostics.parquet"):
                ignored = ("run_id", "units")
                ah = core.economic_digest(table_rows(a, filename), ignored=ignored)
                bh = core.economic_digest(table_rows(b, filename), ignored=ignored)
                row[filename.split(".")[0]+"_equal"] = ah == bh
                row[filename.split(".")[0]+"_sha256"] = ah
                row[filename.split(".")[0]+"_base_sha256"] = bh
            row["economic_invariant"] = all(row[n.split(".")[0]+"_equal"] for n in ECONOMIC_FILES)
            row["forecast_inputs_equal_base"] = projection_digest(parquet(a/"signals.parquet"), FORECAST_FIELDS) == projection_digest(parquet(b/"signals.parquet"), FORECAST_FIELDS)
            aa = read_csv(package/"hipotesis"/scenario/"h1_observaciones.csv")
            bb = read_csv(package/"hipotesis/BASE_E3/h1_observaciones.csv")
            row["h1_targets_equal_base"] = projection_digest(aa, ("symbol", "time_ns", "horizon_end", "horizon_valid", "realized", "reason")) == projection_digest(bb, ("symbol", "time_ns", "horizon_end", "horizon_valid", "realized", "reason"))
            row["h1_no_change_equal_base"] = projection_digest(aa, ("symbol", "time_ns", "no_change")) == projection_digest(bb, ("symbol", "time_ns", "no_change"))
            row["h3_daily_equal_base"] = core.economic_digest(read_csv(package/"hipotesis"/scenario/"h3_diario.csv"), ignored=("scenario",)) == core.economic_digest(read_csv(package/"hipotesis/BASE_E3/h3_diario.csv"), ignored=("scenario",))
            output.append(row)
    return output


def deltas(metrics):
    base = {(r["strategy"], r["period"]): r for r in metrics if r["scenario"] == "BASE_E3"}
    result = []
    for row in metrics:
        if row["scenario"] == "BASE_E3":
            continue
        other = base[row["strategy"], row["period"]]
        for field, value in row.items():
            if isinstance(value, bool) or field in {"horizon_hours", "days", "observations"}:
                continue
            if not isinstance(value, (D, int, float)) and value is not None:
                continue
            prior = other.get(field)
            result.append(dict(scenario=row["scenario"], strategy=row["strategy"], period=row["period"],
                               run_id=row["run_id"], comparator_run_id=other["run_id"], metric=field,
                               value=value, base_value=prior,
                               delta=D(str(value))-D(str(prior)) if value is not None and prior is not None else None,
                               reason="" if value is not None and prior is not None else "undefined_metric"))
    return result


def hypothesis_deltas(h1, h3):
    result = []
    for hypothesis, rows, fields in (
        ("H1", h1, ("mae_ewma_bps", "mae_no_change_bps", "skill_vs_no_change")),
        ("H3", h3, ("opportunity_mean_bps", "eligible_fraction", "conditional_cagr")),
    ):
        base = {(r["period"], r.get("symbol", "EQUAL_WEIGHT")): r for r in rows if r["scenario"] == "BASE_E3"}
        for row in rows:
            if row["scenario"] == "BASE_E3":
                continue
            prior = base[row["period"], row.get("symbol", "EQUAL_WEIGHT")]
            same_horizon = int(row["horizon_hours"]) == int(prior["horizon_hours"])
            for field in fields:
                value, reference = row[field], prior[field]
                comparable = same_horizon or field in {"eligible_fraction", "conditional_cagr"}
                defined = value not in (None, "") and reference not in (None, "")
                result.append(dict(hypothesis=hypothesis, scenario=row["scenario"], period=row["period"],
                                   symbol=row.get("symbol", "EQUAL_WEIGHT"), metric=field,
                                   horizon_hours=row["horizon_hours"], base_horizon_hours=prior["horizon_hours"],
                                   value=value, base_value=reference,
                                   delta=D(str(value))-D(str(reference)) if comparable and defined else None,
                                   reason="different_forecast_horizon" if not comparable else "" if defined else "undefined_metric"))
    return result


def snapshot_tools(destination):
    scripts = [
        "build_signal_sensitivity.py", "signal_sensitivity.py", "signal_sensitivity_report.py",
        "signal_sensitivity_hypotheses.py", "signal_sensitivity_docs.py", "verify_signal_sensitivity.py",
        "signal_sensitivity_delivery.py",
        "run_signal_sensitivity.py", "signal_sensitivity_integrity.py", "run_historical_rules_sensitivity.py",
        "verify_rules_sensitivity_package.py", "report_historical_rules_sensitivity.py",
        "rules_sensitivity_exposure.py", "rules_sensitivity_h2.py",
        "continuous_delivery/__init__.py", "continuous_delivery/common.py",
        "continuous_delivery/hypotheses.py", "continuous_delivery/portfolio.py",
        "return_capital/__init__.py", "return_capital/common.py", "return_capital/accounting.py",
        "return_capital/decisions.py", "return_capital/report.py",
    ]
    for name in scripts:
        target = destination/"herramientas/scripts"/name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(TOOLS_ROOT/"scripts"/name, target)
    for source in (TOOLS_ROOT/"src").rglob("*.py"):
        target = destination/"herramientas"/source.relative_to(TOOLS_ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    for name in ("pyproject.toml", "uv.lock"):
        shutil.copyfile(TOOLS_ROOT/name, destination/"herramientas"/name)
    for source in (TOOLS_ROOT/"tests").rglob("test_signal_sensitivity*.py"):
        target = destination/"herramientas"/source.relative_to(TOOLS_ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    target = destination/"herramientas/tests/conftest.py"
    shutil.copyfile(TOOLS_ROOT/"tests/conftest.py", target)
    target = destination/"herramientas/configs/entrega_4/reglas_historicas/BASE_E3.toml"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(TOOLS_ROOT/"configs/entrega_4/reglas_historicas/BASE_E3.toml", target)


def seal(destination):
    destination = Path(destination).resolve()
    path = destination/"manifiesto_paquete.json"
    if path.exists():
        raise FileExistsError("Package already sealed")
    if any((p/"run_manifest.json").exists() or (p/"manifiesto_paquete.json").exists()
           for p in (destination, *destination.parents)):
        raise ValueError("Cannot seal inside protected evidence")
    index = read_json(destination/"indice_corridas.json")
    if index["schema"] != "signal_entry_batch_v1" or len(index["runs"]) != 14:
        raise ValueError("Only a complete block-2 candidate can be sealed")
    dependencies = read_json(destination/"dependencias.json")
    protected = [r["original_path_hint"] for r in index["runs"]]
    protected += [r["path"] for r in dependencies["previous"]]
    protected += [Path(dependencies["data_root_hint"])/"data"]
    reject_overlaps(destination, protected)
    members = [dict(path=p.relative_to(destination).as_posix(), bytes=p.stat().st_size,
                    sha256=core.sha256(p)) for p in sorted(destination.rglob("*")) if p.is_file()]
    write_json(path, dict(schema="signal_entry_sensitivity_v1", created_at=datetime.now(UTC).isoformat(),
                          members=members, engine_modified=False, economic_replays=12))
    (destination/"manifiesto_paquete.sha256").write_text(core.sha256(path)+"\n", encoding="ascii")


def build(work, data_root, destination, *, draft=False):
    from scripts.signal_sensitivity_docs import write_docs

    if destination.exists():
        raise FileExistsError("Choose a new package version")
    validate_protocol(read_json(work/"protocolo_previo.json"), TOOLS_ROOT, work)
    dependencies = read_json(work/"autenticacion_referencias.json")
    runs = collect_runs(work, data_root)
    reject_overlaps(destination, [r["path"] for r in dependencies+runs]+[data_root/"data"])
    protocol = read_json(work/"protocolo_previo.json")
    for item in runs:
        original = Path(item["path"])
        if not verify_run(original)["valid"] or core.sha256(original/"run_manifest.json") != item["manifest_sha256"]:
            raise ValueError(f"Original run failed authentication: {original}")
        manifest = read_json(original/"run_manifest.json")
        validate_run_identity(item, manifest)
        if item["scenario"] != "BASE_E3" and manifest["code_hash"] != protocol["engine_code_hash"]:
            raise ValueError("Original run differs from predeclared economic code")
    base_config = Config.load(Path(runs[0]["path"])/"effective_config.toml")
    destination.mkdir(parents=True)
    parent = Path(next(r["path"] for r in dependencies if r["dependency"] == "parent"))
    base_manifest = read_json(Path(runs[0]["path"])/"run_manifest.json")
    for name, sha in base_manifest["code_files"].items():
        source = parent/"codigo_base"/name
        if core.sha256(source) != sha:
            raise ValueError(f"Original BASE code snapshot missing or changed: {name}")
        target = destination/"codigo_referencia"/name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    tables = defaultdict(list)
    index, sources, common_funding = [], [], None
    for item in runs:
        original = Path(item["path"])
        if not verify_run(original)["valid"] or core.sha256(original/"run_manifest.json") != item["manifest_sha256"]:
            raise ValueError(f"Original run failed authentication: {original}")
        config = Config.load(original/"effective_config.toml")
        if item["scenario"] != "BASE_E3":
            validate_variant(base_config, item["scenario"], config)
        elif config.to_dict() != base_config.to_dict():
            raise ValueError("BASE configurations differ")
        target = destination/"evidencia"/item["run_id"]
        target.mkdir(parents=True)
        for name in RAW_FILES:
            shutil.copyfile(original/name, target/name)
            sources.append(dict(run_id=item["run_id"], source_name=name,
                                package_path=(target/name).relative_to(destination).as_posix(),
                                sha256=core.sha256(original/name), bytes=(original/name).stat().st_size,
                                transfer="exact_bytes"))
        record = dict(item, path=target.relative_to(destination).as_posix(), original_path_hint=str(original))
        index.append(record)
        derived = portfolio_tables(target, record)
        for name, rows in derived.items():
            tables[name].extend(rows)
        raw_funding = funding_rows_from_run(original)
        if common_funding is None:
            common_funding = raw_funding
            write_csv(destination/"fuentes/funding_consumido.csv", raw_funding)
            shutil.copyfile(original/"funding_mark_audit.json", destination/"fuentes/funding_base_original.json")
            write_json(destination/"fuentes/funding_procedencia.json", dict(
                run_id=item["run_id"], source_name="funding_mark_audit.json",
                path="fuentes/funding_base_original.json", transfer="exact_bytes",
                sha256=core.sha256(original/"funding_mark_audit.json"),
                projection="consumed: symbol,funding_time,available_at,funding_rate,interval_hours,interval_verified"))
        elif raw_funding != common_funding:
            raise ValueError("Funding input changed between independent portfolios")
        if item["strategy"] == "conditional":
            prepare_hypotheses(original, item["scenario"], data_root,
                               destination/"hipotesis"/item["scenario"])
        else:
            conditional = next(r for r in index if r["scenario"] == item["scenario"] and r["strategy"] == "conditional")
            a = projection_digest(parquet(target/"signals.parquet"), FORECAST_FIELDS)
            b = projection_digest(parquet(destination/conditional["path"]/"signals.parquet"), FORECAST_FIELDS)
            if a != b:
                raise ValueError("Strategy-dependent H1 forecasts; investigate before interpretation")
        print(f"POSTPROCESS {item['scenario']}/{item['strategy']} reconciled", flush=True)
    for scenario in ("BASE_E3", *CHANGES):
        config = Config.load(destination/next(r for r in index if r["scenario"] == scenario)["path"]/"effective_config.toml")
        daily = read_csv(destination/"hipotesis"/scenario/"h3_diario.csv")
        h3 = summarize_h3(daily, config, [r for r in tables["metricas"] if r["scenario"] == scenario])
        tables["h3_resumen"].extend(dict(scenario=scenario, **r) for r in h3)
        tables["h1_resumen"].extend(read_csv(destination/"hipotesis"/scenario/"h1_resumen.csv"))
    tables["h2"] = h2_comparison(tables["metricas"])
    tables["deltas_hipotesis"] = hypothesis_deltas(tables["h1_resumen"], tables["h3_resumen"])
    tables["deltas"] = deltas(tables["metricas"])
    tables["invariancias"] = invariances(index, destination)
    for name, rows in tables.items():
        write_table(destination, name, rows)
    write_json(destination/"indice_corridas.json", dict(schema="signal_entry_batch_v1", runs=index))
    write_csv(destination/"fuentes/archivos_originales.csv", sources)
    write_csv(destination/"registro_escenarios_final.csv", [
        {k: r.get(k) for k in ("scenario", "strategy", "status", "engine_status", "run_id",
                               "manifest_sha256", "code_hash", "path")}
        for r in index])
    # Small provenance/documents only; previous packages and large data remain dependencies.
    documents = destination/"documentos"
    documents.mkdir()
    for name in ("protocolo.md", "registro_escenarios_previo.json",
                 "protocolo_previo.json", "preservacion_previa.json", "input_hashes.json",
                 "autenticacion_referencias.json", "verificacion_base_previa.json",
                 "control_compatibilidad.json", "recursos_antes.json"):
        shutil.copyfile(work/name, documents/name)
    (documents/"configuraciones").mkdir()
    for scenario in CHANGES:
        shutil.copyfile(work/"configuraciones"/f"{scenario}.toml", documents/"configuraciones"/f"{scenario}.toml")
    execution = destination/"ejecucion"
    execution.mkdir()
    for stage in ("H", "V", "B"):
        for prefix, suffix in (("etapa_", ".json"), ("etapa_", ".log"), ("control_etapa_", ".json")):
            shutil.copyfile(work/(prefix+stage+suffix), execution/(prefix+stage+suffix))
    shutil.copytree(work/"logs_corridas", execution/"logs_corridas")
    for name in ("material_academico_consultado.json", "control_historico_general.json"):
        shutil.copyfile(work/name, documents/name)
    write_json(destination/"dependencias.json", dict(data_root_hint=str(data_root),
        previous=read_json(work/"autenticacion_referencias.json"),
        included="Selected exact raw run files, numerical daily/H1/H3/decision evidence, code snapshots",
        excluded="Massive minute sources, complete raw run directories, previous packages, new intraday risk series",
        shared_builder_verifier_logic=True))
    snapshot_tools(destination)
    write_docs(destination, tables, index)
    if not draft:
        seal(destination)
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path)
    parser.add_argument("--data-root", type=Path)
    parser.add_argument("--destination", required=True, type=Path)
    parser.add_argument("--draft", action="store_true")
    parser.add_argument("--seal-only", action="store_true")
    args = parser.parse_args()
    if args.seal_only:
        seal(args.destination.resolve())
        return
    if not args.work or not args.data_root:
        parser.error("Building requires --work and --data-root")
    print(build(args.work.resolve(), args.data_root.resolve(), args.destination.resolve(), draft=args.draft))


if __name__ == "__main__":
    main()
