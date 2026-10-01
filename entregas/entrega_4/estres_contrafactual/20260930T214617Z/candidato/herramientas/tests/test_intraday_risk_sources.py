"""Accounting and availability breaks, with small independent fixtures."""

import numpy as np
import pytest

from scripts.intraday_risk_sources import (
    account_history,
    observation_grid,
    price_at,
    reconcile_daily,
)


def movement(time, event, kind, cash, *, spot="1", short="1", collateral="50", debt="0"):
    return dict(
        time_ns=time, event_id=event, kind=kind, symbol="BTCUSDT",
        free_spot=cash, free_futures="0", debt=debt, spot=spot,
        short=short, average="100", collateral=collateral,
    )


def test_funding_then_fill_preserves_pre_and_each_post_without_double_counting():
    rows = [
        movement(10, "opening", "fill", "50"),
        movement(20, "funding", "funding", "48"),
        movement(20, "closing", "fill", "97", short="0", collateral="0"),
    ]
    history = account_history(rows, 200, ("BTCUSDT",))
    grid = observation_grid(0, 31, history, daily_times=[29], step_ns=10)
    at_twenty = grid["time_ns"] == 20
    assert grid["state_index"][at_twenty].tolist() == [1, 2, 3]
    assert history["free_spot"][grid["state_index"][at_twenty]].tolist() == [50, 48, 97]
    assert history["asset_cash"][:, 0].tolist() == [0, -150, -152, -103]
    assert 29 in grid["time_ns"]
    assert grid["sequence"][at_twenty].tolist() == [0, 1, 2]


def test_simultaneous_state_changes_have_zero_duration_and_no_extra_minute():
    rows = [movement(10, "a", "funding", "100"), movement(10, "b", "funding", "99")]
    history = account_history(rows, 200, ("BTCUSDT",))
    grid = observation_grid(0, 21, history, daily_times=[], step_ns=10)
    assert grid["time_ns"].tolist() == [0, 10, 10, 10, 20]
    assert np.diff(grid["time_ns"]).sum() == 20


@pytest.mark.parametrize("change", ["missing", "backwards", "duplicate"])
def test_accounting_corruption_fails_instead_of_creating_zero_balances(change):
    rows = [movement(10, "a", "fill", "50"), movement(20, "b", "fill", "51")]
    if change == "missing":
        del rows[1]["collateral"]
    elif change == "backwards":
        rows[1]["time_ns"] = 9
    else:
        rows[1]["event_id"] = "a"
    with pytest.raises(ValueError):
        account_history(rows, 200, ("BTCUSDT",))


def test_closed_prices_never_read_future_or_inactive_spot_bar():
    prices = dict(
        available_at=np.array([10, 20, 30]),
        open_time=np.array([0, 10, 20]),
        end_time=np.array([10, 20, 30]),
        close=np.array([100.0, 120.0, 130.0]),
        base_volume=np.array([1.0, 0.0, 1.0]),
    )
    result = price_at(prices, np.array([9, 10, 20, 29, 30]), require_volume=True)
    assert np.isnan(result["price"][0])
    assert result["price"][1:].tolist() == [100, 100, 100, 130]
    assert result["available_at"][1:].tolist() == [10, 10, 10, 30]
    assert result["age_ns"][1:].tolist() == [0, 10, 19, 0]


def test_daily_reconciliation_uses_original_exact_timestamp_and_existing_tolerance():
    expected = [dict(time_ns="29", equity="101")]
    records = reconcile_daily(expected, np.array([20, 29, 30]), np.array([80., 101., 90.]))
    assert records[0]["ok"] is True
    assert records[0]["residual_usdt"] == 0
    with pytest.raises(ValueError, match="reconciliation"):
        reconcile_daily(expected, np.array([29]), np.array([101.00000002]))
    with pytest.raises(ValueError, match="missing daily"):
        reconcile_daily(expected, np.array([30]), np.array([101.]))
