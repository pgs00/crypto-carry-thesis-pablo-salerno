"""Predeclared one-factor scenarios. Historical evaluation requires a verified baseline."""

import csv
import hashlib
import json
import tempfile
from dataclasses import dataclass
from decimal import Decimal as D
from pathlib import Path

import numpy as np
import pandas as pd

from .config import Config, timestamp
from .data.prescribed import prescribed_rules
from .data.replay import input_hashes, iter_records
from .data.rules import RuleBook, synthetic_rules
from .data.validate import validate_data
from .evaluation import metric_tables
from .fixtures import demo_records
from .strategy import Backtest


@dataclass(frozen=True)
class Scenario:
    name: str
    dimension: str
    value: str
    config: Config
    changed_fields: tuple[str, ...]


def scenario_configs(base: Config) -> list[Scenario]:
    result = [Scenario("baseline", "baseline", "base", base, ())]
    dimensions = [
        ("cost", "cost_multiplier", (D(1), D(2), D(3))),
        ("slippage", "slippage", (D(0), D(".0001"), D(".0002"), D(".0005"))),
        ("half_life", "half_life_hours", (12, 24, 48)),
        ("window", "window_hours", (168, 336, 672)),
        ("signal_delay", "signal_delay_seconds", (60, 120, 300)),
        ("leg_delay", "leg_delay_seconds", (1, 5, 10)),
        ("horizon", "horizon_hours", (72, 168, 336)),
        ("start", "start", ("2023-01-01T00:00:00Z", "2024-01-01T00:00:00Z")),
        ("aum", "capital", (D(10000), D(100000), D(1000000))),
    ]
    if base.execution_model not in ("minute_open", "next_minute_vwap"):
        dimensions.insert(7, ("execution", "execution_model", ("first_trade", "vwap")))
    for dimension, field, values in dimensions:
        for value in values:
            if dimension == "start" and not (
                timestamp(base.start) <= timestamp(value) < timestamp(base.end)
            ):
                continue
            changes = {field: value}
            if dimension == "horizon":
                changes["holding_hours"] = value
            changed = base.changed(**changes)
            token = str(value).replace(":", "").replace(".", "p")
            result.append(
                Scenario(f"{dimension}-{token}", dimension, str(value), changed, tuple(changes))
            )
    if base.analysis_mode == "prescribed_research":
        research = (
            ("funding-proxy-plus-10", "funding_proxy", "funding_proxy_stress_bps", D("10")),
            ("funding-proxy-minus-10", "funding_proxy", "funding_proxy_stress_bps", D("-10")),
            ("futures-fee-0p0004", "futures_fee", "research_futures_taker_fee", D("0.0004")),
            ("maintenance-2", "maintenance", "research_maintenance_multiplier", D("2")),
            ("liquidation-fee-0p03", "liquidation_fee", "research_liquidation_fee", D("0.03")),
        )
        result.extend(
            Scenario(name, dimension, str(value), base.changed(**{field: value}), (field,))
            for name, dimension, field, value in research
        )
    return result


def run_robustness(
    root: Path, base: Config, *, selected: list[str] | None = None, data_kind: str | None = None
) -> Path:
    from .reporting import write_run

    root = Path(root).resolve()
    inferred = (
        "historical_assumptions" if base.analysis_mode == "prescribed_research" else "historical"
    )
    data_kind = inferred if data_kind is None else data_kind
    if base.analysis_mode == "prescribed_research" and data_kind != "historical_assumptions":
        raise ValueError("prescribed_research robustness requires historical_assumptions data_kind")
    if base.analysis_mode != "prescribed_research" and data_kind == "historical_assumptions":
        raise ValueError(
            "historical_assumptions data_kind requires prescribed_research analysis_mode"
        )
    scenarios = scenario_configs(base)
    if selected:
        unknown = set(selected) - {s.name for s in scenarios}
        if unknown:
            raise ValueError(
                f"Unknown scenarios or initial date outside evaluation range: {sorted(unknown)}"
            )
        scenarios = [s for s in scenarios if s.name == "baseline" or s.name in selected]
    rows = []
    paths = []
    baseline_complete = False
    for index, scenario in enumerate(scenarios):
        config = scenario.config
        quality = (
            dict(
                status="complete",
                historical=False,
                issues=[],
                coverage=[],
                start=timestamp(config.start),
                end=timestamp(config.end),
            )
            if data_kind == "synthetic"
            else validate_data(config, root, scope="full")
        )
        inputs = (
            {"fixture": "synthetic:demo-v1"}
            if data_kind == "synthetic"
            else input_hashes(root, config)
        )
        can_run = quality["status"] == "complete" and (index == 0 or baseline_complete)
        if index and not baseline_complete:
            quality["status"] = "incomplete_data"
            quality["issues"] = quality["issues"] + [
                "Baseline not verified; sensitivity not executed"
            ]
        results = []
        if can_run:
            rules = (
                synthetic_rules(config)
                if data_kind == "synthetic"
                else prescribed_rules(config)
                if data_kind == "historical_assumptions"
                else RuleBook.load(root / config.rules_file)
            )
            for strategy, enabled in (("conditional", True), ("permanent", False)):
                records = (
                    demo_records(config)
                    if data_kind == "synthetic"
                    else iter_records(
                        root,
                        timestamp(config.start),
                        timestamp(config.end),
                        config.window_hours + 24,
                        data_dir=config.data_dir,
                        execution_model=config.execution_model,
                        include_closed_bars=config.signal_price_model == "closed_minute",
                    )
                )
                results.append(
                    Backtest(config, rules, strategy, enabled, inputs=inputs).run(records)
                )
        if index == 0:
            baseline_complete = can_run and all(
                b.status in {"complete", "insolvent"} for b in results
            )
        path = write_run(
            root, config, results, quality, data_kind=data_kind, label=scenario.name, inputs=inputs
        )
        paths.append(path)
        metrics = metric_tables(results, config)
        for strategy in ("conditional", "permanent"):
            metric = {}
            if not metrics.empty:
                match = metrics[(metrics.strategy == strategy) & (metrics.period == "full")]
                if len(match):
                    metric = match.iloc[0].to_dict()
            result = next((b for b in results if b.strategy == strategy), None)
            participation = (
                [
                    float(o.quantity / o.recent_volume_quantity)
                    for o in result.orders.values()
                    if o.recent_volume_quantity > 0
                ]
                if result
                else []
            )
            rows.append(
                dict(
                    run_id=path.name,
                    baseline_run_id=paths[0].name,
                    scenario=scenario.name,
                    dimension=scenario.dimension,
                    value=scenario.value,
                    strategy=strategy,
                    symbol="PORTFOLIO",
                    timestamp_utc=config.end,
                    units="ratio;USDT;seconds",
                    config_hash=config.digest(),
                    data_kind=data_kind,
                    status=result.status if result else "incomplete_data",
                    reason="; ".join(result.reasons if result else quality["issues"]),
                    cagr=metric.get("cagr"),
                    sharpe=metric.get("sharpe"),
                    net_return=metric.get("net_return"),
                    max_drawdown=metric.get("max_drawdown"),
                    coverage_complete=metric.get("coverage_complete", False),
                    participation_p50=float(np.quantile(participation, 0.5))
                    if participation
                    else None,
                    participation_p95=float(np.quantile(participation, 0.95))
                    if participation
                    else None,
                    participation_max=max(participation) if participation else None,
                    attempts=len(result.orders) if result else None,
                    debt_usdt=str(result.ledger.debt) if result else None,
                )
            )
        print(f"{scenario.name}: {rows[-1]['status']} [{path.name}]", flush=True)
    identity = hashlib.sha256(json.dumps([p.name for p in paths]).encode()).hexdigest()[:16]
    destination = root / "outputs" / f"robustness-{identity}"
    if destination.exists():
        verification = verify_robustness(destination)
        if not verification["valid"]:
            raise ValueError(f"Changed robustness artifact: {verification['mismatches']}")
        return destination
    destination.mkdir(parents=True)
    with (destination / "robustness_summary.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (destination / "effective_config.toml").write_text(base.to_toml(), encoding="utf-8")
    _cost_plot(destination, data_kind)
    (destination / "report.md").write_text(
        _index_report(destination, data_kind, baseline_complete), encoding="utf-8"
    )
    manifest = dict(
        run_id=destination.name,
        kind="robustness_index",
        artifacts_complete=True,
        baseline_verified=baseline_complete,
        data_kind=data_kind,
        status=(
            "incomplete_data"
            if any(r["status"] == "incomplete_data" for r in rows)
            else "insolvent"
            if any(r["status"] == "insolvent" for r in rows)
            else "complete"
        ),
        baseline_run_id=paths[0].name,
        scenario_run_ids=[p.name for p in paths],
        config=base.to_dict(),
        output_hashes={
            p.relative_to(destination).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in destination.rglob("*")
            if p.is_file()
        },
    )
    (destination / "run_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )
    (destination / "run_manifest.sha256").write_text(
        _hash(destination / "run_manifest.json"), encoding="ascii"
    )
    return destination


def _cost_plot(destination: Path, data_kind: str, source: Path | None = None) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    frame = pd.read_csv((source or destination) / "robustness_summary.csv")
    frame = frame[(frame.dimension == "cost") & frame.coverage_complete]
    figures = destination / "figures"
    figures.mkdir()
    with plt.rc_context({"svg.hashsalt": (source or destination).name}):
        fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), layout="constrained")
        for ax, metric, label in zip(
            axes, ("cagr", "sharpe"), ("CAGR (proporción anual)", "Sharpe anualizado")
        ):
            valid = frame.dropna(subset=[metric])
            for strategy, group in valid.groupby("strategy"):
                ax.plot(pd.to_numeric(group.value), group[metric], marker="o", label=strategy)
            ax.set(xlabel="Multiplicador de taker y slippage", ylabel=label)
            ax.grid(alpha=0.2)
            if valid.empty:
                ax.text(
                    0.5,
                    0.5,
                    "Sin escenarios históricos evaluables"
                    if data_kind == "historical"
                    else "Sin métricas evaluables del escenario prescrito"
                    if data_kind == "historical_assumptions"
                    else "Sin métricas sintéticas evaluables",
                    ha="center",
                    va="center",
                    transform=ax.transAxes,
                )
            else:
                ax.legend()
        kind_label = (
            "precios observados + supuestos prescriptos"
            if data_kind == "historical_assumptions"
            else data_kind
        )
        fig.suptitle("Sensibilidad a costos · " + kind_label)
        fig.savefig(
            figures / "cost_sensitivity.png", dpi=150, metadata={"Software": "crypto-carry"}
        )
        fig.savefig(
            figures / "cost_sensitivity.svg", metadata={"Date": None, "Creator": "crypto-carry"}
        )
        plt.close(fig)


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _index_report(run: Path, data_kind: str, baseline_verified: bool) -> str:
    rows = pd.read_csv(run / "robustness_summary.csv", dtype=str, keep_default_na=False)
    links = "\n".join(
        f"- [{r.scenario}](../{r.run_id}/report.md): {r.dimension} = {r.value}; {r.status}"
        for r in rows.drop_duplicates("run_id").itertuples()
    )
    kind_label = (
        "precios observados con supuestos prescriptos; no histórico certificado"
        if data_kind == "historical_assumptions"
        else data_kind
    )
    return (
        "# Robustez predefinida\n\n"
        f"Datos: **{kind_label}**. Baseline verificado: **{baseline_verified}**.\n\n"
        "Cada escenario usa ambas estrategias; no se selecciona retrospectivamente el mejor. "
        "Los horizontes cambian conjuntamente forecast, target H1 y permanencia. Las fechas "
        "iniciales reinician sólo sus corridas separadas, nunca la cartera del H3 principal. "
        "Inicios que no preceden el fin de una configuración corta se omiten por rango no evaluable.\n\n"
        "La participación supone fills completos: no prueba escalabilidad ni estima impacto. "
        "Los cargos de liquidación no se multiplican con las comisiones. "
        "Los escenarios sin baseline o reglas suficientes permanecen incompletos.\n\n"
        "![Sensibilidad a costos](figures/cost_sensitivity.png)\n\n" + links + "\n"
    )


def verify_robustness(run: Path, *, allow_missing_derived: bool = False) -> dict:
    from .reporting import verify_run

    run = Path(run).resolve()
    manifest = json.loads((run / "run_manifest.json").read_text(encoding="utf-8"))
    problems = []
    derived = {"report.md", "figures/cost_sensitivity.png", "figures/cost_sensitivity.svg"}
    if (run / "run_manifest.sha256").read_text(encoding="ascii").strip() != _hash(
        run / "run_manifest.json"
    ):
        problems.append("manifest checksum mismatch")
    hashes = manifest.get("output_hashes", {})
    if not (derived | {"robustness_summary.csv", "effective_config.toml"}) <= set(hashes):
        problems.append("missing required artifacts")
    for name, digest in hashes.items():
        path = (run / name).resolve()
        if run not in path.parents:
            problems.append(f"invalid artifact path: {name}")
        elif not path.exists():
            if not (allow_missing_derived and name in derived):
                problems.append(f"missing artifact: {name}")
        elif _hash(path) != digest:
            problems.append(f"checksum mismatch: {name}")
    for name in manifest["scenario_run_ids"]:
        if Path(name).name != name or any(c in name for c in "/\\:"):
            problems.append("invalid scenario path")
        elif not verify_run(run.parent / name)["valid"]:
            problems.append(f"scenario artifacts changed: {name}")
    return dict(
        valid=not problems,
        status=manifest["status"],
        run_id=manifest["run_id"],
        mismatches=problems,
    )


def regenerate_robustness(run: Path) -> Path:
    run = Path(run).resolve()
    result = verify_robustness(run, allow_missing_derived=True)
    if not result["valid"]:
        raise ValueError(f"Robustness validation failed: {result['mismatches']}")
    manifest = json.loads((run / "run_manifest.json").read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix=".robustness-report-", dir=run.parent) as folder:
        staging = Path(folder)
        _cost_plot(staging, manifest["data_kind"], source=run)
        (staging / "report.md").write_text(
            _index_report(run, manifest["data_kind"], manifest["baseline_verified"]),
            encoding="utf-8",
        )
        for name in ("report.md", "figures/cost_sensitivity.png", "figures/cost_sensitivity.svg"):
            if _hash(staging / name) != manifest["output_hashes"][name]:
                raise ValueError(f"Rebuilt robustness artifact differs: {name}")
        for name in ("report.md", "figures/cost_sensitivity.png", "figures/cost_sensitivity.svg"):
            if not (run / name).exists():
                (run / name).parent.mkdir(parents=True, exist_ok=True)
                with (run / name).open("xb") as stream:
                    stream.write((staging / name).read_bytes())
    return run / "report.md"
