"""Independent literal H1/H3 causal and equal-weight contracts."""
from decimal import Decimal as D

import numpy as np

from crypto_carry.config import SECOND, Config, timestamp
from crypto_carry.models import Funding
from scripts.analysis.signal import (
    h1_observations,
    h1_summaries,
    minute_flags,
    summarize_day,
)

MINUTE = 60 * SECOND


def market_inputs(n):
    return dict(
        spot=np.full(n, 100.0),
        future=np.full(n, 100.1),
        spot_volume=np.ones(n),
        future_volume=np.ones(n),
        mark_present=np.ones(n, dtype=bool),
        known_spot_missing=np.zeros(n, dtype=bool),
        known_future_missing=np.zeros(n, dtype=bool),
    )


def test_h3_keeps_full_forecast_zero_minutes_and_equal_asset_weights():
    times = np.arange(1440, dtype=np.int64) * MINUTE
    forecasts = [dict(time_ns=0, forecast="0.004", valid=True, anchor=0)]
    btc, eth = market_inputs(1440), market_inputs(1440)
    btc["future"][720:] = 99
    eth["future"][:] = 99
    results = [minute_flags(times, data, forecasts, D(".0034"), Config()) for data in (btc, eth)]
    daily = [summarize_day(times, flags, forecasts) for flags in results]
    assert daily[0]["eligible_minutes"] == 720
    assert daily[0]["opportunity"] == D(".002")
    assert daily[1]["opportunity"] == 0
    assert sum(r["opportunity"] for r in daily) / 2 == D(".001")


def test_h3_unknown_data_excludes_day_but_documented_closure_is_valid_zero():
    times = np.arange(1440, dtype=np.int64) * MINUTE
    forecasts = [dict(time_ns=0, forecast=".004", valid=True, anchor=0)]
    inputs = market_inputs(1440)
    inputs["spot"][12] = np.nan
    flags = minute_flags(times, inputs, forecasts, D(".0034"), Config())
    assert not summarize_day(times, flags, forecasts)["complete"]
    assert summarize_day(times, flags, forecasts)["opportunity"] is None
    inputs["known_spot_missing"][12] = True
    flags = minute_flags(times, inputs, forecasts, D(".0034"), Config())
    daily = summarize_day(times, flags, forecasts)
    assert daily["complete"]
    assert daily["eligible_minutes"] == 1439
    assert not flags["eligible"][12]


def test_h3_respects_millisecond_publication_and_does_not_use_future_forecasts():
    times = np.array([MINUTE, 2 * MINUTE], dtype=np.int64)
    forecasts = [
        dict(time_ns=0, forecast=".001", valid=True, anchor=0),
        dict(time_ns=MINUTE + 1_000_000, forecast=".004", valid=True, anchor=MINUTE),
        dict(time_ns=3 * MINUTE, forecast=".5", valid=True, anchor=3 * MINUTE),
    ]
    result = minute_flags(times, market_inputs(2), forecasts, D(".0034"), Config())
    assert list(result["eligible"]) == [False, True]
    assert list(result["forecast_index"]) == [0, 1]


def test_h3_exact_cost_and_basis_boundaries_and_zero_volume():
    times = np.arange(4, dtype=np.int64) * MINUTE
    forecasts = [dict(time_ns=0, forecast=".004", valid=True, anchor=0)]
    data = market_inputs(4)
    data["future"] = np.array([100, 100.5, 100.50000001, 100.1])
    data["spot_volume"][3] = 0
    flags = minute_flags(times, data, forecasts, D(".0034"), Config())
    assert list(flags["eligible"]) == [True, True, False, False]
    assert not minute_flags(times, data, forecasts, D(".004"), Config())["eligible"].any()


def test_h1_weights_assets_equally_despite_different_valid_counts():
    rows = [
        dict(
            symbol="BTCUSDT",
            time_ns=1,
            horizon_valid=True,
            absolute_error_ewma=".1",
            absolute_error_no_change=".2",
            reason="",
        ),
        dict(
            symbol="BTCUSDT",
            time_ns=2,
            horizon_valid=True,
            absolute_error_ewma=".1",
            absolute_error_no_change=".2",
            reason="",
        ),
        dict(
            symbol="ETHUSDT",
            time_ns=1,
            horizon_valid=True,
            absolute_error_ewma=".9",
            absolute_error_no_change="1",
            reason="",
        ),
        dict(
            symbol="ETHUSDT",
            time_ns=2,
            horizon_valid=False,
            absolute_error_ewma=None,
            absolute_error_no_change=None,
            reason="horizon_outside_sample",
        ),
    ]
    result = h1_summaries(rows, [("full", 0, 3)])
    equal = next(r for r in result if r["symbol"] == "EQUAL_WEIGHT")
    assert equal["mae_ewma"] == D(".5")
    assert equal["mae_no_change"] == D(".6")
    assert equal["valid_observations"] == 3
    assert equal["excluded_observations"] == 1


def test_h1_labels_exclude_funding_at_signal_and_keep_cross_regime_horizons():
    start = timestamp("2023-12-31T23:00:00Z")
    config = Config(start="2023-12-31T00:00:00Z", end="2024-01-03T00:00:00Z", horizon_hours=2)
    history = {
        s: [
            Funding(
                s,
                start + h * 3600 * SECOND,
                start + h * 3600 * SECOND + MINUTE,
                D(".001"),
                D(1),
                D(100),
                "fixture",
                True,
            )
            for h in range(4)
        ]
        for s in config.symbols
    }
    signals = [
        dict(
            symbol="BTCUSDT",
            time_ns=start,
            anchor=start,
            history_start=start,
            forecast=".002",
            no_change=".003",
            valid=True,
        )
    ]
    row = h1_observations(signals, history, config)[0]
    assert row["horizon_valid"]
    assert row["realized"] == D(".002")
    assert row["absolute_error_ewma"] == 0
    assert row["absolute_error_no_change"] == D(".001")
