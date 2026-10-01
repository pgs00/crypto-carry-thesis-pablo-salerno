"""Pure, opt-in transformations for the approved block-5 market scenarios.

Only closed spot bars are changed. Source observations stay immutable. The
caller owns approval authentication; these functions also accept small fixtures.
"""

from dataclasses import replace
from decimal import Decimal as D

from ..config import SECOND
from ..models import MinuteBar

MINUTE = 60 * SECOND
RECOVERY = 60 * MINUTE


def compile_shock(episodes, magnitudes):
    """Map aligned bar opens to the max-intensity envelope, never compounded."""
    for magnitude in magnitudes.values():
        if not magnitude.is_finite() or not D(0) <= magnitude < 1:
            raise ValueError("Shock magnitude must be a finite fraction in [0,1)")
    intensity = {}
    for symbol, start, end in episodes:
        if end < start or symbol not in magnitudes:
            raise ValueError("Invalid shock episode or missing asset magnitude")
        first = ((start + MINUTE - 1) // MINUTE) * MINUTE
        last = max(first + MINUTE, ((end + MINUTE - 1) // MINUTE) * MINUTE)
        for opening in range(first, last + RECOVERY, MINUTE):
            weight = D(1) if opening < last else D(1) - D(opening - last) / D(RECOVERY)
            key = symbol, opening
            intensity[key] = max(intensity.get(key, D(0)), weight)
    return {key: D(1) - magnitudes[key[0]] * weight for key, weight in intensity.items()}


def validate_bar(bar, *, decimal_roundoff=False):
    """Validate activity/OHLC/availability without forgiving a calendar gap."""
    prices = bar.open, bar.high, bar.low, bar.close
    if (bar.open_time % MINUTE or bar.end_time != bar.open_time + MINUTE
            or bar.available_at != bar.end_time
            or any(not p.is_finite() or p <= 0 for p in prices)
            or not bar.low <= bar.open <= bar.high or not bar.low <= bar.close <= bar.high):
        raise ValueError("Invalid or noncausal OHLC minute")
    if (not bar.base_volume.is_finite() or bar.base_volume < 0
            or not bar.quote_volume.is_finite() or bar.quote_volume < 0
            or bar.trade_count < 0
            or (bar.base_volume == 0) != (bar.quote_volume == 0)
            or (bar.base_volume > 0 and bar.trade_count == 0)):
        raise ValueError("Incoherent minute volume/activity")
    if bar.base_volume:
        vwap = bar.quote_volume / bar.base_volume
        # Only derived Decimal multiplication/division may differ by two ULPs.
        # Raw sources are tested strictly; no price or input is clipped.
        tolerance = D(2).scaleb(max(bar.high.adjusted(), vwap.adjusted()) - 27) \
            if decimal_roundoff else D(0)
        if not bar.low - tolerance <= vwap <= bar.high + tolerance:
            raise ValueError("VWAP outside OHLC")


def shock_bar(bar: MinuteBar, factor: D, scenario: str) -> MinuteBar:
    if bar.market != "spot" or factor == 1:
        return bar
    if not factor.is_finite() or not 0 < factor <= 1:
        raise ValueError("Invalid spot shock factor")
    validate_bar(bar)
    changed = replace(bar, open=bar.open * factor, high=bar.high * factor,
                      low=bar.low * factor, close=bar.close * factor,
                      quote_volume=bar.quote_volume * factor,
                      source_file=f"scenario:{scenario}|{bar.source_file}")
    validate_bar(changed, decimal_roundoff=True)
    return changed


def counterfactual_bar(future: MinuteBar, anchor_spot: D, anchor_future: D,
                       volume: D, trade_count: int, scenario: str) -> MinuteBar:
    validate_bar(future)
    if future.market != "futures" or future.base_volume <= 0:
        raise ValueError("Counterfactual requires a positive-volume future minute")
    if (any(not x.is_finite() or x <= 0 for x in (anchor_spot, anchor_future))
            or not volume.is_finite() or volume < 0 or trade_count < 0
            or (volume > 0 and trade_count < 1) or (volume == 0 and trade_count != 0)):
        raise ValueError("Invalid counterfactual anchor or hypothetical activity")
    ratio = anchor_spot / anchor_future
    vwap = ratio * (future.quote_volume / future.base_volume)
    changed = replace(future, market="spot", open=ratio * future.open,
                      high=ratio * future.high, low=ratio * future.low,
                      close=ratio * future.close, base_volume=volume,
                      quote_volume=volume * vwap, trade_count=trade_count,
                      source_file=f"scenario:{scenario}|{future.source_file}")
    validate_bar(changed, decimal_roundoff=True)
    return changed
