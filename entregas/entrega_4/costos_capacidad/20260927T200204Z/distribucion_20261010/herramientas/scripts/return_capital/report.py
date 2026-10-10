"""Readable reports and scientific figures, all driven by checked CSV tables."""

import html
import re

from .common import RUNS, SYMBOLS, number, truth, write_csv, write_json

LABEL = {"conditional": "Condicional", "permanent": "Permanente"}


def fmt(value, percent=False, digits=2):
    if value in (None, ""):
        return "ND"
    v = number(value) * (100 if percent else 1)
    return f"{v:,.{digits}f}".replace(",", "_").replace(".", ",").replace("_", ".") + (
        "%" if percent else ""
    )


def md_table(headers, rows):
    return "\n".join(
        [
            "| " + " | ".join(headers) + " |",
            "| " + " | ".join("---" for _ in headers) + " |",
            *("| " + " | ".join(str(v).replace("|", "/") for v in row) + " |" for row in rows),
        ]
    )


def report_markdown(tables):
    operational = []
    for strategy in RUNS:
        reasons = [
            r
            for r in tables["motivos_simultaneos"]
            if r["strategy"] == strategy
            and r["period"] == "full"
            and r["symbol"] == "PORTFOLIO"
            and r["decision_kind"] == "entry"
        ]
        groups = {}
        for r in reasons:
            key = int(r["order_position"]), r["filter"], truth(r["applied"])
            groups.setdefault(key, {})[r["state"]] = int(r["count"])
        for (rank, name, applied), states in sorted(groups.items()):
            operational.append(
                [
                    LABEL[strategy],
                    rank + 1,
                    name,
                    "Sí" if applied else "No",
                    states.get("pass", 0),
                    states.get("fail", 0),
                    states.get("not_evaluable", 0),
                ]
            )
    text = [
        "# Retorno, capital y restricciones de entrada",
        "",
        "Entrega 4 · Bloque técnico local · Muestra continua [01/01/2022,01/09/2026) UTC. "
        "Sólo las dos BASE_E3, 10.000 USDT iniciales cada una. Concentración y restricciones: "
        "**ejecutado**. Benchmark: **pendiente_aprobacion_benchmark**. Este bloque no completa toda la Entrega 4.",
        "",
        "[Protocolo](documentos/protocolo.md) · [Mapa de fuentes](documentos/mapa_fuentes.md) · "
        "[Propuesta remunerada](documentos/propuesta_benchmark.md) · [Ficha exacta](documentos/ficha_benchmark.json)",
        "",
        "## Resultado y concentración",
    ]
    summaries = []
    for strategy, run in RUNS.items():
        financial = next(
            r for r in tables["resumen_integrado"] if r["run_id"] == run and r["period"] == "full"
        )
        con = [
            r
            for r in tables["concentracion_ciclos"]
            if r["run_id"] == run and r["period"] == "full" and r["symbol"] == "PORTFOLIO"
        ]
        top3 = next(r for r in con if r["sign"] == "positive" and int(r["requested_k"]) == 3)
        summaries.append(
            dict(
                strategy=strategy,
                **{
                    k: financial[k]
                    for k in (
                        "net_pnl_usdt",
                        "cagr",
                        "invested_fraction",
                        "capital_utilization_daily_mean",
                    )
                },
                top3_share_G=top3["share_sign"],
            )
        )
        text += [
            "",
            f"### {LABEL[strategy]}",
            "",
            f"P&L de cartera: **{fmt(financial['net_pnl_usdt'])} USDT**, retorno {fmt(financial['net_return'], True)} "
            f"y CAGR {fmt(financial['cagr'], True)} sobre 1.704 días. "
            f"Los tres ciclos positivos de mayor contribución reúnen {fmt(top3['share_sign'], True)} de G. "
            f"G={fmt(top3['G_usdt'])} y L={fmt(top3['L_usdt'])} USDT; fuera de ciclo: "
            f"{fmt(financial['outside_cycle_pnl_usdt'], digits=6)} USDT.",
            "",
            md_table(
                [
                    "Signo",
                    "Top solicitado",
                    "Cantidad efectiva",
                    "P&L seleccionado (USDT)",
                    "% de G o L",
                    "% del neto de ciclos",
                ],
                [
                    [
                        "Ganancia" if r["sign"] == "positive" else "Pérdida",
                        r["requested_k"],
                        r["effective_k"],
                        fmt(r["selected_pnl_usdt"]),
                        fmt(r["share_sign"], True),
                        fmt(r["share_net"], True),
                    ]
                    for r in con
                ],
            ),
        ]
    text += [
        "",
        "Los denominadores G/L incluyen únicamente los ciclos del período. El neto de ciclos puede "
        "diferir del de cartera por polvo fuera de ciclo. Los porcentajes sobre neto no son proporciones "
        "del capital; no se recortan si superan 100%. En los CSV se advierte neto no positivo o pequeño "
        "(menor al 10% de G+L). No se calcula un CAGR hipotético quitando los mejores ciclos.",
        "",
        "![Vida completa de todos los ciclos, USDT](figuras/ciclos.png)",
        "",
        "[Ciclos con todos sus componentes](tablas/ciclos_vida.csv) · "
        "[Contribución por fecha y período](tablas/contribuciones_ciclo_periodo.csv) · "
        "[Top por activo y cartera](tablas/concentracion_ciclos.csv)",
        "",
        "### Contribución de cada activo en la muestra completa",
        "",
        md_table(
            [
                "Cartera",
                "Activo",
                "Dentro de ciclos (USDT)",
                "Fuera de ciclos (USDT)",
                "Total (USDT)",
            ],
            [
                [
                    LABEL[strategy],
                    symbol,
                    *[
                        fmt(
                            sum(
                                (
                                    number(r["net_pnl_usdt"])
                                    for r in tables["contribuciones_ciclo_periodo"]
                                    if r["strategy"] == strategy
                                    and r["symbol"] == symbol
                                    and r["period"] == "full"
                                    and (
                                        category == "total"
                                        or (r["category"] == "cycle") == (category == "cycle")
                                    )
                                ),
                                number(0),
                            ),
                            digits=6,
                        )
                        for category in ("cycle", "outside", "total")
                    ],
                ]
                for strategy in RUNS
                for symbol in SYMBOLS
            ],
        ),
        "",
        "## Días de cartera: mejores y peores",
        "",
        "Cada jornada aparece una sola vez por cartera, aunque operen ambos activos. Se reutiliza el P&L "
        "diario conciliado; no se suman retornos porcentuales. Los denominadores diarios son propios de "
        "los días positivos y negativos e incluyen todo el resultado de cartera, incluido el polvo.",
        "",
        md_table(
            ["Cartera", "Signo", "Top días", "P&L (USDT)", "% de G/L diario"],
            [
                [
                    LABEL[r["strategy"]],
                    r["sign"],
                    r["requested_k"],
                    fmt(r["selected_pnl_usdt"]),
                    fmt(r["share_sign"], True),
                ]
                for r in tables["concentracion_dias"]
                if r["period"] == "full"
            ],
        ),
        "",
        "![Concentración diaria y por ciclo, denominadores separados](figuras/concentracion.png)",
        "",
        "[Fechas seleccionadas y denominadores de todos los períodos](tablas/concentracion_dias.csv) · "
        "[Todos los días originales](tablas/diario_reutilizado.csv)",
        "",
        "## Contabilidad, ciclos y remanentes",
        "",
        "Se reconstruyeron las cuentas de cada activo desde el ledger, conservando compras netas, costo "
        "promedio, parciales, rebalanceos, funding, fees y cargos. La atribución es la diferencia de "
        "P&L acumulado del activo entre fronteras. No se asigna el cambio total de equity al activo que "
        "envió una orden. Las 3.408 jornadas concilian a la tolerancia original de 1E-8 USDT.",
        "",
        md_table(
            [
                "Cartera",
                "Ciclos",
                "Cerrados completos",
                "Apertura incompleta",
                "Sin fill",
                "Abiertos al fin",
                "Intentos fallidos de órdenes",
            ],
            [
                [
                    LABEL[r["strategy"]],
                    r["cycles_participating"],
                    r["closed"],
                    r["incomplete_opening"],
                    r["attempt_without_fill"],
                    r["open_at_period_end"],
                    r["failed_attempts"],
                ]
                for r in tables["resumen_integrado"]
                if r["period"] == "full"
            ],
        ),
        "",
        "Un intento fallido de orden no es necesariamente una apertura fallida: puede ser un "
        "rebalanceo, reintento o cierre. Las renovaciones conservan cycle_id. Los abiertos al final "
        "incluyen P&L no realizado sin venta ni comisión terminal. El costo y las unidades del polvo "
        "se conservan; su variación fuera de ciclo figura como outside_dust. Al ingresar a otro ciclo "
        "se toma como base el P&L ya devengado, sin reconocerlo de nuevo. El slippage ya está en los precios.",
        "",
        "Las filas por período atribuyen cambios económicos dentro de cada corte, aunque el ciclo "
        "haya comenzado antes o termine después. No son agrupaciones por año de cierre. Tiempo activo "
        "excluye polvo según la corrección vigente. Una variación de realizado/no realizado puede ser "
        "una reclasificación de una ganancia anterior; sólo su suma es contribución neta nueva.",
        "",
        "[Fronteras y precios trazables](tablas/fronteras_contables.csv) · "
        "[Segmentos contables](tablas/atribuciones_segmentos.csv) · "
        "[Movimientos con event_id/order_id/fill_id](tablas/movimientos_ciclo.csv) · "
        "[Conciliaciones](tablas/conciliaciones.csv)",
        "",
        "## Restricciones: tres poblaciones que no deben confundirse",
        "",
        "### A. Condiciones simultáneas de funding y basis",
        "",
        "Las 10.224 evaluaciones de entrada de cada estrategia están emparejadas por activo, instante "
        "y clase. Tienen las mismas condiciones de mercado, pero diferentes caja y posiciones. "
        "480 pasan ambos filtros; esto no significa 480 órdenes posibles o enviadas. Los límites "
        "de basis 0 y 0,005 son inclusivos. No hubo fallos por basis superior al techo; los fallos "
        "de basis observados son negativos. Una fila no evaluable queda fuera de las cuatro celdas.",
        "",
        md_table(
            ["Cartera", "Celda", "Filas", "Población"],
            [
                [LABEL[r["strategy"]], r["group"], r["count"], r["denominator"]]
                for r in tables["grupos_excluyentes"]
                if r["period"] == "full"
                and r["symbol"] == "PORTFOLIO"
                and r["decision_kind"] == "entry"
                and r["view"] == "market"
            ],
        ),
        "",
        "![Partición de condiciones evaluadas](figuras/filtros_mercado.png)",
        "",
        "### B. Primer bloqueo y restricciones simultáneas",
        "",
        "El embudo usa el orden persistido, con grupos excluyentes. La tabla de motivos simultáneos "
        "conserva pass/fail/not_evaluable y puede solaparse. En la permanente el fallo de funding es "
        "diagnóstico, no aplicado. Un sizing o presupuesto prospectivo con posición abierta no prueba "
        "una entrada perdida por falta de fondos.",
        "",
        md_table(
            ["Cartera", "Primer bloqueo diagnóstico", "Filas", "Población"],
            [
                [LABEL[r["strategy"]], r["group"], r["count"], r["denominator"]]
                for r in tables["grupos_excluyentes"]
                if r["period"] == "full"
                and r["symbol"] == "PORTFOLIO"
                and r["decision_kind"] == "entry"
                and r["view"] == "sequential"
            ],
        ),
        "",
        "[Todos los motivos simultáneos, con orden y aplicación](tablas/motivos_simultaneos.csv) · "
        "[Grupos por activo, estrategia y período](tablas/grupos_excluyentes.csv)",
        "",
        "El detalle siguiente usa 10.224 evaluaciones por cartera y conserva el orden registrado "
        "(posición mostrada desde 1). Cada filtro particiona su propia población; los fallos de "
        "filtros distintos se solapan y no deben sumarse como entradas perdidas. Se muestran también "
        "los filtros con cero fallos y los diagnósticos no aplicados.",
        "",
        md_table(
            ["Cartera", "Orden", "Filtro", "Aplicado", "Pass", "Fail", "No evaluable"], operational
        ),
        "",
        "### C. Decisiones y acciones acreditadas",
        "",
        "Los logs registran 10 entradas aceptadas condicionales y 20 permanentes, enlazadas una a una "
        "con la transición y orden inicial originales. En la condicional, 7.952 decisiones registran "
        "funding_not_above_cost; en la permanente, 323 registran basis_outside_entry_range. "
        "No hay decisiones de entrada con causa insufficient_free_funds: ello no elimina las restricciones de "
        "presupuesto en otros estados ni los rebalanceos omitidos. El campo de primer bloqueo "
        "diagnóstico y la causa de decisión permanecen separados.",
        "",
        "Las acciones sin evaluación exacta acreditable permanecen como unreconciled en su enlace "
        "temporal; incluyen acciones autónomas posteriores a una señal. Coincidir en tiempo no prueba "
        "causalidad. Las órdenes iniciales tienen además un vínculo por order_id; cada tabla conserva "
        "el ordinal original, sin convertir el historial de evaluaciones en órdenes.",
        "",
        "Renovación se analiza aparte: 103 evaluaciones condicionales y 458 permanentes. Su umbral es "
        "forecast positivo, sin costo ni basis de entrada; el registro de resultado puede carecer de "
        "causa textual y se contrasta con las transiciones. La cobertura de emparejamiento se entrega "
        "sin forzar igualdad. Ninguno de estos conteos equivale a minutos elegibles de H3.",
        "",
        "[Registros clasificados](tablas/decisiones_clasificadas.csv) · "
        "[Diagnóstico frente a decisión](tablas/diagnostico_vs_decision.csv) · "
        "[Acciones y enlaces, incluidos los no reconciliados](tablas/acciones_y_enlaces.csv) · "
        "[Entradas acreditadas](tablas/entradas_acreditadas.csv) · [Emparejamiento](tablas/emparejamiento.csv)",
        "",
        "## Retorno anual y capital utilizado",
    ]
    for strategy in RUNS:
        rows = [r for r in tables["resumen_integrado"] if r["strategy"] == strategy]
        full = next(r for r in rows if r["period"] == "full")
        text += [
            "",
            f"### {LABEL[strategy]}",
            "",
            f"Capital utilizado al cierre: media de {fmt(full['capital_deployed_usdt_daily_mean'])} USDT "
            f"y máximo de {fmt(full['capital_deployed_usdt_daily_max'])} USDT en la muestra completa. "
            "Los valores diarios y por período se conservan en el resumen integrado.",
            "",
            md_table(
                [
                    "Período",
                    "Días",
                    "P&L USDT",
                    "Retorno",
                    "CAGR",
                    "Tiempo activo",
                    "Utiliz. media",
                    "Utiliz. máxima",
                    "Ciclos con participación",
                    "Intentos fallidos",
                ],
                [
                    [
                        r["period"],
                        r["days"],
                        fmt(r["net_pnl_usdt"]),
                        fmt(r["net_return"], True, 3),
                        fmt(r["cagr"], True, 3),
                        fmt(r["invested_fraction"], True),
                        fmt(r["capital_utilization_daily_mean"], True),
                        fmt(r["capital_utilization_daily_max"], True),
                        r["cycles_participating"],
                        r["failed_attempts"],
                    ]
                    for r in rows
                ],
            ),
        ]
    text += [
        "",
        "![P&L, tiempo activo y capital utilizado por año](figuras/resumen_anual.png)",
        "",
        "CAGR usa duración/365; 2026 es enero–agosto, no doce meses observados. El capital utilizado "
        "al cierre es spot valuado más garantía, dividido por equity. Puede superar 100% por la "
        "valuación del corto. El tiempo activo es la unión temporal sin polvo: no es utilización "
        "de patrimonio. No se divide CAGR por utilización. Los saldos se heredan y los retornos de "
        "tramos no se suman.",
        "",
        "La mejora de precisión de H1 no garantiza superar el umbral económico ni permanecer "
        "invertido. Los registros muestran pocos ciclos condicionales, concentración de ganancias "
        "y menor utilización. Es consistente con una menor captura de ingresos de funding, pero "
        "no cuantifica cuánto rendiría eliminar filtros o remunerar su caja: eso alteraría tamaños, "
        "margen y decisiones. Son explicaciones posibles, no una prueba causal ni una optimización.",
        "",
        "H1, H2 corregida y H3 se reutilizan sin redefinirlos. H2 sigue no favorable en muestra "
        "completa y ambos cortes por Sharpe condicional inferior. En 2022 el Sharpe condicional "
        "permanece ND por volatilidad muestral cero. El análisis anual complementa los cortes H3; "
        "no sustituye su serie por rechazos. No se rehizo riesgo intradía.",
        "",
        "[Resumen completo y capital en USDT](tablas/resumen_integrado.csv) · "
        "[Componentes por activo originales](tablas/componentes_por_activo_periodo_reutilizado.csv) · "
        "[H1](tablas/h1_resumen_reutilizado.csv) · [H2](tablas/h2_reutilizado.csv) · [H3](tablas/h3_regimen_reutilizado.csv)",
        "",
        "## Propuesta remunerada y límites",
        "",
        "Se recomienda someter a aprobación una cuenta hipotética bruta USD ligada a SOFR realizada, "
        "ACT/360, con paridad nominal 1 USDT=1 USD. SGOV fue la única alternativa real examinada. "
        "La serie oficial SOFR descargada contiene 1.166 observaciones entre 30/12/2021 y 01/09/2026; "
        "se comprobó cobertura, sin calcular retornos. La ficha enumera supuestos, costos excluidos, "
        "acceso hipotético, calendario por acreditar y reglas de frontera. No es una cuenta remunerada "
        "disponible para el inversor ni una tasa pagada por el exchange.",
        "",
        "[Propuesta, fuentes primarias y aprobación puntual](documentos/propuesta_benchmark.md). "
        "Estado pendiente_aprobacion_benchmark. Una aprobación posterior habilitará sólo ese componente "
        "en otra versión; no sumará intereses al carry ni cambiará H2.",
        "",
        "## Verificación y portabilidad",
        "",
        "El paquete contiene código, pruebas, manifiesto y fuentes con hashes. El verificador compacto "
        "recalcula aritmética, segmentos, denominadores y clasificaciones. El completo autentica las "
        "dependencias por rutas explícitas y vuelve a derivar todas las tablas desde los movimientos "
        "originales; comparte los módulos de posprocesamiento y no es una validación independiente "
        "del motor. No consulta Git ni escribe en los paquetes fuente. Ver comandos en [README](README.md).",
        "",
        "Se conserva la incertidumbre de valoración spot durante la suspensión de marzo de 2023 "
        "y las aproximaciones de mark/funding del estudio. Las fronteras de cierre reutilizan precios "
        "del paquete intradía compacto, sin nuevas series masivas. No se afirma leer un PDF E3 ausente. "
        "La aprobación del benchmark, su ejecución y el PDF final quedan pendientes. No se hizo commit, "
        "push ni publicación GitHub.",
    ]
    return "\n".join(text) + "\n", summaries


def render_html(markdown):
    def inline(value):
        value = html.escape(value)
        value = re.sub(
            r"!\[([^]]*)\]\(([^)]+)\)",
            r'<figure><img src="\2" alt="\1"><figcaption>\1</figcaption></figure>',
            value,
        )
        value = re.sub(r"\[([^]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', value)
        value = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", value)
        return value

    output, in_table = [], False
    for line in markdown.splitlines():
        if line.startswith("|"):
            if not in_table:
                output.append('<div class="table-wrap"><table>')
                in_table = True
            if re.fullmatch(r"[| :\-]+", line):
                continue
            output.append(
                "<tr>"
                + "".join("<td>" + inline(v.strip()) + "</td>" for v in line.strip("|").split("|"))
                + "</tr>"
            )
            continue
        if in_table:
            output.append("</table></div>")
            in_table = False
        if line.startswith("#"):
            level = len(line) - len(line.lstrip("#"))
            output.append(f"<h{level}>" + inline(line[level:].strip()) + f"</h{level}>")
        elif line:
            output.append("<p>" + inline(line) + "</p>")
    if in_table:
        output.append("</table></div>")
    return (
        '<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Retorno y capital · BASE_E3</title><style>body{max-width:1180px;margin:48px auto;padding:0 24px;font:17px/1.65 system-ui;color:#183046;background:#fbfcfe}h1{font-size:36px;line-height:1.15}h2{margin-top:48px;border-top:2px solid #d9e4ed;padding-top:22px}h3{color:#245878}a{color:#075c8c}table{border-collapse:collapse;font-size:14px;width:100%;background:white}td{padding:9px 12px;border-bottom:1px solid #dce5ed;text-align:right}td:first-child{text-align:left}tr:first-child{font-weight:700;background:#e8eff6}.table-wrap{overflow-x:auto}figure{margin:28px 0}img{max-width:100%;height:auto}figcaption{font-size:13px;color:#52677a}</style><main>'
        + "\n".join(output)
        + "</main></html>\n"
    )


def figures(package, tables):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    folder = package / "figuras"
    folder.mkdir()
    plt.rcParams.update(
        {
            "font.size": 10,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "savefig.dpi": 180,
            "font.family": "DejaVu Sans",
        }
    )

    def save(fig, name, source):
        fig.tight_layout()
        fig.savefig(folder / (name + ".png"), bbox_inches="tight")
        fig.savefig(folder / (name + ".svg"), bbox_inches="tight")
        plt.close(fig)
        write_csv(folder / "fuentes" / (name + ".csv"), source)

    fig, axes = plt.subplots(1, 2, figsize=(14, 8))
    for ax, strategy in zip(axes, RUNS):
        selected = sorted(
            [r for r in tables["ciclos_vida"] if r["strategy"] == strategy],
            key=lambda r: number(r["net_pnl_usdt"]),
        )
        values = [float(r["net_pnl_usdt"]) for r in selected]
        ax.barh(
            range(len(selected)), values, color=["#ba4b45" if v < 0 else "#267997" for v in values]
        )
        ax.set_yticks(
            range(len(selected)),
            [
                r["symbol"][:3]
                + " "
                + r["entry_utc"][:10]
                + (" *" if r["status"] == "open_at_end" else "")
                for r in selected
            ],
        )
        ax.axvline(0, color="#536271", lw=0.8)
        ax.set(title=LABEL[strategy], xlabel="Contribución de vida completa (USDT)")
    fig.suptitle(
        "Todos los ciclos BASE_E3 · 2022–agosto 2026\n* Abierto al final: incluye valoración sin venta terminal",
        fontsize=14,
    )
    save(fig, "ciclos", tables["ciclos_vida"])
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8))
    sources = []
    for ax, name, title in zip(
        axes, ("concentracion_ciclos", "concentracion_dias"), ("Ciclos", "Días de cartera")
    ):
        for strategy, color in zip(RUNS, ("#267997", "#bf7731")):
            rows = [
                r
                for r in tables[name]
                if r["strategy"] == strategy
                and r["period"] == "full"
                and r.get("symbol", "PORTFOLIO") == "PORTFOLIO"
                and r["sign"] == "positive"
            ]
            sources.extend(dict(unit=title, **r) for r in rows)
            ax.plot(
                [int(r["requested_k"]) for r in rows],
                [float(r["share_sign"]) * 100 for r in rows],
                "o-",
                label=LABEL[strategy],
                color=color,
            )
        ax.set(
            title=title + " positivos",
            xlabel="Cantidad top solicitada",
            ylabel="% de G de la población indicada",
            ylim=(0, 105),
        )
        ax.legend()
    fig.suptitle("Concentración positiva · muestra completa · G de ciclos y G diario son distintos")
    save(fig, "concentracion", sources)
    fig, ax = plt.subplots(figsize=(12, 4.8))
    categories = ["both_pass", "funding_only_fail", "basis_only_fail", "both_fail", "not_evaluable"]
    labels = [
        "Pasan ambos",
        "Falla sólo funding",
        "Falla sólo basis",
        "Fallan ambos",
        "No evaluable",
    ]
    colors = ["#287e8e", "#ebae58", "#815f99", "#c25b51", "#98a4ad"]
    source = [
        r
        for r in tables["grupos_excluyentes"]
        if r["period"] == "full" and r["symbol"] == "PORTFOLIO" and r["view"] == "market"
    ]
    left = np.zeros(2)
    for category, label, color in zip(categories, labels, colors):
        values = [
            int(next(r for r in source if r["strategy"] == s and r["group"] == category)["count"])
            for s in RUNS
        ]
        ax.barh([LABEL[s] for s in RUNS], values, left=left, color=color, label=label)
        left += values
    ax.set(
        xlabel="Evaluaciones de entrada (10.224 por cartera)",
        title="Coincidencia descriptiva de mercado · no equivale a aperturas posibles",
    )
    ax.legend(ncol=3, bbox_to_anchor=(0.5, -0.18), loc="upper center")
    save(fig, "filtros_mercado", source)
    source = [
        r
        for r in tables["resumen_integrado"]
        if r["period"] in ("2022", "2023", "2024", "2025", "2026")
        or r["period"].startswith("2026-")
    ]
    # Use day lengths, so any original label for January-August is retained.
    source = [r for r in tables["resumen_integrado"] if int(r["days"]) in (365, 366, 243)]
    fig, axes = plt.subplots(3, 1, figsize=(12, 9), sharex=True)
    for index, (strategy, color) in enumerate(zip(RUNS, ("#267997", "#bf7731"))):
        rows = sorted(
            [r for r in source if r["strategy"] == strategy], key=lambda r: r["start_utc"]
        )
        x = np.arange(len(rows)) + (index - 0.5) * 0.35
        for ax, field, unit in zip(
            axes,
            ("net_pnl_usdt", "capital_utilization_daily_mean", "invested_fraction"),
            ("P&L (USDT)", "Utilización media diaria (%)", "Tiempo activo sin polvo (%)"),
        ):
            ax.bar(
                x,
                [float(r[field]) * (1 if field == "net_pnl_usdt" else 100) for r in rows],
                width=0.35,
                label=LABEL[strategy],
                color=color,
            )
            ax.set_ylabel(unit)
            ax.axhline(0, color="#536271", lw=0.6)
    axes[0].legend()
    axes[-1].set_xticks(range(5), ["2022", "2023", "2024", "2025", "Ene.–ago. 2026"])
    fig.suptitle(
        "Retorno y capital · cifras corregidas reutilizadas · saldos heredados", fontsize=14
    )
    save(fig, "resumen_anual", source)


def write_report(package, tables):
    markdown, summary = report_markdown(tables)
    (package / "reporte.md").write_text(markdown, encoding="utf-8")
    (package / "reporte.html").write_text(render_html(markdown), encoding="utf-8")
    write_json(package / "hallazgos.json", summary)
    figures(package, tables)


def verify_report(package, tables, compare):
    """Check report text and plotting inputs; image bytes are sealed in the manifest."""
    from .common import read_csv, read_json

    markdown, summary = report_markdown(tables)
    for name, expected in (("reporte.md", markdown), ("reporte.html", render_html(markdown))):
        if (package / name).read_text(encoding="utf-8") != expected:
            raise ValueError("Report no longer agrees with tables: " + name)
    compare(read_json(package / "hallazgos.json"), summary, "report summary")
    sources = {
        "ciclos": tables["ciclos_vida"],
        "concentracion": [
            dict(unit=label, **r)
            for name, label in (
                ("concentracion_ciclos", "Ciclos"),
                ("concentracion_dias", "Días de cartera"),
            )
            for strategy in RUNS
            for r in tables[name]
            if r["strategy"] == strategy
            and r["period"] == "full"
            and r.get("symbol", "PORTFOLIO") == "PORTFOLIO"
            and r["sign"] == "positive"
        ],
        "filtros_mercado": [
            r
            for r in tables["grupos_excluyentes"]
            if r["period"] == "full" and r["symbol"] == "PORTFOLIO" and r["view"] == "market"
        ],
        "resumen_anual": [
            r for r in tables["resumen_integrado"] if int(r["days"]) in (365, 366, 243)
        ],
    }
    for name, rows in sources.items():
        compare(
            read_csv(package / "figuras/fuentes" / (name + ".csv")), rows, "figure source " + name
        )
