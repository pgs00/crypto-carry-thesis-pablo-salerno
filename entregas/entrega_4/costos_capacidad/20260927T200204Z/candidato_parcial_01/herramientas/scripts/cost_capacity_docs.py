"""Spanish technical narrative and standalone figures for verified block-3 tables."""

from __future__ import annotations

from datetime import datetime

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from scripts.cost_capacity import CHANGES, STAGES  # noqa: E402
from scripts.return_capital.report import render_html  # noqa: E402
from scripts.signal_sensitivity_docs import fmt, table  # noqa: E402


def draw_figures(package, tables):
    folder = package/"figuras"
    folder.mkdir()
    colors = ["#183d55", "#c04c35", "#db9640", "#247d80", "#7d63a5"]
    plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False,
                        "axes.grid": True, "grid.alpha": .18, "figure.facecolor": "white"})
    for family, names in STAGES.items():
        rows = 2 if family == "capital" else 1
        fig, axes = plt.subplots(rows, 2, figsize=(12, 4.2*rows), squeeze=False, constrained_layout=True)
        for col, strategy in enumerate(("conditional", "permanent")):
            for index, scenario in enumerate(("BASE_E3", *names)):
                series = [r for r in tables["diario"] if r["scenario"] == scenario and r["strategy"] == strategy]
                if not series:
                    continue
                dates = [datetime.fromtimestamp(int(r["time_ns"])/1e9) for r in series]
                for row in range(rows):
                    values = [float(r["equity_usdt"]) if row == 0 else
                              100*float(r["equity_normalized_own_capital"]) for r in series]
                    axes[row, col].plot(dates, values, label=scenario, color=colors[index], lw=1.4)
                    axes[row, col].set_ylabel("Patrimonio (USDT)" if row == 0 else "Índice: capital propio = 100")
                    axes[row, col].set_title("Condicional" if strategy == "conditional" else "Permanente")
                    axes[row, col].legend(frameon=False, fontsize=8)
        fig.suptitle(f"Costos y capacidad · {family} · cierres diarios", fontsize=13)
        for ext in ("png", "svg"):
            fig.savefig(folder/f"{family}.{ext}", dpi=170)
        plt.close(fig)
    scenarios = ["BASE_E3", *CHANGES]
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), constrained_layout=True)
    for ax, strategy in zip(axes, ("conditional", "permanent")):
        rows = [next((r for r in tables["ejecucion_resumen"] if r["scenario"] == s and
                r["strategy"] == strategy and r["period"] == "full" and r["symbol"] == "PORTFOLIO"), None) for s in scenarios]
        for metric, marker, label in (("capacity_utilization_p50", "o", "Mediana"),
                                       ("capacity_utilization_p95", "s", "P95"),
                                       ("capacity_utilization_max", "|", "Máximo")):
            ax.plot([100*float(r[metric]) if r and r[metric] is not None else float("nan") for r in rows],
                    range(len(scenarios)), marker, label=label)
        ax.set_yticks(range(len(scenarios)), scenarios)
        ax.set_xlabel("Utilización del cupo (%)")
        ax.set_title("Condicional" if strategy == "conditional" else "Permanente")
        ax.legend(frameon=False)
    fig.suptitle("Claves instrumento/minuto con fill; un peso por clave")
    for ext in ("png", "svg"):
        fig.savefig(folder/f"capacidad_distribucion.{ext}", dpi=170)
    plt.close(fig)


def report(tables, index, partial):
    full = {(r["scenario"], r["strategy"]): r for r in tables["metricas"] if r["period"] == "full"}
    h2 = {(r["scenario"], r["period"]): r for r in tables["h2"]}
    h3 = {r["scenario"]: r for r in tables["h3_resumen"] if r["period"] == "full"}
    text = ["# Bloque 3: costos y capacidad\n",
        "**"+("Borrador parcial de desarrollo" if partial else "Dieciséis carteras nuevas y dos BASE reutilizadas verificadas")+".** "
        "Muestra continua UTC [01/01/2022,01/09/2026), BTCUSDT/ETHUSDT spot y perpetuos USD-M. "
        "Las ocho variantes se ejecutan separadas, sin parámetros adoptados del bloque 2. "
        "Las cifras son locales; este bloque no completa la Entrega 4.\n",
        "[Protocolo previo](documentos/protocolo.md) · [Encargo](documentos/encargo_usuario.md) · "
        "[Registro de corridas](indice_corridas.json) · [Verificación](README.md)\n",
        "## Selección fija y costos realizados\n",
        "El modo explícito `base_e3_total` fija **34 pb** sólo para la condición de entrada `forecast > 0.0034`. "
        "Se activa en C02/C03/S02/S05. Renovar requiere `forecast > 0`; la permanente omite ambos requisitos de funding, "
        "manteniendo los restantes. Los modos previos conservan su semántica y digest. "
        "Sizing, presupuesto, comisiones, inventario y garantías usan los costos del escenario: no se fijan decisiones ni cantidades. "
        "Es una regla de selección sin recalibrar ante mayores fricciones.\n",
        table(["Escenario", "Fee spot", "Fee futuros", "Slippage/orden", "Selección"], [
            ["BASE", "0,10%", "0,05%", "1 pb", "34 pb"], ["C02", "0,20%", "0,10%", "2 pb", "34 pb"],
            ["C03", "0,30%", "0,15%", "3 pb", "34 pb"], ["S02", "0,10%", "0,05%", "2 pb", "34 pb"],
            ["S05", "0,10%", "0,05%", "5 pb", "34 pb"]]),
        "C02/C03 son estrés conjunto de comisiones ordinarias y deslizamiento; S02/S05 aíslan deslizamiento. "
        "Compras spot pagan comisión en base, con salida de caja igual al importe bruto ejecutado. "
        "Slippage y tick están incluidos en precio: su diagnóstico no vuelve a restarse del P&L. "
        "La tasa especial de liquidación no se multiplica.\n",
        "## Muestra completa\n",
        table(["Escenario", "Cartera", "Capital inicial", "Equity final", "P&L", "Retorno", "CAGR365", "Sharpe RF=0", "DD diario"],
            [[s, st, fmt(r["starting_equity_usdt"], digits=0), fmt(r["final_equity_usdt"], digits=2),
              fmt(r["net_pnl_usdt"], digits=2), fmt(r["net_return"], True), fmt(r["cagr"], True),
              fmt(r["sharpe"]), fmt(r["max_drawdown"], True)] for (s, st), r in full.items()]),
        "## Lectura por familia\n"]
    for family, names in STAGES.items():
        text.append("### "+family.capitalize()+"\n")
        for name in names:
            for strategy in ("conditional", "permanent"):
                if (name, strategy) not in full:
                    continue
                r, b = full[name, strategy], full["BASE_E3", strategy]
                ex = next(x for x in tables["ejecucion_resumen"] if x["scenario"] == name and x["strategy"] == strategy and x["period"] == "full" and x["symbol"] == "PORTFOLIO")
                text.append(f"**{name} / {strategy}:** P&L {fmt(r['net_pnl_usdt'], digits=2)} USDT; "
                    f"retorno {fmt(r['net_return'], True)}, diferencia frente a BASE "
                    f"{fmt((r['net_return']-b['net_return'])*100, digits=4)} puntos porcentuales. "
                    f"Comisiones {fmt(-r['fees_usdt'], digits=2)} USDT, funding {fmt(r['funding_usdt'], digits=2)} USDT. "
                    f"Capital utilizado medio diario {fmt(r['capital_deployed_usdt_daily_mean'], digits=2)} USDT "
                    f"({fmt(r['capital_utilization_daily_mean'], True)}); actividad sin polvo {fmt(r['invested_fraction'], True)}. "
                    f"Órdenes completas/parciales/sin fill: {ex['orders_complete']}/{ex['orders_partial']}/{ex['orders_no_fill']}; "
                    f"máxima utilización del cupo {fmt(ex['capacity_utilization_max'], True)}.\n")
        text.append(f"![Trayectorias {family}](figuras/{family}.png)\n")
    text += ["Los mayores costos pueden cambiar sizing, fills y la trayectoria; no se exige monotonicidad del P&L. "
        "Las diferencias absolutas de A050/A100 incluyen su mayor escala. Sus curvas normalizadas usan su propio capital inicial; "
        "no se multiplican las cantidades BASE por cinco o diez ni se divide CAGR por utilización.\n",
        "## Capacidad, reglas y exposición\n",
        "El cupo es agregado por cartera/activo/mercado/minuto. Compras y ventas consumen volumen bruto. "
        "Participación realizada = cantidad bruta / volumen base; utilización = cantidad bruta / (límite × volumen). "
        "Las distribuciones tienen un peso por clave con fill y volumen positivo; no suman BTC y ETH en una unidad inventada. "
        "Estados terminales de órdenes, eventos de fill parcial y reintentos son poblaciones distintas. "
        "El volumen elegible posterior se consulta sólo para auditar la ejecución.\n",
        "![Distribución del uso del cupo](figuras/capacidad_distribucion.png)\n",
        "[Órdenes completas](tablas/ordenes.csv), [claves de capacidad](tablas/capacidad.csv), "
        "[fills/ledger](tablas/fills_conciliados.csv), [causas de faltantes](tablas/causas_faltantes.csv), "
        "[demoras por ciclo](tablas/demoras_ciclos.csv), [tramos](tablas/tramos_margen_estados.csv). "
        "El auditor aplica el contrato original a todas las órdenes de este motor, incluidas las que llevan propósito `liquidate`; "
        "el código inspeccionado no incorpora una excepción autónoma de volumen para fills forzosos del exchange. "
        "No se añadió ninguna excepción.\n",
        "Volumen cero, cierre documentado, presupuesto agotado, step y filtros de reglas se separan. "
        "Cuando los registros no permiten identificar separadamente fondos, inventario o reservas pendientes, la causa conserva "
        "`funds_inventory_or_reservations_not_separately_identified`; no se afirma falta de volumen ni se reconstruye una reserva exacta inexistente.\n",
        "Los [cinco casos de mayor cupo y cinco de mayor duración descubierta por cartera](tablas/casos_extremos.csv) "
        "usan el orden y desempates fijados antes de resultados. El [catálogo completo](tablas/episodios_descubiertos.csv) "
        "conserva todos los episodios; los vínculos entre ambos grupos evitan sumar casos repetidos. "
        "La exposición se clasifica sobre toda la trayectoria antes de cortar años; la cartera integra la unión BTC/ETH. "
        "El polvo sigue valorado en equity. Los estados de margen persistidos no constituyen una nueva serie intradía.\n",
        "## H1, H2 y H3\n",
        "H1 conserva una única población BASE autenticada de 10.224 observaciones (10.180 válidas y 44 excluidas), "
        "con MAE EWMA 6,298978 frente a no-change 8,703322 pb/168 h, peso BTC/ETH 50/50. "
        "Se verifica igualdad de forecast/targets por cartera; reutilizarla no añade observaciones independientes. "
        "La [auditoría de invariancias](tablas/invariancias.csv) separa forecast, inputs de oportunidad y agregado H3.\n",
        "La oportunidad de mercado conserva 34 pb y los mismos inputs. La lectura completa de H3 usa, sin embargo, los nuevos CAGR. "
        "H2 exige CAGR condicional positivo y Sharpe superior a la permanente del mismo escenario/período; SOFR no participa.\n",
        table(["Escenario", "H2 full", "Motivo", "H3 entre cortes", "Oportunidad 2022–23", "Oportunidad 2024–ago26"], [
            [s, h2[s, "full"]["verdict"], h2[s, "full"].get("reason", ""), h3[s]["h3_descriptive"],
             fmt(next(r['opportunity_mean_bps'] for r in tables['h3_resumen'] if r['scenario']==s and r['period']=='2022-2023')),
             fmt(next(r['opportunity_mean_bps'] for r in tables['h3_resumen'] if r['scenario']==s and r['period']=='2024+'))]
            for s in dict.fromkeys(r['scenario'] for r in tables['metricas']) if (s,'full') in h2]),
        "H3: si oportunidad y CAGR bajan, favorable; si ambos suben, contraria; demás casos evaluables, mixta. "
        "Las métricas faltantes conservan ND y motivo. No se impone la conclusión del bloque 2.\n",
        "## Años y capital heredado\n",
        table(["Escenario", "Cartera", "Año", "Inicio", "P&L", "Retorno", "Uso medio", "Actividad"],
            [[r['scenario'],r['strategy'],r['period'],fmt(r['starting_equity_usdt'],digits=2),fmt(r['net_pnl_usdt'],digits=2),
              fmt(r['net_return'],True),fmt(r['capital_utilization_daily_mean'],True),fmt(r['invested_fraction'],True)]
             for r in tables['metricas'] if r['period'] in {'2022','2023','2024','2025','2026'}]),
        "2026 abarca enero–agosto (243 días); 2024, 366 días. Retornos de tramos no se suman. "
        "Los [ocho períodos](tablas/metricas.csv), [deltas frente a BASE](tablas/deltas.csv), "
        "[componentes](tablas/componentes_periodo.csv) y [cierres](tablas/diario.csv) conservan denominadores reales, "
        "CAGR365, Sharpe RF=0/ddof=1, volatilidad, drawdown diario y residual contable. "
        "Sin volatilidad muestral, Sharpe es ND; garantías no son nocional ni caja libre.\n",
        "## Alcance de la evidencia\n",
        "Se recalculan contabilidad y ejecución de las variantes; BASE, H1 y oportunidad de mercado se reutilizan con identidad verificada. "
        "Los paquetes previos permanecen sellados. Los drawdowns de este bloque son diarios; no se atribuye a una variante el riesgo intradía BASE. "
        "Se conservan las aproximaciones originales de marks/funding y las reglas prescritas, sin afirmar historia certificada del exchange. "
        "Las velas de un minuto y sus cupos no estiman empíricamente cola, spread o impacto de mercado. "
        "Que funcionen los tamaños probados no demuestra escalabilidad ilimitada, ni permite optimizar un umbral. "
        "No hay remuneración de caja/garantías, nuevos cálculos SOFR, inferencia estadística, Word/PDF o publicación remota.\n"]
    return "\n".join(text)


def write_docs(package, tables, index, partial=False):
    draw_figures(package, tables)
    text = report(tables, index, partial)
    (package/"reporte.md").write_text(text, encoding="utf8")
    (package/"reporte.html").write_text(render_html(text), encoding="utf8")
    summary = "# Síntesis del bloque 3\n\n"+"\n".join(text.split("## Lectura por familia")[1].split("## Capacidad,")[0].splitlines()[:35])
    (package/"sintesis.md").write_text(summary, encoding="utf8")
    readme = """# Evidencia de costos y capacidad

[Reporte](reporte.md) · [HTML](reporte.html) · [Síntesis](sintesis.md)

Verificación offline desde cualquier ruta con Python 3.14 y las dependencias
fijadas en `herramientas/pyproject.toml` y `herramientas/uv.lock`:

```powershell
python -B -X utf8 herramientas/scripts/verify_cost_capacity.py --package . --output ../auditoria_nueva.json
```

El destino debe ser nuevo y externo al sello. No se exige HEAD ni índice Git.
El verificador recalcula cierres/períodos, exposición corregida, H2/H3,
órdenes/fills/ledger, tarifas/precios y capacidad desde ventanas incluidas.
H1 y oportunidad BASE se autentican y se comprueba igualdad de inputs y agregados;
no se cuentan 18 poblaciones independientes. No se ejecuta el motor ni se vuelve
a recorrer cada minuto H3. Constructor/verificador comparten lógica declarada.

Para contrastar nuevamente las ventanas contra archivos masivos locales:

```powershell
python -B -X utf8 herramientas/scripts/verify_cost_capacity.py --package . --data-root D:/Backtesting --output ../auditoria_local_nueva.json
```

Los volúmenes incluidos son extractos exactos por ventana solicitada, ligados
a partición, SHA-256 y manifiesto autenticado. El modo offline comprueba sus
denominadores y la ejecución; no lee una serie masiva ausente. Las corridas
completas permanecen bajo la raíz local indicada en `dependencias.json`.

`codigo_ejecutado` conserva la primera identidad congelada. `codigo_runner_v2`
y protocolos v1/v2 documentan el endurecimiento técnico de recuperación después
del lanzamiento de C02, sin cambio de identidad económica. Las configuraciones,
comandos, intentos, tiempos, RAM, fallos de pruebas y correcciones se conservan.
La incompatibilidad histórica de inventario/config.py continúa documentada;
no se usó para ocultar los cambios de este bloque.
"""
    (package/"README.md").write_text(readme, encoding="utf8")
