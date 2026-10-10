"""Comparison tests use inherited balances and persisted carry numbers."""

from copy import deepcopy
from datetime import date, timedelta
from decimal import Decimal as D

import pytest

from scripts.return_capital.common import RUNS, utc_ns
from scripts.sofr_benchmark.comparison import align_daily, compare_periods


def fixture():
    daily = [
        dict(
            date=str(date(2023, 12, 31) + timedelta(days=i)),
            benchmark_boundary_utc=str(date(2024, 1, 1) + timedelta(days=i)) + "T00:00:00Z",
            carry_close_time_ns=utc_ns(str(date(2024, 1, 1) + timedelta(days=i)) + "T00:00:00Z")
            - 1,
            balance_open=D(11000 + i),
            balance_close=D(11001 + i),
        )
        for i in range(2)
    ]
    metrics, carry = [], []
    for strategy, run in RUNS.items():
        metrics.append(
            dict(
                scenario="BASE_E3",
                strategy=strategy,
                run_id=run,
                period="2024",
                start_utc="2024-01-01T00:00:00.000000000Z",
                end_exclusive_utc="2024-01-02T00:00:00.000000000Z",
                days="1",
                coverage_complete="True",
                starting_equity_usdt="10002.00",
                final_equity_usdt="10004.000",
                net_pnl_usdt="2.000",
                net_return="0.0001999600079984003199360127974",
                cagr="0.0757162",
                sharpe="",
                sharpe_reason="zero sample volatility",
                capital_deployed_usdt_daily_mean="5000.12300",
                capital_utilization_daily_mean="0.50",
                invested_fraction="0.4",
            )
        )
        for i, row in enumerate(daily):
            carry.append(
                dict(
                    strategy=strategy,
                    run_id=run,
                    date=row["date"],
                    time_ns=str(row["carry_close_time_ns"]),
                    starting_equity_usdt=str(10000 + 2 * i),
                    equity_usdt=str(10002 + 2 * i),
                )
            )
    return daily, metrics, carry


def test_period_inherits_sofr_balance_and_preserves_carry_strings_and_sharpe_nd():
    daily, metrics, _ = fixture()
    before = deepcopy(metrics)
    rows, differences = compare_periods(daily, metrics)
    assert metrics == before
    assert len(rows) == 3 and len(differences) == 2
    sofr = next(r for r in rows if r["portfolio"] == "sofr")
    assert sofr["opening_balance"] == D(11001) and sofr["pnl"] == 1
    assert sofr["currency"] == "USD" and sofr["cost_basis"] == "hypothetical_gross"
    assert (
        sofr["sharpe_rf0_carry"] == "" and sofr["sharpe_reason"] == "not_calculated_for_benchmark"
    )
    carried = next(r for r in rows if r["portfolio"] == "conditional")
    assert carried["closing_balance"] == "10004.000"
    assert carried["capital_deployed_usdt_daily_mean"] == "5000.12300"
    assert (
        carried["sharpe_rf0_carry"] == "" and carried["sharpe_reason"] == "zero sample volatility"
    )
    assert differences[0]["pnl_carry_minus_sofr_nominal"] == 1


def test_mismatched_period_boundaries_or_duplicate_metrics_are_rejected():
    daily, metrics, _ = fixture()
    bad = deepcopy(metrics)
    bad[-1]["start_utc"] = "2023-12-31T00:00:00Z"
    with pytest.raises(ValueError):
        compare_periods(daily, bad)
    with pytest.raises(ValueError):
        compare_periods(daily, metrics + metrics[:1])


def test_comparison_cannot_silently_drop_a_strategy_or_use_another_run():
    daily, metrics, _ = fixture()
    with pytest.raises(ValueError):
        compare_periods(daily, metrics[:1])
    metrics[0]["run_id"] = "unapproved_run"
    with pytest.raises(ValueError):
        compare_periods(daily, metrics)


def test_daily_alignment_matches_close_nanosecond_without_extra_accrual():
    daily, _, carry = fixture()
    rows = align_daily(daily, carry)
    assert len(rows) == 3  # One initial boundary and two closes.
    assert rows[0]["boundary_utc"] == "2023-12-31T00:00:00Z"
    assert rows[0]["sofr_usd"] == 11000
    assert rows[-1]["sofr_usd"] == 11002 and rows[-1]["conditional_usdt"] == "10004"
    assert rows[-1]["boundary_utc"] == "2024-01-02T00:00:00Z"


def test_duplicate_or_missing_carry_day_and_wrong_timestamp_are_rejected():
    daily, _, carry = fixture()
    with pytest.raises(ValueError):
        align_daily(daily, carry[:-1])
    with pytest.raises(ValueError):
        align_daily(daily, carry + carry[:1])
    carry[0]["time_ns"] = str(int(carry[0]["time_ns"]) + 1)
    with pytest.raises(ValueError):
        align_daily(daily, carry)
