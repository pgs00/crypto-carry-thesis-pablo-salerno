"""Portfolio evidence derived from persisted state, corrected exposure and corrected H2."""

from __future__ import annotations

from decimal import Decimal as D

from crypto_carry.config import Config, timestamp

if __package__:
    from . import verify_rules_sensitivity_package as core
    from .continuous_delivery.portfolio import activity_summary
    from .report_historical_rules_sensitivity import execution_periods, margin_daily
    from .return_capital.accounting import cycle_catalog
    from .return_capital.common import parquet, read_csv, read_json
    from .return_capital.decisions import analyze_decisions
    from .rules_sensitivity_exposure import exposure_intervals, exposure_summary
else:
    import verify_rules_sensitivity_package as core
    from continuous_delivery.portfolio import activity_summary
    from report_historical_rules_sensitivity import execution_periods, margin_daily
    from return_capital.accounting import cycle_catalog
    from return_capital.common import parquet, read_csv, read_json
    from return_capital.decisions import analyze_decisions
    from rules_sensitivity_exposure import exposure_intervals, exposure_summary


def financial_tables(raw_daily, config):
    daily, assets = core.financial_daily(raw_daily, config.capital)
    periods = core.period_financials(daily, core.periods(config.to_dict()))
    for row in periods:
        if abs(row["reconciliation_residual_usdt"]) > config.accounting_tolerance:
            raise ValueError(f"Period accounting does not reconcile: {row['period']}")
        row["net_return_reason"] = "" if row["net_return"] is not None else "nonpositive starting equity"
        row["max_drawdown_reason"] = "" if row["max_drawdown"] is not None else "nonpositive starting equity"
        if row["starting_equity_usdt"] <= 0:
            row["max_drawdown_days"] = None
    return daily, assets, periods


def compare_archived_metrics(archived, row):
    differences = []
    undefined = {"net_return", "max_drawdown", "max_drawdown_days"} if row["starting_equity_usdt"] <= 0 else set()
    for field in ("net_return", "cagr", "sharpe", "annual_volatility", "max_drawdown", "max_drawdown_days"):
        if field in undefined:
            reason_field = "net_return_reason" if field == "net_return" else "max_drawdown_reason"
            if row[field] is not None or row[reason_field] != "nonpositive starting equity":
                raise ValueError("Nonpositive inherited equity requires explicit ND")
            differences.append(dict(metric=field, archived_value=archived[field], reported_value=None,
                                    reason="nonpositive starting equity"))
        else:
            core.assert_close(archived[field], row[field], field)
    if undefined and any(row[k] != "nonpositive equity or insolvency" for k in ("cagr_reason", "sharpe_reason")):
        raise ValueError("Nonpositive equity lacks its statistical ND reason")
    return differences


def portfolio_tables(run, item):
    config = Config.load(run/"effective_config.toml")
    periods = core.periods(config.to_dict())
    raw_daily = read_csv(run/"equity_daily.csv")
    daily, assets, metrics = financial_tables(raw_daily, config)
    metric_semantics = []
    for archived in read_csv(run/"metrics.csv"):
        row = next(r for r in metrics if r["period"] == archived["period"])
        metric_semantics += [dict(period=row["period"], **r) for r in compare_archived_metrics(archived, row)]
    raw = {name: parquet(run/f"{name}.parquet") for name in (
        "positions", "fills", "orders", "risk_events", "signals", "renewal_diagnostics",
        "funding_payments", "ledger")}
    intervals = exposure_intervals(raw["positions"], timestamp(config.start), timestamp(config.end),
                                   config.hedge_tolerance)
    exposures = exposure_summary(intervals, periods)
    exposure_by_period = {r["period"]: r for r in exposures if r["symbol"] == "PORTFOLIO"}
    for row in metrics:
        row.update({k: v for k, v in exposure_by_period[row["period"]].items()
                    if k not in {"period", "symbol"}})
    cycles = cycle_catalog(raw["risk_events"], timestamp(config.end))
    activity = activity_summary(raw["fills"], raw["orders"], raw["risk_events"], cycles, periods)
    for row in activity:
        _, lower, upper = next(p for p in periods if p[0] == row["period"])
        relevant = [c for c in cycles if row["symbol"] == "PORTFOLIO" or c["symbol"] == row["symbol"]]
        row["inherited_cycles_at_start"] = sum(
            c["entry_ns"] < lower and (c["closed_ns"] is None or c["closed_ns"] >= lower)
            for c in relevant)
        row["open_cycles_at_end"] = sum(
            c["entry_ns"] < upper and (c["closed_ns"] is None or c["closed_ns"] >= upper)
            for c in relevant)
    events = execution_periods(raw, periods)
    decision = analyze_decisions(raw["signals"], raw["renewal_diagnostics"], raw["risk_events"],
                                 raw["orders"], raw["fills"], periods, str(config.basis_max))
    margins = margin_daily(raw_daily, read_json(run/"research_assumptions.json"))
    for row in metrics:
        _, lower, upper = next(p for p in periods if p[0] == row["period"])
        selected = [r for r in margins if lower <= r["time_ns"] < upper]
        ratios = [r["maintenance_to_balance_max"] for r in selected
                  if r["maintenance_to_balance_max"] is not None]
        row["maintenance_to_balance_max_daily_close"] = max(ratios) if ratios else None
        row["margin_frequency"] = "daily_close_only"
        row["engine_status"] = item["engine_status"]
    component_periods = []
    for period, lower, upper in periods:
        for symbol in config.symbols:
            rows = [r for r in assets if r["symbol"] == symbol and lower <= r["time_ns"] < upper]
            component_periods.append(dict(period=period, symbol=symbol, **{
                k: sum((r[k] for r in rows), D(0))
                for k in (*core.COMPONENTS, *core.SPLIT_COMPONENTS, "net_pnl_usdt")}))
    closing_causes = []
    for period, lower, upper in periods:
        counts = {}
        for r in raw["risk_events"]:
            if lower <= int(r["time_ns"]) < upper and r.get("kind") == "close_requested":
                key = (r["symbol"], r.get("cause", ""))
                counts[key] = counts.get(key, 0)+1
        closing_causes += [dict(period=period, symbol=s, cause=c, close_requests=n)
                           for (s, c), n in sorted(counts.items())]
    result = dict(metricas=metrics, semantica_metricas=metric_semantics, diario=daily, componentes_diarios=assets,
                  componentes_periodo=component_periods, exposicion_intervalos=intervals,
                  exposicion_periodo=exposures, ciclos=cycles, actividad=activity,
                  eventos=events, motivos_cierre=closing_causes, margen_cierre_diario=margins,
                  decisiones=decision["classified"], grupos_entradas=decision["groups"],
                  motivos_simultaneos=decision["reasons"], diagnostico_vs_decision=decision["decision_cross"],
                  acciones=decision["actions"])
    identity = dict(scenario=item["scenario"], strategy=item["strategy"], run_id=item["run_id"],
                    horizon_hours=config.horizon_hours)
    return {name: [dict(row, **identity) for row in rows] for name, rows in result.items()}
