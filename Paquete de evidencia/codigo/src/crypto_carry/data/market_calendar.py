"""Source-backed market closures used only for data-quality accounting."""

from __future__ import annotations

from dataclasses import dataclass

from ..config import SECOND, iso, timestamp

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


def closed_minute_count(symbol: str, market: str, start: int, end: int) -> int:
    """Count documented full-minute opens in the half-open interval."""
    if start >= end:
        return 0
    count = 0
    for closure in DOCUMENTED_CLOSURES:
        if symbol not in closure.symbols or market != closure.market:
            continue
        lower = max(start, closure.start)
        upper = min(end, closure.end)
        first = ((lower + MINUTE - 1) // MINUTE) * MINUTE
        if first < upper:
            count += (upper - 1 - first) // MINUTE + 1
    return count


def quality_closures(symbols: tuple[str, ...], start: int, end: int) -> list[dict]:
    """Serialize closure intersections for ex-post data-quality disclosure."""
    result = []
    for closure in DOCUMENTED_CLOSURES:
        affected = tuple(symbol for symbol in symbols if symbol in closure.symbols)
        lower = max(start, closure.start)
        upper = min(end, closure.end)
        if not affected or lower >= upper:
            continue
        result.append(
            {
                "symbols": list(affected),
                "market": closure.market,
                "start": lower,
                "end": upper,
                "start_utc": iso(lower),
                "end_utc": iso(upper),
                "minutes": closed_minute_count(affected[0], closure.market, lower, upper),
                "source_url": closure.source_url,
                "description": closure.description,
            }
        )
    return result
