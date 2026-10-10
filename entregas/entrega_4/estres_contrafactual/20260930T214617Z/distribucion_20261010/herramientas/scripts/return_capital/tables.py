"""Assemble the two authorized analyses and unchanged annual source metrics."""

import tomllib
from collections import Counter, defaultdict
from decimal import Decimal as D

from .attribution import analyze_run
from .common import RUNS, SYMBOLS, number, parquet, periods, read_csv
from .concentration import concentration
from .decisions import analyze_decisions, paired_coverage

ATTRIBUTION_NAMES = {
    "cycles": "ciclos_vida",
    "contributions": "contribuciones_ciclo_periodo",
    "segments": "atribuciones_segmentos",
    "boundaries": "fronteras_contables",
    "movements": "movimientos_ciclo",
    "checks": "conciliaciones",
}
DECISION_NAMES = {
    "classified": "decisiones_clasificadas",
    "groups": "grupos_excluyentes",
    "reasons": "motivos_simultaneos",
    "decision_cross": "diagnostico_vs_decision",
    "actions": "acciones_y_enlaces",
}


def derive(parent, correction, intraday):
    metrics = [
        r
        for r in read_csv(correction / "comparacion/metricas_cartera_periodo.csv")
        if r["scenario"] == "BASE_E3"
    ]
    daily = [
        r
        for r in read_csv(correction / "comparacion/diario_carteras.csv")
        if r["scenario"] == "BASE_E3"
    ]
    windows = periods(metrics)
    compact = parquet(intraday / "evidencia/eventos_financieros.parquet")
    tables = defaultdict(list)
    tables["metricas_reutilizadas"] = metrics
    tables["diario_reutilizado"] = daily
    for strategy, run in RUNS.items():
        root = parent / "corridas" / run
        config = tomllib.loads((root / "effective_config.toml").read_text(encoding="utf-8"))
        if config["accounting_tolerance"] != "1E-8":
            raise ValueError("Original monetary tolerance changed")
        result = analyze_run(root, compact, windows, daily, config["capital"])
        for name, rows in result.items():
            tables[ATTRIBUTION_NAMES[name]].extend(rows)
        signals, renewals, events, orders, fills = [
            parquet(root / (name + ".parquet"))
            for name in ("signals", "renewal_diagnostics", "risk_events", "orders", "fills")
        ]
        decisions = analyze_decisions(
            signals, renewals, events, orders, fills, windows, config["basis_max"]
        )
        for name, rows in decisions.items():
            tables[DECISION_NAMES[name]].extend(rows)
        accepted = {
            (r["symbol"], int(r["decision_time"])): r
            for r in decisions["classified"]
            if r["decision_kind"] == "entry" and r["decision"] == "accepted"
        }
        if len(accepted) != len(result["cycles"]):
            raise ValueError("Accepted evaluations do not reconcile to original cycle entries")
        for cycle in result["cycles"]:
            evaluation = accepted[cycle["symbol"], cycle["entry_ns"]]
            order_id = events[cycle["entry_risk_row"]]["order_id"]
            sent = [r for r in orders if r["order_id"] == order_id and r["action"] == "submitted"]
            if len(sent) != 1 or int(sent[0]["submitted_at"]) != cycle["entry_ns"]:
                raise ValueError("Accepted entry does not match a unique actual initial order")
            failures = [
                r for r in events if r["kind"] == "attempt_failed" and r.get("order_id") == order_id
            ]
            tables["entradas_acreditadas"].append(
                dict(
                    run_id=run,
                    strategy=strategy,
                    symbol=cycle["symbol"],
                    cycle_id=cycle["cycle_id"],
                    evaluation_id=evaluation["evaluation_id"],
                    initial_order_id=order_id,
                    initial_order_fills=sum(f["order_id"] == order_id for f in fills),
                    initial_order_failures=len(failures),
                    cycle_status=cycle["status"],
                    time_ns=cycle["entry_ns"],
                )
            )
        for period, lower, upper in windows:
            own_daily = [
                r for r in daily if r["run_id"] == run and lower <= int(r["time_ns"]) < upper
            ]
            day_rows = [dict(identity=r["date"], net_pnl_usdt=r["net_pnl_usdt"]) for r in own_daily]
            for row in concentration(day_rows, (1, 5, 10)):
                tables["concentracion_dias"].append(
                    dict(
                        run_id=run,
                        strategy=strategy,
                        period=period,
                        start_ns=lower,
                        end_exclusive_ns=upper,
                        **row,
                    )
                )
            for symbol in (*SYMBOLS, "PORTFOLIO"):
                selected = [
                    r
                    for r in result["contributions"]
                    if r["period"] == period
                    and r["category"] == "cycle"
                    and (symbol == "PORTFOLIO" or r["symbol"] == symbol)
                ]
                cycle_rows = [
                    dict(identity=r["cycle_id"], net_pnl_usdt=r["net_pnl_usdt"]) for r in selected
                ]
                for row in concentration(cycle_rows, (1, 3, 5)):
                    tables["concentracion_ciclos"].append(
                        dict(
                            run_id=run,
                            strategy=strategy,
                            period=period,
                            symbol=symbol,
                            start_ns=lower,
                            end_exclusive_ns=upper,
                            **row,
                        )
                    )
                own_cycles = [
                    r for r in result["cycles"] if (symbol == "PORTFOLIO" or r["symbol"] == symbol)
                ]
                overlap = [r for r in own_cycles if r["entry_ns"] < upper and r["end_ns"] >= lower]
                states = Counter(
                    "closed"
                    if r["closed_ns"] is not None and r["closed_ns"] < upper and r["complete"]
                    else r["status"]
                    if r["closed_ns"] is not None and r["closed_ns"] < upper
                    else "open_at_period_end"
                    for r in overlap
                )
                tables["conteo_ciclos_periodo"].append(
                    dict(
                        run_id=run,
                        strategy=strategy,
                        period=period,
                        symbol=symbol,
                        cycles_participating=len(overlap),
                        entries_in_period=sum(lower <= r["entry_ns"] < upper for r in own_cycles),
                        closes_in_period=sum(
                            r["closed_ns"] is not None and lower <= r["closed_ns"] < upper
                            for r in own_cycles
                        ),
                        closed=states["closed"],
                        incomplete_opening=states["incomplete_opening"],
                        attempt_without_fill=states["attempt_without_fill"],
                        open_at_period_end=states["open_at_period_end"],
                    )
                )
    tables["emparejamiento"] = paired_coverage(tables["decisiones_clasificadas"], windows)
    for row in metrics:
        run, period = row["run_id"], row["period"]
        counts = next(
            r
            for r in tables["conteo_ciclos_periodo"]
            if r["run_id"] == run and r["period"] == period and r["symbol"] == "PORTFOLIO"
        )
        own = [
            r
            for r in tables["contribuciones_ciclo_periodo"]
            if r["run_id"] == run and r["period"] == period
        ]
        outside = sum((r["net_pnl_usdt"] for r in own if r["category"] != "cycle"), D(0))
        evaluation_count = sum(
            r["count"]
            for r in tables["grupos_excluyentes"]
            if r["run_id"] == run
            and r["period"] == period
            and r["symbol"] == "PORTFOLIO"
            and r["decision_kind"] == "entry"
            and r["view"] == "market"
        )
        tables["resumen_integrado"].append(
            dict(
                row,
                **{k: v for k, v in counts.items() if k not in row and k != "symbol"},
                outside_cycle_pnl_usdt=outside,
                cycle_pnl_usdt=number(row["net_pnl_usdt"]) - outside,
                entry_evaluations=evaluation_count,
                benchmark_status="pendiente_aprobacion_benchmark",
            )
        )
    for name in (
        "h1_resumen",
        "h1_invariancia",
        "h2",
        "h3_regimen",
        "h3_invariancia",
        "componentes_por_activo_periodo",
        "exposicion_periodo",
        "eventos_periodo",
    ):
        rows = read_csv(correction / "comparacion" / (name + ".csv"))
        tables[name + "_reutilizado"] = [
            r for r in rows if r.get("scenario", "BASE_E3") == "BASE_E3"
        ]
    return dict(tables)
