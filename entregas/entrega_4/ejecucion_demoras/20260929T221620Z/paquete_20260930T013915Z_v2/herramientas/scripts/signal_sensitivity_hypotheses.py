"""Scenario-specific H1/H3 evidence using the original causal evaluation helpers."""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal as D
from pathlib import Path

from crypto_carry.config import Config, timestamp
from crypto_carry.models import Funding

if __package__:
    from . import verify_rules_sensitivity_package as core
    from .continuous_delivery.hypotheses import (
        checked_forecasts,
        h1_observations,
        market_opportunity,
    )
    from .report_historical_rules_sensitivity import write_csv
    from .return_capital.common import parquet, read_csv, read_json, write_json
else:
    import verify_rules_sensitivity_package as core
    from continuous_delivery.hypotheses import (
        checked_forecasts,
        h1_observations,
        market_opportunity,
    )
    from report_historical_rules_sensitivity import write_csv
    from return_capital.common import parquet, read_csv, read_json, write_json


def summarize_h1(rows, config):
    result = core.h1_summaries(rows, core.periods(config.to_dict()))
    for row in result:
        row.update(horizon_hours=config.horizon_hours, unit=f"pb/{config.horizon_hours} h")
        for name in ("mae_ewma", "mae_no_change"):
            row[name+"_bps"] = row[name]*10000 if row[name] is not None else None
        row["skill_vs_no_change"] = (
            1-row["mae_ewma"]/row["mae_no_change"]
            if row["mae_ewma"] is not None and row["mae_no_change"] is not None
            and row["mae_no_change"] > 0 else None)
    return result


def summarize_h3(daily, config, financials):
    metrics = {r["period"]: r for r in financials if r.get("strategy") == "conditional"}
    output = []
    for period, lower, upper in core.periods(config.to_dict()):
        rows = [r for r in daily if lower <= int(r["time_ns"]) < upper]
        valid = [r for r in rows if core.yes(r["complete"])]
        expected = (upper-lower)//core.DAY
        metric = metrics.get(period, {})
        covered = len(rows) == len(valid) == expected and core.yes(
            metric.get("coverage_complete", False))
        output.append(dict(
            period=period, horizon_hours=config.horizon_hours, unit=f"pb/{config.horizon_hours} h",
            observed_days=len(rows), valid_days=len(valid), excluded_days=len(rows)-len(valid),
            expected_days=expected, coverage_complete=covered,
            opportunity_mean=sum((D(str(r["opportunity"])) for r in valid), D(0))/len(valid)
            if valid else None,
            eligible_fraction=sum((D(str(r["eligible_fraction"])) for r in valid), D(0))/len(valid)
            if valid else None, conditional_cagr=metric.get("cagr"),
        ))
    by_period = {r["period"]: r for r in output}
    a, b = by_period.get("2022-2023"), by_period.get("2024+")
    if (not a or not b or any(not r["coverage_complete"] or r["opportunity_mean"] is None
                              or r["conditional_cagr"] in (None, "") for r in (a, b))):
        verdict = "no_concluyente"
    elif (b["opportunity_mean"] < a["opportunity_mean"]
          and D(str(b["conditional_cagr"])) < D(str(a["conditional_cagr"]))):
        verdict = "favorable"
    elif (b["opportunity_mean"] > a["opportunity_mean"]
          and D(str(b["conditional_cagr"])) > D(str(a["conditional_cagr"]))):
        verdict = "contraria"
    else:
        verdict = "mixta"
    for row in output:
        row["opportunity_mean_bps"] = (row["opportunity_mean"]*10000
                                        if row["opportunity_mean"] is not None else None)
        row["h3_descriptive"] = verdict
        row["comparison_scope"] = "2022-2023 versus 2024+; annual rows are descriptive breakdowns"
    return output


FUNDING_FIELDS = ("symbol", "funding_time", "available_at", "funding_rate", "interval_hours",
                  "interval_verified")


def funding_rows_from_run(run):
    return [{k: row[k] for k in FUNDING_FIELDS}
            for row in read_json(Path(run)/"funding_mark_audit.json")["consumed"]]


def funding_history(rows):
    output = defaultdict(list)
    for row in rows:
        item = Funding(row["symbol"], int(row["funding_time"]), int(row["available_at"]),
                       D(str(row["funding_rate"])), D(str(row["interval_hours"])), None,
                       "persisted_consumed_funding", core.yes(row["interval_verified"]))
        output[item.symbol].append(item)
    for symbol, items in output.items():
        items.sort(key=lambda r: r.funding_time)
        if len({r.funding_time for r in items}) != len(items):
            raise ValueError(f"Duplicate consumed funding: {symbol}")
    return output


def evaluate_h1(signals, funding_rows, config):
    history = funding_history(funding_rows)
    schedules, audit = checked_forecasts(signals, history, config)
    observations = h1_observations(signals, history, config)
    for row in observations:
        row.update(horizon_hours=config.horizon_hours, unit=f"pb/{config.horizon_hours} h",
                   available_at=int(row["time_ns"]), target_start_exclusive=int(row["time_ns"]))
    return observations, schedules, audit


def compare_saved_h1(rows, saved):
    """Same 1E-14 rate tolerance as the original E3 float-export comparison."""
    original = {(r["symbol"], int(r["time_ns"])): r for r in saved}
    if len(original) != len(saved) or set(original) != {
        (r["symbol"], r["time_ns"]) for r in rows
    }:
        raise ValueError("H1 source cohort changed")
    for row in rows:
        old = original[row["symbol"], row["time_ns"]]
        if core.yes(row["horizon_valid"]) != core.yes(old["horizon_valid"]) or row["reason"] != old["reason"]:
            raise ValueError("Recomputed H1 exclusions differ from saved evidence")
        if row["horizon_valid"]:
            for field in ("realized", "absolute_error_ewma", "absolute_error_no_change"):
                if abs(D(str(row[field]))-D(str(old[field]))) > D("1E-14"):
                    raise ValueError(f"Recomputed H1 label/error differs: {field}")


def prepare_hypotheses(run, scenario, data_root, destination):
    """New postprocessing, never attributed retrospectively to the archived engine run."""
    run, destination = Path(run), Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    config = Config.load(run/"effective_config.toml")
    signals = parquet(run/"signals.parquet")
    funding_rows = funding_rows_from_run(run)
    observations, schedules, audit = evaluate_h1(signals, funding_rows, config)
    compare_saved_h1(observations, read_csv(run/"forecast_evaluation.csv"))
    manifest = read_json(Path(data_root)/config.data_dir/"manifests/processed.json")
    days, joint, groups, sample = market_opportunity(
        Path(data_root), manifest, schedules, config, D(".0034"))
    raw = {r["date"]: r for r in read_csv(run/"opportunity_daily.csv")}
    if set(raw) != {r["date"] for r in joint}:
        raise ValueError("H3 daily cohort differs from the economic replay")
    for row in joint:
        old = raw[row["date"]]
        if core.yes(old["complete"]) != row["complete"]:
            raise ValueError("H3 coverage differs from the original engine")
        if row["complete"]:
            for field in ("opportunity", "eligible_fraction"):
                if abs(D(str(row[field]))-D(old[field])) > D("1E-14"):
                    raise ValueError(f"H3 {field} differs from economic replay: {row['date']}")
        # Financial/H3 daily reports use end-of-day, not start-of-day timestamps.
        row["time_ns"] = timestamp(row["date"]+"T00:00:00Z")+core.DAY-1
    for name, rows in (("h1_observaciones", observations), ("h1_resumen", summarize_h1(observations, config)),
                       ("h3_activos_diarios", days), ("h3_diario", joint),
                       ("h3_grupos_forecast", groups), ("h3_muestra_minutos", sample)):
        write_csv(destination/f"{name}.csv", [dict(scenario=scenario, **r) for r in rows])
    write_json(destination/"forecasts_verificados.json", dict(
        scenario=scenario, run_id=run.name, audit=audit,
        schedules=schedules, original_config=config.to_dict(),
        h1_saved_float_tolerance="1E-14 (original E3 comparison helper)",
        h3_saved_float_tolerance="1E-14; integer counts checked separately",
        market_dependency=str(Path(data_root)/config.data_dir),
        raw_manifest_sha256=core.sha256(run/"run_manifest.json"),
        funding_source="../../fuentes/funding_consumido.csv",
    ))
    return dict(observations=len(observations), valid_days=sum(r["complete"] for r in joint))
