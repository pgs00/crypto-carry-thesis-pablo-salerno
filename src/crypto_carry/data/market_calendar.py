"""Documented market closures for execution-window checks."""

from __future__ import annotations

from dataclasses import dataclass

from ..config import SECOND, timestamp

MINUTE = 60 * SECOND
BINANCE_SPOT_HALT_SOURCE = "https://www.binance.com/en/blog/from-our-ceo/6789340645608890113"


@dataclass(frozen=True)
class MarketClosure:
    symbols: tuple[str, ...]
    market: str
    start: int
    end: int
    source_url: str
    description: str


DOCUMENTED_CLOSURES = (
    MarketClosure(
        symbols=("BTCUSDT", "ETHUSDT"),
        market="spot",
        start=timestamp("2023-03-24T11:28:00Z"),
        end=timestamp("2023-03-24T14:00:00Z"),
        source_url=BINANCE_SPOT_HALT_SOURCE,
        description="Binance spot trading halt; full unavailable minutes after the 11:27 partial minute",
    ),
)


def closure_for_minute(symbol: str, market: str, open_time: int) -> MarketClosure | None:
    """Return the documented closure containing an aligned minute open."""
    if open_time % MINUTE:
        return None
    return next(
        (
            closure
            for closure in DOCUMENTED_CLOSURES
            if symbol in closure.symbols
            and market == closure.market
            and closure.start <= open_time < closure.end
        ),
        None,
    )
