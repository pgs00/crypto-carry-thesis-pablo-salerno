"""Validated research parameters; no historical exchange rules are inferred here."""

import hashlib
import json
import re
import tomllib
from dataclasses import asdict, dataclass, fields, replace
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

SECOND = 1_000_000_000
HOUR = 3600 * SECOND
DAY = 24 * HOUR


def timestamp(value: str) -> int:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Timestamps must include a timezone")
    delta = parsed.astimezone(timezone.utc) - datetime(1970, 1, 1, tzinfo=timezone.utc)
    fraction = re.search(r"\d{2}:\d{2}:\d{2}\.(\d+)", value)
    digits = fraction.group(1) if fraction else ""
    if len(digits) > 9:
        raise ValueError("Timestamp precision exceeds nanoseconds")
    remainder = int(digits.ljust(9, "0")[6:9])
    return (delta.days * 86400 + delta.seconds) * SECOND + delta.microseconds * 1000 + remainder


def iso(value: int) -> str:
    seconds, nanos = divmod(int(value), SECOND)
    prefix = datetime.fromtimestamp(seconds, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    return f"{prefix}.{nanos:09d}Z"


@dataclass(frozen=True)
class Config:
    symbols: tuple[str, ...] = ("BTCUSDT", "ETHUSDT")
    history_start: str = "2020-08-11T00:00:00Z"
    start: str = "2022-01-01T00:00:00Z"
    end: str = "2026-09-01T00:00:00Z"
    capital: Decimal = Decimal("10000")
    window_hours: int = 336
    half_life_hours: int = 24
    horizon_hours: int = 168
    holding_hours: int = 168
    signal_delay_seconds: int = 60
    target_fraction: Decimal = Decimal("0.30")
    leverage: Decimal = Decimal("2")
    rebalance_threshold: Decimal = Decimal("0.05")
    slippage: Decimal = Decimal("0.0001")
    cost_multiplier: Decimal = Decimal("1")
    leg_delay_seconds: int = 1
    order_timeout_seconds: int = 30
    freshness_seconds: int = 60
    basis_min: Decimal = Decimal("0")
    basis_max: Decimal = Decimal("0.005")
    basis_exit: Decimal = Decimal("0.02")
    margin_exit_ratio: Decimal = Decimal("0.50")
    liquidation_distance: Decimal = Decimal("0.15")
    hedge_trigger: Decimal = Decimal("0.02")
    hedge_tolerance: Decimal = Decimal("0.005")
    correction_seconds: int = 60
    inactivity_seconds: int = 1800
    cooldown_hours: int = 24
    participation_seconds: int = 60
    execution_model: str = "first_trade"
    sizing_model: str = "legacy"
    signal_price_model: str = "execution_default"
    max_volume_participation: Decimal = Decimal("0.01")
    vwap_seconds: int = 5
    data_budget_bytes: int = 20_000_000_000
    data_dir: str = "data"
    rules_file: str = "data/rules/history.json"
    fee_profile: str = "VIP0_no_BNB_no_referral_documented_public_promotions"
    analysis_mode: str = "strict_historical"
    mark_gap_method: str = "strict"
    funding_proxy_stress_bps: Decimal = Decimal("0")
    research_futures_taker_fee: Decimal = Decimal("0.0005")
    research_maintenance_multiplier: Decimal = Decimal("1")
    research_liquidation_fee: Decimal = Decimal("0.0125")
    sample_start: str = "2024-01-01T00:00:00Z"
    sample_end: str = "2024-01-02T00:00:00Z"
    accounting_tolerance: Decimal = Decimal("0.00000001")

    def __post_init__(self) -> None:
        for field in fields(self):
            value = getattr(self, field.name)
            if isinstance(value, Decimal) and not value.is_finite():
                raise ValueError(f"{field.name} must be finite")
            if isinstance(field.default, int) and (
                not isinstance(value, int) or isinstance(value, bool)
            ):
                raise ValueError(f"{field.name} must be an integer")
        if self.symbols != ("BTCUSDT", "ETHUSDT"):
            raise ValueError("The research universe must be BTCUSDT and ETHUSDT")
        for key in (
            "capital",
            "window_hours",
            "half_life_hours",
            "horizon_hours",
            "holding_hours",
            "leverage",
            "order_timeout_seconds",
            "freshness_seconds",
            "correction_seconds",
            "inactivity_seconds",
            "cooldown_hours",
            "participation_seconds",
            "data_budget_bytes",
            "accounting_tolerance",
            "vwap_seconds",
            "basis_exit",
            "margin_exit_ratio",
            "liquidation_distance",
        ):
            if getattr(self, key) <= 0:
                raise ValueError(f"{key} must be positive")
        for key in ("signal_delay_seconds", "leg_delay_seconds", "slippage", "cost_multiplier"):
            if getattr(self, key) < 0:
                raise ValueError(f"{key} must be non-negative")
        if self.signal_delay_seconds < 60:
            raise ValueError("Funding availability cannot precede the 60 second convention")
        if self.execution_model not in ("first_trade", "vwap", "minute_open", "next_minute_vwap"):
            raise ValueError("Unknown execution model")
        if self.sizing_model not in ("legacy", "joint_quantity"):
            raise ValueError("Unknown sizing model")
        if self.signal_price_model not in ("execution_default", "closed_minute"):
            raise ValueError("Unknown signal price model")
        if self.signal_price_model == "closed_minute" and self.execution_model not in (
            "minute_open",
            "next_minute_vwap",
        ):
            raise ValueError("Closed-minute observations require a minute execution model")
        if not 0 < self.max_volume_participation <= 1:
            raise ValueError("max_volume_participation must be positive and at most one")
        if (
            self.execution_model == "next_minute_vwap"
            and self.analysis_mode != "prescribed_research"
        ):
            raise ValueError("next_minute_vwap requires prescribed_research analysis mode")
        if self.execution_model == "minute_open":
            if self.analysis_mode != "prescribed_research":
                raise ValueError("minute_open requires prescribed_research analysis mode")
            if self.order_timeout_seconds <= 60:
                raise ValueError("minute_open requires an order timeout greater than 60 seconds")
        if self.analysis_mode not in ("strict_historical", "prescribed_research"):
            raise ValueError("Unknown analysis mode")
        if self.mark_gap_method not in ("strict", "futures_scaled", "last_official"):
            raise ValueError("Unknown mark gap method")
        if self.mark_gap_method != "strict" and (
            self.analysis_mode != "prescribed_research"
            or self.execution_model != "next_minute_vwap"
        ):
            raise ValueError("Mark gap estimates require minute VWAP research mode")
        if (
            self.analysis_mode == "prescribed_research"
            and self.fee_profile != "prescribed_fixed_no_discounts"
        ):
            raise ValueError("Research fee_profile must be prescribed_fixed_no_discounts")
        if abs(self.funding_proxy_stress_bps) >= Decimal("10000"):
            raise ValueError("funding_proxy_stress_bps magnitude must be less than 10000")
        for key in ("research_futures_taker_fee", "research_liquidation_fee"):
            if not 0 <= getattr(self, key) < 1:
                raise ValueError(f"{key} must be non-negative and less than one")
        if self.research_maintenance_multiplier <= 0:
            raise ValueError("research_maintenance_multiplier must be positive")
        if self.analysis_mode == "strict_historical" and (
            self.funding_proxy_stress_bps != 0
            or self.research_futures_taker_fee != Decimal("0.0005")
            or self.research_maintenance_multiplier != 1
            or self.research_liquidation_fee != Decimal("0.0125")
        ):
            raise ValueError("Research parameters require prescribed_research analysis mode")
        if not 0 < self.target_fraction < Decimal("0.5"):
            raise ValueError("Invalid per-asset target")
        if not 0 <= self.hedge_tolerance < self.hedge_trigger < 1:
            raise ValueError("Invalid hedge thresholds")
        if not 0 <= self.rebalance_threshold < 1:
            raise ValueError("Invalid rebalance threshold")
        if not self.basis_min <= self.basis_max or self.vwap_seconds >= self.order_timeout_seconds:
            raise ValueError("Invalid basis or VWAP bounds")
        if timestamp(self.history_start) > timestamp(self.start) or timestamp(
            self.start
        ) >= timestamp(self.end):
            raise ValueError("Invalid history/evaluation range")
        if timestamp(self.sample_start) >= timestamp(self.sample_end):
            raise ValueError("Invalid sample range")
        for value in (self.data_dir, self.rules_file):
            p = Path(value)
            if p.is_absolute() or ".." in p.parts:
                raise ValueError("Project paths must remain relative to Backtesting")

    def changed(self, **values) -> "Config":
        return replace(self, **values)

    def to_dict(self) -> dict:
        return {
            k: str(v) if isinstance(v, Decimal) else list(v) if isinstance(v, tuple) else v
            for k, v in asdict(self).items()
        }

    def digest(self) -> str:
        return hashlib.sha256(json.dumps(self.to_dict(), sort_keys=True).encode()).hexdigest()

    def to_toml(self) -> str:
        return "\n".join(f"{k} = {json.dumps(v)}" for k, v in self.to_dict().items()) + "\n"

    @classmethod
    def from_dict(cls, values: dict) -> "Config":
        defaults = cls()
        unknown = set(values) - {f.name for f in fields(cls)}
        if unknown:
            raise ValueError(f"Unknown configuration fields: {sorted(unknown)}")
        converted = dict(values)
        for key, value in values.items():
            if isinstance(getattr(defaults, key), Decimal):
                converted[key] = Decimal(str(value))
        if "symbols" in converted:
            converted["symbols"] = tuple(converted["symbols"])
        return cls(**converted)

    @classmethod
    def load(cls, path: str | Path) -> "Config":
        with Path(path).open("rb") as stream:
            return cls.from_dict(tomllib.load(stream))
