"""Closed, explicitly authorized block-2 matrix; no changes to the economic engine."""

from __future__ import annotations

from decimal import Decimal as D

from crypto_carry.config import Config, timestamp
from crypto_carry.data.prescribed import prescribed_rules
from crypto_carry.data.replay import iter_records
from crypto_carry.mark_gap_study import GapAuditedBacktest

BASES = {"conditional": "run_ad71d751b20623006c195ff3",
         "permanent": "run_dfea4b7ac1475668d5968c97"}
CHANGES = {
    "H072": {"horizon_hours": 72, "holding_hours": 72},
    "H336": {"horizon_hours": 336, "holding_hours": 336},
    "V012": {"half_life_hours": 12},
    "V048": {"half_life_hours": 48},
    "B025": {"basis_max": D("0.0025")},
    "B100": {"basis_max": D("0.01")},
}


def validate_variant(base: Config, scenario: str, candidate: Config) -> dict:
    if scenario not in CHANGES:
        raise ValueError(f"Unknown closed-matrix scenario: {scenario}")
    before, after = base.to_dict(), candidate.to_dict()
    diff = {key: {"before": before.get(key), "after": after.get(key)}
            for key in before.keys() | after.keys() if before.get(key) != after.get(key)}
    expected = base.changed(**CHANGES[scenario]).to_dict()
    if after != expected:
        raise ValueError(f"Unauthorized configuration diff for {scenario}: {diff}")
    return diff


def scenario_configs(base: Config) -> dict[str, Config]:
    return {name: base.changed(**changes) for name, changes in CHANGES.items()}


def validate_identity(manifest: dict, config: Config, code_hash: str, inputs: dict) -> None:
    if (manifest.get("config") != config.to_dict()
            or manifest.get("code_hash") != code_hash
            or manifest.get("input_hashes") != inputs):
        raise ValueError("Run identity differs in configuration, inputs or executing code")


def simulate(config: Config, data_root, strategy: str, inputs=None):
    """Same class, rules, reader arguments and warmup as the original batch route."""
    if strategy not in BASES:
        raise ValueError(f"Unknown strategy: {strategy}")
    backtest = GapAuditedBacktest(config, prescribed_rules(config), strategy,
                                strategy == "conditional", inputs or {})
    backtest.run(iter_records(
        data_root, timestamp(config.start), timestamp(config.end), config.window_hours + 24,
        data_dir=config.data_dir, execution_model=config.execution_model,
        include_closed_bars=True, mark_gap_method=config.mark_gap_method,
    ))
    return backtest
