"""Recalculate the published ejecucion scenarios from daily observations."""

from crypto_carry.config import Config

from .common import scenario_metrics

SCENARIOS = {
    "BASE_E3": {},
    "E_OHLC4": {"research_minute_price_model": "ohlc4"},
    "L01": {"research_execution_delay_seconds": 60},
    "L05": {"research_execution_delay_seconds": 300},
    "LC01": {
        "research_execution_delay_seconds": 60,
        "research_execution_delay_scope": "close_only",
    },
    "LC05": {
        "research_execution_delay_seconds": 300,
        "research_execution_delay_scope": "close_only",
    },
    "LC15": {
        "research_execution_delay_seconds": 900,
        "research_execution_delay_scope": "close_only",
    },
}


def recalculate(root):
    return {
        "results/ejecucion/evidencia/tablas/metricas.csv": scenario_metrics(
            root, "ejecucion", SCENARIOS
        )
    }


CHANGES = {key: value for key, value in SCENARIOS.items() if key != "BASE_E3"}


def validate_variant(base: Config, scenario: str, candidate: Config) -> dict:
    if scenario not in CHANGES:
        raise ValueError(f"Unknown closed-matrix scenario: {scenario}")
    before, after = base.to_dict(), candidate.to_dict()
    diff = {
        k: {"before": before.get(k), "after": after.get(k)}
        for k in before.keys() | after.keys()
        if before.get(k) != after.get(k)
    }
    if after != base.changed(**CHANGES[scenario]).to_dict():
        raise ValueError(f"Unauthorized configuration diff for {scenario}: {diff}")
    return diff


def scenario_configs(base: Config) -> dict[str, Config]:
    return {name: base.changed(**changes) for name, changes in CHANGES.items()}
