"""Construct the preliminary rules comparison only from persisted run artifacts."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal as D
from pathlib import Path

if __package__:
    from . import verify_rules_sensitivity_package as verify
else:
    import verify_rules_sensitivity_package as verify

COMPARATORS = verify.COMPARATORS
COMPONENTS = verify.COMPONENTS
SYMBOLS = verify.SYMBOLS
DAY = verify.DAY
SECOND = verify.SECOND


def period_financials(daily, periods):
    return verify.period_financials(daily, periods)


def compare_deltas(rows):
    index = {(r["scenario"], r["strategy"], r["period"]): r for r in rows}
    output = []
    for row in rows:
        comparator = COMPARATORS[row["scenario"]]
        if not comparator:
            continue
        other = index.get((comparator, row["strategy"], row["period"]))
        for key, value in row.items():
            if key in {"days", "period"} or isinstance(value, bool):
                continue
            if not isinstance(value, (D, float, int)) and value is not None:
                continue
            prior = other.get(key) if other else None
            output.append(
                dict(
                    scenario=row["scenario"],
                    comparator=comparator,
                    strategy=row["strategy"],
                    period=row["period"],
                    run_id=row["run_id"],
                    comparator_run_id=other["run_id"] if other else "",
                    metric=key,
                    value=value,
                    comparator_value=prior,
                    delta=D(str(value)) - D(str(prior))
                    if value is not None and prior is not None
                    else None,
                    reason=""
                    if value is not None and prior is not None
                    else "missing_or_undefined_metric",
                )
            )
    return output


def h2_comparison(rows):
    index = {(r["scenario"], r["period"], r["strategy"]): r for r in rows}
    output = []
    for scenario, period in sorted({(r["scenario"], r["period"]) for r in rows}):
        cond, perm = (
            index.get((scenario, period, strategy), {}) for strategy in ("conditional", "permanent")
        )
        a, b = cond.get("sharpe"), perm.get("sharpe")
        difference = D(str(a)) - D(str(b)) if a is not None and b is not None else None
        output.append(
            dict(
                scenario=scenario,
                period=period,
                conditional_run_id=cond.get("run_id", ""),
                permanent_run_id=perm.get("run_id", ""),
                conditional_sharpe=a,
                permanent_sharpe=b,
                sharpe_difference=difference,
                verdict="no_concluyente"
                if difference is None
                else "favorable"
                if difference > 0
                else "no_favorable",
                reason="; ".join(
                    x.get("sharpe_reason", "missing portfolio" if not x else "")
                    for x in (cond, perm)
                ).strip("; "),
            )
        )
    return output


def exposure_summary(ledger, periods, tolerance):
    output = []
    for period, start, end in periods:
        state = {symbol: (D(0), D(0)) for symbol in SYMBOLS}
        events = defaultdict(list)
        for row in ledger:
            moment = int(row["time_ns"])
            if moment < end:
                events[max(start, moment)].append(row)
        times = sorted({start, end, *events})
        totals = {symbol: defaultdict(lambda: D(0)) for symbol in (*SYMBOLS, "PORTFOLIO")}
        for lower, upper in zip(times, times[1:]):
            for row in events.get(lower, []):
                if row["symbol"] in state:
                    state[row["symbol"]] = (
                        verify.decimal(row["spot"]),
                        verify.decimal(row["short"]),
                    )
            seconds = D(upper - lower) / SECOND
            invested, uncovered, covered = [], [], []
            for symbol, (spot, short) in state.items():
                is_invested = spot > 0 or short > 0
                error = abs(spot - short) / spot if spot > 0 else (D(1) if short > 0 else D(0))
                is_uncovered = is_invested and error > tolerance
                is_covered = is_invested and not is_uncovered
                for key, flag in (
                    ("invested_seconds", is_invested),
                    ("unhedged_seconds", is_uncovered),
                    ("covered_seconds", is_covered),
                    ("cash_seconds", not is_invested),
                ):
                    totals[symbol][key] += seconds * flag
                invested.append(is_invested)
                uncovered.append(is_uncovered)
                covered.append(is_covered)
            portfolio = totals["PORTFOLIO"]
            for key, flag in (
                ("invested_seconds", any(invested)),
                ("unhedged_seconds", any(uncovered)),
                ("covered_seconds", any(covered)),
                ("both_covered_seconds", all(covered)),
                ("cash_seconds", not any(invested)),
            ):
                portfolio[key] += seconds * flag
        for symbol, values in totals.items():
            output.append(
                dict(
                    period=period,
                    symbol=symbol,
                    **values,
                    calendar_seconds=D(end - start) / SECOND,
                    invested_fraction=values["invested_seconds"] / (D(end - start) / SECOND),
                )
            )
    return output


def h3_from_assets(rows):
    return verify.h3_from_assets(rows)


def seal_package(package):
    package = Path(package).resolve()
    target = package / verify.MANIFEST
    if target.exists() or (package / verify.MANIFEST_SIDECAR).exists():
        raise FileExistsError(f"Package already sealed: {package}")
    members = []
    for path in sorted(package.rglob("*")):
        if path.is_file():
            relative = path.relative_to(package).as_posix()
            verify.safe_path(package, relative)
            members.append(
                dict(path=relative, size=path.stat().st_size, sha256=verify.sha256(path))
            )
    manifest = dict(
        schema="rules_sensitivity_package_v1",
        created_at=datetime.now(UTC).isoformat(),
        purpose="technical_preliminary_rules_sensitivity",
        members=members,
        excludes=[verify.MANIFEST, verify.MANIFEST_SIDECAR],
        limitations="Integrity and persisted arithmetic; no Git publication or independent engine validation.",
    )
    target.write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    (package / verify.MANIFEST_SIDECAR).write_text(verify.sha256(target) + "\n", encoding="ascii")
    return manifest


def write_csv(path, rows, fields=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = fields or list(dict.fromkeys(key for row in rows for key in row))
    if not columns:
        columns = ["status", "reason"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def h1_summaries(rows, periods):
    return verify.h1_summaries(rows, periods)


def execution_periods(tables, periods):
    output = []
    for period, lower, upper in periods:
        selected = {
            name: [r for r in rows if lower <= int(r["time_ns"]) < upper]
            for name, rows in tables.items()
        }
        fills, orders, risks = (selected[name] for name in ("fills", "orders", "risk_events"))
        events = [r for r in orders if r.get("record_type") == "event"]
        failed = {
            r["order_id"] for r in events if r.get("status") in {"expired", "rejected", "timeout"}
        }
        failed.update(
            r["order_id"] for r in risks if r.get("kind") == "attempt_failed" and r.get("order_id")
        )
        output.append(
            dict(
                period=period,
                orders_submitted=len(
                    {r["order_id"] for r in events if r.get("action") == "submitted"}
                ),
                failed_attempts=len(failed),
                fills=len(fills),
                partial_fills=sum(verify.yes(r["partial"]) for r in fills),
                openings=sum(
                    r.get("kind") == "transition" and r.get("state") == "OPENING_SPOT"
                    for r in risks
                ),
                completed_openings=sum(
                    r.get("kind") == "transition" and r.get("cause") == "opening_complete"
                    for r in risks
                ),
                renewals=sum(r.get("kind") == "renewal" for r in risks),
                rebalances=sum(
                    r.get("kind") == "transition" and r.get("state") == "REBALANCING" for r in risks
                ),
                corrections=sum(
                    r.get("kind") == "transition" and r.get("state") == "CORRECTING_HEDGE"
                    for r in risks
                ),
                close_requests=sum(r.get("kind") == "close_requested" for r in risks),
                margin_close_requests=sum(
                    r.get("kind") == "close_requested" and r.get("cause") == "margin" for r in risks
                ),
                liquidation_fills=sum(verify.yes(r["liquidation"]) for r in fills),
                blocked_orders=sum(r.get("kind") == "order_blocked" for r in risks),
                turnover_usdt=sum(
                    (verify.decimal(r["quantity"]) * verify.decimal(r["price"]) for r in fills),
                    D(0),
                ),
            )
        )
    return output


def margin_daily(rows, assumptions):
    rules = assumptions.get("rules", [])
    output = []
    for row in rows:
        total = D(0)
        ratios, missing, active = [], [], 0
        for symbol in SYMBOLS:
            short = verify.decimal(row[f"{symbol}_short"])
            if not short:
                continue
            active += 1
            current = [
                r
                for r in rules
                if r["symbol"] == symbol
                and r["market"] == "futures"
                and verify.timestamp(r["valid_from"])
                <= int(row["time_ns"])
                < verify.timestamp(r["valid_to"])
            ]
            if len(current) != 1:
                missing.append(symbol)
                continue
            mark = verify.decimal(row[f"{symbol}_mark"])
            notional = short * mark
            tiers = sorted(current[0]["values"]["tiers"], key=lambda t: verify.decimal(t["floor"]))
            tier = next(
                (
                    t
                    for t in tiers
                    if verify.decimal(t["floor"]) <= notional <= verify.decimal(t["cap"])
                ),
                None,
            )
            if tier is None:
                raise ValueError(f"Persisted margin tiers do not cover {symbol}: {notional}")
            requirement = notional * verify.decimal(tier["rate"]) - verify.decimal(
                tier["deduction"]
            )
            balance = verify.decimal(row[f"{symbol}_collateral"]) + short * (
                verify.decimal(row[f"{symbol}_average"]) - mark
            )
            total += requirement
            ratios.append(requirement / balance if balance > 0 else None)
        output.append(
            dict(
                time_ns=int(row["time_ns"]),
                maintenance_usdt=None if missing else total,
                maintenance_to_balance_max=max(ratios) if ratios and None not in ratios else None,
                active_margin_positions=active,
                margin_reason="missing persisted margin rules: " + ",".join(missing)
                if missing
                else "no active short"
                if not active
                else "nonpositive balance"
                if None in ratios
                else "",
            )
        )
    return output


def promotion_boundaries(fills):
    output = []
    for label, moment in (
        ("promo_start", verify.timestamp("2022-07-08T14:00:00Z")),
        ("promo_end", verify.timestamp("2023-03-22T00:00:00Z")),
    ):
        selected = [
            r
            for r in fills
            if r["symbol"] == "BTCUSDT"
            and r["market"] == "spot"
            and int(r.get("window_start") or r["time_ns"])
            <= moment
            <= int(r.get("window_end") or r["time_ns"])
        ]
        if not selected:
            output.append(
                dict(
                    boundary=label,
                    boundary_utc=verify.iso(moment),
                    fill_id="",
                    status="no_fill_at_boundary",
                )
            )
        for row in selected:
            start, end = int(row["window_start"]), int(row["window_end"])
            output.append(
                dict(
                    boundary=label,
                    boundary_utc=verify.iso(moment),
                    fill_id=row["fill_id"],
                    window_start_utc=verify.iso(start),
                    window_end_utc=verify.iso(end),
                    fee_rate=row["fee_rate"],
                    status="crosses_inside_minute" if start < moment < end else "minute_boundary",
                    convention="fee effective at window_start; accounted at window_end",
                )
            )
    return output


def build_report(package, *, figures=True):
    import pyarrow.parquet as pq

    package = Path(package).resolve()
    if (package / verify.MANIFEST).exists():
        raise FileExistsError("Report construction cannot modify a sealed package")
    items = verify.load_index(package)
    output = package / "comparacion"
    output.mkdir(parents=True, exist_ok=True)
    tables = defaultdict(list)
    runs = {}
    for item in items:
        registry = {
            key: item.get(key, "")
            for key in (
                "scenario",
                "strategy",
                "status",
                "engine_status",
                "run_id",
                "path",
                "manifest_sha256",
            )
        }
        registry["reason"] = item.get("reason", item.get("motivo", ""))
        tables["registro_corridas"].append(registry)
        if item["status"] not in verify.SUCCESS:
            continue
        manifest = verify.check_run(package, item)
        run = verify.safe_path(package, item["path"])
        common = dict(scenario=item["scenario"], strategy=item["strategy"], run_id=item["run_id"])
        config = manifest["config"]
        periods = verify.periods(config)
        raw_daily = verify.read_csv(run / "equity_daily.csv")
        daily, assets = verify.financial_daily(raw_daily, verify.decimal(config["capital"]))
        primitives = {
            name: pq.read_table(run / (name + ".parquet")).to_pylist()
            for name in ("signals", "ledger", "fills", "orders", "risk_events")
        }
        events = execution_periods(primitives, periods)
        exposure = exposure_summary(
            primitives["ledger"], periods, verify.decimal(config["hedge_tolerance"])
        )
        assumptions_path = run / "research_assumptions.json"
        margins = margin_daily(
            raw_daily, verify.read_json(assumptions_path) if assumptions_path.is_file() else {}
        )
        for row, margin in zip(daily, margins):
            row.update({key: value for key, value in margin.items() if key != "time_ns"})
        financial = period_financials(daily, periods)
        for archived in verify.read_csv(run / "metrics.csv"):
            selected = next((r for r in financial if r["period"] == archived["period"]), None)
            if selected is None:
                raise ValueError(f"Unexpected archived metric period: {archived['period']}")
            for key in (
                "net_return",
                "cagr",
                "sharpe",
                "annual_volatility",
                "max_drawdown",
                "max_drawdown_days",
            ):
                if key in archived:
                    verify.assert_close(
                        archived[key], selected[key], f"Archived metric {item['run_id']} {key}"
                    )
        for archived in verify.read_csv(run / "execution_summary.csv"):
            selected = next(
                r for r in exposure if r["period"] == "full" and r["symbol"] == archived["symbol"]
            )
            for key in ("invested_seconds", "unhedged_seconds", "cash_seconds"):
                if archived.get(key) not in (None, ""):
                    verify.assert_close(
                        archived[key], selected[key], f"Archived duration {item['run_id']} {key}"
                    )
        for row in financial:
            row.update(next(r for r in events if r["period"] == row["period"]))
            row.update(
                {
                    key: value
                    for key, value in next(
                        r
                        for r in exposure
                        if r["period"] == row["period"] and r["symbol"] == "PORTFOLIO"
                    ).items()
                    if key not in {"symbol", "period"}
                }
            )
            lower, upper = next((lo, hi) for label, lo, hi in periods if label == row["period"])
            selection = [r for r in margins if lower <= r["time_ns"] < upper]
            maintenance = [r["maintenance_usdt"] for r in selection]
            ratios = [
                r["maintenance_to_balance_max"]
                for r in selection
                if r["maintenance_to_balance_max"] is not None
            ]
            row.update(
                maintenance_daily_mean_usdt=sum(maintenance, D(0)) / len(maintenance)
                if None not in maintenance
                else None,
                maintenance_daily_max_usdt=max(maintenance) if None not in maintenance else None,
                maintenance_ratio_daily_max=max(ratios) if ratios else None,
                maintenance_reason="" if ratios else "no defined active daily margin ratio",
            )
        tables["metricas_cartera_periodo"].extend(dict(common, **r) for r in financial)
        tables["diario_carteras"].extend(dict(common, **r) for r in daily)
        tables["eventos_periodo"].extend(dict(common, **r) for r in events)
        tables["exposicion_periodo"].extend(dict(common, **r) for r in exposure)
        for period, lower, upper in periods:
            for symbol in SYMBOLS:
                selected = [
                    r for r in assets if r["symbol"] == symbol and lower <= r["time_ns"] < upper
                ]
                tables["componentes_por_activo_periodo"].append(
                    dict(
                        common,
                        period=period,
                        symbol=symbol,
                        **{
                            key: sum((r[key] for r in selected), D(0))
                            for key in (*COMPONENTS, *verify.SPLIT_COMPONENTS, "net_pnl_usdt")
                        },
                    )
                )
        tables["conciliaciones"].append(
            dict(
                common,
                daily_rows=len(daily),
                max_daily_residual_usdt=max(abs(r["reconciliation_residual_usdt"]) for r in daily),
                max_daily_balance_residual_usdt=max(abs(r["balance_residual_usdt"]) for r in daily),
                max_period_residual_usdt=max(
                    abs(r["reconciliation_residual_usdt"]) for r in financial
                ),
                tolerance_usdt=verify.TOLERANCE,
                status="passed",
            )
        )
        tables["fronteras_promocion"].extend(
            dict(common, **r) for r in promotion_boundaries(primitives["fills"])
        )
        forecast = verify.read_csv(run / "forecast_evaluation.csv")
        h1_summary = verify.read_csv(run / "h1_summary.csv")
        h1 = h1_summaries(forecast, periods)
        for archived in h1_summary:
            selected = next(
                r
                for r in h1
                if r["period"] == archived["period"] and r["symbol"] == archived["symbol"]
            )
            for key in ("observations", "excluded", "mae_ewma", "mae_no_change"):
                verify.assert_close(
                    archived[key], selected[key], f"H1 {item['run_id']} {key}", D("1E-15")
                )
        tables["h1_resumen"].extend(dict(common, **r) for r in h1)
        signal_fields = (
            "symbol",
            "time_ns",
            "anchor",
            "history_start",
            "forecast",
            "no_change",
            "valid",
            "forecast_reason",
        )
        signals = [{key: r.get(key) for key in signal_fields} for r in primitives["signals"]]
        h1_digest = dict(
            forecast_evaluation_sha256=verify.economic_digest(forecast),
            h1_summary_sha256=verify.economic_digest(h1_summary),
            signal_forecasts_sha256=verify.economic_digest(signals),
        )
        opportunity = verify.read_csv(run / "opportunity_daily.csv")
        h3_path, source_id, source_status, source_reason = verify.h3_source(package, item, items)
        h3_assets = verify.read_csv(h3_path) if h3_path.is_file() else []
        if h3_assets and any(r.get("run_id") != source_id for r in h3_assets):
            raise ValueError(f"H3 source run identity mismatch: {h3_path}")
        reconstructed = {r["date"]: r for r in h3_from_assets(h3_assets)}
        h3_days = []
        if reconstructed and set(reconstructed) != {r["date"] for r in opportunity}:
            raise ValueError(f"H3 missing or extra reconstructed day: {item['run_id']}")
        for stored in opportunity:
            if reconstructed:
                row = reconstructed[stored["date"]]
                if verify.yes(stored["complete"]) != row["complete"]:
                    raise ValueError(
                        f"H3 reconstructed completeness differs: {item['run_id']}/{stored['date']}"
                    )
                verify.assert_close(
                    stored["opportunity"],
                    row["opportunity"],
                    "H3 gross eligible forecast",
                    D("1E-14"),
                )
                verify.assert_close(
                    stored["eligible_fraction"],
                    row["eligible_fraction"],
                    "H3 eligible fraction",
                    D("1E-14"),
                )
            else:
                complete = verify.yes(stored["complete"])
                row = dict(
                    date=stored["date"],
                    time_ns=int(stored["time_ns"]),
                    complete=complete,
                    opportunity=verify.decimal(stored["opportunity"]) if complete else None,
                    eligible_fraction=verify.decimal(stored["eligible_fraction"])
                    if complete
                    else None,
                    observed_asset_minutes=None,
                    unknown_asset_minutes=None,
                    reason=stored["reason"],
                )
            h3_days.append(
                dict(
                    common,
                    **row,
                    source_run_id=source_id,
                    provenance=source_status if reconstructed else "solo_agregado_archivado",
                    source_reason=source_reason,
                    per_asset_minutes_verified=bool(reconstructed),
                )
            )
        tables["h3_diario"].extend(h3_days)
        h3_regimes = []
        for period, lower, upper in periods:
            selection = [r for r in h3_days if lower <= r["time_ns"] < upper]
            valid = [r for r in selection if r["complete"]]
            all_valid = len(valid) == (upper - lower) // DAY
            finance = next(r for r in financial if r["period"] == period)
            h3_regimes.append(
                dict(
                    common,
                    period=period,
                    observed_days=len(selection),
                    valid_days=len(valid),
                    coverage_complete=all_valid,
                    opportunity_mean=sum((r["opportunity"] for r in valid), D(0)) / len(valid)
                    if valid
                    else None,
                    eligible_fraction=sum((r["eligible_fraction"] for r in valid), D(0))
                    / len(valid)
                    if valid
                    else None,
                    portfolio_cagr=finance["cagr"],
                    source_run_id=source_id,
                    provenance=source_status if reconstructed else "solo_agregado_archivado",
                )
            )
        before = next((r for r in h3_regimes if r["period"] == "2022-2023"), None)
        after = next((r for r in h3_regimes if r["period"] == "2024+"), None)
        verdict = "no_concluyente"
        if (
            before
            and after
            and before["coverage_complete"]
            and after["coverage_complete"]
            and before["portfolio_cagr"] is not None
            and after["portfolio_cagr"] is not None
        ):
            delta_o = after["opportunity_mean"] - before["opportunity_mean"]
            delta_c = after["portfolio_cagr"] - before["portfolio_cagr"]
            verdict = (
                "favorable"
                if delta_o < 0 and delta_c < 0
                else "contraria"
                if delta_o > 0 and delta_c > 0
                else "mixta"
            )
        for row in h3_regimes:
            row["h3_descriptive"] = (
                verdict if item["strategy"] == "conditional" else "not_used_for_H3_cagr"
            )
        tables["h3_regimen"].extend(h3_regimes)
        runs[(item["scenario"], item["strategy"])] = dict(
            item=item,
            common=common,
            daily=daily,
            financial=financial,
            h1_digest=h1_digest,
            h3_digest=verify.economic_digest(opportunity),
            h3_reconstructed=bool(reconstructed),
            h3_days=h3_days,
        )
    for (scenario, strategy), run in runs.items():
        base = runs.get(("BASE_E3", strategy))
        if base is None:
            raise ValueError(f"Missing verified BASE_E3 for {strategy}")
        same_h1 = run["h1_digest"] == base["h1_digest"]
        if not same_h1:
            raise ValueError(
                f"H1 forecast, target, exclusion or weight invariance failed: {scenario}/{strategy}"
            )
        tables["h1_invariancia"].append(
            dict(
                run["common"],
                base_run_id=base["item"]["run_id"],
                **run["h1_digest"],
                exact_invariance=True,
                btc_weight=D("0.5"),
                eth_weight=D("0.5"),
                ignored_identity_fields="run_id; strategy/filter only in raw signal projection",
            )
        )
        peer = runs.get((scenario, "permanent" if strategy == "conditional" else "conditional"))
        invariant = run["h3_digest"] == base["h3_digest"]
        expected_invariant = not scenario.endswith("_DECISION")
        if expected_invariant and not invariant:
            raise ValueError(
                f"H3 unchanged decision inputs must be exactly invariant: {scenario}/{strategy}"
            )
        if peer and peer["h3_digest"] != run["h3_digest"]:
            raise ValueError(f"H3 cannot depend on portfolio: {scenario}")
        tables["h3_invariancia"].append(
            dict(
                run["common"],
                base_run_id=base["item"]["run_id"],
                opportunity_daily_sha256=run["h3_digest"],
                exact_base_invariance=invariant,
                expected_base_invariance=expected_invariant,
                independent_of_portfolio=bool(peer),
                per_asset_minutes_verified=run["h3_reconstructed"],
                decision_cost="scenario contemporaneous cost"
                if scenario.endswith("_DECISION")
                else "0.0034",
            )
        )
    tables["deltas"] = compare_deltas(tables["metricas_cartera_periodo"])
    tables["h2"] = h2_comparison(tables["metricas_cartera_periodo"])
    for name in (p.removesuffix(".csv") for p in verify.REPORT_REQUIRED if p.endswith(".csv")):
        write_csv(output / (name + ".csv"), tables[name])
    write_csv(output / "fronteras_promocion.csv", tables["fronteras_promocion"])
    if figures:
        draw_figures(output, tables)
    (output / "reporte.md").write_text(render_report(tables, figures), encoding="utf-8")
    return dict(
        status="constructed_not_sealed",
        successful_runs=len(runs),
        financial_periods=len(tables["metricas_cartera_periodo"]),
        daily_reconciliations=len(tables["diario_carteras"]),
        output=str(output),
    )


def format_value(value, digits=4):
    if value is None or value == "":
        return "ND"
    if isinstance(value, (bool, int)):
        return str(value)
    if isinstance(value, (float, D)):
        return f"{value:,.{digits}f}"
    return str(value).replace("|", "\\|").replace("\n", " ")


def md_table(rows, columns):
    header = "| " + " | ".join(columns) + " |\n| " + " | ".join("---" for _ in columns) + " |\n"
    return (
        header
        + "\n".join(
            "| "
            + " | ".join(
                format_value(row.get(key), 8 if key == "opportunity_mean" else 4) for key in columns
            )
            + " |"
            for row in rows
        )
        + "\n"
    )


def render_report(tables, figures):
    metrics = tables["metricas_cartera_periodo"]
    full = [r for r in metrics if r["period"] == "full"]
    statuses = tables["registro_corridas"]
    success = sum(r["status"] in verify.SUCCESS for r in statuses)
    full_index = {(r["scenario"], r["strategy"]): r for r in full}
    findings = []
    for scenario, comparator in COMPARATORS.items():
        if not comparator:
            continue
        changes = []
        for strategy in ("conditional", "permanent"):
            current, previous = (
                full_index.get((scenario, strategy)),
                full_index.get((comparator, strategy)),
            )
            if current and previous:
                delta = current["final_equity_usdt"] - previous["final_equity_usdt"]
                changes.append(
                    f"{strategy}: {delta:+,.4f} USDT (`{current['run_id']}` frente a `{previous['run_id']}`)"
                )
        if changes:
            findings.append(
                f"- **{scenario} frente a {comparator}**, cambio de equity final: "
                + "; ".join(changes)
                + "."
            )
    h2_verdicts = [
        f"{r['scenario']}: {r['verdict']}" for r in tables["h2"] if r["period"] == "full"
    ]
    h3_verdicts = [
        f"{r['scenario']}: {r['h3_descriptive']}"
        for r in tables["h3_regimen"]
        if r["strategy"] == "conditional" and r["period"] == "2024+"
    ]
    sections = [
        "# Primera sensibilidad de reglas — versión técnica preliminar\n",
        "Pendiente de comentarios del profesor. Comparación exploratoria sobre historia observada; no es evaluación fuera de muestra ni Entrega 4 completa. Trabajo local, sin commit ni push.\n",
        "## Referencia presentada y estado de ejecución\n",
        "BASE_E3 conserva las corridas archivadas y sus manifiestos; la reutilización se documenta en la verificación previa del paquete. Las carteras son independientes. Los valores de esta tabla provienen de [metricas_cartera_periodo.csv](metricas_cartera_periodo.csv); cada cifra mantiene su run_id.\n",
        f"Hay {success} resultados utilizables entre {len(statuses)} estados previstos. Los estados fallido/bloqueado se conservan con motivo y no se convierten en períodos sin inversión.\n",
        md_table(statuses, ["scenario", "strategy", "status", "engine_status", "run_id", "reason"]),
        "## Evidencia y supuestos experimentales\n",
        "La promoción BTC spot usa el intervalo documentado `[2022-07-08T14:00:00Z, 2023-03-22T00:00:00Z)`; [fact_id BTC_SPOT_ZERO](../evidencia_historica/data/research/historical-rules-followup-20260924T234206Z/reglas_historicas.json), [source_id PROMO_START y PROMO_END](../evidencia_historica/data/research/historical-rules-followup-20260924T234206Z/fuentes.json), enlazados en la [matriz de integración](../documentos/matriz_integracion.csv). El supuesto de conocimiento al inicio en DECISION no acredita un known_from histórico. La tasa spot 0,001 fuera de promoción sigue siendo un supuesto base. FUT4 es el supuesto constante de 4 pb y no identifica una transición histórica. MARGEN_2X es estrés de mantenimiento, conservando apalancamiento inicial 2x. El [protocolo previo](../documentos/protocolo.md) fija esos comparadores y supuestos.\n",
        "Las variantes REALIZADA cambian comisiones cobradas y conservan filtro 34 pb; DECISION compara con su REALIZADA y usa 2×spot vigente + 2×futuros vigente + 4×slippage, sin anticipar la tarifa futura de salida. Cambian trayectorias completas; los deltas no son un ahorro aislado con posiciones fijas.\n",
        "## Resultados económicos ejecutados\n",
        "USDT para equity/P&L; retorno, CAGR y drawdown son razones (0,01 = 1%). Sharpe usa retornos diarios, desviación muestral, 365 días y tasa libre de riesgo cero. ND conserva su motivo en el CSV.\n",
        md_table(
            full,
            [
                "scenario",
                "strategy",
                "run_id",
                "starting_equity_usdt",
                "final_equity_usdt",
                "net_pnl_usdt",
                "net_return",
                "cagr",
                "sharpe",
                "max_drawdown",
            ],
        ),
        "Cambios frente al comparador fijado, calculados en [deltas.csv](deltas.csv):\n\n"
        + "\n".join(findings)
        + "\n",
        "Los cortes continuos 2022–2023, 2024–agosto de 2026 y años disponibles están en el mismo CSV. Cada subperíodo arranca con equity anterior; no se reinician 10.000 USDT. [Deltas](deltas.csv) identifica la pareja de run_id y el comparador predefinido.\n",
        "## Atribución, exposición y riesgo\n",
        "[Diario](diario_carteras.csv), [atribución por activo/período](componentes_por_activo_periodo.csv) y [conciliaciones](conciliaciones.csv) derivan los cambios de cumulativos spot/futuros realizados y no realizados, funding, fees y liquidación. Slippage ya está en precios: su columna es informativa y nunca se resta otra vez.\n",
        md_table(
            full,
            [
                "scenario",
                "strategy",
                "run_id",
                "spot_pnl_usdt",
                "futures_pnl_usdt",
                "funding_usdt",
                "fees_usdt",
                "liquidation_fees_usdt",
                "slippage_informational_usdt",
                "reconciliation_residual_usdt",
            ],
        ),
        "[Eventos por período](eventos_periodo.csv) cuenta aperturas, intentos fallidos por orden, fills/parciales, cierres solicitados por margen y fills de liquidación. [Exposición](exposicion_periodo.csv) integra cantidades del ledger entre eventos; los segundos de cartera son la unión de activos y conservan residuos spot como inversión, igual que el contador original. Un residuo sin corto cuenta como exposición sin cobertura. No se infieren trades subminuto.\n",
        md_table(
            full,
            [
                "scenario",
                "strategy",
                "run_id",
                "openings",
                "failed_attempts",
                "fills",
                "partial_fills",
                "invested_fraction",
                "unhedged_seconds",
                "margin_close_requests",
                "liquidation_fills",
            ],
        ),
        "Utilización = (valor spot + collateral)/equity, exposición bruta = spot + nocional corto. Utilización, collateral, mantenimiento y su razón se observan al cierre diario; sus máximos no son máximos intradiarios. Mantenimiento se deriva de los tramos prescritos guardados en research_assumptions.json de cada corrida. No es una tabla histórica de Binance. [Fronteras de promoción](fronteras_promocion.csv) conserva todos los fills que tocan una frontera exacta o declara su ausencia.\n",
        "## H1, H2 y H3\n",
        "[H1 invariancia](h1_invariancia.csv) compara exactamente pronósticos Decimal de signals, targets/exclusiones de forecast_evaluation y resumen original, ignorando identidad de corrida. [H1 resumen](h1_resumen.csv) recalcula MAE por activo y promedio 50/50. La invariancia es un control de entradas, no un descubrimiento económico.\n",
        "[H2](h2.csv) compara Sharpe condicional y permanente dentro del mismo escenario y período; un Sharpe ND implica no_concluyente.\n",
        md_table(
            [r for r in tables["h2"] if r["period"] == "full"],
            [
                "scenario",
                "conditional_run_id",
                "permanent_run_id",
                "conditional_sharpe",
                "permanent_sharpe",
                "sharpe_difference",
                "verdict",
                "reason",
            ],
        ),
        "Lectura descriptiva H2 en la muestra completa ([parejas y cifras](h2.csv)): "
        + "; ".join(h2_verdicts)
        + ".\n",
        "[H3 diario](h3_diario.csv) usa todos los minutos, media de forecast bruto elegible por activo y ponderación 50/50. Desconocido mantiene ND. [H3 invariancia](h3_invariancia.csv) prueba igualdad exacta diaria en variantes sin cambio de costo ex ante e independencia de las dos carteras. DECISION recalcula elegibilidad con su costo. El origen de cada reconstrucción por activo figura como source_run_id y provenance; BASE derivada de una REALIZADA no se presenta como archivo por activo archivado de Entrega 3.\n",
        md_table(
            [
                r
                for r in tables["h3_regimen"]
                if r["strategy"] == "conditional" and r["period"] in {"2022-2023", "2024+"}
            ],
            [
                "scenario",
                "period",
                "run_id",
                "source_run_id",
                "opportunity_mean",
                "eligible_fraction",
                "portfolio_cagr",
                "valid_days",
                "h3_descriptive",
            ],
        ),
        "Lectura H3 de oportunidad y CAGR condicional entre regímenes ([tabla trazable](h3_regimen.csv)): "
        + "; ".join(h3_verdicts)
        + ". Un cambio de costos puede alterar el CAGR aun cuando la oportunidad de mercado permanezca igual.\n",
        "## Límites y trabajo pendiente\n",
        "El reporte conserva las aproximaciones futures_scaled para marcas/funding y los límites de ejecución de minuto de Entrega 3. No demuestra una cronología completa de tarifas, filtros ni margen. El diagnóstico sobre la base no simula órdenes que aparecerían bajo otras reglas. La integración de capturas y una segunda tanda permanecen separadas, sin forward-fill ni política de cohortes inventados. Consulte la matriz y el diagnóstico del paquete.\n",
        "El verificador portable comprueba bytes/manifiestos y aritmética persistida sin motor ni datos masivos; los hashes de inputs se conservan pero el comando portable no vuelve a leer esos inputs. El registro previo documenta su rehash local. La integridad no certifica autenticidad de fuentes, primera publicación, causalidad completa del motor ni publicación GitHub.\n",
        "Construcción: `python scripts/report_historical_rules_sensitivity.py --package <paquete>`. Tras cerrar todos los artefactos, sello explícito con `--seal`; verificación: `python -B scripts/verify_rules_sensitivity_package.py --package <paquete>`. Resultados opcionales del verificador van a una ruta nueva externa.\n",
    ]
    if figures:
        sections.insert(11, "![Equity continua por cartera](figuras/equity.png)\n")
        sections.extend(
            [
                "![Delta de equity frente al comparador declarado](figuras/deltas.png)\n",
                "![H3 por régimen](figuras/h3.png)\n",
            ]
        )
    return "\n".join(sections)


def draw_figures(output, tables):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    destination = output / "figuras"
    destination.mkdir(exist_ok=True)
    plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False})
    colors = dict(
        zip(COMPARATORS, ("#172b4d", "#007f5f", "#5dba79", "#a85b00", "#e4a739", "#8b398b"))
    )
    fig, axes = plt.subplots(2, 1, figsize=(10.5, 7), sharex=True, constrained_layout=True)
    for ax, strategy in zip(axes, ("conditional", "permanent")):
        for scenario in COMPARATORS:
            rows = [
                r
                for r in tables["diario_carteras"]
                if r["strategy"] == strategy and r["scenario"] == scenario
            ]
            if rows:
                ax.plot(
                    [datetime.fromisoformat(r["date"]) for r in rows],
                    [float(r["equity_usdt"]) for r in rows],
                    label=scenario,
                    color=colors[scenario],
                    lw=1.2,
                )
        ax.set(title=f"Cartera {strategy}", ylabel="Equity (USDT)")
        ax.grid(alpha=0.18)
    axes[0].legend(fontsize=7, ncol=3)
    axes[-1].set_xlabel("Fecha UTC; trayectoria continua")
    for extension in ("png", "svg"):
        fig.savefig(destination / f"equity.{extension}", dpi=220)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(10.5, 4), constrained_layout=True)
    rows = [
        r
        for r in tables["deltas"]
        if r["period"] == "full" and r["metric"] == "final_equity_usdt" and r["delta"] is not None
    ]
    ax.bar(
        range(len(rows)),
        [float(r["delta"]) for r in rows],
        color=[colors[r["scenario"]] for r in rows],
    )
    ax.set_xticks(
        range(len(rows)),
        [r["scenario"].replace("_", "\n") + "\n" + r["strategy"] for r in rows],
        fontsize=7,
    )
    ax.axhline(0, color="black", lw=0.7)
    ax.set(
        ylabel="Cambio de equity final (USDT)",
        title="Comparador: BASE para REALIZADA/MARGEN; REALIZADA para DECISION",
    )
    ax.grid(axis="y", alpha=0.18)
    for extension in ("png", "svg"):
        fig.savefig(destination / f"deltas.{extension}", dpi=220)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(10.5, 4), constrained_layout=True)
    for i, scenario in enumerate(COMPARATORS):
        rows = [
            r
            for r in tables["h3_regimen"]
            if r["strategy"] == "conditional"
            and r["scenario"] == scenario
            and r["period"] in {"2022-2023", "2024+"}
        ]
        for j, row in enumerate(rows):
            if row["opportunity_mean"] is not None:
                ax.bar(
                    i + (j - 0.5) * 0.35,
                    float(row["opportunity_mean"]) * 10000,
                    width=0.32,
                    color=colors[scenario],
                    alpha=0.5 if j == 0 else 1,
                    label=row["period"] if i == 0 else None,
                    hatch="//" if j == 0 else None,
                )
    ax.set_xticks(range(len(COMPARATORS)), [s.replace("_", "\n") for s in COMPARATORS], fontsize=8)
    ax.set(
        ylabel="Forecast bruto elegible, media (pb)", title="H3: todos los minutos, BTC/ETH 50/50"
    )
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1), borderaxespad=0)
    ax.grid(axis="y", alpha=0.18)
    for extension in ("png", "svg"):
        fig.savefig(destination / f"h3.{extension}", dpi=220)
    plt.close(fig)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument(
        "--seal", action="store_true", help="Seal existing final files only; do not rebuild"
    )
    parser.add_argument("--no-figures", action="store_true")
    args = parser.parse_args(argv)
    if args.seal:
        manifest = seal_package(args.package)
        result = dict(status="sealed", members=len(manifest["members"]))
    else:
        result = build_report(args.package, figures=not args.no_figures)
    sys.stdout.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
