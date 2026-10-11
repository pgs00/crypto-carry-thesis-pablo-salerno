"""Spanish report and standalone figures for the approved hypothetical scenarios."""

import re
from datetime import UTC, datetime
from decimal import Decimal as D

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from crypto_carry.config import timestamp  # noqa: E402
from scripts.return_capital.common import write_csv, write_json  # noqa: E402
from scripts.return_capital.report import render_html  # noqa: E402
from scripts.signal_sensitivity_docs import fmt, table  # noqa: E402
from scripts.stress_counterfactual_contract import SCENARIOS  # noqa: E402

LABELS = dict(conditional="Condicional", permanent="Permanente")
COLORS = dict(BASE_E3="#43515a", SH_P90="#007f8b", SH_MAX="#b83d3d", CF_SIN_INTERRUPCION="#7861ac")


def numeric(value):
    return D(str(value)) if value not in (None, "") else None


def render_report_html(text):
    return re.sub(r"<title>.*?</title>", "<title>Bloque 5 · Estrés y contrafactual</title>", render_html(text), count=1)


def verify_report_documents(package, tables, batch):
    text = report(tables, batch)
    if (package / "reporte.md").read_text(encoding="utf-8") != text:
        raise ValueError("Report prose/numerical tables differ from recomputed presentation")
    if (package / "reporte.html").read_text(encoding="utf-8") != render_report_html(text):
        raise ValueError("HTML does not correspond to the verified Markdown report")
    for link in re.findall(r"!?\[[^\]]*\]\(([^)]+)\)", text):
        if link.startswith(("https://", "http://", "#")):
            continue
        path = (package / link.split("#", 1)[0]).resolve()
        if not path.is_relative_to(package.resolve()) or not path.is_file():
            raise ValueError("Broken or external local report link: " + link)
    return dict(markdown_and_html_match=True, report_links_present=True,
                static_figure_scope="source tables included; plotted images authenticated by final seal and visually reviewed")


def figure_sources(package, tables):
    folder = package / "figuras"
    sources = folder / "fuentes"
    sources.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False,
                         "axes.grid": True, "grid.alpha": .18, "figure.facecolor": "white"})
    metadata = {}
    for family, scenarios in (("shocks", ("SH_P90", "SH_MAX")), ("sin_interrupcion", ("CF_SIN_INTERRUPCION",))):
        selected = [r for r in tables["diario"] if r["scenario"] in ("BASE_E3",) + scenarios]
        plot_rows = []
        fig, axes = plt.subplots(2, 2, figsize=(12, 7), constrained_layout=True)
        for column, strategy in enumerate(LABELS):
            for scenario in ("BASE_E3",) + scenarios:
                rows = [r for r in selected if r["scenario"] == scenario and r["strategy"] == strategy]
                if not rows:
                    continue
                high = 10000.
                x, y, drawdown = [], [], []
                for row in rows:
                    value, t = float(row["equity_usdt"]), int(row["time_ns"])
                    high = max(high, value)
                    dd = 100 * (value / high - 1) if high > 0 else None
                    x.append(datetime.fromtimestamp(t / 1e9, UTC))
                    y.append(value)
                    drawdown.append(dd)
                    plot_rows.append(dict(scenario=scenario, strategy=strategy, time_ns=t,
                                          equity_usdt=value, daily_drawdown_percent=dd))
                axes[0, column].plot(x, y, color=COLORS[scenario], label=scenario, lw=1.25)
                axes[1, column].plot(x, drawdown, color=COLORS[scenario], lw=1.1)
            axes[0, column].set_title(LABELS[strategy])
            axes[0, column].set_ylabel("Equity (USDT; inicial 10.000)")
            axes[1, column].set_ylabel("Drawdown diario (%)")
            axes[0, column].legend(frameon=False, fontsize=8)
        fig.suptitle("Bloque 5 · " + family.replace("_", " ") + " · cierres diarios UTC")
        for extension in ("png", "svg"):
            fig.savefig(folder / (family + "." + extension), dpi=170)
        plt.close(fig)
        write_csv(sources / (family + ".csv"), plot_rows)
        metadata[family] = dict(source="fuentes/" + family + ".csv", upstream="../resultados/diario.parquet",
            scope="Daily closes and initial capital; not an intraday drawdown curve")
    factors = [r for r in tables.get("ventanas_resumen", []) if r["scenario"] in ("SH_P90", "SH_MAX")]
    if factors:
        groups = [(scenario, strategy) for scenario in ("SH_P90", "SH_MAX") for strategy in LABELS]
        labels, drops, recoveries, plot_rows = [], [], [], []
        for scenario, strategy in groups:
            selected = [r for r in factors if r["scenario"] == scenario and r["strategy"] == strategy]
            drop = sum(float(r["imposed_drop_valuation_usdt"]) for r in selected)
            recovery = sum(float(r["imposed_recovery_valuation_usdt"]) for r in selected)
            labels.append(scenario + "\n" + LABELS[strategy])
            drops.append(drop)
            recoveries.append(recovery)
            plot_rows.append(dict(scenario=scenario, strategy=strategy,
                                  imposed_drop_valuation_usdt=drop, imposed_recovery_valuation_usdt=recovery))
        fig, ax = plt.subplots(figsize=(10, 4.8), constrained_layout=True)
        x = list(range(len(labels)))
        ax.bar([v - .18 for v in x], drops, width=.36, color="#b83d3d", label="Descenso impuesto")
        ax.bar([v + .18 for v in x], recoveries, width=.36, color="#007f8b", label="Recuperación impuesta: 60 min")
        ax.set_xticks(x, labels)
        ax.set_ylabel("Efecto de valoración sobre inventario previo (USDT)")
        ax.set_title("Atribución del factor spot · diagnósticos que no se suman al ledger")
        ax.legend(frameon=False)
        for extension in ("png", "svg"):
            fig.savefig(folder / ("atribucion_factor." + extension), dpi=170)
        plt.close(fig)
        write_csv(sources / "atribucion_factor.csv", plot_rows)
        metadata["atribucion_factor"] = dict(source="fuentes/atribucion_factor.csv",
            upstream="../resultados/ventanas_resumen.parquet", scope="Disjoint observation windows, both assets summed on prior inventory")
    cf = [r for r in tables.get("trayectoria_ventanas", []) if r["scenario"] == "CF_SIN_INTERRUPCION"]
    if cf:
        fig, ax = plt.subplots(figsize=(10, 4), constrained_layout=True)
        for strategy in LABELS:
            rows = [r for r in cf if r["strategy"] == strategy]
            x = [datetime.fromtimestamp(int(r["time_ns"]) / 1e9, UTC) for r in rows]
            opening = float(rows[0]["equity_before_usdt"])
            ax.plot(x, [float(r["equity_after_usdt"]) - opening for r in rows], label=LABELS[strategy])
        for label, value in (("Primera vela sintética disponible", "2023-03-24T11:28:00Z"),
                             ("Spot observado disponible", "2023-03-24T14:01:00Z")):
            ax.axvline(datetime.fromtimestamp(timestamp(value) / 1e9, UTC), color="grey", ls="--", lw=.8, label=label)
        ax.set_ylabel("Cambio de equity desde inicio de ventana (USDT)")
        ax.set_xlabel("24/03/2023 · UTC")
        ax.set_title("Contrafactual: trayectoria efectiva dentro de la intervención y sus bordes")
        ax.legend(frameon=False, fontsize=8)
        for extension in ("png", "svg"):
            fig.savefig(folder / ("cf_ventana." + extension), dpi=170)
        plt.close(fig)
        write_csv(sources / "cf_ventana.csv", cf)
        metadata["cf_ventana"] = dict(source="fuentes/cf_ventana.csv", upstream="../resultados/trayectoria_ventanas.parquet",
            scope="Minute/event observations within the approved window; not total causal interruption cost")
    write_json(folder / "fuentes.json", metadata)


def result_lines(tables):
    full = {(r["scenario"], r["strategy"]): r for r in tables["metricas"] if r["period"] == "full"}
    lines = []
    for scenario in SCENARIOS:
        if (scenario, "conditional") not in full or (scenario, "permanent") not in full:
            continue
        pieces = []
        for strategy in LABELS:
            row, base = full[scenario, strategy], full["BASE_E3", strategy]
            delta = numeric(row["final_equity_usdt"]) - numeric(base["final_equity_usdt"])
            pieces.append(f"{LABELS[strategy].lower()}: equity final {fmt(row['final_equity_usdt'], digits=2)} USDT "
                f"(diferencia {fmt(delta, digits=2)} USDT), retorno {fmt(row['net_return'], True, 3)} "
                f"y CAGR {fmt(row['cagr'], True, 3)}")
        lines.append(f"**{scenario}.** " + "; ".join(pieces) + ".")
    return lines


def report(tables, batch):
    partial = batch["partial"]
    title = "# Bloque 5: estrés spot y contrafactual sin interrupción\n"
    state = ("**Candidato parcial.** Sólo se presentan referencias y trayectorias terminadas; "
             "el bloque aún no está completo.\n" if partial else
             "**Matriz ejecutada:** seis carteras económicas continuas y cuatro controles técnicos separados. "
             "Las dos BASE originales y sus dos controles corregidos se preservan como referencias.\n")
    lines = [title, state, "\n".join(result_lines(tables)),
        "## Alcance y supuestos aprobados\n",
        "La [aprobación registrada](aprobacion_recibida.json) remite a la [ficha](ficha_decision.md), "
        "al [protocolo técnico](protocolo_tecnico.md) y a sus hashes. Sus textos históricos pendientes se conservan; "
        "la respuesta posterior del usuario autoriza las dos familias. Magnitudes, calendario, recuperación, "
        "anclas y volumen quedaron fijados antes del primer replay. No se eligieron escenarios por rendimiento.\n",
        "Las carteras comienzan con 10.000 USDT y siguen `[2022-01-01,2026-09-01)` UTC. "
        "Los ocho cortes son full, 2022, 2023, 2024, 2025, 2026 parcial, 2022–2023 y 2024+. "
        "Cada corte hereda inventario y saldos; no reinicia el capital. Se mantienen VWAP, tasas, marks, "
        "costos, cupo bruto compartido del 1%, secuencia, reservas y controles de BASE; las demoras de investigación están apagadas.\n",
        "SH_P90 y SH_MAX reducen sólo spot respecto del perpetuo. No son shocks conjuntos ni prueban resistencia "
        "del corto a subas del mark. Las magnitudes son descriptivas ex post: P90 no es probabilidad de pérdida "
        "ni nivel de confianza. El precio antiguo durante la suspensión limita la calibración original.\n",
        "## Resultados continuos y conciliación\n"]
    full = [r for r in tables["metricas"] if r["period"] == "full"]
    lines.append(table(["Escenario", "Cartera", "Equity final USDT", "P&L USDT", "Retorno", "CAGR365", "Sharpe RF=0", "DD diario"],
        [[r["scenario"], LABELS[r["strategy"]], fmt(r["final_equity_usdt"], digits=2), fmt(r["net_pnl_usdt"], digits=2),
          fmt(r["net_return"], True, 3), fmt(r["cagr"], True, 3), fmt(r["sharpe"], digits=3), fmt(r["max_drawdown"], True, 3)] for r in full]))
    lines += ["El P&L concilia equity final menos equity inicial con spot + futuros + funding + fees + liquidación "
        "a `1E-8` USDT por cierre y por período. El slippage ya está en precios de fills; su diagnóstico informativo "
        "no se resta por segunda vez. ND conserva su motivo, incluido Sharpe con volatilidad muestral cero. "
        "El cuadro principal mide drawdown **diario**.\n",
        "[Ocho períodos y utilización](resultados/metricas.csv) · [Componentes por activo](resultados/componentes_periodo.csv) · "
        "[Ejecución y cupo](resultados/ejecucion_resumen.csv) · [Eventos, deuda y liquidaciones](resultados/eventos.csv) · "
        "[Actividad y ciclos](resultados/actividad.csv) · [Conciliación](resultados/conciliacion_ledger.csv).\n",
        "![Equity y drawdown diario bajo shocks](figuras/shocks.png)\n",
        "![Equity y drawdown diario sin interrupción](figuras/sin_interrupcion.png)\n",
        "## Descenso, recuperación impuesta y operaciones\n",
        "La recuperación de **60 minutos es impuesta**: no es un plazo estimado ni elegido por P&L. "
        "A cada instante se usa la mayor intensidad vigente; los pulsos no se multiplican. El descenso comienza "
        "a afectar información cuando termina la primera vela aprobada y no modifica fills ya consumidos. "
        "Al regresar el factor a uno se conserva todo el inventario, órdenes y saldos resultantes.\n",
        "La atribución utiliza cantidad spot previa `q`, precio original `S` y factor `f`: "
        "`q·S_anterior·(f_nuevo−f_anterior)` mide el factor impuesto y "
        "`q·f_nuevo·(S_nuevo−S_anterior)` mide el movimiento del precio original. "
        "Su suma concilia el cambio de valoración spot sobre ese inventario. El componente positivo del factor "
        "es recuperación impuesta; el negativo es descenso. Son diagnósticos, no transferencias ni cargos adicionales. "
        "No se suman a P&L ni identifican una diferencia causal contra otra cartera con inventario diferente.\n"]
    shocks = []
    for scenario in ("SH_P90", "SH_MAX"):
        for strategy in LABELS:
            rows = [r for r in tables.get("ventanas_resumen", []) if r["scenario"] == scenario and r["strategy"] == strategy]
            if not rows:
                continue
            shocks.append([scenario, LABELS[strategy], len(rows),
                fmt(sum(numeric(r["imposed_drop_valuation_usdt"]) for r in rows), digits=4),
                fmt(sum(numeric(r["imposed_recovery_valuation_usdt"]) for r in rows), digits=4),
                fmt(min(numeric(r["observed_transient_loss_from_open_usdt"]) for r in rows), digits=4)])
    if shocks:
        lines += [table(["Escenario", "Cartera", "Ventanas conjuntas", "Factor descenso USDT", "Factor recuperación USDT", "Peor pérdida desde apertura de ventana USDT"], shocks),
                  "![Atribución separada del factor](figuras/atribucion_factor.png)\n"]
    operation_rows = []
    for scenario in ("SH_P90", "SH_MAX"):
        for strategy in LABELS:
            rows = [r for r in tables.get("operaciones_ventanas", [])
                    if r["scenario"] == scenario and r["strategy"] == strategy]
            if rows:
                sums = {k: sum(numeric(r[k]) for r in rows) for k in (
                    "spot_realized_pnl_usdt", "futures_realized_pnl_usdt", "ordinary_fees_usdt",
                    "liquidation_fees_usdt", "funding_usdt", "realized_operations_net_usdt")}
                operation_rows.append([scenario, LABELS[strategy],
                    fmt(sums["spot_realized_pnl_usdt"] + sums["futures_realized_pnl_usdt"], digits=4),
                    fmt(sums["ordinary_fees_usdt"] + sums["liquidation_fees_usdt"], digits=4),
                    fmt(sums["realized_operations_net_usdt"], digits=4), fmt(sums["funding_usdt"], digits=4)])
    if operation_rows:
        lines += [table(["Escenario", "Cartera", "Realizado spot + futuros USDT", "Fees + liquidación USDT",
                         "Operaciones netas realizadas USDT", "Funding USDT"], operation_rows),
            "[Operaciones por ventana](resultados/operaciones_ventanas.csv) incluye eventos del ledger "
            "en los intervalos observados, con preludio y bordes explícitos. Excluye cambios no realizados. "
            "Estos resultados no son el P&L total de equity y no se les suma la atribución del factor, "
            "pues eso contaría valoración dos veces. El slippage ya está en el precio de cada fill.\n"]
    lines += ["La pérdida transitoria incluye movimientos del mercado y las operaciones de la trayectoria; "
        "se informa separadamente del factor impuesto y del P&L realizado, funding y comisiones del ledger. "
        "Los extremos se limitan a ventanas intervenidas y sus bordes, a cierres de minuto y eventos financieros; "
        "no son máximos intradía de toda la muestra. Su base es el estado anterior al primer evento de "
        "cada ventana; se conserva su timestamp. La valoración sobre spot antiguo durante la suspensión "
        "se identifica por fuente y antigüedad, sin habilitar fills ni renovar su disponibilidad.\n",
        "**El calendario BASE permanece fijo.** No estresa automáticamente exposiciones nuevas que aparezcan "
        "en las trayectorias modificadas. Una posición cerrada antes tampoco elimina el pulso. "
        "[Cobertura de episodios modificados](resultados/cobertura_calendario_fijo.parquet) cuantifica los segundos "
        "dentro y fuera del calendario revelado, sin agregar shocks.\n",
        "## Garantías y caja\n",
        "[Garantías por activo y fase](resultados/garantias_ventanas.parquet) separa saldo de margen, "
        "mantenimiento, holgura, distancia a liquidación y necesidad preventiva. Tras cerrar el corto, "
        "su margen es ND/no aplicable y su requerimiento es cero. Se observan estados anteriores a fills "
        "con el mark recién disponible, además de los estados posteriores. No se combinan extremos de velas "
        "como si hubieran ocurrido simultáneamente.\n",
        "[Necesidad conjunta](resultados/garantias_simultaneas.parquet) suma requerimientos **simultáneos**, "
        "descuenta caja libre de reservas y conserva deuda. No reutiliza colateral aislado ni suma máximos "
        "de distintos instantes. La cifra preventiva es un ínfimo: el límite de ratio exige desigualdad estricta "
        "cuando resulta vinculante. No se inyectan esos importes al backtest.\n",
        "## Escenario sin interrupción y sus fronteras\n",
        "Se sustituyen 153 aperturas de vela por activo del 24/03/2023 `[11:27,14:00)` UTC. "
        "Incluyen la vela parcial de 11:27; los 152 minutos de cierre completo y los 121 minutos descubiertos "
        "de BASE son duraciones distintas. Cada vela sintética se publica al terminar. La reapertura observada "
        "vuelve con la vela abierta 14:00, conocida 14:01.\n",
        "Las anclas aprobadas son BTC `28068.79/28053.70` y ETH `1788.70/1787.90`. "
        "Implican **basis futuro/spot−1 negativo constante** durante las velas sintéticas "
        "(salvo redondeo Decimal 28): aproximadamente −5,3761 pb BTC y −4,4725 pb ETH. "
        "Eso restringe nuevas entradas con el filtro inclusivo `[0,0.005]`. "
        "No se alteraron las anclas para conseguir operaciones. Órdenes heredadas y decisiones posteriores "
        "siguen evolucionando con las reglas ordinarias.\n",
        "El volumen es la mediana spot por hora UTC de los dos días completos anteriores aprobados, "
        "con ceros y 120 observaciones por grupo. No copia volumen de futuros ni supone liquidez infinita. "
        "El lapso corto no acredita estacionalidad semanal o profundidad del libro. Las fuentes de futuros, "
        "marks y tasas quedan intactas como condición hipotética; el importe de funding se recalcula con "
        "el corto anterior a fills simultáneos, mark de cálculo del pago y tasa.\n"]
    risk = tables.get("garantias_resumen", [])
    if risk:
        position = lines.index("## Escenario sin interrupción y sus fronteras\n")
        lines[position:position] = [table(["Escenario", "Cartera", "Máximo preventivo conjunto (ínfimo USDT)",
            "Máximo faltante externo conocido (ínfimo USDT)", "Observaciones ND"],
            [[r["scenario"], LABELS[r["strategy"]], fmt(r["max_preventive_topup_infimum_usdt"], digits=4),
              fmt(r["max_known_external_shortfall_infimum_usdt"], digits=4), r["unknown_external_need_observations"]]
             for r in risk]), "La tabla se limita a las ventanas auditadas. Cero no se interpreta como "
            "ausencia de riesgo fuera de ellas; cuando vincula una restricción estricta, se conserva la "
            "distinción entre ínfimo y aporte suficiente. [Timestamps y cobertura](resultados/garantias_resumen.csv).\n"]
    joins = tables.get("uniones_contrafactual", [])
    if joins:
        lines.append(table(["Cartera", "Activo", "Frontera", "Salto cierre/cierre", "Cantidad previa", "Valoración previa USDT"],
            [[LABELS[r["strategy"]], r["symbol"], r["edge"], fmt(r["price_jump_fraction"], True, 4),
              fmt(r["quantity_before"], digits=8), fmt(r["valuation_on_prior_inventory_usdt"], digits=4)] for r in joins]))
        lines.append("![Ventana contrafactual](figuras/cf_ventana.png)\n")
    contrasts = tables.get("cf_contraste_diario", [])
    if contrasts:
        milestones = []
        for strategy in LABELS:
            selected = [r for r in contrasts if r["strategy"] == strategy]
            if not selected:
                continue
            for label, date in (("Antes del incidente", "2023-03-23"), ("Día intervenido", "2023-03-24"),
                                ("Fin de muestra", selected[-1]["date"])):
                row = next((r for r in selected if r["date"] == date), None)
                if row:
                    milestones.append([LABELS[strategy], label, date, fmt(row["equity_delta_usdt"], digits=4),
                                       fmt(row["daily_pnl_delta_usdt"], digits=4)])
        lines.append(table(["Cartera", "Corte", "Cierre UTC", "Diferencia de equity CF−BASE USDT", "Diferencia de P&L del día USDT"], milestones))
        lines.append("[Contraste diario completo](resultados/cf_contraste_diario.csv) conserva los cambios "
                     "posteriores; la diferencia final no se atribuye íntegramente al día de la intervención.\n")
    actions = tables.get("cf_decisiones_ejecuciones", [])
    if actions:
        phase_labels = dict(ventana_y_reapertura="11:28–14:02 UTC", resto_dia="Resto del 24/03",
                            posterior="Desde 25/03 hasta fin")
        kind_labels = dict(decisions="Decisión/estado", order_submissions="Emisión de orden", fills="Fill")
        lines.append(table(["Cartera", "Tramo", "Registro", "BASE / CF", "Claves comunes modificadas", "Sólo BASE / sólo CF"],
            [[LABELS[r["strategy"]], phase_labels[r["phase"]], kind_labels[r["record_kind"]],
              f"{r['base_records']} / {r['cf_records']}", r["changed_matching_keys"],
              f"{r['only_base_keys']} / {r['only_cf_keys']}"] for r in actions if r["phase"] != "previo"]))
        lines.append("[Comparación de decisiones y ejecuciones](resultados/cf_decisiones_ejecuciones.csv) "
            "exige identidad antes de la primera vela sintética disponible, a las 11:28. Agrupa por "
            "timestamp, activo y tipo; excluye identificadores generados. Un cambio de timestamp aparece "
            "como una clave exclusiva en cada senda, no como una pareja causal demostrada. Para órdenes "
            "se comparan datos de emisión: una orden previa puede ejecutarse después de forma distinta. "
            "Los precios/cantidades y cargos de fills se comparan en su instante de ejecución. "
            "El detalle conserva multiplicidad, proyecciones y primera divergencia por tramo.\n")
    lines += ["La unión no se suaviza. El salto cierre/cierre en cada frontera y su efecto sobre inventario "
        "previo se separan de las operaciones. Ese salto combina el cambio de fuente con el movimiento "
        "de mercado entre los dos cierres; no mide aisladamente un efecto causal de la fuente. "
        "La cartera se ejecuta hasta el fin conservando las consecuencias del episodio, "
        "no se limita a restar el resultado de ese día. Este ejercicio no identifica causalmente el costo "
        "real de la interrupción ni predice cómo habría reaccionado el resto del mercado.\n",
        "## H1, H2 y H3\n",
        "H1 autentica proyecciones, disponibilidad y cohortes de funding antes de reutilizarlas; "
        "recalcula targets desde los registros consumidos y coteja la evaluación archivada. Los targets "
        "posteriores no se usan como información ex ante. H2 compara condicional y permanente del mismo "
        "escenario y mantiene el criterio de exigir CAGR condicional positivo y Sharpe superior al permanente, "
        "con RF=0 y ND explícito.\n",
        "H3 se obtiene del replay del mercado modificado, independiente de inventario y fondos: forecast "
        "completo al pasar filtros, cero para fallas conocidas, ND para desconocidos; promedio diario por "
        "activo y pesos 50/50. Se recomputan las fórmulas de los testigos de las ventanas, su cobertura "
        "y las agregaciones diarias; no se copia H3 BASE. Las dos estrategias deben recibir la misma "
        "senda y oportunidad. Estas sensibilidades hipotéticas no son nueva evidencia histórica ni validación fuera de muestra.\n"]
    h2 = {r["scenario"]: r for r in tables["h2"] if r["period"] == "full"}
    h3 = {r["scenario"]: r for r in tables["h3_resumen"] if r["period"] == "full"}
    lines.append(table(["Escenario", "H2 full", "H3 2022–2023 vs 2024+", "Oportunidad full pb/168h"],
        [[s, h2[s]["verdict"], h3[s]["h3_descriptive"], fmt(h3[s]["opportunity_mean_bps"], digits=6)]
         for s in h2 if s in h3]))
    lines += ["[H1 por períodos](resultados/h1_resumen.csv) · [H2 por ocho cortes](resultados/h2.csv) · "
        "[H3 por períodos](resultados/h3_resumen.csv) · [Deltas frente a BASE](resultados/deltas.csv). "
        "Los resultados anuales no se suman ni se imponen relaciones monótonas entre shocks.\n",
        "## Evidencia, reproducción y pendientes\n",
        "[Índice de corridas](indice_corridas.json) distingue referencias, controles y seis carteras nuevas. "
        "[Contrato congelado](protocolo_ejecucion.json), [exportaciones exactas](fuentes_exportadas.json) "
        "y [catálogo de resultados](resultados/catalogo.json) identifican sus fuentes. "
        "Las corridas originales permanecen intactas; la evaluación CSV grande se incluye comprimida sin pérdida "
        "y se coteja descomprimida contra su hash original. No se duplicaron las bases de minutos por escenario.\n",
        "Hubo además cuatro intentos técnicos iniciales preservados. El control de shock cero detuvo "
        "el avance por cuatro celdas de precio con valor numérico idéntico y distinta representación "
        "Decimal. Se corrigió la identidad cuando el factor vale uno y se repitieron los cuatro controles "
        "con código nuevo, antes de ejecutar economía. No se relajó la comparación ni se cambiaron "
        "referencias o supuestos. [Incidente y corrección](controles/incidente_control_cero.md) · "
        "[Identidades de los intentos previos](intentos_tecnicos_previos.json).\n",
        "El verificador offline recalcula contabilidad, ejecución, fórmulas de intervención, diagnósticos "
        "de ventanas y agregados H1/H2/H3. Comparte helpers de reporte con el constructor; no es otro "
        "motor económico independiente. Las ecuaciones de transformación del auditor son separadas de la capa de replay. "
        "Los minutos de H3 fuera de los testigos se autentican como salida persistida y se agregan; "
        "no se reejecutan millones de minutos offline. Las pertenencias a particiones masivas se autenticaron "
        "al extraer; reproducirlas exige las 1.731 entradas locales identificadas.\n",
        "```powershell\npython -B herramientas/scripts/verify_stress_counterfactual.py . --output ../verificacion_bloque5.json\n```\n",
        "La [guía de reproducción](reproducibilidad.md) declara dependencias y alcance. Las auditorías finales "
        "se guardan fuera del sello. El índice Git no fue modificado por este trabajo; no se hizo commit ni push. "
        "No se ejecutó limpieza, borrado ni archivado. El inventario previo conserva carácter de propuesta separada.\n",
        "Bloque 6, revisión transversal y redacción final siguen pendientes. El alcance de la reparación "
        "de liquidación sobre variantes de bloques 2/3 continúa pendiente y separado: la equivalencia BASE "
        "no lo resuelve. Este bloque no declara completa toda Entrega 4.\n"]
    return "\n".join(lines)


def write_docs(package, tables, batch):
    figure_sources(package, tables)
    text = report(tables, batch)
    (package / "reporte.md").write_text(text, encoding="utf-8")
    (package / "reporte.html").write_text(render_report_html(text), encoding="utf-8")
    synthesis = ["# Síntesis integrable: bloque 5\n",
        "**Borrador parcial: ejecución y verificación final pendientes.**\n" if batch["partial"] else "",
        *result_lines(tables),
        "El protocolo evalúa las trayectorias aprobadas con el motor corregido, bajo un mercado hipotético común "
        "a cada pareja. La referencia es BASE preservada; la equivalencia económica se comprueba con los "
        "controles corregidos, capa apagada y shock cero. Capital, parámetros, costos y muestra son continuos.\n",
        "En shocks, la recuperación de 60 minutos es impuesta y se separa del descenso, del movimiento "
        "del precio original y del resultado de operaciones. La atribución de valoración no agrega flujos "
        "al ledger. El calendario retrospectivo BASE no cubre automáticamente nuevas exposiciones. "
        "El spot antiguo durante la suspensión sigue identificado y no permite transacciones.\n",
        "En el contrafactual, las anclas fijas implican basis negativo constante y restringen entradas. "
        "No se alteraron para obtener operaciones. Precio, volumen y reapertura son supuestos identificados; "
        "la trayectoria posterior conserva sus consecuencias. Mantener futuros, marks y tasas originales "
        "no identifica causalmente el costo real de la interrupción.\n",
        "El drawdown principal es diario. Los extremos de riesgo se limitan a ventanas y fases observadas, "
        "sin denominarlos máximos intradía globales. Garantías y faltantes de caja son necesidades hipotéticas "
        "simultáneas; no se inyectó dinero. H1/H2/H3 mantienen sus definiciones y sus ND, con H3 recalculada "
        "sobre el mercado de cada escenario. Los resultados hipotéticos no reemplazan evidencia histórica.\n",
        "Ver [reporte con tablas](reporte.md), [fuentes y corridas](indice_corridas.json) y "
        "[protocolo aprobado](protocolo_tecnico.md). Bloque 6 y revisión transversal permanecen pendientes.\n"]
    (package / "sintesis.md").write_text("\n".join(synthesis), encoding="utf-8")
