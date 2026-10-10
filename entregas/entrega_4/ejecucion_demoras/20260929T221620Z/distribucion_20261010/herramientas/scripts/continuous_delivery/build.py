"""Build the continuous Entrega 3 evidence from saved runs, never replay strategies."""

import argparse
import json
import shutil
import zipfile
from collections import defaultdict
from pathlib import Path

from crypto_carry.config import DAY, Config, timestamp
from crypto_carry.costs import cycle_cost
from crypto_carry.data.prescribed import prescribed_rules
from scripts.verify_continuous_marks import verify as verify_continuous

from .common import PERIODS, SYMBOLS, decimal, read_rows, sha256, write_json, write_rows, yes
from .diagnostics import (
    check_daily_cashflows,
    event_counts,
    filter_summary,
    outage_fill_audit,
    outage_market,
    outage_summary,
)
from .hypotheses import (
    checked_forecasts,
    funding_history,
    h1_observations,
    h1_summaries,
    market_opportunity,
)
from .portfolio import (
    activity_summary,
    cycle_rows,
    exposure_intervals,
    exposure_summary,
    financial_daily,
    period_financials,
)

STUDY = "continuous_marks_b417d512a416058238193c79"
REPO = Path(__file__).resolve().parents[2]


def tagged(rows, strategy, run_id):
    return [dict(row, strategy=strategy, source_run_id=run_id) for row in rows]


def h3_summary(days, joint, financials):
    result = []
    for period, start, end in PERIODS:
        cagr = next(
            r["cagr"]
            for r in financials
            if r["strategy"] == "conditional" and r["period"] == period
        )
        for symbol in (*SYMBOLS, "EQUAL_WEIGHT"):
            selected = [
                r
                for r in (joint if symbol == "EQUAL_WEIGHT" else days)
                if start <= int(r["time_ns"]) < end
                and (symbol == "EQUAL_WEIGHT" or r["symbol"] == symbol)
            ]
            valid = [r for r in selected if yes(r["complete"])]
            result.append(
                dict(
                    period=period,
                    symbol=symbol,
                    expected_days=(end - start) // DAY,
                    valid_days=len(valid),
                    excluded_days=len(selected) - len(valid),
                    opportunity_mean=sum((decimal(r["opportunity"]) for r in valid), decimal(0))
                    / len(valid)
                    if valid
                    else None,
                    eligible_fraction=sum(
                        (decimal(r["eligible_fraction"]) for r in valid), decimal(0)
                    )
                    / len(valid)
                    if valid
                    else None,
                    conditional_cagr=cagr,
                )
            )
    early = next(r for r in result if r["period"] == "2022-2023" and r["symbol"] == "EQUAL_WEIGHT")
    late = next(
        r for r in result if r["period"] == "2024-2026-08" and r["symbol"] == "EQUAL_WEIGHT"
    )
    if any(
        r["excluded_days"] or r["valid_days"] != r["expected_days"] or r["conditional_cagr"] is None
        for r in (early, late)
    ):
        verdict = "no_concluyente_por_cobertura"
    elif (
        late["opportunity_mean"] < early["opportunity_mean"]
        and late["conditional_cagr"] < early["conditional_cagr"]
    ):
        verdict = "favorable_descriptiva"
    elif (
        late["opportunity_mean"] > early["opportunity_mean"]
        and late["conditional_cagr"] > early["conditional_cagr"]
    ):
        verdict = "contraria_descriptiva"
    else:
        verdict = "mixta"
    for row in result:
        row["h3_verdict"] = verdict
    return result


def compare_saved_h1(rows, saved):
    original = {(r["symbol"], int(r["time_ns"])): r for r in saved}
    if set(original) != {(r["symbol"], int(r["time_ns"])) for r in rows}:
        raise ValueError("H1 source cohort changed")
    for row in rows:
        old = original[row["symbol"], row["time_ns"]]
        if yes(row["horizon_valid"]) != yes(old["horizon_valid"]) or row["reason"] != old["reason"]:
            raise ValueError("Recomputed H1 exclusions differ from saved evidence")
        if row["horizon_valid"]:
            for field in ("realized", "absolute_error_ewma", "absolute_error_no_change"):
                if abs(decimal(row[field]) - decimal(old[field])) > decimal("1e-14"):
                    raise ValueError(f"Recomputed H1 label/error differs: {field}")


def readme(tables, verification):
    summary = tables["resultados_periodos"]
    h1 = tables["h1_resumen"]
    h3 = tables["h3_resumen"]
    outage = tables["episodio_2023_03_24_resumen"]
    lines = [
        "# Actualización de la Entrega 3: backtest continuo",
        "",
        "Evidencia de las carteras condicional y permanente, **01/01/2022–31/08/2026 UTC**,",
        "con `futures_scaled` como método principal. Se reutilizaron las corridas guardadas:",
        "no se ejecutaron estrategias nuevas ni se reiniciaron carteras en 2024. Los cortes",
        "son `[2022-01-01, 2024-01-01)` y `[2024-01-01, 2026-09-01)`. Capital inicial:",
        "10.000 USDT por cartera. Los CSV usan punto decimal, coma como separador y UTF-8.",
        "",
        "| Período | Cartera | Equity al inicio / final (USDT) | Retorno neto | CAGR | Drawdown diario |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for r in summary:
        lines.append(
            f"| {r['period']} | {r['strategy']} | {r['starting_equity_usdt']:.2f} / {r['final_equity_usdt']:.2f} | {r['net_return']:.4%} | {r['cagr']:.4%} | {r['max_drawdown']:.4%} |"
        )
    lines += [
        "",
        "## H1 y H3",
        "",
        "H1 evalúa todas las señales con historia válida, sin condicionarlas a entrada,",
        "basis, saldo o posición. El objetivo suma las tasas liquidadas en `(s, s+168h]`.",
        "La EWMA usa 336 horas y vida media de 24 horas, normalizada por intervalos reales;",
        "no-change extrapola la última tasa por su duración. El MAE conjunto es la media",
        "de los MAE de BTC y ETH (50/50), sobre muestras emparejadas. Los cortes se asignan",
        "por fecha de señal: un horizonte de diciembre de 2023 puede terminar en enero de",
        "2024; sólo se excluyen horizontes fuera de la muestra global o no verificables.",
        "",
        "| H1, igual peso | MAE EWMA (bps/168h) | MAE no-change (bps/168h) | Válidas / excluidas, ambos activos |",
        "|---|---:|---:|---:|",
    ]
    for r in h1:
        if r["symbol"] == "EQUAL_WEIGHT":
            lines.append(
                f"| {r['period']} | {r['mae_ewma'] * 10000:.6f} | {r['mae_no_change'] * 10000:.6f} | {r['valid_observations']} / {r['excluded_observations']} |"
            )
    lines += [
        "",
        "H3 se recalculó una sola vez desde el mercado, independiente de las carteras.",
        "Cada minuto UTC usa el último forecast disponible, velas cerradas publicadas al",
        "minuto siguiente, mark verificado, basis inclusivo `[0, 0.005]`, volumen positivo",
        "y reglas operativas del escenario. Si el forecast supera el costo de ciclo",
        "vigente, el valor elegible es **todo el forecast**, sin restarle costos. Si los",
        "datos son conocidos pero falla un filtro, vale cero. Se promedian los 1.440",
        "minutos por activo y después BTC/ETH 50/50. Un dato requerido desconocido excluye",
        "todo el día conjunto; las ausencias documentadas del cierre spot son ceros",
        "operativos, no datos inventados. La disponibilidad conserva milisegundos: un",
        "forecast publicado a 00:01:00.006 recién puede usarse en la grilla de 00:02.",
        "",
        "| H3, igual peso | Oportunidad media (bps/168h) | Frecuencia elegible | Días válidos / excluidos |",
        "|---|---:|---:|---:|",
    ]
    for r in h3:
        if r["symbol"] == "EQUAL_WEIGHT":
            lines.append(
                f"| {r['period']} | {r['opportunity_mean'] * 10000:.6f} | {r['eligible_fraction']:.4%} | {r['valid_days']} / {r['excluded_days']} |"
            )
    lines += [
        "",
        f"Lectura descriptiva H3: **{h3[0]['h3_verdict']}** al comparar oportunidad y CAGR condicional.",
        "Los CSV contienen resultados por activo, muestras válidas y motivos de exclusión.",
        "Los horizontes H1 se solapan; un menor MAE no demuestra significancia ni rentabilidad.",
        "",
        "## Contabilidad, actividad y episodio de marzo de 2023",
        "",
        "El P&L diario y por tramo es la diferencia de componentes acumulados de las corridas:",
        "spot y futuros incluyen realizado y variación de no realizado; funding es flujo neto;",
        "fees y cargos de liquidación llevan signo negativo. El slippage es informativo y",
        "ya está en los precios: no se resta otra vez. Cada día y cada tramo reconcilian",
        "con el cambio de equity, con tolerancia de 1e-8 USDT. Las tasas y retornos están",
        "en fracciones: 0.01 equivale a 1%; un basis point equivale a 0.0001.",
        "",
        "Tiempo invertido excluye polvo de spot: carry cubierto requiere ambas patas y",
        "descalce ≤ 0.5%; inventario negociable restante es exposición sin cobertura",
        "completa. Los intervalos se recortan en los límites del tramo sin abrir ciclos",
        "nuevos. Los segundos por activo pueden sumarse; los de cartera miden la unión",
        "temporal y no duplican exposición simultánea. El polvo se identifica por los",
        "estados terminales/metadatos conservados, sin volver a simular filtros de venta.",
        "Capital utilizado al cierre diario = valor de spot + colateral aislado;",
        "utilización = ese importe/equity. Las medias son de cierres diarios, no intradía.",
        "",
        "Se distinguen intentos de apertura, aperturas completas, ciclos cerrados, fallas",
        "y solicitudes de cierre. Un ciclo termina en su primer evento terminal; pedidos",
        "repetidos y reintentos siguen visibles en eventos y órdenes. En el comparador",
        "permanente el filtro de funding es diagnóstico, **no un rechazo aplicado**.",
        "",
        "El 24/03/2023 los futuros se cerraron a las 12:00 UTC y el spot a las 14:01:",
        "121 minutos sin cobertura, ETH en la condicional y BTC+ETH en la permanente.",
        "El detalle conserva velas observadas de 11:20 a 14:10 UTC, volumen cero, filas",
        "ausentes documentadas, órdenes, reintentos, fills, funding y ledger.",
        "",
        "| Cartera | P&L diario (USDT) | Funding diario (USDT) | Comisiones diarias (USDT) | Minutos de cartera con exposición sin cobertura |",
        "|---|---:|---:|---:|---:|",
    ]
    for r in outage:
        lines.append(
            f"| {r['strategy']} | {r['net_pnl_usdt']:.6f} | {r['funding_usdt']:.6f} | {r['fees_usdt']:.6f} | {r['any_unhedged_seconds'] / 60:.2f} |"
        )
    lines += [
        "",
        "La proporción del P&L diario sobre beneficios positivos del período/año es una",
        "comparación descriptiva, no atribución causal ni una cartera simulada sin el episodio.",
        "",
        "## Archivos, fuentes y verificación",
        "",
        "- [Catálogo de CSV](catalogo.csv): contenido, unidades y número de filas por archivo.",
        "- `tablas/`: equity/P&L diarios, resultados por tramo, actividad, ciclos, exposición,",
        "  H1, H3 y diagnósticos. `h3_grupos_forecast.csv` contiene los conteos y sumas",
        "  suficientes para recalcular cada día; no se incluyen millones de velas.",
        "- `evidencia/`: registros financieros compactos y revisión del episodio;",
        "  `h3_muestra_minutos.csv` tiene una muestra fija diaria, cambios de forecast y",
        "  todo el 24/03/2023, no una muestra seleccionada por rendimiento.",
        "- [Sensibilidad previa de los 15 marks](data/research/continuous-marks-20260919/README.md):",
        "  copiada con sus bytes y hashes originales, incluidos ambos métodos.",
        "- [Fuentes y hashes](fuentes.json), `fuentes/` y `codigo/`: manifiestos originales,",
        "  parámetros, supuestos y código del posprocesamiento. Los datos de mercado",
        "  proceden de los archivos públicos de Binance ya descargados y normalizados.",
        "",
        f"Verificación local: {verification['source_files_verified']} archivos fuente, las cuatro corridas",
        "de sensibilidad y sus parámetros. El ZIP omite los datos masivos de Binance.",
        "Desde la carpeta extraída, `python verificar.py` valida hashes y recalcula H1,",
        "H3 y las conciliaciones del subconjunto incluido; no requiere D: ni Binance.",
        "Para regenerar el paquete desde el repositorio y las fuentes locales:",
        "",
        "```powershell",
        "& '.\\.venv\\Scripts\\python.exe' -m scripts.continuous_delivery.build --root 'D:\\Backtesting' --destination 'D:\\Backtesting\\outputs\\entrega3_continua_nueva' --zip '.\\entregas\\entrega_3\\paquete_actualizacion_continua_nuevo.zip'",
        "```",
        "",
        "Usar destinos nuevos conserva las evidencias anteriores. El código incluido en",
        "`codigo/scripts/` es el mismo generador; utiliza el entorno y dependencias fijados",
        "en `codigo/pyproject.toml` y `codigo/uv.lock`. Los manifiestos fuente conservan rutas",
        "relativas al root local y referencias a archivos grandes que no forman parte del ZIP.",
        "",
        "## Límites",
        "",
        "Es un escenario de investigación con reglas y tarifas prescritas, ejecución",
        "`next_minute_vwap`, funding aproximado cuando falta el mark de cobro y 15 marks",
        "estimados mediante `futures_scaled`. No certifica reconstrucción histórica exacta.",
        "El drawdown es diario y los marks cerrados no reconstruyen el recorrido intraminuto.",
        "La comparación de regímenes es descriptiva y no identifica causalidad estructural.",
        "Se conservaron todos los resultados, incluso los contrarios a las hipótesis.",
        "",
    ]
    return "\n".join(lines)


def build(root, destination, archive):
    if destination.exists():
        raise ValueError("Use a new destination to preserve previous evidence")
    if archive.exists():
        raise ValueError("Use a new ZIP name to preserve previous evidence")
    study = root / "outputs" / STUDY
    print("Verifying saved runs and local input hashes...", flush=True)
    verification = verify_continuous(root, study)
    index = json.loads((study / "study_index.json").read_text(encoding="utf-8"))
    runs = {
        r["strategy"]: root / r["path"] for r in index["runs"] if r["method"] == "futures_scaled"
    }
    manifests = {
        s: json.loads((p / "run_manifest.json").read_text(encoding="utf-8"))
        for s, p in runs.items()
    }
    config = Config.from_dict(manifests["conditional"]["config"])
    if config != Config.from_dict(manifests["permanent"]["config"]):
        raise ValueError("Economic parameters differ between primary portfolios")
    processed_path = root / config.data_dir / "manifests/processed.json"
    processed = json.loads(processed_path.read_text(encoding="utf-8"))
    destination.mkdir(parents=True)
    tables, evidence = defaultdict(list), defaultdict(list)
    sources = dict(
        study=STUDY,
        method="futures_scaled",
        config=config.to_dict(),
        source_runs={s: p.name for s, p in runs.items()},
        files={},
    )

    def load(run, name):
        path = run / name
        sources["files"][path.relative_to(root).as_posix()] = sha256(path)
        return read_rows(path)

    for strategy, run in runs.items():
        print(f"Extracting continuous accounting and execution: {strategy}", flush=True)
        data = {
            name: load(run, name + (".csv" if name == "equity_daily" else ".parquet"))
            for name in (
                "equity_daily",
                "positions",
                "signals",
                "fills",
                "orders",
                "risk_events",
                "ledger",
                "funding_payments",
                "renewal_diagnostics",
            )
        }
        daily, assets = financial_daily(data["equity_daily"], config)
        intervals = exposure_intervals(
            data["positions"],
            timestamp(config.start),
            timestamp(config.end),
            config.hedge_tolerance,
        )
        cycles = cycle_rows(data["risk_events"], timestamp(config.end))
        check_daily_cashflows(
            daily, data["funding_payments"], data["ledger"], config.accounting_tolerance
        )
        new_tables = dict(
            equity_pnl_diario=daily,
            pnl_diario_activo=assets,
            resultados_periodos=period_financials(daily, assets, config, PERIODS),
            exposicion_intervalos=intervals,
            tiempo_invertido=exposure_summary(intervals, PERIODS),
            ciclos=cycles,
            actividad=activity_summary(
                data["fills"], data["orders"], data["risk_events"], cycles, PERIODS
            ),
            filtros_entrada=filter_summary(data["signals"], PERIODS),
            eventos_por_causa=event_counts(data["risk_events"], PERIODS),
        )
        episode, durations = outage_summary(daily, intervals, PERIODS)
        new_tables["episodio_2023_03_24_resumen"] = [episode]
        new_tables["episodio_2023_03_24_exposicion"] = durations
        for name, rows in new_tables.items():
            tables[name].extend(tagged(rows, strategy, run.name))
        for name, rows in data.items():
            if name != "equity_daily":
                evidence[name].extend(tagged(rows, strategy, run.name))
            selected = [r for r in rows if str(r.get("timestamp_utc", "")).startswith("2023-03-24")]
            if selected:
                evidence["episodio_2023_03_24_" + name].extend(tagged(selected, strategy, run.name))
        saved = load(run, "metrics.csv")
        for result in new_tables["resultados_periodos"]:
            period = "2024+" if result["period"] == "2024-2026-08" else result["period"]
            old = next(r for r in saved if r["period"] == period)
            for field in ("net_return", "cagr", "sharpe", "max_drawdown"):
                if abs(decimal(result[field]) - decimal(old[field])) > decimal("1e-12"):
                    raise ValueError("Recomputed financial metrics differ from saved portfolio")
        target = destination / "fuentes" / run.name
        target.mkdir(parents=True)
        for name in (
            "run_manifest.json",
            "run_manifest.sha256",
            "effective_config.toml",
            "research_assumptions.json",
        ):
            shutil.copyfile(run / name, target / name)
            sources["files"][(run / name).relative_to(root).as_posix()] = sha256(run / name)

    primary_signals = [r for r in evidence["signals"] if r["strategy"] == "conditional"]
    other_signals = [r for r in evidence["signals"] if r["strategy"] == "permanent"]
    common_keys = ("symbol", "time_ns", "anchor", "history_start", "forecast", "no_change", "valid")
    if [[r[k] for k in common_keys] for r in primary_signals] != [
        [r[k] for k in common_keys] for r in other_signals
    ]:
        raise ValueError("H1 forecast inputs differ between portfolios")
    print("Recomputing causal forecasts and H1 labels...", flush=True)
    history = funding_history(root, processed)
    schedules, forecast_audit = checked_forecasts(primary_signals, history, config)
    observations = h1_observations(primary_signals, history, config)
    compare_saved_h1(observations, load(runs["conditional"], "forecast_evaluation.csv"))
    tables["h1_observaciones"] = observations
    tables["h1_resumen"] = h1_summaries(observations, PERIODS)
    evidence["forecast_publicaciones"] = [r for schedule in schedules.values() for r in schedule]
    write_json(destination / "verificacion_forecasts.json", forecast_audit)
    rules = prescribed_rules(config)
    costs = [
        cycle_cost(
            rules.get(s, "spot", timestamp(config.start)),
            rules.get(s, "futures", timestamp(config.start)),
            config,
        )
        for s in SYMBOLS
    ]
    if len(set(costs)) != 1 or config.analysis_mode != "prescribed_research":
        raise ValueError(
            "This verified package requires the current constant prescribed rule scenario"
        )
    days, joint, groups, sample = market_opportunity(root, processed, schedules, config, costs[0])
    tables["h3_diario_activo"], tables["h3_diario_conjunto"] = days, joint
    tables["h3_grupos_forecast"] = groups
    tables["h3_resumen"] = h3_summary(days, joint, tables["resultados_periodos"])
    evidence["h3_muestra_minutos"] = sample
    old_h3 = load(runs["conditional"], "opportunity_daily.csv")
    differences = []
    for row, old in zip(joint, old_h3, strict=True):
        if row["date"] != old["date"]:
            raise ValueError("H3 daily date alignment differs")
        differences.append(
            dict(
                date=row["date"],
                saved_complete=yes(old["complete"]),
                recomputed_complete=row["complete"],
                saved_opportunity=old["opportunity"],
                recomputed_opportunity=row["opportunity"],
                difference=decimal(row["opportunity"]) - decimal(old["opportunity"]),
            )
        )
    evidence["h3_contraste_guardado"] = differences
    evidence["episodio_2023_03_24_velas"] = outage_market(root, processed)
    for strategy, run in runs.items():
        rows = [r for r in evidence["fills"] if r["strategy"] == strategy]
        evidence["episodio_2023_03_24_fills_verificados"].extend(
            tagged(
                outage_fill_audit(rows, evidence["episodio_2023_03_24_velas"], config),
                strategy,
                run.name,
            )
        )
    funding_audit = json.loads(
        (runs["conditional"] / "funding_mark_audit.json").read_text(encoding="utf-8")
    )
    evidence["funding_mercado_y_marks"] = [
        {k: v for k, v in r.items() if k not in {"strategy", "funding_filter_enabled"}}
        for r in funding_audit["consumed"]
    ]
    for entry in processed["entries"]:
        if entry["dataset"] in {"minute_bars", "funding", "marks"}:
            sources["files"][entry["path"]] = entry["sha256"]
    sources["files"][processed_path.relative_to(root).as_posix()] = sha256(processed_path)
    sources["files"][
        (runs["conditional"] / "funding_mark_audit.json").relative_to(root).as_posix()
    ] = sha256(runs["conditional"] / "funding_mark_audit.json")
    write_json(destination / "fuentes.json", sources)
    write_json(destination / "verificacion_local.json", verification)
    for folder, mapping in (("tablas", tables), ("evidencia", evidence)):
        for name, rows in mapping.items():
            write_rows(destination / folder / f"{name}.csv", rows)
    (destination / "README.md").write_text(
        readme(tables, verification), encoding="utf-8", newline="\n"
    )
    copy_support(destination)
    catalog = []
    for path in sorted(destination.rglob("*.csv")):
        if path.parts[-2] not in {"tablas", "evidencia"}:
            continue
        rows = read_rows(path)
        catalog.append(
            dict(
                file=path.relative_to(destination).as_posix(),
                rows=len(rows),
                units="USDT: *_usdt; base asset: spot/short/quantity; seconds: *_seconds; UTC ns: *_ns/time_ns; rates/returns/ratios: fractions; opportunity/MAE: 168h rate fraction; counts: integer",
                columns=";".join(rows[0]) if rows else "",
            )
        )
    write_rows(destination / "catalogo.csv", catalog)
    files = {
        p.relative_to(destination).as_posix(): sha256(p)
        for p in sorted(destination.rglob("*"))
        if p.is_file()
    }
    write_json(
        destination / "manifest.json",
        dict(
            kind="continuous_entrega3_evidence",
            study=STUDY,
            primary_method="futures_scaled",
            source_run_ids={s: p.name for s, p in runs.items()},
            file_hashes=files,
        ),
    )
    (destination / "manifest.sha256").write_text(
        sha256(destination / "manifest.json") + "\n", encoding="ascii", newline="\n"
    )
    from .verify import verify_package

    package_validation = verify_package(destination)
    archive.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as stream:
        for path in sorted(destination.rglob("*")):
            if path.is_file():
                info = zipfile.ZipInfo(
                    path.relative_to(destination).as_posix(), (2026, 9, 19, 0, 0, 0)
                )
                info.compress_type = zipfile.ZIP_DEFLATED
                stream.writestr(info, path.read_bytes(), compresslevel=9)
    digest = sha256(archive)
    archive.with_suffix(archive.suffix + ".sha256").write_text(
        digest + "  " + archive.name + "\n", encoding="ascii", newline="\n"
    )
    with zipfile.ZipFile(archive) as stream:
        if stream.testzip() is not None:
            raise ValueError("ZIP CRC validation failed")
        for name, expected in files.items():
            import hashlib

            if hashlib.sha256(stream.read(name)).hexdigest() != expected:
                raise ValueError(f"ZIP member hash mismatch: {name}")
    return dict(
        zip=str(archive),
        bytes=archive.stat().st_size,
        sha256=digest,
        verification=package_validation,
    )


def copy_support(destination):
    folder = "data/research/continuous-marks-20260919"
    shutil.copytree(
        REPO / folder, destination / folder, ignore=shutil.ignore_patterns("__pycache__", "*.pyc")
    )
    for name in (
        "docs/continuous_mark_gaps.md",
        "data/research/continuous-preparation-20260919/unresolved_mark_minutes.csv",
    ):
        (destination / name).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO / name, destination / name)
    shutil.copytree(
        REPO / "src/crypto_carry",
        destination / "codigo/src/crypto_carry",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    shutil.copytree(
        REPO / "scripts/continuous_delivery",
        destination / "codigo/scripts/continuous_delivery",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    for name in ("scripts/verify_continuous_marks.py", "pyproject.toml", "uv.lock"):
        target = destination / "codigo" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO / name, target)
    shutil.copyfile(Path(__file__).with_name("verify.py"), destination / "verificar.py")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--zip", type=Path, required=True)
    args = parser.parse_args()
    print(
        json.dumps(
            build(args.root.resolve(), args.destination.resolve(), args.zip.resolve()), indent=2
        )
    )


if __name__ == "__main__":
    main()
