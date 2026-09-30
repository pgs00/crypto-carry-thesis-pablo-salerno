"""Timestamp grouping preserves all physical events across storage partitions."""

from dataclasses import dataclass
from itertools import groupby
from typing import Iterable

from .models import Funding


@dataclass(frozen=True)
class DataGap:
    symbol: str
    available_at: int
    reason: str
    resolved: bool = False


def event_time(record) -> int:
    return record.funding_time if isinstance(record, Funding) else record.available_at


def event_key(record) -> tuple:
    trade_id = str(getattr(record, "trade_id", getattr(record, "reference_id", "")))
    ordered_id = trade_id.zfill(30) if trade_id.isdecimal() else trade_id
    return event_time(record), record.symbol, type(record).__name__, ordered_id


def group_events(records: Iterable) -> Iterable[tuple[int, list]]:
    previous = -1
    for time_ns, group in groupby(records, key=event_time):
        if time_ns < previous:
            raise ValueError("Replay input is not chronologically ordered")
        previous = time_ns
        yield time_ns, sorted(group, key=event_key)
