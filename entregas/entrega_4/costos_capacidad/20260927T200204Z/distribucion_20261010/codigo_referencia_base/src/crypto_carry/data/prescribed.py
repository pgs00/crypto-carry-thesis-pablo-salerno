"""Versioned model constraints for the explicitly prescribed research scenario."""

from __future__ import annotations

from copy import deepcopy
from decimal import Decimal

from ..config import Config
from .rules import RuleBook

_DECLARED_AT = "2026-09-18T00:00:00Z"
_VERSION = "prescribed-research-rules-v1"
_PROVENANCE = [
    "docs/research/public_rules_alternatives_20260918.json",
    "docs/research/public_rules_alternatives_20260918.md",
    "docs/research/fees_followup_20260918.md",
    "docs/research/historical_market_rules.md",
    "docs/research/methodology_two_days_20260918.md",
]

_MARKET_VALUES = {
    ("BTCUSDT", "spot"): ("0.00001", "0.01", "0.00001", "128.52621715", "10", "9000000"),
    ("ETHUSDT", "spot"): ("0.0001", "0.01", "0.0001", "3277.54882761", "10", "9000000"),
    ("BTCUSDT", "futures"): ("0.001", "0.1", "0.001", "120", "100", "100000000"),
    ("ETHUSDT", "futures"): ("0.001", "0.01", "0.001", "2000", "20", "100000000"),
}


def _records(config: Config) -> list[dict]:
    multiplier = config.research_maintenance_multiplier
    records = []
    for (symbol, market), values in _MARKET_VALUES.items():
        step, tick, min_qty, max_qty, min_notional, max_notional = values
        if market == "futures":
            first_rate = Decimal("0.004") if symbol == "BTCUSDT" else Decimal("0.0065")
            deduction = Decimal("300") if symbol == "BTCUSDT" else Decimal("175")
            tiers = [
                {
                    "floor": "0",
                    "cap": "50000",
                    "rate": str(first_rate * multiplier),
                    "deduction": "0",
                },
                {
                    "floor": "50000",
                    "cap": "100000000",
                    "rate": str(Decimal("0.01") * multiplier),
                    "deduction": str(deduction * multiplier),
                },
            ]
            fee = config.research_futures_taker_fee
            liquidation_fee = config.research_liquidation_fee
        else:
            tiers = []
            fee = Decimal("0.001")
            liquidation_fee = Decimal("0")
        records.append(
            {
                "symbol": symbol,
                "market": market,
                "rule_type": "market",
                "valid_from": config.start,
                "valid_to": config.end,
                "known_from": _DECLARED_AT,
                "source_url": _PROVENANCE[0],
                "source_publication_time": _DECLARED_AT,
                "retrieved_at": _DECLARED_AT,
                "evidence_status": "prescribed",
                "values": {
                    "step": step,
                    "tick": tick,
                    "min_qty": min_qty,
                    "max_qty": max_qty,
                    "min_notional": min_notional,
                    "max_notional": max_notional,
                    "taker_fee": str(fee),
                    "tiers": tiers,
                    "liquidation_fee": str(liquidation_fee),
                    "liquidation_regular_fee": True,
                    "liquidation_fee_basis": "execution_notional",
                    "operational": True,
                },
            }
        )
    return records


def prescribed_rules(config: Config) -> RuleBook:
    """Build the prescribed rulebook only for an explicitly selected research run."""
    if config.analysis_mode != "prescribed_research":
        raise ValueError("Prescribed rules require prescribed_research analysis mode")
    return RuleBook(_records(config), allow_prescribed=True)


def research_assumptions(config: Config) -> dict:
    """Return the reproducible, JSON-serializable declaration behind the rulebook."""
    if config.analysis_mode != "prescribed_research":
        raise ValueError("Research assumptions require prescribed_research analysis mode")
    declaration = {
        "version": _VERSION,
        "declared_at": _DECLARED_AT,
        "analysis_mode": config.analysis_mode,
        "fee_profile": config.fee_profile,
        "funding_proxy_stress_bps": str(config.funding_proxy_stress_bps),
        "methodology": {
            "historical_reconstruction": False,
            "rules_are_model_constraints": True,
            "constant_over_economic_window": True,
            "operational_availability_assumed": True,
            "observed_market_data_coverage_required": True,
            "fees": "fixed taker fees without discounts or promotions",
            "funding_marks": "keep observed settlement mark; if absent use previous closed one-minute mark available by settlement time",
            "funding_warmup": "missing pre-economic settlement marks stay absent; observed rates and independently verified intervals remain required",
            "funding_proxy_stress": "only substituted marks: previous_close * (1 - sign(funding_rate) * funding_proxy_stress_bps / 10000); positive stress worsens short cash flow",
            "funding_proxy_limits": "causal approximation, not an exact settlement price or guaranteed error bound; portfolio paths can change",
            "filters": "fixed model constraints for every order, including reductions; not historical exchange exemptions",
            "maintenance": "two prescribed continuous tiers; stress scales both rates and deductions",
            "liquidation": "execution notional charge plus regular taker fee",
        },
        "provenance": list(_PROVENANCE),
        "rules": deepcopy(_records(config)),
    }
    if config.execution_model == "minute_open":
        declaration["execution_model"] = "minute_open"
        declaration["methodology"]["minute_execution"] = {
            "source_price": "one-minute bar open assigned to the opening boundary",
            "first_trade_time_known": False,
            "fill_reference_id": "bar:<symbol>:<market>:<open_ns>",
            "fill_reference_is_trade_id": False,
            "order_timeout_seconds": config.order_timeout_seconds,
            "configured_leg_delay_seconds": config.leg_delay_seconds,
            "actual_leg_delay": (
                "fill at a strictly later available minute open; typically up to one "
                "additional minute per leg"
            ),
            "participation_volume": (
                "prior closed one-minute volume; approximation of rolling 60 seconds"
            ),
            "volume_available_before_bar_close": False,
            "liquidation_intrabar_path_modeled": False,
            "risk_mark": "last available closed one-minute mark",
        }
    elif config.execution_model == "next_minute_vwap":
        declaration["execution_model"] = "next_minute_vwap"
        declaration["methodology"]["minute_execution"] = {
            "source_price": "quote-volume divided by base-volume for the eligible minute",
            "eligible_window": "the first full minute beginning at or after submission",
            "fill_time": "eligible minute close, after price and volume are known",
            "volume_cap": (
                f"{config.max_volume_participation * 100:f}".rstrip("0").rstrip(".")
                + "% of observed eligible-minute base volume"
            ),
            "remainder": "unfilled quantity expires at the eligible minute close",
            "partial_fills": "one native fill event records the executable quantity",
            "signal_price": "last fully closed one-minute observation",
            "liquidation_intrabar_path_modeled": False,
            "risk_mark": "last available closed one-minute mark",
        }
    return declaration
