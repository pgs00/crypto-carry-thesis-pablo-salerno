"""Publish continuous-study tables and figures from the sealed evidence ZIP."""

import argparse
import csv
import hashlib
import io
import json
import zipfile
from datetime import date
from decimal import Decimal as D
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
DELIVERY = ROOT / "entregas/entrega_3"
ARCHIVE = DELIVERY / "paquete_actualizacion_entrega_3_continua.zip"
PUBLISHED = DELIVERY / "continua"
TABLES = (
    "resultados_periodos",
    "actividad",
    "tiempo_invertido",
    "ciclos",
    "filtros_entrada",
    "eventos_por_causa",
    "episodio_2023_03_24_exposicion",
    "episodio_2023_03_24_resumen",
    "h1_resumen",
    "h3_resumen",
    "h3_diario_conjunto",
)
NAMES = {"conditional": "Condicional", "permanent": "Permanente"}
COLORS = {"conditional": "#146C94", "permanent": "#B65B23"}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def load_source():
    content = ARCHIVE.read_bytes()
    require(
        digest(content) == ARCHIVE.with_suffix(".zip.sha256").read_text().split()[0],
        "Continuous ZIP checksum mismatch",
    )
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        require(archive.testzip() is None, "ZIP CRC mismatch")
        files = {
            item.filename: archive.read(item) for item in archive.infolist() if not item.is_dir()
        }
    require(
        digest(files["manifest.json"]) == files["manifest.sha256"].decode().strip(),
        "Continuous manifest checksum mismatch",
    )
    manifest = json.loads(files["manifest.json"])
    for name, expected in manifest["file_hashes"].items():
        require(digest(files[name]) == expected, "Source member changed: " + name)
    return files, digest(content)


def rows(content):
    return list(csv.DictReader(io.StringIO(content.decode("utf-8-sig"))))


def daily_projection(content):
    """Keep full-precision source strings in a small GitHub-viewable daily table."""
    fields = ("date", "strategy", "equity_usdt", "daily_return", "net_pnl_usdt")
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    writer.writerows({key: row[key] for key in fields} for row in rows(content))
    return stream.getvalue().encode("utf-8")


def figures(files, destination):
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "svg.hashsalt": "continuous-thesis-20260920",
        }
    )
    destination.mkdir()

    def save(fig, name):
        fig.savefig(
            destination / (name + ".png"),
            dpi=300,
            facecolor="white",
            metadata={"Software": "Backtesting presentation"},
        )
        fig.savefig(destination / (name + ".svg"), facecolor="white", metadata={"Date": None})
        plt.close(fig)

    daily = rows(files["tablas/equity_pnl_diario.csv"])
    fig, axes = plt.subplots(
        2,
        1,
        figsize=(10, 6.8),
        sharex=True,
        layout="constrained",
        gridspec_kw={"height_ratios": [2, 1]},
    )
    for strategy, label in NAMES.items():
        selected = [r for r in daily if r["strategy"] == strategy]
        dates = [date.fromisoformat(r["date"]) for r in selected]
        equity = [D(r["equity_usdt"]) for r in selected]
        peak, drawdown = D(10000), []
        for value in equity:
            peak = max(peak, value)
            drawdown.append(float((value / peak - 1) * 100))
        axes[0].plot(dates, [float(v) for v in equity], label=label, color=COLORS[strategy], lw=1.7)
        axes[1].plot(dates, drawdown, color=COLORS[strategy], lw=1.2)
    axes[0].set(title="Carteras continuas · enero de 2022–agosto de 2026", ylabel="Equity (USDT)")
    axes[0].legend(loc="upper left", frameon=False)
    axes[1].set(ylabel="Drawdown diario (%)", xlabel="Fecha UTC")
    for ax in axes:
        ax.grid(axis="y", alpha=0.2)
        ax.axvline(date(2024, 1, 1), color="#666666", lw=0.8, ls="--")
    fig.suptitle("10.000 USDT iniciales por cartera · futures_scaled · sin reinicios", fontsize=10)
    save(fig, "equity_drawdown")

    metrics = [r for r in rows(files["tablas/resultados_periodos.csv"]) if r["period"] == "full"]
    fields = (
        "spot_pnl_usdt",
        "futures_pnl_usdt",
        "funding_usdt",
        "fees_usdt",
        "liquidation_fees_usdt",
        "net_pnl_usdt",
    )
    labels = ("Spot", "Futuros", "Funding", "Comisiones", "Cargos de liquidación", "P&L neto")
    fig, ax = plt.subplots(figsize=(10, 4.8), layout="constrained")
    for offset, strategy in ((-0.19, "conditional"), (0.19, "permanent")):
        row = next(r for r in metrics if r["strategy"] == strategy)
        ax.barh(
            [i + offset for i in range(len(fields))],
            [float(row[f]) for f in fields],
            height=0.35,
            color=COLORS[strategy],
            label=NAMES[strategy],
        )
    ax.set(
        yticks=list(range(len(labels))),
        yticklabels=labels,
        xlabel="USDT acumulados",
        title="Composición del resultado · período continuo completo",
    )
    ax.invert_yaxis()
    ax.axvline(0, color="#666666", lw=0.8)
    ax.grid(axis="x", alpha=0.2)
    ax.legend(frameon=False, loc="lower right")
    fig.supxlabel(
        "Spot/futuros: realizado y no realizado. Slippage incluido en precios; no se resta otra vez.",
        fontsize=9,
    )
    save(fig, "composicion_pnl")

    h1 = [
        r for r in rows(files["tablas/h1_resumen.csv"]) if r["symbol"] not in {"BTCUSDT", "ETHUSDT"}
    ]
    h3 = [
        r for r in rows(files["tablas/h3_resumen.csv"]) if r["symbol"] not in {"BTCUSDT", "ETHUSDT"}
    ]
    periods = ("full", "2022-2023", "2024-2026-08")
    labels = ("Completo", "2022–2023", "2024–ago. 2026")
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), layout="constrained")
    for shift, field, label, color in (
        (-0.19, "mae_ewma", "EWMA", "#146C94"),
        (0.19, "mae_no_change", "No-change", "#878787"),
    ):
        axes[0].bar(
            [i + shift for i in range(3)],
            [float(next(r for r in h1 if r["period"] == p)[field]) * 10000 for p in periods],
            width=0.35,
            color=color,
            label=label,
        )
    axes[0].set(
        title="H1 · MAE del funding a 168 horas",
        ylabel="bps / 168 horas",
        xticks=range(3),
        xticklabels=labels,
    )
    axes[0].legend(frameon=False)
    values = [
        float(next(r for r in h3 if r["period"] == p)["opportunity_mean"]) * 10000 for p in periods
    ]
    bars = axes[1].bar(range(3), values, color="#38866C", width=0.65)
    axes[1].bar_label(bars, fmt="%.3f", padding=3)
    axes[1].set(
        title="H3 · oportunidad diaria media",
        ylabel="bps de funding previsto / 168 horas",
        xticks=range(3),
        xticklabels=labels,
        ylim=(0, max(values) * 1.2),
    )
    for ax in axes:
        ax.grid(axis="y", alpha=0.2)
    fig.supxlabel(
        "BTC y ETH con igual peso. Cortes de las mismas carteras; evidencia descriptiva.",
        fontsize=9,
    )
    save(fig, "hipotesis")


def readme(files):
    metrics = rows(files["tablas/resultados_periodos.csv"])
    financial = "\n".join(
        f"| {r['period']} | {NAMES[r['strategy']]} | {D(r['starting_equity_usdt']):.2f} | {D(r['final_equity_usdt']):.2f} | "
        f"{D(r['net_return']) * 100:.4f}% | {D(r['cagr']) * 100:.4f}% | {D(r['sharpe']):.4f} | {D(r['max_drawdown']) * 100:.4f}% |"
        for r in metrics
    )
    h1 = rows(files["tablas/h1_resumen.csv"])
    h3 = rows(files["tablas/h3_resumen.csv"])
    hypotheses = "\n".join(
        f"| {a['period']} | {D(a['mae_ewma']) * 10000:.6f} | {D(a['mae_no_change']) * 10000:.6f} | "
        f"{a['valid_observations']} / {a['excluded_observations']} | {D(b['opportunity_mean']) * 10000:.6f} | {b['valid_days']} / {b['excluded_days']} |"
        for a, b in zip(
            [r for r in h1 if r["symbol"] not in {"BTCUSDT", "ETHUSDT"}],
            [r for r in h3 if r["symbol"] not in {"BTCUSDT", "ETHUSDT"}],
            strict=True,
        )
    )
    return f"""# Resultados continuos de la Entrega 3

**01/01/2022–31/08/2026 UTC**, ambas carteras con `futures_scaled`. Los cortes
2022–2023 y 2024–agosto de 2026 pertenecen a las mismas trayectorias: sus saldos
y posiciones se arrastran, sin reinicios. [Índice de la entrega](../README.md).

## Rentabilidad y riesgo

| Período | Cartera | Equity inicial (USDT) | Equity final (USDT) | Retorno neto | CAGR | Sharpe | DD diario |
|---|---|---:|---:|---:|---:|---:|---:|
{financial}

![Equity y drawdown diarios](figuras/equity_drawdown.png)

![Composición del P&L](figuras/composicion_pnl.png)

Los retornos de cada corte usan su equity de entrada; no son sumables. Drawdown
y utilización se calculan con observaciones diarias. El P&L incluye realizado y
no realizado; funding es flujo neto y las comisiones llevan signo negativo.

## H1 y H3

| Período | MAE EWMA (bps/168h) | MAE no-change (bps/168h) | H1 válidas / excluidas | Oportunidad H3 (bps/168h) | H3 días válidos / excluidos |
|---|---:|---:|---:|---:|---:|
{hypotheses}

![Comparación de hipótesis](figuras/hipotesis.png)

H1 usa iguales observaciones por modelo y peso 50/50 entre BTC y ETH. H3 toma
el forecast semanal **completo** cuando pasan funding/costos, basis y operatividad,
cero cuando no pasan con datos conocidos; promedia 1.440 minutos diarios y después
ambos activos por igual. Excluye días incompletos y no usa posiciones de las carteras.
H1 tiene menor MAE descriptivo para EWMA; H2 no muestra superioridad de Sharpe
condicional; H3 es contraria a una caída de oportunidad y CAGR entre estos cortes.

## Tablas y evidencia

- [Resultados y P&L por tramo](tablas/resultados_periodos.csv),
  [equity diario](tablas/equity_diario.csv), [actividad](tablas/actividad.csv),
  [tiempo invertido](tablas/tiempo_invertido.csv) y [ciclos](tablas/ciclos.csv).
- [Filtros de entrada](tablas/filtros_entrada.csv) y
  [eventos por causa](tablas/eventos_por_causa.csv).
- 24/03/2023: [impacto diario](tablas/episodio_2023_03_24_resumen.csv) y
  [exposición sin cobertura](tablas/episodio_2023_03_24_exposicion.csv).
  Ambas carteras tuvieron 121 minutos sin cobertura; P&L diario de 35,908876 USDT
  en la condicional y 73,859494 USDT en la permanente.
- [H1 por activo y período](tablas/h1_resumen.csv),
  [H3 por activo y período](tablas/h3_resumen.csv) y
  [H3 diario conjunto](tablas/h3_diario_conjunto.csv).
- [Sensibilidad de los 15 marks](../../../data/research/continuous-marks-20260919/README.md)
  y [sensibilidad del precio de funding](../../../data/research/funding-price-sensitivity-20260920/README.md).
- [ZIP con evidencia completa](../paquete_actualizacion_entrega_3_continua.zip),
  [metodología](../../../docs/methodology.md) y [manifiesto de esta vista](manifest.json).

Las tablas de resumen conservan los bytes del ZIP. `equity_diario.csv` es una
proyección de cinco columnas sin redondear sus valores. Las tablas Markdown
redondean sólo la presentación. Los retornos CSV son fracciones (0,01 = 1%),
tiempos en segundos y cantidades monetarias en USDT. Los PNG se exportan a
300 dpi; sus versiones SVG están en la misma carpeta.

## Reproducción sin datos masivos

Desde la raíz del repositorio, con el entorno de `uv.lock` instalado:

```powershell
& '.\\.venv\\Scripts\\python.exe' -m scripts.publish_thesis --verify
& '.\\.venv\\Scripts\\python.exe' -m scripts.publish_thesis --output '.\\.superpowers\\presentacion_repro'
```

El segundo comando requiere un destino nuevo. Ambos leen el ZIP guardado; no
descargan datos ni ejecutan backtests. Su manifiesto registra el hash del ZIP,
de cada miembro fuente y de las tablas/figuras generadas.

Los resultados pertenecen a un escenario de investigación con reglas y tarifas
prescritas, ejecuciones por minuto y aproximaciones explícitas de marks/funding.
No reconstruyen el recorrido intraminuto ni garantizan una ejecución real.
Los escenarios de funding con posiciones fijas no incluyen cambios de margen
o decisiones; extrapolan errores de períodos con precios conocidos a otros períodos.
"""


def verify(destination):
    files, source_hash = load_source()
    manifest_bytes = (destination / "manifest.json").read_bytes()
    require(
        digest(manifest_bytes) == (destination / "manifest.sha256").read_text().strip(),
        "View manifest mismatch",
    )
    manifest = json.loads(manifest_bytes)
    require(manifest["source_zip_sha256"] == source_hash, "View points to a different ZIP")
    for name, expected in manifest["file_hashes"].items():
        path = (destination / name).resolve()
        require(
            path.is_relative_to(destination.resolve()) and digest(path.read_bytes()) == expected,
            "Published file differs: " + name,
        )
    for name, expected in manifest["source_members"].items():
        require(digest(files[name]) == expected, "Source member differs: " + name)
    for name in TABLES:
        relative = "tablas/" + name + ".csv"
        require(
            (destination / relative).read_bytes() == files[relative], "Source table bytes differ"
        )
    require(
        (destination / "tablas/equity_diario.csv").read_bytes()
        == daily_projection(files["tablas/equity_pnl_diario.csv"]),
        "Daily equity projection differs",
    )
    for path in (destination / "figuras").glob("*.png"):
        with Image.open(path) as img:
            require(
                all(abs(dpi - 300) < 0.01 for dpi in img.info["dpi"]), "Figure resolution differs"
            )
            img.verify()
    return dict(
        status="verified",
        source_zip_sha256=source_hash,
        original_tables=len(TABLES),
        daily_equity_rows=3408,
        figures=6,
        published_files=len(manifest["file_hashes"]),
    )


def publish(destination):
    require(not destination.exists(), "Use a new output directory; published evidence is immutable")
    files, source_hash = load_source()
    (destination / "tablas").mkdir(parents=True)
    source_members = {}
    for name in (*TABLES, "equity_pnl_diario"):
        relative = "tablas/" + name + ".csv"
        source_members[relative] = digest(files[relative])
        if name != "equity_pnl_diario":
            (destination / relative).write_bytes(files[relative])
    (destination / "tablas/equity_diario.csv").write_bytes(
        daily_projection(files["tablas/equity_pnl_diario.csv"])
    )
    figures(files, destination / "figuras")
    (destination / "README.md").write_text(readme(files), encoding="utf-8", newline="\n")
    manifest = dict(
        source_zip=ARCHIVE.name,
        source_zip_sha256=source_hash,
        source_members=source_members,
        generator="scripts/publish_thesis.py",
        generator_sha256=digest(Path(__file__).read_bytes()),
        file_hashes={
            p.relative_to(destination).as_posix(): digest(p.read_bytes())
            for p in sorted(destination.rglob("*"))
            if p.is_file()
        },
    )
    content = (json.dumps(manifest, sort_keys=True, indent=2) + "\n").encode()
    (destination / "manifest.json").write_bytes(content)
    (destination / "manifest.sha256").write_text(
        digest(content) + "\n", encoding="ascii", newline="\n"
    )
    return verify(destination)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--output", type=Path, default=PUBLISHED)
    args = parser.parse_args()
    destination = args.output.resolve()
    print(json.dumps(verify(destination) if args.verify else publish(destination), indent=2))


if __name__ == "__main__":
    main()
