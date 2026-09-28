"""Closed-matrix and economic-contract regression tests for Entrega 4 block 2."""

import importlib.util
from decimal import Decimal as D
from pathlib import Path

import pytest

from crypto_carry.config import HOUR, SECOND, Config, timestamp
from crypto_carry.evaluation import forecast_evaluation
from crypto_carry.forecast import forecast, weight
from crypto_carry.models import Funding
from crypto_carry.risk import entry_basis

ROOT = Path(__file__).resolve().parents[2]


def test_closed_matrix_rejects_combined_dimension_and_preserves_base():
    assert importlib.util.find_spec("scripts.signal_sensitivity") is not None, (
        "The closed-matrix validator has not been implemented"
    )
    from scripts.signal_sensitivity import scenario_configs, validate_variant

    base = Config.load(ROOT / "configs/entrega_4/reglas_historicas/BASE_E3.toml")
    before = base.to_dict()
    scenarios = scenario_configs(base)
    expected = {
        "H072": {"horizon_hours": 72, "holding_hours": 72},
        "H336": {"horizon_hours": 336, "holding_hours": 336},
        "V012": {"half_life_hours": 12},
        "V048": {"half_life_hours": 48},
        "B025": {"basis_max": D("0.0025")},
        "B100": {"basis_max": D("0.01")},
    }
    assert list(scenarios) == list(expected)
    for name, config in scenarios.items():
        diff = validate_variant(base, name, config)
        assert set(diff) == set(expected[name])
        for field, value in expected[name].items():
            assert getattr(config, field) == value
        assert config.window_hours == 336
        assert config.window_hours + 24 == 360
        assert config.execution_model == "next_minute_vwap"
        assert config.sizing_model == "joint_quantity"
        assert config.order_timeout_seconds == 120
        assert config.mark_gap_method == "futures_scaled"
        assert config.signal_delay_seconds == 60
        assert config.accounting_tolerance == D("1E-8")
        with pytest.raises(ValueError, match="diff"):
            validate_variant(base, name, config.changed(cost_multiplier=D(2)))
    with pytest.raises(ValueError, match="diff"):
        validate_variant(base, "H072", scenarios["H072"].changed(half_life_hours=12))
    with pytest.raises(ValueError):
        validate_variant(base, "H072", scenarios["H072"].changed(holding_hours=168))
    assert base.to_dict() == before


@pytest.mark.parametrize("horizon", [72, 168, 336])
def test_irregular_intervals_forecast_scaling_and_causal_availability(horizon):
    start = timestamp("2024-01-01T00:00:00Z")
    hours = [0]
    for step in [8, 4, 12] * 15:
        hours.append(hours[-1] + step)
    history = [
        Funding("BTCUSDT", start + h * HOUR, start + h * HOUR + 60 * SECOND,
                D("0.0001") * D(h - hours[i-1] if i else 8),
                D(h - hours[i-1] if i else 8), D(100), "synthetic", True)
        for i, h in enumerate(hours)
    ]
    config = Config(horizon_hours=horizon)
    anchor = start + 360 * HOUR
    result = forecast(history, anchor, anchor + 60 * SECOND, config)
    assert result.valid
    # Decimal EWMA divisions round at the existing 28-digit context.
    assert result.value.quantize(D("1E-26")) == D(horizon) * D("0.0001")
    assert result.no_change == D(horizon) * D("0.0001")
    assert not forecast(history, anchor, anchor + 60 * SECOND - 1, config).valid
    assert weight(D(0), D(12)) == 1
    assert weight(D(12), D(12)) == D("0.5")
    assert weight(D(48), D(48)) == D("0.5")


@pytest.mark.parametrize("horizon,expected", [(72, .006), (168, .014), (336, .030)])
def test_h1_uses_signal_time_and_real_irregular_target_not_scaled_target(horizon, expected):
    start = timestamp("2024-01-01T00:00:00Z")
    offsets = [0, 36*HOUR, 72*HOUR+30*SECOND, 144*HOUR, 336*HOUR+30*SECOND, 337*HOUR]
    funding = [
        Funding("BTCUSDT", start+t, start+t+60*SECOND, D(rate),
                D(t-offsets[i-1])/HOUR if i else D(8), D(100), "synthetic", True)
        for i, (t, rate) in enumerate(zip(offsets, [".001", ".002", ".004", ".008", ".016", ".032"]))
    ]
    signal = dict(symbol="BTCUSDT", time_ns=start+60*SECOND, anchor=start,
                  history_start=start-336*HOUR, forecast=".01", no_change=".02", valid=True)
    config = Config(start="2024-01-01T00:00:00Z", end="2024-02-01T00:00:00Z",
                    horizon_hours=horizon)
    row = forecast_evaluation([signal], funding, config).iloc[0]
    assert row.realized == pytest.approx(expected)
    assert row.horizon_end == start + 60*SECOND + horizon*HOUR
    invalid = forecast_evaluation([dict(signal, valid=False, forecast="0")], funding, config).iloc[0]
    assert not invalid.horizon_valid and invalid.reason == "invalid_forecast_history"
    # Equality at the global exclusive end is excluded, even if a rate exists there.
    boundary = dict(signal, time_ns=timestamp(config.end)-horizon*HOUR)
    outside = forecast_evaluation([boundary], funding, config).iloc[0]
    assert not outside.horizon_valid and outside.reason == "horizon_outside_sample"


@pytest.mark.parametrize("ceiling", ["0.0025", "0.005", "0.01"])
def test_basis_inclusive_bounds_and_original_stop(ceiling):
    config = Config(basis_max=D(ceiling))
    assert not entry_basis(D("-1E-20"), config)
    assert entry_basis(D(0), config)
    assert entry_basis(D(ceiling), config)
    assert not entry_basis(D(ceiling)+D("1E-20"), config)
    assert config.basis_exit == D("0.02")


def test_resume_rejects_config_code_or_input_change():
    from scripts import signal_sensitivity as sensitivity

    assert hasattr(sensitivity, "validate_identity"), "resume identity guard is missing"
    base = Config.load(ROOT / "configs/entrega_4/reglas_historicas/BASE_E3.toml")
    config = base.changed(horizon_hours=72, holding_hours=72)
    manifest = dict(config=config.to_dict(), code_hash="code-a", input_hashes={"source": "a"})
    sensitivity.validate_identity(manifest, config, "code-a", {"source": "a"})
    for candidate, code, inputs in [
        (config.changed(half_life_hours=12), "code-a", {"source": "a"}),
        (config.changed(basis_max=D(".01")), "code-a", {"source": "a"}),
        (config, "code-b", {"source": "a"}),
        (config, "code-a", {"source": "b"}),
    ]:
        with pytest.raises(ValueError, match="identity"):
            sensitivity.validate_identity(manifest, candidate, code, inputs)
