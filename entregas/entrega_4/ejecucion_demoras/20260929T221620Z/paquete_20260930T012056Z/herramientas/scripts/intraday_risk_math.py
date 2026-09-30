"""Pure intraday valuation and isolated-margin arithmetic over original states.

Bulk calculations use NumPy float64; only observations at floating-point tier
or preventive boundaries receive a Decimal recheck. No fills, cash movements,
prices or economic decisions are generated here. NaN means non-evaluable,
never zero. Asset inputs have symbols on the last axis; time is the first axis.
"""

from __future__ import annotations

from decimal import Decimal as D
from decimal import localcontext

import numpy as np


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
