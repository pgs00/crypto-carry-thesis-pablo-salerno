"""Causal H1 labels and portfolio-independent minute opportunity evidence."""

from bisect import bisect_left, bisect_right
from collections import Counter
from decimal import Decimal as D

import numpy as np
import pyarrow.parquet as pq

from crypto_carry.config import HOUR, SECOND, iso, timestamp
from crypto_carry.data.market_calendar import DOCUMENTED_CLOSURES
from crypto_carry.data.replay import _records
from crypto_carry.forecast import forecast

from .common import SYMBOLS, decimal, yes

MINUTE = 60 * SECOND


def minute_flags(times, data, forecasts, cost, config):
    """Operate on current closed bars; portfolio state is deliberately absent."""
    published = np.array([r["time_ns"] for r in forecasts], dtype=np.int64)
    if np.any(published[1:] <= published[:-1]):
        raise ValueError("Forecast publications must be strictly increasing")
    indices = np.searchsorted(published, times, side="right") - 1
    valid_fc = np.array([yes(r["valid"]) for r in forecasts])[np.maximum(indices, 0)] & (
        indices >= 0
    )
    funding_pass = (
        np.array([decimal(r["forecast"]) > cost for r in forecasts])[np.maximum(indices, 0)]
        & valid_fc
    )
    spot, future = data["spot"], data["future"]
    spot_known = np.isfinite(spot) | data["known_spot_missing"]
    future_known = np.isfinite(future) | data["known_future_missing"]
    complete = spot_known & future_known & data["mark_present"] & valid_fc
    operational = (
        np.isfinite(spot)
        & np.isfinite(future)
        & (spot > 0)
        & (future > 0)
        & (data["spot_volume"] > 0)
        & (data["future_volume"] > 0)
    )
    # Resolve the rare exact threshold ties with decimal arithmetic.
    low = future - spot * (1 + float(config.basis_min))
    high = future - spot * (1 + float(config.basis_max))
    basis_pass = (low >= 0) & (high <= 0)
    ties = np.flatnonzero((np.abs(low) < 1e-8) | (np.abs(high) < 1e-8))
    for index in ties:
        if spot[index] > 0:
            observed = D(str(future[index])) / D(str(spot[index])) - 1
            basis_pass[index] = config.basis_min <= observed <= config.basis_max
    return dict(
        complete=complete,
        eligible=complete & operational & funding_pass & basis_pass,
        forecast_index=indices,
        funding_pass=funding_pass,
        basis_pass=basis_pass,
        operational=operational,
        known_closure=data["known_spot_missing"] | data["known_future_missing"],
        forecast_valid=valid_fc,
        unknown_market_data=~(spot_known & future_known & data["mark_present"]),
    )


def summarize_day(times, flags, forecasts):
    good = len(times) == 1440 and len(np.unique(times)) == 1440 and bool(flags["complete"].all())
    total = D(0)
    for index in np.unique(flags["forecast_index"]):
        count = int(np.count_nonzero(flags["eligible"] & (flags["forecast_index"] == index)))
        if index >= 0:
            total += decimal(forecasts[index]["forecast"]) * count
    return dict(
        complete=good,
        expected_minutes=1440,
        observed_minutes=len(times),
        valid_minutes=int(flags["complete"].sum()),
        eligible_minutes=int(flags["eligible"].sum()),
        unknown_market_minutes=int(flags["unknown_market_data"].sum()),
        invalid_forecast_minutes=int((~flags["forecast_valid"]).sum()),
        known_closure_missing_minutes=int(flags["known_closure"].sum()),
        nonoperational_minutes=int((flags["complete"] & ~flags["operational"]).sum()),
        funding_failed_minutes=int((flags["complete"] & ~flags["funding_pass"]).sum()),
        basis_failed_minutes=int(
            (flags["complete"] & flags["operational"] & ~flags["basis_pass"]).sum()
        ),
        opportunity_sum=total,
        opportunity=total / 1440 if good else None,
        eligible_fraction=D(int(flags["eligible"].sum())) / 1440 if good else None,
        reason="" if good else "incomplete_required_minute_or_forecast",
    )


def h1_summaries(rows, periods):
    output = []
    for period, start, end in periods:
        asset_rows = []
        for symbol in SYMBOLS:
            group = [r for r in rows if r["symbol"] == symbol and start <= int(r["time_ns"]) < end]
            valid = [r for r in group if yes(r["horizon_valid"])]
            result = dict(
                period=period,
                symbol=symbol,
                total_observations=len(group),
                valid_observations=len(valid),
                excluded_observations=len(group) - len(valid),
                exclusion_counts=dict(
                    Counter(r["reason"] for r in group if not yes(r["horizon_valid"]))
                ),
                mae_ewma=sum((decimal(r["absolute_error_ewma"]) for r in valid), D(0)) / len(valid)
                if valid
                else None,
                mae_no_change=sum((decimal(r["absolute_error_no_change"]) for r in valid), D(0))
                / len(valid)
                if valid
                else None,
            )
            asset_rows.append(result)
        output.extend(asset_rows)
        output.append(
            dict(
                period=period,
                symbol="EQUAL_WEIGHT",
                **{
                    key: sum(r[key] for r in asset_rows)
                    for key in ("total_observations", "valid_observations", "excluded_observations")
                },
                exclusion_counts=dict(
                    sum((Counter(r["exclusion_counts"]) for r in asset_rows), Counter())
                ),
                **{
                    key: sum((r[key] for r in asset_rows), D(0)) / 2
                    if all(r[key] is not None for r in asset_rows)
                    else None
                    for key in ("mae_ewma", "mae_no_change")
                },
            )
        )
    return output


def funding_history(root, manifest):
    result = {}
    for symbol in SYMBOLS:
        rows = [
            r
            for e in manifest["entries"]
            if e["dataset"] == "funding" and e["symbol"] == symbol
            for r in _records(root / e["path"], "funding")
        ]
        rows.sort(key=lambda r: r.funding_time)
        if len({r.funding_time for r in rows}) != len(rows):
            raise ValueError("Duplicate funding source observation")
        result[symbol] = rows
    return result


def checked_forecasts(signals, history, config):
    """Recompute each stored forecast from its historical window, plus the warmup seed."""
    result, audit = {}, []
    for symbol in SYMBOLS:
        funding = history[symbol]
        times = [r.funding_time for r in funding]
        published = sorted(
            (r for r in signals if r["symbol"] == symbol), key=lambda r: int(r["time_ns"])
        )
        seed = max(
            (r for r in funding if r.available_at < timestamp(config.start)),
            key=lambda r: r.available_at,
        )
        schedule = []
        observations = [dict(anchor=seed.funding_time, time_ns=seed.available_at)] + published
        for row in observations:
            anchor, decision = int(row["anchor"]), int(row["time_ns"])
            first = max(0, bisect_right(times, anchor - config.window_hours * HOUR) - 1)
            last = bisect_right(times, anchor)
            fc = forecast(funding[first:last], anchor, decision, config)
            if "forecast" in row and (
                fc.value != decimal(row["forecast"])
                or fc.no_change != decimal(row["no_change"])
                or fc.valid != yes(row["valid"])
                or fc.history_start != int(row["history_start"])
            ):
                raise ValueError(
                    f"Stored forecast does not match its causal inputs: {symbol} {iso(decision)}"
                )
            schedule.append(
                dict(
                    time_ns=decision,
                    symbol=symbol,
                    anchor=anchor,
                    valid=fc.valid,
                    forecast=str(fc.value),
                    no_change=str(fc.no_change),
                    history_start=fc.history_start,
                    reason=fc.reason,
                )
            )
        result[symbol] = schedule
        audit.append(
            dict(
                symbol=symbol,
                stored_forecasts_verified=len(published),
                warmup_anchor_utc=iso(seed.funding_time),
                warmup_available_at_utc=iso(seed.available_at),
            )
        )
    return result, audit


def h1_observations(signals, history, config):
    """Future observations are labels only; cohort membership uses signal time."""
    output = []
    for symbol in SYMBOLS:
        funding = history[symbol]
        times = [r.funding_time for r in funding]
        sums = [D(0)]
        bad = [0]
        for i, row in enumerate(funding):
            sums.append(sums[-1] + row.funding_rate)
            good = row.interval_verified and (
                i == 0 or D(row.funding_time - times[i - 1]) / HOUR == row.interval_hours
            )
            bad.append(bad[-1] + int(not good))
        for signal in signals:
            if signal["symbol"] != symbol:
                continue
            now = int(signal["time_ns"])
            end = now + config.horizon_hours * HOUR
            reason = ""
            left, right = bisect_right(times, now), bisect_right(times, end)
            following = bisect_left(times, end)
            if not yes(signal["valid"]):
                reason = "invalid_forecast_history"
            elif end >= timestamp(config.end):
                reason = "horizon_outside_sample"
            elif left == 0 or following == len(times):
                reason = "funding_calendar_boundary_unverified"
            elif bad[following + 1] - bad[left]:
                reason = "missing_or_unverified_funding_interval"
            observed = sums[right] - sums[left] if not reason else None
            ewma, nc = decimal(signal["forecast"]), decimal(signal["no_change"])
            output.append(
                dict(
                    symbol=symbol,
                    time_ns=now,
                    signal_utc=iso(now),
                    anchor=int(signal["anchor"]),
                    history_start=int(signal["history_start"]),
                    horizon_end=end,
                    horizon_end_utc=iso(end),
                    forecast=ewma,
                    no_change=nc,
                    realized=observed,
                    horizon_valid=not reason,
                    realized_funding_events=right - left if not reason else None,
                    reason=reason,
                    error_ewma=ewma - observed if observed is not None else None,
                    error_no_change=nc - observed if observed is not None else None,
                    absolute_error_ewma=abs(ewma - observed) if observed is not None else None,
                    absolute_error_no_change=abs(nc - observed) if observed is not None else None,
                )
            )
    return sorted(output, key=lambda r: (r["time_ns"], r["symbol"]))


def month_grid(root, entries, symbol, market, dataset, times):
    """Select exact closed-minute observations, including the preceding month edge."""
    columns = ["open_time", "available_at", "close"]
    if dataset == "minute_bars":
        columns += ["base_volume", "end_time"]
    selected = [
        e
        for e in entries
        if e["dataset"] == dataset
        and e["symbol"] == symbol
        and e["market"] == market
        and e["start"] <= int(times[-1])
        and e["end"] >= int(times[0])
    ]
    values = np.full(len(times), np.nan)
    volumes = np.zeros(len(times))
    seen = np.zeros(len(times), dtype=bool)
    for entry in selected:
        table = pq.ParquetFile(root / entry["path"]).read(columns=columns)
        available = table["available_at"].to_numpy()
        opened = table["open_time"].to_numpy()
        mask = (available >= times[0]) & (available <= times[-1])
        indices = ((available[mask] - times[0]) // MINUTE).astype(np.int64)
        if np.any(available[mask] != times[indices]) or np.any(
            opened[mask] + MINUTE != available[mask]
        ):
            raise ValueError("Noncausal or unaligned closed-minute observation")
        if seen[indices].any() or len(np.unique(indices)) != len(indices):
            raise ValueError("Duplicate closed-minute source")
        seen[indices] = True
        values[indices] = table["close"].cast("double").to_numpy()[mask]
        if dataset == "minute_bars":
            if np.any(table["end_time"].to_numpy()[mask] != available[mask]):
                raise ValueError("Bar end differs from publication time")
            volumes[indices] = table["base_volume"].cast("double").to_numpy()[mask]
    known = np.zeros(len(times), dtype=bool)
    for closure in DOCUMENTED_CLOSURES:
        if symbol in closure.symbols and market == closure.market:
            known |= (times - MINUTE >= closure.start) & (times - MINUTE < closure.end) & ~seen
    return values, volumes, seen, known


def market_opportunity(root, manifest, schedules, config, cost, progress=print):
    days, groups, sample = [], [], []
    start, end = timestamp(config.start), timestamp(config.end)
    current = start
    while current < end:
        month = iso(current)[:7]
        year, number = map(int, month.split("-"))
        next_month = timestamp(f"{year + (number == 12):04d}-{number % 12 + 1:02d}-01T00:00:00Z")
        stop = min(end, next_month)
        times = np.arange(current, stop, MINUTE, dtype=np.int64)
        for symbol in config.symbols:
            spot, sv, _, sk = month_grid(
                root, manifest["entries"], symbol, "spot", "minute_bars", times
            )
            future, fv, _, fk = month_grid(
                root, manifest["entries"], symbol, "futures", "minute_bars", times
            )
            mark, _, mp, _ = month_grid(
                root, manifest["entries"], symbol, "futures", "marks", times
            )
            schedule = schedules[symbol]
            flags = minute_flags(
                times,
                dict(
                    spot=spot,
                    future=future,
                    spot_volume=sv,
                    future_volume=fv,
                    mark_present=mp,
                    known_spot_missing=sk,
                    known_future_missing=fk,
                ),
                schedule,
                cost,
                config,
            )
            for first in range(0, len(times), 1440):
                last = first + 1440
                day_times = times[first:last]
                day_flags = {k: v[first:last] for k, v in flags.items()}
                date = iso(int(day_times[0]))[:10]
                days.append(
                    dict(
                        date=date,
                        time_ns=int(day_times[0]),
                        symbol=symbol,
                        **summarize_day(day_times, day_flags, schedule),
                    )
                )
                for index in np.unique(day_flags["forecast_index"]):
                    subset = day_flags["forecast_index"] == index
                    fc = schedule[index] if index >= 0 else {}
                    count = int((day_flags["eligible"] & subset).sum())
                    groups.append(
                        dict(
                            date=date,
                            symbol=symbol,
                            forecast_anchor=fc.get("anchor"),
                            forecast_available_at=fc.get("time_ns"),
                            forecast=fc.get("forecast"),
                            minutes=int(subset.sum()),
                            valid_minutes=int((day_flags["complete"] & subset).sum()),
                            eligible_minutes=count,
                            opportunity_sum=decimal(fc.get("forecast")) * count,
                        )
                    )
                # Fixed daily observations plus transitions and the full outage day.
                sample_indices = {first, first + 720, last - 1}
                if date == "2023-03-24":
                    sample_indices.update(range(first, last))
                sample_indices.update(
                    first + int(i) for i in np.flatnonzero(np.diff(day_flags["forecast_index"])) + 1
                )
                for i in sorted(sample_indices):
                    index = flags["forecast_index"][i]
                    fc = schedule[index] if index >= 0 else {}
                    sample.append(
                        dict(
                            symbol=symbol,
                            time_ns=int(times[i]),
                            minute_utc=iso(int(times[i])),
                            candle_open_utc=iso(int(times[i] - MINUTE)),
                            spot_close=spot[i] if np.isfinite(spot[i]) else None,
                            future_close=future[i] if np.isfinite(future[i]) else None,
                            mark_close=mark[i] if np.isfinite(mark[i]) else None,
                            spot_base_volume=sv[i],
                            future_base_volume=fv[i],
                            forecast=fc.get("forecast"),
                            forecast_available_at=fc.get("time_ns"),
                            cycle_cost=cost,
                            **{k: bool(v[i]) for k, v in flags.items() if k != "forecast_index"},
                        )
                    )
        progress(f"H3 market-only: {month} | {(stop - start) / (end - start):.1%}", flush=True)
        current = stop
    joint = []
    for date in sorted({r["date"] for r in days}):
        pair = [r for r in days if r["date"] == date]
        complete = len(pair) == 2 and all(r["complete"] for r in pair)
        joint.append(
            dict(
                date=date,
                time_ns=timestamp(date + "T00:00:00Z"),
                complete=complete,
                opportunity=sum((r["opportunity"] for r in pair), D(0)) / 2 if complete else None,
                eligible_fraction=sum((r["eligible_fraction"] for r in pair), D(0)) / 2
                if complete
                else None,
                reason="" if complete else "incomplete_asset_day",
            )
        )
    return days, joint, groups, sample
