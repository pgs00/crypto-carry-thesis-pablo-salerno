"""Explicit JSON encoding for trusted, inspectable checkpoint state (no pickle)."""

from collections import deque
from dataclasses import fields, is_dataclass
from decimal import Decimal
from enum import Enum

from . import models
from .forecast import Forecast
from .ledger import Position

TYPES = {
    cls.__name__: cls
    for cls in (
        models.Trade,
        models.MinutePrice,
        models.MinuteVolume,
        models.MinuteBar,
        models.Funding,
        models.Mark,
        models.Tier,
        models.MarketRule,
        models.Order,
        models.Fill,
        models.Pair,
        Forecast,
        Position,
    )
}


def encode(value):
    if isinstance(value, Decimal):
        return {"decimal": str(value)}
    if isinstance(value, Enum):
        return {"state": value.value}
    if is_dataclass(value):
        return {
            "type": type(value).__name__,
            "fields": {f.name: encode(getattr(value, f.name)) for f in fields(value)},
        }
    if isinstance(value, dict):
        return {"mapping": [[encode(k), encode(v)] for k, v in value.items()]}
    if isinstance(value, (set, tuple, deque)):
        return {type(value).__name__: [encode(v) for v in value]}
    if isinstance(value, list):
        return [encode(v) for v in value]
    return value


def decode(value):
    if isinstance(value, list):
        return [decode(v) for v in value]
    if not isinstance(value, dict):
        return value
    if "decimal" in value:
        return Decimal(value["decimal"])
    if "state" in value:
        return models.State(value["state"])
    if "type" in value:
        return TYPES[value["type"]](**{k: decode(v) for k, v in value["fields"].items()})
    if "mapping" in value:
        return {decode(k): decode(v) for k, v in value["mapping"]}
    for key, constructor in (("set", set), ("tuple", tuple), ("deque", deque)):
        if key in value:
            return constructor(decode(v) for v in value[key])
    raise ValueError("Unknown checkpoint encoding")
