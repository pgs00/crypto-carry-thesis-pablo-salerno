"""Small exact financial examples; none are historical performance results."""

from datetime import date, timedelta
from decimal import Decimal as D
from decimal import localcontext

import pytest

from scripts.sofr_benchmark.accrual import (
    build_account,
    index_checks,
    period_summary,
    rounding_interval,
)
from scripts.sofr_benchmark.calendar import calendar_rows


def dates(*strings):
    return [date.fromisoformat(s) for s in strings]


def rates(*days, percent="0.05"):
    return [
        dict(effectiveDate=d, type="SOFR", percentRate=percent, revisionIndicator="") for d in days
    ]


def test_initial_saturday_accrues_exactly_two_days_without_december_interest():
    with localcontext(prec=50):
        cal = calendar_rows([], [], *dates("2021-12-31", "2022-01-03"))
        blocks, daily = build_account(
            rates("2021-12-31", "2022-01-03"), cal, *dates("2022-01-01", "2022-01-03")
        )
        assert len(blocks) == 1 and len(daily) == 2
        assert blocks[0]["source_days"] == 3 and blocks[0]["accrual_days"] == 2
        assert abs(daily[0]["balance_close"] - (D(10000) + D(1) / 72)) < D("1E-40")
        assert abs(daily[1]["balance_close"] - (D(10000) + D(1) / 36)) < D("1E-40")
        assert daily[0]["capitalized_at_close"] is False
        assert daily[1]["capitalized_at_close"] is True


def test_equal_rates_on_consecutive_business_dates_must_compound_separately():
    cal = calendar_rows([], [], *dates("2024-01-08", "2024-01-10"))
    blocks, daily = build_account(
        rates("2024-01-08", "2024-01-09", "2024-01-10", percent="36"),
        cal,
        *dates("2024-01-08", "2024-01-10"),
    )
    assert len(blocks) == 2
    assert daily[0]["balance_close"] == D("10010")
    assert daily[1]["balance_close"] == D("10020.01")


def test_weekend_and_holiday_interest_stays_simple_until_next_business_date():
    holidays = [
        dict(date="2024-01-15", sifma_status="full_close", source_file="fixture", holiday="MLK")
    ]
    cal = calendar_rows(holidays, [], *dates("2024-01-12", "2024-01-17"))
    blocks, daily = build_account(
        rates("2024-01-12", "2024-01-16", "2024-01-17", percent="36"),
        cal,
        *dates("2024-01-12", "2024-01-17"),
    )
    assert len(blocks) == 2
    assert [r["balance_close"] for r in daily] == [
        D("10010"),
        D("10020"),
        D("10030"),
        D("10040"),
        D("10050.04"),
    ]


def test_cut_inside_yearend_block_preserves_principal_and_pending_interest():
    holiday = [
        dict(
            date="2024-01-01", sifma_status="full_close", source_file="fixture", holiday="New Year"
        )
    ]
    cal = calendar_rows(holiday, [], *dates("2023-12-29", "2024-01-03"))
    _, daily = build_account(
        rates("2023-12-29", "2024-01-02", "2024-01-03", percent="36"),
        cal,
        *dates("2023-12-30", "2024-01-03"),
    )
    assert daily[0]["principal_after_close"] == 10000
    assert daily[0]["pending_interest_after_close"] == 10
    assert daily[1]["capitalized_at_close"] is False
    cut = period_summary(daily, *dates("2024-01-01", "2024-01-03"))
    assert cut["equity_start"] == 10020 and cut["equity_end"] == D("10040.03")
    assert cut["pnl_usd"] == D("20.03")


def test_leap_day_uses_one_actual_day_and_end_date_rate_is_excluded():
    cal = calendar_rows([], [], *dates("2024-02-28", "2024-03-01"))
    r = rates("2024-02-28", "2024-02-29", percent="36") + rates("2024-03-01", percent="999")
    blocks, daily = build_account(r, cal, *dates("2024-02-28", "2024-03-01"))
    assert len(daily) == 2 and daily[-1]["date"] == "2024-02-29"
    assert daily[-1]["balance_close"] == D("10020.01") and len(blocks) == 2


def test_cagr_uses_365_while_interest_contract_remains_act360():
    days = [
        dict(
            date=str(date(2022, 1, 1) + timedelta(days=i)),
            balance_open=D(10000),
            balance_close=D(11000) if i == 364 else D(10000),
        )
        for i in range(365)
    ]
    r = period_summary(days, *dates("2022-01-01", "2023-01-01"))
    assert r["days"] == 365 and r["cagr"] == D("0.1")


def test_index_comparison_uses_public_rounding_bounds_not_monetary_tolerance():
    lo, hi = rounding_interval("1.00000000", "1.00010000")
    assert lo < D("1.0001") < hi
    assert not lo <= D("1.0001001") <= hi
    cal = calendar_rows([], [], *dates("2024-01-08", "2024-01-10"))
    r = rates("2024-01-08", "2024-01-09", "2024-01-10", percent="3.6")
    idx = [
        dict(effectiveDate=d, index=v)
        for d, v in [("2024-01-08", "1"), ("2024-01-09", "1.0001"), ("2024-01-10", "1.00020001")]
    ]
    checks = index_checks(r, cal, idx, *dates("2024-01-08", "2024-01-10"))
    assert len(checks) == 4 and all(x["compatible_with_rounding"] for x in checks)
    idx[-1]["index"] = "1.00019"  # Discrepancy larger than the published rounding bounds.
    with pytest.raises(ValueError):
        index_checks(r, cal, idx, *dates("2024-01-08", "2024-01-10"))


def test_index_cannot_start_on_saturday_and_missing_rate_is_not_carried():
    cal = calendar_rows([], [], *dates("2022-01-01", "2022-01-04"))
    with pytest.raises(ValueError):
        index_checks([], cal, [], *dates("2022-01-01", "2022-01-04"))
    cal = calendar_rows([], [], *dates("2024-01-08", "2024-01-10"))
    with pytest.raises(ValueError):
        build_account(rates("2024-01-08", "2024-01-10"), cal, *dates("2024-01-08", "2024-01-10"))


def test_final_revision_rate_is_used_and_indicator_and_expected_publication_survive():
    cal = calendar_rows([], [], *dates("2024-01-08", "2024-01-09"))
    observations = rates("2024-01-08", "2024-01-09", percent="3.6")
    observations[0]["revisionIndicator"] = "*"
    blocks, daily = build_account(observations, cal, *dates("2024-01-08", "2024-01-09"))
    assert daily[0]["interest_usd"] == D(1)
    assert blocks[0]["revisionIndicator"] == daily[0]["revisionIndicator"] == "*"
    assert daily[0]["rate_effective_date"] == "2024-01-08"
    assert daily[0]["rate_publication_date_expected"] == "2024-01-09"
