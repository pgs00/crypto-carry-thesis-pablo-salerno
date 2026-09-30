"""Execution gates do not infer liquidity or prices from missing observations."""

from decimal import Decimal

from .config import SECOND, Config
from .costs import floor_step
from .models import MinutePrice, Order, Trade

MINUTE = 60 * SECOND
CLIENT_PURPOSES = frozenset((
    "open_spot", "open_perp", "increase_spot", "increase_perp", "reduce_perp",
    "reduce_spot", "correct", "close_perp", "close_spot",
))
CLOSE_PURPOSES = frozenset(("close_perp", "close_spot"))


def order_delay_seconds(config: Config, purpose: str) -> int:
    """Classify at order creation; exchange liquidations never get client delay."""
    if purpose not in CLIENT_PURPOSES | {"liquidate"}:
        raise ValueError(f"Unclassified execution purpose: {purpose}")
    included = purpose in (
        CLIENT_PURPOSES if config.research_execution_delay_scope == "all_client"
        else CLOSE_PURPOSES
    )
    return config.research_execution_delay_seconds if included else 0


def order_execution_metadata(config: Config, purpose: str, submitted_at: int) -> dict:
    applied = order_delay_seconds(config, purpose)
    return dict(
        reference_price_model=config.research_minute_price_model,
        delay_configured_seconds=config.research_execution_delay_seconds,
        delay_scope=config.research_execution_delay_scope,
        delay_applied_seconds=applied,
        generated_at=submitted_at,
        generation_definition="order creation in _submit; decision events recorded separately",
        eligible_at=submitted_at + applied * SECOND,
    )


def minute_ohlc4(bar) -> Decimal | None:
    """Closed-candle sensitivity; never an executable price without activity."""
    values = (bar.open, bar.high, bar.low, bar.close)
    if (any(not v.is_finite() or v <= 0 for v in values)
            or not bar.low <= bar.open <= bar.high
            or not bar.low <= bar.close <= bar.high):
        raise ValueError("Invalid OHLC execution candle")
    if bar.base_volume <= 0 or bar.quote_volume <= 0 or bar.trade_count <= 0:
        return None
    return sum(values) / Decimal(4)


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
