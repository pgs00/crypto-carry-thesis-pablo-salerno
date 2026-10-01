"""Compact, exact transfers and reproducible presentation tables for block 5."""

import gzip
import hashlib
import json
import shutil
from collections import defaultdict
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from crypto_carry.config import Config, timestamp
from scripts.build_signal_sensitivity import RAW_FILES
from scripts.check_execution_delays_base import FILES, ordered_economic_digest
from scripts.execution_delays_sources import forecast_rows
from scripts.return_capital.common import (
    parquet,
    read_csv,
    read_json,
    sha256,
    write_csv,
    write_json,
)
from scripts.rules_sensitivity_h2 import h2_comparison
from scripts.signal_sensitivity_hypotheses import summarize_h3

EXPORT_FILES = RAW_FILES + ("forecast_evaluation.csv", "funding_mark_audit.json", "data_quality.json")


def contained(package, name):
    relative = Path(name)
    target = (package / relative).resolve()
    if relative.is_absolute() or ".." in relative.parts or not target.is_relative_to(package.resolve()):
        raise ValueError("Unsafe evidence path")
    return target


def bytes_hash(value):
    return hashlib.sha256(value).hexdigest()


def transfer_run(package, run, item):
    target = package / "evidencia" / item["run_id"]
    target.mkdir(parents=True, exist_ok=True)
    rows = []
    for filename in EXPORT_FILES:
        original = (run / filename).read_bytes()
        compressed = filename == "forecast_evaluation.csv"
        value = gzip.compress(original, mtime=0) if compressed else original
        path = target / (filename + ".gz" if compressed else filename)
        if path.exists():
            if path.read_bytes() != value:
                raise ValueError("Previously exported economic evidence changed")
        else:
            path.write_bytes(value)
        rows.append(dict(run_id=item["run_id"], source_name=filename,
            package_path=path.relative_to(package).as_posix(), source_sha256=bytes_hash(original),
            source_bytes=len(original), sha256=bytes_hash(value), bytes=len(value),
            transfer="lossless_gzip" if compressed else "exact_bytes"))
    return rows


def verify_exports(package, rows):
    seen = set()
    for row in rows:
        path = contained(package, row["package_path"])
        compressed = row["source_name"] == "forecast_evaluation.csv"
        canonical = "evidencia/" + row["run_id"] + "/" + row["source_name"] + (".gz" if compressed else "")
        if (row["package_path"] != canonical
                or row["transfer"] != ("lossless_gzip" if compressed else "exact_bytes")):
            raise ValueError("Export path or representation is not canonical")
        if row["package_path"] in seen:
            raise ValueError("Duplicate exported artifact")
        seen.add(row["package_path"])
        content = path.read_bytes()
        if len(content) != row["bytes"] or bytes_hash(content) != row["sha256"]:
            raise ValueError("Exported evidence bytes changed")
        original = gzip.decompress(content) if row["transfer"] == "lossless_gzip" else content
        if len(original) != row["source_bytes"] or bytes_hash(original) != row["source_sha256"]:
            raise ValueError("Export differs from original source bytes")
        manifest = read_json(package / "evidencia" / row["run_id"] / "run_manifest.json")
        filename = row["source_name"]
        if filename not in ("run_manifest.json", "run_manifest.sha256"):
            if manifest["output_hashes"].get(filename) != row["source_sha256"]:
                raise ValueError("Export not authenticated by original run manifest")
    return len(rows)


def transfer_interventions(package, item):
    manifest_path = Path(item["evidence_manifest"])
    if sha256(manifest_path) != item["evidence_manifest_sha256"]:
        raise ValueError("External scenario evidence identity changed")
    source = manifest_path.parent
    destination = package / "intervenciones" / item["run_id"]
    manifest = read_json(manifest_path)
    # Copy exact small journal members, never market partitions or older packages.
    for path in sorted(source.rglob("*")):
        if not path.is_file():
            continue
        name = path.relative_to(source)
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            if sha256(target) != sha256(path):
                raise ValueError("Previously exported intervention evidence changed")
        else:
            shutil.copyfile(path, target)
    return manifest


def compact_compare(reference, run):
    if Config.load(reference / "effective_config.toml").to_dict() != Config.load(run / "effective_config.toml").to_dict():
        raise ValueError("Control configuration differs from its corrected reference")
    rows = []
    for name in FILES:
        def load(path):
            if name == "forecast_evaluation.csv":
                return forecast_rows(path)
            return parquet(path / name) if name.endswith(".parquet") else read_csv(path / name)
        a, b = load(reference), load(run)
        first, second = ordered_economic_digest(a), ordered_economic_digest(b)
        rows.append(dict(file=name, reference_rows=len(a), actual_rows=len(b),
                         reference_digest=first, actual_digest=second, exact_equal=first == second))
    if not all(row["exact_equal"] for row in rows):
        raise ValueError("Ordered economic compatibility comparison failed")
    return dict(passed=True, original_run_id=reference.name, control_run_id=run.name,
                comparisons=rows, excluded_fields=["run_id", "units"])


def cell(value):
    if value is None:
        return ""
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return str(value)


def canonical_rows(rows):
    fields = list(dict.fromkeys(key for row in rows for key in row))
    return [{key: cell(row.get(key)) for key in fields} for row in rows]


def table_digest(rows):
    return bytes_hash(json.dumps(canonical_rows(rows), ensure_ascii=False, sort_keys=True,
                                 separators=(",", ":")).encode())


def save_tables(folder, tables):
    folder.mkdir(parents=True, exist_ok=True)
    inventory = {}
    for name, rows in tables.items():
        values = canonical_rows(rows)
        fields = list(values[0]) if values else ["no_rows"]
        table = pa.Table.from_pylist(values, schema=pa.schema([(k, pa.string()) for k in fields]))
        pq.write_table(table, folder / (name + ".parquet"), compression="zstd")
        # Large diagnostics remain in Parquet; short presentation tables are also CSV.
        csv_export = bool(values) and len(values) <= 40000 and name not in ("decisiones", "h1_observaciones")
        if csv_export:
            write_csv(folder / (name + ".csv"), values)
        inventory[name] = dict(rows=len(values), semantic_sha256=table_digest(rows), csv_export=csv_export)
    write_json(folder / "catalogo.json", inventory)
    return inventory


def load_tables(folder):
    return {name: parquet(folder / (name + ".parquet")) for name in read_json(folder / "catalogo.json")}


def counterfactual_contrasts(daily):
    from decimal import Decimal as D

    base = {(r["strategy"], str(r["time_ns"])): r for r in daily if r["scenario"] == "BASE_E3"}
    output = []
    for row in daily:
        if row["scenario"] != "CF_SIN_INTERRUPCION":
            continue
        reference = base[row["strategy"], str(row["time_ns"])]
        output.append(dict(scenario=row["scenario"], strategy=row["strategy"], date=row["date"],
            time_ns=row["time_ns"], cf_equity_usdt=row["equity_usdt"], base_equity_usdt=reference["equity_usdt"],
            equity_delta_usdt=D(str(row["equity_usdt"])) - D(str(reference["equity_usdt"])),
            daily_pnl_delta_usdt=D(str(row["net_pnl_usdt"])) - D(str(reference["net_pnl_usdt"])),
            scope="continuous inherited trajectories; descriptive difference, not causal interruption cost"))
    return output


def counterfactual_actions(tables, sample_end):
    """Compare observed decisions/orders/fills by timestamp, with no causal matching claim."""
    start = timestamp("2022-01-01T00:00:00Z")
    first = timestamp("2023-03-24T11:28:00Z")
    edge_end = timestamp("2023-03-24T14:02:00Z")
    day_end = timestamp("2023-03-25T00:00:00Z")
    phases = (("previo", start, first), ("ventana_y_reapertura", first, edge_end),
              ("resto_dia", edge_end, day_end), ("posterior", day_end, sample_end))
    profiles = (
        ("decisiones", "decisions", "time_ns", ("symbol", "decision_kind"),
         ("decision", "actual_outcome", "renewal_status_kind", "portfolio_state", "state_after", "expiry_after")),
        ("ordenes", "order_submissions", "submitted_at", ("symbol", "market", "side", "purpose"),
         ("requested_gross_quantity", "window_start", "window_end", "recent_volume_at_submission")),
        ("fills_conciliados", "fills", "time_ns", ("symbol", "market", "side", "purpose"),
         ("quantity", "net_quantity", "price", "reference_price", "ordinary_fee_usdt",
          "base_fee_quantity", "specific_liquidation_charge_usdt")),
    )
    strategies = sorted({r["strategy"] for name, *_ in profiles for r in tables.get(name, [])
                         if r["scenario"] == "CF_SIN_INTERRUPCION"})
    result = []
    for strategy in strategies:
        for name, kind, time_field, key_fields, values in profiles:
            for phase, lower, upper in phases:
                grouped, counts = {}, {}
                for scenario in ("BASE_E3", "CF_SIN_INTERRUPCION"):
                    groups = defaultdict(list)
                    selected = [r for r in tables.get(name, []) if r["scenario"] == scenario
                        and r["strategy"] == strategy and lower <= int(r[time_field]) < upper]
                    for row in selected:
                        key = (int(row[time_field]), *(str(row.get(k, "")) for k in key_fields))
                        groups[key].append(tuple("" if row.get(k) in (None, "") else str(row[k]) for k in values))
                    grouped[scenario], counts[scenario] = groups, len(selected)
                base, cf = grouped["BASE_E3"], grouped["CF_SIN_INTERRUPCION"]
                shared = base.keys() & cf.keys()
                changed = {k for k in shared if base[k] != cf[k]}
                removed, added = base.keys() - cf.keys(), cf.keys() - base.keys()
                differences = changed | removed | added
                if phase == "previo" and differences:
                    raise ValueError("Counterfactual decision/execution changed before first synthetic availability")
                result.append(dict(strategy=strategy, scenario="CF_SIN_INTERRUPCION", phase=phase,
                    record_kind=kind, start_ns=lower, end_exclusive_ns=upper,
                    base_records=counts["BASE_E3"], cf_records=counts["CF_SIN_INTERRUPCION"],
                    changed_matching_keys=len(changed), only_base_keys=len(removed), only_cf_keys=len(added),
                    first_difference_time_ns=min(k[0] for k in differences) if differences else None,
                    projection_fields=list(values),
                    interpretation="timestamp/key groups in persisted order; different timestamps are not a causal pairing; generated IDs excluded"))
    return result


def consolidate(portfolios, config):
    from decimal import Decimal as D

    tables = defaultdict(list)
    for result in portfolios:
        for name, rows in result.items():
            tables[name].extend(rows)
    tables["cf_contraste_diario"] = counterfactual_contrasts(tables["diario"])
    tables["cf_decisiones_ejecuciones"] = counterfactual_actions(tables, timestamp(config.end))
    risk_groups = defaultdict(list)
    for row in tables["garantias_simultaneas"]:
        risk_groups[row["scenario"], row["strategy"]].append(row)
    for (scenario, strategy), rows in sorted(risk_groups.items()):
        known = [r for r in rows if r["external_shortfall_infimum_usdt"] not in (None, "")]
        peak = max(known, key=lambda r: D(str(r["external_shortfall_infimum_usdt"]))) if known else None
        assets = [r for r in tables["garantias_ventanas"] if r["scenario"] == scenario and r["strategy"] == strategy]
        active = [r for r in assets if str(r["no_open_short"]) == "False"]
        tables["garantias_resumen"].append(dict(scenario=scenario, strategy=strategy,
            simultaneous_observations=len(rows), unknown_external_need_observations=len(rows) - len(known),
            max_known_external_shortfall_infimum_usdt=peak["external_shortfall_infimum_usdt"] if peak else None,
            peak_event_time_ns=peak["time_ns"] if peak else None, peak_state_time_ns=peak["state_time_ns"] if peak else None,
            peak_phase=peak["phase"] if peak else None,
            active_short_asset_observations=len(active),
            max_maintenance_shortfall_usdt=max((D(str(r["maintenance_shortfall_usdt"])) for r in active
                if r["maintenance_shortfall_usdt"] not in (None, "")), default=None),
            max_preventive_topup_infimum_usdt=max((D(str(r["preventive_topup_infimum_usdt"])) for r in rows
                if r["preventive_topup_infimum_usdt"] not in (None, "")), default=None),
            scope="only intervention windows/phases; simultaneous needs, not summed per-asset maxima"))
    scenarios = list(dict.fromkeys(row["scenario"] for row in tables["metricas"]))
    tables["h2"] = h2_comparison(tables["metricas"])
    for scenario in scenarios:
        market = [row for row in tables["h3_diario"] if row["scenario"] == scenario and row["strategy"] == "conditional"]
        other = [row for row in tables["h3_diario"] if row["scenario"] == scenario and row["strategy"] == "permanent"]
        if other:
            fields = ("date", "complete", "opportunity", "eligible_fraction")
            if [{k: str(r[k]) for k in fields} for r in market] != [{k: str(r[k]) for k in fields} for r in other]:
                raise ValueError("H2/H3 portfolios did not receive the same market opportunity")
        metrics = [r for r in tables["metricas"] if r["scenario"] == scenario]
        tables["h3_resumen"].extend(dict(scenario=scenario, **r) for r in summarize_h3(market, config, metrics))
        footprints = [r for r in tables["control_transformaciones"] if r["scenario"] == scenario]
        if len(footprints) == 2 and footprints[0]["market_projection_sha256"] != footprints[1]["market_projection_sha256"]:
            raise ValueError("Strategies did not receive identical intervention records")
    base = {(r["strategy"], r["period"]): r for r in tables["metricas"] if r["scenario"] == "BASE_E3"}
    fields = ("final_equity_usdt", "net_pnl_usdt", "net_return", "cagr", "sharpe", "max_drawdown",
              "capital_utilization_daily_mean", "invested_fraction")
    for row in tables["metricas"]:
        if row["scenario"] == "BASE_E3":
            continue
        reference = base[row["strategy"], row["period"]]
        for field in fields:
            a, b = row.get(field), reference.get(field)
            valid = a not in (None, "") and b not in (None, "")
            tables["deltas"].append(dict(scenario=row["scenario"], strategy=row["strategy"],
                period=row["period"], metric=field, value=a, comparator_value=b,
                delta=D(str(a)) - D(str(b)) if valid else None,
                comparator="BASE_E3 preserved; corrected controls economically equivalent",
                interpretation="descriptive hypothetical trajectory contrast; not causal identification"))
    return dict(tables)
