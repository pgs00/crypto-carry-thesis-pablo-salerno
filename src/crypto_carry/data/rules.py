"""Point-in-time market rules with separate validity and knowledge times."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from ..config import Config, timestamp
from ..models import MarketRule, Tier

_VALUE_FIELDS = {
    "step",
    "tick",
    "min_qty",
    "max_qty",
    "min_notional",
    "max_notional",
    "taker_fee",
    "tiers",
    "liquidation_fee",
    "liquidation_regular_fee",
    "liquidation_fee_basis",
    "operational",
}
_META_FIELDS = {
    "symbol",
    "market",
    "rule_type",
    "valid_from",
    "valid_to",
    "known_from",
    "source_url",
    "source_publication_time",
    "retrieved_at",
    "evidence_status",
    "values",
}


def _time_ns(value: str | int | None) -> int | None:
    if value is None:
        return None
    return int(value) if isinstance(value, int) else timestamp(value)


class RuleBook:
    """Select rules that were both effective and knowable at a point in time."""

    def __init__(self, records: list[dict], allow_synthetic: bool = False):
        self.allow_synthetic = allow_synthetic
        self.records = [self._validate_record(record) for record in records]
        self.records.sort(key=lambda row: (row["symbol"], row["market"], row["valid_from"]))
        self._reject_overlaps()

    @staticmethod
    def _validate_record(raw: dict[str, Any]) -> dict[str, Any]:
        missing = _META_FIELDS - raw.keys()
        if missing:
            raise ValueError(f"Market-rule metadata missing: {sorted(missing)}")
        if raw["rule_type"] != "market":
            raise ValueError("Only complete market-rule snapshots are supported")
        values = raw["values"]
        missing_values = _VALUE_FIELDS - values.keys()
        if missing_values:
            raise ValueError(f"Market-rule values missing: {sorted(missing_values)}")
        status = raw["evidence_status"]
        if status not in {"verified", "synthetic", "unverified", "current_snapshot"}:
            raise ValueError(f"Unknown evidence status: {status}")
        record = dict(raw)
        record["valid_from"] = _time_ns(raw["valid_from"])
        record["valid_to"] = _time_ns(raw["valid_to"])
        record["known_from"] = _time_ns(raw["known_from"])
        record["source_publication_time"] = _time_ns(raw["source_publication_time"])
        record["retrieved_at"] = _time_ns(raw["retrieved_at"])
        if record["valid_to"] is not None and record["valid_to"] <= record["valid_from"]:
            raise ValueError("Market-rule valid_to must follow valid_from")
        rule = RuleBook._market_rule(record)
        for name in ("step", "tick", "min_qty", "max_qty", "min_notional", "max_notional"):
            if getattr(rule, name) <= 0:
                raise ValueError(f"Market-rule {name} must be positive")
        if rule.min_qty > rule.max_qty or rule.min_notional > rule.max_notional:
            raise ValueError("Market-rule minimum exceeds maximum")
        if rule.taker_fee < 0 or rule.liquidation_fee < 0:
            raise ValueError("Market-rule fees cannot be negative")
        for tier in rule.tiers:
            if tier.floor < 0 or tier.cap <= tier.floor or tier.rate < 0 or tier.deduction < 0:
                raise ValueError("Invalid maintenance tier")
        return record

    def _reject_overlaps(self) -> None:
        by_key: dict[tuple[str, str], list[dict]] = {}
        for record in self.records:
            by_key.setdefault((record["symbol"], record["market"]), []).append(record)
        for key, records in by_key.items():
            previous_end = None
            for index, record in enumerate(records):
                if index and (previous_end is None or record["valid_from"] < previous_end):
                    raise ValueError(f"Overlapping market-rule snapshots for {key}")
                previous_end = record["valid_to"]

    @staticmethod
    def _market_rule(record: dict) -> MarketRule:
        values = record["values"]
        tiers = tuple(
            Tier(
                floor=Decimal(str(tier["floor"])),
                cap=Decimal(str(tier["cap"])),
                rate=Decimal(str(tier["rate"])),
                deduction=Decimal(str(tier["deduction"])),
            )
            for tier in values["tiers"]
        )
        return MarketRule(
            symbol=record["symbol"],
            market=record["market"],
            step=Decimal(str(values["step"])),
            tick=Decimal(str(values["tick"])),
            min_qty=Decimal(str(values["min_qty"])),
            max_qty=Decimal(str(values["max_qty"])),
            min_notional=Decimal(str(values["min_notional"])),
            max_notional=Decimal(str(values["max_notional"])),
            taker_fee=Decimal(str(values["taker_fee"])),
            tiers=tiers,
            liquidation_fee=Decimal(str(values["liquidation_fee"])),
            liquidation_regular_fee=bool(values["liquidation_regular_fee"]),
            liquidation_fee_basis=str(values["liquidation_fee_basis"]),
            operational=bool(values["operational"]),
        )

    def get(self, symbol: str, market: str, time_ns: int) -> MarketRule | None:
        for record in self.records:
            if record["symbol"] != symbol or record["market"] != market:
                continue
            if time_ns < record["valid_from"] or time_ns < record["known_from"]:
                continue
            if record["valid_to"] is not None and time_ns >= record["valid_to"]:
                continue
            status = record["evidence_status"]
            if status in {"verified", "current_snapshot"} or (
                status == "synthetic" and self.allow_synthetic
            ):
                return self._market_rule(record)
        return None

    @classmethod
    def load(cls, path: str | Path, allow_synthetic: bool = False) -> RuleBook:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        records = payload["records"] if isinstance(payload, dict) else payload
        return cls(records, allow_synthetic=allow_synthetic)

    def transition_times(self, start: int, end: int) -> list[int]:
        boundaries: set[int] = set()
        for record in self.records:
            for value in (record["valid_from"], record["valid_to"], record["known_from"]):
                if value is not None and start <= value <= end:
                    boundaries.add(value)
        return sorted(boundaries)


def synthetic_rules(config: Config) -> RuleBook:
    """Return explicit illustrative rules for tests/demo, never historical claims."""
    records = []
    for symbol in config.symbols:
        for market, fee in (("spot", "0.001"), ("futures", "0.0005")):
            records.append(
                {
                    "symbol": symbol,
                    "market": market,
                    "rule_type": "market",
                    "valid_from": 0,
                    "valid_to": None,
                    "known_from": 0,
                    "source_url": "synthetic://illustrative-vip0",
                    "source_publication_time": 0,
                    "retrieved_at": 0,
                    "evidence_status": "synthetic",
                    "values": {
                        "step": "0.001",
                        "tick": "0.01",
                        "min_qty": "0.001",
                        "max_qty": "100000",
                        "min_notional": "5",
                        "max_notional": "100000000",
                        "taker_fee": fee,
                        "tiers": [
                            {"floor": "0", "cap": "50000", "rate": "0.004", "deduction": "0"},
                            {
                                "floor": "50000",
                                "cap": "100000000",
                                "rate": "0.005",
                                "deduction": "50",
                            },
                        ]
                        if market == "futures"
                        else [],
                        "liquidation_fee": "0.01" if market == "futures" else "0",
                        "liquidation_regular_fee": True,
                        "liquidation_fee_basis": "execution_notional",
                        "operational": True,
                    },
                }
            )
    return RuleBook(records, allow_synthetic=True)
