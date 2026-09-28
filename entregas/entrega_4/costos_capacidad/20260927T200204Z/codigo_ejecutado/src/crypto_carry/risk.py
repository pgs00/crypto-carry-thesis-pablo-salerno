"""Risk predicates retain exact strict/non-strict boundaries from the specification."""

from decimal import Decimal

from .config import Config
from .margin import margin_state
from .portfolio import hedge_error


def basis(spot: Decimal, futures: Decimal) -> Decimal:
    return futures / spot - 1


def entry_basis(value: Decimal, config: Config) -> bool:
    return config.basis_min <= value <= config.basis_max


def position_risk(position, mark, rule, config: Config) -> str | None:
    if position.short <= 0:
        return None
    state = margin_state(position.short, position.average, position.collateral, mark, rule, config)
    if state["liquidate"]:
        return "liquidation"
    if state["preventive"]:
        return "margin"
    return None


def needs_hedge_correction(position, config: Config) -> bool:
    return hedge_error(position.spot, position.short) > config.hedge_trigger
