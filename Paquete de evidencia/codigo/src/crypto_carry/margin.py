"""Isolated short margin maintenance and liquidation calculations."""

from decimal import Decimal

from .config import Config
from .models import MarketRule, Tier

D = Decimal


def _tier(notional: Decimal, rule: MarketRule) -> Tier:
    for tier in sorted(rule.tiers, key=lambda item: (item.floor, item.cap)):
        if tier.floor <= notional <= tier.cap:
            return tier
    raise ValueError(f"No maintenance tier covers notional {notional}")


def maintenance(q: Decimal, mark: Decimal, rule: MarketRule) -> Decimal:
    if q < 0 or mark < 0:
        raise ValueError("quantity and mark must be non-negative")
    if q == 0:
        return D(0)
    tier = _tier(q * mark, rule)
    return q * mark * tier.rate - tier.deduction


def liquidation_price(
    q: Decimal, average: Decimal, collateral: Decimal, rule: MarketRule
) -> Decimal | None:
    if q < 0:
        raise ValueError("quantity must be non-negative")
    if q == 0:
        return None
    candidates: list[Decimal] = []
    for tier in sorted(rule.tiers, key=lambda item: (item.floor, item.cap)):
        denominator = q * (D(1) + tier.rate)
        if denominator <= 0:
            continue
        candidate = (collateral + q * average + tier.deduction) / denominator
        if candidate >= 0 and tier.floor <= q * candidate <= tier.cap:
            candidates.append(candidate)
    if not candidates:
        raise ValueError("No maintenance tier contains the liquidation price")
    return min(candidates)


def margin_state(
    q: Decimal,
    average: Decimal,
    collateral: Decimal,
    mark: Decimal,
    rule: MarketRule,
    config: Config,
) -> dict:
    if mark <= 0:
        raise ValueError("mark must be positive")
    balance = collateral + q * (average - mark)
    requirement = maintenance(q, mark, rule)
    liquidation = liquidation_price(q, average, collateral, rule)
    liquidate = q > 0 and (
        balance <= 0 or balance <= requirement or (liquidation is not None and mark >= liquidation)
    )
    if requirement <= 0:
        ratio = D("Infinity") if balance <= 0 else D(0)
    else:
        ratio = requirement / balance if balance > 0 else D("Infinity")
    distance = None if liquidation is None else (liquidation - mark) / mark
    preventive = q > 0 and (
        liquidate
        or ratio >= config.margin_exit_ratio
        or (distance is not None and distance < config.liquidation_distance)
    )
    return {
        "balance": balance,
        "maintenance": requirement,
        "liquidation_price": liquidation,
        "ratio": ratio,
        "distance": distance,
        "liquidate": liquidate,
        "preventive": preventive,
    }
