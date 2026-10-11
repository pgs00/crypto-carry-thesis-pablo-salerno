"""Readable comparison and static scientific figures from verified tables."""

from datetime import datetime

from scripts.return_capital.common import number, read_csv, write_csv, write_json
from scripts.return_capital.report import fmt, md_table, render_html

LABEL = {
    "conditional": "Carry condicional neto",
    "permanent": "Carry permanente neto",
    "sofr": "SOFR hipotética bruta",
}
COLOR = {"conditional": "#267997", "permanent": "#bf7731", "sofr": "#39467e"}


def period_label(value):
    return {"full": "Muestra completa", "2026": "Ene.–ago. 2026", "2024+": "2024–ago. 2026"}.get(
        value, value
    )


def figure_sources(tables):
    return dict(
        capital=tables["saldos_alineados"],
        resultados_anuales=[r for r in tables["comparacion_periodos"] if r["period"].isdigit()],
        control_index=tables["control_sofr_index"],
    )


def report_markdown(tables, audit):
    rows = tables["comparacion_periodos"]
    full = {r["portfolio"]: r for r in rows if r["period"] == "full"}
    diff = {r["carry_strategy"]: r for r in tables["diferencias_periodos"] if r["period"] == "full"}
    b = full["sofr"]

    def performance(selected):
        return md_table(
            ["Período", "Cuenta", "Saldo inicial", "Saldo final", "P&L", "Retorno", "CAGR365"],
            [
                [
                    period_label(r["period"]),
                    LABEL[r["portfolio"]],
                    fmt(r["opening_balance"]),
                    fmt(r["closing_balance"]),
                    fmt(r["pnl"]),
                    fmt(r["net_return"], True, 3),
                    fmt(r["cagr365"], True, 3),
                ]
                for r in selected
            ],
        )

    capital = [r for r in rows if r["portfolio"] != "sofr" and r["period"].isdigit()]
    text = [
        "# Carry y cuenta SOFR hipotética bruta",
        "",
        "Comparación aprobada sobre [01/01/2022, 01/09/2026) UTC: 1.704 días, "
        "con 10.000 iniciales en cada cuenta independiente. Las cifras carry son netas de los "
        "costos modelados y están expresadas en USDT. La cuenta SOFR es hipotética bruta en USD. "
        "La comparación nominal supone 1 USDT = 1 USD durante toda la muestra.",
        "",
        "[Aprobación](documentos/aprobacion.md) · [Protocolo](documentos/protocolo.md) · "
        "[Fuentes y lectura](documentos/mapa_fuentes.md) · [Verificación y reproducción](README.md)",
        "",
        "## Resultado de la cuenta completa",
        "",
        f"SOFR termina en **{fmt(b['closing_balance'])} USD**, con intereses de **{fmt(b['pnl'])} USD**, "
        f"retorno **{fmt(b['net_return'], True, 3)}** y CAGR365 **{fmt(b['cagr365'], True, 3)}**. "
        "Estos resultados se interpretan después de validar el calendario, el comienzo inhábil "
        "y los contrastes con el Index. No se reinicia el capital al comenzar un año.",
        "",
        performance([r for r in rows if r["period"] == "full"]),
        "",
        f"La diferencia de P&L carry menos SOFR es {fmt(diff['conditional']['pnl_carry_minus_sofr_nominal'])} "
        f"para la condicional y {fmt(diff['permanent']['pnl_carry_minus_sofr_nominal'])} para la permanente, "
        "en unidades nominales comparadas. Son diferencias descriptivas entre cuentas completas. "
        "No miden un beneficio causal recuperable remunerando caja, ni rendimiento por unidad de "
        "riesgo o de capital desplegado.",
        "",
        "![Capital acumulado, con las tres cuentas independientes y la paridad nominal aprobada](figuras/capital.png)",
        "",
        "## Años y saldos heredados",
        "",
        "Los saldos iniciales son los efectivamente heredados por cada cuenta. 2026 abarca sólo "
        "enero–agosto (243 días); 2024 tiene 366 días. Las sumas de P&L anuales reconcilian con el "
        "total; los retornos anuales no se suman. Los P&L de años posteriores usan bases de capital distintas.",
        "",
        performance([r for r in rows if r["period"].isdigit()]),
        "",
        "En esta muestra, la permanente supera el retorno SOFR en 2024; el resto de sus años "
        "queda por debajo. La condicional queda por debajo en los cinco cortes anuales. Es una "
        "descripción histórica bajo las convenciones aprobadas, sin extrapolación ni garantía.",
        "",
        "![P&L y retorno por año, con 2026 limitado a enero–agosto](figuras/resultados_anuales.png)",
        "",
        "## Cortes ya utilizados por el estudio",
        "",
        performance([r for r in rows if r["period"] in {"2022-2023", "2024+"}]),
        "",
        "Se conservan los mismos cortes de H3 como ventanas de comparación. El saldo al "
        "01/01/2024 cae dentro de un bloque inhábil y conserva principal e interés pendiente. "
        "Ese corte no capitaliza antes del próximo hábil y no modifica H3 ni sus hipótesis.",
        "",
        "## Capital utilizado y H2: resultados vigentes reutilizados",
        "",
        md_table(
            [
                "Período",
                "Carry neto",
                "Capital desplegado medio (USDT)",
                "Utilización media diaria",
                "Tiempo activo sin polvo",
            ],
            [
                [
                    period_label(r["period"]),
                    LABEL[r["portfolio"]],
                    fmt(r["capital_deployed_usdt_daily_mean"]),
                    fmt(r["capital_utilization_daily_mean"], True, 3),
                    fmt(r["invested_fraction"], True, 3),
                ]
                for r in capital
            ],
        ),
        "",
        f"En toda la muestra, la utilización media diaria vigente es "
        f"{fmt(full['conditional']['capital_utilization_daily_mean'], True, 3)} en la condicional y "
        f"{fmt(full['permanent']['capital_utilization_daily_mean'], True, 3)} en la permanente. "
        "Se transcriben las cifras de la corrección vigente: no se vuelve a calcular exposición "
        "ni restricciones. El capital utilizado es informativo y no reemplaza al patrimonio "
        "como denominador del retorno de cartera.",
        "",
        "[Métricas carry originales](reutilizado/metricas_reutilizadas.csv), "
        "[diarios originales](reutilizado/diario_reutilizado.csv) y "
        "[H2 original](reutilizado/h2_reutilizado.csv) son copias byte a byte del paquete previo. "
        "La permanente sigue siendo el comparador de H2; el Sharpe carry mantiene RF=0. "
        "El Sharpe condicional de 2022 sigue ND por volatilidad muestral cero. No se calcula "
        "Sharpe para esta cuenta SOFR ni se infiere riesgo nulo de su suavidad contable.",
        "",
        "## Verificaciones del calendario y la composición",
        "",
        f"Se verificaron {audit['observed_business_dates']} fechas hábiles observadas entre 30/12/2021 "
        f"y 01/09/2026 contra {audit['calendar_days']} fechas calendario. Las 53 ausencias de días "
        "de semana corresponden a 51 cierres completos SIFMA y dos excepciones NY Fed. "
        "No quedaron faltantes hábiles inexplicados, duplicados ni observaciones en inhábiles. "
        "Un faltante detiene el cálculo y no se arrastra automáticamente una tasa.",
        "",
        "Se distinguen el [archivo histórico SIFMA](https://www.sifma.org/resources/general/us-holiday-archive) "
        "y su [calendario 2026](https://www.sifma.org/resources/general/holiday-schedule). "
        "Los cierres tempranos conservan SOFR salvo aviso específico. El NY Fed exceptuó "
        "[07/04/2023](https://www.newyorkfed.org/markets/opolicy/operating_policy_230308a) y "
        "[03/04/2026](https://www.newyorkfed.org/markets/opolicy/operating_policy_260312a), "
        "y mantuvo publicación para [09/01/2025](https://www.newyorkfed.org/markets/opolicy/operating_policy_250102). "
        "31/12/2021 fue cierre temprano, por lo que su tasa es una observación válida.",
        "",
        "El tramo inicial usa exactamente 0,05% anual del 31/12 sólo durante 01/01–03/01: "
        "10.000 × (0,05/100) × 2/360 = **1/36 USD**. El bloque fuente abarca tres días; "
        "la cuenta sólo participa en dos. El primer cierre devenga 1/72 USD. No hay índice "
        "oficial inventado para el sábado ni cociente de tres días aplicado a ese tramo.",
        "",
        f"Los {audit['business_blocks']} bloques se delimitan por hábiles consecutivos, aunque "
        f"tengan igual tasa. Los {audit['index_checks']} contrastes posteriores al 03/01/2022 "
        "incluyen cada bloque y cada acumulación desde ese anclaje hasta 01/09/2026. Todos "
        "son compatibles con los intervalos derivados de los ocho decimales publicados del "
        "[SOFR Index oficial](https://markets.newyorkfed.org/api/rates/secured/sofrai/search.json?startDate=2021-12-30&endDate=2026-09-01). "
        "No se ampliaron tolerancias para lograr coincidencia. La tabla guarda factor calculado, "
        "cociente publicado, error y ambos límites para cada control.",
        "",
        "![Error de composición frente al cociente Index y sus límites de redondeo publicados](figuras/control_index.png)",
        "",
        "## Convenciones, alcance y límites",
        "",
        "**ACT/360 devenga intereses; CAGR365 anualiza rendimientos.** Un bloque de n días usa "
        "1 + r×n/360 y capitaliza al siguiente hábil; dentro del bloque el interés es simple. "
        "CAGR = (saldo final/saldo inicial)^(365/días) − 1. Se cuentan días reales, incluido "
        "29 de febrero. La [metodología NY Fed](https://www.newyorkfed.org/markets/reference-rates/additional-information-about-reference-rates) "
        "sustenta el devengamiento; el mapeo de fechas económicas a días UTC es una convención "
        "explícita del estudio. No se afirma liquidación real a medianoche UTC.",
        "",
        "Cada cierre carry a 23:59:59.999999999 se empareja con el saldo SOFR al término de "
        "ese día. No se agrega un día de interés. Se usa la tasa efectiva 31/08 hasta 01/09; "
        "la tasa efectiva 01/09 queda fuera. Las tasas realizadas se usan retrospectivamente. "
        "La publicación esperada es el siguiente hábil, no la fecha económica; los originales "
        "conservan revisionIndicator, pero no acreditan vintages disponibles en tiempo real.",
        "",
        "SOFR es una referencia hipotética bruta, sin costos añadidos de conversión, custodia, "
        "intermediación, spread o impuestos. No acredita cuenta remunerada accesible, contrato, "
        "mínimo comercial ni producto del NY Fed o Binance. La paridad USDT/USD es un supuesto "
        "nominal, no convertibilidad garantizada ni equivalencia de riesgos. La trayectoria "
        "no mide precios de liquidación ni riesgo de contraparte o liquidez.",
        "",
        "El carry conserva sus resultados netos de costos modelados. No se remunera su caja "
        "ni sus garantías, no se transfieren fondos y no se ejecutan backtests nuevos. "
        "Los diagnósticos de concentración, entrada, exposición y riesgo permanecen en el "
        "paquete anterior, enlazado por hash. Esta comparación no los repite ni valida de "
        "nuevo el motor. El verificador recalcula sólo este postprocesamiento SOFR; comparte "
        "código con el constructor, complementado por fixtures exactos y el contraste Index externo.",
        "",
        "[Todos los períodos](tablas/comparacion_periodos.csv) · "
        "[Diferencias](tablas/diferencias_periodos.csv) · [Cuenta diaria](tablas/cartera_sofr_diaria.csv) · "
        "[Bloques](tablas/bloques_sofr.csv) · [Calendario por fecha](tablas/calendario_verificado.csv) · "
        "[53 ausencias justificadas](tablas/dias_semana_sin_observacion.csv) · "
        "[Control inicial](tablas/control_bloque_inicial.csv) · [Controles Index](tablas/control_sofr_index.csv)",
        "",
    ]
    return "\n".join(text)


def figures(package, tables):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    plt.rcParams.update(
        {
            "font.size": 10,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "savefig.dpi": 180,
            "font.family": "DejaVu Sans",
            "svg.hashsalt": "sofr-approved-v1",
        }
    )
    folder = package / "figuras"
    folder.mkdir()
    sources = figure_sources(tables)

    def save(fig, name):
        fig.tight_layout()
        fig.savefig(folder / (name + ".png"), bbox_inches="tight")
        fig.savefig(folder / (name + ".svg"), bbox_inches="tight", metadata={"Date": None})
        plt.close(fig)
        write_csv(folder / "fuentes" / (name + ".csv"), sources[name])

    source = sources["capital"]
    fig, ax = plt.subplots(figsize=(12, 5.5))
    x = [datetime.fromisoformat(r["boundary_utc"].replace("Z", "+00:00")) for r in source]
    for s in LABEL:
        field = s + ("_usd" if s == "sofr" else "_usdt")
        ax.plot(x, [float(r[field]) for r in source], label=LABEL[s], color=COLOR[s], lw=1.8)
    ax.set(
        title="Capital acumulado · 10.000 iniciales por cuenta",
        ylabel="Saldo nominal (1 USDT = 1 USD)",
        xlabel="Frontera diaria UTC",
    )
    ax.grid(axis="y", alpha=0.2)
    ax.legend(loc="upper left")
    save(fig, "capital")
    source = sources["resultados_anuales"]
    fig, axes = plt.subplots(2, 1, figsize=(12, 7), sharex=True)
    for i, s in enumerate(LABEL):
        selected = sorted([r for r in source if r["portfolio"] == s], key=lambda r: r["start_utc"])
        x = np.arange(len(selected)) + (i - 1) * 0.25
        for ax, field, scale, label in (
            (axes[0], "pnl", 1, "P&L nominal"),
            (axes[1], "net_return", 100, "Retorno del período (%)"),
        ):
            ax.bar(
                x,
                [float(r[field]) * scale for r in selected],
                width=0.24,
                label=LABEL[s],
                color=COLOR[s],
            )
            ax.set_ylabel(label)
            ax.axhline(0, color="#627481", lw=0.6)
            ax.grid(axis="y", alpha=0.2)
    axes[0].margins(y=0.18)
    axes[0].legend(ncol=3, fontsize=9, loc="upper left")
    axes[1].set_xticks(range(5), ["2022", "2023", "2024", "2025", "Ene.–ago. 2026"])
    fig.suptitle(
        "Resultados anuales · carry neto de costos modelados y SOFR hipotética bruta\nSaldos heredados · 1 USDT = 1 USD",
        fontsize=13,
    )
    save(fig, "resultados_anuales")
    fig, axes = plt.subplots(2, 1, figsize=(12, 7), sharex=True)
    for ax, scope, label in zip(
        axes,
        ("business_block", "cumulative_from_anchor"),
        ("Cada bloque hábil", "Acumulado desde 03/01/2022"),
    ):
        selected = [r for r in sources["control_index"] if r["scope"] == scope]
        x = [datetime.fromisoformat(r["end"]) for r in selected]
        lo = [
            float(number(r["factor_lower_from_rounding"]) - number(r["published_ratio"])) * 1e9
            for r in selected
        ]
        hi = [
            float(number(r["factor_upper_from_rounding"]) - number(r["published_ratio"])) * 1e9
            for r in selected
        ]
        y = [float(r["signed_error_vs_published_ratio"]) * 1e9 for r in selected]
        ax.fill_between(x, lo, hi, color="#d7e2eb", label="Límites del redondeo publicado")
        ax.scatter(x, y, s=3, color=COLOR["sofr"], label="Factor calculado − cociente Index")
        ax.set(title=label, ylabel="Error del factor × 10⁹")
        ax.axhline(0, color="#627481", lw=0.6)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, ncol=2, fontsize=9, loc="lower center", bbox_to_anchor=(0.5, -0.03))
    axes[-1].set_xlabel("Fecha hábil de cierre")
    fig.suptitle("SOFR Index · control sin ampliar tolerancias", fontsize=14)
    save(fig, "control_index")


def write_report(package, tables, audit):
    markdown = report_markdown(tables, audit)
    (package / "reporte.md").write_text(markdown, encoding="utf-8")
    (package / "reporte.html").write_text(render_html(markdown), encoding="utf-8")
    write_json(
        package / "hallazgos.json",
        [r for r in tables["comparacion_periodos"] if r["period"] == "full"],
    )
    figures(package, tables)


def verify_report(package, tables, audit, compare):
    from scripts.return_capital.common import read_json

    markdown = report_markdown(tables, audit)
    for name, expected in (("reporte.md", markdown), ("reporte.html", render_html(markdown))):
        if (package / name).read_text(encoding="utf-8") != expected:
            raise ValueError("Report differs from verified tables: " + name)
    compare(
        read_json(package / "hallazgos.json"),
        [r for r in tables["comparacion_periodos"] if r["period"] == "full"],
        "headline results",
    )
    for name, expected in figure_sources(tables).items():
        compare(
            read_csv(package / "figuras/fuentes" / (name + ".csv")),
            expected,
            "figure source " + name,
        )
