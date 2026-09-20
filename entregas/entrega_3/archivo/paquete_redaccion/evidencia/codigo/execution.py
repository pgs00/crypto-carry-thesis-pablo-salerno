"""Execution gates do not infer liquidity or prices from missing observations."""

from decimal import Decimal

from .config import SECOND, Config
from .costs import floor_step
from .models import MinutePrice, Order, Trade

MINUTE = 60 * SECOND


def minute_window(submitted_at: int) -> tuple[int, int]:
    """Return the first full minute which does not precede submission."""
    start = ((submitted_at + MINUTE - 1) // MINUTE) * MINUTE
    return start, start + MINUTE


def minute_vwap(bar) -> Decimal | None:
    """Use actual quote/base totals; an inactive bar has no executable price."""
    return bar.quote_volume / bar.base_volume if bar.base_volume > 0 else None


def minute_capacity(
    remaining: Decimal,
    base_volume: Decimal,
    step: Decimal,
    participation: Decimal,
    used: Decimal = Decimal(0),
) -> Decimal:
    """Share aggregate capacity across orders of one instrument and interval."""
    available = max(Decimal(0), base_volume * participation - used)
    return floor_step(min(remaining, available), step)


def eligible_trade(order: Order, trade: Trade | MinutePrice) -> bool:
    return (
        order.status == "pending"
        and (order.symbol, order.market) == (trade.symbol, trade.market)
        and order.submitted_at < trade.event_time < order.deadline
        and trade.available_at == trade.event_time
    )


def observe_vwap(order: Order, trade: Trade, config: Config) -> None:
    if (
        eligible_trade(order, trade)
        and trade.event_time <= order.submitted_at + config.vwap_seconds * SECOND
    ):
        order.vwap_notional += trade.price * trade.quantity
        order.vwap_quantity += trade.quantity
        order.reference_ids.append(trade.trade_id)
