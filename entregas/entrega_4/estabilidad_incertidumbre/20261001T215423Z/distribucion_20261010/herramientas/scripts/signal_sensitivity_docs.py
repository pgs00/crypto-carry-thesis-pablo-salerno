"""Technical report and standalone figures for the closed signal sensitivity block."""

from __future__ import annotations

from collections import Counter
from decimal import Decimal as D

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

if __package__:
    from .report_historical_rules_sensitivity import write_csv
    from .return_capital.report import render_html
else:
    from report_historical_rules_sensitivity import write_csv
    from return_capital.report import render_html


def fmt(value, percent=False, digits=4):
    if value in (None, ""):
        return "ND"
    number = D(str(value))
    return f"{number*(100 if percent else 1):.{digits}f}"+("%" if percent else "")


def table(headers, rows):
    return "| "+" | ".join(headers)+" |\n|"+"|".join("---" for _ in headers)+"|\n"+"\n".join(
        "| "+" | ".join(str(v) for v in row)+" |" for row in rows)+"\n"


def conclusion_lines(tables):
    """Interpret the checked results without selecting a parameter or merging populations."""
    full = {(r["scenario"], r["strategy"]): r for r in tables["metricas"] if r["period"] == "full"}
    h1 = {r["scenario"]: r for r in tables["h1_resumen"]
          if r["period"] == "full" and r["symbol"] == "EQUAL_WEIGHT"}
    h2 = {(r["scenario"], r["period"]): r["verdict"] for r in tables["h2"]}
    h3 = {r["scenario"]: r for r in tables["h3_resumen"] if r["period"] == "full"}
    invariants = {(r["scenario"], r["strategy"]): r for r in tables["invariancias"]}
    variants = ("H072", "H336", "V012", "V048", "B025", "B100")
    same_h2 = [s for s in variants if h2[s, "full"] == h2["BASE_E3", "full"]]
    changed_h2 = [s for s in variants if s not in same_h2]
    same_h3 = [s for s in variants if h3[s]["h3_descriptive"] == h3["BASE_E3"]["h3_descriptive"]]
    changed_h3 = [s for s in variants if s not in same_h3]
    period_changes = [f"{s}/{p}: {verdict}" for (s, p), verdict in h2.items()
                      if s != "BASE_E3" and p != "full" and verdict != h2["BASE_E3", p]]
    lines = [
        f"H2 completo conserva el resultado BASE ({h2['BASE_E3','full']}) en "
        + (", ".join(same_h2) or "ninguna variante") + "; cambia en "
        + (", ".join(changed_h2) or "ninguna") + ". H3 conserva el veredicto BASE ("
        + h3["BASE_E3"]["h3_descriptive"] + ") en " + (", ".join(same_h3) or "ninguna variante")
        + "; cambia en " + (", ".join(changed_h3) or "ninguna") + ".\n",
        "En años y cortes, los cambios de veredicto H2 frente al mismo período BASE son: "
        + ("; ".join(period_changes) or "ninguno") + ". El agregado no sustituye este desglose.\n",
    ]
    horizon = []
    for scenario in ("H072", "BASE_E3", "H336"):
        row = full[scenario, "conditional"]
        horizon.append(f"{scenario}: P&L {fmt(row['net_pnl_usdt'], digits=2)} USDT, "
                       f"actividad {fmt(row['invested_fraction'], True)}, "
                       f"uso medio diario {fmt(row['capital_utilization_daily_mean'], True)}")
    lines.append("La sensibilidad al horizonte combina predicción y tenencia. En la condicional, "
                 + "; ".join(horizon) + ". Estos cambios se leen conjuntamente con el capital utilizado; "
                 "los MAE de 72/168/336 h evalúan objetivos distintos y no ordenan la calidad de un único target.\n")
    for scenario in ("V012", "V048"):
        row = full[scenario, "conditional"]
        lines.append(f"{scenario}, con target común de 168 h: MAE EWMA "
            f"{fmt(h1[scenario]['mae_ewma_bps'], digits=6)} frente a "
            f"{fmt(h1['BASE_E3']['mae_ewma_bps'], digits=6)} pb/168 h de BASE; "
            f"P&L condicional {fmt(row['net_pnl_usdt'], digits=2)} USDT, "
            f"actividad {fmt(row['invested_fraction'], True)} y uso medio diario "
            f"{fmt(row['capital_utilization_daily_mean'], True)}. Economía permanente igual a BASE="
            f"{invariants[scenario,'permanent']['economic_invariant']}. "
            "La relación entre error, actividad y resultado no establece causalidad ni un parámetro óptimo.\n")
    for scenario in ("B025", "B100"):
        values = (h3[scenario]["opportunity_mean_bps"], h3["BASE_E3"]["opportunity_mean_bps"])
        change = None if any(v in (None, "") for v in values) else D(str(values[0]))-D(str(values[1]))
        lines.append(f"{scenario}: economía igual a BASE en condicional="
            f"{invariants[scenario,'conditional']['economic_invariant']} y permanente="
            f"{invariants[scenario,'permanent']['economic_invariant']}; "
            f"H3 diario igual={invariants[scenario,'conditional']['h3_daily_equal_base']}, "
            f"delta de oportunidad media completa {fmt(change, digits=6)} pb/168 h. "
            "La igualdad de operaciones no se extiende automáticamente a los minutos de mercado de H3.\n")
    return lines


def report_markdown(tables, index):
    metrics = tables["metricas"]
    period_metrics = {(r["scenario"], r["strategy"], r["period"]): r for r in metrics}
    full = {(r["scenario"], r["strategy"]): r for r in metrics if r["period"] == "full"}
    h1 = {r["scenario"]: r for r in tables["h1_resumen"]
          if r["period"] == "full" and r["symbol"] == "EQUAL_WEIGHT"}
    h2 = {(r["scenario"], r["period"]): r for r in tables["h2"]}
    h3 = {(r["scenario"], r["period"]): r for r in tables["h3_resumen"]}
    invariants = {(r["scenario"], r["strategy"]): r for r in tables["invariancias"]}
    scenarios = ("BASE_E3", "H072", "H336", "V012", "V048", "B025", "B100")
    verdicts = Counter(h2[s, "full"]["verdict"] for s in scenarios[1:])
    lines = [
        "# Bloque 2: señal y selección de entradas\n",
        "Entrega 4 técnica preliminar. Sensibilidad exploratoria de historia ya observada: "
        "doce carteras nuevas, seis variantes sin cruces y dos referencias BASE reutilizadas con sus run_id. "
        "El feedback de E3 ya fue recibido. Este bloque no reemplaza las hipótesis/cifras de E3 ni completa toda E4.\n",
        "## Síntesis\n",
        "Muestra UTC [2022-01-01,2026-09-01), 10.000 USDT por cartera, BTCUSDT y ETHUSDT, "
        "sin reinicios. Se conservan window=336 h, precarga=360 h, disponibilidad de funding=60 s, "
        "costo de ciclo=34 pb, ejecución next_minute_vwap/joint_quantity y participación 1%. "
        "No hubo cambios del código económico en este bloque.\n",
        f"En la muestra completa, H2 de las seis variantes: {dict(verdicts)}. "
        "H2 requiere CAGR condicional positivo y Sharpe superior a la permanente del mismo escenario; "
        "no exige un CAGR superior a ella ni un Sharpe positivo. ND conserva su motivo.\n",
        table(["Escenario", "Cartera", "Equity final USDT", "P&L USDT", "Retorno", "CAGR365", "Sharpe RF0", "Activo sin polvo", "Capital medio USDT", "Uso medio diario"],
              [[s, strategy, fmt(full[s, strategy]["final_equity_usdt"], digits=2),
                fmt(full[s, strategy]["net_pnl_usdt"], digits=2), fmt(full[s, strategy]["net_return"], True),
                fmt(full[s, strategy]["cagr"], True), fmt(full[s, strategy]["sharpe"]),
                fmt(full[s, strategy]["invested_fraction"], True),
                fmt(full[s, strategy]["capital_deployed_usdt_daily_mean"], digits=2),
                fmt(full[s, strategy]["capital_utilization_daily_mean"], True)]
               for s in scenarios for strategy in ("conditional", "permanent")]),
        "Las medias/máximos de capital y garantías se miden en cierres diarios. Tiempo activo "
        "es la unión temporal BTC/ETH después de clasificar la trayectoria completa y excluir polvo "
        "de la actividad; el polvo conserva su valor/riesgo en equity. No se divide CAGR por utilización.\n",
    ]
    for title, pairs, explanation, figure in (
        ("Horizonte y tenencia", ("H072", "H336"),
         "Cambia conjuntamente horizonte del forecast, objetivo realizado de H1 y reloj de tenencia/renovación. "
         "El costo sigue siendo 34 pb por ciclo y la renovación condicional exige sólo forecast >0. "
         "Es una dimensión económica compuesta. El final financiero permanece fijo; las exclusiones H1 "
         "no provocan cierres ficticios ni recortan entradas cerca del final.", "horizonte"),
        ("Vida media EWMA", ("V012", "V048"),
         "Cambia sólo el peso de observaciones dentro de la ventana de 336 h. Horizonte/tenencia=168 h; "
         "targets y no-change se comparan por igualdad de inputs. La permanente omite los filtros de funding "
         "para entrar y renovar; la igualdad de su economía se comprueba sobre trayectorias y operaciones.", "vida_media"),
        ("Techo del basis de entrada", ("B025", "B100"),
         "Se conserva el piso cero y los extremos inclusivos; los techos son 0,0025 y 0,01. "
         "No cambia el stop de ampliación ni se impone basis de entrada a renovaciones. "
         "Decisiones de entrada, economía y todos los minutos H3 son poblaciones distintas.", "basis"),
    ):
        lines += [f"## {title}\n", explanation+"\n"]
        for s in pairs:
            c, p = full[s, "conditional"], full[s, "permanent"]
            base_c, base_p = full["BASE_E3", "conditional"], full["BASE_E3", "permanent"]
            lines.append(
                f"**{s}**: P&L condicional {fmt(c['net_pnl_usdt'], digits=2)} USDT "
                f"(delta BASE {fmt(D(str(c['net_pnl_usdt']))-D(str(base_c['net_pnl_usdt'])), digits=2)}); "
                f"permanente {fmt(p['net_pnl_usdt'], digits=2)} "
                f"(delta {fmt(D(str(p['net_pnl_usdt']))-D(str(base_p['net_pnl_usdt'])), digits=2)}). "
                f"Actividad condicional {fmt(c['invested_fraction'], True)}, "
                f"capital medio {fmt(c['capital_deployed_usdt_daily_mean'], digits=2)} USDT. "
                f"H2 completo: {h2[s,'full']['verdict']}. "
                f"Economía idéntica a BASE: condicional={invariants[s,'conditional']['economic_invariant']}, "
                f"permanente={invariants[s,'permanent']['economic_invariant']}.\n")
            early, later = (period_metrics[s, "conditional", p] for p in ("2022-2023", "2024+"))
            years = [period_metrics[s, "conditional", str(y)] for y in range(2022, 2027)]
            lines.append(
                f"En la condicional, CAGR 2022–2023 / 2024–agosto 2026: "
                f"{fmt(early['cagr'], True)} / {fmt(later['cagr'], True)}; "
                f"uso medio diario del capital: {fmt(early['capital_utilization_daily_mean'], True)} / "
                f"{fmt(later['capital_utilization_daily_mean'], True)}. "
                f"P&L anual 2022, 2023, 2024, 2025 y enero–agosto 2026 (USDT): "
                +", ".join(fmt(r["net_pnl_usdt"], digits=2) for r in years)+". "
                f"Targets H1 iguales a BASE={invariants[s,'conditional']['h1_targets_equal_base']}; "
                f"no-change igual={invariants[s,'conditional']['h1_no_change_equal_base']}; "
                f"H3 diario igual={invariants[s,'conditional']['h3_daily_equal_base']}.\n")
        lines.append(f"![Curvas de patrimonio: {title}](figuras/{figure}.png)\n")
    lines += [
        "## H1: capacidad predictiva\n",
        "Todos los pronósticos elegibles, independientemente de entrada/posición/caja. "
        "EWMA y no-change usan las mismas observaciones dentro de cada escenario; MAE por activo y "
        "promedio 50/50. El target suma funding real en (señal,señal+H], con calendario acreditado "
        "y fin global exclusivo. Se conservan inválidos y motivos. La habilidad 1−MAE_EWMA/MAE_no_change "
        "es descriptiva, con denominador positivo, y no es rentabilidad. "
        "Un MAE menor con 72 h no demuestra mejor modelo que con 168/336 h.\n",
        "Los períodos H1 se asignan por fecha de la señal. Un target puede cruzar enero o el corte "
        "de 2024; esa realización futura sirve para evaluar, no para decidir ni entrenar antes de tiempo.\n",
        table(["Escenario", "Unidad", "Válidas", "Excluidas", "MAE EWMA", "MAE no-change", "Habilidad"],
              [[s, h1[s]["unit"], h1[s]["observations"], h1[s]["excluded"],
                fmt(h1[s]["mae_ewma_bps"], digits=6), fmt(h1[s]["mae_no_change_bps"], digits=6),
                fmt(h1[s]["skill_vs_no_change"])] for s in scenarios]),
        "H1 se calculó desde funding consumido y señales guardadas para cada configuración. "
        "Ambas estrategias se contrastaron por igualdad de inputs; se publica una población común "
        "por escenario, sin duplicarla como observaciones independientes. "
        "Los horizontes solapados tampoco son observaciones independientes.\n",
        "## H2 y H3\n",
        table(["Escenario", "H2 full", "Motivo H2", "H3", "Oportunidad 2022–23", "Oportunidad 2024–ago26", "Unidad"],
              [[s, h2[s,"full"]["verdict"], h2[s,"full"]["reason"], h3[s,"full"]["h3_descriptive"],
                fmt(h3[s,"2022-2023"]["opportunity_mean_bps"], digits=6),
                fmt(h3[s,"2024+"]["opportunity_mean_bps"], digits=6), h3[s,"full"]["unit"]]
               for s in scenarios]),
        "H3 usa todos los minutos, independientemente de posiciones. Forecast completo si pasa costo, "
        "basis y operatividad; cero para fallas conocidas, desconocido no es cero. Se promedian "
        "1.440 minutos por activo/día y después BTC/ETH 50/50. Se mantiene la publicación real, "
        "incluidos milisegundos, y la interrupción documentada. H3 es favorable sólo si bajan "
        "oportunidad media y CAGR condicional entre los cortes; contraria si ambos suben; mixta "
        "en los demás casos evaluables. Los resultados H072/H336 son sensibilidades en su propia "
        "unidad, no nuevos valores de H3 original de 168 h. No se resta el costo al indicador.\n",
        "En la tabla H3, el veredicto compara siempre 2022–2023 con 2024–agosto 2026; los años "
        "son desgloses del indicador y del CAGR, no hipótesis temporales nuevas.\n",
        "## Años, saldos heredados y capital\n",
        "El tramo 2026 incluye enero–agosto. CAGR se anualiza con 365 días, mientras retorno y P&L "
        "corresponden al tramo observado. No se suman retornos anuales. Las tablas completas también "
        "incluyen volatilidad, drawdown diario, ND/motivos, componentes P&L y ambos cortes H3.\n",
        table(["Escenario", "Cartera", "Año", "Inicio USDT", "P&L USDT", "Retorno", "CAGR", "Sharpe", "Uso medio diario", "Activo"],
              [[r["scenario"], r["strategy"], r["period"], fmt(r["starting_equity_usdt"], digits=2),
                fmt(r["net_pnl_usdt"], digits=2), fmt(r["net_return"], True), fmt(r["cagr"], True),
                fmt(r["sharpe"]), fmt(r["capital_utilization_daily_mean"], True), fmt(r["invested_fraction"], True)]
               for r in metrics if r["period"] in {"2022", "2023", "2024", "2025", "2026"}]),
        "![CAGR y capital por año](figuras/anual_capital.png)\n",
        "## Entradas, ciclos, exposición y conciliación\n",
        "Se conservan evaluaciones excluyentes funding/basis, no evaluables, primer bloqueo, "
        "motivos simultáneos y acciones enlazadas. Un fallo de funding en la permanente es descriptivo "
        "y no un rechazo aplicado. Las renovaciones tienen su tabla y su condición de funding cero. "
        "Intentos de órdenes no son ciclos; renovar no crea un ciclo. Las tablas distinguen aperturas "
        "completas, parciales, fallas, ciclos heredados/abiertos y motivos de cierre.\n",
        table(["Escenario", "Cartera", "Intentos de ciclo", "Aperturas completas", "Renovaciones", "Fills parciales", "Ciclos fallidos", "Minutos sin cobertura (unión)"],
              [[r["scenario"], r["strategy"], r["opening_attempts"], r["completed_openings"], r["renewals"],
                r["partial_fills"], r["failed_cycles"], fmt(full[r["scenario"],r["strategy"]]["unhedged_seconds"]/60, digits=2)]
               for r in tables["actividad"] if r["period"] == "full" and r["symbol"] == "PORTFOLIO"]),
        "Cada cierre y cada período se concilian con patrimonio y componentes a 1E-8 USDT. "
        "Transferencias/colateral no son P&L; slippage ya integra precios y no se resta dos veces. "
        "Las posiciones abiertas al final se valúan sin venta ni fee ficticio. El polvo no se descuenta "
        "de equity. Los eventos de margen/liquidación/deuda disponibles están en eventos, ledger y "
        "margen_cierre_diario; los extremos de esta última tabla son exclusivamente de cierres diarios.\n",
        "## Lectura y límites\n",
        *conclusion_lines(tables),
        "Las diferencias describen simultáneamente predicción, actividad, capital y resultado. "
        "No se atribuye causalmente toda variación de P&L a un contador de entradas. Una invariancia "
        "comprobada es un resultado y no motiva cambiar el experimento. Seis sensibilidades no "
        "establecen robustez universal, significancia ni un parámetro óptimo. Los años complementan "
        "el agregado y permiten observar cambios que éste oculta.\n",
        "La tabla de [deltas de hipótesis](tablas/deltas_hipotesis.csv) compara vidas medias y basis "
        "con BASE. En H072/H336 no calcula diferencias de MAE ni tasa de oportunidad entre "
        "horizontes distintos. Mantiene valores, unidad/horizonte y el motivo de no comparabilidad. "
        "La habilidad contra no-change sólo describe cada target; no selecciona un horizonte ganador.\n",
        "Se mantienen las tarifas/reglas prescritas, 15 marks futures_scaled y tratamiento original "
        "de precios de funding. No se certifica una reconstrucción histórica completa de reglas ni "
        "liquidez ejecutable real. Los drawdowns nuevos son diarios. No se recalcularon concentración, "
        "riesgo intradía, SOFR ni remuneración de caja/garantía. SOFR no sustituye RF=0 ni la permanente "
        "en H2. La ficha SOFR pendiente conservada en un paquete antiguo es histórica: la versión "
        "posterior aprobada se conserva sólo como contexto terminado.\n",
        "## Evidencia y reproducción\n",
        "[Índice de corridas](indice_corridas.json), [métricas de los ocho períodos](tablas/metricas.csv), "
        "[deltas sin redondear](tablas/deltas.csv), [invariancias](tablas/invariancias.csv), "
        "[H2 completo](tablas/h2.csv), [H3 por período](tablas/h3_resumen.csv), "
        "[fuentes exactas](fuentes/archivos_originales.csv) y [matriz de requisitos](matriz_requisitos.csv). "
        "Las observaciones H1, agregados H3 por activo, grupos de disponibilidad y muestra fija "
        "de minutos están en hipotesis/<escenario>/. Las fuentes de figuras están en figuras/fuentes/.\n",
        "Verificación y alcance: [README](README.md). El verificador recalcula desde evidencia persistida; "
        "con --data-root contrasta H3 contra los minutos locales. Constructor y verificador comparten "
        "algunos helpers: no se afirma independencia total ni se ejecuta un nuevo replay al verificar. "
        "No hubo commit, push ni modificación del índice del usuario.\n",
        "El [control histórico de limpieza del repositorio](documentos/control_historico_general.json) "
        "no pasó: espera un hash anterior de src/crypto_carry/config.py. El archivo actual coincide "
        "con el registrado antes de este bloque; no se modificó ese manifiesto para forzar su pase. "
        "Los controles de este bloque tienen alcance propio y no certifican todo el motor ni "
        "todas las versiones históricas del repositorio.\n",
    ]
    return "\n".join(lines)


def draw_figures(package, tables):
    import pandas as pd

    output = package/"figuras"
    output.mkdir(exist_ok=True)
    (output/"fuentes").mkdir(exist_ok=True)
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
    for name, scenarios in (("horizonte", ("BASE_E3", "H072", "H336")),
                             ("vida_media", ("BASE_E3", "V012", "V048")),
                             ("basis", ("BASE_E3", "B025", "B100"))):
        data = [{k: r[k] for k in ("scenario", "strategy", "run_id", "date", "equity_usdt")}
                for r in tables["diario"] if r["scenario"] in scenarios]
        write_csv(output/"fuentes"/f"{name}.csv", data)
        fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), sharex=True)
        for ax, strategy in zip(axes, ("conditional", "permanent")):
            for s, color, style in zip(scenarios, ("#4d5966", "#147d92", "#bd642d"), ("-", "--", ":")):
                rows = [r for r in data if r["scenario"] == s and r["strategy"] == strategy]
                ax.plot(pd.to_datetime([r["date"] for r in rows]), [float(r["equity_usdt"]) for r in rows],
                        label=s, color=color, linestyle=style, linewidth=1.7)
            ax.set_title("Condicional" if strategy == "conditional" else "Permanente")
            ax.set_ylabel("Patrimonio al cierre (USDT)")
            ax.grid(alpha=.2)
            ax.legend(frameon=False)
        fig.autofmt_xdate()
        fig.tight_layout()
        for extension in ("png", "svg"):
            fig.savefig(output/f"{name}.{extension}", dpi=160)
        plt.close(fig)
    data = [{k: r[k] for k in ("scenario", "strategy", "period", "cagr", "capital_utilization_daily_mean")}
            for r in tables["metricas"] if r["period"].isdigit()]
    write_csv(output/"fuentes/anual_capital.csv", data)
    fig, axes = plt.subplots(2, 2, figsize=(13, 8), sharex=True)
    colors = ("#4d5966", "#147d92", "#bd642d", "#437345", "#914d84", "#456dc1", "#b1852d")
    for col, strategy in enumerate(("conditional", "permanent")):
        for scenario, color in zip(("BASE_E3", "H072", "H336", "V012", "V048", "B025", "B100"), colors):
            rows = sorted((r for r in data if r["scenario"] == scenario and r["strategy"] == strategy), key=lambda r:r["period"])
            for i, field in enumerate(("cagr", "capital_utilization_daily_mean")):
                axes[i,col].plot([r["period"] for r in rows], [float(r[field])*100 if r[field] is not None else float("nan") for r in rows],
                                 label=scenario, color=color, marker="o", linewidth=1.2)
        axes[0,col].set_title("Condicional" if strategy == "conditional" else "Permanente")
        axes[0,col].set_ylabel("CAGR365 (%)")
        axes[1,col].set_ylabel("Capital utilizado / equity\nmedia de cierres diarios (%)")
        axes[1,col].set_xlabel("Año; 2026: enero–agosto")
    for ax in axes.flat:
        ax.grid(alpha=.2)
    axes[0,1].legend(ncol=2, frameon=False, fontsize=8)
    fig.tight_layout()
    for extension in ("png", "svg"):
        fig.savefig(output/f"anual_capital.{extension}", dpi=160)
    plt.close(fig)


def write_docs(package, tables, index):
    text = report_markdown(tables, index)
    (package/"reporte.md").write_text(text, encoding="utf-8")
    (package/"reporte.html").write_text(render_html(text).replace(
        "<title>Retorno y capital · BASE_E3</title>", "<title>Bloque 2 · Señal y entradas</title>"), encoding="utf-8")
    draw_figures(package, tables)
    write_matrix(package)
    (package/"README.md").write_text(
        "# Bloque 2: evidencia de señal y entradas\n\n"
        "Abrir [reporte.html](reporte.html) o [reporte.md](reporte.md). Doce nuevas simulaciones "
        "y dos BASE reutilizadas. Sin cambios del motor, referencias ni índice Git.\n\n"
        "## Verificación portable offline\n\n"
        "Con Python 3.14 y dependencias del lock incluido, ejecutar desde cualquier directorio:\n\n"
        "```powershell\npython -B -X utf8 <paquete>/herramientas/scripts/verify_signal_sensitivity.py --package <paquete> --output <auditoria_nueva.json>\n"
        "python -B -X utf8 <paquete>/herramientas/scripts/verify_signal_sensitivity.py --package <paquete> --data-root <datos_locales> --output <auditoria_completa_nueva.json>\n```\n\n"
        "La salida es opcional, nueva y externa al paquete/datos. No se usa Git, HEAD, índice, red "
        "ni sesiones previas. El código incluido se carga antes que cualquier instalación editable. "
        "El modo compacto verifica sellos, configuración cerrada, fuentes incluidas, contabilidad "
        "diaria/período, exposición/ciclos/decisiones, H1 desde tasas/señales, H2 y H3 desde grupos "
        "con conteos/sumas, y datos de figuras. Con --data-root autentica inputs y reconstruye H3 "
        "desde velas locales. Los ficheros masivos no están duplicados en el paquete.\n\n"
        "Las fuentes exactas incluidas se autentican contra los manifiestos originales; archivos "
        "de esos manifiestos que no se incluyen no se presentan como recalculados. Imágenes sólo "
        "se autentican por hash; sus tablas se verifican numéricamente. Hay lógica compartida con "
        "el constructor; H2 tiene además el validador independiente corregido. No es verificación "
        "independiente de todo el motor ni un replay económico.\n\n"
        "Si un período heredara patrimonio no positivo, las métricas no definidas conservan ND "
        "y su motivo. `tablas/semantica_metricas.csv` documenta diferencias con los valores "
        "archivados del writer original, que permanecen intactos.\n\n"
        "## Identidad y alcance\n\n"
        "`evidencia/<run_id>` contiene un subconjunto exacto de las salidas originales. "
        "`fuentes/archivos_originales.csv` identifica cada transferencia binaria. "
        "`documentos/input_hashes.json` enlaza fuentes locales; `dependencias.json` enlaza "
        "los cinco paquetes anteriores sin duplicarlos. `herramientas` congela código económico "
        "y posprocesamiento; `codigo_referencia` conserva el código original de BASE. "
        "Las tasas consumidas de H1 están incluidas; los minutos H3 completos requieren datos locales.\n\n"
        "`tablas/decisiones.parquet` conserva todas las celdas como texto exacto y usa compresión "
        "sin pérdida, para evitar un CSV repetitivo de más de 100 MiB. Puede leerse con "
        "`pyarrow.parquet.read_table`; no redondea decimales ni timestamps. Las métricas, grupos "
        "y demás tablas de lectura directa permanecen en CSV UTF-8. Los logs originales "
        "conservan sus bytes y, cuando corresponde, su BOM UTF-16.\n\n"
        "Los comandos realmente ejecutados, tiempos, códigos de salida y registros de avance "
        "están en `ejecucion/etapa_H.json`, `etapa_V.json`, `etapa_B.json` y sus logs. "
        "El control de cada etapa autentica el protocolo congelado antes de continuar. "
        "La prueba global histórica de limpieza tiene una incompatibilidad de hash preexistente "
        "documentada en `documentos/control_historico_general.json`; no invalida por sí sola "
        "las fuentes de BASE ni acredita una validación integral del motor actual.\n\n"
        "Los controles del candidato previos al sello se incluyen en `pruebas/`, con sus "
        "alcances y resultados reales. Las auditorías finales del paquete sellado, preservación "
        "y exportación binaria se guardan fuera del sello, en la carpeta de trabajo que lo contiene. No hay "
        "publicación Git realizada. No se generó PDF final.\n", encoding="utf-8")


def write_matrix(package):
    """Verification rows remain partial until the actual pre-seal audit is attached."""
    import json

    proof = package/"pruebas/validaciones_pre_sello.json"
    validated = proof.is_file() and json.loads(proof.read_text(encoding="utf-8")).get("passed") is True
    specifications = [
        ("R01", "Referencia y paquetes previos autenticados", "documentos/autenticacion_referencias.json;documentos/verificacion_base_previa.json", False),
        ("R02", "Dos BASE reutilizadas con sus run_id, configuración y fuentes originales", "indice_corridas.json;fuentes/archivos_originales.csv", False),
        ("R03", "Seis variantes sin cruces, doce carteras continuas, diffs económicos exactos", "documentos/registro_escenarios_previo.json;registro_escenarios_final.csv", False),
        ("R04", "Horizonte, objetivo H1 y holding coherentes; ciclo fijo 34 pb", "documentos/configuraciones/H072.toml;documentos/configuraciones/H336.toml;herramientas/tests/integration/test_signal_sensitivity_contracts.py", False),
        ("R05", "Vida media aislada, ventana y target fijos; invariancia no forzada", "documentos/configuraciones/V012.toml;documentos/configuraciones/V048.toml;tablas/invariancias.csv", False),
        ("R06", "Techo basis inclusivo, piso y stop originales; renovación separada", "documentos/configuraciones/B025.toml;documentos/configuraciones/B100.toml;tablas/grupos_entradas.csv", False),
        ("R07", "H1 causal por observación y ocho períodos, exclusiones y unidades", "fuentes/funding_procedencia.json;hipotesis/H072/h1_observaciones.csv;tablas/h1_resumen.csv", False),
        ("R08", "H2 corregida CAGR condicional >0 y Sharpe superior, ND con motivo", "tablas/h2.csv;herramientas/scripts/rules_sensitivity_h2.py", False),
        ("R09", "H3 de mercado por minuto, calendario real, cero conocido y ND separados", "hipotesis/H072/h3_activos_diarios.csv;hipotesis/H072/h3_grupos_forecast.csv;tablas/h3_resumen.csv", False),
        ("R10", "Exposición completa antes del recorte, polvo y unión BTC/ETH", "tablas/exposicion_intervalos.csv;tablas/exposicion_periodo.csv;herramientas/scripts/rules_sensitivity_exposure.py", False),
        ("R11", "Años, cortes y total sin reinicios; saldos y capital utilizado", "tablas/metricas.csv;tablas/diario.csv;figuras/anual_capital.png", False),
        ("R12", "Entradas, motivos simultáneos, ciclos, parciales, fallas, cierres y renovaciones", "tablas/decisiones.parquet;tablas/actividad.csv;tablas/motivos_cierre.csv;tablas/diagnostico_vs_decision.csv", False),
        ("R13", "Componentes diarios y por período, conciliación 1E-8 y ND", "tablas/componentes_diarios.csv;tablas/componentes_periodo.csv;tablas/semantica_metricas.csv", False),
        ("R14", "Código económico y runner predeclarados; controles de compatibilidad", "documentos/protocolo_previo.json;documentos/control_compatibilidad.json;herramientas/scripts/signal_sensitivity_integrity.py", False),
        ("R15", "Pruebas pequeñas, regresión, Ruff y registro de fallos/correcciones reales", "pruebas/validaciones_pre_sello.json", True),
        ("R16", "Corrupciones semánticas rechazadas aun renovando hashes", "pruebas/validaciones_pre_sello.json;herramientas/tests/unit/test_signal_sensitivity_package.py", True),
        ("R17", "Copia limpia offline y H3 con datos locales explícitos, verificación sin escrituras", "pruebas/validaciones_pre_sello.json;README.md;herramientas/scripts/verify_signal_sensitivity.py", True),
        ("R18", "Bytes de exportación Git aislada y EOL limitados a la evidencia nueva", "pruebas/validaciones_pre_sello.json", True),
        ("R19", "Fuentes y paquetes preservados, índice del usuario intacto, sin commit/push", "pruebas/validaciones_pre_sello.json;documentos/preservacion_previa.json", True),
        ("R20", "Reporte Markdown/HTML, curvas y deltas verificables; sin PDF final", "reporte.md;reporte.html;tablas/deltas.csv;tablas/deltas_hipotesis.csv;figuras/fuentes/horizonte.csv", False),
        ("R21", "Interpretación descriptiva; sin SOFR, concentración, intradía u optimización adicionales", "documentos/encargo_usuario.md;documentos/protocolo.md;reporte.md", False),
    ]
    rows = [dict(id=key, requirement=description,
                 status="cumplido" if not needs_proof or validated else "parcial",
                 evidence=evidence,
                 scope="Bloque 2 exclusivamente; no declara completa la Entrega 4",
                 note="Validación de candidato antes del sello; auditoría final del sello externa" if needs_proof and validated else
                      "Pendiente validación final real del candidato" if needs_proof else "Evidencia derivada de las catorce carteras autenticadas")
            for key, description, evidence, needs_proof in specifications]
    write_csv(package/"matriz_requisitos.csv", rows)
    return rows
