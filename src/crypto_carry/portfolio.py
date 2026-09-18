"""Portfolio sizing, hedge drift, and conservative pre-trade cash estimates."""

from decimal import Decimal

from .config import Config
from .costs import execution_price, floor_step
from .models import MarketRule

D = Decimal


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
