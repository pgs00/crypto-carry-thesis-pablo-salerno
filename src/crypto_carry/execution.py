"""Execution gates do not infer liquidity or prices from missing observations."""

from .config import SECOND, Config
from .models import Order, Trade


def eligible_trade(order: Order, trade: Trade) -> bool:
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
