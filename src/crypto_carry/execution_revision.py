"""Reproducible execution-method revision matrix built from immutable runs."""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
import tempfile
from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pyarrow.parquet as pq

from .config import HOUR, Config, timestamp
from .data.prescribed import prescribed_rules
from .data.replay import _select_partitions, input_hashes, iter_records
from .data.validate import validate_data
from .diagnostics import FILTER_ORDER
from .reporting import _code_identity, verify_run, write_run
from .strategy import Backtest

LEGACY_REFERENCES = {
    "early": "run_8fb22fa8b377466cff981b99",
    "late": "run_0cb21afbec7cdba1e5848df6",
}
SCENARIOS = (
    "legacy_reference",
    "joint_sizing_only",
    "alignment_only",
    "vwap_only",
    "vwap_joint",
)
STRATEGIES = (("conditional", True), ("permanent", False))
_NEW_CONFIG_FIELDS = {"sizing_model", "signal_price_model", "max_volume_participation"}


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _load_config(value: Config | str | Path) -> Config:
    return value if isinstance(value, Config) else Config.load(value)


def execution_revision_scenarios(base: Config) -> dict[str, Config]:
    """Return the controlled five-scenario matrix in report order."""
    if base.analysis_mode != "prescribed_research" or base.execution_model != "minute_open":
        raise ValueError("Execution revision requires a prescribed minute_open legacy profile")
    legacy = base.changed(
        execution_model="minute_open",
        sizing_model="legacy",
        signal_price_model="execution_default",
    )
    return {
        "legacy_reference": legacy,
        "joint_sizing_only": legacy.changed(sizing_model="joint_quantity"),
        "alignment_only": legacy.changed(signal_price_model="closed_minute"),
        "vwap_only": legacy.changed(
            execution_model="next_minute_vwap", signal_price_model="closed_minute"
        ),
        "vwap_joint": legacy.changed(
            execution_model="next_minute_vwap",
            sizing_model="joint_quantity",
            signal_price_model="closed_minute",
        ),
    }


def _read_manifest(run: Path) -> dict:
    result = verify_run(run)
    if not result["valid"]:
        raise ValueError(f"Run verification failed for {run}: {result['mismatches']}")
    return json.loads((run / "run_manifest.json").read_text(encoding="utf-8"))


def _matching_reference(root: Path, window: str, config: Config, inputs: dict) -> Path:
    run = root / "outputs" / LEGACY_REFERENCES[window]
    manifest = _read_manifest(run)
    expected = config.to_dict()
    actual = manifest.get("config", {})
    mismatches = {
        key: (actual.get(key), value)
        for key, value in expected.items()
        if key not in _NEW_CONFIG_FIELDS and actual.get(key) != value
    }
    if mismatches:
        raise ValueError(f"Legacy reference configuration mismatch for {window}: {mismatches}")
    legacy_inputs = manifest.get("input_hashes", {})
    changed_inputs = {
        name: (digest, inputs.get(name))
        for name, digest in legacy_inputs.items()
        if name != "processed_manifest_semantics" and inputs.get(name) != digest
    }
    if changed_inputs:
        raise ValueError(
            f"Legacy reference partition/source hashes differ for {window}: {changed_inputs}"
        )
    if manifest.get("requested_range") != {
        "start": config.start,
        "end": config.end,
        "end_inclusive": False,
        "history_start": config.history_start,
    }:
        raise ValueError(f"Legacy reference range mismatch for {window}")
    return run


def _revision_input_hashes(root: Path, config: Config) -> dict[str, str]:
    """Hash only persisted partitions the selected replay model can consume."""
    manifest_path = root / config.data_dir / "manifests" / "processed.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    datasets = {"marks", "funding", "gaps"}
    if config.execution_model == "next_minute_vwap":
        datasets.add("minute_bars")
    else:
        datasets.update({"minute_prices", "minute_volumes"})
        if config.signal_price_model == "closed_minute":
            datasets.add("minute_bars")
    start, end = timestamp(config.start), timestamp(config.end)
    grouped = defaultdict(list)
    for entry in manifest.get("entries", []):
        if entry.get("dataset") in datasets:
            grouped[(entry["dataset"], entry.get("symbol", ""), entry.get("market", ""))].append(
                entry
            )
    selected = []
    for (dataset, _symbol, _market), entries in grouped.items():
        lower = start - (config.window_hours + 24) * HOUR if dataset == "funding" else start
        selected.extend(_select_partitions(entries, lower, end))
    semantic = {
        "kind": manifest.get("kind"),
        "version": manifest.get("version"),
        "entries": selected,
        "execution_model": config.execution_model,
        "include_closed_bars": config.signal_price_model == "closed_minute",
    }
    result = {"processed_replay_semantics": hashlib.sha256(_json(semantic).encode()).hexdigest()}
    for entry in selected:
        path = root / entry["path"]
        if not path.is_file():
            raise ValueError(f"Missing selected replay input: {entry['path']}")
        digest = _hash(path)
        if entry.get("sha256") and digest != entry["sha256"]:
            raise ValueError(f"Selected replay input checksum mismatch: {entry['path']}")
        result[entry["path"]] = digest
    return result


def _cached_run(root: Path, config: Config, inputs: dict, label: str) -> Path | None:
    code_hash, _ = _code_identity()
    identity = {
        "config": config.to_dict(),
        "code_hash": code_hash,
        "input_hashes": inputs,
        "strategies": [
            {"strategy": name, "funding_filter_enabled": enabled} for name, enabled in STRATEGIES
        ],
        "data_kind": "historical_assumptions",
        "label": label,
    }
    candidate = (
        root
        / "outputs"
        / ("run_" + hashlib.sha256(_json(identity).encode("utf-8")).hexdigest()[:24])
    )
    if not candidate.exists():
        return None
    manifest = _read_manifest(candidate)
    if any(manifest.get(key) != value for key, value in identity.items()):
        raise ValueError(f"Cached immutable run identity is inconsistent: {candidate}")
    return candidate


def _run_scenario(root: Path, window: str, scenario: str, config: Config, quality, inputs) -> Path:
    label = f"execution-revision:{window}:{scenario}"
    cached = _cached_run(root, config, inputs, label)
    if cached is not None:
        print(f"[{window}/{scenario}] reused {cached.name}", flush=True)
        return cached
    rules = prescribed_rules(config)
    results = []
    for strategy, enabled in STRATEGIES:
        print(f"[{window}/{scenario}/{strategy}] replay", flush=True)
        backtest = Backtest(config, rules, strategy, enabled, inputs)
        backtest.run(
            iter_records(
                root,
                timestamp(config.start),
                timestamp(config.end),
                config.window_hours + 24,
                data_dir=config.data_dir,
                execution_model=config.execution_model,
                include_closed_bars=config.signal_price_model == "closed_minute",
            )
        )
        results.append(backtest)
    run = write_run(
        root,
        config,
        results,
        quality,
        "historical_assumptions",
        label=label,
        inputs=inputs,
    )
    _read_manifest(run)
    return run


def _rows(run: Path, name: str) -> list[dict]:
    path = run / name
    if not path.is_file():
        return []
    if path.suffix == ".parquet":
        return pq.read_table(path).to_pylist()
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _decimal(value, default=Decimal(0)) -> Decimal:
    try:
        return Decimal(str(value)) if value not in (None, "") else default
    except Exception:
        return default


def _yes(value) -> bool:
    return str(value).lower() in {"true", "1"}


def _position_durations(
    rows: list[dict], end_ns: int, tolerance: Decimal, start_ns: int = 0
) -> dict[tuple, dict]:
    grouped = defaultdict(list)
    for row in rows:
        if row.get("symbol") in {None, "", "PORTFOLIO"}:
            continue
        grouped[(row.get("strategy"), row.get("symbol"))].append(row)
    output = {}
    for key, values in grouped.items():
        totals = {
            "covered_asset_seconds": Decimal(0),
            "unhedged_asset_seconds": Decimal(0),
            "dust_asset_seconds": Decimal(0),
        }
        values.sort(key=lambda row: int(row.get("time_ns") or 0))
        known_dust = Decimal(0)
        for index, row in enumerate(values):
            start = max(start_ns, int(row.get("time_ns") or 0))
            following = values[index + 1] if index + 1 < len(values) else None
            stop = min(end_ns, int(following.get("time_ns") or end_ns) if following else end_ns)
            seconds = Decimal(max(0, stop - start)) / Decimal(1_000_000_000)
            spot, short = _decimal(row.get("spot")), _decimal(row.get("short"))
            inventory = spot > 0 or short > 0
            has_dust_metadata = row.get("dust_spot") not in (None, "") or row.get(
                "tradable_spot"
            ) not in (None, "")
            tradable = _decimal(row.get("tradable_spot"))
            dust = (
                spot > 0
                and short == 0
                and tradable == 0
                and (
                    (_decimal(row.get("dust_spot")) > 0 if has_dust_metadata else False)
                    or row.get("state") in {"FLAT", "COOLDOWN"}
                    or (not has_dust_metadata and spot <= known_dust)
                )
            )
            covered = (
                not dust
                and inventory
                and spot > 0
                and short > 0
                and abs(spot - short) / spot <= tolerance
            )
            if dust:
                known_dust = spot
                totals["dust_asset_seconds"] += seconds
            elif covered:
                totals["covered_asset_seconds"] += seconds
            elif inventory:
                totals["unhedged_asset_seconds"] += seconds
        output[key] = totals
    return output


def _cycle_counts(events: list[dict]) -> tuple[int, int]:
    cycles = defaultdict(list)
    for event in events:
        if event.get("cycle_id"):
            cycles[(event.get("symbol"), event["cycle_id"])].append(event)
    complete = failed = 0
    for cycle in cycles.values():
        opened = any(
            event.get("kind") == "transition" and event.get("cause") == "opening_complete"
            for event in cycle
        )
        terminal = any(
            event.get("kind") == "transition"
            and event.get("cause") in {"unwind_complete", "ordinary_close_complete"}
            and event.get("state") in {"FLAT", "COOLDOWN"}
            for event in cycle
        )
        complete += int(opened and terminal)
        failed += int((not opened) and terminal)
    return complete, failed


def _summaries(window: str, scenario: str, run: Path, config: dict):
    metrics = _rows(run, "metrics.csv")
    execution = _rows(run, "execution_summary.csv")
    components = _rows(run, "pnl_components.csv")
    daily = _rows(run, "equity_daily.csv")
    fills = _rows(run, "fills.parquet")
    risk_events = _rows(run, "risk_events.parquet")
    positions = _rows(run, "positions.parquet")
    durations = _position_durations(
        positions, timestamp(config["end"]), _decimal(config.get("hedge_tolerance", "0.005"))
    )
    pnl = defaultdict(lambda: Decimal(0))
    for row in components:
        pnl[(row.get("strategy"), row.get("component"))] += _decimal(row.get("amount_usdt"))
    result = []
    for strategy, _ in STRATEGIES:
        metric = next(
            (r for r in metrics if r.get("strategy") == strategy and r.get("period") == "full"),
            {},
        )
        ex = next(
            (
                r
                for r in execution
                if r.get("strategy") == strategy and r.get("symbol") == "PORTFOLIO"
            ),
            {},
        )
        used = []
        for row in daily:
            if row.get("strategy") == strategy:
                used.append(
                    sum(
                        (
                            _decimal(row.get(f"{symbol}_spot"))
                            * _decimal(row.get(f"{symbol}_spot_price"))
                            + _decimal(row.get(f"{symbol}_collateral"))
                            for symbol in ("BTCUSDT", "ETHUSDT")
                        ),
                        Decimal(0),
                    )
                )
        duration = {
            key: sum((d[key] for (s, _), d in durations.items() if s == strategy), Decimal(0))
            for key in ("covered_asset_seconds", "unhedged_asset_seconds", "dust_asset_seconds")
        }
        strategy_fills = [r for r in fills if r.get("strategy") == strategy]
        strategy_risk = [r for r in risk_events if r.get("strategy") == strategy]
        complete_cycles, failed_cycles = _cycle_counts(strategy_risk)
        final_daily = max(
            (r for r in daily if r.get("strategy") == strategy),
            key=lambda r: int(r["time_ns"]),
            default=None,
        )
        net_components = sum(
            (
                pnl[(strategy, name)]
                for name in ("spot_pnl", "futures_pnl", "funding", "fees", "liquidation_fees")
            ),
            Decimal(0),
        )
        reconciliation = (
            _decimal(final_daily["equity"]) - _decimal(config["capital"]) - net_components
            if final_daily
            else None
        )
        if reconciliation is not None and abs(reconciliation) > _decimal(
            config["accounting_tolerance"]
        ):
            raise ValueError(
                f"Persisted P&L does not reconcile: {run.name}/{strategy}: {reconciliation}"
            )
        result.append(
            {
                "window": window,
                "scenario": scenario,
                "strategy": strategy,
                "run_id": run.name,
                "status": metric.get("status"),
                "start": config["start"],
                "end": config["end"],
                "capital_usdt": config["capital"],
                "final_equity_usdt": final_daily["equity"] if final_daily else None,
                "reconciliation_residual_usdt": str(reconciliation)
                if reconciliation is not None
                else None,
                "native_fills": ex.get("native_fill_count"),
                "net_return": metric.get("net_return"),
                "cagr": metric.get("cagr"),
                "sharpe": metric.get("sharpe"),
                "max_drawdown": metric.get("max_drawdown"),
                "spot_pnl_usdt": str(pnl[(strategy, "spot_pnl")]),
                "futures_pnl_usdt": str(pnl[(strategy, "futures_pnl")]),
                "funding_usdt": str(pnl[(strategy, "funding")]),
                "fees_usdt": str(pnl[(strategy, "fees")]),
                "liquidation_fees_usdt": str(pnl[(strategy, "liquidation_fees")]),
                "slippage_informational_usdt": str(pnl[(strategy, "slippage_informational")]),
                "orders": ex.get("orders"),
                "fills": ex.get("fills"),
                "failed_attempts": ex.get("failed_attempts"),
                "complete_cycles": complete_cycles,
                "failed_cycles": failed_cycles,
                "opening_attempts": ex.get("openings"),
                "openings": sum(
                    r.get("cause") == "opening_complete" and r.get("kind") == "transition"
                    for r in strategy_risk
                ),
                "closes": ex.get("closes"),
                "partial_fills": sum(bool(r.get("partial")) for r in strategy_fills),
                "capital_deployed_daily_avg_usdt": str(sum(used, Decimal(0)) / len(used))
                if used
                else None,
                "capital_deployed_daily_max_usdt": str(max(used)) if used else None,
                **{key: str(value) for key, value in duration.items()},
            }
        )
    return result


def _diagnostics(window: str, scenario: str, run: Path) -> tuple[list[dict], list[dict]]:
    signals = _rows(run, "signals.parquet")
    states = sorted(
        {
            key
            for row in signals
            for key, value in row.items()
            if key.startswith("filter_") and value in {"pass", "fail", "not_evaluable"}
        }
    )
    counts = CounterLike()
    distributions = defaultdict(list)
    for row in signals:
        strategy, symbol = row.get("strategy"), row.get("symbol")
        if states:
            failed = [field for field in states if row.get(field) == "fail"]
            funding_enabled = _yes(row.get("funding_filter_enabled", strategy != "permanent"))
            applicable = [field for field in failed if field != "filter_funding" or funding_enabled]
            counts[(strategy, symbol, "simultaneous_reject")] += bool(applicable)
            for field in failed:
                suffix = (
                    ":diagnostic_fail_not_applied"
                    if field == "filter_funding" and not funding_enabled
                    else ":reject"
                )
                counts[(strategy, symbol, field + suffix)] += 1
            for field in states:
                if row.get(field) == "not_evaluable":
                    counts[(strategy, symbol, field + ":not_evaluable")] += 1
            ordered = row.get("sequential_rejection")
            if ordered:
                counts[(strategy, symbol, "ordered_reject:" + str(ordered))] += 1
        else:
            counts[(strategy, symbol, "stored_decision:" + str(row.get("decision")))] += 1
        forecast = _decimal(row.get("forecast"), Decimal("NaN"))
        cost = _decimal(row.get("estimated_cycle_cost"), Decimal("NaN"))
        basis = _decimal(row.get("basis"), Decimal("NaN"))
        if forecast.is_finite():
            distributions[(strategy, symbol, "forecast")].append(forecast)
        if cost.is_finite():
            distributions[(strategy, symbol, "estimated_cycle_cost")].append(cost)
        if forecast.is_finite() and cost.is_finite():
            distributions[(strategy, symbol, "forecast_minus_cost")].append(forecast - cost)
        if basis.is_finite():
            distributions[(strategy, symbol, "basis")].append(basis)
    summary = [
        {
            "window": window,
            "scenario": scenario,
            "strategy": s,
            "symbol": symbol,
            "diagnostic": k,
            "count": v,
            "scope": (
                "theoretical_not_applied"
                if k.endswith(":diagnostic_fail_not_applied")
                else "sequential_first_rejection"
                if k.startswith("ordered_reject:")
                else "simultaneous_filter_states"
                if states
                else "legacy_single_decision"
            ),
        }
        for (s, symbol, k), v in sorted(counts.items(), key=lambda item: str(item[0]))
    ]
    renewal_counts = CounterLike()
    for row in _rows(run, "renewal_diagnostics.parquet"):
        outcome = (
            row.get("actual_outcome")
            or row.get("state_after")
            or row.get("renewal_status_kind")
            or "unknown"
        )
        renewal_counts[(row.get("strategy"), str(outcome))] += 1
    summary.extend(
        {
            "window": window,
            "scenario": scenario,
            "strategy": strategy,
            "symbol": "PORTFOLIO",
            "diagnostic": "renewal_outcome:" + outcome,
            "count": count,
            "scope": "renewal_diagnostics",
        }
        for (strategy, outcome), count in sorted(
            renewal_counts.items(), key=lambda item: str(item[0])
        )
    )
    quantiles = []
    for (strategy, symbol, measure), values in sorted(
        distributions.items(), key=lambda item: str(item[0])
    ):
        values.sort()

        def pick(q):
            return values[min(len(values) - 1, int((len(values) - 1) * q))]

        quantiles.append(
            {
                "window": window,
                "scenario": scenario,
                "strategy": strategy,
                "symbol": symbol,
                "measure": measure,
                "observations": len(values),
                "p10": str(pick(0.1)),
                "p50": str(pick(0.5)),
                "p90": str(pick(0.9)),
            }
        )
    return summary, quantiles


def _hypotheses(window: str, scenario: str, run: Path) -> list[dict]:
    output = []
    full_metrics = {
        row.get("strategy"): row for row in _rows(run, "metrics.csv") if row.get("period") == "full"
    }
    conditional, permanent = full_metrics.get("conditional", {}), full_metrics.get("permanent", {})
    coverage = all(
        _yes(row.get("coverage_complete")) and row.get("status") == "complete"
        for row in (conditional, permanent)
    )
    for row in _rows(run, "h1_summary.csv"):
        if row.get("symbol") == "EQUAL_WEIGHT" and row.get("period") == "full":
            ewma = _decimal(row.get("mae_ewma"), Decimal("NaN"))
            no_change = _decimal(row.get("mae_no_change"), Decimal("NaN"))
            comparable = coverage and ewma.is_finite() and no_change.is_finite()
            verdict = "no_concluyente"
            if comparable and _decimal(row.get("observations")) > 0 and ewma != no_change:
                verdict = "favorable" if ewma < no_change else "contraria"
            output.append(
                {
                    "window": window,
                    "scenario": scenario,
                    "hypothesis": "H1",
                    "strategy": "COMMON",
                    "period": row.get("period"),
                    "measure": "forecast_mae",
                    "value": row.get("mae_ewma"),
                    "comparator": row.get("mae_no_change"),
                    "observations": row.get("observations"),
                    "excluded": row.get("excluded"),
                    "criterion": "mae_ewma < mae_no_change",
                    "result": verdict,
                }
            )
    cagr = _decimal(conditional.get("cagr"), Decimal("NaN"))
    conditional_sharpe = _decimal(conditional.get("sharpe"), Decimal("NaN"))
    permanent_sharpe = _decimal(permanent.get("sharpe"), Decimal("NaN"))
    daily = _rows(run, "equity_daily.csv")
    dates = {
        strategy: [r.get("time_ns") for r in daily if r.get("strategy") == strategy]
        for strategy, _ in STRATEGIES
    }
    comparable = (
        coverage
        and _yes(conditional.get("funding_filter_enabled"))
        and not _yes(permanent.get("funding_filter_enabled"))
        and dates["conditional"] == dates["permanent"]
        and bool(dates["conditional"])
        and cagr.is_finite()
        and conditional_sharpe.is_finite()
        and permanent_sharpe.is_finite()
    )
    verdict = "no_concluyente"
    if comparable:
        verdict = "favorable" if cagr > 0 and conditional_sharpe > permanent_sharpe else "contraria"
    output.append(
        {
            "window": window,
            "scenario": scenario,
            "hypothesis": "H2",
            "strategy": "conditional_vs_permanent",
            "period": "full",
            "measure": "conditional_cagr_and_relative_sharpe",
            "value": conditional.get("cagr"),
            "comparator": permanent.get("cagr"),
            "conditional_sharpe": conditional.get("sharpe"),
            "permanent_sharpe": permanent.get("sharpe"),
            "observations": conditional.get("observations"),
            "criterion": "conditional CAGR > 0 and both Sharpes defined and conditional > permanent",
            "result": verdict,
        }
    )
    return output


def _cross_window_h3(scenario: str, runs: dict[tuple[str, str], Path]) -> dict:
    values = {}
    for window in ("early", "late"):
        rows = [
            row
            for row in _rows(runs[(window, scenario)], "regime_comparison.csv")
            if row.get("symbol") == "EQUAL_WEIGHT"
        ]
        preferred = "2024+" if window == "late" else "2022-2023"
        values[window] = next((row for row in rows if row.get("period") == preferred), {})
    early, late = values["early"], values["late"]
    early_days, late_days = int(early.get("valid_days") or 0), int(late.get("valid_days") or 0)
    early_value = _decimal(early.get("opportunity_mean"), Decimal("NaN"))
    late_value = _decimal(late.get("opportunity_mean"), Decimal("NaN"))
    early_cagr = _decimal(early.get("conditional_cagr"), Decimal("NaN"))
    late_cagr = _decimal(late.get("conditional_cagr"), Decimal("NaN"))
    comparable = (
        early_days == 365
        and late_days == 365
        and _yes(early.get("coverage_complete"))
        and _yes(late.get("coverage_complete"))
        and early_value.is_finite()
        and late_value.is_finite()
        and early_cagr.is_finite()
        and late_cagr.is_finite()
    )
    verdict = "no_concluyente"
    if comparable:
        if late_value < early_value and late_cagr < early_cagr:
            verdict = "favorable"
        elif late_value > early_value and late_cagr > early_cagr:
            verdict = "contraria"
        else:
            verdict = "mixta"
    return {
        "window": "early_vs_late",
        "scenario": scenario,
        "hypothesis": "H3",
        "strategy": "COMMON",
        "period": "independent_365_day_windows",
        "measure": "opportunity_mean",
        "value": str(late_value) if late_value.is_finite() else None,
        "comparator": str(early_value) if early_value.is_finite() else None,
        "early_conditional_cagr": str(early_cagr) if early_cagr.is_finite() else None,
        "late_conditional_cagr": str(late_cagr) if late_cagr.is_finite() else None,
        "observations": f"{early_days}/{late_days}",
        "excluded": f"{365 - early_days}/{365 - late_days}",
        "early_valid_days": early_days,
        "criterion": "complete independent 365-day windows; both late opportunity and conditional CAGR < early",
        "result": verdict,
    }


class CounterLike(defaultdict):
    def __init__(self):
        super().__init__(int)


def _write_csv(path: Path, rows: list[dict]) -> None:
    fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields or ["empty"])
        writer.writeheader()
        writer.writerows(rows)


def _number_text(value, decimals=2, percent=False) -> str:
    number = _decimal(value, Decimal("NaN"))
    if not number.is_finite():
        return "ND"
    if percent:
        number *= 100
    suffix = "%" if percent else ""
    return f"{number:.{decimals}f}{suffix}"


def _markdown_table(headers: list[str], rows: list[list[object]]) -> list[str]:
    return [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join("---" for _ in headers) + "|",
        *("| " + " | ".join(str(value) for value in row) + " |" for row in rows),
    ]


def _outage_close_prices(fills: list[dict]) -> list[dict]:
    """Keep weighted close prices within a single base asset and strategy."""
    groups = defaultdict(list)
    for row in fills:
        if str(row.get("purpose", "")).startswith("close") or row.get("purpose") == "liquidate":
            groups[(row["scenario"], row["strategy"], row["symbol"])].append(row)
    result = []
    for (scenario, strategy, symbol), rows in sorted(groups.items()):
        item = {"scenario": scenario, "strategy": strategy, "symbol": symbol}
        for prefix, market, side in (("future", "futures", "BUY"), ("spot", "spot", "SELL")):
            selected = [r for r in rows if r["market"] == market and r["side"] == side]
            quantity = sum((_decimal(r["quantity"]) for r in selected), Decimal(0))
            item[f"{prefix}_close_utc"] = max((r["timestamp_utc"] for r in selected), default=None)
            item[f"{prefix}_close_price_usdt"] = (
                str(
                    sum(
                        (_decimal(r["quantity"]) * _decimal(r["price"]) for r in selected),
                        Decimal(0),
                    )
                    / quantity
                )
                if quantity
                else None
            )
        result.append(item)
    return result


def _outage_rows(window: str, scenario: str, run: Path) -> tuple[list, list, list, list, list]:
    if window != "early":
        return [], [], [], [], []

    def on_day(row):
        return str(row.get("timestamp_utc", "")).startswith("2023-03-24")

    orders = [
        {"window": window, "scenario": scenario, **row}
        for row in _rows(run, "orders.parquet")
        if on_day(row)
    ]
    fills = [
        {"window": window, "scenario": scenario, **row}
        for row in _rows(run, "fills.parquet")
        if on_day(row)
    ]
    ledger = [row for row in _rows(run, "ledger.parquet") if on_day(row)]
    funding = [row for row in _rows(run, "funding_payments.parquet") if on_day(row)]
    all_daily = _rows(run, "equity_daily.csv")
    daily = [row for row in all_daily if on_day(row)]
    if not daily:
        return [], [], [], [], []
    day_start = timestamp("2023-03-24T00:00:00Z")
    day_end = timestamp("2023-03-25T00:00:00Z")
    day_durations = _position_durations(
        _rows(run, "positions.parquet"), day_end, Decimal("0.005"), day_start
    )
    summaries = []
    for strategy, _ in STRATEGIES:
        strategy_orders = [r for r in orders if r.get("strategy") == strategy]
        strategy_fills = [r for r in fills if r.get("strategy") == strategy]
        current = next((r for r in daily if r.get("strategy") == strategy), None)
        prior = max(
            (
                r
                for r in all_daily
                if r.get("strategy") == strategy and int(r.get("time_ns") or 0) < day_start
            ),
            key=lambda row: int(row.get("time_ns") or 0),
            default=None,
        )
        day_pnl = (
            _decimal(current.get("equity")) - _decimal(prior.get("equity"))
            if current and prior
            else None
        )
        unhedged = sum(
            (
                values["unhedged_asset_seconds"]
                for (row_strategy, _), values in day_durations.items()
                if row_strategy == strategy
            ),
            Decimal(0),
        )
        summaries.append(
            {
                "window": window,
                "scenario": scenario,
                "strategy": strategy,
                "orders": len({r["order_id"] for r in strategy_orders}),
                "fills": len(strategy_fills),
                "close_orders": len(
                    {
                        r["order_id"]
                        for r in strategy_orders
                        if str(r.get("purpose", "")).startswith("close")
                        or r.get("purpose") == "liquidate"
                    }
                ),
                "first_fill_utc": min(
                    (r.get("timestamp_utc") for r in strategy_fills), default=None
                ),
                "last_fill_utc": max(
                    (r.get("timestamp_utc") for r in strategy_fills), default=None
                ),
                "fees_usdt": str(
                    sum(
                        (_decimal(r.get("fee")) for r in ledger if r.get("strategy") == strategy),
                        Decimal(0),
                    )
                ),
                "funding_usdt": str(
                    sum(
                        (
                            _decimal(r.get("amount_usdt"))
                            for r in funding
                            if r.get("strategy") == strategy
                        ),
                        Decimal(0),
                    )
                ),
                "day_end_equity_usdt": current.get("equity") if current else None,
                "day_pnl_usdt": str(day_pnl) if day_pnl is not None else None,
                "unhedged_asset_seconds": str(unhedged),
                "pnl_method": "persisted day-end equity and persisted ledger components; no manual substitution",
            }
        )
    tagged_funding = [{"window": window, "scenario": scenario, **row} for row in funding]
    tagged_ledger = [{"window": window, "scenario": scenario, **row} for row in ledger]
    return orders, fills, tagged_funding, tagged_ledger, summaries


def _revision_report_lines(
    summaries, hypotheses, diagnostics, quantiles, outage_summary, outage_fills
):
    comparison = [
        [
            r["window"],
            r["scenario"],
            r["strategy"],
            r["status"],
            f"[{r['start'][:10]}, {r['end'][:10]})",
            f"{_number_text(r['capital_usdt'], 0)} USDT",
            _number_text(r["net_return"], 4, True),
            _number_text(r["cagr"], 4, True),
            _number_text(r["sharpe"]),
            _number_text(r["max_drawdown"], 4, True),
        ]
        for r in summaries
    ]
    economics = [
        [
            r["window"],
            r["scenario"],
            r["strategy"],
            _number_text(r["spot_pnl_usdt"]),
            _number_text(r["futures_pnl_usdt"]),
            _number_text(r["funding_usdt"]),
            _number_text(r["fees_usdt"]),
            _number_text(r["liquidation_fees_usdt"]),
            _number_text(r["slippage_informational_usdt"]),
            r["complete_cycles"],
            r["failed_cycles"],
            r["failed_attempts"],
            r["partial_fills"],
        ]
        for r in summaries
    ]
    exposures = [
        [
            r["window"],
            r["scenario"],
            r["strategy"],
            _number_text(r["capital_deployed_daily_avg_usdt"]),
            _number_text(r["capital_deployed_daily_max_usdt"]),
            _number_text(_decimal(r["covered_asset_seconds"]) / 3600),
            _number_text(_decimal(r["unhedged_asset_seconds"]) / 3600),
            _number_text(_decimal(r["dust_asset_seconds"]) / 3600),
        ]
        for r in summaries
    ]
    hypothesis_rows = [
        [
            r["hypothesis"],
            r["window"],
            r["scenario"],
            r["result"],
            r["measure"],
            _number_text(r.get("value"), 6),
            _number_text(r.get("comparator"), 6),
            r.get("observations", ""),
            r.get("excluded", ""),
        ]
        for r in hypotheses
    ]
    principal = sorted(
        (
            r
            for r in diagnostics
            if r["scenario"] == "vwap_joint"
            and ("reject" in r["diagnostic"] or "not_evaluable" in r["diagnostic"])
        ),
        key=lambda r: (r["window"], r["strategy"], r["symbol"], -int(r["count"])),
    )
    diagnostic_rows = [
        [r["window"], r["strategy"], r["symbol"], r["diagnostic"], r["count"]] for r in principal
    ]
    inactive_diagnostic_rows = [
        [r["window"], r["strategy"], r["symbol"], r["diagnostic"], r["count"]]
        for r in diagnostics
        if r["scenario"] == "vwap_joint"
        and r["diagnostic"].endswith(":diagnostic_fail_not_applied")
    ]
    quantile_rows = [
        [
            r["window"],
            r["symbol"],
            r["measure"],
            r["observations"],
            _number_text(r["p10"], 6),
            _number_text(r["p50"], 6),
            _number_text(r["p90"], 6),
        ]
        for r in quantiles
        if r["scenario"] == "vwap_joint" and r["strategy"] == "conditional"
    ]
    outage = [
        [
            r["scenario"],
            r["strategy"],
            r["orders"],
            r["fills"],
            r["close_orders"],
            _number_text(r["day_pnl_usdt"]),
            _number_text(r["funding_usdt"]),
            _number_text(r["fees_usdt"]),
            _number_text(_decimal(r["unhedged_asset_seconds"]) / 60),
        ]
        for r in outage_summary
    ]
    outage_prices = [
        [
            r["scenario"],
            r["strategy"],
            r["symbol"],
            r["future_close_utc"] or "ND",
            _number_text(r["future_close_price_usdt"], 4),
            r["spot_close_utc"] or "ND",
            _number_text(r["spot_close_price_usdt"], 4),
        ]
        for r in _outage_close_prices(outage_fills)
    ]
    max_residual = max(
        (abs(_decimal(r["reconciliation_residual_usdt"])) for r in summaries), default=Decimal(0)
    )
    h3_comparison = [
        [
            r["scenario"],
            _number_text(r["comparator"], 8),
            _number_text(r["value"], 8),
            _number_text(r["early_conditional_cagr"], 4, True),
            _number_text(r["late_conditional_cagr"], 4, True),
            r["result"],
        ]
        for r in hypotheses
        if r["hypothesis"] == "H3"
    ]
    operation_notes = []
    for row in summaries:
        if row["scenario"] != "vwap_joint":
            continue
        reasons = sorted(
            (
                r
                for r in diagnostics
                if r["window"] == row["window"]
                and r["strategy"] == row["strategy"]
                and r["scenario"] == "vwap_joint"
                and r["diagnostic"].startswith("ordered_reject:")
            ),
            key=lambda r: -int(r["count"]),
        )[:3]
        detail = "; ".join(
            f"{r['symbol']} {r['diagnostic'].removeprefix('ordered_reject:')} = {r['count']}"
            for r in reasons
        )
        operation_notes.append(
            f"- {row['window']} / {row['strategy']}: {row['fills']} fills, {row['openings']} aperturas completas. "
            f"Principales rechazos secuenciales: {detail or 'ninguno'}."
        )
    return [
        "# Revision de ejecucion",
        "",
        "El analisis principal preespecificado es `vwap_joint`: observaciones cerradas, VWAP del siguiente minuto elegible, limite de volumen y sizing conjunto. Los otros cuatro escenarios son controles de atribucion.",
        "Cada ventana es independiente y reinicia 10,000 USDT. `alignment_only` separa el cambio de observacion. Drawdown es diario; Sharpe es una razon; `ND` indica valor no definido.",
        "",
        "## Resultados comparativos",
        "",
        *_markdown_table(
            [
                "Ventana",
                "Escenario",
                "Estrategia",
                "Estado",
                "Fechas UTC",
                "Capital",
                "Retorno",
                "CAGR",
                "Sharpe",
                "DD diario",
            ],
            comparison,
        ),
        "",
        *operation_notes,
        "",
        "La permanente omite únicamente el filtro de funding. El sizing conjunto no cambia los umbrales de funding o basis. Cero operaciones no demuestra rentabilidad; su Sharpe permanece indefinido.",
        "",
        "## PnL y ejecucion",
        "",
        "Componentes en USDT. Fees y liquidaciones tienen signo de costo. El slippage es informativo y ya está incorporado en los precios: no se resta otra vez. Un ciclo completo requiere apertura completa y cierre terminal del mismo cycle_id; intentos fallidos se informan por separado.",
        "",
        *_markdown_table(
            [
                "Ventana",
                "Escenario",
                "Estrategia",
                "Spot",
                "Futuros",
                "Funding",
                "Fees",
                "Liquidación",
                "Slippage informativo",
                "Ciclos",
                "Fallidos",
                "Intentos",
                "Parciales",
            ],
            economics,
        ),
        "",
        f"Máximo residuo de conciliación entre equity final menos capital inicial y componentes: {max_residual} USDT (tolerancia 1e-8). Los conteos de fills nativos y económicos quedan en scenario_summary.csv y execution_summary.csv de cada corrida.",
        "",
        "## Capital y cobertura",
        "",
        "Capital desplegado = valor spot persistido mas collateral. Duraciones en horas-activo por simbolo; polvo se excluye de exposicion activa sin cobertura.",
        "",
        *_markdown_table(
            [
                "Ventana",
                "Escenario",
                "Estrategia",
                "Capital prom.",
                "Capital max.",
                "Cubierto h",
                "Sin cobertura h",
                "Polvo h",
            ],
            exposures,
        ),
        "",
        "## H1, H2 y H3",
        "",
        "H1 compara MAE EWMA con no-change. H2 exige cobertura comparable, CAGR condicional positivo y ambos Sharpes definidos, con el condicional mayor. H3 exige que disminuyan tanto opportunity_mean como CAGR condicional entre ventanas independientes, con 365 días válidos en ambas. Una métrica ausente produce no_concluyente; resultados mixtos no se convierten en favorables. Son contrastes descriptivos, sin atribución causal.",
        "",
        *_markdown_table(
            [
                "H",
                "Ventana",
                "Escenario",
                "Resultado",
                "Medida",
                "Valor",
                "Comparador",
                "Obs.",
                "Excl.",
            ],
            hypothesis_rows,
        ),
        "",
        *_markdown_table(
            [
                "Escenario",
                "Oportunidad temprana",
                "Oportunidad tardía",
                "CAGR cond. temprano",
                "CAGR cond. tardío",
                "H3",
            ],
            h3_comparison,
        ),
        "",
        "## Por que no hubo operaciones",
        "",
        "Escenario principal por estrategia y símbolo. Las condiciones incumplidas de filtros aplicables se solapan; sólo el primer rechazo secuencial identifica el bloqueo operativo de cada evaluación. `simultaneous_reject` excluye funding cuando la estrategia no lo aplica. Legacy conserva sólo su decisión persistida. Las distribuciones muestran proporciones decimales (0.0034 = 0.34%); la condicional y la permanente comparten forecast y costo ex ante.",
        "Orden secuencial: `" + " → ".join(FILTER_ORDER) + "`. La permanente salta `funding`.",
        "",
        *_markdown_table(
            ["Ventana", "Estrategia", "Simbolo", "Filtro/decision", "Conteo"], diagnostic_rows
        ),
        "",
        "Diagnósticos teóricos de filtros omitidos: no bloquean órdenes ni integran `simultaneous_reject`. Un forecast que no cubre costos no es un rechazo operativo de la permanente.",
        "",
        *_markdown_table(
            ["Ventana", "Estrategia", "Simbolo", "Diagnóstico no aplicado", "Conteo"],
            inactive_diagnostic_rows,
        ),
        "",
        *_markdown_table(
            ["Ventana", "Simbolo", "Distribucion", "N", "P10", "P50", "P90"], quantile_rows
        ),
        "",
        "## Interrupcion del 24-03-2023",
        "",
        "PnL diario por diferencia de equities persistidos; funding y fees provienen del ledger, sin sustitucion manual. Duracion en minuto-activo.",
        "",
        *_markdown_table(
            [
                "Escenario",
                "Estrategia",
                "Ordenes",
                "Fills",
                "Cierres",
                "PnL USDT",
                "Funding",
                "Fees",
                "Sin cobertura min",
            ],
            outage,
        ),
        "",
        *_markdown_table(
            [
                "Escenario",
                "Estrategia",
                "Activo",
                "Último cierre futuro UTC",
                "Precio futuro USDT",
                "Último cierre spot UTC",
                "Precio spot USDT",
            ],
            outage_prices,
        ),
        "",
        "Los precios son promedios ponderados de los fills de cierre persistidos del mismo activo, con slippage; los rebalanceos no forman parte de esos promedios. El 58.0045% informado en la referencia corresponde al cambio de equity del día dividido por el beneficio anual; no es una atribución aislada a un fill. El episodio permanece dentro de todas las corridas, sin restar manualmente su P&L.",
        "",
        "Detalles: [escenarios](scenario_summary.csv), [hipotesis](hypotheses_by_window.csv), [diagnosticos](diagnostics_summary.csv), [cuantiles](diagnostic_quantiles.csv), [ordenes](outage_2023-03-24_orders.csv), [fills](outage_2023-03-24_fills.csv), [funding](outage_2023-03-24_funding.csv) y [ledger](outage_2023-03-24_ledger.csv).",
        "",
        "## Alcance y reproducción",
        "",
        "El contrato nuevo incluye precio VWAP, capacidad del 1%, parciales, vencimientos y prioridad temporal. `alignment_only` mide la observación alineada por separado; la diferencia contra legacy no es un efecto puro del VWAP. Se mantienen las reglas y costos prescritos, y los proxies causales de mark de funding temprano: es una simulación de investigación, no una reconstrucción exacta de fills y tarifas históricas. No se consumen trades ni datos subminuto.",
        "",
        "Desde la raíz del proyecto, con el entorno y los datos preparados:",
        "",
        "```powershell",
        "& '.\\.venv\\Scripts\\python.exe' -u -m crypto_carry --root 'D:\\Backtesting' execution-revision `",
        "  --early-config (Resolve-Path '.\\configs\\download_minutes_2022_2023_d.toml').Path `",
        "  --late-config (Resolve-Path '.\\configs\\download_minutes_2025_2026_d.toml').Path",
        "```",
        "",
        "El manifiesto de revisión identifica y verifica cada corrida, sus configuraciones, código, datos y artefactos. Las referencias originales se reutilizan si sus hashes coinciden; en una instalación sin esos artefactos puede ejecutarse el modelo anterior con `--no-reuse-references`.",
    ]


def _build_revision(root: Path, runs: dict[tuple[str, str], Path]) -> Path:
    manifests = {}
    for key, run in runs.items():
        manifests[key] = _read_manifest(run)
    report_code_hash, report_code_files = _code_identity()
    input_identity = [
        {
            "window": w,
            "scenario": s,
            "run_id": run.name,
            "manifest_sha256": _hash(run / "run_manifest.json"),
        }
        for (w, s), run in sorted(runs.items())
    ]
    identity = {"report_code_hash": report_code_hash, "input_runs": input_identity}
    revision_id = "revision_" + hashlib.sha256(_json(identity).encode()).hexdigest()[:24]
    target = root / "outputs" / revision_id
    if target.exists():
        verified = verify_execution_revision(target)
        if not verified["valid"]:
            raise ValueError(f"Immutable revision is corrupt: {verified['mismatches']}")
        return target
    (root / "outputs").mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=revision_id + "-", dir=root / "outputs"))
    try:
        summaries, diagnostics, quantiles, hypotheses = [], [], [], []
        outage_orders, outage_fills, outage_funding, outage_ledger, outage_summary = (
            [],
            [],
            [],
            [],
            [],
        )
        for (window, scenario), run in sorted(runs.items()):
            manifest = manifests[(window, scenario)]
            summaries += _summaries(window, scenario, run, manifest["config"])
            diagnostic, distribution = _diagnostics(window, scenario, run)
            diagnostics += diagnostic
            quantiles += distribution
            hypotheses += _hypotheses(window, scenario, run)
            orders, fills, funding, ledger, outage = _outage_rows(window, scenario, run)
            outage_orders += orders
            outage_fills += fills
            outage_funding += funding
            outage_ledger += ledger
            outage_summary += outage
        hypotheses += [_cross_window_h3(scenario, runs) for scenario in SCENARIOS]
        for name, rows in (
            ("scenario_summary.csv", summaries),
            ("diagnostics_summary.csv", diagnostics),
            ("diagnostic_quantiles.csv", quantiles),
            ("hypotheses_by_window.csv", hypotheses),
            ("outage_2023-03-24_orders.csv", outage_orders),
            ("outage_2023-03-24_fills.csv", outage_fills),
            ("outage_2023-03-24_funding.csv", outage_funding),
            ("outage_2023-03-24_ledger.csv", outage_ledger),
            ("outage_2023-03-24_summary.csv", outage_summary),
            ("outage_2023-03-24_close_prices.csv", _outage_close_prices(outage_fills)),
        ):
            _write_csv(staging / name, rows)
        lines = _revision_report_lines(
            summaries, hypotheses, diagnostics, quantiles, outage_summary, outage_fills
        )
        lines += [
            "",
            "## Corridas y versión del informe",
            "",
            f"Este informe usa el código `{report_code_hash}`. Cada corrida conserva su versión original: regenerar tablas y presentación no vuelve a simular ni cambia sus saldos.",
            "",
            *_markdown_table(
                ["Ventana", "Escenario", "Corrida", "Código de simulación"],
                [
                    [w, s, f"[{run.name}](../{run.name}/report.md)", manifests[(w, s)]["code_hash"]]
                    for (w, s), run in sorted(runs.items())
                ],
            ),
            "",
            "Para verificar y regenerar esta comparación desde sus corridas guardadas:",
            "",
            "```powershell",
            f"& '.\\.venv\\Scripts\\python.exe' -m crypto_carry --root 'D:\\Backtesting' report --run-id {revision_id}",
            "```",
        ]
        (staging / "execution_revision_report.md").write_text(
            "\n".join(lines) + "\n", encoding="utf-8"
        )
        manifest = {
            "revision_id": revision_id,
            "created_at": datetime.now(UTC).isoformat(),
            "artifacts_complete": True,
            "status": (
                "complete"
                if all(
                    item.get("status") in {"complete", "insolvent"} for item in manifests.values()
                )
                else "incomplete_data"
            ),
            "identity": identity,
            "report_code_hash": report_code_hash,
            "report_code_files": report_code_files,
            "input_runs": [
                {
                    "window": w,
                    "scenario": s,
                    "path": str(run.resolve()),
                    "manifest_sha256": _hash(run / "run_manifest.json"),
                    "input_hashes": manifests[(w, s)].get("input_hashes", {}),
                }
                for (w, s), run in sorted(runs.items())
            ],
        }
        manifest["output_hashes"] = {
            p.name: _hash(p) for p in sorted(staging.iterdir()) if p.is_file()
        }
        path = staging / "revision_manifest.json"
        path.write_text(
            json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        (staging / "revision_manifest.sha256").write_text(_hash(path) + "\n", encoding="ascii")
        staging.rename(target)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    verified = verify_execution_revision(target)
    if not verified["valid"]:
        raise ValueError(f"New revision verification failed: {verified['mismatches']}")
    return target


def verify_execution_revision(path: str | Path) -> dict[str, object]:
    revision = Path(path).resolve()
    mismatches = []
    try:
        manifest_path = revision / "revision_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        expected = (revision / "revision_manifest.sha256").read_text(encoding="ascii").strip()
        if _hash(manifest_path) != expected:
            mismatches.append(
                {"path": "revision_manifest.json", "reason": "manifest checksum mismatch"}
            )
    except Exception as exc:
        return {
            "valid": False,
            "status": "failed",
            "revision_id": revision.name,
            "mismatches": [{"path": "revision_manifest.json", "reason": str(exc)}],
        }
    if manifest.get("revision_id") != revision.name or not manifest.get("artifacts_complete"):
        mismatches.append(
            {"path": "revision_manifest.json", "reason": "identity or completion mismatch"}
        )
    for name, expected in manifest.get("output_hashes", {}).items():
        candidate = revision / name
        if not candidate.is_file() or _hash(candidate) != expected:
            mismatches.append({"path": name, "reason": "missing or checksum mismatch"})
    for item in manifest.get("input_runs", []):
        run_path = Path(item["path"])
        source = run_path / "run_manifest.json"
        run_verification = verify_run(run_path)
        if (
            not run_verification["valid"]
            or not source.is_file()
            or _hash(source) != item.get("manifest_sha256")
        ):
            mismatches.append({"path": item["path"], "reason": "input run manifest changed"})
    expected_files = set(manifest.get("output_hashes", {})) | {
        "revision_manifest.json",
        "revision_manifest.sha256",
    }
    actual_files = {p.relative_to(revision).as_posix() for p in revision.rglob("*") if p.is_file()}
    for name in sorted(actual_files - expected_files):
        mismatches.append({"path": name, "reason": "untracked artifact"})
    return {
        "valid": not mismatches,
        "status": manifest.get("status", "failed") if not mismatches else "failed",
        "revision_id": manifest.get("revision_id"),
        "mismatches": mismatches,
    }


def rebuild_execution_revision(root: str | Path, revision: str | Path) -> Path:
    """Regenerate presentation from verified economic runs, preserving their identities."""
    source = Path(revision).resolve()
    checked = verify_execution_revision(source)
    if not checked["valid"]:
        raise ValueError(f"Source revision is not verified: {checked.get('mismatches')}")
    manifest = json.loads((source / "revision_manifest.json").read_text(encoding="utf-8"))
    entries = manifest["input_runs"]
    runs = {(r["window"], r["scenario"]): Path(r["path"]) for r in entries}
    expected = {(w, s) for w in ("early", "late") for s in SCENARIOS}
    if set(runs) != expected or len(entries) != len(expected):
        raise ValueError("Revision must identify each scenario/window exactly once")
    return _build_revision(Path(root).resolve(), runs)


def run_execution_revision(
    root: str | Path,
    early_config: Config | str | Path,
    late_config: Config | str | Path,
    *,
    reuse_references: bool = True,
    sample: bool = False,
) -> Path:
    """Execute both independent windows and build an immutable persisted-table report."""
    root = Path(root).resolve()
    configs = {"early": _load_config(early_config), "late": _load_config(late_config)}
    if configs["early"].start == configs["late"].start:
        raise ValueError("Early and late windows must be independent")
    start_code = _code_identity()[0]
    runs = {}
    frozen_inputs = {}
    for window, original in configs.items():
        base = (
            original.changed(start=original.sample_start, end=original.sample_end)
            if sample
            else original
        )
        scenarios = execution_revision_scenarios(base)
        qualities = {}
        for scenario, config in scenarios.items():
            print(f"[{window}/{scenario}] start", flush=True)
            if scenario == "legacy_reference" and reuse_references and not sample:
                legacy_inputs = input_hashes(root, config)
                runs[(window, scenario)] = _matching_reference(root, window, config, legacy_inputs)
                for strategy, _ in STRATEGIES:
                    print(
                        f"[{window}/{scenario}/{strategy}] reused {runs[(window, scenario)].name}",
                        flush=True,
                    )
            else:
                validation_key = (config.execution_model, config.signal_price_model)
                if validation_key not in qualities:
                    qualities[validation_key] = validate_data(
                        config, root, scope="sample" if sample else "full"
                    )
                quality = qualities[validation_key]
                if quality.get("status") != "complete":
                    raise ValueError(
                        f"Data validation is not complete for {window}/{scenario}: "
                        f"{quality.get('issues', [])}"
                    )
                inputs = _revision_input_hashes(root, config)
                frozen_inputs[(window, scenario)] = (config, inputs)
                runs[(window, scenario)] = _run_scenario(
                    root, window, scenario, config, quality, inputs
                )
    if _code_identity()[0] != start_code:
        raise RuntimeError("Source code changed during the execution revision matrix")
    for key, (config, expected) in frozen_inputs.items():
        if _revision_input_hashes(root, config) != expected:
            raise RuntimeError(f"Replay inputs changed during execution revision: {key}")
    return _build_revision(root, runs)
