"""Exact execution rounding and ex-ante transaction cost calculations."""

from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal

from .config import Config
from .models import MarketRule

D = Decimal


def floor_step(value: Decimal, step: Decimal) -> Decimal:
    if step <= 0:
        raise ValueError("step must be positive")
    return (value / step).to_integral_value(rounding=ROUND_FLOOR) * step


def execution_price(
    reference: Decimal, side: str, rule: MarketRule, config: Config
) -> tuple[Decimal, Decimal]:
    if reference <= 0 or rule.tick <= 0:
        raise ValueError("reference and tick must be positive")
    normalized_side = side.lower()
    if normalized_side == "buy":
        raw = reference * (D(1) + config.slippage * config.cost_multiplier)
        rounded = (raw / rule.tick).to_integral_value(rounding=ROUND_CEILING) * rule.tick
        return rounded, rounded - raw
    if normalized_side == "sell":
        raw = reference * (D(1) - config.slippage * config.cost_multiplier)
        rounded = (raw / rule.tick).to_integral_value(rounding=ROUND_FLOOR) * rule.tick
        return rounded, raw - rounded
    raise ValueError(f"Unknown side: {side}")


def cycle_cost(spot_rule: MarketRule, futures_rule: MarketRule, config: Config) -> Decimal:
    return config.cost_multiplier * (
        D(2) * spot_rule.taker_fee + D(2) * futures_rule.taker_fee + D(4) * config.slippage
    )


def valid_quantity(quantity: Decimal, price: Decimal, rule: MarketRule) -> bool:
    if not rule.operational or quantity <= 0 or price <= 0 or rule.step <= 0:
        return False
    notional = quantity * price
    return (
        quantity >= rule.min_qty
        and quantity <= rule.max_qty
        and notional >= rule.min_notional
        and notional <= rule.max_notional
        and quantity % rule.step == 0
    )
