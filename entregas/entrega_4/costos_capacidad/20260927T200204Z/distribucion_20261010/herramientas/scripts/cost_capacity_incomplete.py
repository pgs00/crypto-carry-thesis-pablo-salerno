"""Interrupted portfolios retain observed balances; never invent later coverage."""

from decimal import Decimal as D

from crypto_carry.config import DAY, Config, iso, timestamp
from scripts import verify_rules_sensitivity_package as core
from scripts.continuous_delivery.portfolio import activity_summary
from scripts.report_historical_rules_sensitivity import execution_periods, margin_daily
from scripts.return_capital.accounting import cycle_catalog
from scripts.return_capital.common import parquet, read_csv, read_json
from scripts.return_capital.decisions import analyze_decisions
from scripts.rules_sensitivity_exposure import exposure_intervals, exposure_summary
from scripts.signal_sensitivity_report import financial_tables, portfolio_tables


def observed_financial_periods(daily, periods):
    result = []
    for label, lower, upper in periods:
        selected = [r for r in daily if lower <= r["time_ns"] < upper]
        expected = list(range(lower+DAY-1, upper, DAY))
        complete = bool(selected) and [r["time_ns"] for r in selected] == expected and not any(r["partial_day"] for r in selected)
        if complete:
            result.extend(core.period_financials(daily, [(label, lower, upper)]))
            continue
        reason = "incomplete observed coverage after economic stop"
        opening = selected[0]["starting_equity_usdt"] if selected else None
        final = selected[-1]["equity_usdt"] if selected else None
        row = dict(period=label, start_utc=iso(lower), end_exclusive_utc=iso(upper),
            observed_end_exclusive_utc=iso(selected[-1]["time_ns"]+1) if selected else None,
            days=sum(not r["partial_day"] for r in selected), observed_snapshots=len(selected),
            coverage_complete=False, coverage_reason=reason,
            balance_scope="last observed balance within nominal period; not extrapolated to requested end",
            starting_equity_usdt=opening, final_equity_usdt=final,
            net_pnl_usdt=final-opening if selected else None)
        for name in ("net_return", "cagr", "sharpe", "annual_volatility", "max_drawdown", "max_drawdown_days"):
            row[name], row[name+"_reason"] = None, reason
        for name in (*core.COMPONENTS, *core.SPLIT_COMPONENTS):
            row[name] = sum((r[name] for r in selected), D(0)) if selected else None
        row["reconciliation_residual_usdt"] = (row["net_pnl_usdt"]-sum(row[k] for k in core.COMPONENTS[:-1])) if selected else None
        if selected and abs(row["reconciliation_residual_usdt"]) > core.TOLERANCE:
            raise ValueError("Observed interrupted P&L does not reconcile")
        for name in ("capital_deployed_usdt", "capital_utilization", "gross_exposure_usdt", "collateral_usdt", "debt_usdt"):
            row[name+"_daily_mean"] = row[name+"_daily_max"] = None
        result.append(row)
    return result


def financial_for_run(run, config):
    raw = read_csv(run/"equity_daily.csv")
    status = read_json(run/"run_manifest.json")["status"]
    if status == "complete":
        return financial_tables(raw, config)
    if status != "insolvent":
        raise ValueError("Unsupported unfinished technical run")
    daily, assets = core.financial_daily(raw, config.capital)
    return daily, assets, observed_financial_periods(daily, core.periods(config.to_dict()))


def portfolio_with_coverage(run, item):
    if item["engine_status"] == "complete":
        return portfolio_tables(run, item)
    config = Config.load(run/"effective_config.toml")
    periods = core.periods(config.to_dict())
    raw_daily = read_csv(run/"equity_daily.csv")
    # The current engine can remain insolvent while still observing later days.
    # Economic status alone therefore does not imply an interrupted calendar.
    expected = list(range(timestamp(config.start)+DAY-1, timestamp(config.end), DAY))
    if ([int(r["time_ns"]) for r in raw_daily] == expected
            and not any(core.yes(r["partial_day"]) for r in raw_daily)):
        return portfolio_tables(run, item)
    summary = read_csv(run/"run_summary.csv")
    if len(summary) != 1 or summary[0]["status"] != "insolvent" or not summary[0]["stopped_at"]:
        raise ValueError("Interrupted portfolio requires an authenticated economic stop")
    stopped = str(summary[0]["stopped_at"])
    stop_ns = int(stopped) if stopped.isdigit() else timestamp(stopped)
    if stop_ns != int(summary[0]["time_ns"]):
        raise ValueError("Economic stop differs from final observed clock")
    end = min(timestamp(config.end), stop_ns+1)
    if end <= timestamp(config.start):
        raise ValueError("Invalid economic stop boundary")
    raw = {n: parquet(run/f"{n}.parquet") for n in ("positions", "fills", "orders", "risk_events", "signals", "renewal_diagnostics", "funding_payments", "ledger")}
    if any(int(row["time_ns"]) > stop_ns for rows in raw.values() for row in rows):
        raise ValueError("Persisted events extend after economic stop")
    daily, assets, metrics = financial_for_run(run, config)
    if any(r["time_ns"] >= end for r in daily):
        raise ValueError("Daily records extend after actual economic stop")
    clipped = [(name, lower, min(upper, end)) for name, lower, upper in periods if lower < end]
    intervals = exposure_intervals(raw["positions"], timestamp(config.start), end, config.hedge_tolerance)
    exposures = exposure_summary(intervals, clipped)
    for row in exposures:
        row["denominator_scope"] = "observed calendar clipped at economic stop"
    cycles = cycle_catalog(raw["risk_events"], end)
    activity = activity_summary(raw["fills"], raw["orders"], raw["risk_events"], cycles, clipped)
    decisions = analyze_decisions(raw["signals"], raw["renewal_diagnostics"], raw["risk_events"], raw["orders"], raw["fills"], clipped, str(config.basis_max))
    margins = margin_daily(read_csv(run/"equity_daily.csv"), read_json(run/"research_assumptions.json"))
    for row in metrics:
        exposure = next((r for r in exposures if r["period"] == row["period"] and r["symbol"] == "PORTFOLIO"), {})
        row.update({k: v for k, v in exposure.items() if k not in {"period", "symbol"}})
        row.setdefault("invested_fraction", None)
        row.update(engine_status="insolvent", margin_frequency="observed daily closes only",
                   maintenance_to_balance_max_daily_close=None)
    components = []
    for period, lower, upper in periods:
        for symbol in config.symbols:
            chosen = [r for r in assets if r["symbol"] == symbol and lower <= r["time_ns"] < upper]
            components.append(dict(period=period, symbol=symbol, coverage_complete=upper <= end,
                **{k: sum((r[k] for r in chosen), D(0)) if chosen else None
                   for k in (*core.COMPONENTS, *core.SPLIT_COMPONENTS, "net_pnl_usdt")}))
    result = dict(metricas=metrics, semantica_metricas=[], diario=daily, componentes_diarios=assets,
        componentes_periodo=components, exposicion_intervalos=intervals, exposicion_periodo=exposures,
        ciclos=cycles, actividad=activity, eventos=execution_periods(raw, clipped), motivos_cierre=[],
        margen_cierre_diario=margins, decisiones=decisions["classified"], grupos_entradas=decisions["groups"],
        motivos_simultaneos=decisions["reasons"], diagnostico_vs_decision=decisions["decision_cross"], acciones=decisions["actions"])
    return result
