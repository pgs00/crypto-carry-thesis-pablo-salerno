"""Read-only block-5 reporting from persisted continuous portfolios and witnesses."""

import json
from collections import defaultdict
from decimal import Decimal as D

from crypto_carry.config import DAY, Config, iso, timestamp
from crypto_carry.data.prescribed import prescribed_rules
from scripts.build_signal_sensitivity import projection_digest
from scripts.cost_capacity_incomplete import portfolio_with_coverage
from scripts.cost_capacity_ledger import audit_ledger
from scripts.execution_delays_audit import audit_execution, exposure_episodes, summarize_execution
from scripts.execution_delays_report import FORECAST, validate_selection
from scripts.execution_delays_sources import forecast_rows
from scripts.return_capital.common import parquet, read_csv, read_json
from scripts.signal_sensitivity_hypotheses import (
    compare_saved_h1,
    evaluate_h1,
    funding_rows_from_run,
    summarize_h1,
)
from scripts.stress_counterfactual_audit import (
    MINUTE,
    TOLERANCE,
    audit_funding_amounts,
    audit_interventions,
    audit_observation_population,
    audit_opportunity,
    audit_window_price_sources,
    audit_witness_sources,
    derived_bar,
    joint_requirement,
    number,
    preventive_requirement,
    price_attribution,
    source_bar,
)
from scripts.verify_rules_sensitivity_package import periods


def h3_daily(rows, symbols):
    groups = defaultdict(dict)
    for row in rows:
        date, symbol = row["date"], row["symbol"]
        if symbol not in symbols or symbol in groups[date]:
            raise ValueError("Duplicate or unknown H3 asset day")
        total, known, unknown, eligible = (int(row[k]) for k in (
            "minutos_totales", "minutos_conocidos", "minutos_desconocidos", "minutos_elegibles"))
        if not 0 <= eligible <= known <= total <= 1440 or known + unknown != total:
            raise ValueError("Inconsistent H3 minute counts")
        groups[date][symbol] = dict(total=total, known=known, unknown=unknown,
                                    eligible=eligible, sum=number(row["suma_forecast_elegible"]))
    result = []
    for date, group in sorted(groups.items()):
        complete = set(group) == set(symbols) and all(
            row["known"] == row["total"] == 1440 for row in group.values())
        result.append(dict(date=date, time_ns=timestamp(date + "T00:00:00Z") + DAY - 1, complete=complete,
            opportunity=sum((r["sum"] / 1440 for r in group.values()), D(0)) / len(symbols)
                        if complete else None,
            eligible_fraction=sum((D(r["eligible"]) / 1440 for r in group.values()), D(0)) / len(symbols)
                        if complete else None,
            reason="" if complete else "incomplete or unknown asset minutes",
            unit="fraction/168h", aggregation="equal asset weights; all calendar minutes"))
    return result


def audit_h3_saved(daily, saved):
    if len(daily) != len(saved):
        raise ValueError("H3 daily cohort changed")
    for actual, archived in zip(daily, saved, strict=True):
        if actual["date"] != archived["date"] or actual["complete"] != (archived["complete"] == "True"):
            raise ValueError("H3 daily completeness differs from persisted replay")
        if actual["complete"]:
            for field in ("opportunity", "eligible_fraction"):
                if abs(actual[field] - number(archived[field])) > D("1E-14"):
                    raise ValueError("H3 daily value differs from persisted replay")
    return dict(passed=True, daily_rows=len(daily), tolerance="1E-14")


def overlap_duration(start, end, intervals):
    covered, right = 0, start
    for lower, upper in sorted(intervals):
        lower, upper = max(start, lower, right), min(end, upper)
        if upper > lower:
            covered += upper - lower
            right = upper
    return covered


def fixed_calendar_coverage(spec, episodes):
    output, spans = [], defaultdict(list)
    for symbol, start, end in spec.get("episodes", []):
        a = ((start + MINUTE - 1) // MINUTE) * MINUTE
        b = max(a + MINUTE, ((end + MINUTE - 1) // MINUTE) * MINUTE)
        # Bar opened at a is first revealed at a+M; factor returns to one at b+61M.
        spans[symbol].append((a + MINUTE, b + 61 * MINUTE))
    for row in episodes:
        covered = overlap_duration(row["start_ns"], row["end_ns"], spans[row["symbol"]])
        duration = row["end_ns"] - row["start_ns"]
        output.append(dict(row, stressed_seconds=D(covered) / 1_000_000_000,
            unstressed_seconds=D(duration - covered) / 1_000_000_000,
            stressed_fraction=D(covered) / duration if duration else None,
            calendar_fixed_to_base=True, automatic_new_pulses=False))
    return output


def execution_windows(spec, originals, intervention_sources):
    result = []
    for row in originals:
        if row["market"] != "spot":
            result.append(row)
            continue
        symbol, opening = row["symbol"], int(row["open_time"])
        original = source_bar(row)
        future_row = intervention_sources.get((symbol, "futures", opening))
        modified = derived_bar(spec, original, source_bar(future_row), symbol, opening)
        if modified is None or modified == original:
            result.append(row)
            continue
        result.append(dict(row, **modified, present=True,
            scenario=spec["id"], hypothetical=True,
            original_source_sha256=row.get("source_sha256"),
            source_path=f"approved_scenario:{spec['id']}|{row.get('source_path')}",
            source_sha256=(future_row or row).get("source_sha256")))
    return result


def decode_interventions(path):
    return [dict(row, original=json.loads(row["original_json"]),
                 modified=json.loads(row["modified_json"]), source_record=json.loads(row["source_json"]))
            for row in parquet(path)]


def audit_snapshot(snapshot):
    value = number(snapshot["free_spot"]) + number(snapshot["free_futures"]) - number(snapshot["debt"])
    for asset in snapshot["assets"].values():
        spot, short = number(asset["spot"]), number(asset["short"])
        if spot:
            value += spot * number(asset["spot_price"])
        value += number(asset["collateral"])
        if short:
            value += short * (number(asset["average"]) - number(asset["mark"]))
    if abs(value - number(snapshot["equity"])) > TOLERANCE:
        raise ValueError("Window snapshot equity does not reconcile")
    if number(snapshot["reservations"]) != sum(
            (number(a["reservation"]) for a in snapshot["assets"].values()), D(0)):
        raise ValueError("Window reservations do not reconcile")


def window_ledger_components(windows, ledger):
    def value(row, field):
        return D(str(row.get(field) or 0))

    result = []
    for window in windows:
        lower, upper = int(window["start_ns"]), int(window["end_ns"])
        rows = [r for r in ledger if lower <= int(r["time_ns"]) <= upper]
        if any(value(r, "pnl") != 0 and not r["kind"].startswith(("spot_", "futures_")) for r in rows):
            raise ValueError("Unclassified realized ledger result in observed window")
        spot = sum((value(r, "pnl") for r in rows if r["kind"].startswith("spot_")), D(0))
        future = sum((value(r, "pnl") for r in rows if r["kind"].startswith("futures_")), D(0))
        fees = -sum((value(r, "fee") for r in rows), D(0))
        liquidations = -sum((value(r, "liquidation_fee") for r in rows), D(0))
        funding = sum((value(r, "funding") for r in rows), D(0))
        operations = spot + future + fees + liquidations
        result.append(dict(window_id=window["window_id"], start_ns=lower, end_inclusive_ns=upper,
            ledger_records=len(rows), spot_realized_pnl_usdt=spot, futures_realized_pnl_usdt=future,
            ordinary_fees_usdt=fees, liquidation_fees_usdt=liquidations, funding_usdt=funding,
            realized_operations_net_usdt=operations, realized_plus_funding_usdt=operations + funding,
            valuation_attribution_added=False,
            scope="realized ledger events within observation window; excludes unrealized changes; not total equity P&L"))
    return result


def window_diagnostics(evidence, spec, config, sources):
    rules = prescribed_rules(config)
    attribution, margin_assets, margin_joint, trajectory, joins = [], [], [], [], []
    scope = read_json(evidence / "estado_capa.json")["windows"]
    for persisted in parquet(evidence / "observaciones_ventanas.parquet"):
        time = int(persisted["time_ns"])
        phases = {name: json.loads(persisted[name + "_json"])
                  for name in ("before", "before_fills", "after_fills", "after")}
        for phase, snapshot in phases.items():
            if snapshot is None:
                continue
            audit_snapshot(snapshot)
            audit_window_price_sources(spec, sources, snapshot)
            state_time = int(snapshot["time_ns"])
            needs = []
            for symbol, asset in snapshot["assets"].items():
                need = preventive_requirement(asset, rules.get(symbol, "futures", state_time), config)
                needs.append(need)
                margin_assets.append(dict(time_ns=time, utc=iso(time), phase=phase, symbol=symbol,
                    state_time_ns=state_time,
                    position_state=asset["state"], spot_inventory_includes_dust=True,
                    spot_quantity=asset["spot"], short_quantity=asset["short"],
                    collateral_usdt=asset["collateral"], mark_price=asset["mark"],
                    spot_price=asset["spot_price"], spot_source=asset["spot_source"],
                    spot_source_available_at=asset["spot_source_available_at"],
                    stale_spot=asset["spot_source_available_at"] is not None
                        and state_time - int(asset["spot_source_available_at"]) > config.freshness_seconds * 1_000_000_000,
                    **need))
            cash = number(snapshot["free_spot"]) + number(snapshot["free_futures"])
            joint = joint_requirement(needs, cash, number(snapshot["reservations"]), number(snapshot["debt"]))
            margin_joint.append(dict(time_ns=time, utc=iso(time), state_time_ns=state_time, phase=phase, **joint))
        before, after = phases["before"], phases["after"]
        trajectory.append(dict(time_ns=time, utc=iso(time), equity_before_usdt=number(before["equity"]),
            prior_state_time_ns=before["time_ns"],
            equity_after_usdt=number(after["equity"]),
            equity_before_fills_usdt=number(phases["before_fills"]["equity"])
                if phases["before_fills"] else None))
        for symbol, prior in before["assets"].items():
            current = after["assets"][symbol]
            if spec["kind"] == "shock":
                attribution.append(dict(time_ns=time, utc=iso(time), symbol=symbol,
                    source_age_ns=time - int(current["original_spot_available_at"])
                        if current["original_spot_available_at"] is not None else None,
                    original_spot_source=current["original_spot_source"],
                    **price_attribution(prior, current)))
            elif time in (spec["start"] + MINUTE, spec["end"] + MINUTE):
                old, new = prior["spot_price"], current["spot_price"]
                joins.append(dict(time_ns=time, utc=iso(time), symbol=symbol,
                    edge="synthetic_start" if time == spec["start"] + MINUTE else "observed_reopening",
                    prior_price=old, current_price=new, quantity_before=prior["spot"],
                    price_jump_fraction=number(new) / number(old) - 1 if old and new else None,
                    valuation_on_prior_inventory_usdt=number(prior["spot"]) * (number(new) - number(old))
                        if old and new else None,
                    source_before=prior["spot_source"], source_after=current["spot_source"],
                    ledger_movement_created=False))
    summaries = []
    for index, (start, end) in enumerate(scope, 1):
        selected = [r for r in trajectory if start <= r["time_ns"] <= end]
        if not selected:
            continue
        first = selected[0]["equity_before_usdt"]
        points = [first] + [value for r in selected for value in
            (r["equity_before_fills_usdt"], r["equity_after_usdt"]) if value is not None]
        peak, worst = first, D(0)
        for value in points:
            peak = max(peak, value)
            if peak > 0:
                worst = min(worst, value / peak - 1)
        factors = [r for r in attribution if start <= r["time_ns"] <= end and r["evaluable"]]
        margins = [r for r in margin_joint if start <= r["time_ns"] <= end]
        summaries.append(dict(window_id=index, start_ns=start, end_ns=end, start_utc=iso(start),
            end_utc=iso(end), observations=len(selected), opening_equity_usdt=first,
            opening_state_time_ns=selected[0]["prior_state_time_ns"],
            min_observed_equity_usdt=min(points), ending_equity_usdt=points[-1],
            observed_transient_loss_from_open_usdt=min(D(0), min(points) - first),
            observed_drawdown_within_window=worst,
            imposed_drop_valuation_usdt=sum((r["imposed_drop_usdt"] for r in factors), D(0)),
            imposed_recovery_valuation_usdt=sum((r["imposed_recovery_usdt"] for r in factors), D(0)),
            underlying_spot_valuation_usdt=sum((r["underlying_price_usdt"] for r in factors), D(0)),
            max_simultaneous_external_shortfall_infimum_usdt=max(
                (r["external_shortfall_infimum_usdt"] for r in margins
                 if r["external_shortfall_infimum_usdt"] is not None), default=None),
            scope="selected intervention windows and phases; not a global intraday maximum",
            factor_attribution_applicable=spec["kind"] == "shock"))
    return dict(atribucion_valoracion=attribution, garantias_ventanas=margin_assets,
        garantias_simultaneas=margin_joint, trayectoria_ventanas=trajectory,
        ventanas_resumen=summaries, uniones_contrafactual=joins)


def hypothesis_h1(run, base, config, cache):
    signals = parquet(run / "signals.parquet")
    validate_selection(signals, config)
    funding = funding_rows_from_run(run)
    fields = ("symbol", "funding_time", "available_at", "funding_rate", "interval_hours", "interval_verified")
    funding_hash = projection_digest(funding, fields)
    forecast_hash = projection_digest(signals, FORECAST)
    key = funding_hash, forecast_hash
    if key not in cache:
        observations, schedules, audit = evaluate_h1(signals, funding, config)
        cache[key] = observations, audit
    observations, audit = cache[key]
    compare_saved_h1(observations, forecast_rows(run))
    reference = parquet(base / "signals.parquet")
    original_funding_hash = projection_digest(funding_rows_from_run(base), fields)
    original_forecast_hash = projection_digest(reference, FORECAST)
    return dict(h1_observaciones=observations, h1_resumen=summarize_h1(observations, config),
        h1_controles=[dict(forecast_sha256=forecast_hash, funding_sha256=funding_hash,
            original_forecast_sha256=original_forecast_hash,
            original_funding_sha256=original_funding_hash,
            equal_to_original=key == (original_funding_hash, original_forecast_hash),
            exact_cohort_reuse_permitted=key == (original_funding_hash, original_forecast_hash),
            observed_cohort=len(observations),
            available_at_checked=True, evaluation_targets_not_trading_information=True,
            audit=audit)])


def derive_portfolio(run, item, originals, sources, spec, evidence, base, h1_cache):
    config = Config.load(run / "effective_config.toml")
    result = portfolio_with_coverage(run, item)
    raw = {name: parquet(run / f"{name}.parquet")
           for name in ("orders", "fills", "ledger", "risk_events", "positions")}
    windows = execution_windows(spec, originals, sources)
    execution = audit_execution(config, raw["orders"], raw["fills"], raw["ledger"], windows,
                                risk_events=raw["risk_events"])
    result.update(execution)
    result["conciliacion_ledger"] = [audit_ledger(config, raw["ledger"],
                                                read_csv(run / "equity_daily.csv"), raw["positions"])]
    consumed = read_json(run / "funding_mark_audit.json")["consumed"]
    result["funding_importes"] = audit_funding_amounts(raw["ledger"], consumed)
    funding_fields = ("symbol", "funding_time", "available_at", "funding_rate", "interval_hours",
                      "interval_verified", "settlement_mark_price", "settlement_mark_available_at",
                      "settlement_mark_close_time", "settlement_mark_method")
    actual_funding = projection_digest(consumed, funding_fields)
    base_funding = projection_digest(read_json(base / "funding_mark_audit.json")["consumed"], funding_fields)
    result["funding_fuentes"] = [dict(rates_and_marks_equal=actual_funding == base_funding,
        scenario_projection_sha256=actual_funding, original_projection_sha256=base_funding,
        amounts_recomputed_from_scenario_inventory=True)]
    if item["engine_status"] == "complete" and actual_funding != base_funding:
        raise ValueError("Funding rates/settlement marks changed in a complete scenario")
    result["ejecucion_resumen"] = summarize_execution(execution, periods(config.to_dict()))
    episodes = exposure_episodes(result["exposicion_intervalos"])
    result["episodios_descubiertos"] = episodes
    result["cobertura_calendario_fijo"] = fixed_calendar_coverage(spec, episodes) if spec["kind"] == "shock" else []
    result.update(hypothesis_h1(run, base, config, h1_cache))
    if evidence is not None:
        observed_end = int(read_csv(run / "run_summary.csv")[0]["time_ns"])
        intervened = decode_interventions(evidence / "intervenciones.parquet")
        state = read_json(evidence / "estado_capa.json")
        if len(intervened) != state["intervention_rows"]:
            raise ValueError("Intervention journal count differs from final layer state")
        result["control_transformaciones"] = [audit_interventions(spec, sources, intervened, observed_end)]
        witnesses = [json.loads(r["evidence_json"]) for r in parquet(evidence / "oportunidad_ventanas.parquet")]
        for witness in witnesses:
            audit_witness_sources(spec, sources, witness)
        result["cobertura_testigos"] = [audit_observation_population(spec,
            state,
            parquet(evidence / "observaciones_ventanas.parquet"), witnesses,
            timestamp(config.start), observed_end, config.symbols)]
        result["h3_testigos"] = [audit_opportunity(r, config) for r in witnesses]
        asset_days = read_csv(evidence / "h3_minutos" / (item["run_id"] + ".csv"))
        result["h3_por_activo"] = asset_days
        result["h3_diario"] = h3_daily(asset_days, config.symbols)
        result["h3_controles"] = [audit_h3_saved(result["h3_diario"], read_csv(run / "opportunity_daily.csv"))]
        result.update(window_diagnostics(evidence, spec, config, sources))
        result["operaciones_ventanas"] = window_ledger_components(result["ventanas_resumen"], raw["ledger"])
    else:
        result["h3_diario"] = [dict(row, opportunity=number(row["opportunity"]) if row["opportunity"] else None,
                eligible_fraction=number(row["eligible_fraction"]) if row["eligible_fraction"] else None)
                for row in read_csv(run / "opportunity_daily.csv")]
    identity = dict(scenario=item["scenario"], strategy=item["strategy"], run_id=item["run_id"])
    return {name: [dict(row, **identity) for row in rows] for name, rows in result.items()}
