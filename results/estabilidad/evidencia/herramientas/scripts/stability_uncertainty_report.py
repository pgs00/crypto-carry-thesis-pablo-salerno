"""B6 read-only financial reconstruction, compact evidence and offline verification.

No engine replay is imported or invoked. Original source bytes are losslessly
included for the consumed financial artifacts; minute evidence is a projection
with its authenticated partition provenance. Builder and verifier share the
accounting, exposure and execution audit helpers explicitly identified below.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import html
import io
import json
import shutil
import sys
from collections import defaultdict
from decimal import Decimal as D
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from crypto_carry.config import DAY, Config, iso, timestamp  # noqa: E402
from scripts import verify_rules_sensitivity_package as core  # noqa: E402
from scripts.continuous_delivery.common import write_rows  # noqa: E402
from scripts.continuous_delivery.portfolio import activity_summary  # noqa: E402
from scripts.cost_capacity_ledger import audit_ledger  # noqa: E402
from scripts.execution_delays_audit import audit_execution, summarize_execution  # noqa: E402
from scripts.execution_delays_sources import extract_windows  # noqa: E402
from scripts.return_capital.accounting import cycle_catalog  # noqa: E402
from scripts.return_capital.common import parquet, read_json, sha256, write_json  # noqa: E402
from scripts.rules_sensitivity_exposure import exposure_intervals, exposure_summary  # noqa: E402
from scripts.rules_sensitivity_h2 import h2_comparison, validate_h2_rows  # noqa: E402
from scripts.stress_counterfactual_audit import audit_funding_amounts  # noqa: E402

BASES = {"conditional": "run_ad71d751b20623006c195ff3",
         "permanent": "run_dfea4b7ac1475668d5968c97"}
STARTS = {"I2023": timestamp("2023-01-01T00:00:00Z"),
          "I2024": timestamp("2024-01-01T00:00:00Z")}
END = timestamp("2026-09-01T00:00:00Z")
SOURCE_FILES = ("effective_config.toml", "equity_daily.csv", "run_summary.csv",
                "positions.parquet", "ledger.parquet", "orders.parquet", "fills.parquet",
                "risk_events.parquet", "funding_payments.parquet", "funding_mark_audit.json")
PARQUETS = ("positions", "ledger", "orders", "fills", "risk_events", "funding_payments")
CAPITAL_FIELDS = ("capital_deployed_usdt", "capital_utilization", "gross_exposure_usdt",
                  "collateral_usdt", "debt_usdt")
METRICS = ("net_return", "cagr", "sharpe", "annual_volatility", "max_drawdown",
           "max_drawdown_days")
SCHEMA = "b6_financial_evidence_v1"


def _time(value):
    if isinstance(value, bool) or not str(value).isdigit():
        raise ValueError("Invalid integer time_ns")
    return int(value)


def period_specs(start, end):
    """Original cuts retain nominal dates and receive explicit partial labels."""
    output = [dict(period="full", lower=start, upper=end, nominal_lower=start,
                   nominal_upper=end, period_kind="available_sample")]
    originals = (("2022-2023", timestamp("2022-01-01T00:00:00Z"),
                  timestamp("2024-01-01T00:00:00Z")),
                 ("2024+", timestamp("2024-01-01T00:00:00Z"), END))
    for label, lo, hi in originals:
        lower, upper = max(start, lo), min(end, hi)
        if lower < upper:
            output.append(dict(period=label if (lower, upper) == (lo, hi)
                               else label + "_disponible", lower=lower, upper=upper,
                               nominal_lower=lo, nominal_upper=hi, period_kind="original_cut"))
    for year in range(int(iso(start)[:4]), int(iso(end - 1)[:4]) + 1):
        lo = timestamp(f"{year}-01-01T00:00:00Z")
        hi = timestamp(f"{year + 1}-01-01T00:00:00Z")
        output.append(dict(period=str(year), lower=max(start, lo), upper=min(end, hi),
                           nominal_lower=lo, nominal_upper=hi, period_kind="calendar_year"))
    return output


def summarize_periods(daily, start, end):
    output = []
    for spec in period_specs(start, end):
        selected = [r for r in daily if spec["lower"] <= r["time_ns"] < spec["upper"]]
        if not selected:
            continue
        lower = max(spec["lower"], selected[0]["time_ns"] // DAY * DAY)
        upper = min(spec["upper"], selected[-1]["time_ns"] + 1)
        full_days = sum(not r["partial_day"] for r in selected)
        expected_times = list(range(lower + DAY - 1, upper, DAY))
        regular = ([r["time_ns"] for r in selected] == expected_times
                   and not any(r["partial_day"] or r["daily_return"] is None
                               and r["starting_equity_usdt"] > 0 for r in selected))
        if regular:
            row = core.period_financials(daily, [(spec["period"], lower, upper)])[0]
        else:
            opening, final = selected[0]["starting_equity_usdt"], selected[-1]["equity_usdt"]
            row = dict(period=spec["period"], starting_equity_usdt=opening,
                       final_equity_usdt=final, net_pnl_usdt=final - opening)
            row.update({key: None for key in METRICS})
            row.update(cagr_reason="incomplete_daily_grid", sharpe_reason="incomplete_daily_grid")
            for key in (*core.COMPONENTS, *core.SPLIT_COMPONENTS):
                row[key] = sum((r[key] for r in selected), D(0))
            for key in CAPITAL_FIELDS:
                row[key + "_daily_mean"] = row[key + "_daily_max"] = None
            row["reconciliation_residual_usdt"] = row["net_pnl_usdt"] - sum(
                (row[key] for key in core.COMPONENTS[:-1]), D(0))
        if abs(row["reconciliation_residual_usdt"]) > D("1E-8"):
            raise ValueError("Period Decimal reconciliation exceeds 1E-8")
        complete = regular and (lower, upper) == (spec["lower"], spec["upper"])
        nominal = complete and (lower, upper) == (spec["nominal_lower"], spec["nominal_upper"])
        row.update(start_utc=iso(lower), end_exclusive_utc=iso(upper),
                   requested_start_utc=iso(spec["lower"]),
                   requested_end_exclusive_utc=iso(spec["upper"]),
                   nominal_start_utc=iso(spec["nominal_lower"]),
                   nominal_end_exclusive_utc=iso(spec["nominal_upper"]),
                   period_kind=spec["period_kind"], days=full_days,
                   observed_snapshots=len(selected),
                   missing_days=max(0, (spec["upper"] - spec["lower"]) // DAY - full_days),
                   coverage_complete=complete, original_period_complete=nominal,
                   year_complete=nominal if spec["period_kind"] == "calendar_year" else None,
                   coverage_reason="" if complete else "actual_dates_only_no_extrapolation",
                   metrics_evaluable_on_observed_grid=regular,
                   drawdown_frequency="daily_close", sharpe_rf=0, sharpe_ddof=1,
                   annualization_days=365)
        if row["starting_equity_usdt"] <= 0:
            row["net_return"] = row["max_drawdown"] = row["max_drawdown_days"] = None
        output.append(row)
    return output


def opening_balances(raw, config, start):
    prior = [r for r in raw if _time(r["time_ns"]) < start]
    inherited = start > timestamp(config.start)
    if inherited and (not prior or _time(prior[-1]["time_ns"]) != start - 1):
        raise ValueError("Inherited start requires the exact previous closing balance")
    source = prior[-1] if inherited else None
    output = []
    for symbol in config.symbols:
        row = dict(symbol=symbol, start_utc=iso(start), inherited=inherited,
                   balance_time_utc=iso(start - 1) if source else None,
                   balance_semantics="pre-cut closing mark; first return includes next-day changes"
                   if source else "new account before first economic event")
        for field in ("spot", "short", "average", "spot_cost", "collateral", "funding",
                      "realized_spot", "realized_futures", "fees", "liquidation_fees"):
            row[field] = core.decimal(source[symbol + "_" + field]) if source else D(0)
        for field in ("free_spot", "free_futures", "debt"):
            row[field + "_usdt"] = core.decimal(source[field]) if source else (
                config.capital if field == "free_spot" else D(0))
        row["equity_usdt"] = core.decimal(source["equity"]) if source else config.capital
        output.append(row)
    return output


def financial_view(raw_daily, config, start_ns=None):
    """Difference the complete account before slicing; never rebase monetary P&L."""
    economic_start, end = timestamp(config.start), timestamp(config.end)
    start = economic_start if start_ns is None else _time(start_ns)
    if not economic_start <= start < end:
        raise ValueError("View outside economic sample")
    raw = sorted(raw_daily, key=lambda r: _time(r["time_ns"]))
    for row in raw:
        time = _time(row["time_ns"])
        if not economic_start <= time < end:
            raise ValueError("Daily row outside economic sample")
        partial = core.yes(row.get("partial_day", False))
        if not partial and (time + 1) % DAY:
            raise ValueError("Complete daily row must be a UTC closing snapshot")
    daily, assets = core.financial_daily(raw, config.capital)
    previous = economic_start - 1
    for row in daily:
        row["return_reason"] = ""
        if row["time_ns"] - previous != DAY or row["partial_day"]:
            row["daily_return"] = None
            row["return_reason"] = "nonconsecutive_daily_observations"
        elif row["starting_equity_usdt"] <= 0:
            row["return_reason"] = "nonpositive_starting_equity"
        previous = row["time_ns"]
    selected = [r for r in daily if r["time_ns"] >= start]
    if not selected:
        raise ValueError("No observed equity within financial view")
    opening = opening_balances(raw, config, start)
    metrics = summarize_periods(selected, start, end)
    components = []
    for metric in metrics:
        lower, upper = timestamp(metric["start_utc"]), timestamp(metric["end_exclusive_utc"])
        for symbol in config.symbols:
            chosen = [r for r in assets if r["symbol"] == symbol and lower <= r["time_ns"] < upper]
            components.append(dict(period=metric["period"], symbol=symbol,
                start_utc=metric["start_utc"], end_exclusive_utc=metric["end_exclusive_utc"],
                **{k: sum((r[k] for r in chosen), D(0))
                   for k in (*core.COMPONENTS, *core.SPLIT_COMPONENTS, "net_pnl_usdt")}))
    return dict(diario=selected, metricas=metrics, componentes_periodo=components,
                saldos_iniciales=opening)


def h3_coverage(metrics):
    rows = {}
    for row in metrics:
        if row["period"] != "full":
            continue
        original = row["scenario"] == "BASE_E3"
        rows[row["scenario"], row["strategy"]] = dict(
            scenario=row["scenario"], strategy=row["strategy"], run_id=row["run_id"],
            start_utc=row["start_utc"], end_exclusive_utc=row["end_exclusive_utc"],
            verdict="conservado_BASE" if original else "ND",
            reason="original_2022_2023_and_2024_2026_comparison_in_BASE_bootstrap"
            if original else "missing_part_or_all_of_original_2022_2023_regime",
            out_of_sample_validation=False)
    return list(rows.values())


def write_table(path, rows):
    write_rows(path, rows, fields=None if rows else ["scenario", "strategy", "run_id"])


def verify_table(path, expected):
    actual = core.read_csv(path)
    if len(actual) != len(expected):
        raise ValueError(f"{Path(path).name}: row population differs")
    fields = set().union(*(set(r) for r in expected)) if expected else set()
    for ordinal, (saved, row) in enumerate(zip(actual, expected)):
        if set(saved) != fields:
            raise ValueError(f"{Path(path).name}: columns differ")
        for key in fields:
            value, target = saved[key], row.get(key)
            label = f"{Path(path).name}[{ordinal}].{key}"
            if target is None:
                valid = value == ""
            elif isinstance(target, bool):
                valid = value == str(target)
            elif isinstance(target, int):
                valid = value == str(target)
            elif isinstance(target, (float, D)):
                observed = core.decimal(value, label)
                tolerance = D("1E-10") if isinstance(target, float) else D("1E-8")
                valid = abs(observed - D(str(target))) <= tolerance
            elif isinstance(target, (dict, list)):
                valid = value == json.dumps(target, sort_keys=True, default=str)
            else:
                valid = value == str(target)
            if not valid:
                raise ValueError(f"{label}: recalculated value differs")
    return len(actual)


def _gzip_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, sort_keys=True, default=str, ensure_ascii=False).encode("utf-8")
    path.write_bytes(gzip.compress(payload, mtime=0))


def _source_bytes(folder, name):
    direct = folder / name
    return direct.read_bytes() if direct.is_file() else gzip.decompress(
        (folder / (name + ".gz")).read_bytes())


def _source_csv(folder, name):
    return list(csv.DictReader(io.StringIO(_source_bytes(folder, name).decode("utf-8-sig"))))


def export_sources(run, destination, item):
    manifest_path = run / "run_manifest.json"
    if sha256(manifest_path) != item["manifest_sha256"]:
        raise ValueError("Source run manifest identity changed")
    manifest = read_json(manifest_path)
    if (manifest.get("run_id") != item["run_id"] or not manifest.get("artifacts_complete")
            or manifest.get("status") not in {"complete", "insolvent"}
            or [r["strategy"] for r in manifest["strategies"]] != [item["strategy"]]):
        raise ValueError("Source portfolio identity/status invalid")
    destination.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(manifest_path, destination / "run_manifest.json")
    files = []
    for name in SOURCE_FILES:
        source = run / name
        if sha256(source) != manifest["output_hashes"].get(name):
            raise ValueError("Consumed source artifact changed: " + name)
        compressed = name.endswith((".json", ".csv"))
        target = destination / (name + ".gz" if compressed else name)
        if compressed:
            target.write_bytes(gzip.compress(source.read_bytes(), mtime=0))
        else:
            shutil.copyfile(source, target)
        files.append(dict(source=name, member=target.name, source_sha256=manifest["output_hashes"][name],
                          member_sha256=sha256(target), original_bytes=source.stat().st_size))
    write_json(destination / "fuentes.json", files)
    return manifest


def load_bundle(folder, item):
    manifest = read_json(folder / "run_manifest.json")
    if sha256(folder / "run_manifest.json") != item["manifest_sha256"]:
        raise ValueError("Included run manifest changed")
    files = read_json(folder / "fuentes.json")
    if {r["source"] for r in files} != set(SOURCE_FILES) or len(files) != len(SOURCE_FILES):
        raise ValueError("Compact financial artifact population differs")
    for entry in files:
        path = core.safe_path(folder, entry["member"])
        payload = _source_bytes(folder, entry["source"])
        if (sha256(path) != entry["member_sha256"]
                or hashlib.sha256(payload).hexdigest() != manifest["output_hashes"][entry["source"]]
                or entry["source_sha256"] != manifest["output_hashes"][entry["source"]]
                or len(payload) != entry["original_bytes"]):
            raise ValueError("Included financial evidence differs from source manifest")
    config = Config.load(folder / "effective_config.toml")
    raw = {name: parquet(folder / (name + ".parquet")) for name in PARQUETS}
    raw["daily"] = _source_csv(folder, "equity_daily.csv")
    raw["summary"] = _source_csv(folder, "run_summary.csv")
    raw["funding"] = json.loads(_source_bytes(folder, "funding_mark_audit.json"))["consumed"]
    return dict(item=item, config=config, raw=raw, manifest=manifest)


def audit_bundle(bundle, windows):
    config, raw, manifest, item = (bundle[k] for k in ("config", "raw", "manifest", "item"))
    start, end = timestamp(config.start), timestamp(config.end)
    if config.capital != D(10000) or end != END:
        raise ValueError("B6 accounts require 10000 USDT and the prescribed exclusive end")
    expected_start = timestamp("2022-01-01T00:00:00Z") if item["scenario"] == "BASE_E3" else STARTS[item["scenario"]]
    if start != expected_start or manifest["run_id"] != item["run_id"]:
        raise ValueError("B6 scenario identity/start differs")
    if len(raw["summary"]) != 1 or raw["summary"][0]["status"] != manifest["status"]:
        raise ValueError("Run summary and manifest status differ")
    for name in (*PARQUETS, "daily"):
        if any(not start <= _time(r["time_ns"]) < end for r in raw[name]):
            raise ValueError("Economic movement outside economic sample: " + name)
    summary = raw["summary"][0]
    if manifest["status"] == "complete":
        expected = list(range(start + DAY - 1, end, DAY))
        if [_time(r["time_ns"]) for r in raw["daily"]] != expected:
            raise ValueError("Complete run has an incomplete daily calendar")
    elif summary.get("stopped_at"):
        stop = summary["stopped_at"]
        stopped = int(stop) if str(stop).isdigit() else timestamp(stop)
        if any(_time(r["time_ns"]) > stopped for name in (*PARQUETS, "daily") for r in raw[name]):
            raise ValueError("Observed records extend after persisted economic stop")
    ledger = audit_ledger(config, raw["ledger"], raw["daily"], raw["positions"])
    execution = audit_execution(config, raw["orders"], raw["fills"], raw["ledger"], windows,
                                risk_events=raw["risk_events"])
    funding = audit_funding_amounts(raw["ledger"], raw["funding"])
    expected_payments = {r["event_id"]: r for r in raw["ledger"] if r["kind"] == "funding"}
    if len(raw["funding_payments"]) != len(expected_payments):
        raise ValueError("Funding payments population differs from ledger")
    for payment in raw["funding_payments"]:
        source = expected_payments.pop(payment["event_id"], None)
        if source is None:
            raise ValueError("Duplicate or unknown funding payment")
        for key in ("symbol", "time_ns", "short", "funding", "amount_usdt"):
            if str(payment[key]) != str(source[key]):
                raise ValueError("Funding payment differs from ledger: " + key)
    return ledger, execution, funding


def derive_tables(bundles, windows):
    tables = defaultdict(list)
    bases = {b["item"]["strategy"]: b["config"] for b in bundles
             if b["item"]["scenario"] == "BASE_E3"}
    for bundle in bundles:
        item, config = bundle["item"], bundle["config"]
        if item["scenario"] == "BASE_E3":
            if item["run_id"] != BASES[item["strategy"]]:
                raise ValueError("Original BASE run identity differs")
        else:
            base = bases[item["strategy"]].to_dict()
            changed = {k for k, value in config.to_dict().items() if value != base[k]}
            if changed != {"start"}:
                raise ValueError("Only the economic start may differ from BASE")
    for bundle in bundles:
        item, config, raw = (bundle[k] for k in ("item", "config", "raw"))
        ledger, execution, funding = audit_bundle(bundle, windows)
        full = financial_view(raw["daily"], config)
        final = full["diario"][-1]
        core.assert_close(raw["summary"][0]["final_equity_usdt"], final["equity_usdt"], "Final equity")
        observed_end = min(timestamp(config.end), _time(raw["summary"][0]["time_ns"]) + 1)
        intervals = exposure_intervals(raw["positions"], timestamp(config.start), observed_end,
                                       config.hedge_tolerance)
        cycles = cycle_catalog(raw["risk_events"], observed_end)
        views = [(item["scenario"], "BASE_continua_desde_2022" if item["scenario"] == "BASE_E3"
                  else "cuenta_nueva_10000_sin_inventario", full)]
        if item["scenario"] == "BASE_E3":
            views += [("BASE_CONTINUA_" + scenario, "tramo_BASE_con_saldos_heredados",
                       financial_view(raw["daily"], config, start))
                      for scenario, start in STARTS.items()]
        for scenario, account, view in views:
            identity = dict(scenario=scenario, strategy=item["strategy"], run_id=item["run_id"],
                            account_type=account, engine_status=bundle["manifest"]["status"])
            periods = [(r["period"], timestamp(r["start_utc"]), timestamp(r["end_exclusive_utc"]))
                       for r in view["metricas"]]
            exposures = exposure_summary(intervals, periods)
            indexed = {r["period"]: r for r in exposures if r["symbol"] == "PORTFOLIO"}
            for row in view["metricas"]:
                row.update({k: v for k, v in indexed[row["period"]].items()
                            if k not in {"period", "symbol"}})
            activity = activity_summary(raw["fills"], raw["orders"], raw["risk_events"], cycles, periods)
            for row in activity:
                _, lo, hi = next(p for p in periods if p[0] == row["period"])
                selected = [c for c in cycles if row["symbol"] == "PORTFOLIO" or c["symbol"] == row["symbol"]]
                row["inherited_cycles_at_start"] = sum(c["entry_ns"] < lo and
                    (c["closed_ns"] is None or c["closed_ns"] >= lo) for c in selected)
                row["open_cycles_at_end"] = sum(c["entry_ns"] < hi and
                    (c["closed_ns"] is None or c["closed_ns"] >= hi) for c in selected)
            view.update(exposicion_periodo=exposures, actividad=activity,
                        ejecucion_resumen=summarize_execution(execution, periods))
            for name, rows in view.items():
                tables[name].extend(dict(row, **identity) for row in rows)
        identity = dict(scenario=item["scenario"], strategy=item["strategy"], run_id=item["run_id"])
        tables["conciliaciones"].append(dict(identity, ledger_checked=ledger["passed"],
            ledger_rows=ledger["ledger_rows"], daily_links=ledger["daily_links"],
            position_links=ledger["position_links"], funding_amounts_checked=len(funding),
            fills_checked=len(execution["fills_conciliados"]),
            orders_checked=len(execution["ordenes"]), tolerance_usdt="1E-8",
            daily_max_residual_usdt=max(abs(r["reconciliation_residual_usdt"]) for r in full["diario"]),
            daily_max_balance_residual_usdt=max(abs(r["balance_residual_usdt"]) for r in full["diario"])))
    tables["h2"] = h2_comparison(tables["metricas"])
    validate_h2_rows(tables["h2"], tables["metricas"])
    tables["h3_cobertura"] = h3_coverage(tables["metricas"])
    grouped = {(r["scenario"], r["strategy"], r["period"]): r for r in tables["metricas"]}
    for scenario in STARTS:
        for row in [r for r in tables["metricas"] if r["scenario"] == scenario]:
            base = grouped.get(("BASE_CONTINUA_" + scenario, row["strategy"], row["period"]))
            if base is None:
                continue
            same_dates = all(row[k] == base[k] for k in ("start_utc", "end_exclusive_utc"))
            result = dict(scenario=scenario, strategy=row["strategy"], period=row["period"],
                          run_id=row["run_id"], base_run_id=base["run_id"],
                          start_utc=row["start_utc"], end_exclusive_utc=row["end_exclusive_utc"],
                          matching_observed_dates=same_dates,
                          new_denominator_usdt=row["starting_equity_usdt"],
                          inherited_denominator_usdt=base["starting_equity_usdt"])
            for key in METRICS:
                result["new_" + key], result["inherited_" + key] = row[key], base[key]
                result["difference_" + key] = (D(str(row[key])) - D(str(base[key]))
                    if same_dates and row[key] is not None and base[key] is not None else None)
            tables["comparacion_inicios"].append(result)
    return dict(tables)


def _load_evidence(candidate):
    root = candidate / "evidencia" / "financiera"
    index = read_json(root / "indice.json")
    expected = {(s, t) for s in ("BASE_E3", *STARTS) for t in BASES}
    actual = {(r["scenario"], r["strategy"]) for r in index["runs"]}
    if index["schema"] != SCHEMA or actual != expected or len(index["runs"]) != 6:
        raise ValueError("Financial evidence must contain exactly BASE plus four new accounts")
    windows = json.loads(gzip.decompress((root / "ventanas_ejecucion.json.gz").read_bytes()))
    if sha256(root / "ventanas_ejecucion.json.gz") != index["windows_sha256"]:
        raise ValueError("Compact execution windows changed")
    return index, [load_bundle(core.safe_path(candidate, r["evidence_path"]), r)
                   for r in index["runs"]], windows


def build(candidate: Path, data_root: Path):
    candidate, data_root = Path(candidate), Path(data_root)
    states = []
    for scenario in STARTS:
        for strategy in BASES:
            state = read_json(candidate / "ejecuciones" / f"{scenario}__{strategy}.json")
            if (state.get("status") != "ejecutado" or state.get("scenario") != scenario
                    or state.get("strategy") != strategy):
                raise ValueError("Report requires four completed compatible portfolio states")
            states.append(state)
    for strategy, run_id in BASES.items():
        run = data_root / "outputs" / run_id
        states.append(dict(scenario="BASE_E3", strategy=strategy, run_id=run_id,
                           path=str(run), manifest_sha256=sha256(run / "run_manifest.json")))
    evidence = candidate / "evidencia" / "financiera"
    items, orders, inputs, config = [], [], {}, None
    for state in states:
        item = {k: state[k] for k in ("scenario", "strategy", "run_id", "manifest_sha256")}
        folder = evidence / item["run_id"]
        manifest = export_sources(Path(state["path"]), folder, item)
        item.update(evidence_path=folder.relative_to(candidate).as_posix(),
                    original_path=str(state["path"]), engine_status=manifest["status"])
        bundle = load_bundle(folder, item)
        config = bundle["config"]
        orders.extend(bundle["raw"]["orders"])
        for name, digest in manifest["input_hashes"].items():
            if name in inputs and inputs[name] != digest:
                raise ValueError("Accounts use incompatible market input identities")
            inputs[name] = digest
        items.append(item)
    windows = extract_windows(data_root, config, orders, inputs)
    _gzip_json(evidence / "ventanas_ejecucion.json.gz", windows)
    write_json(evidence / "indice.json", dict(schema=SCHEMA, runs=items,
        windows_sha256=sha256(evidence / "ventanas_ejecucion.json.gz"),
        source_scope="exact consumed financial artifacts plus exact requested execution minutes",
        source_massive_partitions_reopened_offline=False))
    _, bundles, windows = _load_evidence(candidate)
    tables = derive_tables(bundles, windows)
    for name, rows in tables.items():
        write_table(candidate / "tablas" / (name + ".csv"), rows)
    result = dict(schema=SCHEMA, passed=True, engine_replay=False,
                  unique_portfolios=6, fresh_portfolios=4,
                  table_rows={name: len(rows) for name, rows in tables.items()},
                  original_manifests={r["run_id"]: r["manifest_sha256"] for r in items},
                  shared_logic=["verify_rules_sensitivity_package.financial_daily/period_financials",
                                "cost_capacity_ledger.audit_ledger", "return_capital.accounting.Account",
                                "execution_delays_audit.audit_execution",
                                "rules_sensitivity_exposure", "rules_sensitivity_h2"])
    write_json(candidate / "resultados" / "financiero.json", result)
    render_report(candidate, tables)
    return result


def verify(candidate: Path):
    candidate = Path(candidate)
    _, bundles, windows = _load_evidence(candidate)
    tables = derive_tables(bundles, windows)
    counts = {name: verify_table(candidate / "tablas" / (name + ".csv"), rows)
              for name, rows in tables.items()}
    saved = read_json(candidate / "resultados" / "financiero.json")
    if saved.get("table_rows") != counts or saved.get("engine_replay") is not False:
        raise ValueError("Financial result summary differs from recomputation")
    return dict(passed=True, engine_replay=False, offline=True, unique_portfolios=len(bundles),
                recalculated_table_rows=counts, execution_windows=len(windows),
                tolerance_usdt="1E-8", massive_market_sources_reopened=False,
                scope="recomputed accounting, inherited/fresh metrics, H2, exposure, ledger, funding and fills")


def _format(value, percent=False):
    if value in (None, ""):
        return "ND"
    return f"{float(value) * 100:.2f}%" if percent else f"{float(value):,.2f}"


def _md_table(rows, columns):
    lines = ["| " + " | ".join(label for _, label, _ in columns) + " |",
             "| " + " | ".join("---" for _ in columns) + " |"]
    for row in rows:
        values = []
        for key, _, kind in columns:
            value = row.get(key)
            values.append(_format(value, kind == "%") if kind else str(value or "ND"))
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def _figures(candidate, tables):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt
    import numpy as np

    directory = candidate / "figuras"
    directory.mkdir(parents=True, exist_ok=True)
    colors = {"conditional": "#146c94", "permanent": "#b85135"}
    fig, axes = plt.subplots(2, 2, figsize=(12, 7), constrained_layout=True)
    for i, scenario in enumerate(STARTS):
        for j, strategy in enumerate(BASES):
            ax = axes[i, j]
            for source, label, style in ((scenario, "Cuenta nueva", "-"),
                    ("BASE_CONTINUA_" + scenario, "BASE heredada", "--")):
                rows = [r for r in tables["diario"] if r["scenario"] == source and r["strategy"] == strategy]
                denominator = float(rows[0]["starting_equity_usdt"])
                dates = [np.datetime64(r["date"]) for r in rows]
                ax.plot(dates, [100 * float(r["equity_usdt"]) / denominator for r in rows],
                        style, color=colors[strategy] if style == "-" else "#64676b", label=label)
            ax.set_title(f"{scenario} · {strategy}")
            ax.set_ylabel("Índice inicial 100")
            ax.xaxis.set_major_locator(mdates.YearLocator())
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
            ax.grid(alpha=.2)
            ax.legend(fontsize=8)
    fig.suptitle("Reinicio desde efectivo y tramo BASE con patrimonio heredado", fontsize=14)
    fig.savefig(directory / "01_cuentas_nuevas_y_heredadas.png", dpi=160)
    plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), constrained_layout=True)
    for ax, strategy in zip(axes, BASES):
        years = [2022, 2023, 2024, 2025, 2026]
        for offset, scenario in enumerate(("BASE_E3", *STARTS)):
            rows = {(int(r["period"])): r for r in tables["metricas"]
                    if r["strategy"] == strategy and r["scenario"] == scenario
                    and r["period"].isdigit()}
            present = [year for year in years if year in rows]
            ax.bar([years.index(year) + (offset - 1) * .24 for year in present],
                   [100 * float(rows[year]["net_return"]) if rows[year]["net_return"] is not None
                    else float("nan") for year in present], width=.24, label=scenario)
        ax.set_xticks(range(5), ["2022", "2023", "2024", "2025", "2026*"], fontsize=9)
        ax.axhline(0, color="#555", linewidth=.6)
        ax.set_title(strategy)
        ax.set_ylabel("Retorno anual sobre patrimonio inicial (%)")
        ax.legend(fontsize=8)
        ax.grid(axis="y", alpha=.2)
    fig.suptitle("Desglose anual disponible · *2026: enero–agosto", fontsize=14)
    fig.savefig(directory / "02_retornos_anuales.png", dpi=160)
    plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), constrained_layout=True)
    selected = [r for r in tables["metricas"] if r["period"] == "full" and r["scenario"] in ("BASE_E3", *STARTS)]
    for row in selected:
        strategy = row["strategy"]
        x = row["capital_utilization_daily_mean"]
        if x is None or row["cagr"] is None:
            continue
        axes[0].scatter(float(x) * 100, float(row["cagr"]) * 100, color=colors[strategy], s=60)
        axes[0].annotate(f"{row['scenario']} {strategy[:4]}",
                         (float(x) * 100, float(row["cagr"]) * 100),
                         xytext=(5, 4), textcoords="offset points", fontsize=8)
    axes[0].set(xlabel="Capital utilizado medio / equity diario (%)", ylabel="CAGR365 (%)")
    axes[0].grid(alpha=.2)
    labels = [r["scenario"] + "\n" + r["strategy"][:4] for r in selected]
    axes[1].bar(range(len(selected)), [float(r["invested_fraction"]) * 100 for r in selected],
                color=[colors[r["strategy"]] for r in selected])
    axes[1].set_xticks(range(len(selected)), labels, fontsize=8)
    axes[1].set_ylabel("Tiempo con exposición activa, sin polvo (%)")
    axes[1].grid(axis="y", alpha=.2)
    fig.suptitle("Retorno, capital utilizado al cierre y actividad", fontsize=14)
    fig.savefig(directory / "03_retorno_capital_actividad.png", dpi=160)
    plt.close(fig)
    intervals_path = candidate / "tablas" / "bootstrap_intervalos.csv"
    if intervals_path.is_file():
        rows = [r for r in core.read_csv(intervals_path) if r["block_length_days"] == "28"
                and (r["period"] == "full" or r["hypothesis"] == "H3")
                and r.get("symbol", "") in ("", "PORTFOLIO", "EQUAL_WEIGHT")]
        rows = [r for r in rows if r["point_estimate"] not in (None, "")]
        if rows:
            fig, axes = plt.subplots(len(rows), 1, figsize=(10, max(3, len(rows) * 1.15)),
                                     constrained_layout=True, squeeze=False)
            for ax, row in zip(axes[:, 0], rows):
                point = float(row["point_estimate"])
                ax.axvline(0, color="#888", linewidth=.7)
                if row["interval_low"] and row["interval_high"]:
                    ax.plot([float(row["interval_low"]), float(row["interval_high"])], [0, 0],
                            color="#146c94", linewidth=4)
                ax.scatter([point], [0], color="#b85135", zorder=3)
                ax.set_title(row["metric"] + " · " + row["unit"], fontsize=9, loc="left")
                ax.set_yticks([])
                ax.grid(axis="x", alpha=.2)
            fig.suptitle("BASE: efectos e intervalos marginales nominales del 95% · bloques 28 días")
            fig.savefig(directory / "04_incertidumbre_base.png", dpi=160)
            plt.close(fig)


def render_report(candidate, tables=None):
    """Refresh presentation after bootstrap/synthesis without rereading market data."""
    candidate = Path(candidate)
    if tables is None:
        saved = read_json(candidate / "resultados" / "financiero.json")
        if saved.get("passed") is not True:
            raise ValueError("Rendering requires reconciled financial tables")
        tables = {name: [{k: None if v == "" else v for k, v in row.items()}
                         for row in core.read_csv(candidate / "tablas" / (name + ".csv"))]
                  for name in ("metricas", "diario", "h2")}
    _figures(candidate, tables)
    full = [r for r in tables["metricas"] if r["period"] == "full"]
    display = _md_table(full, [
        ("scenario", "Cuenta / tramo", ""), ("strategy", "Estrategia", ""),
        ("days", "Días", "n"), ("starting_equity_usdt", "Denominador USDT", "n"),
        ("net_return", "Retorno", "%"), ("cagr", "CAGR365", "%"),
        ("sharpe", "Sharpe RF=0", "n"), ("max_drawdown", "DD diario", "%"),
        ("capital_utilization_daily_mean", "Capital/equity medio", "%")])
    h2 = _md_table([r for r in tables["h2"] if r["period"] == "full"], [
        ("scenario", "Cuenta / tramo", ""), ("verdict", "H2 muestra disponible", ""),
        ("conditional_cagr", "CAGR condicional", "%"),
        ("sharpe_difference", "Diferencia de Sharpe", "n"), ("reason", "Criterio", "")])
    synthesis_path = candidate / "fuentes" / "sintesis_estado.json"
    diagnostic = "El diagnóstico dirigido del defecto histórico de liquidación B2/B3 está pendiente; sus conclusiones siguen condicionadas."
    if synthesis_path.is_file():
        state = read_json(synthesis_path)
        pending = state.get("diagnostic_pending_run_ids", [])
        statuses = state.get("diagnostic_statuses", {})
        diagnostic = (f"El diagnóstico de logs y estados B2/B3 registra {statuses}. "
                      f"Corridas pendientes o afectadas: {', '.join(pending) if pending else 'ninguna según la cobertura documentada'}. "
                      "Su criterio y cobertura constan en la síntesis; no se ejecutaron replays históricos.")
    text = f"""# Bloque 6: estabilidad temporal e incertidumbre

Se comparan cuatro cuentas nuevas desde 10.000 USDT, sin posiciones heredadas, con
los tramos coincidentes de BASE continua iniciada en 2022. Las cuentas continuas
conservan el patrimonio, el inventario, los ciclos y los costos acumulados reales.
El índice 100 facilita la lectura; no representa una nueva cartera ni vuelve
directamente comparables los P&L monetarios. Toda la historia ya fue examinada:
los inicios alternativos no son una validación fuera de muestra.

## Muestra disponible y denominadores

{display}

Las fechas observadas, nominales y solicitadas constan en [métricas](tablas/metricas.csv).
Se publican sólo años con evidencia; 2026 termina el 1 de septiembre exclusivo.
Los cortes originales incompletos llevan el sufijo `disponible`. La tabla de
[saldos iniciales](tablas/saldos_iniciales.csv) conserva efectivo, deuda, spot,
cortos, collateral y costos heredados. No se imputan filas cero anteriores al inicio.

![Cuentas nuevas y tramos heredados](figuras/01_cuentas_nuevas_y_heredadas.png)

## Retorno, capital y actividad

El P&L concilia patrimonio final menos inicial con spot, futuros, funding, fees y
cargos de liquidación a 1E-8 USDT. El slippage es informativo y no se descuenta dos
veces. CAGR usa 365 días; Sharpe RF=0 usa retornos diarios, días inactivos y varianza
muestral (ddof=1). Sharpe sin volatilidad evaluable permanece ND.
El capital utilizado es valor spot más collateral al cierre diario; su media es
descriptiva y no mide el pico intradía. La exposición activa excluye polvo y conserva
por separado el inventario bruto y su riesgo de precio.

![Retornos anuales](figuras/02_retornos_anuales.png)

![Capital utilizado y actividad](figuras/03_retorno_capital_actividad.png)

## Hipótesis y dependencia de la fecha inicial

{h2}

H2 compara estrategias con el mismo inicio y período: requiere CAGR condicional
positivo y Sharpe superior. La [tabla completa H2](tablas/h2.csv) conserva todos los
cortes y años, incluidos los favorables y no evaluables. H3 original permanece en
BASE continua: I2023/I2024 carecen de parte o todo el régimen 2022–2023 y son ND
para ese contraste. Ver [cobertura H3](tablas/h3_cobertura.csv) y
[comparación de inicios](tablas/comparacion_inicios.csv).

## Incertidumbre de BASE y síntesis

El bootstrap utiliza exclusivamente BASE autenticada; los inicios y escenarios
hipotéticos no se agregan como observaciones. Bloques circulares emparejados de 28
días, sensibilidades 14/56, estratos anuales y segmentos contiguos; 5.000 réplicas por
longitud, PCG64/SeedSequence raíz 20261001 e intervalos percentiles marginales
nominales del 95%, cuantiles lineales. Son decisiones del estudio. La circularidad
no es contigüidad histórica; estratificar supone estabilidad aproximada dentro del
estrato y corta dependencia entre años. La selección histórica, los pocos ciclos y
los días inactivos limitan la inferencia. Dos intervalos marginales al 95% no son un
contraste conjunto al 95%; las frecuencias no son probabilidades de verdad ni de
ganancia futura. Menos del 95% de réplicas válidas deja el intervalo principal ND;
los cuantiles finitos se identifican como condicionales a evaluabilidad.

Ver [efectos, intervalos y degeneración](tablas/bootstrap_intervalos.csv),
[protocolo y cobertura estadística](estadistica/protocolo.json) y [síntesis](sintesis.md).
Las excepciones favorables H336, A100, L01 y contrafactuales deben conservarse por
período. {diagnostic} SOFR es una comparación hipotética bruta;
no es una cuenta realizada comparable en riesgo. El drawdown de este informe es
diario: riesgo intradía global y ventanas locales permanecen separados en sus fuentes.

## Trazabilidad y verificación

[Conciliaciones](tablas/conciliaciones.csv), [componentes por activo](tablas/componentes_periodo.csv),
[actividad](tablas/actividad.csv) y [ejecución](tablas/ejecucion_resumen.csv).
La evidencia financiera contiene bytes originales comprimidos sin pérdida y
manifiestos de seis carteras únicas; los dos tramos de cada BASE son vistas de la
misma cuenta. Las ventanas mínimas de ejecución conservan identidad de partición,
volumen y precio. El verificador recalcula contabilidad, funding, fees, posiciones,
actividad, exposición, métricas y H2 desde esos insumos; comparte helpers auditados
con el constructor. No relee particiones masivas ni ejecuta el motor offline.

Mecanismo estadístico: [CircularBlockBootstrap](https://bashtage.github.io/arch/bootstrap/generated/arch.bootstrap.CircularBlockBootstrap.html),
[bootstrap de series](https://bashtage.github.io/arch/bootstrap/timeseries-bootstraps.html),
[flujos NumPy](https://numpy.org/doc/stable/reference/random/parallel.html),
[compatibilidad NumPy](https://numpy.org/doc/stable/reference/global_state.html).
La documentación respalda el mecanismo, no los parámetros ni la estratificación elegidos.
"""
    if (candidate / "figuras" / "04_incertidumbre_base.png").is_file():
        text += "\n![Incertidumbre BASE](figuras/04_incertidumbre_base.png)\n"
    (candidate / "reporte.md").write_text(text, encoding="utf-8", newline="\n")
    # Self-contained HTML structure keeps wide tables scrollable without a new dependency.
    import re

    body, table_open = [], False
    for line in text.splitlines():
        if line.startswith("| "):
            if not table_open:
                body.append('<div class="scroll"><table>')
                table_open = True
            cells = [v.strip() for v in line.strip("|").split("|")]
            if not all(c == "---" for c in cells):
                body.append("<tr>" + "".join("<td>" + html.escape(c) + "</td>" for c in cells) + "</tr>")
            continue
        if table_open:
            body.append("</table></div>")
            table_open = False
        match = re.fullmatch(r"!\[(.*?)\]\((.*?)\)", line)
        if match:
            body.append(f'<figure><img src="{html.escape(match[2])}" alt="{html.escape(match[1])}"></figure>')
        elif line.startswith("#"):
            level = len(line) - len(line.lstrip("#"))
            body.append(f"<h{level}>{html.escape(line[level:].strip())}</h{level}>")
        elif line:
            escaped = html.escape(line)
            body.append("<p>" + re.sub(r"\[(.*?)\]\((.*?)\)", r'<a href="\2">\1</a>', escaped) + "</p>")
    if table_open:
        body.append("</table></div>")
    document = '<!doctype html><html lang="es"><meta charset="utf-8"><title>B6: estabilidad e incertidumbre</title>'
    document += '<style>body{max-width:1200px;margin:3rem auto;padding:0 1.5rem;font:16px/1.55 system-ui;color:#202b34}h1,h2{color:#146c94}p{margin:.4em 0}.scroll{overflow:auto}table{border-collapse:collapse;font-size:13px}td{padding:.65rem;border-bottom:1px solid #d8e0e5}tr:first-child{font-weight:700;background:#eef4f7}figure{margin:2rem 0}img{width:100%;height:auto}a{color:#146c94}</style><body>'
    (candidate / "reporte.html").write_text(document + "\n".join(body) + "</body></html>", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, default=Path("D:/Backtesting"))
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--render-only", action="store_true")
    args = parser.parse_args()
    if args.render_only:
        render_report(args.candidate)
        result = dict(rendered=True, engine_replay=False)
    else:
        result = verify(args.candidate) if args.verify else build(args.candidate, args.data_root)
    print(json.dumps(result, default=str, ensure_ascii=False))


if __name__ == "__main__":
    main()
