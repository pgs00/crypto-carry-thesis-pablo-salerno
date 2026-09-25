"""Exact execution rounding and ex-ante transaction cost calculations."""

from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal

from .config import Config, timestamp
from .models import MarketRule

D = Decimal
BTC_PROMO_START = timestamp("2022-07-08T14:00:00Z")
BTC_PROMO_END = timestamp("2023-03-22T00:00:00Z")


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
    """Contemporaneous entry estimate, independent of fees charged by the ledger."""
    spot_fee, future_fee = spot_rule.taker_fee, futures_rule.taker_fee
    if config.research_decision_fee_mode == "base_e3":
        spot_fee, future_fee = D("0.001"), D("0.0005")
    return config.cost_multiplier * (
        D(2) * spot_fee + D(2) * future_fee + D(4) * config.slippage
    )


def realized_taker_fee(rule: MarketRule, config: Config, time_ns: int) -> Decimal:
    """Unscaled realized tariff; minute executions use their window's start.

    BTC_SPOT_ZERO / PROMO_START / PROMO_END establishes only this interval.
    The 0.001 outside it is the explicit BASE_E3 assumption.
    """
    if (config.research_spot_fee_schedule == "btc_promo_2022_2023"
            and rule.symbol == "BTCUSDT" and rule.market == "spot"):
        return D(0) if BTC_PROMO_START <= time_ns < BTC_PROMO_END else D("0.001")
    return rule.taker_fee


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
