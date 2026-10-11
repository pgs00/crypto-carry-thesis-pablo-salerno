"""Exactly the six independently authorized block-4 variants derived from BASE."""

from crypto_carry.config import Config
from scripts.signal_sensitivity import BASES, simulate, validate_identity  # noqa: F401

CHANGES = {
    "E_OHLC4": {"research_minute_price_model": "ohlc4"},
    "L01": {"research_execution_delay_seconds": 60},
    "L05": {"research_execution_delay_seconds": 300},
    "LC01": {"research_execution_delay_seconds": 60,
             "research_execution_delay_scope": "close_only"},
    "LC05": {"research_execution_delay_seconds": 300,
             "research_execution_delay_scope": "close_only"},
    "LC15": {"research_execution_delay_seconds": 900,
             "research_execution_delay_scope": "close_only"},
}
STAGES = {"precio": ("E_OHLC4",), "general": ("L01", "L05"),
          "cierre": ("LC01", "LC05", "LC15")}


def validate_variant(base: Config, scenario: str, candidate: Config) -> dict:
    if scenario not in CHANGES:
        raise ValueError(f"Unknown closed-matrix scenario: {scenario}")
    before, after = base.to_dict(), candidate.to_dict()
    diff = {k: {"before": before.get(k), "after": after.get(k)}
            for k in before.keys() | after.keys() if before.get(k) != after.get(k)}
    if after != base.changed(**CHANGES[scenario]).to_dict():
        raise ValueError(f"Unauthorized configuration diff for {scenario}: {diff}")
    return diff


def scenario_configs(base: Config) -> dict[str, Config]:
    return {name: base.changed(**changes) for name, changes in CHANGES.items()}
