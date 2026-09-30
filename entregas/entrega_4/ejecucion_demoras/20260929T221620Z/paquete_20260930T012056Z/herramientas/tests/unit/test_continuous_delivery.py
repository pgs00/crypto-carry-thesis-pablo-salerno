from decimal import Decimal as D

import numpy as np
import pytest

from crypto_carry.config import DAY, SECOND, Config, timestamp
from crypto_carry.models import Funding
from scripts.continuous_delivery.hypotheses import (
    h1_observations,
    h1_summaries,
    minute_flags,
    summarize_day,
)
from scripts.continuous_delivery.portfolio import (
    cycle_rows,
    exposure_intervals,
    financial_daily,
    period_financials,
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


def test_exposure_intervals_carry_positions_across_regime_boundary_and_ignore_dust():
    split = timestamp("2024-01-01T00:00:00Z")
    rows = [
        dict(time_ns=split - MINUTE, symbol="BTCUSDT", spot="1", short="1", state="HOLDING"),
        dict(time_ns=split + MINUTE, symbol="BTCUSDT", spot="1", short="0", state="CLOSING_SPOT"),
        dict(
            time_ns=split + 2 * MINUTE,
            symbol="BTCUSDT",
            spot=".000001",
            short="0",
            state="COOLDOWN",
        ),
    ]
    result = exposure_intervals(rows, split, split + 3 * MINUTE, D(".005"), symbols=("BTCUSDT",))
    assert [(r["exposure"], r["seconds"]) for r in result] == [
        ("covered", D(60)),
        ("unhedged", D(60)),
        ("dust", D(60)),
    ]


def test_regime_pnl_uses_incoming_equity_and_differences_cumulative_components():
    split = timestamp("2024-01-01T00:00:00Z")
    config = Config(start="2023-12-31T00:00:00Z", end="2024-01-02T00:00:00Z")
    rows = [
        dict(
            time_ns=split - 1,
            equity="10100",
            free_spot="10100",
            free_futures="0",
            debt="0",
            BTCUSDT_realized_spot="100",
        ),
        dict(
            time_ns=split + DAY - 1,
            equity="10150",
            free_spot="10150",
            free_futures="0",
            debt="0",
            BTCUSDT_realized_spot="150",
        ),
    ]
    daily, assets = financial_daily(rows, config)
    assert daily[1]["net_pnl_usdt"] == D(50)
    assert daily[1]["spot_pnl_usdt"] == D(50)
    periods = period_financials(daily, assets, config, [("late", split, split + DAY)])
    assert periods[0]["starting_equity_usdt"] == D(10100)
    assert periods[0]["net_pnl_usdt"] == D(50)
    assert periods[0]["net_return"] == pytest.approx(50 / 10100)


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


def test_cycle_closes_at_first_terminal_event_not_later_repeated_dust_unwind():
    events = [
        dict(
            symbol="BTCUSDT", cycle_id="one", time_ns=t, kind="transition", cause=cause, state=state
        )
        for t, cause, state in (
            (1, "entry", "OPENING_SPOT"),
            (2, "opening_complete", "HOLDING"),
            (3, "unwind_complete", "COOLDOWN"),
            (100, "unwind_complete", "COOLDOWN"),
        )
    ]
    row = cycle_rows(events, 101)[0]
    assert row["closed_ns"] == 3


def test_cycle_keeps_close_request_cause_without_a_cycle_id():
    events = [
        dict(
            symbol="BTCUSDT",
            cycle_id="one",
            time_ns=1,
            kind="transition",
            cause="entry",
            state="OPENING_SPOT",
        ),
        dict(
            symbol="BTCUSDT",
            cycle_id="one",
            time_ns=2,
            kind="transition",
            cause="opening_complete",
            state="HOLDING",
        ),
        dict(symbol="BTCUSDT", cycle_id=None, time_ns=3, kind="close_requested", cause="margin"),
        dict(
            symbol="BTCUSDT",
            cycle_id="one",
            time_ns=4,
            kind="transition",
            cause="unwind_complete",
            state="COOLDOWN",
        ),
        dict(
            symbol="BTCUSDT",
            cycle_id=None,
            time_ns=10,
            kind="close_requested",
            cause="real_market_inactivity",
        ),
    ]
    assert cycle_rows(events, 20)[0]["close_causes"] == ["margin"]


def test_episode_profit_share_is_not_assigned_to_a_period_excluding_its_date():
    from scripts.continuous_delivery.diagnostics import outage_summary

    event = timestamp("2023-03-24T00:00:00Z")
    later = timestamp("2024-01-01T00:00:00Z")
    daily = [
        dict(date="2023-03-24", time_ns=event + DAY - 1, net_pnl_usdt=D(10)),
        dict(date="2024-01-01", time_ns=later + DAY - 1, net_pnl_usdt=D(100)),
    ]
    result, _ = outage_summary(daily, [], [("late", later, later + DAY)])
    assert result["daily_share_of_positive_profit_late"] is None
