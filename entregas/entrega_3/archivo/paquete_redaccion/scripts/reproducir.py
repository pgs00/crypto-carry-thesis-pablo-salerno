"""Rebuild portable tables and checks solely from the supplied evidence subset."""

import argparse
import csv
import hashlib
import json
from collections import Counter
from datetime import datetime
from decimal import Decimal, localcontext
from pathlib import Path

import numpy as np
from generar_figuras import figures

D = Decimal
PACKAGE = Path(__file__).resolve().parents[1]
EVIDENCE = "evidencia/revision/"
RUNS = {"early": "run_f4151cc97937f3704d77fb14", "late": "run_519a165818e2cadce24bc873"}
LABELS = {"early": "2022–2023", "late": "2025–2026"}
TRACES = []
CHECKS = []


def read(path):
    with (PACKAGE / path).open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def load(path):
    return json.loads((PACKAGE / path).read_text(encoding="utf-8"))


def write(destination, relative, rows):
    path = destination / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def trace(table, row_key, field, value, unit, source, original_field, selection, formula=""):
    TRACES.append(
        dict(
            id_cifra=f"F{len(TRACES) + 1:05d}",
            archivo_presentado=table,
            seleccion_presentada=row_key,
            campo_presentado=field,
            valor_original=value,
            unidad=unit,
            archivo_fuente=source,
            campo_fuente=original_field,
            filtro_fuente=selection,
            calculo=formula,
            run_id=next(
                (r for r in RUNS.values() if r in source), RUNS.get(row_key.split("/")[0], "COMMON")
            ),
        )
    )


def check(name, actual, expected, tolerance=D(0), context=""):
    difference = abs(
        D(int(actual) if isinstance(actual, bool) else str(actual))
        - D(int(expected) if isinstance(expected, bool) else str(expected))
    )
    passed = difference <= tolerance
    CHECKS.append(
        dict(
            control=name,
            contexto=context,
            obtenido=str(actual),
            esperado=str(expected),
            diferencia=str(difference),
            tolerancia=str(tolerance),
            aprobado=passed,
        )
    )
    if not passed:
        raise ValueError(f"{name}/{context}: {actual} != {expected}")


def select(rows, **filters):
    matches = [row for row in rows if all(row.get(k) == v for k, v in filters.items())]
    if len(matches) != 1:
        raise ValueError(f"Expected one row for {filters}, got {len(matches)}")
    return matches[0]


def metric_check(equities, capital, source, key):
    """Use the persisted binary64 convention, with initial capital as the first balance."""
    equity = np.array([float(capital)] + [float(row["equity"]) for row in equities])
    returns = equity[1:] / equity[:-1] - 1
    deviation = float(np.std(returns, ddof=1))
    calculated = dict(
        net_return=equity[-1] / float(capital) - 1,
        cagr=float(np.exp(np.log(equity[-1] / float(capital))) - 1),
        max_drawdown=float(np.min(equity / np.maximum.accumulate(equity) - 1)),
        annual_volatility=deviation * np.sqrt(365),
    )
    if deviation:
        calculated["sharpe"] = float(np.mean(returns)) / deviation * np.sqrt(365)
    else:
        check("Sharpe nulo por volatilidad nula", source["sharpe"] == "", True, context=key)
        if source["sharpe_reason"] != "zero sample volatility":
            raise ValueError("Undefined Sharpe reason changed")
    for name, value in calculated.items():
        check("Métrica diaria: " + name, value, source[name], D("1e-12"), key)
    return returns


def core_tables(destination):
    summary = [r for r in read(EVIDENCE + "scenario_summary.csv") if r["scenario"] == "vwap_joint"]
    check("Cuatro carteras principales", len(summary), 4)
    results, components, daily, activity, parameters, coverage = [], [], [], [], [], []
    result_map = {
        "capital_inicial_usdt": ("capital_usdt", "USDT"),
        "equity_final_usdt": ("final_equity_usdt", "USDT"),
        "retorno_neto": ("net_return", "proporción"),
        "cagr": ("cagr", "proporción/año"),
        "sharpe": ("sharpe", "razón"),
        "drawdown_diario": ("max_drawdown", "proporción con signo"),
        "aperturas_completas": ("openings", "aperturas"),
        "ciclos_cerrados": ("complete_cycles", "ciclos"),
        "intentos_orden_fallidos": ("failed_attempts", "órdenes/intentos"),
        "aperturas_fallidas": ("failed_cycles", "ciclos sin apertura completa"),
        "intentos_apertura": ("opening_attempts", "aperturas intentadas"),
        "fills": ("fills", "fills"),
        "fills_parciales": ("partial_fills", "fills"),
    }
    pnl_map = {
        "spot_usdt": "spot_pnl",
        "futuros_usdt": "futures_pnl",
        "funding_usdt": "funding",
        "comisiones_usdt": "fees",
        "liquidaciones_usdt": "liquidation_fees",
        "slippage_informativo_usdt": "slippage_informational",
    }
    for row in summary:
        window, strategy, run = row["window"], row["strategy"], row["run_id"]
        check("Corrida corresponde a ventana", run == RUNS[window], True)
        base = f"evidencia/corridas/{run}/"
        manifest = load(base + "run_manifest.json")
        config = manifest["config"]
        check(
            "Duración de la ventana",
            (datetime.fromisoformat(config["end"]) - datetime.fromisoformat(config["start"])).days,
            365,
        )
        key = window + "/" + strategy
        selector = f"window={window};scenario=vwap_joint;strategy={strategy}"
        metadata = dict(
            ventana=window,
            estrategia=strategy,
            run_id=run,
            inicio_utc=config["start"],
            fin_exclusivo_utc=config["end"],
        )
        result = dict(metadata)
        for name, (original, unit) in result_map.items():
            result[name] = row[original]
            trace(
                "tablas/resultados_principales.csv",
                key,
                name,
                row[original],
                unit,
                EVIDENCE + "scenario_summary.csv",
                original,
                selector,
            )
        metric = select(read(base + "metrics.csv"), strategy=strategy, period="full")
        for name in ("cagr_reason", "sharpe_reason"):
            translated = "cagr_motivo_nulo" if name == "cagr_reason" else "sharpe_motivo_nulo"
            result[translated] = (
                "volatilidad muestral nula"
                if metric[name] == "zero sample volatility"
                else metric[name]
            )
        results.append(result)
        equity = sorted(
            [
                r
                for r in read(base + "equity_daily.csv")
                if r["strategy"] == strategy and r["partial_day"] == "False"
            ],
            key=lambda r: int(r["time_ns"]),
        )
        check("Días completos", len(equity), 365, context=key)
        check("Fechas únicas", len({r["timestamp_utc"][:10] for r in equity}), 365, context=key)
        check(
            "Cierres diarios consecutivos",
            all(
                int(b["time_ns"]) - int(a["time_ns"]) == 86400_000_000_000
                for a, b in zip(equity, equity[1:])
            ),
            True,
            context=key,
        )
        check("Equity final", equity[-1]["equity"], row["final_equity_usdt"], context=key)
        check(
            "Fecha inicial",
            equity[0]["timestamp_utc"][:10] == config["start"][:10],
            True,
            context=key,
        )
        float_returns = metric_check(equity, D(config["capital"]), metric, key)
        previous = D(config["capital"])
        for eq, float_return in zip(equity, float_returns):
            value = D(eq["equity"])
            daily.append(
                dict(
                    ventana=window,
                    estrategia=strategy,
                    run_id=run,
                    fecha_utc=eq["timestamp_utc"][:10],
                    instante_utc=eq["timestamp_utc"],
                    time_ns=eq["time_ns"],
                    equity_usdt=eq["equity"],
                    retorno_diario_decimal=str(value / previous - 1),
                    retorno_diario_metricas=str(float_return),
                    capital_inicial_usdt=config["capital"],
                )
            )
            previous = value
        for field, original, formula in (
            ("equity_usdt", "equity", "copia decimal sin redondeo"),
            (
                "retorno_diario_decimal",
                "equity; config.capital",
                "equity_t/equity_anterior-1; primer denominador=capital; Decimal 60",
            ),
            (
                "retorno_diario_metricas",
                "equity; config.capital",
                "mismo cociente en binary64, convención de métricas persistidas",
            ),
        ):
            trace(
                "datos/equity_diaria.csv",
                key + "/cada fecha_utc",
                field,
                "serie completa",
                "USDT" if field == "equity_usdt" else "proporción/día",
                base + "equity_daily.csv",
                original,
                f"strategy={strategy};partial_day=False;orden time_ns",
                formula,
            )
        pc = {
            r["component"]: r["amount_usdt"]
            for r in read(base + "pnl_components.csv")
            if r["strategy"] == strategy
        }
        pnl = dict(metadata)
        for name, original in pnl_map.items():
            pnl[name] = pc[original]
            trace(
                "tablas/pnl_componentes.csv",
                key,
                name,
                pc[original],
                "USDT",
                base + "pnl_components.csv",
                "amount_usdt",
                f"strategy={strategy};component={original}",
            )
        total = sum(D(pnl[name]) for name in pnl_map if name != "slippage_informativo_usdt")
        net = D(row["final_equity_usdt"]) - D(config["capital"])
        pnl.update(
            precios_usdt=str(D(pnl["spot_usdt"]) + D(pnl["futuros_usdt"])),
            neto_componentes_usdt=str(total),
            beneficio_equity_usdt=str(net),
            residuo_conciliacion_usdt=str(net - total),
            slippage_resta_adicional=False,
        )
        check(
            "Conciliación equity y componentes", net, total, D(config["accounting_tolerance"]), key
        )
        for name, formula in (
            ("precios_usdt", "spot_usdt+futuros_usdt"),
            (
                "neto_componentes_usdt",
                "spot+futuros+funding+comisiones+liquidaciones; excluye slippage informativo",
            ),
            ("beneficio_equity_usdt", "equity_final-capital_inicial"),
            ("residuo_conciliacion_usdt", "beneficio_equity-neto_componentes"),
        ):
            trace(
                "tablas/pnl_componentes.csv",
                key,
                name,
                pnl[name],
                "USDT",
                base + "pnl_components.csv",
                "amount_usdt; equity_daily.equity; config.capital",
                f"strategy={strategy}",
                formula,
            )
        components.append(pnl)
        for field in (
            "capital_deployed_daily_avg_usdt",
            "capital_deployed_daily_max_usdt",
            "covered_asset_seconds",
            "unhedged_asset_seconds",
            "dust_asset_seconds",
        ):
            time = field.endswith("seconds")
            value = str(D(row[field]) / 3600) if time else row[field]
            activity.append(
                dict(
                    ventana=window,
                    estrategia=strategy,
                    run_id=run,
                    simbolo="PORTFOLIO",
                    tipo="exposición",
                    medida=field.replace("seconds", "hours"),
                    valor=value,
                    unidad="horas-activo" if time else "USDT",
                    denominador="",
                    unidad_denominador="",
                    alcance="suma por activo" if time else "cortes diarios persistidos",
                )
            )
            trace(
                "tablas/actividad_y_rechazos.csv",
                key,
                field.replace("seconds", "hours"),
                value,
                "horas-activo" if time else "USDT",
                EVIDENCE + "scenario_summary.csv",
                field,
                selector,
                "segundos/3600" if time else "copia",
            )
        if strategy == "conditional":
            for name, value in config.items():
                parameters.append(
                    dict(
                        ventana=window,
                        run_id=run,
                        parametro=name,
                        valor=json.dumps(value) if isinstance(value, list) else value,
                    )
                )
                trace(
                    "tablas/parametros_vigentes.csv",
                    window,
                    name,
                    value,
                    "según parámetro",
                    base + "run_manifest.json",
                    "config." + name,
                    "corrida principal",
                )
            cost = (
                D("2") * D("0.001")
                + D(2) * D(config["research_futures_taker_fee"])
                + D(4) * D(config["slippage"])
            ) * D(config["cost_multiplier"])
            assumptions = load(base + "research_assumptions.json")
            for rule in assumptions["rules"]:
                check(
                    "Comisión prescrita",
                    rule["values"]["taker_fee"],
                    "0.001" if rule["market"] == "spot" else "0.0005",
                )
            check("Costo del ciclo", cost, "0.0034", context=window)
            parameters.append(
                dict(ventana=window, run_id=run, parametro="costo_ciclo_derivado", valor=str(cost))
            )
            trace(
                "tablas/parametros_vigentes.csv",
                window,
                "costo_ciclo_derivado",
                cost,
                "proporción",
                base + "research_assumptions.json",
                "rules[].values.taker_fee; config.slippage; cost_multiplier",
                "spot y futures",
                "2*fee_spot+2*fee_futures+4*slippage, multiplicado por cost_multiplier",
            )
            funding = load(base + "funding_mark_audit.json")
            unique = {}
            for obs in funding["consumed"]:
                k = obs["symbol"], obs["funding_time"]
                prior = unique.setdefault(k, obs)
                if (prior["settlement_mark_price"], prior["settlement_mark_method"]) != (
                    obs["settlement_mark_price"],
                    obs["settlement_mark_method"],
                ):
                    raise ValueError("Strategies have different funding evidence")
            counts = Counter(
                (r["symbol"], r["economic_window"], r["settlement_mark_method"])
                for r in unique.values()
            )
            for (symbol, economic, method), count in sorted(counts.items()):
                coverage.append(
                    dict(
                        ventana=window,
                        run_id=run,
                        simbolo=symbol,
                        periodo="económico" if economic else "calentamiento",
                        metodo=method,
                        eventos_unicos=count,
                        unidad="eventos de mercado; estrategias deduplicadas",
                    )
                )
                trace(
                    "tablas/cobertura_funding.csv",
                    f"{window}/{symbol}/{economic}/{method}",
                    "eventos_unicos",
                    count,
                    "eventos",
                    base + "funding_mark_audit.json",
                    "consumed[].settlement_mark_method",
                    f"symbol={symbol};economic_window={economic};method={method}",
                    "count unique(symbol,funding_time)",
                )
    denominators = {
        (r["window"], r["symbol"]): r["observations"]
        for r in read("evidencia/basis/basis_audit_summary.csv")
    }
    diagnostics = read(EVIDENCE + "diagnostics_summary.csv")
    for window in RUNS:
        for name in ("filter_funding:reject", "ordered_reject:funding"):
            count = sum(
                int(r["count"])
                for r in diagnostics
                if r["scenario"] == "vwap_joint"
                and r["strategy"] == "permanent"
                and r["window"] == window
                and r["diagnostic"] == name
            )
            check(
                "Permanente sin rechazo operativo de funding", count, 0, context=window + "/" + name
            )
    for r in diagnostics:
        if r["scenario"] != "vwap_joint" or r["symbol"] == "PORTFOLIO":
            continue
        name = r["diagnostic"]
        if (
            r["strategy"] == "permanent"
            and name in ("filter_funding:reject", "ordered_reject:funding")
            and int(r["count"])
        ):
            raise ValueError("The permanent strategy cannot be blocked by funding")
        activity.append(
            dict(
                ventana=r["window"],
                estrategia=r["strategy"],
                run_id=RUNS[r["window"]],
                simbolo=r["symbol"],
                tipo="diagnóstico",
                medida=name,
                valor=r["count"],
                unidad="evaluaciones",
                denominador=denominators[r["window"], r["symbol"]],
                unidad_denominador="evaluaciones de entrada",
                alcance=r["scope"],
            )
        )
        trace(
            "tablas/actividad_y_rechazos.csv",
            f"{r['window']}/{r['strategy']}/{r['symbol']}",
            name,
            r["count"],
            "evaluaciones",
            EVIDENCE + "diagnostics_summary.csv",
            "count",
            ";".join(
                f"{k}={r[k]}" for k in ("scenario", "window", "strategy", "symbol", "diagnostic")
            ),
        )
    for (window, symbol), count in denominators.items():
        trace(
            "tablas/actividad_y_rechazos.csv",
            f"{window}/ambas/{symbol}/diagnóstico",
            "denominador",
            count,
            "evaluaciones por estrategia",
            "evidencia/basis/basis_audit_summary.csv",
            "observations",
            f"window={window};symbol={symbol}",
        )
    for name, rows in (
        ("tablas/resultados_principales.csv", results),
        ("tablas/pnl_componentes.csv", components),
        ("datos/equity_diaria.csv", daily),
        ("tablas/actividad_y_rechazos.csv", activity),
        ("tablas/parametros_vigentes.csv", parameters),
        ("tablas/cobertura_funding.csv", coverage),
    ):
        write(destination, name, rows)
    return summary, results, components, daily


def context_tables(destination, summary, daily):
    hypotheses = [
        r for r in read(EVIDENCE + "hypotheses_by_window.csv") if r["scenario"] == "vwap_joint"
    ]
    write(destination, "tablas/hipotesis.csv", hypotheses)
    for row in hypotheses:
        for field, value in row.items():
            if value and field not in {
                "scenario",
                "strategy",
                "window",
                "period",
                "hypothesis",
                "measure",
                "criterion",
                "result",
            }:
                trace(
                    "tablas/hipotesis.csv",
                    row["window"] + "/" + row["hypothesis"],
                    field,
                    value,
                    "según measure; proporciones sin anualizar salvo CAGR",
                    EVIDENCE + "hypotheses_by_window.csv",
                    field,
                    f"scenario=vwap_joint;window={row['window']};hypothesis={row['hypothesis']}",
                )
        if row["hypothesis"] == "H1":
            source = f"evidencia/corridas/{RUNS[row['window']]}/h1_summary.csv"
            h1 = select(read(source), period="full", symbol="EQUAL_WEIGHT")
            for a, b in (
                ("value", "mae_ewma"),
                ("comparator", "mae_no_change"),
                ("observations", "observations"),
                ("excluded", "excluded"),
            ):
                check("Hipótesis H1: " + a, row[a], h1[b], D("1e-15"), row["window"])
    basis = read("evidencia/basis/basis_audit_summary.csv")
    write(destination, "tablas/basis_audit_summary.csv", basis)
    for row in basis:
        check(
            "Basis cero incluido en elegible",
            row["eligible_inclusive"],
            D(row["zero"]) + D(row["positive_eligible"]),
        )
        for field, value in row.items():
            if field not in {"symbol", "window"}:
                trace(
                    "tablas/basis_audit_summary.csv",
                    row["window"] + "/" + row["symbol"],
                    field,
                    value,
                    "basis decimal"
                    if field in {"minimum", "median", "maximum", "max_absolute_error"}
                    else "conteo",
                    "evidencia/basis/basis_audit_summary.csv",
                    field,
                    f"window={row['window']};symbol={row['symbol']}",
                )
    closes = [
        r
        for r in read(EVIDENCE + "outage_2023-03-24_close_prices.csv")
        if r["scenario"] == "vwap_joint"
    ]
    episode = []
    for row in read(EVIDENCE + "outage_2023-03-24_summary.csv"):
        if row["scenario"] != "vwap_joint":
            continue
        strategy = row["strategy"]
        annual = select(summary, window="early", strategy=strategy)
        profit = D(annual["final_equity_usdt"]) - D(annual["capital_usdt"])
        days = {
            r["fecha_utc"]: D(r["equity_usdt"])
            for r in daily
            if r["ventana"] == "early" and r["estrategia"] == strategy
        }
        day = days["2023-03-24"] - days["2023-03-23"]
        check("PnL diario episodio", day, row["day_pnl_usdt"], D("1e-8"), strategy)
        close_rows = [r for r in closes if r["strategy"] == strategy]
        result = dict(
            ventana="early",
            estrategia=strategy,
            run_id=RUNS["early"],
            fecha_utc="2023-03-24",
            cambio_equity_diario_usdt=row["day_pnl_usdt"],
            funding_usdt=row["funding_usdt"],
            fees_costo_positivo_usdt=row["fees_usdt"],
            beneficio_anual_usdt=str(profit),
            fraccion_beneficio_anual=str(day / profit) if profit > 0 else "",
            motivo_fraccion_no_aplicable="" if profit > 0 else "beneficio anual no positivo",
            minutos_activo_sin_cobertura=str(D(row["unhedged_asset_seconds"]) / 60),
            activos_cerrados=";".join(r["symbol"] for r in close_rows),
            cierres_futuros_utc=";".join(
                r["symbol"] + "=" + r["future_close_utc"] for r in close_rows
            ),
            cierres_spot_utc=";".join(r["symbol"] + "=" + r["spot_close_utc"] for r in close_rows),
            precios_futuros_usdt=";".join(
                r["symbol"] + "=" + r["future_close_price_usdt"] for r in close_rows
            ),
            precios_spot_usdt=";".join(
                r["symbol"] + "=" + r["spot_close_price_usdt"] for r in close_rows
            ),
            ordenes_cierre=row["close_orders"],
            fills=row["fills"],
        )
        episode.append(result)
        episode_fields = {
            "cambio_equity_diario_usdt": ("day_pnl_usdt", "USDT"),
            "funding_usdt": ("funding_usdt", "USDT"),
            "fees_costo_positivo_usdt": ("fees_usdt", "USDT; costo positivo"),
            "minutos_activo_sin_cobertura": ("unhedged_asset_seconds", "minutos-activo"),
            "ordenes_cierre": ("close_orders", "órdenes"),
            "fills": ("fills", "fills"),
        }
        selection = f"scenario=vwap_joint;strategy={strategy}"
        for field, (source_field, unit) in episode_fields.items():
            trace(
                "tablas/episodio_2023_03_24.csv",
                "early/" + strategy,
                field,
                result[field],
                unit,
                EVIDENCE + "outage_2023-03-24_summary.csv",
                source_field,
                selection,
                "segundos/60" if field == "minutos_activo_sin_cobertura" else "copia",
            )
        for field, source_field in (
            ("cierres_futuros_utc", "future_close_utc"),
            ("cierres_spot_utc", "spot_close_utc"),
            ("precios_futuros_usdt", "future_close_price_usdt"),
            ("precios_spot_usdt", "spot_close_price_usdt"),
        ):
            trace(
                "tablas/episodio_2023_03_24.csv",
                "early/" + strategy,
                field,
                result[field],
                "UTC" if field.endswith("utc") else "USDT/unidad del activo",
                EVIDENCE + "outage_2023-03-24_close_prices.csv",
                source_field,
                selection,
                "pares symbol=valor; una fila fuente por símbolo",
            )
        for field, formula in (
            ("beneficio_anual_usdt", "final_equity_usdt-capital_usdt"),
            (
                "fraccion_beneficio_anual",
                "outage.day_pnl_usdt/(final_equity_usdt-capital_usdt); Decimal 60",
            ),
        ):
            trace(
                "tablas/episodio_2023_03_24.csv",
                "early/" + strategy,
                field,
                result[field],
                "USDT" if field == "beneficio_anual_usdt" else "proporción",
                EVIDENCE + "scenario_summary.csv;" + EVIDENCE + "outage_2023-03-24_summary.csv",
                "final_equity_usdt;capital_usdt;day_pnl_usdt",
                selection + ";window=early",
                formula,
            )
    write(destination, "tablas/episodio_2023_03_24.csv", episode)
    variants = read(EVIDENCE + "scenario_summary.csv")
    write(destination, "tablas/anexo_variantes_ejecucion.csv", variants)
    for row in variants:
        for field, value in row.items():
            if field in {"window", "strategy", "scenario", "run_id", "status", "start", "end"}:
                continue
            trace(
                "tablas/anexo_variantes_ejecucion.csv",
                "/".join(row[k] for k in ("window", "strategy", "scenario")),
                field,
                value,
                "según diccionario",
                EVIDENCE + "scenario_summary.csv",
                field,
                ";".join(f"{k}={row[k]}" for k in ("scenario", "window", "strategy")),
                "copia",
            )
            TRACES[-1]["run_id"] = row["run_id"]
    return episode


def documentation_tables(destination):
    """Expose effective versions and the provenance of narrative aggregates."""
    versions = []
    for window, run in RUNS.items():
        source = f"evidencia/corridas/{run}/run_manifest.json"
        manifest = load(source)
        for name, value in {"python": manifest["python"], **manifest["dependencies"]}.items():
            versions.append(dict(ventana=window, run_id=run, herramienta=name, version=value))
            trace(
                "tablas/versiones.csv; base_para_redaccion.md",
                window,
                name,
                value,
                "versión",
                source,
                "python" if name == "python" else "dependencies." + name,
                "corrida principal",
            )
    write(destination, "tablas/versiones.csv", versions)
    for window in RUNS:
        basis = [
            r for r in read("evidencia/basis/basis_audit_summary.csv") if r["window"] == window
        ]
        trace(
            "base_para_redaccion.md",
            window,
            "observaciones_basis",
            sum(int(r["observations"]) for r in basis),
            "observaciones de mercado",
            "evidencia/basis/basis_audit_summary.csv",
            "observations",
            "window=" + window,
            "suma por símbolo; total de ventanas=4380; decisiones=2*4380",
        )
    trace(
        "base_para_redaccion.md",
        "metodología",
        "precarga_horas",
        360,
        "horas",
        "evidencia/codigo/execution_revision.py",
        "_run_scenario: timedelta(hours=config.window_hours + 24)",
        "vwap_joint",
        "336+24; más antecedente de intervalo; no altera la ventana EWMA",
    )
    # Presentation values retain a direct chain to every underlying table and formula.
    for item in list(TRACES):
        if item["archivo_presentado"] in {
            "tablas/resultados_principales.csv",
            "tablas/pnl_componentes.csv",
            "tablas/hipotesis.csv",
            "tablas/episodio_2023_03_24.csv",
            "tablas/cobertura_funding.csv",
            "tablas/parametros_vigentes.csv",
        }:
            trace(
                "base_para_redaccion.md; figuras/notas_figuras.md",
                item["seleccion_presentada"],
                item["campo_presentado"],
                item["valor_original"],
                item["unidad"],
                item["archivo_fuente"],
                item["campo_fuente"],
                item["filtro_fuente"],
                item["calculo"]
                + "; presentación: redondear; porcentaje=decimal*100; bps=decimal*10000; cobertura total=suma de activos",
            )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destino", type=Path, default=PACKAGE)
    args = parser.parse_args()
    for item in load("fuentes_originales.json")["files"]:
        path = PACKAGE / item["archivo"]
        with path.open("rb") as stream:
            if hashlib.file_digest(stream, "sha256").hexdigest() != item["sha256"]:
                raise ValueError(f"Modified evidence: {path}")
    with localcontext() as context:
        context.prec = 60
        summary, results, components, daily = core_tables(args.destino)
        episode = context_tables(args.destino, summary, daily)
        documentation_tables(args.destino)
    write(args.destino, "fuentes_de_cifras.csv", TRACES)
    write(args.destino, "verificaciones_numericas.csv", CHECKS)
    figures(args.destino, results, components, daily)
    print(
        json.dumps(
            dict(
                carteras=len(results),
                filas_diarias=len(daily),
                comprobaciones=len(CHECKS),
                cifras_trazadas=len(TRACES),
                fracciones_episodio=[r["fraccion_beneficio_anual"] for r in episode],
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
