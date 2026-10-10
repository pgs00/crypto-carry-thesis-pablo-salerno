"""Plot persisted daily equities and reconciled P&L with Spanish labels."""

from datetime import datetime

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.ticker import FuncFormatter

COLORS = {"conditional": "#2864a8", "permanent": "#14846f"}
NAMES = {"conditional": "Condicional", "permanent": "Permanente"}
MONTHS = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


def number(value, decimals=0):
    return f"{value:,.{decimals}f}".replace(",", "_").replace(".", ",").replace("_", ".")


def save(figure, folder, stem):
    figure.savefig(folder / (stem + ".png"), dpi=300, facecolor="white")
    figure.savefig(folder / (stem + ".svg"), metadata={"Date": None}, facecolor="white")
    plt.close(figure)


def figures(destination, results, components, daily):
    folder = destination / "figuras"
    folder.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 12,
            "axes.titlesize": 14,
            "axes.labelsize": 12,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "svg.fonttype": "none",
            "svg.hashsalt": "entrega3-20260919",
        }
    )
    figure, axes = plt.subplots(1, 2, figsize=(13.6, 5.8))
    figure.subplots_adjust(left=0.08, right=0.98, bottom=0.26, top=0.78, wspace=0.27)
    figure.suptitle("Evolución del capital por ventana", fontsize=18, x=0.08, ha="left", y=0.96)
    for axis, window in zip(axes, ("early", "late")):
        for strategy in ("conditional", "permanent"):
            rows = sorted(
                [r for r in daily if r["ventana"] == window and r["estrategia"] == strategy],
                key=lambda r: r["time_ns"],
            )
            result = next(
                r for r in results if r["ventana"] == window and r["estrategia"] == strategy
            )
            # The initial point is the configured opening balance, not interpolated history.
            dates = [datetime.fromisoformat(result["inicio_utc"])] + [
                datetime.fromisoformat(r["instante_utc"]) for r in rows
            ]
            values = [float(result["capital_inicial_usdt"])] + [
                float(r["equity_usdt"]) for r in rows
            ]
            axis.plot(dates, values, color=COLORS[strategy], lw=2.1, label=NAMES[strategy])
        axis.axhline(10000, color="#777777", linestyle=":", lw=1, zorder=0)
        axis.set_title("2022–2023" if window == "early" else "2025–2026", loc="left", pad=12)
        axis.set_ylabel("Equity (USDT)")
        axis.set_xlabel("Fecha (UTC)", labelpad=10)
        axis.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
        axis.xaxis.set_major_formatter(
            FuncFormatter(
                lambda x, _: (
                    f"{MONTHS[mdates.num2date(x).month - 1]} {mdates.num2date(x).year % 100:02d}"
                )
            )
        )
        axis.yaxis.set_major_formatter(FuncFormatter(lambda y, _: number(y)))
        axis.grid(axis="y", color="#e4e7ea", lw=0.7)
        axis.margins(x=0.01, y=0.08)
    figure.legend(
        *axes[0].get_legend_handles_labels(),
        loc="lower left",
        bbox_to_anchor=(0.07, 0.10),
        frameon=False,
        ncol=2,
        fontsize=12,
    )
    figure.text(
        0.08,
        0.065,
        "Capital inicial: 10.000 USDT por cartera. Reinicio independiente en cada ventana.",
        fontsize=11,
    )
    figure.text(
        0.08,
        0.023,
        "365 cierres diarios por cartera. Escalas verticales diferentes. Escenario principal: vwap_joint.",
        fontsize=11,
        color="#444444",
    )
    save(figure, folder, "equity_comparativa")

    figure, axis = plt.subplots(figsize=(12.6, 6.3))
    figure.subplots_adjust(left=0.09, right=0.97, bottom=0.22, top=0.75)
    figure.suptitle("Componentes del resultado neto", fontsize=18, x=0.09, ha="left", y=0.96)
    ordered = [
        next(r for r in components if r["ventana"] == w and r["estrategia"] == s)
        for w in ("early", "late")
        for s in ("conditional", "permanent")
    ]
    x = np.arange(4)
    positive, negative = np.zeros(4), np.zeros(4)
    values = [
        ("Resultado por precios", "#2864a8", [float(r["precios_usdt"]) for r in ordered]),
        ("Funding", "#14846f", [float(r["funding_usdt"]) for r in ordered]),
        (
            "Costos",
            "#c26b4b",
            [float(r["comisiones_usdt"]) + float(r["liquidaciones_usdt"]) for r in ordered],
        ),
    ]
    for label, color, amounts in values:
        amounts = np.array(amounts)
        axis.bar(
            x,
            amounts,
            bottom=np.where(amounts >= 0, positive, negative),
            width=0.55,
            color=color,
            label=label,
        )
        positive += np.maximum(amounts, 0)
        negative += np.minimum(amounts, 0)
    nets = [float(r["beneficio_equity_usdt"]) for r in ordered]
    axis.scatter(x, nets, color="#171a20", marker="D", s=48, label="Neto", zorder=5)
    for place, net in zip(x, nets):
        axis.annotate(
            number(net, 2),
            (place, net),
            xytext=(21, 10),
            textcoords="offset points",
            fontsize=12,
            fontweight="bold",
            bbox=dict(facecolor="white", edgecolor="none", alpha=0.85, pad=1.5),
        )
    axis.set_xticks(
        x,
        [
            f"{'2022–2023' if r['ventana'] == 'early' else '2025–2026'}\n{NAMES[r['estrategia']]}"
            for r in ordered
        ],
    )
    axis.set_ylabel("P&L (USDT)")
    axis.yaxis.set_major_formatter(FuncFormatter(lambda y, _: number(y)))
    axis.axhline(0, color="#666666", lw=0.8)
    axis.grid(axis="y", color="#e4e7ea", lw=0.7, zorder=0)
    axis.set_axisbelow(True)
    figure.legend(
        *axis.get_legend_handles_labels(),
        loc="upper left",
        bbox_to_anchor=(0.08, 0.88),
        ncol=4,
        frameon=False,
        fontsize=11,
    )
    figure.text(
        0.09,
        0.075,
        "Precios = P&L spot + futuros. Costos = comisiones y liquidaciones, con signo negativo.",
        fontsize=11,
    )
    figure.text(
        0.09,
        0.028,
        "El slippage ya está incorporado en los precios; no se descuenta nuevamente. Sin cierre final forzado.",
        fontsize=11,
        color="#444444",
    )
    save(figure, folder, "pnl_comparativo")
