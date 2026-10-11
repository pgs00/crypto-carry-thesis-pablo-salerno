"""Compact risk tables derived from the complete reconstructed local series."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

if __package__:
    from .build_intraday_risk import load_runs, write_csv, write_json
    from .intraday_risk_math import drawdown_summary
    from .intraday_risk_sources import DAY, SECOND, SYMBOLS, iso, read_csv, utc_ns
else:
    from build_intraday_risk import load_runs, write_csv, write_json
    from intraday_risk_math import drawdown_summary
    from intraday_risk_sources import DAY, SECOND, SYMBOLS, iso, read_csv, utc_ns


def compare_drawdowns(times, equity, daily_times, daily_equity, initial, initial_time,
                      *, daily_initial=None, daily_initial_time=None):
    """Same endpoints and causal daily subset; separate peaks may precede a cut."""
    daily_times = np.asarray(daily_times, dtype=np.int64)
    ix = np.searchsorted(times, daily_times, side="right") - 1
    if (np.any(ix < 0) or np.any(times[ix] != daily_times)
            or not np.all(np.isfinite(equity[ix])) or not np.all(np.isfinite(daily_equity))
            or np.any(np.abs(equity[ix] - daily_equity) > 1e-8)):
        raise ValueError("daily timestamps or values are not nested in intraday series")
    intraday = drawdown_summary(times, equity, initial, initial_time)
    daily = drawdown_summary(daily_times, daily_equity,
                             initial if daily_initial is None else daily_initial,
                             initial_time if daily_initial_time is None else daily_initial_time)
    if intraday["complete"] and daily["complete"] and intraday["drawdown"] > daily["drawdown"] + 1e-12:
        raise ValueError("daily drawdown exceeds nested intraday drawdown")
    output = {}
    for label, result in (("daily", daily), ("intraday", intraday)):
        for key in ("drawdown", "loss_usdt", "peak_time_ns", "trough_time_ns", "recovery_time_ns",
                    "peak_equity", "trough_equity", "complete", "missing_observations", "reason"):
            output[f"{label}_{key}"] = result[key]
        for key in ("peak", "trough", "recovery"):
            output[f"{label}_{key}_utc"] = iso(result[f"{key}_time_ns"])
    output.update(extra_drawdown_pp=100 * (daily["drawdown"] - intraday["drawdown"]),
                  extra_peak_to_trough_loss_usdt=intraday["loss_usdt"] - daily["loss_usdt"],
                  daily_zero_dd=daily["drawdown"] == 0, nested_daily_check=True)
    return output


def group_incidents(intervals, events):
    """Merge adjacent active uncovered states only within the same asset and cycle."""
    cycles = defaultdict(list)
    for event in events:
        if event.get("cycle_id"):
            cycles[event["symbol"]].append((int(event["time_ns"]), event["cycle_id"]))
    output = []
    for symbol in SYMBOLS:
        points = sorted(cycles[symbol], key=lambda item: item[0])
        active = [row for row in intervals if row["symbol"] == symbol and row["exposure"] == "unhedged"]
        current = None
        for row in active:
            lower, upper = int(row["start_ns"]), int(row["end_ns"])
            prior = [cycle for time, cycle in points if time <= lower]
            cycle = prior[-1] if prior else "unrecorded"
            if current and current["end_ns"] == lower and current["cycle_id"] == cycle:
                current["end_ns"] = upper
                current["states"].add(row["state"])
            else:
                current = dict(symbol=symbol, start_ns=lower, end_ns=upper, cycle_id=cycle,
                               states={row["state"]})
                output.append(current)
    for row in output:
        row["states"] = ";".join(sorted(row["states"]))
    return sorted(output, key=lambda row: (row["start_ns"], row["symbol"]))


def arrays(table):
    return {key: table[key].combine_chunks().to_numpy(zero_copy_only=False) for key in table.column_names}


def identify_evidence(table, column, identity):
    """The source identity has the same string schema even in zero-event blocks."""
    return table.append_column(column, pa.array([identity] * len(table), type=pa.string()))


def incident_exposure_mask(values, symbol, end_ns):
    """Active interval plus its pre-close price, never the newly hedged/dust state.

    Simultaneous movements on another asset still precede this asset's closure.
    Closing account outcome is retained separately using the final post-state.
    """
    times = values["time_ns"]
    selected = times < end_ns
    before = np.flatnonzero(selected)
    if not len(before):
        raise ValueError("Incident has no observation before its exclusive end")
    last = int(before[-1])
    end_rows = np.flatnonzero(times == end_ns)
    for index in end_rows:
        if values["phase"][index] == 0:
            break
        if any(values[f"{symbol}_{key}"][index] != values[f"{symbol}_{key}"][last]
               for key in ("spot", "short")):
            break
        selected[index] = True
    return selected


def classify_incident(episode, events, orders, fills):
    """Describe documented execution states; elapsed minutes alone are not a cause."""
    lower, upper, symbol = episode["start_ns"], episode["end_ns"], episode["symbol"]
    if lower < utc_ns("2023-03-24T14:01:00Z") and upper > utc_ns("2023-03-24T11:28:00Z"):
        return "documented_spot_interruption"
    matching_fills = [row for row in fills if row["symbol"] == symbol
                      and lower <= int(row["time_ns"]) <= upper]
    if any(row.get("partial") is True for row in matching_fills):
        return "partial_fill_or_unwind"
    states = episode["states"]
    if "CORRECT" in states:
        return "hedge_correction"
    failed = any(row.get("kind") == "attempt_failed" for row in events)
    if "OPENING" in states:
        return "opening_with_failed_attempt" if failed else "sequential_opening"
    if "REBALANC" in states:
        return "rebalance_with_failed_attempt" if failed else "sequential_rebalance"
    if "CLOSING" in states:
        submitted = [row for row in orders if row["symbol"] == symbol
                     and lower <= int(row["time_ns"]) <= upper and row.get("action") == "submitted"
                     and row.get("purpose") in {"close_spot", "reduce_spot", "close_futures", "reduce_futures"}
                     and row.get("window_end") is not None]
        expected = min((int(row["window_end"]) for row in submitted), default=None)
        if failed or (expected is not None and upper > expected):
            return "close_retry_or_delay"
        return "sequential_close" if expected is not None else "closing_cause_not_attributable"
    return "unhedged_cause_not_attributable"


def point(values, index, identity, label):
    fields = ["time_ns", "sequence", "phase", "equity_usdt", "equity_proxy_usdt", "free_cash_usdt",
              "redistributable_cash_usdt", "maintenance_need_joint_usdt",
              "preventive_need_joint_infimum_usdt", "preventive_joint_strict",
              "maintenance_external_deficit_usdt", "preventive_external_deficit_usdt",
              "preventive_external_lower_bound_usdt", "preventive_external_upper_bound_usdt",
              "reservations_available_known", "reservations_reason"]
    fields += [f"{symbol}_{key}" for symbol in SYMBOLS for key in (
        "spot", "short", "average", "collateral", "spot_price", "mark_price", "spot_age_ns",
        "mark_age_ns", "mark_estimated", "spot_proxy", "proxy_active", "asset_pnl_usdt",
        "net_exposure_usdt", "maintenance_usdt", "margin_balance_usdt", "headroom_usdt",
        "margin_ratio", "liquidation_price", "liquidation_distance", "preventive_topup_infimum_usdt",
    )]
    row = dict(identity, label=label)
    for key in fields:
        value = values[key][index]
        row[key] = value.item() if hasattr(value, "item") else value
    row["timestamp_utc"] = iso(row["time_ns"])
    return row


def window(entries, root, lower, upper, columns=None):
    chunks = []
    for entry in entries:
        if entry["start_ns"] <= upper and entry["end_exclusive_ns"] > lower:
            table = pq.ParquetFile(Path(root) / entry["path"]).read(columns=columns)
            times = table["time_ns"].to_numpy()
            chunks.append(table.filter(pa.array((times >= lower) & (times <= upper))))
    if not chunks:
        raise ValueError("Requested risk window is outside reconstructed coverage")
    return pa.concat_tables(chunks)


def daily_block(values, lower, upper, identity):
    """Daily diagnostics and per-asset maintenance, with duration from exact clocks."""
    times = values["time_ns"]
    days = times // DAY
    daily, margin, extrema = [], [], []
    for day in np.unique(days):
        first, last = np.searchsorted(days, day, side="left"), np.searchsorted(days, day, side="right")
        ts, eq = times[first:last], values["equity_usdt"][first:last]
        weights = np.diff(np.r_[ts, min((int(day) + 1) * DAY, upper)]) / SECOND
        initial = float(eq[0])
        dd = drawdown_summary(ts, eq, initial, int(ts[0]))
        minimum = int(np.argmin(eq)) + first
        row = dict(identity, day_ns=int(day) * DAY, date=iso(int(day) * DAY)[:10],
            day_open_equity_usdt=initial, minimum_equity_usdt=float(eq.min()),
            minimum_equity_utc=iso(times[minimum]),
            drop_from_day_open_usdt=float(eq.min())-initial,
            drop_from_day_open_fraction=float(eq.min()/initial-1) if initial > 0 else None,
            within_day_peak_drawdown=dd["drawdown"], within_day_peak_loss_usdt=dd["loss_usdt"],
            observations=len(ts), unknown_equity=int(np.count_nonzero(~np.isfinite(eq))),
            maximum_maintenance_need_joint_usdt=float(np.nanmax(values["maintenance_need_joint_usdt"][first:last])),
            maximum_preventive_need_joint_infimum_usdt=float(np.nanmax(values["preventive_need_joint_infimum_usdt"][first:last])),
            maximum_external_lower_bound_usdt=float(np.nanmax(values["preventive_external_lower_bound_usdt"][first:last])),
            maximum_external_upper_bound_usdt=float(np.nanmax(values["preventive_external_upper_bound_usdt"][first:last])),
            unknown_redistributable_observations=int(np.count_nonzero(~values["reservations_available_known"][first:last])),
            unknown_redistributable_seconds=float(weights[~values["reservations_available_known"][first:last]].sum()),
            maximum_proxy_difference_usdt=float(np.nanmax(np.abs(values["equity_proxy_usdt"][first:last]-eq))))
        daily.append(row)
        for symbol in SYMBOLS:
            q = values[f"{symbol}_short"][first:last]
            active = q > 0
            mask = np.flatnonzero(active) + first
            item = dict(identity, date=row["date"], day_ns=row["day_ns"], symbol=symbol,
                short_seconds=float(weights[active].sum()), active_observations=int(active.sum()),
                minimum_headroom_usdt=None, minimum_headroom_time_ns=None,
                maximum_maintenance_usdt=0., maximum_ratio=None, minimum_liquidation_distance=None,
                maximum_preventive_topup_infimum_usdt=0., minimum_margin_balance_usdt=None,
                maximum_collateral_usdt=0., maximum_notional_usdt=0.,
                spot_carried_observations=int(np.count_nonzero(values[f"{symbol}_spot_age_ns"][first:last] >= 60*SECOND)),
                estimated_mark_observations=int(np.count_nonzero(values[f"{symbol}_mark_estimated"][first:last] == 1)))
            if len(mask):
                headroom = values[f"{symbol}_headroom_usdt"][mask]
                selected = int(mask[np.nanargmin(headroom)])
                item.update(minimum_headroom_usdt=float(np.nanmin(headroom)),
                    minimum_headroom_time_ns=int(times[selected]),
                    maximum_maintenance_usdt=float(np.nanmax(values[f"{symbol}_maintenance_usdt"][mask])),
                    maximum_ratio=float(np.nanmax(values[f"{symbol}_margin_ratio"][mask])),
                    minimum_liquidation_distance=float(np.nanmin(values[f"{symbol}_liquidation_distance"][mask])),
                    maximum_preventive_topup_infimum_usdt=float(np.nanmax(values[f"{symbol}_preventive_topup_infimum_usdt"][mask])),
                    minimum_margin_balance_usdt=float(np.nanmin(values[f"{symbol}_margin_balance_usdt"][mask])),
                    maximum_collateral_usdt=float(np.nanmax(values[f"{symbol}_collateral"][mask])),
                    maximum_notional_usdt=float(np.nanmax(values[f"{symbol}_notional_usdt"][mask])))
                extrema.append(point(values, selected, identity, "daily_min_headroom_" + symbol))
            margin.append(item)
    return daily, margin, extrema


def build_tables(package, series_root, parent, correction):
    package, series_root = Path(package), Path(series_root)
    meta = json.loads((package / "series_locales.json").read_text(encoding="utf-8"))
    original = read_csv(Path(correction) / "comparacion/metricas_cartera_periodo.csv")
    all_dd, all_daily, all_margin, all_points, all_episodes = [], [], [], [], []
    financial_chunks, episode_chunks, march_chunks = [], [], []
    periods_margin, reused = [], []
    for run in load_runs(parent):
        identity = run["identity"]
        fills = pq.ParquetFile(run["path"] / "fills.parquet").read().to_pylist()
        entries = [item for item in meta["entries"] if item["run_id"] == identity["run_id"]]
        equity_chunks = []
        run_daily, run_margin, run_points = [], [], []
        for entry in entries:
            table = pq.ParquetFile(series_root / entry["path"]).read()
            values = arrays(table)
            daily, margin, points = daily_block(values, entry["start_ns"], entry["end_exclusive_ns"], identity)
            run_daily.extend(daily)
            run_margin.extend(margin)
            run_points.extend(points)
            equity_chunks.append(table.select(["time_ns", "equity_usdt", "equity_proxy_usdt"]))
            financial = table.filter(pa.array(values["phase"] != 0))
            financial = identify_evidence(financial, "run_id", identity["run_id"])
            financial_chunks.append(financial)
        eq = arrays(pa.concat_tables(equity_chunks))
        times, equities = eq["time_ns"], eq["equity_usdt"]
        d_times = np.array([int(row["time_ns"]) for row in run["daily"]])
        d_equity = np.array([float(row["equity"]) for row in run["daily"]])
        source_periods = [row for row in original if row["run_id"] == identity["run_id"]]
        for period in source_periods:
            reused.append(period)
            lower, upper = utc_ns(period["start_utc"]), utc_ns(period["end_exclusive_utc"])
            select, dselect = (times >= lower) & (times < upper), (d_times >= lower) & (d_times < upper)
            for policy in ("period_reset", "full_trajectory_peak"):
                initial = float(period["starting_equity_usdt"])
                initial_time = lower if lower == utc_ns(run["config"]["start"]) else lower-1
                di, dit = initial, initial_time
                if policy == "full_trajectory_peak":
                    for t, e, daily_flag in ((times, equities, False), (d_times, d_equity, True)):
                        previous = np.flatnonzero((t < lower) & (e > 10000.))
                        ix = int(previous[np.argmax(e[previous])]) if len(previous) else None
                        peak, peak_time = (float(e[ix]), int(t[ix])) if ix is not None else (10000., utc_ns("2022-01-01T00:00:00Z"))
                        if daily_flag:
                            di, dit = peak, peak_time
                        else:
                            initial, initial_time = peak, peak_time
                result = compare_drawdowns(times[select], equities[select], d_times[dselect],
                    d_equity[dselect], initial, initial_time, daily_initial=di, daily_initial_time=dit)
                all_dd.append(dict(identity, period=period["period"], peak_policy=policy,
                    start_utc=period["start_utc"], end_exclusive_utc=period["end_exclusive_utc"],
                    valuation="original_reconstructed", price_coverage="original_with_documented_carry_and_estimates",
                    **result))
                proxy_equity = eq["equity_proxy_usdt"]
                proxy_initial, proxy_initial_time = initial, initial_time
                if policy == "full_trajectory_peak":
                    previous = np.flatnonzero((times < lower) & (proxy_equity > 10000.))
                    ix = int(previous[np.argmax(proxy_equity[previous])]) if len(previous) else None
                    proxy_initial, proxy_initial_time = ((float(proxy_equity[ix]), int(times[ix]))
                        if ix is not None else (10000., utc_ns("2022-01-01T00:00:00Z")))
                proxy_result = compare_drawdowns(times[select], proxy_equity[select], d_times[dselect],
                    d_equity[dselect], proxy_initial, proxy_initial_time, daily_initial=di,
                    daily_initial_time=dit)
                all_dd.append(dict(identity, period=period["period"], peak_policy=policy,
                    start_utc=period["start_utc"], end_exclusive_utc=period["end_exclusive_utc"],
                    valuation="valoracion_proxy_hipotetica", price_coverage="causal_fixed_anchor_only_during_suspension",
                    **proxy_result))
            selected_days = [row for row in run_daily if lower <= row["day_ns"] < upper]
            selected_margin = [row for row in run_margin if lower <= row["day_ns"] < upper and row["active_observations"]]
            item = dict(identity, period=period["period"],
                min_headroom_usdt=min((r["minimum_headroom_usdt"] for r in selected_margin), default=None),
                min_margin_balance_usdt=min((r["minimum_margin_balance_usdt"] for r in selected_margin), default=None),
                max_contract_maintenance_usdt=max((r["maximum_maintenance_usdt"] for r in selected_margin), default=0),
                max_margin_ratio=max((r["maximum_ratio"] for r in selected_margin), default=None),
                min_liquidation_distance=min((r["minimum_liquidation_distance"] for r in selected_margin), default=None),
                max_joint_maintenance_need_usdt=max(r["maximum_maintenance_need_joint_usdt"] for r in selected_days),
                max_joint_preventive_need_infimum_usdt=max(r["maximum_preventive_need_joint_infimum_usdt"] for r in selected_days),
                max_external_lower_bound_usdt=max(r["maximum_external_lower_bound_usdt"] for r in selected_days),
                max_external_upper_bound_usdt=max(r["maximum_external_upper_bound_usdt"] for r in selected_days),
                unknown_redistributable_seconds=sum(r["unknown_redistributable_seconds"] for r in selected_days),
                max_loss_from_day_open_usdt=-min(r["drop_from_day_open_usdt"] for r in selected_days),
                max_within_day_peak_loss_usdt=max(r["within_day_peak_loss_usdt"] for r in selected_days))
            periods_margin.append(item)
        for n, episode in enumerate(group_incidents(run["intervals"], run["events"]), 1):
            lower, upper, symbol = episode["start_ns"], episode["end_ns"], episode["symbol"]
            detail = window(entries, series_root, lower, upper)
            v = arrays(detail)
            begin = int(np.searchsorted(v["time_ns"], lower, side="right") - 1)
            detail = detail.slice(begin)
            v = arrays(detail)
            episode_id = f"{identity['run_id']}_{symbol}_{n:03d}"
            episode_chunks.append(identify_evidence(detail, "episode_id", episode_id))
            daily_events = [event for event in run["events"] if event["symbol"] == symbol
                            and lower - 180*SECOND <= int(event["time_ns"]) <= upper]
            orders = sorted({event["order_id"] for event in daily_events if event.get("order_id")})
            causes = sorted({event["cause"] for event in daily_events if event.get("cause")})
            duration = (upper-lower)/SECOND
            classification = classify_incident(episode, daily_events, run["orders"], fills)
            start_eq, finish_eq = float(v["equity_usdt"][0]), float(v["equity_usdt"][-1])
            asset = v[f"{symbol}_asset_pnl_usdt"]
            active = incident_exposure_mask(v, symbol, upper)
            all_episodes.append(dict(identity, episode_id=episode_id, **episode,
                start_utc=iso(lower), end_exclusive_utc=iso(upper), seconds=duration,
                classification=classification, order_ids=";".join(orders), causes=";".join(causes),
                maximum_spot_quantity=float(np.max(v[f"{symbol}_spot"][active])),
                maximum_short_quantity=float(np.max(v[f"{symbol}_short"][active])),
                maximum_signed_net_exposure_usdt=float(np.max(v[f"{symbol}_net_exposure_usdt"][active])),
                minimum_signed_net_exposure_usdt=float(np.min(v[f"{symbol}_net_exposure_usdt"][active])),
                maximum_absolute_net_exposure_usdt=float(np.max(np.abs(v[f"{symbol}_net_exposure_usdt"][active]))),
                start_post_equity_usdt=start_eq, end_post_equity_usdt=finish_eq,
                portfolio_change_usdt=finish_eq-start_eq,
                worst_portfolio_change_usdt=float(np.min(v["equity_usdt"][active])-start_eq),
                asset_change_usdt=float(asset[-1]-asset[0]),
                worst_asset_change_usdt=float(np.min(asset[active])-asset[0]),
                worst_proxy_portfolio_change_usdt=float(np.min(v["equity_proxy_usdt"][active])-v["equity_proxy_usdt"][0]),
                maximum_spot_age_seconds=float(np.max(v[f"{symbol}_spot_age_ns"][active])/SECOND),
                attribution="asset_inventory_plus_assigned_cash_changes; contemporaneous_not_causal"))
        march = window(entries, series_root, utc_ns("2023-03-23T00:00:00Z"), utc_ns("2023-03-26T00:00:00Z")-1)
        march_chunks.append(identify_evidence(march, "run_id", identity["run_id"]))
        full = next(r for r in all_dd if r["run_id"] == identity["run_id"]
                    and r["period"] == "full" and r["peak_policy"] == "period_reset"
                    and r["valuation"] == "original_reconstructed")
        for label, time_key in (("worst_equity_drawdown", "intraday_trough_time_ns"),):
            t = full[time_key]
            detail = arrays(window(entries, series_root, t, t))
            ix = int(np.argmin(detail["equity_usdt"]))
            all_points.append(point(detail, ix, identity, label))
        if run_points:
            for symbol in SYMBOLS:
                rows = [r for r in run_points if r["label"].endswith(symbol)]
                selected = min(rows, key=lambda r: r[f"{symbol}_headroom_usdt"])
                all_points.append(dict(selected, label="full_min_headroom_" + symbol))
        all_daily.extend(run_daily)
        all_margin.extend(run_margin)
        print(identity["run_id"] + ": tables complete", flush=True)
    tables = package / "tablas"
    for name, rows in (("drawdown_comparativo", all_dd), ("riesgo_diario", all_daily),
                       ("garantias_diarias_activo", all_margin), ("garantias_periodo", periods_margin),
                       ("catalogo_incidentes", all_episodes), ("puntos_extremos", all_points),
                       ("metricas_reutilizadas", reused)):
        write_csv(tables / (name + ".csv"), rows)
    evidence = package / "evidencia"
    evidence.mkdir(exist_ok=True)
    for name, chunks in (("eventos_financieros", financial_chunks), ("episodios", episode_chunks),
                         ("marzo_2023", march_chunks)):
        pq.write_table(pa.concat_tables(chunks), evidence / (name + ".parquet"), compression="zstd")
    for name in ("h1_resumen.csv", "h1_invariancia.csv", "h2.csv", "h3_regimen.csv", "h3_invariancia.csv"):
        (tables / name).write_bytes((Path(correction) / "comparacion" / name).read_bytes())
    write_json(package / "tablas_procedencia.json", dict(
        status="postprocessed", engine_replay=False,
        source_run_ids=list(dict.fromkeys(r["run_id"] for r in meta["entries"])),
        daily_risk_rows=len(all_daily), margin_daily_asset_rows=len(all_margin), incidents=len(all_episodes),
        drawdown_rows=len(all_dd), attribution="fixed persisted positions and cash changes, not causal incident estimates"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("package", "series-root", "parent", "correction"):
        parser.add_argument("--"+name, required=True, type=Path)
    args = parser.parse_args()
    build_tables(args.package, args.series_root, args.parent, args.correction)


if __name__ == "__main__":
    main()
