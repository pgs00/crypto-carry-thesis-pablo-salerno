"""Side-effect-free opportunity diagnostics evaluated at a decision timestamp."""

import json
from decimal import Decimal

from .costs import cycle_cost, execution_price, floor_step, valid_quantity
from .portfolio import hedge_error, joint_quantity, target_quantity
from .risk import basis

D = Decimal
ZERO = D(0)

PASS = "pass"
FAIL = "fail"
NOT_EVALUABLE = "not_evaluable"

FILTER_ORDER = (
    "state_active",
    "cooldown",
    "pending_orders",
    "debt",
    "coverage",
    "forecast",
    "rules",
    "operational",
    "mark",
    "price_alignment",
    "freshness",
    "funding",
    "basis_negative",
    "basis_above_max",
    "sizing",
    "budget",
)

RENEWAL_FILTER_ORDER = (
    "state_holding",
    "data_valid",
    "forecast",
    "debt",
    "funding_positive",
)


def _decimal(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


def _json(values) -> str:
    return json.dumps(list(values), separators=(",", ":"))


def _causal_reference(reference, now: int):
    if reference is None:
        return None
    available_at = getattr(reference, "available_at", None)
    event_time = getattr(reference, "event_time", getattr(reference, "end_time", None))
    if available_at is None or event_time is None:
        return None
    if available_at > now or event_time > now:
        return None
    return reference


def _price_fields(prefix: str, reference) -> dict:
    return {
        f"{prefix}_price": _decimal(reference.price) if reference is not None else None,
        f"{prefix}_price_time": getattr(reference, "event_time", None),
        f"{prefix}_open_time": getattr(reference, "open_time", None),
        f"{prefix}_end_time": getattr(reference, "end_time", None),
        f"{prefix}_available_at": getattr(reference, "available_at", None),
    }


def _prices_aligned(spot_reference, futures_reference) -> bool:
    spot_interval = (
        getattr(spot_reference, "open_time", None),
        getattr(spot_reference, "end_time", None),
    )
    futures_interval = (
        getattr(futures_reference, "open_time", None),
        getattr(futures_reference, "end_time", None),
    )
    if None not in spot_interval and None not in futures_interval:
        return spot_interval == futures_interval
    return spot_reference.event_time == futures_reference.event_time


def _planned_quantity_valid(quantity, price, side, rule, config) -> bool:
    execution, _ = execution_price(price, side, rule, config)
    return valid_quantity(quantity, price, rule) and valid_quantity(quantity, execution, rule)


def _empty_sizing() -> dict:
    return {
        "target_quantity": None,
        "proposed_spot_side": None,
        "proposed_gross_spot": None,
        "proposed_net_spot": None,
        "proposed_futures_side": None,
        "proposed_futures_quantity": None,
        "proposed_short": None,
        "proposed_spot_delta": None,
        "proposed_short_delta": None,
        "planned_hedge_error": None,
        "unallocated_target_usdt": None,
        "budget_required_cash": None,
        "sizing_feasible": None,
        "sizing_reason": "not_evaluable",
        "sizing_enforcement": None,
        "prospective_pair_feasible": None,
        "prospective_sizing_reason": "not_evaluable",
        "budget_reason": "not_evaluable",
        "filter_sizing": NOT_EVALUABLE,
        "filter_budget": NOT_EVALUABLE,
    }


def _invalid_balance_sizing(reason, equity, prices, position, config) -> dict:
    spot = position.spot if position is not None else ZERO
    short = position.short if position is not None else ZERO
    target_usdt = max(ZERO, equity) * config.target_fraction
    target_quantity_value = (
        target_usdt / prices[0] if prices is not None and prices[0] > 0 else ZERO
    )
    return {
        "target_quantity": _decimal(target_quantity_value),
        "proposed_spot_side": None,
        "proposed_gross_spot": _decimal(ZERO),
        "proposed_net_spot": _decimal(spot),
        "proposed_futures_side": None,
        "proposed_futures_quantity": _decimal(ZERO),
        "proposed_short": _decimal(short),
        "proposed_spot_delta": _decimal(ZERO),
        "proposed_short_delta": _decimal(ZERO),
        "planned_hedge_error": _decimal(hedge_error(spot, short)),
        "unallocated_target_usdt": _decimal(
            max(ZERO, target_usdt - spot * (prices[0] if prices else ZERO))
        ),
        "budget_required_cash": _decimal(ZERO),
        "sizing_feasible": False,
        "sizing_reason": reason,
        "sizing_enforcement": None,
        "prospective_pair_feasible": None,
        "prospective_sizing_reason": reason,
        "budget_reason": reason,
        "filter_sizing": NOT_EVALUABLE,
        "filter_budget": FAIL,
    }


def _joint_sizing(backtest, equity, prices, rules, mark, position, available) -> dict:
    plan = joint_quantity(
        equity,
        prices[0],
        prices[1],
        mark,
        position.spot,
        position.short,
        available,
        rules[0],
        rules[1],
        backtest.config,
        existing_collateral=getattr(position, "collateral", None),
        existing_average=getattr(position, "average", None),
    )
    proposal = plan
    if not plan.feasible and plan.reason == "insufficient_cash":
        proposal = joint_quantity(
            equity,
            prices[0],
            prices[1],
            mark,
            position.spot,
            position.short,
            D("1E999"),
            rules[0],
            rules[1],
            backtest.config,
            existing_collateral=getattr(position, "collateral", None),
            existing_average=getattr(position, "average", None),
        )
    sizing_filter = PASS if plan.feasible or plan.reason == "insufficient_cash" else FAIL
    budget_filter = (
        PASS if plan.feasible else FAIL if plan.reason == "insufficient_cash" else NOT_EVALUABLE
    )
    return {
        "target_quantity": _decimal(equity * backtest.config.target_fraction / prices[0]),
        "proposed_spot_side": proposal.spot_side,
        "proposed_gross_spot": _decimal(proposal.spot_quantity),
        "proposed_net_spot": _decimal(proposal.spot_net_total),
        "proposed_futures_side": proposal.futures_side,
        "proposed_futures_quantity": _decimal(proposal.futures_quantity),
        "proposed_short": _decimal(proposal.short_total),
        "proposed_spot_delta": _decimal(proposal.spot_net_total - position.spot),
        "proposed_short_delta": _decimal(proposal.short_total - position.short),
        "planned_hedge_error": _decimal(proposal.hedge_error),
        "unallocated_target_usdt": _decimal(proposal.unallocated_target_usdt),
        "budget_required_cash": _decimal(proposal.required_cash),
        "sizing_feasible": plan.feasible,
        "sizing_reason": plan.reason,
        "sizing_enforcement": "joint_pair",
        "prospective_pair_feasible": proposal.feasible,
        "prospective_sizing_reason": proposal.reason,
        "budget_reason": "ok" if plan.feasible else plan.reason,
        "filter_sizing": sizing_filter,
        "filter_budget": budget_filter,
    }


def _legacy_sizing(backtest, symbol, equity, prices, rules, position, available) -> dict:
    target = target_quantity(equity, prices[0], position.spot, rules[0], backtest.config)
    quantity = floor_step(max(ZERO, target - position.spot), rules[0].step)
    fee = rules[0].taker_fee * backtest.config.cost_multiplier
    net_spot = position.spot + quantity * (D(1) - fee)
    short_total = floor_step(net_spot, rules[1].step)
    futures_quantity = max(ZERO, short_total - position.short)
    needed = backtest._required(symbol, quantity) if quantity > 0 else ZERO

    positive_increment = quantity > 0
    entry_valid = positive_increment and valid_quantity(quantity, prices[0], rules[0])
    sizing_reason = (
        "ok"
        if entry_valid
        else "no_positive_increment"
        if not positive_increment
        else "historical_quantity_filter"
    )
    prospective_reason = "ok"
    if not entry_valid:
        prospective_reason = sizing_reason
    elif not _planned_quantity_valid(quantity, prices[0], "buy", rules[0], backtest.config):
        prospective_reason = "spot_adverse_execution_filter"
    elif futures_quantity <= 0 or not _planned_quantity_valid(
        futures_quantity, prices[1], "sell", rules[1], backtest.config
    ):
        prospective_reason = "futures_quantity_filter"
    elif hedge_error(net_spot, short_total) > backtest.config.hedge_tolerance:
        prospective_reason = "hedge_tolerance"
    prospective_pair_feasible = prospective_reason == "ok"
    budget_ok = entry_valid and needed <= available
    feasible = entry_valid and budget_ok
    return {
        "target_quantity": _decimal(target),
        "proposed_spot_side": "buy" if quantity > 0 else None,
        "proposed_gross_spot": _decimal(quantity),
        "proposed_net_spot": _decimal(net_spot),
        "proposed_futures_side": "sell" if futures_quantity > 0 else None,
        "proposed_futures_quantity": _decimal(futures_quantity),
        "proposed_short": _decimal(short_total),
        "proposed_spot_delta": _decimal(net_spot - position.spot),
        "proposed_short_delta": _decimal(short_total - position.short),
        "planned_hedge_error": _decimal(hedge_error(net_spot, short_total)),
        "unallocated_target_usdt": _decimal(
            max(ZERO, equity * backtest.config.target_fraction - net_spot * prices[0])
        ),
        "budget_required_cash": _decimal(needed),
        "sizing_feasible": feasible,
        "sizing_reason": sizing_reason,
        "sizing_enforcement": "spot_entry_only",
        "prospective_pair_feasible": prospective_pair_feasible,
        "prospective_sizing_reason": prospective_reason,
        "budget_reason": "ok" if budget_ok else "insufficient_cash" if entry_valid else None,
        "filter_sizing": PASS if entry_valid else FAIL,
        "filter_budget": PASS if budget_ok else FAIL if entry_valid else NOT_EVALUABLE,
    }


def _sizing(
    backtest, symbol, equity, spot, future, mark, spot_rule, futures_rule, position, available
):
    if any(value is None for value in (spot, future, mark, spot_rule, futures_rule, position)):
        return _empty_sizing()
    prices = (spot.price, future.price)
    rules = (spot_rule, futures_rule)
    if equity <= 0:
        return _invalid_balance_sizing(
            "nonpositive_equity", equity, prices, position, backtest.config
        )
    if available < 0:
        return _invalid_balance_sizing(
            "negative_available_cash", equity, prices, position, backtest.config
        )
    if backtest.config.sizing_model == "joint_quantity":
        return _joint_sizing(backtest, equity, prices, rules, mark.close, position, available)
    return _legacy_sizing(backtest, symbol, equity, prices, rules, position, available)


def signal_diagnostics(backtest, symbol: str, equity_snapshot: Decimal) -> dict:
    """Evaluate all available entry filters without changing backtest state."""

    now = backtest.now
    raw_forecast = backtest.forecasts.get(symbol)
    forecast = (
        raw_forecast
        if raw_forecast is not None
        and raw_forecast.available_at <= now
        and raw_forecast.anchor <= now
        else None
    )
    raw_spot, raw_future = backtest._signal_prices(symbol)
    spot = _causal_reference(raw_spot, now)
    future = _causal_reference(raw_future, now)
    sizing_spot = _causal_reference(backtest.trades.get((symbol, "spot")), now)
    sizing_future = _causal_reference(backtest.trades.get((symbol, "futures")), now)
    raw_mark = backtest.marks.get(symbol)
    mark = (
        raw_mark
        if raw_mark is not None and raw_mark.available_at <= now and raw_mark.close_time <= now
        else None
    )
    spot_rule = backtest._rule(symbol, "spot")
    futures_rule = backtest._rule(symbol, "futures")
    pair = backtest.pairs[symbol]
    position = backtest.ledger.positions.get(symbol)
    available = backtest._available(symbol)

    state = pair.state.value if hasattr(pair.state, "value") else str(pair.state)
    active = state not in ("FLAT", "COOLDOWN")
    pending = bool(backtest._pending(symbol))
    closed_signals = bool(backtest._uses_closed_signals())
    coverage_available = symbol not in backtest.bad_symbols
    filters = {
        "state_active": FAIL if active else PASS,
        "cooldown": FAIL if now < pair.cooldown_until else PASS,
        "pending_orders": FAIL if pending else PASS,
        "debt": FAIL if backtest.ledger.debt > 0 or backtest.status == "insolvent" else PASS,
        "coverage": PASS if coverage_available else NOT_EVALUABLE,
        "forecast": NOT_EVALUABLE if forecast is None or not forecast.valid else PASS,
        "rules": NOT_EVALUABLE if spot_rule is None or futures_rule is None else PASS,
        "operational": (
            NOT_EVALUABLE
            if spot_rule is None or futures_rule is None
            else PASS
            if spot_rule.operational and futures_rule.operational
            else FAIL
        ),
        "mark": NOT_EVALUABLE if mark is None else PASS,
        "price_alignment": (
            NOT_EVALUABLE
            if spot is None or future is None
            else PASS
            if _prices_aligned(spot, future)
            else FAIL
        ),
        "freshness": (
            NOT_EVALUABLE
            if spot is None or future is None
            else PASS
            if backtest._fresh(symbol)
            else FAIL
        ),
    }

    rules_complete = spot_rule is not None and futures_rule is not None
    estimated_cost = (
        cycle_cost(spot_rule, futures_rule, backtest.config) if rules_complete else None
    )
    forecast_observed = forecast.value if forecast is not None else None
    forecast_value = forecast.value if forecast is not None and forecast.valid else None
    filters["funding"] = (
        NOT_EVALUABLE
        if forecast_value is None or estimated_cost is None
        else PASS
        if forecast_value > estimated_cost
        else FAIL
    )

    raw_basis = None
    if spot is not None and future is not None and spot.price > 0 and future.price > 0:
        raw_basis = basis(spot.price, future.price)
    basis_inputs_valid = (
        raw_basis is not None
        and filters["freshness"] == PASS
        and (filters["price_alignment"] == PASS or not closed_signals)
    )
    observed_basis = raw_basis if basis_inputs_valid else None
    filters["basis_negative"] = (
        NOT_EVALUABLE if observed_basis is None else FAIL if observed_basis < 0 else PASS
    )
    filters["basis_above_max"] = (
        NOT_EVALUABLE
        if observed_basis is None
        else FAIL
        if observed_basis > backtest.config.basis_max
        else PASS
    )

    sizing = _sizing(
        backtest,
        symbol,
        equity_snapshot,
        sizing_spot,
        sizing_future,
        mark,
        spot_rule,
        futures_rule,
        position,
        available,
    )
    filters["sizing"] = sizing["filter_sizing"]
    filters["budget"] = sizing["filter_budget"]

    latest_funding = max(
        (
            row
            for row in backtest.history.get(symbol, ())
            if row.funding_time <= now and row.available_at <= now
        ),
        key=lambda row: row.funding_time,
        default=None,
    )
    row = {
        "decision_kind": "entry",
        "decision_time": now,
        "filter_order": _json(FILTER_ORDER),
        "funding_filter_enabled": backtest.funding_filter_enabled,
        "forecast": _decimal(forecast_observed),
        "forecast_no_change": _decimal(forecast.no_change) if forecast is not None else None,
        "forecast_anchor": forecast.anchor if forecast is not None else None,
        "funding_anchor": forecast.anchor if forecast is not None else None,
        "forecast_available_at": forecast.available_at if forecast is not None else None,
        "forecast_history_start": forecast.history_start if forecast is not None else None,
        "forecast_reason": (
            forecast.reason
            if forecast is not None
            else "unavailable"
            if raw_forecast is not None
            else "missing"
        ),
        "latest_funding_time": latest_funding.funding_time if latest_funding else None,
        "latest_funding_available_at": latest_funding.available_at if latest_funding else None,
        "cost_spot_open_fee": _decimal(
            spot_rule.taker_fee * backtest.config.cost_multiplier if spot_rule else None
        ),
        "cost_spot_close_fee": _decimal(
            spot_rule.taker_fee * backtest.config.cost_multiplier if spot_rule else None
        ),
        "cost_futures_open_fee": _decimal(
            futures_rule.taker_fee * backtest.config.cost_multiplier if futures_rule else None
        ),
        "cost_futures_close_fee": _decimal(
            futures_rule.taker_fee * backtest.config.cost_multiplier if futures_rule else None
        ),
        "cost_slippage_per_order": _decimal(
            backtest.config.slippage * backtest.config.cost_multiplier
        ),
        "cost_slippage_total": _decimal(
            D(4) * backtest.config.slippage * backtest.config.cost_multiplier
        ),
        "estimated_cycle_cost": _decimal(estimated_cost),
        "forecast_cost_gap": _decimal(
            forecast_observed - estimated_cost
            if forecast_observed is not None and estimated_cost is not None
            else None
        ),
        **_price_fields("spot", spot),
        **_price_fields("futures", future),
        "sizing_spot_price": _decimal(sizing_spot.price) if sizing_spot else None,
        "sizing_spot_price_time": getattr(sizing_spot, "event_time", None),
        "sizing_futures_price": _decimal(sizing_future.price) if sizing_future else None,
        "sizing_futures_price_time": getattr(sizing_future, "event_time", None),
        "mark_price": _decimal(mark.close) if mark is not None else None,
        "mark_open_time": mark.open_time if mark is not None else None,
        "mark_time": mark.close_time if mark is not None else None,
        "mark_available_at": mark.available_at if mark is not None else None,
        "basis_raw": _decimal(raw_basis),
        "basis": _decimal(observed_basis),
        "price_alignment_enforced": closed_signals,
        "basis_negative": observed_basis < 0 if observed_basis is not None else None,
        "basis_above_max": (
            observed_basis > backtest.config.basis_max if observed_basis is not None else None
        ),
        "portfolio_state": state,
        "cooldown_until": pair.cooldown_until,
        "current_spot": _decimal(position.spot) if position is not None else None,
        "current_short": _decimal(position.short) if position is not None else None,
        "equity_snapshot": _decimal(equity_snapshot),
        "available_cash": _decimal(available),
        "target_usdt": _decimal(equity_snapshot * backtest.config.target_fraction),
        "data_valid": (
            bool(backtest._data_valid(symbol))
            if spot is not None and future is not None and mark is not None and rules_complete
            else None
        ),
        **sizing,
    }
    row.update({f"filter_{name}": filters[name] for name in FILTER_ORDER})
    row["filter_data_valid"] = (
        NOT_EVALUABLE
        if row["data_valid"] is None or not coverage_available
        else PASS
        if row["data_valid"]
        else FAIL
    )
    failures = [name for name in FILTER_ORDER if filters[name] == FAIL]
    unavailable = [name for name in FILTER_ORDER if filters[name] == NOT_EVALUABLE]
    row["simultaneous_rejections"] = _json(failures)
    row["simultaneous_not_evaluable"] = _json(unavailable)
    row["sequential_rejection"] = None
    for name in FILTER_ORDER:
        if name == "funding" and not backtest.funding_filter_enabled:
            continue
        if name == "price_alignment" and not closed_signals:
            continue
        if filters[name] == FAIL:
            row["sequential_rejection"] = name
            break
        if filters[name] == NOT_EVALUABLE:
            row["sequential_rejection"] = f"not_evaluable:{name}"
            break
    return row


def renewal_diagnostics(backtest, symbol: str, equity_snapshot: Decimal) -> dict:
    """Return diagnostics using only the filters applied by the renewal path."""

    row = signal_diagnostics(backtest, symbol, equity_snapshot)
    row["entry_filter_order"] = row["filter_order"]
    row["entry_simultaneous_rejections"] = row["simultaneous_rejections"]
    row["entry_simultaneous_not_evaluable"] = row["simultaneous_not_evaluable"]
    row["decision_kind"] = "renewal"
    row["entry_funding_cost_filter_applied"] = False
    row["entry_basis_filter_applied"] = False
    row["entry_sizing_filter_applied"] = False
    row["renewal_funding_threshold"] = "0"

    forecast_state = row["filter_forecast"]
    funding_positive = (
        NOT_EVALUABLE
        if forecast_state != PASS or row["forecast"] is None
        else PASS
        if D(row["forecast"]) > 0
        else FAIL
    )
    renewal_filters = {
        "state_holding": PASS if row["portfolio_state"] == "HOLDING" else FAIL,
        "data_valid": row["filter_data_valid"],
        "forecast": forecast_state,
        "debt": row["filter_debt"],
        "funding_positive": funding_positive,
    }
    row["filter_state_holding"] = renewal_filters["state_holding"]
    row["filter_funding_positive"] = funding_positive
    row["filter_order"] = _json(RENEWAL_FILTER_ORDER)
    row["simultaneous_rejections"] = _json(
        name for name in RENEWAL_FILTER_ORDER if renewal_filters[name] == FAIL
    )
    row["simultaneous_not_evaluable"] = _json(
        name for name in RENEWAL_FILTER_ORDER if renewal_filters[name] == NOT_EVALUABLE
    )
    row["sequential_rejection"] = None
    for name in RENEWAL_FILTER_ORDER:
        if name == "funding_positive" and not backtest.funding_filter_enabled:
            continue
        if renewal_filters[name] == FAIL:
            row["sequential_rejection"] = name
            break
        if renewal_filters[name] == NOT_EVALUABLE:
            row["sequential_rejection"] = f"not_evaluable:{name}"
            break

    if renewal_filters["state_holding"] == FAIL:
        row["renewal_status_kind"] = "skipped_not_holding"
    elif row["sequential_rejection"] is None:
        row["renewal_status_kind"] = "eligible"
    elif row["sequential_rejection"].startswith("not_evaluable:"):
        row["renewal_status_kind"] = "not_evaluable"
    else:
        row["renewal_status_kind"] = "rejected"
    return row
