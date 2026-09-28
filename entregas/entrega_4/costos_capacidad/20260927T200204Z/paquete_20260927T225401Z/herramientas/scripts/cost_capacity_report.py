"""Derived block-3 results and hypothesis invariance, with no economic replay."""

from collections import Counter, defaultdict
from decimal import Decimal as D

from crypto_carry.config import DAY, Config, timestamp
from crypto_carry.data.prescribed import prescribed_rules
from crypto_carry.margin import _tier, maintenance
from scripts.build_signal_sensitivity import deltas, projection_digest
from scripts.cost_capacity_audit import audit_execution, exposure_episodes, summarize_execution
from scripts.cost_capacity_incomplete import portfolio_with_coverage
from scripts.cost_capacity_ledger import audit_ledger
from scripts.cost_capacity_sources import forecast_rows
from scripts.return_capital.common import parquet, read_csv
from scripts.rules_sensitivity_h2 import h2_comparison
from scripts.signal_sensitivity_hypotheses import summarize_h3
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
    daily = read_csv(run/"equity_daily.csv")
    complete = [int(r["time_ns"]) for r in daily] == list(range(timestamp(config.start)+DAY-1, timestamp(config.end), DAY))
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
        actual_rows = forecast_rows(run) if filename == "forecast_evaluation.csv" else read_csv(run/filename)
        base_rows = forecast_rows(base) if filename == "forecast_evaluation.csv" else read_csv(base/filename)
        a, b = projection_digest(actual_rows, fields), projection_digest(base_rows, fields)
        output.update({name+"_sha256": a, name+"_base_sha256": b, name+"_equal": a == b})
        if complete and a != b:
            raise ValueError("Unexpected change in invariant "+name)
    return output


def margin_observations(rows, config):
    rules = prescribed_rules(config)
    result, prior_tier = [], {}
    for row in rows:
        q = D(row["short"])
        if q == 0:
            prior_tier[row["symbol"]] = None
            continue
        mark = D(row["mark_price"]) if row.get("mark_price") not in (None, "") else None
        time = int(row["time_ns"])
        rule = rules.get(row["symbol"], "futures", time)
        reason = ""
        try:
            if mark is None or mark <= 0 or rule is None:
                raise ValueError("missing mark or prescribed rule; not evaluable")
            tier = _tier(q*mark, rule)
            mm = maintenance(q, mark, rule)
        except ValueError as exc:
            tier, mm, reason = None, None, str(exc)
        before = prior_tier.get(row["symbol"])
        current = tier.floor if tier else None
        result.append(dict(symbol=row["symbol"], time_ns=time, short_quantity=q, mark_price=mark,
            short_notional=q*mark if mark is not None else None, tier_floor=tier.floor if tier else None,
            tier_cap=tier.cap if tier else None, tier_rate=tier.rate if tier else None,
            tier_deduction=tier.deduction if tier else None, maintenance_usdt=mm,
            previous_active_tier_floor=before,
            observed_tier_change=before is not None and current is not None and before != current,
            reason=reason, frequency="persisted position snapshots; not full intraday series"))
        prior_tier[row["symbol"]] = current
    return result


def explain_cases(extremes, capacity, episodes, orders):
    result = []
    for case in extremes:
        relevant = [o for o in orders if o["symbol"] == case["symbol"] and
                    case["start_ns"] <= o["window_end"] <= case["end_ns"]]
        details = dict(case)
        details["order_ids"] = [o["order_id"] for o in relevant]
        details["purposes"] = sorted({o["purpose"] for o in relevant})
        details["shortfall_causes"] = dict(sorted(Counter(o["shortfall_cause"] for o in relevant if o["unfilled_quantity"] > 0).items()))
        details["orders_complete"] = sum(o["execution_outcome"] == "complete" for o in relevant)
        details["orders_partial"] = sum(o["execution_outcome"] == "partial" for o in relevant)
        details["orders_no_fill"] = sum(o["execution_outcome"] == "no_fill" for o in relevant)
        if case["group"] == "capacity":
            c = next(r for r in capacity if (r["symbol"], r["market"], r["window_start"]) == (case["symbol"], case["market"], case["start_ns"]))
            # Restrict this explanation to its instrument/market/minute key.
            relevant = [o for o in relevant if o["market"] == case["market"] and o["window_start"] == case["start_ns"]]
            details.update({k: c[k] for k in ("executed_gross_quantity", "base_volume", "capacity_quantity", "participation_limit", "realized_participation", "source_path", "source_sha256")})
            details["explanation"] = (
                f"Cantidad bruta {c['executed_gross_quantity']} sobre volumen base {c['base_volume']}; "
                f"cupo {c['capacity_quantity']} con límite {c['participation_limit']}. "
                "El uso alto del cupo no prueba por sí solo una ejecución fallida. "
                "El volumen corresponde a la ventana posterior al envío.")
        else:
            e = next(r for r in episodes if r["episode_id"] == case["case_id"])
            details.update(states=e["states"], max_abs_quantity_gap=e["max_abs_quantity_gap"])
            details["explanation"] = (
                f"Exposición activa descubierta durante {e['seconds']} segundos; "
                f"descalce absoluto máximo {e['max_abs_quantity_gap']} {case['symbol'].removesuffix('USDT')}. "
                f"Estados persistidos: {', '.join(e['states'])}. "
                "Las causas de órdenes coincidentes son evidencia operativa, no una atribución causal exclusiva del episodio.")
        details["order_ids"] = [o["order_id"] for o in relevant]
        details["purposes"] = sorted({o["purpose"] for o in relevant})
        details["shortfall_causes"] = dict(sorted(Counter(o["shortfall_cause"] for o in relevant if o["unfilled_quantity"] > 0).items()))
        for outcome in ("complete", "partial", "no_fill"):
            details["orders_"+outcome] = sum(o["execution_outcome"] == outcome for o in relevant)
        result.append(details)
    return result


def derive_portfolio(run, item, windows, base):
    config = Config.load(run/"effective_config.toml")
    result = portfolio_with_coverage(run, item)
    raw = {n: parquet(run/f"{n}.parquet") for n in ("orders", "fills", "ledger", "risk_events", "positions")}
    execution = audit_execution(config, raw["orders"], raw["fills"], raw["ledger"], windows)
    result.update(execution)
    result["conciliacion_ledger"] = [audit_ledger(config, raw["ledger"],
                                  read_csv(run/"equity_daily.csv"), raw["positions"])]
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
    result["casos_explicados"] = explain_cases(extremes, execution["capacidad"], episodes, execution["ordenes"])
    causes = []
    for period, lower, upper in periods(config.to_dict()):
        counts = Counter((r["symbol"], r["market"], r["shortfall_cause"]) for r in execution["ordenes"]
                         if lower <= r["submitted_at"] < upper and r["unfilled_quantity"] > 0)
        causes.extend(dict(period=period, symbol=s, market=m, cause=c, orders=n)
                      for (s, m, c), n in sorted(counts.items()))
    result["causas_faltantes"] = causes
    result["tramos_margen_estados"] = margin_observations(raw["positions"], config)
    margin_summary = []
    for period, lower, upper in periods(config.to_dict()):
        for symbol in config.symbols:
            selected = [r for r in result["tramos_margen_estados"] if r["symbol"] == symbol and lower <= r["time_ns"] < upper]
            known = [r for r in selected if r["tier_floor"] is not None]
            margin_summary.append(dict(period=period, symbol=symbol, active_snapshots=len(selected),
                non_evaluable=len(selected)-len(known),
                tier_floors=sorted({str(r["tier_floor"]) for r in known}),
                observed_tier_changes=sum(r["observed_tier_change"] for r in selected),
                max_observed_notional=max((r["short_notional"] for r in known), default=None),
                frequency="persisted position snapshots; no reconstruction of full intraday maximum"))
    result["tramos_margen_resumen"] = margin_summary
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
    tables["deltas"] = comparable_deltas(tables["metricas"])
    # A semantic digest names each complete derived table before serialization.
    return dict(tables)


def comparable_deltas(metrics):
    """Keep observed balances, but do not subtract incompatible time windows."""
    by_key = {(r["scenario"], r["strategy"], r["period"]): r for r in metrics}
    rows = deltas(metrics)
    for row in rows:
        actual = by_key[row["scenario"], row["strategy"], row["period"]]
        base = by_key["BASE_E3", row["strategy"], row["period"]]
        complete = all(r.get("coverage_complete") in (True, "True") for r in (actual, base))
        same_window = all(actual.get(k) == base.get(k) for k in ("start_utc", "end_exclusive_utc"))
        if not complete or not same_window:
            row.update(delta=None, reason="incomplete_comparable_window")
    return rows
