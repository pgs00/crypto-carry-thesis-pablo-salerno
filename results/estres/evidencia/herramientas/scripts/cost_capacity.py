"""Authorized block-3 matrix, derived exclusively from an effective BASE configuration."""

from decimal import Decimal as D

from crypto_carry.config import Config
from scripts.signal_sensitivity import BASES, simulate, validate_identity  # noqa: F401

CHANGES = {
    "C02": {"cost_multiplier": D(2), "research_decision_fee_mode": "base_e3_total"},
    "C03": {"cost_multiplier": D(3), "research_decision_fee_mode": "base_e3_total"},
    "S02": {"slippage": D(".0002"), "research_decision_fee_mode": "base_e3_total"},
    "S05": {"slippage": D(".0005"), "research_decision_fee_mode": "base_e3_total"},
    "P050": {"max_volume_participation": D(".005")},
    "P025": {"max_volume_participation": D(".0025")},
    "A050": {"capital": D(50000)},
    "A100": {"capital": D(100000)},
}
STAGES = {"costos": ("C02", "C03", "S02", "S05"),
          "participacion": ("P050", "P025"), "capital": ("A050", "A100")}


def validate_variant(base: Config, scenario: str, candidate: Config) -> dict:
    if scenario not in CHANGES:
        raise ValueError(f"Unknown closed-matrix scenario: {scenario}")
    before, after = base.to_dict(), candidate.to_dict()
    diff = {key: {"before": before.get(key), "after": after.get(key)}
            for key in before.keys() | after.keys() if before.get(key) != after.get(key)}
    if after != base.changed(**CHANGES[scenario]).to_dict():
        raise ValueError(f"Unauthorized configuration diff for {scenario}: {diff}")
    return diff


def scenario_configs(base: Config) -> dict[str, Config]:
    return {name: base.changed(**changes) for name, changes in CHANGES.items()}
