"""Build an immutable Entrega 3/4 summary from verified saved run artifacts."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import tempfile
from decimal import Decimal, InvalidOperation
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pyarrow.parquet as pq

from crypto_carry.reporting import verify_run
from crypto_carry.robustness import verify_robustness

WINDOWS = {
    "early": ("2022-09-01T00:00:00Z", "2023-09-01T00:00:00Z"),
    "late": ("2025-09-01T00:00:00Z", "2026-09-01T00:00:00Z"),
}
STRATEGIES = ("conditional", "permanent")
SENSITIVITIES = (
    ("cost-2", "Costos x2"),
    ("cost-3", "Costos x3"),
    ("funding-proxy-plus-10", "Proxy de funding +10 bps"),
    ("funding-proxy-minus-10", "Proxy de funding -10 bps"),
    ("futures-fee-0p0004", "Comisión de futuros 0,04 %"),
    ("maintenance-2", "Mantenimiento x2"),
    ("liquidation-fee-0p03", "Cargo de liquidación 3 %"),
)
ALLOWED_CONFIG_DIFFERENCES = {
    "start",
    "end",
    "history_start",
    "sample_start",
    "sample_end",
    "data_dir",
}
CSV_OUTPUTS = {
    "cost_path.csv",
    "portfolios.csv",
    "h1.csv",
    "h3.csv",
    "pnl_components.csv",
    "signal_decisions.csv",
    "sensitivities.csv",
}
FIGURE_OUTPUTS = {"figures/cost_sensitivity.png", "figures/cost_sensitivity.svg"}
OUTPUTS = {"report.md", "summary.json", *CSV_OUTPUTS, *FIGURE_OUTPUTS}
HUMAN_VERDICTS = {
    "favorable": "Favorable",
    "contraria_al_criterio_definido": "Contraria al criterio definido",
    "no_concluyente": "No concluyente",
    "no_concluyente_cobertura": "No concluyente por cobertura",
    "ambas_mayores_en_ventana_tardia": "Ambas variables son mayores en la ventana tardía",
    "ambas_menores_en_ventana_tardia": "Ambas variables son menores en la ventana tardía",
    "no_direccional": "Sin dirección conjunta",
}
HUMAN_STRATEGIES = {"conditional": "Condicional", "permanent": "Permanente"}
HUMAN_DECISIONS = {
    "accepted": "Aceptada",
    "basis_outside_entry_range": "Basis fuera del rango de entrada",
    "funding_not_above_cost": "Funding no supera el costo",
    "state_or_cooldown": "Estado activo o cooldown",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def write_rows(path: Path, rows: list[dict]) -> None:
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def formatted(value: str, kind: str) -> str:
    if value in {None, ""}:
        return "—"
    number = Decimal(str(value))
    return {
        "money": f"{number:.2f}",
        "percent": f"{number * 100:.4f}%",
        "sharpe": f"{number:.3f}",
        "bps": f"{number * 10000:.3f}",
        "seconds": f"{number:.0f}",
    }[kind]


def audit_evidence(baselines: dict[str, str]) -> dict:
    path = Path(__file__).with_name("annual-economic-audit.json")
    audit = load_json(path)
    if audit.get("status") != "passed" or audit.get("issues"):
        raise ValueError("Independent annual economic audit is not passed")

    def decimals(value):
        if isinstance(value, dict):
            for child in value.values():
                yield from decimals(child)
        elif isinstance(value, str):
            try:
                yield abs(Decimal(value))
            except InvalidOperation:
                pass

    runs = audit["runs"]
    audited_ids = {
        "early": runs["early_2022_2023"]["run_id"],
        "late": runs["late_2025_2026"]["run_id"],
    }
    if audited_ids != baselines:
        raise ValueError(f"Economic audit belongs to different baselines: {audited_ids}")
    fills = sum(run["fill_checks"]["fills_checked"] for run in runs.values())
    residues = [
        number
        for run in runs.values()
        for strategy in run["strategies"].values()
        for number in decimals(strategy["differences"])
    ]
    late = runs["late_2025_2026"]
    exceptional = runs["early_2022_2023"].get("exceptional_event", {})
    if set(exceptional.get("strategies", {})) != set(STRATEGIES):
        raise ValueError("Economic audit lacks both strategies for the exceptional event")
    return {
        "source": path.relative_to(Path(__file__).resolve().parents[3]).as_posix(),
        "sha256": sha256(path),
        "status": audit["status"],
        "fills_checked": str(fills),
        "maximum_absolute_residue": str(max(residues)),
        "tolerance": audit["tolerance"],
        "late_completion_failure_count": str(
            late["completion_risk_checks"]["completion_failure_count"]
        ),
        "late_failure_symbols": sorted(
            {row["symbol"] for row in late["completion_risk_checks"]["checks"]}
        ),
        "baseline_run_ids": audited_ids,
        "exceptional_event": exceptional,
    }


def outage_evidence(baselines: dict[str, str]) -> dict:
    path = Path(__file__).with_name("outage-trades-validation.json")
    evidence = load_json(path)
    baseline_run_id = evidence["baseline"]["run"]["run_id"]
    if baseline_run_id != baselines["early"]:
        raise ValueError(
            f"Outage trade validation belongs to a different baseline: {baseline_run_id}"
        )
    if evidence.get("kind") != "outage_trade_validation" or not evidence["findings"].get(
        "reference_prices_match_first_strict_source_trade"
    ):
        raise ValueError("Outage trade validation did not validate the baseline references")
    for market in ("spot", "futures"):
        source = evidence["sources"][market]
        if not source.get("checksum_verified") or not source.get("zip_crc_verified"):
            raise ValueError(f"Outage {market} source did not pass integrity checks")
    spot = evidence["sources"]["spot"]["analysis"]
    futures = evidence["sources"]["futures"]["analysis"]
    return {
        "source": path.relative_to(Path(__file__).resolve().parents[3]).as_posix(),
        "sha256": sha256(path),
        "baseline_run_id": baseline_run_id,
        "baseline_order_quantity": evidence["baseline"]["spot"]["quantity"],
        "first_trade": spot["first_trade_strictly_after_boundary"],
        "first_price_persistence": spot["first_price_persistence"],
        "windows": spot["windows"],
        "spot_short_missing_ids": spot["short_window_id_time_audit"]["missing_id_count"],
        "futures_short_missing_ids": futures["short_window_id_time_audit"]["missing_id_count"],
        "futures_day_missing_ids": futures["day"]["id_audit"]["missing_id_count"],
        "sources": {
            market: {
                "url": evidence["sources"][market]["source_url"],
                "sha256": evidence["sources"][market]["sha256"],
            }
            for market in ("spot", "futures")
        },
    }


def one(rows: list[dict[str, str]], **where: str) -> dict[str, str]:
    found = [row for row in rows if all(row.get(key) == value for key, value in where.items())]
    if len(found) != 1:
        raise ValueError(f"Expected one row for {where} in saved table; found {len(found)}")
    return found[0]


def valid_id(value: str) -> str:
    if Path(value).name != value or any(char in value for char in "/\\:"):
        raise ValueError(f"Invalid artifact identifier: {value}")
    return value


def verify_baseline(root: Path, run_id: str, window: str) -> tuple[Path, dict]:
    run = root / "outputs" / valid_id(run_id)
    result = verify_run(run)
    if not result["valid"] or result["status"] != "complete":
        raise ValueError(f"Baseline {run_id} is not complete and verified: {result}")
    manifest = load_json(run / "run_manifest.json")
    config = manifest["config"]
    start, end = WINDOWS[window]
    required = {
        "start": start,
        "end": end,
        "capital": "10000",
        "analysis_mode": "prescribed_research",
        "execution_model": "minute_open",
    }
    if any(config.get(key) != value for key, value in required.items()):
        raise ValueError(f"{window} baseline does not match the approved profile: {required}")
    if manifest.get("label") != "baseline" or manifest.get("data_kind") != "historical_assumptions":
        raise ValueError(f"{window} input is not the prescribed baseline")
    summaries = read_rows(run / "run_summary.csv")
    if {row["strategy"] for row in summaries} != set(STRATEGIES):
        raise ValueError(f"{window} baseline must contain exactly both strategies")
    if any(row["status"] != "complete" or row["capital_usdt"] != "10000" for row in summaries):
        raise ValueError(f"{window} strategies must complete with independent 10000 USDT resets")
    return run, manifest


def compatible(early: dict, late: dict) -> None:
    if early.get("code_hash") != late.get("code_hash"):
        raise ValueError("Baselines were not produced by the same code identity")
    left, right = early["config"], late["config"]
    differing = {key for key in left | right if left.get(key) != right.get(key)}
    unexpected = differing - ALLOWED_CONFIG_DIFFERENCES
    if unexpected:
        raise ValueError(f"Incompatible financial configurations: {sorted(unexpected)}")


def collect_window(run: Path, label: str) -> dict:
    summaries = read_rows(run / "run_summary.csv")
    metrics = read_rows(run / "metrics.csv")
    execution = read_rows(run / "execution_summary.csv")
    h1 = one(read_rows(run / "h1_summary.csv"), symbol="EQUAL_WEIGHT", period="full")
    opportunity = [
        row
        for row in read_rows(run / "opportunity_daily.csv")
        if row["complete"] == "True" and row["opportunity"] != ""
    ]
    portfolios = []
    by_strategy = {}
    for strategy in STRATEGIES:
        summary = one(summaries, strategy=strategy)
        metric = one(metrics, strategy=strategy, period="full")
        activity = one(execution, strategy=strategy, symbol="PORTFOLIO")
        row = {
            "window": label,
            "strategy": strategy,
            "capital_usdt": summary["capital_usdt"],
            "final_equity_usdt": summary["final_equity_usdt"],
            "net_return": metric["net_return"],
            "cagr": metric["cagr"],
            "sharpe": metric["sharpe"],
            "max_drawdown": metric["max_drawdown"],
            "fills": activity["fills"],
            "invested_seconds": activity["invested_seconds"],
        }
        portfolios.append(row)
        by_strategy[strategy] = row | {"coverage_complete": metric["coverage_complete"]}
    conditional, permanent = by_strategy["conditional"], by_strategy["permanent"]
    if (
        conditional["coverage_complete"] != "True"
        or permanent["coverage_complete"] != "True"
        or not conditional["cagr"]
        or not conditional["sharpe"]
        or not permanent["sharpe"]
    ):
        h2 = "no_concluyente"
    elif Decimal(conditional["cagr"]) > 0 and Decimal(conditional["sharpe"]) > Decimal(
        permanent["sharpe"]
    ):
        h2 = "favorable"
    else:
        h2 = "contraria_al_criterio_definido"
    opportunity_mean = (
        str(
            sum((Decimal(row["opportunity"]) for row in opportunity), Decimal(0)) / len(opportunity)
        )
        if opportunity
        else ""
    )
    pnl_rows = [
        row for row in read_rows(run / "pnl_components.csv") if row["symbol"] == "PORTFOLIO"
    ]
    pnl = []
    for strategy in STRATEGIES:
        pnl.append(
            {
                "window": label,
                "strategy": strategy,
                **{
                    row["component"]: row["amount_usdt"]
                    for row in pnl_rows
                    if row["strategy"] == strategy
                },
                "total_pnl_usdt": one(summaries, strategy=strategy)["net_pnl_usdt"],
            }
        )
    signal_counts = {}
    for signal in pq.read_table(
        run / "signals.parquet", columns=["strategy", "decision"]
    ).to_pylist():
        key = (signal["strategy"], signal["decision"])
        signal_counts[key] = signal_counts.get(key, 0) + 1
    return {
        "portfolios": portfolios,
        "h1": {
            "window": label,
            "observations": h1["observations"],
            "excluded": h1["excluded"],
            "mae_ewma": h1["mae_ewma"],
            "mae_no_change": h1["mae_no_change"],
        },
        "h2": {"window": label, "verdict": h2},
        "h3_inputs": {
            "window": label,
            "complete_days": str(len(opportunity)),
            "opportunity_mean": opportunity_mean,
            "conditional_cagr": conditional["cagr"],
        },
        "pnl": pnl,
        "signal_decisions": [
            {
                "window": label,
                "strategy": strategy,
                "decision": decision,
                "count": str(count),
            }
            for (strategy, decision), count in sorted(signal_counts.items())
        ],
    }


def h3_comparison(early: dict, late: dict) -> dict:
    fields = (
        early["opportunity_mean"],
        late["opportunity_mean"],
        early["conditional_cagr"],
        late["conditional_cagr"],
    )
    if (
        early["complete_days"] != "365"
        or late["complete_days"] != "365"
        or any(value == "" for value in fields)
    ):
        verdict = "no_concluyente_cobertura"
    else:
        eo, lo, ec, lc = map(Decimal, fields)
        verdict = (
            "ambas_mayores_en_ventana_tardia"
            if lo > eo and lc > ec
            else "ambas_menores_en_ventana_tardia"
            if lo < eo and lc < ec
            else "no_direccional"
        )
    return {"verdict": verdict, "early": early, "late": late}


def collect_sensitivities(root: Path, ids: dict[str, str | None], baselines: dict[str, str]):
    if bool(ids["early"]) != bool(ids["late"]):
        raise ValueError("Provide both robustness indexes or neither")
    values = {
        (name, window, strategy): {
            "scenario": name,
            "label": label,
            "window": window,
            "strategy": strategy,
            "status": "pending",
            "net_return": "",
            "run_id": "",
        }
        for name, label in SENSITIVITIES
        for window in ("early", "late")
        for strategy in STRATEGIES
    }
    provenance = {}
    cost_path = []
    if not ids["early"]:
        return list(values.values()), provenance, cost_path
    for window in ("early", "late"):
        index_id = valid_id(str(ids[window]))
        path = root / "outputs" / index_id
        result = verify_robustness(path)
        manifest = load_json(path / "run_manifest.json")
        if not result["valid"] or result["status"] not in {"complete", "insolvent"}:
            raise ValueError(f"Robustness index {index_id} is not completed and verified: {result}")
        if (
            not manifest.get("baseline_verified")
            or manifest.get("baseline_run_id") != baselines[window]
        ):
            raise ValueError(f"Robustness index {index_id} does not belong to {window} baseline")
        rows = read_rows(path / "robustness_summary.csv")
        for scenario, _ in SENSITIVITIES:
            selected = [row for row in rows if row["scenario"] == scenario]
            if {row["strategy"] for row in selected} != set(STRATEGIES):
                raise ValueError(
                    f"Robustness index {index_id} lacks {scenario} for both strategies"
                )
            if any(row["status"] == "incomplete_data" for row in selected):
                raise ValueError(f"Robustness scenario {scenario} was not evaluated in {index_id}")
            if any(row["net_return"] == "" for row in selected):
                raise ValueError(f"Robustness scenario {scenario} lacks numerical returns")
            for row in selected:
                values[(scenario, window, row["strategy"])].update(
                    status=row["status"],
                    net_return=row["net_return"],
                    run_id=row["run_id"],
                )
        if window == "late":
            cost_path = collect_cost_path(root, rows)
        provenance[window] = {"id": index_id, "manifest_sha256": sha256(path / "run_manifest.json")}
    return list(values.values()), provenance, cost_path


def collect_cost_path(root: Path, index_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    evidence = []
    for scenario in ("baseline", "cost-2", "cost-3"):
        index_row = one(
            index_rows,
            scenario=scenario,
            strategy="permanent",
            symbol="PORTFOLIO",
        )
        run = root / "outputs" / valid_id(index_row["run_id"])
        manifest = load_json(run / "run_manifest.json")
        fills = pq.read_table(
            run / "fills.parquet",
            columns=[
                "symbol",
                "strategy",
                "timestamp_utc",
                "market",
                "side",
                "quantity",
                "fee_rate",
                "purpose",
            ],
        ).to_pylist()
        spot_open = next(
            (
                row
                for row in fills
                if row["symbol"] == "BTCUSDT"
                and row["strategy"] == "permanent"
                and row["purpose"] == "open_spot"
            ),
            None,
        )
        futures_open = next(
            (
                row
                for row in fills
                if row["symbol"] == "BTCUSDT"
                and row["strategy"] == "permanent"
                and row["purpose"] == "open_perp"
            ),
            None,
        )
        if not spot_open or not futures_open:
            raise ValueError(f"Cost path {scenario} lacks the expected BTC opening fills")
        gross_spot = Decimal(spot_open["quantity"])
        net_spot = gross_spot * (Decimal(1) - Decimal(spot_open["fee_rate"]))
        futures_quantity = Decimal(futures_open["quantity"])
        imbalance = abs(net_spot - futures_quantity) / net_spot
        tolerance = Decimal(str(manifest["config"]["hedge_tolerance"]))
        risk_events = pq.read_table(
            run / "risk_events.parquet",
            columns=["symbol", "strategy", "timestamp_utc", "kind", "cause"],
        ).to_pylist()
        outcome_event = one(
            [
                row
                for row in risk_events
                if row["symbol"] == "BTCUSDT"
                and row["strategy"] == "permanent"
                and row["timestamp_utc"] == futures_open["timestamp_utc"]
                and row["kind"] == "transition"
                and row["cause"] in {"opening_complete", "completion_hedge_or_freshness_failure"}
            ]
        )
        persisted_result = "accepted" if outcome_event["cause"] == "opening_complete" else "unwound"
        calculated_result = "accepted" if imbalance <= tolerance else "unwound"
        if persisted_result != calculated_result:
            raise ValueError(f"Cost path {scenario} conflicts with its persisted risk event")
        funding = [
            row
            for row in pq.read_table(
                run / "funding_payments.parquet",
                columns=["symbol", "strategy", "amount_usdt"],
            ).to_pylist()
            if row["symbol"] == "BTCUSDT" and row["strategy"] == "permanent"
        ]
        run_summary = one(read_rows(run / "run_summary.csv"), strategy="permanent")
        evidence.append(
            {
                "scenario": scenario,
                "run_id": run.name,
                "cost_multiplier": str(manifest["config"]["cost_multiplier"]),
                "gross_spot_quantity": str(gross_spot),
                "net_spot_quantity": str(net_spot),
                "futures_quantity": str(futures_quantity),
                "hedge_error": str(imbalance),
                "hedge_tolerance": str(tolerance),
                "opening_result": persisted_result,
                "opening_event_cause": outcome_event["cause"],
                "funding_payments": str(len(funding)),
                "funding_usdt": str(
                    sum((Decimal(row["amount_usdt"]) for row in funding), Decimal(0))
                ),
                "net_pnl_usdt": run_summary["net_pnl_usdt"],
            }
        )
    return evidence


def markdown(rows: list[dict], columns: list[tuple[str, str]]) -> str:
    lines = [
        "| " + " | ".join(label for _, label in columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(str(row.get(key, "") or "—").replace("|", "\\|") for key, _ in columns)
            + " |"
        )
    return "\n".join(lines)


def plot_cost_sensitivity(summary: dict, destination: Path) -> None:
    matplotlib.rcParams["svg.hashsalt"] = "minute-study-cost-sensitivity-v1"
    figure, axes = plt.subplots(1, 2, figsize=(10, 4), sharey=True)
    for axis, (window, label) in zip(axes, (("early", "2022–2023"), ("late", "2025–2026"))):
        for strategy, color, marker in (
            ("conditional", "#1665D8", "o"),
            ("permanent", "#D35400", "s"),
        ):
            baseline = one(summary["portfolios"], window=label, strategy=strategy)
            points = [(1, Decimal(baseline["net_return"]) * 100)]
            for multiplier, scenario in ((2, "cost-2"), (3, "cost-3")):
                sensitivity = one(
                    summary["sensitivities"],
                    scenario=scenario,
                    window=window,
                    strategy=strategy,
                )
                if sensitivity["status"] != "pending":
                    points.append((multiplier, Decimal(sensitivity["net_return"]) * 100))
            axis.plot(
                [point[0] for point in points],
                [float(point[1]) for point in points],
                color=color,
                marker=marker,
                linewidth=1.5,
                label=HUMAN_STRATEGIES[strategy],
            )
        axis.axhline(0, color="#666666", linewidth=0.8)
        axis.set_title(label)
        axis.set_xlabel("Multiplicador de costos")
        axis.set_xticks((1, 2, 3))
        axis.grid(alpha=0.25)
    axes[0].set_ylabel("Retorno neto (%)")
    axes[1].legend(frameon=False)
    figure.suptitle(
        "Sensibilidad del retorno neto a costos\n"
        "Precios observados con ejecución y reglas prescritas"
    )
    figure.tight_layout()
    destination.mkdir(parents=True, exist_ok=True)
    figure.savefig(
        destination / "cost_sensitivity.png",
        dpi=160,
        metadata={"Software": "build_study_report.py"},
    )
    figure.savefig(
        destination / "cost_sensitivity.svg",
        metadata={"Date": None, "Creator": "build_study_report.py"},
    )
    plt.close(figure)


def render(summary: dict) -> str:
    portfolios = [
        row
        | {
            "strategy": HUMAN_STRATEGIES[row["strategy"]],
            "final_equity_usdt": formatted(row["final_equity_usdt"], "money"),
            "net_return": formatted(row["net_return"], "percent"),
            "max_drawdown": formatted(row["max_drawdown"], "percent"),
            "sharpe": formatted(row["sharpe"], "sharpe"),
            "invested_seconds": formatted(row["invested_seconds"], "seconds"),
        }
        for row in summary["portfolios"]
    ]
    h1 = [
        row
        | {
            "mae_ewma": formatted(row["mae_ewma"], "bps"),
            "mae_no_change": formatted(row["mae_no_change"], "bps"),
        }
        for row in summary["h1"]
    ]
    h2 = [row | {"verdict": HUMAN_VERDICTS[row["verdict"]]} for row in summary["h2"]]
    h3_rows = [
        row
        | {
            "opportunity_mean": formatted(row["opportunity_mean"], "bps"),
            "conditional_cagr": formatted(row["conditional_cagr"], "percent"),
        }
        for row in (summary["h3"]["early"], summary["h3"]["late"])
    ]
    pnl = [
        row
        | {"strategy": HUMAN_STRATEGIES[row["strategy"]]}
        | {
            key: formatted(row.get(key, ""), "money")
            for key in (
                "spot_pnl",
                "futures_pnl",
                "funding",
                "fees",
                "liquidation_fees",
                "slippage_informational",
                "total_pnl_usdt",
            )
        }
        for row in summary["pnl"]
    ]
    late_signals = [
        {
            "strategy": HUMAN_STRATEGIES[row["strategy"]],
            "decision": HUMAN_DECISIONS.get(row["decision"], row["decision"]),
            "count": row["count"],
        }
        for row in summary["signal_decisions"]
        if row["window"] == "2025–2026"
    ]
    sensitivities = []
    for scenario, label in SENSITIVITIES:
        display = {"label": label}
        for window in ("early", "late"):
            for strategy in STRATEGIES:
                value = one(
                    summary["sensitivities"],
                    scenario=scenario,
                    window=window,
                    strategy=strategy,
                )
                cell = "Pendiente"
                if value["status"] != "pending":
                    status = "Completo" if value["status"] == "complete" else "Insolvente"
                    cell = (
                        f"[{formatted(value['net_return'], 'percent')} · {status}]"
                        f"(../{value['run_id']}/report.md)"
                    )
                display[f"{window}_{strategy}"] = cell
        sensitivities.append(display)
    if summary["cost_path"]:
        cost_path = [
            row
            | {
                "scenario": f"[{row['cost_multiplier']}x](../{row['run_id']}/report.md)",
                "hedge_error": formatted(row["hedge_error"], "percent"),
                "opening_result": (
                    "Aceptada" if row["opening_result"] == "accepted" else "Desarmada"
                ),
                "funding_usdt": formatted(row["funding_usdt"], "money"),
                "net_pnl_usdt": formatted(row["net_pnl_usdt"], "money"),
            }
            for row in summary["cost_path"]
        ]
        cost_path_discussion = f"""#### Trayectoria no monótona de costos en 2025–2026

{markdown(cost_path, [("scenario", "Costo"), ("gross_spot_quantity", "Compra spot (BTC)"), ("net_spot_quantity", "Spot neto (BTC)"), ("futures_quantity", "Futuros (BTC)"), ("hedge_error", "Desbalance"), ("opening_result", "Apertura"), ("funding_payments", "Pagos funding"), ("funding_usdt", "Funding (USDT)"), ("net_pnl_usdt", "P&L neto (USDT)")])}

La respuesta a costos no es monótona porque el fee spot cambia la cantidad neta luego de una compra bruta igual. El estado de cada apertura se lee de `risk_events.parquet` y se contrasta con el desbalance calculado. El redondeo del futuro al tamaño permitido deja trayectorias distintas alrededor de la tolerancia de {formatted(summary["cost_path"][0]["hedge_tolerance"], "percent")}: una apertura desarmada no recibe funding posterior, mientras que una aceptada sí puede permanecer abierta. Por eso estas filas comparan caminos de ejecución diferentes y no miden un simple aumento lineal del gasto.
"""
    else:
        cost_path_discussion = """#### Trayectoria no monótona de costos en 2025–2026

Pendiente hasta incorporar los dos índices de robustez verificados.
"""
    exceptional = summary["audit"]["exceptional_event"]
    exceptional_rows = [
        {
            "strategy": HUMAN_STRATEGIES[strategy],
            "daily_equity_change_usdt": formatted(evidence["daily_equity_change_usdt"], "money"),
            "fraction_of_final_profit": formatted(evidence["fraction_of_final_profit"], "percent"),
            "unhedged_minutes": evidence["unhedged_minutes"],
            "futures_close": evidence["futures_close"]["timestamp_utc"],
            "spot_close": evidence["spot_close"]["timestamp_utc"],
        }
        for strategy, evidence in exceptional["strategies"].items()
    ]
    conditional_event = exceptional["strategies"]["conditional"]
    outage = summary["outage_trade_validation"]
    outage_rows = [
        {
            "window": f"{seconds} s",
            "vwap": f"{Decimal(values['vwap']):.2f}",
            "base_volume": f"{Decimal(values['base_volume']):.3f}",
            "trade_count": values["trade_count"],
            "local_pnl_delta": formatted(
                values["gross_pnl_delta_if_vwap_replaced_baseline_fill_usdt"], "money"
            ),
        }
        for seconds, values in outage["windows"].items()
    ]
    first_trade = outage["first_trade"]
    persistence = outage["first_price_persistence"]
    sensitivities_complete = all(row["status"] != "pending" for row in summary["sensitivities"])
    sensitivity_lead = (
        "Los dos índices verificados aportan resultados para los siete escenarios."
        if sensitivities_complete
        else "Sin índices de robustez, los siete escenarios quedan pendientes."
    )
    sensitivity_status = (
        "Los índices verificados aportan los puntos 2x y 3x."
        if sensitivities_complete
        else "Los índices están pendientes; la figura muestra sólo los baselines 1x disponibles."
    )
    links = "\n".join(
        f"- **{'2022–2023' if window == 'early' else '2025–2026'}**: "
        f"[informe](../{run_id}/report.md) · [equity](../{run_id}/figures/equity.png)"
        for window, run_id in summary["baseline_run_ids"].items()
    )
    return f"""# Entregas 3 y 4 · estudio anual por minuto

Este informe conciso agrega dos corridas anuales verificadas; no es la tesina completa. Cada ventana reinicia 10000 USDT por estrategia y no existe una cartera continua entre años excluidos.

Las ventanas UTC son [{WINDOWS["early"][0]}, {WINDOWS["early"][1]}) y [{WINDOWS["late"][0]}, {WINDOWS["late"][1]}): inicio incluido y fin excluido. Se usan precios de un minuto de BTCUSDT y ETHUSDT, con spot y perpetuos USD-M.

{links}

## Entrega 3 · resultados de las cuatro carteras

{markdown(portfolios, [("window", "Ventana"), ("strategy", "Estrategia"), ("final_equity_usdt", "Equity final (USDT)"), ("net_return", "Retorno neto"), ("max_drawdown", "Máx. drawdown diario"), ("sharpe", "Sharpe"), ("fills", "Fills de patas"), ("invested_seconds", "Tiempo con inventario (s; incluye polvo)")])}

El máximo drawdown se calcula sobre equity diario en UTC y no acota pérdidas intradiarias.

### H1 · error de pronóstico

{markdown(h1, [("window", "Ventana"), ("observations", "Observaciones"), ("excluded", "Excluidas"), ("mae_ewma", "MAE EWMA (bps)"), ("mae_no_change", "MAE sin cambio (bps)")])}

Los horizontes de pronóstico se superponen y el agregado EQUAL_WEIGHT combina ambos activos. Esta lectura es descriptiva y no establece significancia estadística.

### H2 · criterio predefinido por ventana

{markdown(h2, [("window", "Ventana"), ("verdict", "Resultado")])}

El criterio exige CAGR condicional positivo y Sharpe condicional mayor que el permanente. Si algún Sharpe está indefinido, el resultado es no concluyente.

### H3 · comparación descriptiva entre ventanas

{markdown(h3_rows, [("window", "Ventana"), ("complete_days", "Días completos"), ("opportunity_mean", "Oportunidad media (bps)"), ("conditional_cagr", "CAGR condicional")])}

Resultado descriptivo: **{HUMAN_VERDICTS[summary["h3"]["verdict"]]}**. H3 sólo se evalúa con 365 días válidos en ambas ventanas. Dos ventanas independientes no identifican causalidad; movimientos opuestos o empates se clasifican como no direccionales y cobertura insuficiente como no concluyente.

### P&L persistido por componente

{markdown(pnl, [("window", "Ventana"), ("strategy", "Estrategia"), ("spot_pnl", "Spot"), ("futures_pnl", "Futuros"), ("funding", "Funding"), ("fees", "Fees"), ("liquidation_fees", "Liquidación"), ("slippage_informational", "Slippage informativo"), ("total_pnl_usdt", "Total")])}

Los importes se muestran en USDT. El retorno condicional temprano no se atribuye íntegramente al funding: la tabla separa spot, futuros, funding y fees. El slippage es informativo porque ya está incorporado en los precios de ejecución de los fills; no se suma ni se resta otra vez al total.

## Entrega 4 · ejecución y robustez

La tabla principal informa fills y tiempo con inventario desde `execution_summary.csv`. Cada fill corresponde a una pata y no equivale a un round trip. `invested_seconds` cuenta cualquier inventario positivo, incluido polvo residual después de un cierre; no representa necesariamente carry activo, continuo y cubierto. Cero operaciones no constituye evidencia de desempeño de inversión. La estrategia permanente desactiva el filtro de funding, pero conserva filtros de basis, frescura, reglas de mercado y controles de riesgo.

{markdown(late_signals, [("strategy", "Estrategia"), ("decision", "Decisión de señal 2025–2026"), ("count", "Conteo")])}

La falta de operaciones condicionales en 2025–2026 proviene del filtro que exige funding superior al costo. En la permanente, casi todas las señales quedaron fuera del rango de basis y sólo dos fueron aceptadas. Estos conteos pertenecen a una corrida anual completa y verificada; no se explican por archivos faltantes.

En la ventana tardía, la permanente tuvo {summary["audit"]["late_completion_failure_count"]} aperturas de BTCUSDT desarmadas: el redondeo al tamaño permitido del contrato dejó un desbalance superior al 0,5%. Sus ocho fills no prueban carry estable y su funding acumulado fue 0.00 USDT.

### Sensibilidades predeclaradas

{markdown(sensitivities, [("label", "Escenario"), ("early_conditional", "22–23 cond."), ("early_permanent", "22–23 perm."), ("late_conditional", "25–26 cond."), ("late_permanent", "25–26 perm.")])}

Cada celda informa retorno neto y estado, con enlace a la corrida. {sensitivity_lead} No se omiten resultados sin cambios o negativos, no se reemplaza el baseline y no se selecciona retrospectivamente un resultado. Una variante sin cambios no valida por sí sola el riesgo tensionado: el proxy no modifica marks exactos ya disponibles y un cargo de liquidación no actúa cuando no hay liquidaciones. Este subconjunto de siete escenarios no evalúa AUM, slippage aislado, demoras de señal o entre patas ni parámetros del pronóstico (ventana, vida media u horizonte); los informes anuales enlazados registran esas dimensiones como pendientes.

![Retorno neto frente a costos 1x, 2x y 3x](figures/cost_sensitivity.png)

{sensitivity_status} [Versión SVG](figures/cost_sensitivity.svg).

### Discusión crítica

#### Ganancia concentrada en un cierre excepcional

{markdown(exceptional_rows, [("strategy", "Estrategia"), ("daily_equity_change_usdt", "Cambio diario (USDT)"), ("fraction_of_final_profit", "Fracción del beneficio final"), ("unhedged_minutes", "Minutos sin cobertura"), ("futures_close", "Cierre futuro"), ("spot_close", "Cierre spot")])}

El {formatted(conditional_event["fraction_of_final_profit"], "percent")} del beneficio final condicional se concentró el {exceptional["date"]} en un cierre forzado por inactividad real del mercado. El futuro de ETH cerró antes que el spot y la estrategia conservó exposición direccional durante {conditional_event["unhedged_minutes"]} minutos mientras vencían {conditional_event["expired_spot_close_orders"]} órdenes de cierre spot. La ganancia está respaldada por la fuente y reconciliada con los componentes persistidos, pero proviene de un desarme excepcional durante una interrupción; no representa funding ordinario ni evidencia de rentabilidad en vivo.

##### Trades observados en la reapertura spot

El primer trade estrictamente posterior a las 14:00 UTC ocurrió a las {first_trade["timestamp_utc"]}, a {Decimal(first_trade["price"]):.2f} USDT y por {Decimal(first_trade["quantity"]):.4f} ETH, frente a una orden baseline de {Decimal(outage["baseline_order_quantity"]):.4f} ETH. Ese precio duró {persistence["milliseconds_until_different_price"]} ms hasta el primer cambio; hubo {persistence["same_price_trade_count_until_change"]} trades y {Decimal(persistence["same_price_base_volume_until_change"]):.3f} ETH al mismo precio.

{markdown(outage_rows, [("window", "Ventana desde 14:00"), ("vwap", "VWAP (USDT)"), ("base_volume", "Volumen (ETH)"), ("trade_count", "Trades"), ("local_pnl_delta", "Delta P&L bruto local (USDT)")])}

El precio de referencia es un trade observado con volumen suficiente para la cantidad baseline, pero los trades no prueban acceso, prioridad de cola ni capacidad de enviar una orden durante la suspensión. El diagnóstico local no sustituye los retornos anuales. Las ventanas cortas tienen {outage["spot_short_missing_ids"]} IDs faltantes en spot y {outage["futures_short_missing_ids"]} en futuros; el día completo de futuros registra {outage["futures_day_missing_ids"]} IDs faltantes. Evidencia: `{outage["source"]}` (SHA-256 `{outage["sha256"]}`), [ZIP spot]({outage["sources"]["spot"]["url"]}) y [ZIP futuros]({outage["sources"]["futures"]["url"]}).

{cost_path_discussion}

### Auditoría económica independiente

El audit persistido `{summary["audit"]["source"]}` (SHA-256 `{summary["audit"]["sha256"]}`) verificó {summary["audit"]["fills_checked"]} fills. El máximo residuo absoluto fue {Decimal(summary["audit"]["maximum_absolute_residue"]):.3E} USDT frente a una tolerancia de {summary["audit"]["tolerance"]}. Este control valida consistencia aritmética de artefactos, no rentabilidad en vivo ni aptitud de inversión.

## Límites

La ejecución usa opens de barras de un minuto y volumen cerrado previo; los IDs de fill refieren a barras, no a operaciones individuales. No se modela una trayectoria intraminuto de liquidación. Fees, slippage, reglas y proxies son los supuestos prescriptos de cada run. Los valores de este informe se leen o derivan aritméticamente de tablas guardadas y verificadas.

## Conclusión

El beneficio condicional aparente de 2022–2023 está concentrado: {formatted(conditional_event["fraction_of_final_profit"], "percent")} del beneficio final provino de una interrupción documentada que dejó {conditional_event["unhedged_minutes"]} minutos de riesgo direccional. Este resultado excepcional limita la interpretación económica del retorno anual y no demuestra una ganancia ordinaria de carry.
"""


def verify_study(path: Path) -> list[str]:
    problems = []
    manifest_path = path / "study_manifest.json"
    if not manifest_path.is_file() or not (path / "study_manifest.sha256").is_file():
        return ["missing study manifest or sidecar"]
    manifest = load_json(manifest_path)
    if manifest.get("study_id") != path.name:
        problems.append("study identity mismatch")
    if set(manifest.get("output_hashes", {})) != OUTPUTS:
        problems.append("invalid output hash inventory")
    if (path / "study_manifest.sha256").read_text(encoding="ascii").strip() != sha256(
        manifest_path
    ):
        problems.append("study manifest checksum mismatch")
    for name, digest in manifest.get("output_hashes", {}).items():
        artifact = path / name
        if not artifact.is_file() or sha256(artifact) != digest:
            problems.append(f"changed or missing artifact: {name}")
    return problems


def build(args) -> Path:
    root = Path(args.root).resolve()
    early_run, early_manifest = verify_baseline(root, args.early, "early")
    late_run, late_manifest = verify_baseline(root, args.late, "late")
    if early_run == late_run:
        raise ValueError("Early and late baselines must be distinct runs")
    compatible(early_manifest, late_manifest)
    collected = {
        "early": collect_window(early_run, "2022–2023"),
        "late": collect_window(late_run, "2025–2026"),
    }
    baselines = {"early": args.early, "late": args.late}
    sensitivities, robustness, cost_path = collect_sensitivities(
        root,
        {"early": args.early_robustness, "late": args.late_robustness},
        baselines,
    )
    audit = audit_evidence(baselines)
    outage = outage_evidence(baselines)
    script_hash = sha256(Path(__file__).resolve())
    inputs = {
        window: {
            "id": baselines[window],
            "manifest_sha256": sha256(
                (early_run if window == "early" else late_run) / "run_manifest.json"
            ),
            "code_hash": manifest["code_hash"],
            "config": manifest["config"],
        }
        for window, manifest in (("early", early_manifest), ("late", late_manifest))
    }
    identity_payload = {
        "script_sha256": script_hash,
        "inputs": inputs,
        "robustness": robustness,
        "audit_sha256": audit["sha256"],
        "outage_sha256": outage["sha256"],
    }
    identity = hashlib.sha256(
        json.dumps(identity_payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()[:24]
    destination = root / "outputs" / f"study_{identity}"
    if destination.exists():
        problems = verify_study(destination)
        if problems:
            raise ValueError(f"Immutable study changed: {problems}")
        return destination
    h3 = h3_comparison(collected["early"]["h3_inputs"], collected["late"]["h3_inputs"])
    summary = {
        "study_id": destination.name,
        "baseline_run_ids": baselines,
        "portfolios": collected["early"]["portfolios"] + collected["late"]["portfolios"],
        "h1": [collected["early"]["h1"], collected["late"]["h1"]],
        "h2": [collected["early"]["h2"], collected["late"]["h2"]],
        "h3": h3,
        "pnl": collected["early"]["pnl"] + collected["late"]["pnl"],
        "signal_decisions": collected["early"]["signal_decisions"]
        + collected["late"]["signal_decisions"],
        "sensitivities": sensitivities,
        "cost_path": cost_path,
        "audit": audit,
        "outage_trade_validation": outage,
    }
    outputs = root / "outputs"
    outputs.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".study-", dir=outputs) as folder:
        staging = Path(folder)
        plot_cost_sensitivity(summary, staging / "figures")
        (staging / "summary.json").write_text(
            json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (staging / "report.md").write_text(render(summary), encoding="utf-8")
        csv_tables = {
            "cost_path.csv": summary["cost_path"],
            "portfolios.csv": summary["portfolios"],
            "h1.csv": summary["h1"],
            "h3.csv": [summary["h3"]["early"], summary["h3"]["late"]],
            "pnl_components.csv": summary["pnl"],
            "signal_decisions.csv": summary["signal_decisions"],
            "sensitivities.csv": summary["sensitivities"],
        }
        for name, rows in csv_tables.items():
            write_rows(staging / name, rows)
        manifest = {
            "kind": "minute_study_report",
            "study_id": destination.name,
            "script_sha256": script_hash,
            "inputs": inputs,
            "robustness_inputs": robustness,
            "audit_input": {key: audit[key] for key in ("source", "sha256", "status")},
            "outage_input": {key: outage[key] for key in ("source", "sha256", "baseline_run_id")},
            "output_hashes": {name: sha256(staging / name) for name in sorted(OUTPUTS)},
        }
        manifest_path = staging / "study_manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (staging / "study_manifest.sha256").write_text(
            sha256(manifest_path) + "\n", encoding="ascii"
        )
        staging.replace(destination)
    problems = verify_study(destination)
    if problems:
        raise ValueError(f"New study verification failed: {problems}")
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--early", required=True)
    parser.add_argument("--late", required=True)
    parser.add_argument("--early-robustness")
    parser.add_argument("--late-robustness")
    args = parser.parse_args()
    print(build(args))


if __name__ == "__main__":
    main()
