"""Reconstruct fixed published portfolios from local records; never run an engine."""

from __future__ import annotations

import argparse
import csv
import json
import time
import tomllib
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

if __package__:
    from . import intraday_risk_math as risk
    from .intraday_risk_sources import (
        ACCOUNT,
        POSITION,
        SYMBOLS,
        LocalPrices,
        account_history,
        iso,
        observation_grid,
        price_at,
        read_csv,
        read_parquet,
        reconcile_daily,
        sha256,
        utc_ns,
    )
    from .rules_sensitivity_exposure import exposure_intervals
else:
    import intraday_risk_math as risk
    from intraday_risk_sources import (
        ACCOUNT,
        POSITION,
        SYMBOLS,
        LocalPrices,
        account_history,
        iso,
        observation_grid,
        price_at,
        read_csv,
        read_parquet,
        reconcile_daily,
        sha256,
        utc_ns,
    )
    from rules_sensitivity_exposure import exposure_intervals


def write_csv(path, rows):
    rows = list(rows)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    names = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, names, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False, default=str) + "\n",
                          encoding="utf-8")


def value_grid(history, grid, prices, tiers, *, ratio_limit=.5, distance_limit=.15):
    """Value immutable states on minute/event union, retaining original and proxy."""
    times, state_index = grid["time_ns"], grid["state_index"]
    states = {key: history[key][state_index] for key in (*ACCOUNT, *POSITION, "asset_cash")}
    output = dict(grid)
    output.update({f"{key}_usdt": states[key] for key in ACCOUNT})
    spot_prices, mark_prices, proxy_prices, requirements, topups = [], [], [], [], []
    strict = []
    anchor_time = utc_ns("2023-03-24T11:28:00Z")
    resume_time = utc_ns("2023-03-24T14:01:00Z")
    for j, symbol in enumerate(SYMBOLS):
        references = {}
        for label in ("spot", "mark", "futures"):
            selected = price_at(prices[symbol, label], times, require_volume=label != "mark")
            references[label] = selected
            for key, values in selected.items():
                output[f"{symbol}_{label}_{key}"] = values
        spot, mark = references["spot"]["price"], references["mark"]["price"]
        proxy = spot.copy()
        proxy_active = ((times > anchor_time) & (times < resume_time)
                        & (references["spot"]["available_at"] == anchor_time))
        if np.any(proxy_active):
            anchors = {label: price_at(prices[symbol, label], np.array([anchor_time]),
                                      require_volume=True) for label in ("spot", "futures")}
            aligned = anchors["spot"]["available_at"][0] == anchors["futures"]["available_at"][0]
            if not aligned:
                proxy[proxy_active] = np.nan
            else:
                alternative = risk.causal_spot_proxy(
                    anchors["spot"]["price"][0], anchors["futures"]["price"][0],
                    references["futures"]["price"], anchor_time,
                    references["futures"]["available_at"], times,
                )
                proxy[proxy_active] = alternative["price"][proxy_active]
        output[f"{symbol}_spot_proxy"] = proxy
        output[f"{symbol}_proxy_active"] = proxy_active
        spot_prices.append(spot)
        mark_prices.append(mark)
        proxy_prices.append(proxy)
        q, avg, collateral = (states[key][:, j] for key in ("short", "average", "collateral"))
        for key in POSITION:
            output[f"{symbol}_{key}"] = states[key][:, j]
        margin = risk.short_margin(q, avg, collateral, mark, 0., 0.)
        maintenance = risk.maintenance_requirement(q, mark, tiers[symbol])
        balance = margin["margin_balance"]
        ratio = np.divide(maintenance, balance, out=np.full(len(times), np.nan),
                          where=(q > 0) & (balance > 0))
        liquidation = risk.liquidation_distance(q, avg, collateral, mark, tiers[symbol])
        preventive = risk.preventive_topup(q, avg, collateral, mark, tiers[symbol],
                                           ratio_limit=ratio_limit, distance_limit=distance_limit)
        output[f"{symbol}_notional_usdt"] = q * mark
        output[f"{symbol}_margin_balance_usdt"] = balance
        output[f"{symbol}_maintenance_usdt"] = maintenance
        output[f"{symbol}_headroom_usdt"] = balance - maintenance
        output[f"{symbol}_margin_ratio"] = ratio
        output[f"{symbol}_liquidation_price"] = liquidation["liquidation_price"]
        output[f"{symbol}_liquidation_distance"] = liquidation["distance"]
        output[f"{symbol}_preventive_topup_infimum_usdt"] = preventive["topup_infimum"]
        output[f"{symbol}_preventive_topup_strict"] = preventive["strict_boundary"]
        output[f"{symbol}_maintenance_shortfall_usdt"] = np.where(
            q > 0, np.maximum(0, maintenance - balance), 0.)
        output[f"{symbol}_net_exposure_usdt"] = states["spot"][:, j] * spot - q * mark
        output[f"{symbol}_asset_pnl_usdt"] = (states["asset_cash"][:, j] + collateral
            + np.where(states["spot"][:, j] == 0, 0., states["spot"][:, j] * spot)
            + np.where(q == 0, 0., q * (avg - mark)))
        requirements.append(output[f"{symbol}_maintenance_shortfall_usdt"])
        topups.append(preventive["topup_infimum"])
        strict.append(preventive["strict_boundary"])
    arguments = [states[key] for key in (*ACCOUNT, *POSITION)]
    # equity_value takes quantity matrices with symbols on the final axis.
    output["equity_usdt"] = risk.equity_value(*arguments, np.column_stack(spot_prices),
                                             np.column_stack(mark_prices))
    output["equity_proxy_usdt"] = risk.equity_value(*arguments, np.column_stack(proxy_prices),
                                                   np.column_stack(mark_prices))
    output["free_cash_usdt"] = states["free_spot"] + states["free_futures"]
    output["maintenance_need_joint_usdt"] = np.sum(np.column_stack(requirements), axis=1)
    output["preventive_need_joint_infimum_usdt"] = np.sum(np.column_stack(topups), axis=1)
    output["preventive_joint_strict"] = np.any(np.column_stack(strict), axis=1)
    return output


def load_runs(parent):
    index = json.loads((Path(parent) / "indice_corridas.json").read_text(encoding="utf-8"))
    output = []
    for record in index["runs"]:
        if record["scenario"] not in {"BASE_E3", "MARGEN_2X"}:
            continue
        path = Path(parent) / "corridas" / record["run_id"]
        config = tomllib.loads((path / "effective_config.toml").read_text(encoding="utf-8"))
        assumptions = json.loads((path / "research_assumptions.json").read_text(encoding="utf-8"))
        ledger = read_parquet(path / "ledger.parquet")
        positions = read_parquet(path / "positions.parquet")
        start, end = utc_ns(config["start"]), utc_ns(config["end"])
        output.append(dict(identity={k: record[k] for k in ("scenario", "strategy", "run_id")},
            path=path, config=config, history=account_history(ledger, config["capital"]),
            daily=read_csv(path / "equity_daily.csv"),
            tiers={row["symbol"]: row["values"]["tiers"] for row in assumptions["rules"]
                   if row["market"] == "futures"},
            intervals=exposure_intervals(positions, start, end, config["hedge_tolerance"]),
            events=read_parquet(path / "risk_events.parquet"),
            orders=read_parquet(path / "orders.parquet"), ledger=ledger))
    if len(output) != 4:
        raise ValueError("Expected two BASE and two MARGEN_2X preserved portfolios")
    return output


def block_ranges(start, end):
    cursor = start
    while cursor < end:
        value = datetime.fromtimestamp(cursor / 1e9, UTC)
        year, month = (value.year + 1, 1) if value.month == 12 else (value.year, value.month + 1)
        following = int(datetime(year, month, 1, tzinfo=UTC).timestamp()) * 1_000_000_000
        upper = min(end, following)
        yield value.strftime("%Y-%m"), cursor, upper
        cursor = upper


def add_liquidity(output, run):
    if __package__:
        from .intraday_risk_reservations import reservation_grid
    else:
        from intraday_risk_reservations import reservation_grid
    times = output["time_ns"]
    phases = np.full(len(times), "post", dtype="U12")
    phases[output["phase"] == 1] = "pre"
    intermediate = (output["phase"][:-1] == 2) & (times[:-1] == times[1:])
    phases[np.flatnonzero(intermediate)] = "intermediate"
    reservation = reservation_grid(run["path"], times, phases=phases)
    for key in ("reserved_cash", "available_known", "pending_orders_count", "reason"):
        output[f"reservations_{key}"] = reservation[key]
    known = reservation["available_known"]
    cash = np.maximum(0., output["free_cash_usdt"] - output["debt_usdt"])
    output["redistributable_cash_usdt"] = np.where(
        known, np.maximum(0., cash - reservation["reserved_cash"]), np.nan)
    for prefix, need_key in (("maintenance", "maintenance_need_joint_usdt"),
                             ("preventive", "preventive_need_joint_infimum_usdt")):
        needs = output[need_key]
        output[f"{prefix}_external_deficit_usdt"] = np.where(
            needs == 0, 0., np.maximum(0, needs - output["redistributable_cash_usdt"]))
        output[f"{prefix}_external_lower_bound_usdt"] = np.maximum(0, needs - cash)
        output[f"{prefix}_external_upper_bound_usdt"] = np.where(
            known, output[f"{prefix}_external_deficit_usdt"], needs)


def reconstruct(parent, output, series_root, data_root, *, start=None, end=None):
    """Write a NEW product; a pilot uses explicit narrower bounds and its own paths."""
    output, series_root = Path(output), Path(series_root)
    for path in (output, series_root):
        if path.exists() and any(path.iterdir()):
            raise ValueError(f"Destination must be new or empty: {path}")
    output.mkdir(parents=True, exist_ok=True)
    series_root.mkdir(parents=True, exist_ok=True)
    begun = time.perf_counter()
    runs, prices = load_runs(parent), LocalPrices(data_root)
    start_ns = utc_ns(start or runs[0]["config"]["start"])
    end_ns = utc_ns(end or runs[0]["config"]["end"])
    reconciliations, series_manifest, timings = [], [], []
    for month, lower, upper in block_ranges(start_ns, end_ns):
        block_begun = time.perf_counter()
        price_block = prices.block(month)
        for run in runs:
            identity = run["identity"]
            daily = [row for row in run["daily"] if lower <= int(row["time_ns"]) < upper]
            extra = [int(row["time_ns"]) for row in run["events"] + run["orders"]
                     if lower <= int(row["time_ns"]) < upper]
            grid = observation_grid(lower, upper, run["history"],
                                    [int(row["time_ns"]) for row in daily], extra_times=extra)
            values = value_grid(run["history"], grid, price_block, run["tiers"],
                               ratio_limit=float(run["config"]["margin_exit_ratio"]),
                               distance_limit=float(run["config"]["liquidation_distance"]))
            reconciliations.extend(dict(identity, **row) for row in reconcile_daily(
                daily, values["time_ns"], values["equity_usdt"],
                float(run["config"]["accounting_tolerance"])))
            add_liquidity(values, run)
            path = series_root / identity["run_id"] / f"{month}.parquet"
            path.parent.mkdir(parents=True, exist_ok=True)
            table = pa.table(values)
            metadata = dict(run_id=identity["run_id"], valuation="original_plus_separate_hypothetical_proxy",
                            grid="closed_minute_union_financial_events_and_original_daily_timestamps",
                            phase="0=regular;1=pre_first_ledger;2=post_each_ledger;ties_use_sequence",
                            numeric="float64_bulk;Decimal_source;daily_tolerance_1E-8_USDT")
            table = table.replace_schema_metadata({k.encode(): v.encode() for k, v in metadata.items()})
            pq.write_table(table, path, compression="zstd", row_group_size=65536)
            series_manifest.append(dict(identity, path=path.relative_to(series_root).as_posix(),
                sha256=sha256(path), bytes=path.stat().st_size, rows=len(table),
                start_ns=lower, end_exclusive_ns=upper))
        timings.append(dict(month=month, seconds=time.perf_counter()-block_begun))
        print(json.dumps(timings[-1]), flush=True)
    write_csv(output / "tablas/conciliaciones_diarias.csv", reconciliations)
    write_csv(output / "tablas/intervalos_exposicion_reutilizados.csv",
              [dict(run["identity"], **row) for run in runs for row in run["intervals"]])
    write_json(output / "series_locales.json", dict(root_recorded=str(series_root.resolve()),
        entries=series_manifest, full_series_in_compact_package=False))
    write_json(output / "fuentes_precios.json", dict(manifest_path=str(prices.manifest_path),
        manifest_sha256=sha256(prices.manifest_path), entries=prices.entries))
    write_json(output / "reconstruccion.json", dict(
        status="reconstructed_and_daily_reconciled", engine_replay=False,
        created_at_utc=datetime.now(UTC).isoformat(), parent_recorded=str(Path(parent).resolve()),
        start_ns=start_ns, end_exclusive_ns=end_ns, start_utc=iso(start_ns),
        end_exclusive_utc=iso(end_ns), elapsed_seconds=time.perf_counter()-begun,
        rows=sum(row["rows"] for row in series_manifest),
        daily_reconciliations=len(reconciliations), blocks=timings,
        maximum_daily_residual_usdt=max(abs(row["residual_usdt"]) for row in reconciliations),
        runs=[run["identity"] for run in runs]))
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("parent", "output", "series-root", "data-root"):
        parser.add_argument("--" + key, required=True, type=Path)
    parser.add_argument("--start")
    parser.add_argument("--end")
    args = parser.parse_args()
    reconstruct(args.parent, args.output, args.series_root, args.data_root,
                start=args.start, end=args.end)


if __name__ == "__main__":
    main()
