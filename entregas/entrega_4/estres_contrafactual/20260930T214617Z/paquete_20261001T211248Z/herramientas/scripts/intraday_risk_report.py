"""Render the new intraday evidence package without changing financial inputs."""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

if __package__:
    from .intraday_risk_tables import incident_exposure_mask
else:
    from intraday_risk_tables import incident_exposure_mask

DAY = 86_400_000_000_000
MINUTE = 60_000_000_000
SYMBOLS = ("BTCUSDT", "ETHUSDT")
ORIGINAL = "original_reconstructed"
PROXY = "valoracion_proxy_hipotetica"
YEARS = ("2022", "2023", "2024", "2025", "2026")
PERIODS = ("full", "2022-2023", "2024+", *YEARS)
BLUE, ORANGE, GREY, GREEN = "#17618c", "#cb6530", "#7c8790", "#23806b"
COLORS = (BLUE, ORANGE, GREEN, "#8666a8")


def sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_csv(path):
    with Path(path).open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path, rows):
    rows = list(rows)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path, value):
    Path(path).write_text(
        json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8"
    )


def number(value):
    try:
        return float(value)
    except TypeError, ValueError:
        return math.nan


def fmt(value, digits=2):
    value = number(value)
    if not math.isfinite(value):
        return "ND"
    return f"{value:,.{digits}f}".replace(",", "@").replace(".", ",").replace("@", ".")


def pct(value, digits=2):
    return fmt(100 * number(value), digits) + "%" if math.isfinite(number(value)) else "ND"


def ns(value):
    return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()) * 1_000_000_000


def iso(value):
    if value is None or value == "" or not math.isfinite(number(value)):
        return "ND"
    value = int(value)
    seconds, nanos = divmod(value, 1_000_000_000)
    return (
        datetime.fromtimestamp(seconds, UTC).strftime("%Y-%m-%d %H:%M:%S")
        + (f".{nanos:09d}" if nanos else "")
        + " UTC"
    )


def dates(times):
    return np.asarray(times, dtype=np.int64).astype("datetime64[ns]")


def identity(row):
    strategy = "Condicional" if row["strategy"] == "conditional" else "Permanente"
    return ("BASE" if row["scenario"] == "BASE_E3" else "MARGEN_2X") + " · " + strategy


def period_label(period):
    return {"full": "Muestra completa", "2024+": "2024–ago. 2026", "2026": "Ene.–ago. 2026"}.get(
        period, period
    )


def policy_label(policy):
    return (
        "Pico reiniciado al saldo real de entrada"
        if policy == "period_reset"
        else "Pico acumulado de toda la trayectoria"
    )


def valuation_label(method):
    return "Original reconstruida" if method == ORIGINAL else "Proxy hipotético de suspensión"


CSS = """
:root{color-scheme:light;--ink:#18334a;--muted:#566674;--line:#dbe3e9}
body{max-width:1180px;margin:0 auto;padding:36px 26px 72px;color:#263641;background:#fff;
font:16px/1.65 system-ui,-apple-system,Segoe UI,sans-serif}h1,h2,h3{color:var(--ink);line-height:1.25}
h1{font-size:2.2rem;margin-bottom:14px}h2{margin-top:48px;border-top:1px solid var(--line);padding-top:24px}
h3{margin-top:32px}p{max-width:1050px}a{color:#126086}code{font-size:.88em;overflow-wrap:anywhere}
.table-wrap{overflow-x:auto;margin:18px 0 25px}table{border-collapse:collapse;width:100%;font-size:.87rem}
th,td{padding:9px 11px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top}
th{background:#edf3f7;color:var(--ink)}tbody tr:nth-child(even){background:#fafcfd}
figure{margin:26px 0 35px}img{width:100%;height:auto;display:block}figcaption{font-size:.85rem;color:var(--muted)}
.lede{font-size:1.08rem;background:#eff5f8;border-left:4px solid #17618c;padding:15px 19px}
.meta{color:var(--muted);font-size:.9rem}ul{padding-left:24px}@media print{body{padding:0;font-size:11px}
h2{break-before:auto}figure,table{break-inside:avoid}a{color:inherit}.table-wrap{overflow:visible}}
"""


class Report:
    def __init__(self, title):
        self.title, self.md, self.body = title, [], []
        self.heading(title, 1)

    def heading(self, text, level=2):
        self.md.extend(["#" * level + " " + text, ""])
        self.body.append(f"<h{level}>{html.escape(text)}</h{level}>")

    def paragraph(self, text, *, lede=False):
        self.md.extend([text, ""])
        self.body.append(f'<p class="{"lede" if lede else ""}">{html.escape(text)}</p>')

    def links(self, text, links):
        self.md.extend([text + " " + " · ".join(f"[{label}]({url})" for label, url in links), ""])
        self.body.append(
            "<p>"
            + html.escape(text)
            + " "
            + " · ".join(
                f'<a href="{html.escape(url, quote=True)}">{html.escape(label)}</a>'
                for label, url in links
            )
            + "</p>"
        )

    def table(self, headers, rows):
        rows = [[str(cell) for cell in row] for row in rows]
        self.md.append("| " + " | ".join(headers) + " |")
        self.md.append("| " + " | ".join("---" for _ in headers) + " |")
        self.md.extend(
            "| " + " | ".join(cell.replace("|", " / ") for cell in row) + " |" for row in rows
        )
        self.md.append("")
        self.body.append(
            '<div class="table-wrap"><table><thead><tr>'
            + "".join(f"<th>{html.escape(cell)}</th>" for cell in headers)
            + "</tr></thead><tbody>"
            + "".join(
                "<tr>" + "".join(f"<td>{html.escape(cell)}</td>" for cell in row) + "</tr>"
                for row in rows
            )
            + "</tbody></table></div>"
        )

    def figure(self, stem, caption):
        path = f"figuras/{stem}.png"
        source = f"figuras/fuentes/{stem}.csv"
        self.md.extend(
            [
                f"![{caption}]({path})",
                "",
                caption,
                f"[Datos de la figura]({source}) · [SVG](figuras/{stem}.svg)",
                "",
            ]
        )
        self.body.append(
            f'<figure><img src="{path}" alt="{html.escape(caption, quote=True)}">'
            f"<figcaption>{html.escape(caption)} "
            f'<a href="{source}">Datos CSV</a> · '
            f'<a href="figuras/{stem}.svg">SVG</a></figcaption></figure>'
        )

    def save(self, package, stem):
        (package / (stem + ".md")).write_text("\n".join(self.md), encoding="utf-8")
        (package / (stem + ".html")).write_text(
            '<!doctype html><html lang="es"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            f"<title>{html.escape(self.title)}</title><style>{CSS}</style></head><body>"
            + "\n".join(self.body)
            + "</body></html>\n",
            encoding="utf-8",
        )


class Figures:
    def __init__(self, package):
        self.package, self.index = package, []
        self.folder = package / "figuras"
        (self.folder / "fuentes").mkdir(parents=True, exist_ok=True)
        plt.rcParams.update(
            {
                "font.family": "DejaVu Sans",
                "font.size": 10,
                "axes.spines.top": False,
                "axes.spines.right": False,
                "axes.titleweight": "bold",
                "axes.labelcolor": "#293d4e",
                "grid.alpha": 0.22,
                "svg.fonttype": "none",
                "savefig.facecolor": "white",
            }
        )

    def save(self, fig, stem, rows, title, sources, *, note="", run_ids=()):
        source_path = self.folder / "fuentes" / (stem + ".csv")
        write_csv(source_path, rows)
        source_records = [{"path": str(path), "sha256": sha256(path)} for path in sources]
        metadata = {
            "title": title,
            "source_run_ids": list(run_ids),
            "sources": source_records,
            "data_csv": source_path.relative_to(self.package).as_posix(),
            "data_sha256": sha256(source_path),
            "time_zone": "UTC",
            "status": "presentation_of_reconstructed_or_reused_evidence",
            "valuation": "original_reconstructed; hypothetical proxy explicitly labelled",
            "note": note,
        }
        write_json(self.folder / "fuentes" / (stem + ".json"), metadata)
        fig.set_layout_engine("constrained", rect=(0, 0.055, 1, 0.945))
        fig.text(
            0.01,
            0.012,
            "Fuente: "
            + ", ".join(Path(path).name for path in sources)
            + " · CSV y procedencia adjuntos · UTC",
            color="#536471",
            fontsize=8,
        )
        fig.savefig(self.folder / (stem + ".png"), dpi=170, bbox_inches="tight")
        fig.savefig(self.folder / (stem + ".svg"), bbox_inches="tight")
        plt.close(fig)
        self.index.append(
            {
                "figure": stem,
                "title": title,
                "source_csv": metadata["data_csv"],
                "run_ids": ";".join(run_ids),
                "note": note,
            }
        )


def load_window(meta, series_root, run_id, lower, upper, columns):
    chunks = []
    for entry in meta["entries"]:
        if (
            entry["run_id"] != run_id
            or entry["start_ns"] > upper
            or entry["end_exclusive_ns"] <= lower
        ):
            continue
        table = pq.ParquetFile(series_root / entry["path"]).read(columns=columns)
        times = table["time_ns"].to_numpy()
        chunks.append(table.filter(pa.array((times >= lower) & (times <= upper))))
    if not chunks:
        raise ValueError(f"No local series for {run_id}: {lower}..{upper}")
    table = pa.concat_tables(chunks)
    return {name: table[name].combine_chunks().to_numpy(zero_copy_only=False) for name in columns}


def chart_rows(values, row, keys, selection=None):
    selection = range(len(values["time_ns"])) if selection is None else selection
    for index in selection:
        result = {
            "run_id": row["run_id"],
            "scenario": row["scenario"],
            "strategy": row["strategy"],
            "time_ns": int(values["time_ns"][index]),
            "timestamp_utc": iso(values["time_ns"][index]),
            "status": "reconstruido",
            "proxy_status": "hipotetico",
        }
        for key in keys:
            value = values[key][index]
            result[key] = value.item() if hasattr(value, "item") else value
        yield result


def format_time_axis(ax, *, hours=False):
    locator = mdates.AutoDateLocator(minticks=4, maxticks=8)
    locator.intervald[mdates.HOURLY] = [1, 2, 3, 4, 6, 8, 12]
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(
        mdates.DateFormatter("%d %b %Y\n%H:%M" if hours else "%d %b %Y", tz=UTC)
    )
    ax.set_xlabel("Fecha y hora UTC" if hours else "Fecha UTC")
    ax.grid(True)


def plot_dd(figures, rows, dd_source):
    selected = [
        row for row in rows if row["period"] == "full" and row["peak_policy"] == "period_reset"
    ]
    original = [row for row in selected if row["valuation"] == ORIGINAL]
    alternatives = {row["run_id"]: row for row in selected if row["valuation"] == PROXY}
    fig, ax = plt.subplots(figsize=(11, 5.2), layout="constrained")
    x, width = np.arange(len(original)), 0.24
    for shift, key, color, label in [
        (-1, "daily", GREY, "Cierres diarios"),
        (0, "original", BLUE, "Intradía · valoración original"),
        (1, "proxy", ORANGE, "Intradía · proxy hipotético"),
    ]:
        values = [
            100
            * number(
                row["daily_drawdown"]
                if key == "daily"
                else (row if key == "original" else alternatives[row["run_id"]])[
                    "intraday_drawdown"
                ]
            )
            for row in original
        ]
        bars = ax.bar(x + shift * width, values, width, color=color, label=label)
        ax.bar_label(bars, labels=[f"{value:.3f}%" for value in values], padding=4, fontsize=9)
    ax.axhline(0, color="#30485c", lw=0.7)
    ax.set_xticks(x, [identity(row).replace(" · ", "\n") for row in original])
    ax.set_ylabel("Drawdown máximo (%) · signo negativo")
    ax.set_title("Riesgo que los cierres diarios no muestran")
    ax.legend(loc="lower left", fontsize=8)
    ax.grid(axis="y")
    ax.margins(y=0.2)
    figures.save(
        fig,
        "drawdown_muestra_completa",
        selected,
        "Drawdown diario, intradía original y proxy hipotético",
        [dd_source],
        note="Misma muestra y capital inicial; minutos más eventos y cierres diarios. No ticks.",
        run_ids=[row["run_id"] for row in original],
    )


def plot_annual(figures, metrics, lookup, sources):
    annual = [row for row in metrics if row["scenario"] == "BASE_E3" and row["period"] in YEARS]
    rows = []
    fig, axes = plt.subplots(3, 2, figsize=(13, 9.6), sharex=True, layout="constrained")
    x = np.arange(5)
    for col, strategy in enumerate(("conditional", "permanent")):
        selected = sorted(
            [row for row in annual if row["strategy"] == strategy], key=lambda r: r["period"]
        )
        axes[0, col].set_title(identity(selected[0]))
        axes[0, col].bar(x, [100 * number(r["net_return"]) for r in selected], color=BLUE)
        axes[0, col].set_ylabel("Retorno del período (%)")
        axes[1, col].plot(
            x,
            [100 * number(r["capital_utilization_daily_mean"]) for r in selected],
            "o-",
            color=BLUE,
            label="Media diaria",
        )
        axes[1, col].plot(
            x,
            [100 * number(r["capital_utilization_daily_max"]) for r in selected],
            "s--",
            color=GREY,
            label="Máxima diaria",
        )
        axes[1, col].set_ylabel("Capital utilizado / equity (%)")
        for method, field, color, style, label in [
            (ORIGINAL, "daily_drawdown", GREY, "o--", "Diario"),
            (ORIGINAL, "intraday_drawdown", BLUE, "o-", "Intradía original"),
            (PROXY, "intraday_drawdown", ORANGE, "s:", "Intradía proxy hipotético"),
        ]:
            axes[2, col].plot(
                x,
                [
                    100 * number(lookup[(r["run_id"], r["period"], "period_reset", method)][field])
                    for r in selected
                ],
                style,
                color=color,
                label=label,
            )
        axes[2, col].set_ylabel("Drawdown del período (%)")
        axes[2, col].set_xticks(x, ["2022", "2023", "2024", "2025", "2026*"], rotation=0)
        for ax in axes[:, col]:
            ax.axhline(0, color="#30485c", lw=0.6)
            ax.grid(axis="y")
        axes[1, col].legend(fontsize=8)
        axes[2, col].legend(fontsize=8)
        for row in selected:
            data = dict(row, status="reutilizado_con_riesgo_reconstruido")
            for method in (ORIGINAL, PROXY):
                dd = lookup[(row["run_id"], row["period"], "period_reset", method)]
                data[method + "_intraday_drawdown"] = dd["intraday_drawdown"]
                data[method + "_daily_drawdown"] = dd["daily_drawdown"]
            rows.append(data)
    fig.suptitle(
        "Retorno, capital utilizado y riesgo anual · BASE\n*2026: enero–agosto, ocho meses",
        fontsize=14,
    )
    figures.save(
        fig,
        "resumen_anual_base",
        rows,
        "Resumen anual BASE",
        sources,
        note="Retorno parcial 2026 sin equipararlo a doce meses; DD con pico reiniciado al saldo real.",
        run_ids=sorted({row["run_id"] for row in rows}),
    )


def march_figures(figures, package, base_runs):
    source = package / "evidencia/marzo_2023.parquet"
    needed = ["run_id", "time_ns", "sequence", "phase", "equity_usdt", "equity_proxy_usdt"]
    needed += [
        f"{symbol}_{key}"
        for symbol in SYMBOLS
        for key in (
            "spot",
            "short",
            "spot_price",
            "spot_proxy",
            "spot_age_ns",
            "mark_price",
            "net_exposure_usdt",
            "maintenance_usdt",
            "margin_balance_usdt",
            "headroom_usdt",
        )
    ]
    table = pq.ParquetFile(source).read(columns=needed)
    results = []
    full_fig, full_axes = plt.subplots(2, 1, figsize=(12, 7.4), sharex=True, layout="constrained")
    full_rows = []
    for run, ax in zip(base_runs, full_axes):
        part = table.filter(pa.array(np.asarray(table["run_id"]) == run["run_id"]))
        values = {
            name: part[name].combine_chunks().to_numpy(zero_copy_only=False)
            for name in needed
            if name != "run_id"
        }
        t = dates(values["time_ns"])
        ax.plot(t, values["equity_usdt"], color=BLUE, label="Valoración original")
        ax.plot(t, values["equity_proxy_usdt"], color=ORANGE, ls="--", label="Proxy hipotético")
        ax.axvspan(
            dates([ns("2023-03-24T11:28:00Z")])[0],
            dates([ns("2023-03-24T14:01:00Z")])[0],
            color=ORANGE,
            alpha=0.12,
        )
        ax.set_title(identity(run))
        ax.set_ylabel("Equity (USDT)")
        ax.legend(fontsize=8)
        format_time_axis(ax, hours=True)
        full_rows.extend(
            chart_rows(values, run, ["sequence", "phase", "equity_usdt", "equity_proxy_usdt"])
        )
        lower, upper = ns("2023-03-24T10:30:00Z"), ns("2023-03-24T15:30:00Z")
        select = (values["time_ns"] >= lower) & (values["time_ns"] <= upper)
        view = {key: value[select] for key, value in values.items()}
        when = dates(view["time_ns"])
        fig, axes = plt.subplots(4, 1, figsize=(12, 11), sharex=True, layout="constrained")
        axes[0].plot(when, view["equity_usdt"], color=BLUE, label="Original: spot arrastrado")
        axes[0].plot(
            when, view["equity_proxy_usdt"], color=ORANGE, ls="--", label="Proxy hipotético"
        )
        axes[0].set_ylabel("Equity (USDT)")
        axes[0].set_title(identity(run) + " · suspensión spot del 24/03/2023")
        anchor_time = ns("2023-03-24T11:28:00Z")
        for symbol, color in zip(SYMBOLS, (BLUE, GREEN)):
            anchor_index = np.searchsorted(view["time_ns"], anchor_time, side="right") - 1
            anchor = view[symbol + "_spot_price"][anchor_index]
            axes[1].plot(
                when,
                100 * view[symbol + "_spot_price"] / anchor,
                color=color,
                label=symbol[:3] + " spot original",
            )
            axes[1].plot(
                when,
                100 * view[symbol + "_spot_proxy"] / anchor,
                color=color,
                ls="--",
                label=symbol[:3] + " proxy hipotético",
            )
            axes[2].plot(when, view[symbol + "_net_exposure_usdt"], color=color, label=symbol[:3])
            axes[3].plot(when, view[symbol + "_maintenance_usdt"], color=color, label=symbol[:3])
        axes[1].set_ylabel("Spot / ancla 11:28 = 100")
        axes[2].set_ylabel("Exposición neta (USDT)")
        axes[3].set_ylabel("Mantenimiento (USDT)")
        for axis in axes:
            axis.axvspan(
                dates([anchor_time])[0],
                dates([ns("2023-03-24T14:01:00Z")])[0],
                color=ORANGE,
                alpha=0.10,
            )
            axis.axvline(dates([ns("2023-03-24T12:00:00Z")])[0], color=GREY, lw=0.8, ls=":")
            axis.legend(fontsize=8, loc="best", ncol=2)
            axis.grid(True)
        format_time_axis(axes[-1], hours=True)
        stem = "marzo_detalle_" + run["strategy"]
        keys = [key for key in view if key != "time_ns"]
        figures.save(
            fig,
            stem,
            chart_rows(view, run, keys),
            "Detalle suspensión " + identity(run),
            [source],
            note="Sombreado: spot sin observación nueva; línea 12:00: referencia del tramo descubierto. Posiciones originales.",
            run_ids=[run["run_id"]],
        )
        gap = (values["time_ns"] > anchor_time) & (values["time_ns"] < ns("2023-03-24T14:01:00Z"))
        differences = values["equity_proxy_usdt"] - values["equity_usdt"]
        i = np.flatnonzero(gap)[np.argmin(differences[gap])]
        results.append(
            {
                "run_id": run["run_id"],
                "scenario": run["scenario"],
                "strategy": run["strategy"],
                "maximum_proxy_valuation_reduction_usdt": float(-differences[i]),
                "time_ns": int(values["time_ns"][i]),
                "timestamp_utc": iso(values["time_ns"][i]),
                "original_equity_at_difference": float(values["equity_usdt"][i]),
                "proxy_equity_at_difference": float(values["equity_proxy_usdt"][i]),
                "source": "evidencia/marzo_2023.parquet",
                "status": "hipotetico",
            }
        )
    full_fig.suptitle("Antes, durante y después · 23–25 de marzo de 2023", fontsize=14)
    figures.save(
        full_fig,
        "marzo_tres_dias",
        full_rows,
        "Suspensión: ventana de tres días",
        [source],
        note="La diferencia es de valoración sobre estados originales; no representa operaciones adicionales.",
        run_ids=[row["run_id"] for row in base_runs],
    )
    return results


def envelope_indices(times, equity, threshold=14000):
    if len(times) <= threshold:
        return np.arange(len(times))
    buckets = times // DAY
    indices = {0, len(times) - 1}
    for bucket in np.unique(buckets):
        lo, hi = np.searchsorted(buckets, bucket, "left"), np.searchsorted(buckets, bucket, "right")
        indices.update(
            (
                int(lo),
                int(hi - 1),
                int(lo + np.argmin(equity[lo:hi])),
                int(lo + np.argmax(equity[lo:hi])),
            )
        )
    return np.array(sorted(indices))


def extrema_figures(figures, package, series_root, meta, runs, dd_lookup, points):
    descriptions = []
    for run in runs:
        run_id = run["run_id"]
        dd = dd_lookup[(run_id, "full", "period_reset", ORIGINAL)]
        peak, trough = int(dd["intraday_peak_time_ns"]), int(dd["intraday_trough_time_ns"])
        recovery = dd.get("intraday_recovery_time_ns")
        end = int(recovery) if recovery else trough + DAY
        end = min(end, max(entry["end_exclusive_ns"] for entry in meta["entries"]) - 1)
        values = load_window(
            meta,
            series_root,
            run_id,
            peak,
            max(end, peak + MINUTE),
            ["time_ns", "sequence", "equity_usdt"],
        )
        values["drawdown_from_selected_peak"] = (
            values["equity_usdt"]
            / np.maximum.accumulate(
                np.maximum(values["equity_usdt"], number(dd["intraday_peak_equity"]))
            )
            - 1
        )
        select = envelope_indices(values["time_ns"], values["equity_usdt"])
        fig, axes = plt.subplots(2, 1, figsize=(11.5, 6.8), sharex=True, layout="constrained")
        dates_selected = dates(values["time_ns"][select])
        axes[0].plot(dates_selected, values["equity_usdt"][select], color=BLUE, lw=1)
        axes[0].axhline(
            number(dd["intraday_peak_equity"]), color=GREY, ls=":", label="Pico seleccionado"
        )
        axes[0].scatter(
            dates([trough]),
            [number(dd["intraday_trough_equity"])],
            color=ORANGE,
            zorder=5,
            label="Valle",
        )
        axes[0].set_title(identity(run) + " · mayor drawdown original")
        axes[0].set_ylabel("Equity (USDT)")
        axes[0].legend(fontsize=8)
        axes[1].plot(
            dates_selected, 100 * values["drawdown_from_selected_peak"][select], color=BLUE
        )
        axes[1].set_ylabel("Drawdown (%)")
        for axis in axes:
            axis.grid(True)
        format_time_axis(axes[-1], hours=(end - peak) < 4 * DAY)
        stem = "peor_drawdown_" + run_id
        sample_note = (
            "Puntos originales completos"
            if len(select) == len(values["time_ns"])
            else "Envolvente diaria: primero, último, mínimo y máximo en su orden temporal; las métricas proceden de la tabla completa"
        )
        figures.save(
            fig,
            stem,
            chart_rows(
                values, run, ["sequence", "equity_usdt", "drawdown_from_selected_peak"], select
            ),
            "Peor drawdown " + identity(run),
            [package / "series_locales.json", package / "tablas/drawdown_comparativo.csv"],
            note=sample_note,
            run_ids=[run_id],
        )
        candidates = [
            (row, symbol)
            for row in points
            for symbol in SYMBOLS
            if row["run_id"] == run_id and row["label"] == "full_min_headroom_" + symbol
        ]
        selected, symbol = min(
            candidates, key=lambda pair: number(pair[0][pair[1] + "_headroom_usdt"])
        )
        center = int(selected["time_ns"])
        center_day = (center // DAY) * DAY
        requested_lower, requested_upper = center_day - DAY, center_day + 2 * DAY - 1
        run_entries = [entry for entry in meta["entries"] if entry["run_id"] == run_id]
        lower = max(requested_lower, min(entry["start_ns"] for entry in run_entries))
        upper = min(requested_upper, max(entry["end_exclusive_ns"] for entry in run_entries) - 1)
        margin_window_note = (
            "Tres días calendario UTC: día anterior, día del mínimo y día posterior. "
            f"Intervalo solicitado inclusivo: {iso(requested_lower)} a {iso(requested_upper)}. "
        )
        if lower != requested_lower or upper != requested_upper:
            margin_window_note += (
                f"Truncado a los límites disponibles de la muestra: {iso(lower)} a {iso(upper)}. "
            )
        else:
            margin_window_note += "Sin truncamiento por límites de la muestra. "
        keys = [
            "time_ns",
            "sequence",
            "phase",
            "free_cash_usdt",
            "redistributable_cash_usdt",
            "preventive_need_joint_infimum_usdt",
            "preventive_joint_strict",
            "preventive_external_lower_bound_usdt",
            "preventive_external_upper_bound_usdt",
            "reservations_available_known",
        ]
        keys += [
            symbol + "_" + key
            for key in (
                "short",
                "collateral",
                "mark_price",
                "maintenance_usdt",
                "margin_balance_usdt",
                "headroom_usdt",
                "margin_ratio",
                "liquidation_distance",
            )
        ]
        state = load_window(meta, series_root, run_id, lower, upper, keys)
        when = dates(state["time_ns"])
        active = state[symbol + "_short"] > 0
        fig, axes = plt.subplots(3, 1, figsize=(11.5, 8.6), sharex=True, layout="constrained")
        for field, color, label in [
            ("margin_balance_usdt", BLUE, "Saldo de margen"),
            ("maintenance_usdt", ORANGE, "Mantenimiento"),
        ]:
            axes[0].plot(
                when,
                np.where(active, state[symbol + "_" + field], np.nan),
                color=color,
                label=label,
            )
        axes[0].set_title(identity(run) + " · menor holgura aislada · " + symbol)
        axes[0].set_ylabel("USDT · corto abierto")
        axes[1].plot(
            when,
            100 * state[symbol + "_margin_ratio"],
            color=ORANGE,
            label="Ratio mantenimiento / saldo",
        )
        axes[1].plot(
            when,
            100 * state[symbol + "_liquidation_distance"],
            color=BLUE,
            label="Distancia a liquidación",
        )
        axes[1].axhline(50, color=ORANGE, ls=":", lw=0.8, label="Umbral ratio: 50%")
        axes[1].axhline(15, color=BLUE, ls=":", lw=0.8, label="Umbral distancia: 15%")
        axes[1].set_ylabel("Porcentaje (%)")
        for field, color, style, label in [
            ("free_cash_usdt", GREY, ":", "Caja bruta"),
            ("redistributable_cash_usdt", GREEN, "-", "Caja redistribuible acreditada"),
            (
                "preventive_need_joint_infimum_usdt",
                ORANGE,
                "-",
                "Necesidad preventiva conjunta (ínfimo)",
            ),
        ]:
            axes[2].plot(when, state[field], color=color, ls=style, label=label)
        axes[2].set_ylabel("USDT · cartera")
        for axis in axes:
            axis.axvline(dates([center])[0], color=GREY, lw=0.7, ls="--")
            axis.grid(True)
            axis.legend(fontsize=8, ncol=2)
        format_time_axis(axes[-1], hours=True)
        margin_stem = "menor_holgura_" + run_id
        figures.save(
            fig,
            margin_stem,
            chart_rows(state, run, [key for key in keys if key != "time_ns"]),
            "Menor holgura " + identity(run),
            [package / "series_locales.json", package / "tablas/puntos_extremos.csv"],
            note=margin_window_note
            + "ND de caja neta cuando las reservas no son acreditables. No se transfieren fondos.",
            run_ids=[run_id],
        )
        descriptions.append(
            {
                "run": run,
                "dd": dd,
                "margin_point": selected,
                "symbol": symbol,
                "dd_figure": stem,
                "margin_figure": margin_stem,
                "margin_window_note": margin_window_note,
                "sampling": sample_note,
            }
        )
    return descriptions


def episode_price_descriptions(package, episodes):
    """Describe adverse spot moves, without creating scenario portfolio outcomes."""
    source = package / "evidencia/episodios.parquet"
    columns = ["episode_id", "time_ns", "sequence", "phase"]
    columns += [
        symbol + "_" + key
        for symbol in SYMBOLS
        for key in ("spot", "short", "spot_price", "spot_proxy")
    ]
    table = pq.ParquetFile(source).read(columns=columns)
    identifiers = table["episode_id"].combine_chunks().to_numpy(zero_copy_only=False)
    details = []
    for episode in episodes:
        if episode["scenario"] != "BASE_E3":
            continue
        part = table.filter(pa.array(identifiers == episode["episode_id"]))
        values = {
            key: part[key].combine_chunks().to_numpy(zero_copy_only=False)
            for key in columns
            if key != "episode_id"
        }
        symbol = episode["symbol"]
        selected = incident_exposure_mask(values, symbol, int(episode["end_ns"]))
        selected &= values[symbol + "_spot"] > 0
        for method, column in ((ORIGINAL, "spot_price"), (PROXY, "spot_proxy")):
            valid = selected & np.isfinite(values[symbol + "_" + column])
            ix = np.flatnonzero(valid)
            row = {
                key: episode[key]
                for key in ("run_id", "scenario", "strategy", "symbol", "episode_id")
            }
            row.update(
                valuation=method,
                status="descriptive_price_calibration_not_scenario_result",
                duration_seconds=episode["seconds"],
                observations=len(ix),
            )
            if len(ix):
                prices = values[symbol + "_" + column]
                minimum = int(ix[np.argmin(prices[ix])])
                start = int(ix[0])
                row.update(
                    start_time_ns=int(values["time_ns"][start]),
                    minimum_time_ns=int(values["time_ns"][minimum]),
                    initial_spot_price=float(prices[start]),
                    minimum_spot_price=float(prices[minimum]),
                    adverse_fraction=max(0.0, float(1 - prices[minimum] / prices[start])),
                    reason="",
                )
            else:
                row.update(
                    adverse_fraction=None, reason="no_observable_long_spot_in_active_interval"
                )
            details.append(row)
    summaries = []
    for symbol in SYMBOLS:
        for method in (ORIGINAL, PROXY):
            selected = [
                row for row in details if row["symbol"] == symbol and row["valuation"] == method
            ]
            values = np.array([number(row["adverse_fraction"]) for row in selected])
            finite = values[np.isfinite(values)]
            summaries.append(
                {
                    "symbol": symbol,
                    "valuation": method,
                    "episodes": len(selected),
                    "non_evaluable": int(np.sum(~np.isfinite(values))),
                    "zero_loss_episodes": int(np.sum(finite == 0)),
                    "median_adverse_fraction": float(np.median(finite)) if len(finite) else None,
                    "p90_adverse_fraction": float(np.quantile(finite, 0.9))
                    if len(finite)
                    else None,
                    "maximum_adverse_fraction": float(np.max(finite)) if len(finite) else None,
                }
            )
    write_csv(package / "figuras/fuentes/calibracion_episodios.csv", details)
    write_csv(package / "figuras/fuentes/calibracion_escenarios_pendientes.csv", summaries)
    write_json(
        package / "figuras/fuentes/calibracion_escenarios_pendientes.json",
        {
            "source": "evidencia/episodios.parquet",
            "source_sha256": sha256(source),
            "catalogue_sha256": sha256(package / "tablas/catalogo_incidentes.csv"),
            "formula": "max(0, 1-min(spot within active episode)/spot at first active state)",
            "boundary": "start post through end pre; same verified incident_exposure_mask as catalogue",
            "limits": "Whole episodes with unequal durations; not rates per minute or probabilities. Same market observations may occur in both portfolios.",
            "new_backtest": False,
        },
    )
    return summaries


def build_report(package, series_root):
    package, series_root = Path(package).resolve(), Path(series_root).resolve()
    required = [
        "drawdown_comparativo",
        "garantias_periodo",
        "metricas_reutilizadas",
        "catalogo_incidentes",
        "puntos_extremos",
        "riesgo_diario",
        "h1_resumen",
        "h1_invariancia",
        "h2",
        "h3_regimen",
        "h3_invariancia",
    ]
    tables = {name: read_csv(package / "tablas" / (name + ".csv")) for name in required}
    meta = json.loads((package / "series_locales.json").read_text(encoding="utf-8"))
    reconstruction = json.loads((package / "reconstruccion.json").read_text(encoding="utf-8"))
    runs = sorted(reconstruction["runs"], key=lambda r: (r["scenario"] != "BASE_E3", r["strategy"]))
    base_runs = [run for run in runs if run["scenario"] == "BASE_E3"]
    dd_lookup = {
        (row["run_id"], row["period"], row["peak_policy"], row["valuation"]): row
        for row in tables["drawdown_comparativo"]
    }
    metrics = {(row["run_id"], row["period"]): row for row in tables["metricas_reutilizadas"]}
    margins = {(row["run_id"], row["period"]): row for row in tables["garantias_periodo"]}
    if any(
        (run["run_id"], "full", "period_reset", method) not in dd_lookup
        for run in runs
        for method in (ORIGINAL, PROXY)
    ):
        raise ValueError("Both explicitly labelled valuation methods are required")
    figures = Figures(package)
    plot_dd(figures, tables["drawdown_comparativo"], package / "tablas/drawdown_comparativo.csv")
    plot_annual(
        figures,
        tables["metricas_reutilizadas"],
        dd_lookup,
        [package / "tablas/metricas_reutilizadas.csv", package / "tablas/drawdown_comparativo.csv"],
    )
    march = march_figures(figures, package, base_runs)
    extrema = extrema_figures(
        figures, package, series_root, meta, runs, dd_lookup, tables["puntos_extremos"]
    )
    write_csv(package / "figuras/indice_figuras.csv", figures.index)

    report = Report("Riesgo intradía, incidentes y garantías")
    report.paragraph(
        "Informe técnico preliminar · Entrega 4 · Construcción y conciliación ejecutadas. Muestra continua del 1 de enero de 2022 al 31 de agosto de 2026 · UTC. Posprocesamiento de cuatro carteras publicadas; no se ejecutó un nuevo backtest. El sello se verifica con los comandos del paquete; los resultados finales se conservan en la carpeta de ejecución.",
        lede=True,
    )
    report.paragraph(
        "Este bloque responde a la devolución recibida sobre pérdidas transitorias y garantías. Conserva la desagregación anual y el vínculo entre retorno y capital utilizado. La comparación remunerada y las nuevas trayectorias hipotéticas siguen pendientes; no completa toda la Entrega 4."
    )
    report.links(
        "Documentos de alcance:",
        [
            ("Feedback literal", "documentos/feedback_e3.md"),
            ("Protocolo previo", "documentos/protocolo.md"),
            ("Matriz de cobertura", "documentos/matriz_cobertura_feedback.csv"),
        ],
    )
    report.heading("Hallazgos principales")
    for run in base_runs:
        row = dd_lookup[(run["run_id"], "full", "period_reset", ORIGINAL)]
        proxy = dd_lookup[(run["run_id"], "full", "period_reset", PROXY)]
        margin = margins[(run["run_id"], "full")]
        report.paragraph(
            f"{identity(run)}: el drawdown máximo pasa de {pct(row['daily_drawdown'], 4)} diario a {pct(row['intraday_drawdown'], 4)} en la unión de minutos y eventos, una diferencia de {fmt(row['extra_drawdown_pp'], 4)} puntos porcentuales. El diagnóstico separado con proxy alcanza {pct(proxy['intraday_drawdown'], 4)}. La menor holgura aislada observada es {fmt(margin['min_headroom_usdt'])} USDT; el máximo déficit conjunto de mantenimiento es {fmt(margin['max_joint_maintenance_need_usdt'])} USDT y la necesidad preventiva conjunta llega a un ínfimo de {fmt(margin['max_joint_preventive_need_infimum_usdt'])} USDT."
        )
    report.paragraph(
        f"Se conciliaron {reconstruction['daily_reconciliations']} cierres diarios, con residuo monetario máximo {number(reconstruction['maximum_daily_residual_usdt']):.3g} USDT, frente a la tolerancia original de 1E-8 USDT. La conciliación valida la contabilidad bajo la convención original; no convierte un spot antiguo en una observación contemporánea."
    )
    report.paragraph(
        "Durante la suspensión spot del 24/03/2023 hay 152 minutos sin un cierre spot nuevo: 72 velas de volumen cero y 80 registros ausentes. La referencia original conserva su último valor. El proxy conserva la relación spot/perpetuo del ancla y cambia exclusivamente la valoración. La diferencia no es un beneficio realizable ni una venta que hubiera sido posible durante la suspensión."
    )
    report.paragraph(
        "En BASE condicional, el peor drawdown de valoración original parte de un pico durante la suspensión: el spot antiguo permanece fijo mientras se mueve el mark del corto. Ese pico contable puede exagerar la caída posterior cuando vuelve un spot negociado. Por ello, la medida original se conserva para conciliar, pero no se interpreta como una pérdida de riqueza ejecutable observada desde un máximo de mercado igualmente negociable. El proxy presenta por separado la sensibilidad a ese problema de valoración."
    )
    report.figure(
        "drawdown_muestra_completa",
        "Figura 1. Drawdown de la muestra completa, incluyendo 10.000 USDT iniciales. La valoración proxy es hipotética y se mantiene separada del resultado original reconstruido.",
    )

    report.heading("Identidad, valoración y alcance verificable")
    report.table(
        ["Cartera", "run_id original", "Estado"],
        [[identity(run), run["run_id"], "Reconstruido por posprocesamiento"] for run in runs],
    )
    report.paragraph(
        "La permanente omite sólo el filtro de funding de entrada y renovación; conserva basis y controles operativos. MARGEN_2X duplica el importe de mantenimiento, incluida la deducción del tramo, y mantiene el apalancamiento elegido. No se repiten las variantes de costos."
    )
    report.paragraph(
        "La trayectoria es la unión de cierres de un minuto disponibles, instantes financieros necesarios y cierres diarios originales; no es tick-by-tick. Spot utiliza el último cierre con volumen positivo disponible; futuros se valúa al mark de riesgo. Un cierre de vela se conoce en su límite exclusivo. El cierre diario 23:59:59.999999999 utiliza normalmente la vela abierta a las 23:58, disponible a las 23:59; nunca anticipa la vela de las 23:59."
    )
    report.paragraph(
        "Se conservan el funding_time exacto y los milisegundos originales: funding sobre el corto anterior a fills simultáneos, fills comprometidos y controles posteriores. Los estados pre/post tienen duración cero y pueden cambiar necesidades instantáneas. Los 15 marks futures_scaled aprobados son distintos de los settlement marks de funding tratados como previous_closed_1m. Ambos conservan su procedencia."
    )
    report.paragraph(
        "Equity = caja spot + caja futuros + garantías + valor spot + P&L no realizado de futuros − deuda. Las transferencias y movimientos de garantía no crean equity. Funding, comisiones y slippage no se duplican. El polvo conserva su riesgo de precio, aunque se distingue de una posición activa."
    )
    report.links(
        "Evidencia de reconstrucción:",
        [
            ("Metadatos y conciliación", "reconstruccion.json"),
            ("Todos los residuos diarios", "tablas/conciliaciones_diarias.csv"),
            ("Dependencia de la serie local completa", "series_locales.json"),
        ],
    )

    report.heading("Drawdown comparable: muestra, años y cortes")
    report.paragraph(
        "DD(t) = equity(t) / máximo hasta t − 1, incluyendo el capital inicial y la observación actual. La política period_reset reinicia sólo el máximo de referencia en el saldo real de entrada del corte. full_trajectory_peak conserva el pico anterior de la trayectoria respectiva. No se reinician caja ni posiciones. Cada comparación utiliza el mismo período y política; los cierres diarios forman un subconjunto conciliado de la trayectoria intradía."
    )
    for policy in ("period_reset", "full_trajectory_peak"):
        report.heading(policy_label(policy), 3)
        selected = sorted(
            [row for row in tables["drawdown_comparativo"] if row["peak_policy"] == policy],
            key=lambda r: (
                r["scenario"] != "BASE_E3",
                r["strategy"],
                PERIODS.index(r["period"]),
                r["valuation"],
            ),
        )
        report.table(
            ["Cartera", "Período", "Valoración", "DD diario", "DD intradía", "Diferencia (pp)"],
            [
                [
                    identity(r),
                    period_label(r["period"]),
                    valuation_label(r["valuation"]),
                    pct(r["daily_drawdown"], 4),
                    pct(r["intraday_drawdown"], 4),
                    fmt(r["extra_drawdown_pp"], 4),
                ]
                for r in selected
            ],
        )
    report.paragraph(
        "La diferencia monetaria entre pérdidas pico–valle se conserva en el CSV y puede corresponder a picos y valles distintos; no es un P&L incremental causado por pasar a frecuencia intradía. No se divide por drawdown diario cero. Los máximos describen la valoración observada bajo sus arrastres y aproximaciones, no un máximo de riesgo de mercado conocido durante una suspensión."
    )
    report.links(
        "Tabla de precisión completa, picos, valles y recuperación:",
        [("drawdown_comparativo.csv", "tablas/drawdown_comparativo.csv")],
    )
    report.heading("Caída desde apertura de jornada y desde máximo intradiario", 3)
    report.table(
        [
            "Cartera",
            "Peor caída desde inicio del día (USDT)",
            "Peor pérdida desde pico del día (USDT)",
        ],
        [
            [
                identity(run),
                fmt(margins[(run["run_id"], "full")]["max_loss_from_day_open_usdt"]),
                fmt(margins[(run["run_id"], "full")]["max_within_day_peak_loss_usdt"]),
            ]
            for run in runs
        ],
    )
    report.paragraph(
        "Estas dos pérdidas reinician su referencia dentro de cada jornada y no se llaman indistintamente drawdown máximo de la muestra. Los timestamps y todos los días permanecen en riesgo_diario.csv."
    )

    report.heading("Suspensión spot: antes, durante y después")
    report.paragraph(
        "La ventana publicada cubre 23–25 de marzo de 2023. La última vela spot/perpetuo alineada se abrió a las 11:27 del 24/03 y estuvo disponible a las 11:28: BTC 28.080/28.070 y ETH 1.789,52/1.788,54. El ancla queda fija; S_proxy(t)=S(s)×F(t)/F(s). La primera vela válida de reapertura se abre a las 14:00 y se conoce a las 14:01. Allí se retoma spot observado. El supuesto conserva la relación del ancla; no recupera el precio real durante el hueco ni demuestra convergencia del basis."
    )
    march_episodes = [
        r
        for r in tables["catalogo_incidentes"]
        if r["scenario"] == "BASE_E3" and r["classification"] == "documented_spot_interruption"
    ]
    report.table(
        [
            "Cartera",
            "Activo",
            "Inicio UTC",
            "Fin UTC",
            "Minutos",
            "Mayor corto durante episodio",
            "Cambio cartera (USDT)",
            "Cambio activo (USDT)",
        ],
        [
            [
                identity(r),
                r["symbol"],
                r["start_utc"],
                r["end_exclusive_utc"],
                fmt(number(r["seconds"]) / 60, 0),
                fmt(r["maximum_short_quantity"], 6),
                fmt(r["portfolio_change_usdt"]),
                fmt(r["asset_change_usdt"]),
            ]
            for r in march_episodes
        ],
    )
    report.paragraph(
        "Los 121 minutos de exposición activa descubierta se controlan por unión de cartera, sin sumar BTC y ETH simultáneos. En ese tramo los futuros afectados ya están cerrados: no se les asigna mantenimiento por llamarse incidente operativo. La garantía se analiza antes del cierre y el riesgo posterior corresponde al inventario spot. La constancia de su precio original no demuestra ausencia de pérdida intradía."
    )
    report.links(
        "Controles de exposición ejecutados:",
        [
            ("Duraciones por cartera y activos", "tablas/controles_exposicion.csv"),
            ("Resultado de controles", "controles_exposicion.json"),
        ],
    )
    report.table(
        [
            "Cartera",
            "Mayor reducción de equity al usar proxy (USDT)",
            "Instante UTC",
            "Interpretación",
        ],
        [
            [
                identity(r),
                fmt(r["maximum_proxy_valuation_reduction_usdt"]),
                r["timestamp_utc"],
                "Diferencia de valoración; posiciones originales",
            ]
            for r in march
        ],
    )
    report.paragraph(
        "La comparación anterior incluye todo el intervalo de suspensión, también antes de que el futuro fuera cerrado. No debe confundirse con la peor pérdida dentro de los 121 minutos descubiertos. En la reapertura, el spot observado supera al proxy del mismo instante en 22,653057 USDT por BTC y 3,626131 USDT por ETH; se incorpora ese cambio de referencia, sin inventar una ejecución."
    )
    report.figure(
        "marzo_tres_dias",
        "Figura 3. Ventana completa de tres días. El área sombreada identifica el tramo sin un nuevo cierre spot disponible.",
    )
    for run in base_runs:
        report.figure(
            "marzo_detalle_" + run["strategy"],
            "Detalle intradiario de "
            + identity(run)
            + ": valoración, referencia spot, exposición neta y mantenimiento. La línea vertical de las 12:00 facilita localizar el tramo descubierto.",
        )
    report.links(
        "Evidencia íntegra del detalle:",
        [
            ("marzo_2023.parquet", "evidencia/marzo_2023.parquet"),
            ("Catálogo de incidentes", "tablas/catalogo_incidentes.csv"),
        ],
    )

    report.heading("Catálogo completo y selección de episodios")
    episodes = tables["catalogo_incidentes"]
    report.table(
        [
            "Cartera",
            "Episodios por activo",
            "Tiempo descubierto de cartera (s)",
            "Criterio de agregación",
        ],
        [
            [
                identity(run),
                str(sum(r["run_id"] == run["run_id"] for r in episodes)),
                fmt(metrics[(run["run_id"], "full")]["unhedged_seconds"], 0),
                "Unión temporal; episodios por activo y ciclo",
            ]
            for run in runs
        ],
    )
    report.paragraph(
        "El catálogo conserva secuencias normales, parciales/desarmes, correcciones, cierres demorados e interrupciones documentadas. Una espera normal entre patas no se describe automáticamente como incidente extraordinario. Se conservan ciclos, órdenes, estados y causas registradas; el P&L contemporáneo de cartera y la contribución del activo son distintos de un efecto causal del incidente."
    )
    worst_incidents = [
        min(
            [row for row in episodes if row["run_id"] == run["run_id"]],
            key=lambda row: number(row["worst_portfolio_change_usdt"]),
        )
        for run in runs
    ]
    report.table(
        [
            "Cartera",
            "Episodio de mayor caída desde su inicio",
            "Clase",
            "Duración (min)",
            "Peor cambio cartera (USDT)",
            "Cambio final cartera (USDT)",
            "Peor cambio activo (USDT)",
        ],
        [
            [
                identity(r),
                r["episode_id"],
                r["classification"],
                fmt(number(r["seconds"]) / 60),
                fmt(r["worst_portfolio_change_usdt"]),
                fmt(r["portfolio_change_usdt"]),
                fmt(r["worst_asset_change_usdt"]),
            ]
            for r in worst_incidents
        ],
    )
    report.paragraph(
        "El peor estado transitorio y el resultado final del episodio no son la misma magnitud. La malla conserva el estado PRE de la primera operación y cada estado POST del ledger, ordenados por secuencia, aunque compartan hora y tengan duración cronológica cero. En la reapertura de marzo, la valoración PRE incorpora el primer spot nuevo antes de vender; el POST incorpora el precio VWAP, efectivo y comisiones de la ejecución original. Así puede observarse una pérdida transitoria mayor que la pérdida final sin que exista una contradicción contable. Estos estados no se convierten en minutos adicionales de exposición."
    )
    report.links(
        "Todos los episodios, incluidos los que finalizan con ganancia:",
        [
            ("Catálogo legible completo", "catalogo_completo.html"),
            ("CSV de precisión completa", "tablas/catalogo_incidentes.csv"),
            ("Estados de cada episodio", "evidencia/episodios.parquet"),
        ],
    )

    report.heading("Garantías, prevención y liquidez")
    report.paragraph(
        "Con corto abierto, saldo de margen B = garantía + q×(precio medio−mark); mantenimiento M(n) = nocional×tasa del tramo−deducción, con el multiplicador efectivo de cada corrida. Holgura = B−M. Un saldo no positivo se trata como señal de riesgo; ratio y distancia no son tranquilizadores ni se reemplazan por cero. Sin corto, mantenimiento es cero y ratio/distancia no aplican."
    )
    report.table(
        [
            "Cartera",
            "Menor holgura (USDT)",
            "Mayor ratio",
            "Menor distancia",
            "Máx. déficit mantenimiento conjunto (USDT)",
            "Máx. necesidad preventiva conjunta: ínfimo (USDT)",
            "Faltante externo preventivo: cotas del máximo (USDT)",
        ],
        [
            [
                identity(run),
                fmt((r := margins[(run["run_id"], "full")])["min_headroom_usdt"]),
                pct(r["max_margin_ratio"], 3),
                pct(r["min_liquidation_distance"], 3),
                fmt(r["max_joint_maintenance_need_usdt"]),
                fmt(r["max_joint_preventive_need_infimum_usdt"]),
                fmt(r["max_external_lower_bound_usdt"])
                + " a "
                + fmt(r["max_external_upper_bound_usdt"]),
            ]
            for run in runs
        ],
    )
    report.paragraph(
        "Tres preguntas se separan: mantenimiento exigido; déficit para llegar a la frontera, max(0,M−B); y necesidad de conservar ambos umbrales preventivos. Una transferencia hipotética x debe cumplir x≥0, x>M(qm)/0,50−B y x≥qm×0,15+M(qm×1,15)−B. Se informa el ínfimo y una bandera de frontera estricta. Cuando el ínfimo coincide con la condición estricta no es un mínimo suficiente: hace falta superarlo, sin inventar un quantum ni sumar un centavo arbitrario."
    )
    report.paragraph(
        "Las necesidades se suman entre contratos sólo en el mismo instante y se comparan una sola vez con la caja común acreditada. No se reutiliza garantía ajena, ni se cuenta spot no vendido como efectivo, ni se suman máximos de activos ocurridos en fechas distintas. Transferir caja libre a garantía conserva equity. Tampoco se suman déficits de minutos consecutivos como aportes realizados."
    )
    report.table(
        ["Cartera", "Tiempo con disponibilidad neta no acreditable (s)", "Tratamiento"],
        [
            [
                identity(run),
                fmt(margins[(run["run_id"], "full")]["unknown_redistributable_seconds"], 3),
                "Caja neta y faltante exacto ND; cotas con caja bruta y reserva desconocida",
            ]
            for run in runs
        ],
    )
    report.paragraph(
        "Las cotas no declaran que toda la caja bruta estuviera libre: la cota inferior resta como máximo esa caja y la superior conserva la necesidad cuando la reserva no es acreditable. Son cotas del máximo instantáneo, no una trayectoria de aportes. Si la necesidad es cero, el déficit correspondiente puede ser cero aun cuando falte precisión sobre la disponibilidad. La igualdad de mantenimiento no acredita evitar todo cargo, liquidación o salida preventiva."
    )
    report.links(
        "Detalle por período, día y contrato:",
        [
            ("Garantías por período", "tablas/garantias_periodo.csv"),
            ("Garantías diarias por activo", "tablas/garantias_diarias_activo.csv"),
            ("Puntos extremos", "tablas/puntos_extremos.csv"),
        ],
    )

    report.heading("Peor drawdown y menor holgura de cada cartera")
    report.paragraph(
        "La selección sigue los criterios fijados en el protocolo, sin omitir resultados favorables o adversos: peor drawdown de la trayectoria original y menor holgura mientras existe corto. Pueden corresponder a episodios distintos. Los gráficos extensos utilizan una envolvente diaria que conserva extremos en su orden temporal; las cifras proceden de las tablas calculadas sobre la serie completa."
    )
    for item in extrema:
        run, row, point, symbol = item["run"], item["dd"], item["margin_point"], item["symbol"]
        trough_point = next(
            value
            for value in tables["puntos_extremos"]
            if value["run_id"] == run["run_id"] and value["label"] == "worst_equity_drawdown"
        )
        report.heading(identity(run), 3)
        report.table(
            [
                "Pico UTC",
                "Valle UTC",
                "Recuperación UTC",
                "Pérdida pico–valle (USDT)",
                "DD original",
            ],
            [
                [
                    row["intraday_peak_utc"],
                    row["intraday_trough_utc"],
                    row["intraday_recovery_utc"] or "Sin recuperación en muestra",
                    fmt(row["intraday_loss_usdt"]),
                    pct(row["intraday_drawdown"], 4),
                ]
            ],
        )
        report.table(
            ["Activo", "Cantidad spot", "Cantidad corta", "Precio spot (USDT)", "Mark (USDT)"],
            [
                [
                    asset,
                    fmt(trough_point[asset + "_spot"], 8),
                    fmt(trough_point[asset + "_short"], 8),
                    fmt(trough_point[asset + "_spot_price"], 6),
                    fmt(trough_point[asset + "_mark_price"], 6),
                ]
                for asset in SYMBOLS
            ],
        )
        phase = {"0": "regular", "1": "PRE de la primera operación", "2": "POST de operación"}[
            trough_point["phase"]
        ]
        report.paragraph(
            f"Estado del valle: {phase}, secuencia {trough_point['sequence']}; equity {fmt(trough_point['equity_usdt'], 6)} USDT y caja bruta {fmt(trough_point['free_cash_usdt'], 6)} USDT. Fuente: puntos_extremos.csv, con cantidades y precios de la misma observación."
        )
        if run["scenario"] == "BASE_E3" and run["strategy"] == "conditional":
            report.paragraph(
                "Este valle es anterior al primer fill de reapertura, con ETH spot todavía en cartera y el corto ya cerrado. El máximo que inicia el drawdown original ocurre durante el carry del precio spot. La figura conserva esa valoración para conciliar; el proxy y el cambio final del episodio se muestran por separado."
            )
        else:
            report.paragraph(
                "En este valle, las cantidades spot y cortas están casi igualadas para ambos activos. La pérdida máxima de equity no identifica por sí sola una exposición extraordinaria sin cobertura: el estado observado conserva diferencias entre spot y mark con posiciones cubiertas. Es contexto de valoración y convergencia, no una atribución causal de toda la pérdida pico–valle a la diferencia de precios de este instante."
            )
        report.paragraph(
            f"Menor holgura: {symbol}, {point['timestamp_utc']}, cantidad corta {fmt(point[symbol + '_short'], 6)}, garantía {fmt(point[symbol + '_collateral'])} USDT, saldo de margen {fmt(point[symbol + '_margin_balance_usdt'])} USDT, mantenimiento {fmt(point[symbol + '_maintenance_usdt'])} USDT y holgura {fmt(point[symbol + '_headroom_usdt'])} USDT. El estado incluye fase y secuencia originales en puntos_extremos.csv."
        )
        report.figure(
            item["dd_figure"], item["sampling"] + ". Estado: reconstruido; valoración original."
        )
        report.figure(
            item["margin_figure"],
            item["margin_window_note"]
            + "Sólo se muestran métricas contractuales con corto abierto. Caja neta desconocida permanece como hueco.",
        )

    report.heading("Resultados anuales y capital utilizado")
    report.paragraph(
        "Los P&L, retornos, CAGR, Sharpe y utilización proceden de la corrección verificada, sin resimulación ni cambios en H1/H2/H3. CAGR anualiza el período indicado usando su duración; no convierte enero–agosto de 2026 en doce meses observados. Tiempo activo excluye polvo. Capital utilizado, garantía, caja libre y equity se mantienen como conceptos distintos. No se divide CAGR por utilización media para fabricar un retorno comparable."
    )
    for run in runs:
        report.heading(identity(run), 3)
        rows = []
        for year in YEARS:
            row = metrics[(run["run_id"], year)]
            dd = dd_lookup[(run["run_id"], year, "period_reset", ORIGINAL)]
            margin = margins[(run["run_id"], year)]
            rows.append(
                [
                    period_label(year),
                    fmt(row["net_pnl_usdt"]),
                    pct(row["net_return"]),
                    pct(row["cagr"]),
                    pct(dd["daily_drawdown"], 4),
                    pct(dd["intraday_drawdown"], 4),
                    pct(row["invested_fraction"]),
                    pct(row["capital_utilization_daily_mean"]),
                    pct(row["capital_utilization_daily_max"]),
                    fmt(margin["min_headroom_usdt"]),
                    fmt(margin["max_joint_preventive_need_infimum_usdt"]),
                ]
            )
        report.table(
            [
                "Período",
                "P&L (USDT)",
                "Retorno",
                "CAGR anualizado",
                "DD diario",
                "DD intradía",
                "Tiempo activo",
                "Utiliz. media diaria",
                "Utiliz. máx. diaria",
                "Holgura mín. (USDT)",
                "Necesidad preventiva máx.: ínfimo (USDT)",
            ],
            rows,
        )
        recent = [metrics[(run["run_id"], year)] for year in ("2024", "2025", "2026")]
        report.paragraph(
            f"Lectura de los años recientes: retorno {pct(recent[0]['net_return'])} en 2024, {pct(recent[1]['net_return'])} en 2025 y {pct(recent[2]['net_return'])} en enero–agosto de 2026. El promedio del corte 2024+ no reemplaza esta trayectoria anual ni la información sobre capital efectivamente utilizado."
        )
    report.figure(
        "resumen_anual_base",
        "Retorno, utilización y drawdown anual BASE. Los drawdowns del gráfico reinician el pico al saldo real de entrada; la evidencia conserva además el pico acumulado.",
    )
    report.heading("H1, H2 y H3 conservadas", 3)
    h2 = [
        r
        for r in tables["h2"]
        if r["scenario"] in {"BASE_E3", "MARGEN_2X"}
        and r["period"] in ("full", "2022-2023", "2024+")
    ]
    report.table(
        [
            "Escenario",
            "Período",
            "H2 publicada",
            "Razón publicada",
            "Sharpe condicional",
            "Sharpe permanente",
        ],
        [
            [
                r["scenario"],
                period_label(r["period"]),
                r["verdict"],
                r["reason"],
                fmt(r["conditional_sharpe"], 3),
                fmt(r["permanent_sharpe"], 3),
            ]
            for r in h2
        ],
    )
    report.paragraph(
        "H1 conserva pronósticos y ponderaciones; H2 conserva su criterio corregido y el Sharpe diario publicado, incluido ND cuando no existe volatilidad muestral; H3 conserva los cortes originales y su lectura descriptiva. Los nuevos indicadores intradía no cambian retrospectivamente esos contrastes."
    )
    report.links(
        "Tablas originales reutilizadas:",
        [
            ("H1", "tablas/h1_resumen.csv"),
            ("Invariancia H1", "tablas/h1_invariancia.csv"),
            ("H2", "tablas/h2.csv"),
            ("H3", "tablas/h3_regimen.csv"),
            ("Invariancia H3", "tablas/h3_invariancia.csv"),
            ("Métricas financieras completas", "tablas/metricas_reutilizadas.csv"),
        ],
    )

    report.heading("Bloque siguiente: propuestas todavía no ejecutadas")
    base_episodes = [row for row in episodes if row["scenario"] == "BASE_E3"]
    durations = np.array([number(row["seconds"]) / 60 for row in base_episodes])
    report.paragraph(
        f"Para dar escala a los escenarios, el catálogo BASE contiene {len(durations)} episodios por activo, con mediana de duración {fmt(np.median(durations))} minutos, percentil 90 {fmt(np.quantile(durations, 0.9))} minutos y máximo {fmt(np.max(durations))} minutos. Estas estadísticas son descriptivas del catálogo y no probabilidades de eventos futuros; no se suman entre activos como duración de cartera."
    )
    calibrations = episode_price_descriptions(package, episodes)
    report.table(
        [
            "Activo",
            "Valoración",
            "Episodios",
            "Sin caída de precio",
            "Mediana caída spot",
            "P90 caída spot",
            "Máxima caída spot",
        ],
        [
            [
                row["symbol"],
                valuation_label(row["valuation"]),
                row["episodes"],
                row["zero_loss_episodes"],
                pct(row["median_adverse_fraction"], 4),
                pct(row["p90_adverse_fraction"], 4),
                pct(row["maximum_adverse_fraction"], 4),
            ]
            for row in calibrations
        ],
    )
    report.paragraph(
        "La escala anterior mide max(0,1−mínimo spot/precio spot inicial) dentro de cada episodio activo, desde inicio post hasta fin pre, conservando ceros. Usa precios observados o, separadamente, el proxy de valoración; no es P&L de cartera. Los episodios tienen distinta duración y pueden compartir observaciones de mercado entre carteras: no son ensayos independientes, tasas por minuto ni probabilidades. Se propone usar P90 y máximo de la valoración original como dos magnitudes de caída spot y mostrar la sensibilidad de calibrarlas con el proxy por separado."
    )
    report.links(
        "Cálculos descriptivos de la escala propuesta:",
        [
            ("Cada episodio", "figuras/fuentes/calibracion_episodios.csv"),
            ("Percentiles y máximos", "figuras/fuentes/calibracion_escenarios_pendientes.csv"),
        ],
    )
    report.table(
        [
            "Tanda pequeña pendiente",
            "Comparador y magnitud",
            "Justificación",
            "Nueva trayectoria requerida",
        ],
        [
            [
                "Demoras adicionales de cierre",
                "Referencia original frente a +1, +5 y +15 minutos en episodios previamente catalogados",
                "1 minuto coincide con la resolución; 5 y 15 exploran retrasos operativos mayores sin elegir sólo episodios rentables",
                "Sí: nuevas ventanas elegibles, fills, funding y controles; preservar reglas y datos",
            ],
            [
                "Movimientos adversos con exposición",
                "Dos niveles por activo: P90 y máximo de caída spot del episodio completo, medidos en la tabla anterior; escenarios separados de las tres demoras",
                "Aplicarlos a todos los episodios comparables con observación spot válida; shock al inicio descubierto y persistente hasta cierre, sin inferir probabilidades ni combinar extremos de mark",
                "Sí: la trayectoria de precio hipotética cambia valoración, ejecución y controles. Durante una suspensión seguirá sin autorizar ventas; el contrafactual de reapertura es otro experimento",
            ],
            [
                "Contrafactual sin interrupción",
                "Comparar la cartera original con una trayectoria que explicite qué mercado y liquidez habrían existido",
                "Compromiso previo distinto del proxy de valoración",
                "Sí; el proxy con posiciones fijas no lo resuelve",
            ],
            [
                "Alternativa remunerada: todo el capital",
                "Benchmark en la misma moneda y período con datos históricos verificables",
                "Es una alternativa al capital completo",
                "Definir disponibilidad, costos, riesgos, reinversión y garantías antes de elegir tasa o producto",
            ],
            [
                "Remuneración sólo de efectivo libre",
                "Aplicar remuneración únicamente a caja acreditada disponible, con calendario de entradas/salidas",
                "Experimento distinto; respeta órdenes pendientes y garantías no redistribuibles",
                "Requiere trayectoria de caja y reglas de disponibilidad; no sumar interés al P&L base actual",
            ],
        ],
    )
    report.paragraph(
        "Estas propuestas no se ejecutaron. La tanda inicial comprende tres demoras y dos niveles de movimiento adverso, sin cruzar una matriz general; la referencia mantiene los precios y decisiones originales. Las magnitudes medidas justifican la escala de estrés, no una probabilidad. No se selecciona ahora moneda alternativa, tasa, producto ni regla de reinversión. El Sharpe de H2 permanece intacto."
    )

    report.heading("Límites y reproducción")
    report.paragraph(
        f"La reconstrucción local contiene {fmt(reconstruction['rows'], 0)} observaciones en {len(meta['entries'])} particiones; los archivos de serie suman {fmt(sum(int(entry['bytes']) for entry in meta['entries']) / 1_000_000_000, 3)} GB decimales comprimidos. El registro de reconstrucción informa {fmt(reconstruction['elapsed_seconds'], 2)} segundos de ejecución. Estos datos describen esa ejecución, no incluyen necesariamente auditorías, exportación y generación del reporte."
    )
    report.paragraph(
        "La serie completa comprimida permanece local en la ruta indicada por --series-root, con hashes en series_locales.json. El paquete compacto conserva tablas, estados financieros y ventanas de episodios y marzo; evita duplicar millones de registros. El verificador compacto puede comprobar identidad, aritmética y evidencia exportada, pero no recalcular independientemente el máximo de toda la muestra sin acceder a la serie completa y a las fuentes locales. La verificación completa exige esas rutas y sus precios/estados originales."
    )
    report.paragraph(
        "Persisten incertidumbre del precio spot durante la interrupción, las excepciones de marks y funding declaradas, disponibilidad neta ND en estados con compromisos no acreditables y ausencia de trayectoria intravela. No se combinan mínimos spot y máximos mark de una vela como si fueran simultáneos. No se afirma haber leído un PDF E3 ausente. Este reporte no sustituye un contrafactual de ejecución ni una comparación remunerada."
    )
    report.links(
        "Archivos para reproducir y revisar:",
        [
            ("Procedencia de tablas", "tablas_procedencia.json"),
            ("Índice de figuras", "figuras/indice_figuras.csv"),
            ("Comando y procedencia del reporte", "generacion_reporte.json"),
        ],
    )
    report.save(package, "reporte")

    catalogue = Report("Catálogo completo de exposición activa sin cobertura")
    catalogue.paragraph(
        "Todos los episodios detectados, sin excluir finales positivos. Se agrupan estados contiguos sólo dentro del mismo activo y ciclo. Las duraciones por activo no se suman como tiempo de cartera. Cifras redondeadas aquí; el CSV conserva la precisión y los identificadores completos."
    )
    for run in runs:
        catalogue.heading(identity(run))
        selected = [row for row in episodes if row["run_id"] == run["run_id"]]
        catalogue.table(
            [
                "Episodio",
                "Activo",
                "Inicio UTC",
                "Fin UTC",
                "Min",
                "Clase",
                "Peor Δ cartera (USDT)",
                "Δ final cartera (USDT)",
                "Peor Δ activo (USDT)",
                "Máx. exposición absoluta (USDT)",
            ],
            [
                [
                    r["episode_id"],
                    r["symbol"],
                    r["start_utc"],
                    r["end_exclusive_utc"],
                    fmt(number(r["seconds"]) / 60),
                    r["classification"],
                    fmt(r["worst_portfolio_change_usdt"]),
                    fmt(r["portfolio_change_usdt"]),
                    fmt(r["worst_asset_change_usdt"]),
                    fmt(r["maximum_absolute_net_exposure_usdt"]),
                ]
                for r in selected
            ],
        )
    catalogue.links(
        "Fuente completa:",
        [
            ("catalogo_incidentes.csv", "tablas/catalogo_incidentes.csv"),
            ("Reporte", "reporte.html"),
        ],
    )
    catalogue.save(package, "catalogo_completo")
    summary = {
        "status": "preliminary_report_generated",
        "engine_replay": False,
        "full_original": [
            dd_lookup[(run["run_id"], "full", "period_reset", ORIGINAL)] for run in runs
        ],
        "full_proxy_hypothetical": [
            dd_lookup[(run["run_id"], "full", "period_reset", PROXY)] for run in runs
        ],
        "margin_full": [margins[(run["run_id"], "full")] for run in runs],
        "march_proxy_comparison": march,
        "pending_scenario_price_calibration": calibrations,
        "worst_incidents": worst_incidents,
        "pending": [
            "delay_and_adverse_new_trajectories",
            "no_interruption_counterfactual",
            "remunerated_benchmarks",
        ],
    }
    write_json(package / "resumen_hallazgos.json", summary)
    input_paths = [package / "tablas" / (name + ".csv") for name in required]
    input_paths += [
        package / "series_locales.json",
        package / "reconstruccion.json",
        package / "evidencia/marzo_2023.parquet",
        package / "evidencia/episodios.parquet",
    ]
    write_json(
        package / "generacion_reporte.json",
        {
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "script": str(Path(__file__).resolve()),
            "script_sha256": sha256(Path(__file__)),
            "series_root": str(series_root),
            "command": [
                sys.executable,
                "-B",
                "-X",
                "utf8",
                str(Path(__file__).resolve()),
                "--package",
                str(package),
                "--series-root",
                str(series_root),
            ],
            "input_hashes": {
                path.relative_to(package).as_posix(): sha256(path) for path in input_paths
            },
            "figure_count": len(figures.index),
            "source_run_ids": [run["run_id"] for run in runs],
            "engine_replay": False,
            "financial_tables_modified": False,
            "scope": "Presentation only. Whole-sample maxima come from supplied tables; local series support figures.",
        },
    )
    print(
        json.dumps(
            {
                "report": str(package / "reporte.html"),
                "figures": len(figures.index),
                "summary": str(package / "resumen_hallazgos.json"),
            },
            ensure_ascii=False,
        )
    )
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", required=True, type=Path)
    parser.add_argument("--series-root", required=True, type=Path)
    args = parser.parse_args()
    build_report(args.package, args.series_root)


if __name__ == "__main__":
    main()
