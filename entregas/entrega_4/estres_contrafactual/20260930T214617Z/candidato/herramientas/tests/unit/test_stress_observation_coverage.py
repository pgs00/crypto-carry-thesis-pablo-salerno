from decimal import Decimal as D

import pytest

from scripts.stress_counterfactual_audit import audit_observation_population

M = 60_000_000_000


def fixture():
    from crypto_carry.serialization import encode
    spec = dict(id="CF", kind="counterfactual", start=2 * M, end=4 * M)
    times = list(range(2 * M, 7 * M, M))
    observations = [dict(time_ns=t) for t in times]
    witnesses = [dict(time_ns=t, symbol=s) for t in times for s in ("BTCUSDT", "ETHUSDT")]
    state = dict(windows=[[2 * M, 6 * M]], factors=encode({}), observation_rows=len(observations))
    return spec, state, observations, witnesses


def test_every_window_minute_and_asset_is_required_independent_of_declared_counts():
    spec, state, snapshots, witnesses = fixture()
    assert audit_observation_population(spec, state, snapshots, witnesses, 0, 10 * M)["passed"]
    witnesses.pop()
    with pytest.raises(ValueError, match="opportunity"):
        audit_observation_population(spec, state, snapshots, witnesses, 0, 10 * M)


def test_omitted_snapshot_cannot_be_hidden_by_refreshing_its_counter():
    spec, state, snapshots, witnesses = fixture()
    snapshots.pop(1)
    state["observation_rows"] = len(snapshots)
    with pytest.raises(ValueError, match="snapshot"):
        audit_observation_population(spec, state, snapshots, witnesses, 0, 10 * M)


def test_shortened_declared_window_is_not_authoritative():
    spec, state, snapshots, witnesses = fixture()
    state["windows"][0][1] -= M
    with pytest.raises(ValueError, match="window"):
        audit_observation_population(spec, state, snapshots, witnesses, 0, 10 * M)


def test_zero_shock_keeps_its_factor_map_but_requires_no_observations():
    from crypto_carry.serialization import encode
    spec = dict(id="ZERO", kind="shock", magnitudes={"BTCUSDT": D(0)}, episodes=[("BTCUSDT", 0, M)])
    state = dict(windows=[], factors=encode({("BTCUSDT", u): D(1) for u in range(0, 61 * M, M)}),
                 observation_rows=0)
    assert audit_observation_population(spec, state, [], [], 0, 100 * M)["passed"]
