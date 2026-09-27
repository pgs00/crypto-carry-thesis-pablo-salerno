"""Comparison policies and incident grouping, independent of historical values."""

import numpy as np
import pyarrow as pa
import pytest

from scripts.intraday_risk_tables import compare_drawdowns, group_incidents
from scripts.rules_sensitivity_exposure import exposure_intervals


def test_nested_daily_zero_dd_does_not_hide_intraday_twenty_percent_loss():
    row = compare_drawdowns(np.array([0, 1, 2]), np.array([100., 80., 101.]),
                            np.array([2]), np.array([101.]), 100., 0)
    assert row["daily_drawdown"] == 0
    assert row["intraday_drawdown"] == pytest.approx(-.2)
    assert row["extra_drawdown_pp"] == pytest.approx(20.)
    assert row["intraday_loss_usdt"] == 20
    assert row["daily_zero_dd"]
    assert row["nested_daily_check"]


def test_interpolated_or_misaligned_series_cannot_pass_nested_daily_control():
    with pytest.raises(ValueError, match="daily"):
        compare_drawdowns(np.array([0, 2]), np.array([100., 100.]),
                          np.array([2]), np.array([101.]), 100., 0)


def test_unknown_value_at_original_daily_timestamp_cannot_claim_nesting():
    with pytest.raises(ValueError, match="daily"):
        compare_drawdowns(np.array([0, 1]), np.array([100., np.nan]),
                          np.array([1]), np.array([101.]), 100., 0)


def test_dust_inherited_from_before_cut_never_becomes_an_incident():
    positions = [dict(symbol=s, time_ns=0, spot=".001", short="0", state="FLAT")
                 for s in ("BTCUSDT", "ETHUSDT")]
    positions += [dict(symbol=s, time_ns=5, spot=".001", short="0", state="OPENING_SPOT")
                  for s in ("BTCUSDT", "ETHUSDT")]
    positions += [dict(symbol="BTCUSDT", time_ns=10, spot="1", short="0", state="OPENING_FUTURES"),
                  dict(symbol="BTCUSDT", time_ns=20, spot="1", short="1", state="HOLDING")]
    intervals = exposure_intervals(positions, 0, 30, ".005")
    incidents = group_incidents(intervals, [])
    assert len(incidents) == 1
    assert incidents[0]["symbol"] == "BTCUSDT"
    assert incidents[0]["start_ns"] == 10
    assert incidents[0]["end_ns"] == 20


def test_adjacent_unhedged_states_keep_distinct_cycles():
    intervals = [dict(symbol="BTCUSDT", exposure="unhedged", start_ns=10, end_ns=20,
                      state="OPENING_FUTURES"),
                 dict(symbol="BTCUSDT", exposure="unhedged", start_ns=20, end_ns=30,
                      state="OPENING_FUTURES")]
    events = [dict(symbol="BTCUSDT", time_ns=9, cycle_id="a"),
              dict(symbol="BTCUSDT", time_ns=20, cycle_id="b")]
    assert len(group_incidents(intervals, events)) == 2


def test_cycle_ties_keep_physical_order_instead_of_sorting_identifiers():
    intervals = [dict(symbol="BTCUSDT", exposure="unhedged", start_ns=10, end_ns=20,
                      state="OPENING_FUTURES")]
    events = [dict(symbol="BTCUSDT", time_ns=10, cycle_id="z_first"),
              dict(symbol="BTCUSDT", time_ns=10, cycle_id="a_last")]
    assert group_incidents(intervals, events)[0]["cycle_id"] == "a_last"


def test_first_year_without_financial_events_can_join_later_evidence():
    from scripts.intraday_risk_tables import identify_evidence

    empty = pa.table({"time_ns": pa.array([], type=pa.int64())})
    populated = pa.table({"time_ns": [10, 20]})
    exported = pa.concat_tables([identify_evidence(empty, "run_id", "source_a"),
                                 identify_evidence(populated, "run_id", "source_a")])
    assert exported.to_pylist() == [{"time_ns": 10, "run_id": "source_a"},
                                   {"time_ns": 20, "run_id": "source_a"}]


def test_two_minute_eligible_close_is_normal_not_an_extraordinary_delay():
    from scripts.intraday_risk_tables import classify_incident

    episode = dict(symbol="BTCUSDT", start_ns=0, end_ns=120_000_000_000, states="CLOSING")
    orders = [dict(symbol="BTCUSDT", time_ns=1, window_end=120_000_000_000,
                   order_id="close", action="submitted", purpose="close_spot")]
    assert classify_incident(episode, [], orders, []) == "sequential_close"


def test_failed_attempt_does_not_invent_partial_fill_evidence():
    from scripts.intraday_risk_tables import classify_incident

    episode = dict(symbol="BTCUSDT", start_ns=0, end_ns=60_000_000_000,
                   states="OPENING_FUTURES")
    events = [dict(kind="attempt_failed", cause="timeout")]
    assert classify_incident(episode, events, [], []) == "opening_with_failed_attempt"


def test_exposure_extrema_exclude_completed_hedge_but_keep_end_pre_price():
    from scripts.intraday_risk_tables import incident_exposure_mask

    values = {"time_ns": np.array([10, 15, 20, 20, 20]),
              "phase": np.array([2, 0, 1, 2, 2]),
              "BTCUSDT_spot": np.array([1., 1., 1., 1., 1.]),
              "BTCUSDT_short": np.array([0., 0., 0., 0., 1.])}
    # The fourth observation is an event on the other asset, still before BTC hedges.
    mask = incident_exposure_mask(values, "BTCUSDT", 20)
    assert mask.tolist() == [True, True, True, True, False]


def test_residual_after_close_is_not_minimum_active_exposure():
    from scripts.intraday_risk_tables import incident_exposure_mask

    values = {"time_ns": np.array([10, 20, 20]), "phase": np.array([2, 1, 2]),
              "ETHUSDT_spot": np.array([1., 1., .00001]),
              "ETHUSDT_short": np.array([0., 0., 0.])}
    assert incident_exposure_mask(values, "ETHUSDT", 20).tolist() == [True, True, False]
