"""Read-only offline validation; optional local minute inputs extend the H3 check."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from decimal import Decimal as D
from pathlib import Path

sys.dont_write_bytecode = True
TOOLS_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_ROOT))
sys.path.insert(0, str(TOOLS_ROOT/"src"))

from crypto_carry.config import DAY, SECOND, Config, timestamp  # noqa: E402
from scripts import verify_rules_sensitivity_package as core  # noqa: E402
from scripts.build_signal_sensitivity import (  # noqa: E402
    FORECAST_FIELDS,
    RAW_FILES,
    deltas,
    hypothesis_deltas,
    invariances,
    projection_digest,
    read_table,
)
from scripts.continuous_delivery.hypotheses import market_opportunity  # noqa: E402
from scripts.return_capital.common import parquet, read_csv, read_json, write_json  # noqa: E402
from scripts.rules_sensitivity_h2 import h2_comparison, validate_h2_rows  # noqa: E402
from scripts.signal_sensitivity import BASES, CHANGES, validate_variant  # noqa: E402
from scripts.signal_sensitivity_hypotheses import (  # noqa: E402
    FUNDING_FIELDS,
    evaluate_h1,
    summarize_h1,
    summarize_h3,
)
from scripts.signal_sensitivity_integrity import (  # noqa: E402
    reject_sealed_ancestor,
    validate_protocol,
    validate_run_identity,
)
from scripts.signal_sensitivity_report import portfolio_tables  # noqa: E402


def cell(value):
    if value is None:
        return ""
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return str(value)


def same_rows(actual, expected, label):
    if len(actual) != len(expected):
        raise ValueError(f"{label}: row count differs ({len(actual)} != {len(expected)})")
    for index, (a, b) in enumerate(zip(actual, expected)):
        for key in a.keys() | b.keys():
            if cell(a.get(key)) != cell(b.get(key)):
                raise ValueError(f"{label}/{index}/{key}: value differs")


def check_manifest(package):
    manifest = package/"manifiesto_paquete.json"
    if (package/"manifiesto_paquete.sha256").read_text(encoding="ascii").strip() != core.sha256(manifest):
        raise ValueError("Package checksum mismatch")
    data = read_json(manifest)
    if data["schema"] != "signal_entry_sensitivity_v1":
        raise ValueError("Unknown package schema")
    seen = set()
    for row in data["members"]:
        name = row["path"]
        if name in seen:
            raise ValueError("Duplicate manifest member")
        seen.add(name)
        path = core.safe_path(package, name)
        if path.stat().st_size != row["bytes"] or core.sha256(path) != row["sha256"]:
            raise ValueError(f"Package member changed: {name}")
    actual = {p.relative_to(package).as_posix() for p in package.rglob("*") if p.is_file()}
    if actual != seen | {"manifiesto_paquete.json", "manifiesto_paquete.sha256"}:
        raise ValueError("Unlisted or missing package members")
    return dict(members=len(seen), sha256=core.sha256(manifest))


def verify_configs(package, runs):
    protocol = read_json(package/"documentos/protocolo_previo.json")
    validate_protocol(protocol, package/"herramientas", package/"documentos")
    expected = {(s, strategy) for s in ("BASE_E3", *CHANGES) for strategy in BASES}
    if len(runs) != 14 or {(r["scenario"], r["strategy"]) for r in runs} != expected:
        raise ValueError("Closed matrix requires exactly fourteen distinct portfolios")
    if len({r["run_id"] for r in runs}) != len(runs):
        raise ValueError("Run identifiers were relabelled or duplicated")
    base_item = next(r for r in runs if r["scenario"] == "BASE_E3" and r["strategy"] == "conditional")
    base = Config.load(core.safe_path(package, base_item["path"])/"effective_config.toml")
    original = read_json(package/"documentos/verificacion_base_previa.json")["runs"]
    if base.to_dict() != Config.from_dict(original[0]["config"]).to_dict():
        raise ValueError("Reference configuration changed")
    inputs = read_json(package/"documentos/input_hashes.json")
    sources = read_csv(package/"fuentes/archivos_originales.csv")
    for item in runs:
        if item["status"] not in {"ejecutado", "reutilizado_verificado"}:
            raise ValueError("Unexecuted scenario cannot count as completed sensitivity")
        run = core.safe_path(package, item["path"])
        if item["path"] != "evidencia/"+item["run_id"]:
            raise ValueError("Run path/identity mismatch")
        mpath = run/"run_manifest.json"
        if core.sha256(mpath) != item["manifest_sha256"] or (run/"run_manifest.sha256").read_text().strip() != core.sha256(mpath):
            raise ValueError("Original run manifest changed")
        manifest = read_json(mpath)
        validate_run_identity(item, manifest)
        config = Config.load(run/"effective_config.toml")
        if config.to_dict() != Config.from_dict(manifest["config"]).to_dict():
            raise ValueError("Effective config differs from run identity")
        if item["scenario"] == "BASE_E3":
            if item["run_id"] != BASES[item["strategy"]] or config.to_dict() != base.to_dict():
                raise ValueError("Original BASE identity changed")
            prior = next(r for r in original if r["strategy"] == item["strategy"])
            if (item["manifest_sha256"] != prior["protected_files"]["run_manifest.json"]
                    or manifest["code_hash"] != prior["code_hash_original"]
                    or manifest["status"] != prior["verification"]["status"]
                    or manifest["input_hashes"] != inputs):
                raise ValueError("BASE differs from authenticated pre-execution reference")
            code_root = package/"codigo_referencia"
        else:
            validate_variant(base, item["scenario"], config)
            if manifest["code_hash"] != protocol["engine_code_hash"]:
                raise ValueError("Run differs from predeclared engine identity")
            code_root = package/"herramientas"
            wanted = dict(inputs, signal_protocol_sha256=core.sha256(package/"documentos/protocolo_previo.json"))
            if manifest["input_hashes"] != wanted:
                raise ValueError("Scenario input identity changed")
        for name, sha in manifest["code_files"].items():
            if core.sha256(core.safe_path(code_root, name)) != sha:
                raise ValueError(f"Executing code snapshot changed: {name}")
        aggregate = hashlib.sha256(json.dumps(manifest["code_files"], sort_keys=True,
                                                separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
        if aggregate != manifest["code_hash"]:
            raise ValueError("Economic code identity does not aggregate")
        for name in RAW_FILES:
            path = run/name
            if name not in {"run_manifest.json", "run_manifest.sha256"} and core.sha256(path) != manifest["output_hashes"][name]:
                raise ValueError(f"Raw run evidence differs from original manifest: {name}")
        selected = [r for r in sources if r["run_id"] == item["run_id"]]
        if len(selected) != len(RAW_FILES) or {r["source_name"] for r in selected} != set(RAW_FILES):
            raise ValueError("Source inventory is incomplete")
        for row in selected:
            source = core.safe_path(package, row["package_path"])
            if row["sha256"] != core.sha256(source) or int(row["bytes"]) != source.stat().st_size:
                raise ValueError("Exact source transfer inventory mismatch")
    return base


def validate_h3_groups(groups, schedules, config):
    """Independently check UTC grid ownership, strict funding cost and sufficient sums."""
    minute = 60*SECOND
    start, end = timestamp(config.start), timestamp(config.end)
    expected = {}
    for symbol in config.symbols:
        schedule = schedules[symbol]
        if any(int(a["time_ns"]) >= int(b["time_ns"]) for a, b in zip(schedule, schedule[1:])):
            raise ValueError("Non-monotonic H3 publication schedule")
        for index, fc in enumerate(schedule):
            first = max(start, ((int(fc["time_ns"])+minute-1)//minute)*minute)
            stop = min(end, ((int(schedule[index+1]["time_ns"])+minute-1)//minute)*minute
                       if index+1 < len(schedule) else end)
            while first < stop:
                day_end = (first//DAY+1)*DAY
                upper = min(stop, day_end)
                key = (core.iso(first)[:10], symbol, int(fc["time_ns"]))
                expected[key] = ((upper-first)//minute, fc)
                first = upper
    seen, daily = set(), defaultdict(lambda: [0, 0, 0, D(0)])
    for row in groups:
        key = row["date"], row["symbol"], int(row["forecast_available_at"])
        if key in seen or key not in expected:
            raise ValueError("H3 duplicate or unknown publication group")
        seen.add(key)
        minutes, fc = expected[key]
        if int(row["minutes"]) != minutes or int(row["forecast_anchor"]) != int(fc["anchor"]):
            raise ValueError("H3 publication grid differs from real availability")
        value = D(str(fc["forecast"]))
        if D(str(row["forecast"])) != value:
            raise ValueError("H3 forecast changed")
        known, eligible = int(row["valid_minutes"]), int(row["eligible_minutes"])
        if not 0 <= eligible <= known <= minutes:
            raise ValueError("H3 minute counts do not partition")
        if not core.yes(fc["valid"]) and known:
            raise ValueError("Invalid forecast was treated as known H3 opportunity")
        if eligible and value <= D(".0034"):
            raise ValueError("H3 strict cycle cost condition failed")
        if D(str(row["opportunity_sum"])) != value*eligible:
            raise ValueError("H3 eligible forecast sum changed")
        total = daily[row["date"], row["symbol"]]
        total[0] += minutes
        total[1] += known
        total[2] += eligible
        total[3] += value*eligible
    if seen != set(expected):
        raise ValueError("Missing H3 publication groups")
    result = []
    for (date, symbol), (total, known, eligible, value) in sorted(daily.items()):
        if total != 1440:
            raise ValueError("H3 daily grid must have 1440 minutes")
        result.append(dict(date=date, symbol=symbol, minutos_totales=total, minutos_conocidos=known,
                           minutos_desconocidos=total-known, minutos_elegibles=eligible,
                           suma_forecast_elegible=value))
    return result


def validate_h3_asset_rows(raw_assets, assets):
    asset_map = {(r["date"], r["symbol"]): r for r in assets}
    keys = [(r["date"], r["symbol"]) for r in raw_assets]
    if len(keys) != len(set(keys)) or set(keys) != set(asset_map):
        raise ValueError("H3 asset-day population changed or duplicated")
    for row in raw_assets:
        actual = asset_map[row["date"], row["symbol"]]
        if int(row["time_ns"]) != timestamp(row["date"]+"T00:00:00Z") or int(row["expected_minutes"]) != 1440:
            raise ValueError("H3 asset-day timestamp or expected grid changed")
        for a, b in (("observed_minutes", "minutos_totales"), ("valid_minutes", "minutos_conocidos"),
                     ("eligible_minutes", "minutos_elegibles"), ("opportunity_sum", "suma_forecast_elegible")):
            if D(str(row[a])) != D(actual[b]):
                raise ValueError(f"H3 asset sufficient statistic differs: {a}")
        known = int(row["valid_minutes"]) == 1440
        if core.yes(row["complete"]) != known:
            raise ValueError("H3 unknown minutes converted to valid day")
        expected_value = D(actual["suma_forecast_elegible"])/1440 if known else None
        expected_fraction = D(actual["minutos_elegibles"])/1440 if known else None
        if cell(row["opportunity"]) != cell(expected_value) or cell(row["eligible_fraction"]) != cell(expected_fraction):
            raise ValueError("H3 asset mean changed")
        if row["reason"] != ("" if known else "incomplete_required_minute_or_forecast"):
            raise ValueError("H3 asset-day ND reason changed")


def verify_hypotheses(package, runs, financials, data_root=None):
    funding = read_csv(package/"fuentes/funding_consumido.csv")
    provenance = read_json(package/"fuentes/funding_procedencia.json")
    base = next(r for r in runs if r["scenario"] == "BASE_E3" and r["strategy"] == "conditional")
    original = read_json(package/base["path"]/"run_manifest.json")
    source = core.safe_path(package, provenance["path"])
    if (provenance["run_id"] != base["run_id"] or provenance["source_name"] != "funding_mark_audit.json"
            or core.sha256(source) != original["output_hashes"]["funding_mark_audit.json"]
            or provenance["sha256"] != core.sha256(source)):
        raise ValueError("Consumed funding is not authenticated against original BASE")
    expected_funding = [{k: r[k] for k in FUNDING_FIELDS} for r in read_json(source)["consumed"]]
    same_rows(funding, expected_funding, "Original consumed funding projection")
    h1_all, h3_all = [], []
    for scenario in ("BASE_E3", *CHANGES):
        item = next(r for r in runs if r["scenario"] == scenario and r["strategy"] == "conditional")
        other = next(r for r in runs if r["scenario"] == scenario and r["strategy"] == "permanent")
        run, permanent = package/item["path"], package/other["path"]
        config = Config.load(run/"effective_config.toml")
        signals = parquet(run/"signals.parquet")
        if projection_digest(signals, FORECAST_FIELDS) != projection_digest(parquet(permanent/"signals.parquet"), FORECAST_FIELDS):
            raise ValueError("H1 populations differ between strategies")
        observations, schedules, audit = evaluate_h1(signals, funding, config)
        folder = package/"hipotesis"/scenario
        same_rows(read_csv(folder/"h1_observaciones.csv"), [dict(scenario=scenario, **r) for r in observations], "H1 observations")
        summaries = [dict(scenario=scenario, **r) for r in summarize_h1(observations, config)]
        same_rows(read_csv(folder/"h1_resumen.csv"), summaries, "H1 summary")
        h1_all += summaries
        saved = read_json(folder/"forecasts_verificados.json")
        if saved["schedules"] != schedules or saved["audit"] != audit or saved["original_config"] != config.to_dict():
            raise ValueError("Causal forecast schedule or configuration changed")
        assets = validate_h3_groups(read_csv(folder/"h3_grupos_forecast.csv"), schedules, config)
        raw_assets = read_csv(folder/"h3_activos_diarios.csv")
        validate_h3_asset_rows(raw_assets, assets)
        joint = core.h3_from_assets(assets)
        expected_joint = [{k: r[k] for k in ("date", "time_ns", "complete", "opportunity", "eligible_fraction", "reason")} for r in joint]
        for row in expected_joint:
            row["reason"] = "" if row["complete"] else "incomplete_asset_day"
        expected_joint = [dict(scenario=scenario, **r) for r in expected_joint]
        same_rows(read_csv(folder/"h3_diario.csv"), expected_joint, "H3 daily")
        for source in (run, permanent):
            engine = read_csv(source/"opportunity_daily.csv")
            if len(engine) != len(joint):
                raise ValueError("H3 engine daily population changed")
            for a, b in zip(engine, joint):
                if a["date"] != b["date"] or core.yes(a["complete"]) != b["complete"]:
                    raise ValueError("H3 engine coverage differs")
                if b["complete"]:
                    for key in ("opportunity", "eligible_fraction"):
                        if abs(D(a[key])-D(b[key])) > D("1E-14"):
                            raise ValueError(f"H3 disagrees with actual portfolio replay: {key}")
        summaries = summarize_h3(joint, config, [r for r in financials if r["scenario"] == scenario])
        h3_all += [dict(scenario=scenario, **r) for r in summaries]
        if data_root is not None:
            manifest = read_json(data_root/config.data_dir/"manifests/processed.json")
            days, _, groups, sample = market_opportunity(data_root, manifest, schedules, config, D(".0034"))
            for name, rows in (("h3_activos_diarios", days), ("h3_grupos_forecast", groups), ("h3_muestra_minutos", sample)):
                same_rows(read_csv(folder/f"{name}.csv"), [dict(scenario=scenario, **r) for r in rows], name)
        print(f"VERIFIED H1/H3 {scenario}", flush=True)
    same_rows(read_csv(package/"tablas/h1_resumen.csv"), h1_all, "H1 consolidated")
    same_rows(read_csv(package/"tablas/h3_resumen.csv"), h3_all, "H3 consolidated")
    return h1_all, h3_all


def verify(package, data_root=None, *, unsealed=False):
    package = Path(package).resolve()
    authentication = {"unsealed_candidate": True} if unsealed else check_manifest(package)
    index = read_json(package/"indice_corridas.json")
    if index["schema"] != "signal_entry_batch_v1":
        raise ValueError("Wrong index schema")
    runs = index["runs"]
    base = verify_configs(package, runs)
    metrics = read_csv(package/"tablas/metricas.csv")
    validate_h2_rows(read_csv(package/"tablas/h2.csv"), metrics)
    if data_root is not None:
        from crypto_carry.data.replay import input_hashes

        data_root = Path(data_root).resolve()
        inputs = input_hashes(data_root, base)
        if inputs != read_json(package/"documentos/input_hashes.json"):
            raise ValueError("Local input files differ from pre-execution identity")
    h1, h3 = verify_hypotheses(package, runs, metrics, data_root)
    same_rows(read_csv(package/"tablas/deltas_hipotesis.csv"), hypothesis_deltas(h1, h3), "Hypothesis deltas")
    derived = defaultdict(list)
    for item in runs:
        tables = portfolio_tables(package/item["path"], item)
        for name, rows in tables.items():
            derived[name] += rows
        # portfolio_tables also authenticates archived metrics and records any ND semantic differences.
        print(f"VERIFIED financials/exposure/decisions {item['scenario']}/{item['strategy']}", flush=True)
    for name, rows in derived.items():
        same_rows(read_table(package, name), rows, name)
    expected_h2 = h2_comparison(derived["metricas"])
    same_rows(read_csv(package/"tablas/h2.csv"), expected_h2, "H2")
    expected_deltas = deltas(derived["metricas"])
    same_rows(read_csv(package/"tablas/deltas.csv"), expected_deltas, "Deltas")
    expected_invariance = invariances(runs, package)
    same_rows(read_csv(package/"tablas/invariancias.csv"), expected_invariance, "Invariance")
    derived.update(h1_resumen=read_csv(package/"tablas/h1_resumen.csv"), h3_resumen=h3,
                   h2=expected_h2, deltas=expected_deltas, invariancias=expected_invariance)
    from scripts.return_capital.report import render_html
    from scripts.signal_sensitivity_docs import report_markdown

    markdown = report_markdown(derived, runs)
    if (package/"reporte.md").read_text(encoding="utf-8") != markdown:
        raise ValueError("Report differs from checked numerical tables")
    html = render_html(markdown).replace("<title>Retorno y capital · BASE_E3</title>", "<title>Bloque 2 · Señal y entradas</title>")
    if (package/"reporte.html").read_text(encoding="utf-8") != html:
        raise ValueError("HTML report differs")
    for name, scenarios in (("horizonte", ("BASE_E3", "H072", "H336")), ("vida_media", ("BASE_E3", "V012", "V048")), ("basis", ("BASE_E3", "B025", "B100"))):
        data = [{k: r[k] for k in ("scenario", "strategy", "run_id", "date", "equity_usdt")}
                for r in derived["diario"] if r["scenario"] in scenarios]
        same_rows(read_csv(package/"figuras/fuentes"/f"{name}.csv"), data, "Curve source "+name)
    data = [{k: r[k] for k in ("scenario", "strategy", "period", "cagr", "capital_utilization_daily_mean")}
            for r in derived["metricas"] if r["period"].isdigit()]
    same_rows(read_csv(package/"figuras/fuentes/anual_capital.csv"), data, "Annual figure source")
    return dict(passed=True, authentication=authentication, portfolios=len(runs),
                new_economic_replays=12, reused_portfolios=2, daily_reconciliations=len(derived["diario"]),
                financial_periods=len(derived["metricas"]), h1_summary_rows=len(h1), h3_summary_rows=len(h3),
                local_market_h3_recomputed=data_root is not None, builder_logic_shared=True,
                read_only=True, engine_replay=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--data-root", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--unsealed", action="store_true", help="Numeric check of a new draft, no package seal claim")
    args = parser.parse_args()
    package = args.package.resolve()
    if args.output:
        target = args.output.resolve()
        if target.exists() or target.is_relative_to(package) or (args.data_root and target.is_relative_to(args.data_root.resolve())):
            raise ValueError("Audit output must be new and outside protected inputs")
        reject_sealed_ancestor(target)
    result = verify(package, args.data_root, unsealed=args.unsealed)
    if args.output:
        write_json(target, result)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
