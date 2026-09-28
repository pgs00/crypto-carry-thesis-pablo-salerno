"""Derived block-3 results and hypothesis invariance, with no economic replay."""

from collections import Counter, defaultdict
from decimal import Decimal as D

from crypto_carry.config import Config
from crypto_carry.data.prescribed import prescribed_rules
from crypto_carry.margin import _tier, maintenance
from scripts.build_signal_sensitivity import deltas, projection_digest
from scripts.cost_capacity_audit import audit_execution, exposure_episodes, summarize_execution
from scripts.return_capital.common import parquet, read_csv
from scripts.rules_sensitivity_h2 import h2_comparison
from scripts.signal_sensitivity_hypotheses import summarize_h3
from scripts.signal_sensitivity_report import portfolio_tables
from scripts.verify_rules_sensitivity_package import periods

FORECAST = ("symbol", "time_ns", "anchor", "history_start", "forecast", "no_change", "valid")
OPPORTUNITY_INPUT = FORECAST + ("basis", "basis_raw", "filter_operational", "filter_coverage",
    "filter_price_alignment", "filter_freshness", "filter_mark", "estimated_cycle_cost")
H3_DAILY = ("time_ns", "date", "complete", "opportunity", "eligible_fraction", "reason")


def validate_selection(signals, config):
    for row in signals:
        cost = row.get("estimated_cycle_cost")
        if cost is None:
            continue
        if D(cost) != D(".0034"):
            raise ValueError("Selection threshold differs from 34 bp")
        if config.research_decision_fee_mode == "base_e3_total":
            components = ("cost_spot_open_fee", "cost_spot_close_fee", "cost_futures_open_fee",
                          "cost_futures_close_fee", "cost_slippage_total")
            if sum(D(row[k]) for k in components) != D(".0034"):
                raise ValueError("Selection diagnostic components do not sum to 34 bp")
            expected = dict(scenario_spot_taker_fee=D(".001")*config.cost_multiplier,
                            scenario_futures_taker_fee=D(".0005")*config.cost_multiplier,
                            scenario_slippage_per_order=config.slippage*config.cost_multiplier)
            if any(D(row[k]) != v for k, v in expected.items()):
                raise ValueError("Scenario diagnostic rates differ from realized contract")


def invariance(run, base, config, item):
    signals, reference = parquet(run/"signals.parquet"), parquet(base/"signals.parquet")
    validate_selection(signals, config)
    complete = item["engine_status"] == "complete"
    output = dict(scenario=item["scenario"], strategy=item["strategy"], run_id=item["run_id"],
                  comparator_run_id=base.name, full_observed_coverage=complete,
                  h1_reused_observations="hipotesis_base/h1_observaciones.csv" if complete else None,
                  h1_evaluation_status="reutilizado_verificado" if complete else "cobertura_parcial_ND",
                  opportunity_definition_unchanged=True)
    for name, fields in (("forecast", FORECAST), ("opportunity_inputs_at_signals", OPPORTUNITY_INPUT)):
        a, b = projection_digest(signals, fields), projection_digest(reference, fields)
        output.update({name+"_sha256": a, name+"_base_sha256": b, name+"_equal": a == b})
        if complete and a != b:
            raise ValueError("Unexpected change in invariant "+name)
    for name, filename, fields in (("h3_daily", "opportunity_daily.csv", H3_DAILY),
        ("h1_saved_targets", "forecast_evaluation.csv", ("symbol", "time_ns", "forecast", "no_change", "realized", "horizon_end", "horizon_valid", "reason"))):
        a, b = projection_digest(read_csv(run/filename), fields), projection_digest(read_csv(base/filename), fields)
        output.update({name+"_sha256": a, name+"_base_sha256": b, name+"_equal": a == b})
        if complete and a != b:
            raise ValueError("Unexpected change in invariant "+name)
    return output


def margin_observations(rows, config):
    rules = prescribed_rules(config)
    result = []
    for row in rows:
        q, mark = D(row["short"]), D(row["mark_price"] or "0")
        if q == 0:
            continue
        time = int(row["time_ns"])
        rule = rules.get(row["symbol"], "futures", time)
        reason = ""
        try:
            tier = _tier(q*mark, rule)
            mm = maintenance(q, mark, rule)
        except ValueError as exc:
            tier, mm, reason = None, None, str(exc)
        result.append(dict(symbol=row["symbol"], time_ns=time, short_quantity=q, mark_price=mark,
            short_notional=q*mark, tier_floor=tier.floor if tier else None,
            tier_cap=tier.cap if tier else None, tier_rate=tier.rate if tier else None,
            tier_deduction=tier.deduction if tier else None, maintenance_usdt=mm,
            reason=reason, frequency="persisted position snapshots; not full intraday series"))
    return result


def derive_portfolio(run, item, windows, base):
    config = Config.load(run/"effective_config.toml")
    result = portfolio_tables(run, item)
    raw = {n: parquet(run/f"{n}.parquet") for n in ("orders", "fills", "ledger", "risk_events", "positions")}
    execution = audit_execution(config, raw["orders"], raw["fills"], raw["ledger"], windows)
    result.update(execution)
    result["ejecucion_resumen"] = summarize_execution(execution, periods(config.to_dict()))
    episodes = exposure_episodes(result["exposicion_intervalos"])
    top_capacity = sorted(execution["capacidad"], key=lambda r: (-r["capacity_utilization"], r["window_start"], r["symbol"], r["market"]))[:5]
    top_exposure = sorted(episodes, key=lambda r: (-r["seconds"], r["start_ns"], r["symbol"]))[:5]
    extremes = []
    for rank, row in enumerate(top_capacity, 1):
        matches = [e["episode_id"] for e in top_exposure if e["symbol"] == row["symbol"] and
                   e["start_ns"] <= row["window_end"] <= e["end_ns"]]
        extremes.append(dict(group="capacity", rank=rank, case_id=f"{row['symbol']}-{row['market']}-{row['window_start']}",
            symbol=row["symbol"], market=row["market"], start_ns=row["window_start"], end_ns=row["window_end"],
            value=row["capacity_utilization"], unit="fraction of cap", shared_episode_ids=matches))
    for rank, row in enumerate(top_exposure, 1):
        matches = [c["case_id"] for c in extremes if row["episode_id"] in c["shared_episode_ids"]]
        extremes.append(dict(group="unhedged_duration", rank=rank, case_id=row["episode_id"],
            symbol=row["symbol"], market="PAIR", start_ns=row["start_ns"], end_ns=row["end_ns"],
            value=row["seconds"], unit="seconds", shared_episode_ids=matches))
    result["episodios_descubiertos"] = episodes
    result["casos_extremos"] = extremes
    causes = []
    for period, lower, upper in periods(config.to_dict()):
        counts = Counter((r["symbol"], r["market"], r["shortfall_cause"]) for r in execution["ordenes"]
                         if lower <= r["submitted_at"] < upper and r["unfilled_quantity"] > 0)
        causes.extend(dict(period=period, symbol=s, market=m, cause=c, orders=n)
                      for (s, m, c), n in sorted(counts.items()))
    result["causas_faltantes"] = causes
    result["tramos_margen_estados"] = margin_observations(raw["positions"], config)
    delays = []
    for cycle in result["ciclos"]:
        opened, closed, entry = cycle["opened_ns"], cycle["closed_ns"], cycle["entry_ns"]
        close_events = [r for r in raw["risk_events"] if r["symbol"] == cycle["symbol"] and
                        r["kind"] == "close_requested" and entry <= int(r["time_ns"]) <= cycle["end_ns"]]
        first_close = min((int(r["time_ns"]) for r in close_events), default=None)
        delays.append(dict(cycle_id=cycle["cycle_id"], symbol=cycle["symbol"], entry_ns=entry,
            opened_ns=opened, first_close_request_ns=first_close, closed_ns=closed,
            opening_seconds=D(opened-entry)/1_000_000_000 if opened is not None else None,
            closing_seconds=D(closed-first_close)/1_000_000_000 if closed is not None and first_close is not None else None,
            failed=cycle["failed"], still_open_at_end=cycle["still_open_at_end"]))
    result["demoras_ciclos"] = delays
    result["invariancias"] = [invariance(run, base, config, item)]
    identity = dict(scenario=item["scenario"], strategy=item["strategy"], run_id=item["run_id"])
    # Original diagnostic tables already carry identity; update consistently.
    result = {name: [dict(r, **identity) for r in rows] for name, rows in result.items()}
    for r in result["diario"]:
        r["equity_normalized_own_capital"] = r["equity_usdt"]/config.capital
        r["initial_capital_usdt"] = config.capital
    return result


def consolidate(portfolios, h3_daily, base_config):
    tables = defaultdict(list)
    for portfolio in portfolios:
        for name, rows in portfolio.items():
            tables[name].extend(rows)
    scenarios = list(dict.fromkeys(r["scenario"] for r in tables["metricas"]))
    tables["h2"] = h2_comparison(tables["metricas"])
    for scenario in scenarios:
        financials = [r for r in tables["metricas"] if r["scenario"] == scenario]
        tables["h3_resumen"].extend(dict(scenario=scenario, **r) for r in summarize_h3(h3_daily, base_config, financials))
    tables["deltas"] = deltas(tables["metricas"])
    # A semantic digest names each complete derived table before serialization.
    return dict(tables)
