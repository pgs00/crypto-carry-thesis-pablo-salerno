"""Continuous portfolios with read-only observation of the approved mark gaps."""

from __future__ import annotations

import csv
import gc
import hashlib
import json
from collections import Counter
from dataclasses import asdict
from decimal import Decimal as D
from pathlib import Path
from time import monotonic

import pyarrow.parquet as pq

from .config import Config, iso, timestamp
from .data.mark_gaps import (
    APPROVED_MINUTES,
    METHODS,
    MINUTE,
    _immutable,
    _json,
    official_anchor,
    prepare_mark_gaps,
)
from .data.prescribed import prescribed_rules
from .data.replay import _sha256, input_hashes, iter_records
from .data.validate import validate_data
from .margin import margin_state
from .strategy import Backtest


def gap_windows():
    groups = {}
    for symbol, t in sorted(APPROVED_MINUTES):
        anchor = official_anchor(symbol, t)
        groups[symbol, anchor] = max(t, groups.get((symbol, anchor), t))
    return [(s, anchor, last) for (s, anchor), last in sorted(groups.items())]


class GapAuditedBacktest(Backtest):
    """Observe the existing risk predicate without changing orders or balances."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mark_gap_checks = []
        self._gap_windows = gap_windows()
        self._progress_at = monotonic()

    def process(self, time_ns, records, native):
        super().process(time_ns, records, native)
        if monotonic() - self._progress_at >= 30:
            self._progress_at = monotonic()
            fraction = max(0, min(1, (self.now - self.start) / (self.end - self.start)))
            print(
                f"[{self.config.mark_gap_method}/{self.strategy}] {fraction:.1%} "
                f"| UTC {iso(self.now)} | fills {len(self.fills)}",
                flush=True,
            )

    def _risk(self, symbol, periodic=False):
        window = next(
            (
                w
                for w in self._gap_windows
                if w[0] == symbol and w[1] + MINUTE <= self.now <= w[2] + 2 * MINUTE
            ),
            None,
        )
        if window is None:
            return super()._risk(symbol, periodic)
        mark = self.marks.get(symbol)
        p, pair = self.ledger.positions[symbol], self.pairs[symbol]
        row = dict(
            time_ns=self.now,
            timestamp_utc=iso(self.now),
            symbol=symbol,
            strategy=self.strategy,
            method=self.config.mark_gap_method,
            gap_anchor=window[1],
            gap_last=window[2],
            periodic=periodic,
            state_before=pair.state.value,
            **asdict(p),
            pending_orders_before=[o.order_id for o in self._pending(symbol)],
            mark_open_time=mark.open_time if mark else None,
            mark_available_at=mark.available_at if mark else None,
            mark_close=mark.close if mark else None,
            mark_source=mark.source_file if mark else None,
            estimation_method=mark.estimation_method if mark else None,
            stage="anchor"
            if mark and mark.open_time == window[1]
            else "estimated"
            if mark and (symbol, mark.open_time) in APPROVED_MINUTES
            else "recovery",
            equity_before_risk=self.equity(),
            margin_exit_ratio=self.config.margin_exit_ratio,
            liquidation_distance=self.config.liquidation_distance,
            risk_applicable=bool(p.spot > 0 or p.short > 0 or self._pending(symbol)),
        )
        rule = self._rule(symbol, "futures")
        row.update(
            dict(
                balance=None,
                maintenance=None,
                liquidation_price=None,
                ratio=None,
                distance=None,
                liquidate=False,
                preventive=False,
            )
        )
        if p.short > 0 and mark and rule:
            try:
                row.update(
                    margin_state(p.short, p.average, p.collateral, mark.close, rule, self.config)
                )
            except ValueError as exc:
                # The observer records the failure; the parent owns the halt.
                row["margin_error"] = str(exc)
        offset = len(self.risk_events)
        super()._risk(symbol, periodic)
        row.update(
            state_after=pair.state.value,
            risk_events=[dict(e) for e in self.risk_events[offset:]],
            pending_orders_after=[o.order_id for o in self._pending(symbol)],
            equity_after_risk=self.equity(),
        )
        self.mark_gap_checks.append(row)


def compare_records(left: list[dict], right: list[dict]) -> dict:
    """Ignore run identity, retaining all economic and decision fields."""
    ignored = {"run_id", "units", "data_kind"}

    def clean(rows):
        return [{k: v for k, v in row.items() if k not in ignored} for row in rows]

    a, b = clean(left), clean(right)
    changed = sum(x != y for x, y in zip(a, b)) + abs(len(a) - len(b))
    return dict(
        identical=a == b, changed_rows=changed, primary_rows=len(a), sensitivity_rows=len(b)
    )


def _read_csv(path):
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def _write_csv(path, rows):
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(
            {
                k: json.dumps(v, sort_keys=True, default=str) if isinstance(v, (dict, list)) else v
                for k, v in row.items()
            }
            for row in rows
        )


def build_study_report(root: Path, study: Path) -> dict:
    """Build a comparison from verified persisted artifacts, without replaying data."""
    from .reporting import verify_run

    index = json.loads((study / "study_index.json").read_text(encoding="utf-8"))
    if len(index["runs"]) != 4:
        raise ValueError("Both strategies and both methods must finish before comparison")
    results, checks, tables, funding, period_metrics = [], [], {}, {}, []
    for item in index["runs"]:
        method, strategy = item["method"], item["strategy"]
        run = root / item["path"]
        verification = verify_run(run)
        if not verification["valid"]:
            raise ValueError(f"Unverified run: {item['path']}")
        manifest = json.loads((run / "run_manifest.json").read_text(encoding="utf-8"))
        if manifest["status"] != "complete" or manifest["config"]["mark_gap_method"] != method:
            raise ValueError("Incomplete or mismatched continuous run")
        metrics = _read_csv(run / "metrics.csv")
        period_metrics.extend(dict(r, method=method) for r in metrics)
        metric = next(r for r in metrics if r["period"] == "full")
        summary = _read_csv(run / "run_summary.csv")[0]
        risks = pq.ParquetFile(run / "risk_events.parquet").read().to_pylist()
        fills = pq.ParquetFile(run / "fills.parquet").read().to_pylist()
        gap_checks = pq.ParquetFile(run / "mark_gap_checks.parquet").read().to_pylist()
        checks.extend(gap_checks)
        decisions = Counter(r.get("cause") for r in risks if r["kind"] == "close_requested")
        results.append(
            dict(
                method=method,
                strategy=strategy,
                run_id=run.name,
                final_equity_usdt=summary["final_equity_usdt"],
                net_return=metric["net_return"],
                cagr=metric["cagr"],
                max_drawdown_daily=metric["max_drawdown"],
                daily_observations=metric["observations"],
                margin_closes=decisions["margin"],
                liquidation_requests=decisions["liquidation"],
                liquidation_fills=sum(bool(r.get("liquidation")) for r in fills),
                close_causes=dict(decisions),
                gap_checks=len(gap_checks),
                run_manifest_sha256=_sha256(run / "run_manifest.json"),
            )
        )
        tables[method, strategy] = {
            "risk_events": risks,
            "fills": fills,
            "signals": pq.ParquetFile(run / "signals.parquet").read().to_pylist(),
            "daily_equity": _read_csv(run / "equity_daily.csv"),
        }
        funding[method, strategy] = json.loads(
            (run / "funding_mark_audit.json").read_text(encoding="utf-8")
        )["consumed"]
    comparisons = {}
    for strategy in ("conditional", "permanent"):
        comparisons[strategy] = {
            name: compare_records(rows, tables["last_official", strategy][name])
            for name, rows in tables["futures_scaled", strategy].items()
        }
        comparisons[strategy]["funding_observations"] = compare_records(
            funding["futures_scaled", strategy], funding["last_official", strategy]
        )
    gap_summary = []
    for method in METHODS:
        for strategy in ("conditional", "permanent"):
            for symbol, anchor, last in gap_windows():
                selected = [
                    r
                    for r in checks
                    if r["method"] == method
                    and r["strategy"] == strategy
                    and r["symbol"] == symbol
                    and r["stage"] == "estimated"
                    and anchor < int(r["mark_open_time"]) <= last
                ]
                if not selected:
                    raise ValueError("Missing risk observations during an approved gap")

                def values(key):
                    return [D(r[key]) for r in selected if r.get(key) not in (None, "")]

                ratios, distances = values("ratio"), values("distance")
                events = [e for r in selected for e in json.loads(r["risk_events"])]
                gap_summary.append(
                    dict(
                        method=method,
                        strategy=strategy,
                        symbol=symbol,
                        first_open_utc=iso(anchor + MINUTE),
                        last_open_utc=iso(last),
                        checks=len(selected),
                        spot_min=str(min(values("spot"))),
                        spot_max=str(max(values("spot"))),
                        short_min=str(min(values("short"))),
                        short_max=str(max(values("short"))),
                        collateral_min=str(min(values("collateral"))),
                        collateral_max=str(max(values("collateral"))),
                        mark_min=str(min(values("mark_close"))),
                        mark_max=str(max(values("mark_close"))),
                        max_margin_ratio=str(max(ratios)) if ratios else None,
                        min_liquidation_distance=str(min(distances)) if distances else None,
                        close_causes=[e["cause"] for e in events if e["kind"] == "close_requested"],
                    )
                )
    _write_csv(study / "comparison.csv", results)
    _write_csv(study / "period_metrics.csv", period_metrics)
    _write_csv(study / "gap_risk_checks.csv", checks)
    _write_csv(study / "gap_positions_summary.csv", gap_summary)
    (study / "method_differences.json").write_bytes(_json(comparisons))
    lines = [
        "# Sensibilidad de los 15 marks: cartera continua",
        "",
        "Período UTC: 01/01/2022–31/08/2026 (fin exclusivo: 01/09/2026). "
        "Cada cartera comienza con 10.000 USDT y conserva capital y posiciones al cambiar de año. "
        "Cobertura **completed_with_approximations**: 13 minutos ETH y 2 BTC, en siete huecos por activo.",
        "",
        "Método principal, fijado antes de observar resultados: `futures_scaled`. "
        "Se multiplica el OHLC del futuro por el cierre de mark oficial / cierre de futuro del "
        "minuto anterior al hueco. El ancla permanece fija; no se suma nuevamente el basis. "
        "Sensibilidad `last_official`: OHLC constante en el último cierre oficial. Ambos métodos "
        "se publican al minuto siguiente, exclusivamente con velas cerradas.",
        "",
        "| Método | Cartera | Equity final USDT | Retorno neto | CAGR | Drawdown máximo diario | Cierres por margen | Liquidaciones ejecutadas |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for r in results:
        lines.append(
            f"| {r['method']} | {r['strategy']} | {D(r['final_equity_usdt']):,.2f} | "
            f"{float(r['net_return']):.4%} | {float(r['cagr']):.4%} | "
            f"{float(r['max_drawdown_daily']):.4%} | {r['margin_closes']} | {r['liquidation_fills']} |"
        )
    lines.extend(
        [
            "",
            "El drawdown de esta tabla usa cierres diarios, igual que los informes anteriores; "
            "no representa el peor recorrido intraminuto. [Métricas por año y régimen](period_metrics.csv) "
            "se calculan sobre las mismas carteras continuas, sin reinicios.",
            "",
            "## Decisiones y posiciones durante los huecos",
            "",
        ]
    )
    for strategy, differences in comparisons.items():
        lines.append(
            f"- `{strategy}`: "
            + "; ".join(
                f"{name}: {'idénticos' if d['identical'] else str(d['changed_rows']) + ' filas diferentes'}"
                for name, d in differences.items()
            )
            + "."
        )
    lines.extend(
        [
            "",
            "[Controles individuales de riesgo](gap_risk_checks.csv): posiciones antes del control, "
            "precio medio del short, colateral, balance, mantenimiento, ratio, precio y distancia "
            "a liquidación, estado antes/después y eventos realmente emitidos. Incluyen el ancla y "
            "el primer mark oficial de recuperación. [Resumen por hueco](gap_positions_summary.csv).",
            "",
            "| Método / cartera | Activo / primera apertura UTC | Spot (mín.–máx.) | Short (mín.–máx.) | Máx. ratio margen | Mín. distancia liquidación | Cierres durante hueco |",
            "|---|---|---:|---:|---:|---:|---|",
        ]
    )
    for r in gap_summary:
        ratio = f"{D(r['max_margin_ratio']):.4%}" if r["max_margin_ratio"] else "sin short"
        distance = (
            f"{D(r['min_liquidation_distance']):.4%}"
            if r["min_liquidation_distance"]
            else "sin short"
        )
        lines.append(
            f"| {r['method']} / {r['strategy']} | {r['symbol']} {r['first_open_utc'][:16]} | "
            f"{r['spot_min']}–{r['spot_max']} | {r['short_min']}–{r['short_max']} | "
            f"{ratio} | {distance} | {', '.join(r['close_causes']) or 'ninguno'} |"
        )
    lines.extend(
        [
            "",
            "## Supuestos, límites y reproducción",
            "",
            "Los controles existentes permanecen activos: cierre preventivo por ratio de mantenimiento "
            "≥ 50% o distancia a liquidación < 15%, y liquidación según balance, mantenimiento y precio "
            "de liquidación del modelo. Un mark aproximado puede desplazar esos umbrales. El método "
            "escalado supone estable la relación mark/futuro durante el hueco; el constante ignora "
            "el movimiento del futuro. Ninguno reconstruye el mark oficial desconocido ni un recorrido "
            "intraminuto. Se conserva la aproximación de funding `previous_closed_1m`, junto con las "
            "comisiones y reglas prescritas actuales. La cobertura aproximada no certifica reglas históricas.",
            "",
            "La validación estricta de los originales se conserva en `strict_validation/manifests/coverage.json`; "
            "continúa bloqueada por los 15 marks. Las capas derivadas reemplazan solamente tres particiones "
            "de mark y verifican todas sus filas frente al original más las 15 estimaciones. Los restantes "
            "precios, funding y parámetros económicos son compartidos sin cambios. Todos los resultados "
            "anteriores y las fuentes originales se conservan.",
            "",
            "Desde el repositorio, ejecutar `python -u -m crypto_carry --root D:\\Backtesting "
            "continuous-mark-study --config <ruta absoluta a configs/download_minutes_2022_2026_d.toml>`. "
            "`study_index.json` identifica las cuatro corridas; sus manifiestos registran código, parámetros "
            "y hashes de entradas/salidas. `python -m crypto_carry --root D:\\Backtesting report --run-id "
            "<run_id>` verifica una corrida y reconstruye su informe sin repetirla. "
            "`verify_mark_gap_study(Path(...))` verifica el estudio y sus cuatro corridas.",
            "",
        ]
    )
    (study / "mark_gap_report.md").write_text("\n".join(lines), encoding="utf-8")
    manifest = dict(
        status="complete",
        coverage_kind="completed_with_approximations",
        results=results,
        differences=comparisons,
        runs=index["runs"],
        output_hashes={
            p.relative_to(study).as_posix(): _sha256(p)
            for p in sorted(study.rglob("*"))
            if p.is_file() and p.name not in ("study_manifest.json", "study_manifest.sha256")
        },
    )
    (study / "study_manifest.json").write_bytes(_json(manifest))
    (study / "study_manifest.sha256").write_text(
        _sha256(study / "study_manifest.json") + "\n", encoding="ascii"
    )
    return manifest


def verify_mark_gap_study(study: Path) -> dict:
    from .reporting import verify_run

    study = Path(study).resolve()
    manifest = json.loads((study / "study_manifest.json").read_text(encoding="utf-8"))
    errors = []
    if (
        _sha256(study / "study_manifest.json")
        != (study / "study_manifest.sha256").read_text().strip()
    ):
        errors.append("study manifest checksum")
    for name, digest in manifest["output_hashes"].items():
        if not (study / name).is_file() or _sha256(study / name) != digest:
            errors.append(name)
    for item in manifest["runs"]:
        if not verify_run(study.parent.parent / item["path"])["valid"]:
            errors.append(item["path"])
    return dict(valid=not errors, mismatches=errors, runs=len(manifest["runs"]))


def run_mark_gap_study(root: Path, config: Config) -> Path:
    from .reporting import verify_run, write_run

    root = Path(root).resolve()
    if (timestamp(config.start), timestamp(config.end)) != (
        timestamp("2022-01-01T00:00:00Z"),
        timestamp("2026-09-01T00:00:00Z"),
    ):
        raise ValueError("This continuous study requires the approved full 2022-2026 period")
    base = root / config.data_dir / "manifests"
    identity = dict(
        config=config.to_dict(),
        code_hash=Backtest._code_hash(),
        source_manifest_sha256=_sha256(base / "processed.json"),
        download_sha256=_sha256(base / "download.json"),
    )
    study_id = "continuous_marks_" + hashlib.sha256(_json(identity)).hexdigest()[:24]
    study = root / "outputs" / study_id
    study.mkdir(parents=True, exist_ok=True)
    index_path = study / "study_index.json"
    index = (
        json.loads(index_path.read_text(encoding="utf-8"))
        if index_path.exists()
        else dict(identity=identity, runs=[])
    )
    if index["identity"] != identity:
        raise ValueError("Continuous study identity mismatch")
    if (study / "study_manifest.json").is_file():
        if not verify_mark_gap_study(study)["valid"]:
            raise ValueError("Previously finished study failed verification")
        return study
    strict_dir = study / "strict_validation"
    for name in ("processed.json", "download.json"):
        _immutable(strict_dir / "manifests" / name, (base / name).read_bytes())
    print("Verifying strict original coverage (expected block for 15 marks)...", flush=True)
    strict_quality = validate_data(
        config.changed(data_dir=strict_dir.relative_to(root).as_posix()), root, "full"
    )
    if strict_quality["status"] != "incomplete_data" or len(strict_quality["issues"]) != 7:
        raise ValueError(f"Unexpected strict-source coverage: {strict_quality['issues']}")
    for method in METHODS:
        print(f"Preparing and validating {method}...", flush=True)
        derived = prepare_mark_gaps(config, root, method)
        quality = validate_data(derived, root, "full")
        if quality["status"] != "complete":
            raise ValueError(f"Derived coverage remains blocked: {quality['issues']}")
        inputs = input_hashes(root, derived)
        rules = prescribed_rules(derived)
        for strategy, enabled in (("conditional", True), ("permanent", False)):
            previous = next(
                (r for r in index["runs"] if r["method"] == method and r["strategy"] == strategy),
                None,
            )
            if previous:
                if not verify_run(root / previous["path"])["valid"]:
                    raise ValueError("Cannot resume study with a corrupted prior run")
                continue
            print(f"Starting uninterrupted portfolio: {method}/{strategy}", flush=True)
            b = GapAuditedBacktest(derived, rules, strategy, enabled, inputs)
            b.run(
                iter_records(
                    root,
                    timestamp(derived.start),
                    timestamp(derived.end),
                    derived.window_hours + 24,
                    data_dir=derived.data_dir,
                    execution_model=derived.execution_model,
                    include_closed_bars=True,
                    mark_gap_method=method,
                )
            )
            print(
                f"Persisting {method}/{strategy}; status={b.status}; equity={b.equity()}",
                flush=True,
            )
            run = write_run(
                root,
                derived,
                [b],
                quality,
                "historical_assumptions",
                label="continuous-mark-gap-sensitivity",
                inputs=inputs,
            )
            if b.status != "complete" or b.now != timestamp(config.end) - 1:
                raise ValueError(f"Continuous run stopped: {run}: {b.reasons}")
            reconciliation = b.ledger.reconcile(b.spot_prices(), b.mark_prices())
            if abs(reconciliation["difference"]) > config.accounting_tolerance:
                raise ValueError("Final accounting reconciliation failed")
            index["runs"].append(
                dict(
                    method=method,
                    strategy=strategy,
                    path=run.relative_to(root).as_posix(),
                    accounting_difference=str(reconciliation["difference"]),
                )
            )
            index_path.write_bytes(_json(index))
            del b
            gc.collect()
    build_study_report(root, study)
    if not verify_mark_gap_study(study)["valid"]:
        raise ValueError("Continuous study verification failed")
    return study
