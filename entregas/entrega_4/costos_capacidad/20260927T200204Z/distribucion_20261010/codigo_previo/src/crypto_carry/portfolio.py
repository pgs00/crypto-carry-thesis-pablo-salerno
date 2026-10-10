"""Portfolio sizing, hedge drift, and conservative pre-trade cash estimates."""

from dataclasses import dataclass
from decimal import ROUND_CEILING, Decimal

from .config import Config
from .costs import execution_price, floor_step, valid_quantity
from .models import MarketRule

D = Decimal
ZERO = D(0)


@dataclass(frozen=True)
class JointQuantityPlan:
    """A pre-trade plan whose totals include the portfolio's existing inventory.

    ``spot_quantity`` is the gross base quantity submitted to spot. Under the
    project's current fee convention a spot buy receives less base, while a
    spot sell and both futures sides pay their fee in quote currency.
    """

    feasible: bool
    reason: str
    spot_side: str | None
    spot_quantity: Decimal
    futures_side: str | None
    futures_quantity: Decimal
    spot_net_total: Decimal
    short_total: Decimal
    hedge_error: Decimal
    required_cash: Decimal
    unallocated_target_usdt: Decimal


def _ceil_step(value: Decimal, step: Decimal) -> Decimal:
    if step <= 0:
        raise ValueError("step must be positive")
    return (value / step).to_integral_value(rounding=ROUND_CEILING) * step


def _unchanged_plan(
    reason: str,
    *,
    existing_spot: Decimal,
    existing_short: Decimal,
    target_usdt: Decimal,
    spot_price: Decimal,
) -> JointQuantityPlan:
    return JointQuantityPlan(
        feasible=False,
        reason=reason,
        spot_side=None,
        spot_quantity=ZERO,
        futures_side=None,
        futures_quantity=ZERO,
        spot_net_total=existing_spot,
        short_total=existing_short,
        hedge_error=hedge_error(existing_spot, existing_short),
        required_cash=ZERO,
        unallocated_target_usdt=max(ZERO, target_usdt - existing_spot * spot_price),
    )


def _trade_to_total(
    final_short: Decimal,
    existing_spot: Decimal,
    existing_short: Decimal,
    spot_rule: MarketRule,
    futures_rule: MarketRule,
    spot_buy_fee: Decimal,
) -> tuple[str | None, Decimal, Decimal, str | None, Decimal]:
    if final_short > existing_spot:
        spot_side = "buy"
        spot_quantity = _ceil_step(
            (final_short - existing_spot) / (D(1) - spot_buy_fee), spot_rule.step
        )
        spot_total = existing_spot + spot_quantity * (D(1) - spot_buy_fee)
    elif final_short < existing_spot:
        spot_quantity = floor_step(existing_spot - final_short, spot_rule.step)
        spot_side = "sell" if spot_quantity > 0 else None
        spot_total = existing_spot - spot_quantity
    else:
        spot_side = None
        spot_quantity = ZERO
        spot_total = existing_spot

    futures_delta = final_short - existing_short
    if futures_delta > 0:
        futures_side = "sell"
        futures_quantity = futures_delta
    elif futures_delta < 0:
        futures_side = "buy"
        futures_quantity = -futures_delta
    else:
        futures_side = None
        futures_quantity = ZERO
    return spot_side, spot_quantity, spot_total, futures_side, futures_quantity


def _joint_required_cash(
    spot_side: str | None,
    spot_quantity: Decimal,
    futures_side: str | None,
    futures_quantity: Decimal,
    spot_price: Decimal,
    futures_price: Decimal,
    mark: Decimal,
    spot_rule: MarketRule,
    futures_rule: MarketRule,
    config: Config,
    existing_short: Decimal,
    existing_collateral: Decimal | None,
    existing_average: Decimal | None,
) -> Decimal:
    required = ZERO
    if spot_side == "buy":
        spot_execution, _ = execution_price(spot_price, "buy", spot_rule, config)
        required += spot_quantity * spot_execution
    if futures_side == "sell":
        futures_execution, _ = execution_price(futures_price, "sell", futures_rule, config)
        futures_notional = futures_quantity * futures_execution
        required += futures_notional * futures_rule.taker_fee * config.cost_multiplier
        required += futures_notional / config.leverage
        required += max(ZERO, futures_quantity * (mark - futures_execution))
    elif futures_side == "buy":
        futures_execution, _ = execution_price(futures_price, "buy", futures_rule, config)
        closing_fee = (
            futures_quantity * futures_execution * futures_rule.taker_fee * config.cost_multiplier
        )
        if existing_collateral is None or existing_average is None:
            required += closing_fee
        else:
            released = existing_collateral * futures_quantity / existing_short
            realized = futures_quantity * (existing_average - futures_execution)
            required += max(ZERO, closing_fee - realized - released)
    return required


def _valid_at_planned_prices(
    side: str | None,
    quantity: Decimal,
    reference_price: Decimal,
    rule: MarketRule,
    config: Config,
) -> bool:
    if side is None:
        return True
    execution, _ = execution_price(reference_price, side, rule, config)
    return valid_quantity(quantity, reference_price, rule) and valid_quantity(
        quantity, execution, rule
    )


def joint_quantity(
    equity: Decimal,
    spot_price: Decimal,
    futures_price: Decimal,
    mark: Decimal,
    existing_spot: Decimal,
    existing_short: Decimal,
    available_cash: Decimal,
    spot_rule: MarketRule,
    futures_rule: MarketRule,
    config: Config,
    *,
    existing_collateral: Decimal | None = None,
    existing_average: Decimal | None = None,
) -> JointQuantityPlan:
    """Return the largest jointly executable hedge at or below the target.

    Market filters apply to the incremental orders. Hedge error applies to the
    final net spot inventory and total short. Cash follows :class:`Ledger`:
    opening a short reserves its fee, isolated margin and adverse opening loss.
    With the existing position metadata, a reduction reserves only the loss and
    fee left after its own released collateral and realized profit. Without that
    metadata it conservatively reserves the closing fee.
    """

    values = (
        equity,
        spot_price,
        futures_price,
        mark,
        existing_spot,
        existing_short,
        available_cash,
    )
    if any(not value.is_finite() for value in values):
        raise ValueError("joint sizing inputs must be finite")
    if spot_price <= 0 or futures_price <= 0 or mark <= 0:
        raise ValueError("joint sizing prices must be positive")
    if equity < 0 or existing_spot < 0 or existing_short < 0 or available_cash < 0:
        raise ValueError("joint sizing balances must be non-negative")
    if spot_rule.market.lower() != "spot" or futures_rule.market.lower() != "futures":
        raise ValueError("joint sizing requires spot and futures rules")
    if spot_rule.step <= 0 or futures_rule.step <= 0:
        raise ValueError("quantity steps must be positive")
    if (existing_collateral is None) != (existing_average is None):
        raise ValueError("existing collateral and average must be provided together")
    if existing_collateral is not None and existing_average is not None:
        if not existing_collateral.is_finite() or not existing_average.is_finite():
            raise ValueError("existing collateral and average must be finite")
        if existing_collateral < 0 or existing_average < 0:
            raise ValueError("existing collateral and average must be non-negative")

    spot_buy_fee = spot_rule.taker_fee * config.cost_multiplier
    futures_fee = futures_rule.taker_fee * config.cost_multiplier
    if not ZERO <= spot_buy_fee < D(1) or not ZERO <= futures_fee < D(1):
        raise ValueError("effective fee rates must be non-negative and less than one")

    target_usdt = equity * config.target_fraction
    desired_short = target_usdt / spot_price
    intended_increase = desired_short > existing_short
    if desired_short >= existing_short:
        candidate = existing_short + floor_step(desired_short - existing_short, futures_rule.step)
    else:
        candidate = existing_short - _ceil_step(existing_short - desired_short, futures_rule.step)

    saw_market_valid = False
    saw_hedge_valid = False
    while candidate >= 0:
        (
            spot_side,
            spot_quantity,
            spot_total,
            futures_side,
            futures_quantity,
        ) = _trade_to_total(
            candidate,
            existing_spot,
            existing_short,
            spot_rule,
            futures_rule,
            spot_buy_fee,
        )

        has_exposure = spot_total > 0 or candidate > 0
        has_order = spot_side is not None or futures_side is not None
        preserves_increase = not intended_increase or (
            candidate >= existing_short and spot_side != "sell" and has_order
        )
        within_target = spot_total <= desired_short
        spot_valid = _valid_at_planned_prices(
            spot_side, spot_quantity, spot_price, spot_rule, config
        )
        futures_valid = _valid_at_planned_prices(
            futures_side, futures_quantity, futures_price, futures_rule, config
        )
        if has_exposure and preserves_increase and within_target and spot_valid and futures_valid:
            saw_market_valid = True
            final_hedge_error = hedge_error(spot_total, candidate)
            if final_hedge_error <= config.hedge_tolerance:
                saw_hedge_valid = True
                cash = _joint_required_cash(
                    spot_side,
                    spot_quantity,
                    futures_side,
                    futures_quantity,
                    spot_price,
                    futures_price,
                    mark,
                    spot_rule,
                    futures_rule,
                    config,
                    existing_short,
                    existing_collateral,
                    existing_average,
                )
                if cash <= available_cash:
                    return JointQuantityPlan(
                        feasible=True,
                        reason="ok",
                        spot_side=spot_side,
                        spot_quantity=spot_quantity,
                        futures_side=futures_side,
                        futures_quantity=futures_quantity,
                        spot_net_total=spot_total,
                        short_total=candidate,
                        hedge_error=final_hedge_error,
                        required_cash=cash,
                        unallocated_target_usdt=max(ZERO, target_usdt - spot_total * spot_price),
                    )
        candidate -= futures_rule.step

    reason = (
        "insufficient_cash"
        if saw_hedge_valid
        else "hedge_tolerance"
        if saw_market_valid
        else "market_rules"
    )
    return _unchanged_plan(
        reason,
        existing_spot=existing_spot,
        existing_short=existing_short,
        target_usdt=target_usdt,
        spot_price=spot_price,
    )


def target_quantity(
    equity: Decimal,
    price: Decimal,
    existing_spot: Decimal,
    rule: MarketRule,
    config: Config,
) -> Decimal:
    if price <= 0 or equity <= 0:
        return max(existing_spot, D(0))
    desired = equity * config.target_fraction / price
    if desired < existing_spot:
        # Reductions must be possible; preserve only the non-tradable dust.
        reduction = floor_step(existing_spot - desired, rule.step)
        return existing_spot - reduction
    incremental = floor_step(max(D(0), desired - existing_spot), rule.step)
    return existing_spot + incremental


def needs_rebalance(spot_value: Decimal, equity: Decimal, config: Config) -> bool:
    target = equity * config.target_fraction
    if target <= 0:
        return False
    return abs(spot_value - target) / target > config.rebalance_threshold


def hedge_error(spot: Decimal, short: Decimal) -> Decimal:
    if spot < 0 or short < 0:
        raise ValueError("spot and short quantities must be non-negative")
    if spot == 0:
        return D(0) if short == 0 else D("Infinity")
    return abs(spot - short) / spot


def required_cash(
    quantity: Decimal,
    spot_price: Decimal,
    futures_price: Decimal,
    mark: Decimal,
    spot_rule: MarketRule,
    futures_rule: MarketRule,
    config: Config,
) -> Decimal:
    if quantity < 0 or futures_price <= 0 or mark <= 0:
        raise ValueError("quantities and prices must be valid")
    spot_execution, _ = execution_price(spot_price, "buy", spot_rule, config)
    net_spot = quantity * (D(1) - spot_rule.taker_fee * config.cost_multiplier)
    short = floor_step(net_spot, futures_rule.step)
    futures_execution, _ = execution_price(futures_price, "sell", futures_rule, config)
    futures_notional = short * futures_execution
    futures_fee = futures_notional * futures_rule.taker_fee * config.cost_multiplier
    collateral = futures_notional / config.leverage
    open_loss = max(D(0), short * (mark - futures_execution))
    return quantity * spot_execution + futures_fee + collateral + open_loss
