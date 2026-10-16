"""Pure intraday valuation and isolated-margin arithmetic over original states.

Bulk calculations use NumPy float64; only observations at floating-point tier
or preventive boundaries receive a Decimal recheck. No fills, cash movements,
prices or economic decisions are generated here. NaN means non-evaluable,
never zero. Asset inputs have symbols on the last axis; time is the first axis.
"""

from __future__ import annotations

import tomllib
from collections import defaultdict
from decimal import Decimal as D
from decimal import localcontext
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq

from . import common as sources


def _arrays(*values):
    return np.broadcast_arrays(*(np.asarray(value, dtype=np.float64) for value in values))


def _finite(*values):
    return np.logical_and.reduce([np.isfinite(value) for value in values])


def _nonnegative(**values):
    for name, value in values.items():
        if np.any(value < 0):
            raise ValueError(f"{name} must be nonnegative")


def _sum_assets(value):
    return np.sum(value, axis=-1) if value.ndim else value


def _timestamps(value):
    """Keep nanosecond integers exact; do not round timestamps through float."""
    array = np.asarray(value)
    if array.dtype.kind in "iu":
        if array.dtype.kind == "u" and np.any(array > np.iinfo(np.int64).max):
            raise ValueError("timestamp outside int64 range")
        return array.astype(np.int64, copy=False), np.ones(array.shape, dtype=bool)
    if array.dtype.kind == "f" and np.all(~np.isfinite(array)):
        return np.zeros(array.shape, dtype=np.int64), np.zeros(array.shape, dtype=bool)
    if array.dtype.kind == "O":
        result = np.zeros(array.shape, dtype=np.int64)
        valid = np.zeros(array.shape, dtype=bool)
        for index in np.ndindex(array.shape):
            item = array[index]
            if item is None:
                continue
            if not isinstance(item, (int, np.integer)) or isinstance(item, bool):
                raise ValueError("timestamps must be integer nanoseconds")
            result[index], valid[index] = item, True
        return result, valid
    raise ValueError("timestamps must be integer nanoseconds")


def equity_value(
    free_spot, free_futures, debt, spot, short, average, collateral, spot_price, mark_price
):
    """Sum cash, collateral, spot value and short UPnL, minus existing debt.

    Funding/fees are already present in these account balances. A zero quantity
    does not require a price; a missing price on nonzero inventory makes equity ND.
    Collateral is a per-symbol stock, including any balance after a short closes.
    """
    spot, short, average, collateral, spot_price, mark_price = _arrays(
        spot, short, average, collateral, spot_price, mark_price
    )
    _nonnegative(spot=spot, short=short)
    spot_value = np.zeros(spot.shape)
    upnl = np.zeros(short.shape)
    with np.errstate(invalid="ignore", over="ignore"):
        np.multiply(spot, spot_price, out=spot_value, where=spot != 0)
        np.multiply(short, average - mark_price, out=upnl, where=short != 0)
        cash_spot, cash_futures, borrowed, holdings = _arrays(
            free_spot, free_futures, debt, _sum_assets(collateral + spot_value + upnl)
        )
        value = cash_spot + cash_futures + holdings - borrowed
    return np.where(np.isfinite(value), value, np.nan)


def drawdown_path(equity, initial_equity):
    """Signed DD against the known high-water mark, with initial capital included.

    Missing observations stay NaN. Following values use the observed maximum only;
    call drawdown_summary to distinguish that diagnostic from complete coverage.
    Negative equity is retained and may produce a drawdown below -100%.
    """
    equity = np.asarray(equity, dtype=np.float64)
    if not equity.ndim:
        raise ValueError("equity must have a time axis")
    initial = np.broadcast_to(np.asarray(initial_equity, dtype=np.float64), equity.shape[1:])
    values = np.where(np.isfinite(equity), equity, np.nan)
    first = np.where(np.isfinite(initial), initial, np.nan)
    highwater = np.fmax.accumulate(np.concatenate((first[None, ...], values)), axis=0)[1:]
    result = np.full(equity.shape, np.nan)
    np.divide(values, highwater, out=result, where=np.isfinite(values) & (highwater > 0))
    return result - 1


def drawdown_summary(times_ns, equity, initial_equity, initial_time_ns):
    """One account, ordered observations; ties select the first persisted row.

    With gaps, full-period drawdown/loss are ND and observed_* fields retain the
    observed-only diagnostic. Peak/trough/recovery then describe observed points,
    not a proof that no larger loss or earlier recovery occurred inside a gap.
    """
    times, valid_times = _timestamps(times_ns)
    initial_time, valid_initial_time = _timestamps(initial_time_ns)
    values = np.asarray(equity, dtype=np.float64)
    if (
        values.ndim != 1
        or times.ndim != 1
        or len(times) != len(values)
        or not np.all(valid_times)
        or initial_time.ndim
        or not valid_initial_time
    ):
        raise ValueError("summary requires aligned finite integer timestamps and one equity vector")
    if np.any(times[1:] < times[:-1]) or (len(times) and initial_time > times[0]):
        raise ValueError("account states must preserve chronological order")
    initial = float(initial_equity)
    missing = int(np.count_nonzero(~np.isfinite(values)))
    positive_initial = np.isfinite(initial) and initial > 0
    complete = bool(len(values) and missing == 0 and positive_initial)
    result = dict(
        drawdown=np.nan,
        observed_drawdown=np.nan,
        peak_time_ns=None,
        trough_time_ns=None,
        recovery_time_ns=None,
        peak_equity=np.nan,
        trough_equity=np.nan,
        loss_usdt=np.nan,
        observed_loss_usdt=np.nan,
        peak_index=None,
        trough_index=None,
        recovery_index=None,
        recovery_observed=False,
        missing_observations=missing,
        observations=len(values),
        complete=complete,
        nonpositive_equity_observations=int(np.count_nonzero(values <= 0)),
        reason="",
        scope="complete" if complete else "observed_only",
    )
    if not positive_initial:
        result["reason"] = "initial_equity_not_positive"
    elif not len(values):
        result["reason"] = "no_equity_observations"
    elif missing:
        result["reason"] = "incomplete_equity_coverage_observed_only"
    elif result["nonpositive_equity_observations"]:
        result["reason"] = "nonpositive_equity_observed"
    path = drawdown_path(values, initial)
    if not np.any(np.isfinite(path)):
        return result
    trough = int(np.nanargmin(path))
    prior = np.concatenate(([initial], values[: trough + 1]))
    prior = np.where(np.isfinite(prior), prior, -np.inf)
    peak = int(np.argmax(prior)) - 1
    peak_value = initial if peak == -1 else float(values[peak])
    later = np.flatnonzero(np.isfinite(values[trough:]) & (values[trough:] >= peak_value))
    recovery = int(trough + later[0]) if len(later) else None
    observed_dd, observed_loss = float(path[trough]), peak_value - float(values[trough])
    result.update(
        observed_drawdown=observed_dd,
        observed_loss_usdt=observed_loss,
        drawdown=observed_dd if complete else np.nan,
        loss_usdt=observed_loss if complete else np.nan,
        peak_time_ns=int(initial_time) if peak == -1 else int(times[peak]),
        trough_time_ns=int(times[trough]),
        peak_equity=peak_value,
        trough_equity=float(values[trough]),
        peak_index=peak,
        trough_index=trough,
        recovery_index=recovery,
        recovery_observed=recovery is not None,
        recovery_time_ns=int(times[recovery]) if recovery is not None else None,
    )
    return result


def joint_liquidity(needs_by_asset, free_cash, reserved_cash=0):
    """Compare simultaneous needs with shared, verified uncommitted cash once."""
    needs = np.asarray(needs_by_asset, dtype=np.float64)
    _nonnegative(needs=needs)
    total, cash, reserved = _arrays(_sum_assets(needs), free_cash, reserved_cash)
    _nonnegative(reserved_cash=reserved)
    valid = _finite(total, cash, reserved)
    available = np.where(valid, np.maximum(0, cash - reserved), np.nan)
    return dict(
        total_need=np.where(np.isfinite(total), total, np.nan),
        redistributable=available,
        external_shortfall=np.where(valid, np.maximum(0, total - available), np.nan),
        evaluable=valid,
        reason=np.where(valid, "", "unknown_need_or_cash_commitment"),
    )


def causal_spot_proxy(
    spot_anchor,
    futures_anchor,
    futures_price,
    anchor_available_ns,
    price_available_ns,
    valuation_ns,
):
    """Fixed-anchor valuation diagnostic; availability prohibits future prices."""
    anchor_time, anchor_known = _timestamps(anchor_available_ns)
    price_time, price_known = _timestamps(price_available_ns)
    value_time, value_known = _timestamps(valuation_ns)
    spot, future, current = _arrays(spot_anchor, futures_anchor, futures_price)
    spot, future, current, anchor_time, price_time, value_time, known = np.broadcast_arrays(
        spot,
        future,
        current,
        anchor_time,
        price_time,
        value_time,
        anchor_known & price_known & value_known,
    )
    reason = np.full(spot.shape, "", dtype=object)
    reason[price_time < anchor_time] = "futures_price_precedes_anchor"
    reason[price_time > value_time] = "future_futures_price"
    reason[anchor_time > value_time] = "future_anchor"
    reason[~known] = "missing_price_availability"
    reason[~np.isfinite(current) | (current <= 0)] = "missing_or_nonpositive_futures_price"
    reason[~_finite(spot, future) | (spot <= 0) | (future <= 0)] = "missing_or_nonpositive_anchor"
    valid = reason == ""
    price = np.full(spot.shape, np.nan)
    with np.errstate(invalid="ignore", over="ignore"):
        np.divide(spot * current, future, out=price, where=valid)
    valid &= np.isfinite(price)
    reason[(reason == "") & ~valid] = "nonfinite_proxy"
    return dict(price=np.where(valid, price, np.nan), evaluable=valid, reason=reason)


def short_margin(quantity, average, collateral, mark, rate, deduction, multiplier=1):
    """Frozen isolated-short arithmetic; M2 scales the entire requirement.

    An unknown active margin state is flagged unsafe conservatively and remains
    non-evaluable. A known nonpositive balance is unsafe and has a NaN ratio.
    """
    q, average, collateral, mark, rate, deduction, factor = _arrays(
        quantity, average, collateral, mark, rate, deduction, multiplier
    )
    _nonnegative(quantity=q, rate=rate, deduction=deduction)
    if np.any(factor <= 0):
        raise ValueError("maintenance multiplier must be positive")
    active, closed = q > 0, q == 0
    valid = active & _finite(q, average, collateral, mark, rate, deduction, factor) & (mark > 0)
    with np.errstate(invalid="ignore", over="ignore"):
        upnl = np.where(closed, 0, q * (average - mark))
        balance = collateral + upnl
        maintenance = np.where(
            closed, 0, np.where(valid, (q * mark * rate - deduction) * factor, np.nan)
        )
    ratio = np.full(q.shape, np.nan)
    np.divide(maintenance, balance, out=ratio, where=valid & (balance > 0))
    reason = np.full(q.shape, "", dtype=object)
    reason[~valid] = "non_evaluable_margin"
    reason[valid & (balance <= 0)] = "nonpositive_margin_balance"
    reason[closed] = "no_open_short"
    unsafe = ~closed & (~valid | (balance <= 0) | (balance <= maintenance))
    return dict(
        notional=np.where(closed, 0, q * mark),
        unrealized_pnl=upnl,
        margin_balance=balance,
        maintenance=maintenance,
        headroom=balance - maintenance,
        ratio=ratio,
        maintenance_shortfall=np.where(closed, 0, np.maximum(0, maintenance - balance)),
        unsafe=unsafe,
        no_short=closed,
        evaluable=valid,
        reason=reason,
    )


def _tiers(tiers):
    rows = []
    for row in tiers:
        values = tuple(float(row[key]) for key in ("floor", "cap", "rate", "deduction"))
        floor, cap, rate, deduction = values
        if not all(np.isfinite(values)) or floor < 0 or cap <= floor or rate < 0 or deduction < 0:
            raise ValueError("invalid maintenance tier")
        rows.append(values)
    if not rows:
        raise ValueError("maintenance tiers are required")
    return sorted(rows, key=lambda row: row[:2])


def _tier_values(notional, tiers):
    rate, deduction = np.full(notional.shape, np.nan), np.full(notional.shape, np.nan)
    for floor, cap, tier_rate, tier_deduction in tiers:
        selected = np.isnan(rate) & (notional >= floor) & (notional <= cap)
        rate[selected], deduction[selected] = tier_rate, tier_deduction
    return rate, deduction


def _near(left, right):
    return (
        np.isfinite(left)
        & np.isfinite(right)
        & (
            np.abs(left - right)
            <= 8 * np.finfo(float).eps * np.maximum(1, np.maximum(np.abs(left), np.abs(right)))
        )
    )


def _decimal(value):
    return D(str(float(value)))


def _decimal_liquidation(q, average, collateral, tiers, factor):
    candidates = []
    for floor, cap, rate, deduction in tiers:
        candidate = (collateral + q * average + _decimal(deduction) * factor) / (
            q * (1 + _decimal(rate) * factor)
        )
        if candidate >= 0 and _decimal(floor) <= q * candidate <= _decimal(cap):
            candidates.append(candidate)
    return min(candidates) if candidates else None


def liquidation_distance(quantity, average, collateral, mark, tiers, multiplier=1):
    """Solve every frozen tier, take the minimum valid short liquidation price."""
    tiers = _tiers(tiers)
    q, average, collateral, mark, factor = _arrays(quantity, average, collateral, mark, multiplier)
    _nonnegative(quantity=q)
    if np.any(factor <= 0):
        raise ValueError("maintenance multiplier must be positive")
    active = (q > 0) & _finite(q, average, collateral, mark, factor) & (mark > 0)
    price = np.full(q.shape, np.inf)
    for floor, cap, rate, deduction in tiers:
        candidate = np.full(q.shape, np.nan)
        np.divide(
            collateral + q * average + deduction * factor,
            q * (1 + rate * factor),
            out=candidate,
            where=active,
        )
        notional = q * candidate
        matches = active & (candidate >= 0) & (notional >= floor) & (notional <= cap)
        boundary = active & (_near(notional, floor) | _near(notional, cap))
        with localcontext() as context:
            context.prec = 50
            for index in zip(*np.nonzero(boundary.reshape(-1))):
                offset = index[0]
                dq, da, dc, df = (
                    _decimal(v.flat[offset]) for v in (q, average, collateral, factor)
                )
                exact = (dc + dq * da + _decimal(deduction) * df) / (dq * (1 + _decimal(rate) * df))
                matches.flat[offset] = exact >= 0 and _decimal(floor) <= dq * exact <= _decimal(cap)
                candidate.flat[offset] = float(exact)
        price = np.minimum(price, np.where(matches, candidate, np.inf))
    valid = active & np.isfinite(price)
    price = np.where(valid, price, np.nan)
    distance = np.full(q.shape, np.nan)
    np.divide(price - mark, mark, out=distance, where=valid)
    reason = np.full(q.shape, "", dtype=object)
    reason[~active] = "non_evaluable_liquidation"
    reason[active & ~valid] = "liquidation_price_outside_tiers"
    reason[q == 0] = "no_open_short"
    return dict(
        liquidation_price=price, distance=distance, evaluable=valid, reason=reason, no_short=q == 0
    )


def _decimal_maintenance(notional, tiers, factor):
    for floor, cap, rate, deduction in tiers:
        if _decimal(floor) <= notional <= _decimal(cap):
            return (notional * _decimal(rate) - _decimal(deduction)) * factor
    return None


def maintenance_requirement(quantity, mark, tiers, multiplier=1):
    """Frozen first-inclusive-tier amount, zero for no short, NaN if uncovered."""
    table = _tiers(tiers)
    q, mark, factor = _arrays(quantity, mark, multiplier)
    _nonnegative(quantity=q, mark=mark)
    if np.any(factor <= 0):
        raise ValueError("maintenance multiplier must be positive")
    notional = q * mark
    rate, deduction = _tier_values(notional, table)
    valid = (q > 0) & _finite(q, mark, factor, rate, deduction)
    amount = np.where(q == 0, 0, np.where(valid, (notional * rate - deduction) * factor, np.nan))
    boundary = np.zeros(q.shape, dtype=bool)
    for floor, cap, _, _ in table:
        boundary |= (
            (q > 0) & _finite(q, mark, factor) & (_near(notional, floor) | _near(notional, cap))
        )
    with localcontext() as context:
        context.prec = 50
        for offset in np.flatnonzero(boundary):
            exact = _decimal_maintenance(
                _decimal(q.flat[offset]) * _decimal(mark.flat[offset]),
                table,
                _decimal(factor.flat[offset]),
            )
            amount.flat[offset] = float(exact) if exact is not None else np.nan
    return amount


def preventive_topup(
    quantity, average, collateral, mark, tiers, multiplier=1, ratio_limit=0.50, distance_limit=0.15
):
    """Infimum of a hypothetical cash-to-collateral transfer over original states.

    Safe requires M/B < ratio_limit and liquidation distance >= distance_limit.
    When the ratio constraint binds, the returned infimum itself still triggers
    prevention: strict_infimum is true. No arbitrary transfer quantum is added.
    """
    table = _tiers(tiers)
    q, average, collateral, mark, factor = _arrays(quantity, average, collateral, mark, multiplier)
    ratio_limit, distance_limit = float(ratio_limit), float(distance_limit)
    if (
        not np.isfinite(ratio_limit)
        or ratio_limit <= 0
        or not np.isfinite(distance_limit)
        or distance_limit < 0
    ):
        raise ValueError("invalid preventive thresholds")
    rate, deduction = _tier_values(q * mark, table)
    margin = short_margin(q, average, collateral, mark, rate, deduction, factor)
    liquidation = liquidation_distance(q, average, collateral, mark, tiers, factor)
    target_notional = q * mark * (1 + distance_limit)
    target_rate, target_deduction = _tier_values(target_notional, table)
    target_maintenance = (target_notional * target_rate - target_deduction) * factor
    balance, maintenance = margin["margin_balance"], margin["maintenance"]
    valid = margin["evaluable"] & liquidation["evaluable"] & np.isfinite(target_maintenance)
    ratio_need = maintenance / ratio_limit - balance
    distance_need = q * mark * distance_limit + target_maintenance - balance
    infimum = np.maximum(0, np.maximum(ratio_need, distance_need))
    ratio_triggered = valid & ((balance <= 0) | (maintenance >= ratio_limit * balance))
    distance_triggered = valid & (liquidation["distance"] < distance_limit)
    strict = valid & (ratio_need >= 0) & (ratio_need >= distance_need)
    boundary = valid & (
        _near(ratio_need, 0)
        | _near(distance_need, 0)
        | _near(ratio_need, distance_need)
        | _near(liquidation["distance"], distance_limit)
    )
    with localcontext() as context:
        context.prec = 50
        for offset in np.flatnonzero(boundary):
            dq, da, dc, dm, df = (
                _decimal(v.flat[offset]) for v in (q, average, collateral, mark, factor)
            )
            limit, distance = _decimal(ratio_limit), _decimal(distance_limit)
            db = dc + dq * (da - dm)
            requirement = _decimal_maintenance(dq * dm, table, df)
            stressed = _decimal_maintenance(dq * dm * (1 + distance), table, df)
            liquidation_exact = _decimal_liquidation(dq, da, dc, table, df)
            if requirement is None or stressed is None or liquidation_exact is None:
                valid.flat[offset] = False
                continue
            dr, dd = requirement / limit - db, dq * dm * distance + stressed - db
            ratio_need.flat[offset], distance_need.flat[offset] = float(dr), float(dd)
            infimum.flat[offset] = float(max(D(0), dr, dd))
            ratio_triggered.flat[offset] = db <= 0 or requirement >= limit * db
            distance_triggered.flat[offset] = liquidation_exact < dm * (1 + distance)
            strict.flat[offset] = dr >= 0 and dr >= dd
    closed = q == 0
    reason = np.where(valid, "", "non_evaluable_preventive_requirement").astype(object)
    reason[closed] = "no_open_short"
    return dict(
        **{
            key: margin[key]
            for key in (
                "notional",
                "margin_balance",
                "maintenance",
                "headroom",
                "ratio",
                "maintenance_shortfall",
                "unsafe",
            )
        },
        liquidation_price=liquidation["liquidation_price"],
        distance=liquidation["distance"],
        ratio_need=np.where(closed, 0, np.where(valid, np.maximum(0, ratio_need), np.nan)),
        distance_need=np.where(closed, 0, np.where(valid, np.maximum(0, distance_need), np.nan)),
        topup_infimum=np.where(closed, 0, np.where(valid, infimum, np.nan)),
        strict_infimum=strict & valid,
        strict_boundary=strict & valid,
        ratio_triggered=ratio_triggered & valid,
        distance_triggered=distance_triggered & valid,
        preventive=(q > 0) & (~valid | margin["unsafe"] | ratio_triggered | distance_triggered),
        evaluable=valid,
        no_short=closed,
        reason=reason,
    )


SCENARIOS = {
    "BASE_E3": ("conditional", "permanent"),
    "L01": ("conditional", "permanent"),
}


def recalculate(root):
    """Recalculate ratios from the archived intraday peak/trough witnesses.

    Complete intraday histories are not retained. This checks witness arithmetic,
    not whether the selected intraday extrema are globally worst. Daily BASE
    drawdown is independently recomputed over every retained daily balance.
    """
    from pathlib import Path

    from .common import read_rows, scenario_metrics
    from .signal import SCENARIOS as SIGNAL_SCENARIOS

    path = "results/riesgo/evidencia/tablas/drawdown_comparativo.csv"
    daily = scenario_metrics(root, "senal", SIGNAL_SCENARIOS)
    daily = {
        (r["strategy"], r["period"]): r["max_drawdown"] for r in daily if r["scenario"] == "BASE_E3"
    }
    output = []
    for source in read_rows(Path(root) / path):
        row = {
            key: source[key]
            for key in (
                "scenario",
                "strategy",
                "run_id",
                "period",
                "peak_policy",
                "start_utc",
                "end_exclusive_utc",
                "valuation",
            )
        }
        for frequency in ("daily", "intraday"):
            peak = float(source[frequency + "_peak_equity"])
            trough = float(source[frequency + "_trough_equity"])
            if peak <= 0 or trough > peak:
                raise ValueError("Invalid archived peak/trough witnesses")
            row[frequency + "_drawdown"] = trough / peak - 1
            row[frequency + "_loss_usdt"] = peak - trough
        if (
            source["scenario"] == "BASE_E3"
            and source["peak_policy"] == "period_reset"
            and source["valuation"] == "original_reconstructed"
        ):
            value = daily[(source["strategy"], source["period"])]
            if abs(float(value) - row["daily_drawdown"]) > 1e-12:
                raise ValueError("Daily risk witnesses disagree with the complete daily series")
            row["daily_drawdown"] = value
        row["extra_drawdown_pp"] = 100 * (float(row["daily_drawdown"]) - row["intraday_drawdown"])
        row["extra_peak_to_trough_loss_usdt"] = row["intraday_loss_usdt"] - row["daily_loss_usdt"]
        row["recalculation_scope"] = "archived_peak_trough_witness_arithmetic"
        output.append(row)
    return {path: output}


ZERO = D(0)


RELEASES = {
    "unwind_complete",
    "ordinary_close_complete",
    "rebalance_first_leg_failed",
    "opening_complete",
    "rebalance_complete",
}


ASSIGNING_ORDERS = {"open_spot", "increase_spot", "reduce_perp", "reduce_spot", "increase_perp"}


FIELDS = {
    "signals": {
        "time_ns",
        "symbol",
        "decision",
        "available_cash",
        "budget_required_cash",
        "sizing_feasible",
    },
    "renewal_diagnostics": {
        "time_ns",
        "symbol",
        "state_after",
        "available_cash",
        "budget_required_cash",
        "sizing_feasible",
    },
    "orders": {
        "time_ns",
        "symbol",
        "order_id",
        "status",
        "action",
        "purpose",
        "record_type",
        "cancel_requested_at",
        "quantity",
        "market",
        "side",
    },
    "fills": {"time_ns", "symbol", "order_id", "purpose", "partial", "remaining_quantity"},
    "risk_events": {"time_ns", "symbol", "kind", "cause"},
    "ledger": {"time_ns", "free_spot", "free_futures", "debt"},
    "positions": {"time_ns", "symbol", "spot_price"},
}


def _yes(value) -> bool:
    return value is True or str(value).lower() == "true"


def _tables(run: Path) -> dict:
    result = {}
    for name, fields in FIELDS.items():
        path = run / f"{name}.parquet"
        if not path.is_file():
            raise ValueError(f"Missing reservation evidence: {path}")
        schema = pq.read_schema(path)
        rows = pq.read_table(
            path, columns=[key for key in schema.names if key in fields]
        ).to_pylist()
        if name == "orders":
            rows = [row for row in rows if row.get("record_type", "event") == "event"]
        # Final positions can be appended after event snapshots; they are used
        # only for prices at the very same timestamp, never as a state stream.
        if name != "positions" and any(a["time_ns"] > b["time_ns"] for a, b in zip(rows, rows[1:])):
            raise ValueError(f"Nonmonotonic reservation source: {name}")
        result[name] = rows
    return result


def _history(run: Path) -> tuple[dict, dict]:
    config = tomllib.loads((run / "effective_config.toml").read_text(encoding="utf-8"))
    symbols = config["symbols"]
    tolerance = D(config.get("accounting_tolerance", "1E-8"))
    grouped = defaultdict(lambda: defaultdict(list))
    for name, rows in _tables(run).items():
        for row in rows:
            grouped[int(row["time_ns"])][name].append(row)
    bounds = {symbol: [ZERO, ZERO, "verified_no_reservation"] for symbol in symbols}
    tracked = {symbol: False for symbol in symbols}
    latest_orders = {}
    cash, debt = D(config["capital"]), ZERO
    columns = defaultdict(list)
    checks = {
        "diagnostics_checked": 0,
        "diagnostics_resolved_unknown": 0,
        "accepted_assignments": 0,
        "renewal_assignments": 0,
    }

    def totals():
        lo = sum((value[0] for value in bounds.values()), ZERO)
        hi = sum((value[1] for value in bounds.values()), ZERO)
        reason = next(
            (value[2] for value in bounds.values() if value[0] != value[1]),
            "verified_no_reservation" if hi == 0 else "verified_reservation",
        )
        pending = [row for row in latest_orders.values() if row["status"] == "pending"]
        # These closing/correction orders have no explicit strategy reservation.
        # Their future execution loss/fee is unknown until the persisted fill.
        unpriced = any(
            row.get("market") == "futures"
            and row.get("purpose") in {"close_perp", "liquidate", "correct"}
            for row in pending
        )
        if unpriced:
            hi = D("Infinity")
            reason = "unpriced_pending_futures_commitment"
        return lo, hi, reason, len(pending), unpriced

    def append(moment, *, interim=None):
        lo, hi, reason, pending, unpriced = totals()
        known = lo == hi and not unpriced
        spendable = max(ZERO, cash - debt)
        values = dict(
            time_ns=moment,
            reserved_cash=float(lo) if known else np.nan,
            reserved_cash_lower=float(lo),
            reserved_cash_upper=float(hi),
            available_known=known,
            reason=reason,
            pending_orders_count=pending,
            cash_available_lower=float(max(ZERO, spendable - hi)),
            cash_available_upper=float(max(ZERO, spendable - lo)),
        )
        for key, value in values.items():
            columns[key].append(value)
        if interim is None:
            interim = values
        for key in values:
            if key != "time_ns":
                columns[f"intermediate_{key}"].append(interim[key])

    append(np.iinfo(np.int64).min)
    for moment in sorted(grouped):
        groups = grouped[moment]
        pre_lo, pre_hi, _, pre_pending, _ = totals()
        cash_candidates = [max(ZERO, cash - debt)]
        envelope_hi = {symbol: bounds[symbol][1] for symbol in symbols}
        envelope_lo = {symbol: bounds[symbol][0] for symbol in symbols}
        reserve_activity = False

        def assign_bound(symbol, lo, hi, reason):
            nonlocal reserve_activity
            if symbol not in bounds or lo < 0 or hi < lo:
                raise ValueError(f"Invalid reservation bound for {symbol} at {moment}")
            reserve_activity = True
            envelope_lo[symbol] = min(envelope_lo[symbol], lo)
            envelope_hi[symbol] = max(envelope_hi[symbol], hi)
            bounds[symbol] = [lo, hi, reason]

        # Orders retain their physical event order. Final report copies were
        # filtered out; a deferred cancel remains pending.
        for row in groups["orders"]:
            latest_orders[row["order_id"]] = row
        for row in groups["ledger"]:
            cash = D(row["free_spot"]) + D(row["free_futures"])
            debt = D(row["debt"])
            cash_candidates.append(max(ZERO, cash - debt))

        same_time_prices = defaultdict(set)
        for row in groups["positions"]:
            if row.get("spot_price") not in (None, ""):
                same_time_prices[row["symbol"]].add(D(row["spot_price"]))
        for row in groups["fills"]:
            symbol, purpose = row["symbol"], row["purpose"]
            full = not _yes(row.get("partial")) and D(row.get("remaining_quantity") or "0") == 0
            order = latest_orders.get(row["order_id"])
            cancelled = order is not None and order.get("cancel_requested_at") not in (
                None,
                "",
                "None",
            )
            if not full or cancelled:
                continue
            if purpose in {"open_spot", "increase_spot"}:
                lo, hi, _ = bounds[symbol]
                prices = same_time_prices[symbol]
                if order is not None and len(prices) == 1:
                    reduction = D(order["quantity"]) * next(iter(prices))
                    assign_bound(
                        symbol,
                        max(ZERO, lo - reduction),
                        max(ZERO, hi - reduction),
                        "verified_reservation" if lo == hi else "bounded_reservation",
                    )
                else:
                    assign_bound(symbol, ZERO, hi, "missing_spot_close_at_full_fill")
            elif purpose in {"open_perp", "increase_perp", "reduce_spot"}:
                assign_bound(symbol, ZERO, ZERO, "verified_no_reservation")
                tracked[symbol] = False
        for row in groups["risk_events"]:
            if row.get("kind") == "transition" and row.get("cause") in RELEASES:
                assign_bound(row["symbol"], ZERO, ZERO, "verified_no_reservation")
                tracked[row["symbol"]] = False

        def diagnostic(row):
            if row.get("available_cash") in (None, ""):
                return
            other = [symbol for symbol in symbols if symbol != row["symbol"]]
            observed = cash - D(row["available_cash"])
            lower = sum((bounds[symbol][0] for symbol in other), ZERO)
            upper = sum((bounds[symbol][1] for symbol in other), ZERO)
            if observed < lower - tolerance or observed > upper + tolerance:
                raise ValueError(
                    f"available_cash inconsistent at {moment} {row['symbol']}: "
                    f"other reservations observed={observed}, derived=[{lower},{upper}]"
                )
            checks["diagnostics_checked"] += 1
            uncertain = [symbol for symbol in other if bounds[symbol][0] != bounds[symbol][1]]
            if len(uncertain) == 1:
                symbol = uncertain[0]
                known_other = sum((bounds[name][0] for name in other if name != symbol), ZERO)
                exact = min(bounds[symbol][1], max(bounds[symbol][0], observed - known_other))
                assign_bound(symbol, exact, exact, "verified_by_available_cash")
                checks["diagnostics_resolved_unknown"] += 1

        def assign(row, category):
            if row.get("budget_required_cash") in (None, "") or not _yes(
                row.get("sizing_feasible", True)
            ):
                assign_bound(row["symbol"], ZERO, max(ZERO, cash), "missing_reservation_assignment")
            else:
                amount = D(row["budget_required_cash"])
                assign_bound(row["symbol"], amount, amount, "verified_reservation")
            tracked[row["symbol"]] = True
            checks[category] += 1

        renewal_symbols = {
            row["symbol"]
            for row in groups["risk_events"]
            if row.get("kind") == "transition" and row.get("cause") == "renewal_rebalance"
        }
        for row in groups["renewal_diagnostics"]:
            diagnostic(row)
            if row["symbol"] in renewal_symbols:
                assign(row, "renewal_assignments")
        for row in groups["signals"]:
            diagnostic(row)
            if row.get("decision") == "accepted":
                assign(row, "accepted_assignments")
        for row in groups["orders"]:
            symbol = row["symbol"]
            if (
                row.get("action") == "submitted"
                and row.get("purpose") in ASSIGNING_ORDERS
                and not tracked[symbol]
            ):
                # A first-leg order without its sizing diagnostic cannot make
                # cash appear freely redistributable merely because a table is missing.
                assign_bound(
                    symbol,
                    ZERO,
                    max(bounds[symbol][1], max(ZERO, cash)),
                    "missing_reservation_assignment",
                )
                tracked[symbol] = True

        lo, hi, reason, pending, unpriced = totals()
        if reserve_activity or unpriced or pending != pre_pending:
            lower = min(pre_lo, lo, sum(envelope_lo.values(), ZERO))
            upper = max(pre_hi, hi, sum(envelope_hi.values(), ZERO))
            interim = dict(
                reserved_cash=np.nan,
                reserved_cash_lower=float(lower),
                reserved_cash_upper=float(upper),
                available_known=False,
                reason="ambiguous_simultaneous_phase",
                pending_orders_count=-1,
                cash_available_lower=float(max(ZERO, min(cash_candidates) - upper)),
                cash_available_upper=float(max(ZERO, max(cash_candidates) - lower)),
            )
        else:
            known = lo == hi
            interim = dict(
                reserved_cash=float(lo) if known else np.nan,
                reserved_cash_lower=float(lo),
                reserved_cash_upper=float(hi),
                available_known=known,
                reason=reason,
                pending_orders_count=pending,
                cash_available_lower=float(max(ZERO, min(cash_candidates) - hi)),
                cash_available_upper=float(max(ZERO, max(cash_candidates) - lo)),
            )
        append(moment, interim=interim)
    return {
        key: np.asarray(values, dtype=object if key.endswith("reason") else None)
        for key, values in columns.items()
    }, checks


def reservation_grid(run_path, times_ns, phases=None) -> dict:
    """Return commitments and availability bounds, preserving query order.

    ``available_known`` refers to the commitment amount, not future execution
    prices. ``cash_available_*`` deduct current debt as well as reservations.
    An unpriced futures closing/correction commitment has an infinite upper
    liability bound, while its available-cash bounds remain finite [0, cash].
    ``pending_orders_count=-1`` means the intermediate cross-table phase is not
    identifiable. ``validation`` records actual diagnostic comparisons.
    """
    times = np.asarray(times_ns, dtype=np.int64)
    if times.ndim != 1:
        raise ValueError("times_ns must be one-dimensional")
    phase = np.full(len(times), "post", dtype="U12") if phases is None else np.asarray(phases)
    if phase.shape != times.shape or not np.isin(phase, ["pre", "post", "intermediate"]).all():
        raise ValueError("phases must match times and contain pre/post/intermediate")
    history, validation = _history(Path(run_path))
    indices = np.searchsorted(history["time_ns"], times, side="right") - 1
    pre = phase == "pre"
    indices[pre] = np.searchsorted(history["time_ns"], times[pre], side="left") - 1
    if (indices < 0).any():
        raise ValueError("times outside supported int64 range")
    result = {
        key: values[indices].copy()
        for key, values in history.items()
        if key != "time_ns" and not key.startswith("intermediate_")
    }
    at_exact = history["time_ns"][indices] == times
    middle = (phase == "intermediate") & at_exact
    for key in result:
        result[key][middle] = history[f"intermediate_{key}"][indices[middle]]
    result["validation"] = validation
    return result


REASON_DICTIONARY = {
    "0": {
        "name": "causal_current",
        "description": "La última barra de minuto completamente disponible es válida para esta referencia.",
    },
    "1": {
        "name": "no_causal_valid_reference",
        "description": "No hay ningún cierre válido causal disponible; no se inventa precio ni causa de arrastre.",
    },
    "2": {
        "name": "carried_expected_minute_absent",
        "description": "Existe una referencia válida anterior, pero falta el registro de la última barra esperada.",
    },
    "3": {
        "name": "carried_zero_volume_omitted",
        "description": "La última barra esperada tiene precio válido y volumen cero: se omite según la política original.",
    },
    "4": {
        "name": "carried_invalid_price_omitted",
        "description": "La última barra esperada tiene cierre no finito o no positivo: se mantiene una referencia válida anterior.",
    },
    "5": {
        "name": "carried_invalid_volume_omitted",
        "description": "La última barra esperada tiene precio válido pero volumen negativo o NaN; no satisface volumen > 0.",
    },
}


def quality_codes(prices, times, *, require_volume):
    """Explain the last expected available bar, using only records available at t.

    Availability must lie on the authenticated UTC minute grid. A daily timestamp
    at 23:59:59.999999999 therefore expects availability 23:59, never next midnight.
    Code 1 takes precedence when no valid prior price exists; otherwise invalid
    close precedes volume rejection. Marks do not require positive trading volume.
    Estimated provenance is orthogonal and remains in the original observation.
    """
    times = np.asarray(times, dtype=np.int64)
    available = np.asarray(prices["available_at"], dtype=np.int64)
    close = np.asarray(prices["close"], dtype=np.float64)
    if available.ndim != 1 or close.shape != available.shape or times.ndim != 1:
        raise ValueError("Invalid price availability dimensions")
    if np.any(np.diff(available) <= 0) or np.any(available % sources.MINUTE):
        raise ValueError("Price availability must be strictly increasing on the UTC minute grid")
    result = np.ones(len(times), dtype=np.uint8)
    if not len(available):
        return result
    valid_close = np.isfinite(close) & (close > 0)
    eligible = valid_close.copy()
    if require_volume:
        volume = np.asarray(prices["base_volume"], dtype=np.float64)
        if volume.shape != available.shape:
            raise ValueError("Invalid volume dimensions")
        # Match price_at exactly: do not introduce a different eligibility rule.
        eligible &= volume > 0
    known = np.searchsorted(available[eligible], times, side="right") > 0
    result[known] = 2
    expected = (times // sources.MINUTE) * sources.MINUTE
    locations = np.searchsorted(available, expected)
    clipped = np.minimum(locations, len(available) - 1)
    present = known & (locations < len(available)) & (available[clipped] == expected)
    result[present & ~valid_close[clipped]] = 4
    valid_expected = present & valid_close[clipped]
    if require_volume:
        result[valid_expected & (volume[clipped] == 0)] = 3
        result[valid_expected & ~(volume[clipped] > 0) & (volume[clipped] != 0)] = 5
    result[present & eligible[clipped]] = 0
    return result
