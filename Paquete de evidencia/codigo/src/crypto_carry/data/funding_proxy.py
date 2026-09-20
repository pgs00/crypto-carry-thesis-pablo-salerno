"""Explicit causal settlement-mark assumptions; observed records stay immutable."""

from dataclasses import replace
from decimal import Decimal

from ..config import SECOND, Config, iso, timestamp
from ..models import Funding, Mark

MINUTE = 60 * SECOND


def resolve_funding_mark(record: Funding, mark: Mark | None, config: Config) -> Funding:
    """Keep exact marks, or use the previous closed minute in prescribed research.

    The stress sign refers to cash received by a short, not to price direction.
    Warmup events have no economic exposure and need rates/intervals only.
    """
    if config.analysis_mode != "prescribed_research":
        return record
    identity = f"{record.symbol} at {iso(record.funding_time)}"
    if record.settlement_mark_price is not None:
        if not record.settlement_mark_price.is_finite() or record.settlement_mark_price <= 0:
            raise ValueError(f"Invalid observed funding settlement mark: {identity}")
        return record
    if record.funding_time < timestamp(config.start):
        return replace(record, settlement_mark_method="not_required_before_start")
    boundary = record.funding_time // MINUTE * MINUTE
    if (
        mark is None
        or mark.symbol != record.symbol
        or mark.open_time != boundary - MINUTE
        or not boundary - 1_000_000 <= mark.close_time < boundary
        or not boundary <= mark.available_at <= record.funding_time
        or not mark.close.is_finite()
        or mark.close <= 0
    ):
        raise ValueError(f"Missing valid previous closed one-minute funding mark: {identity}")
    if not record.funding_rate.is_finite():
        raise ValueError(f"Invalid observed funding rate: {identity}")
    sign = (record.funding_rate > 0) - (record.funding_rate < 0)
    stress = config.funding_proxy_stress_bps
    price = mark.close * (Decimal(1) - sign * stress / Decimal(10000))
    return replace(
        record,
        settlement_mark_price=price,
        settlement_mark_method="previous_closed_1m",
        settlement_mark_source_file=mark.source_file,
        settlement_mark_close_time=mark.close_time,
        settlement_mark_available_at=mark.available_at,
        settlement_mark_proxy_base=mark.close,
        settlement_mark_stress_bps=stress,
    )
