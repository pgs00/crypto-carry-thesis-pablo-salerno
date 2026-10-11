"""Calendar contracts: business dates come from documented calendars, not rate gaps."""

from datetime import date

import pytest

from scripts.sofr_benchmark.calendar import calendar_rows, parse_sifma, validate_coverage


def test_sifma_full_and_early_close_are_distinct_and_uk_is_excluded():
    html = "<h2>U.S. Holiday Recommendations</h2><h3>Independence Day</h3><span>Friday, July 3, 2026</span><p>Early Close (2:00 p.m.): Thursday, July 2, 2026</p><h2>U.K. Holiday Recommendations</h2><h3>Other</h3><span>Monday, July 6, 2026</span>"
    rows = parse_sifma(html, "current.html", current=True)
    assert [(r["date"], r["sifma_status"]) for r in rows] == [
        ("2026-07-03", "full_close"),
        ("2026-07-02", "early_close"),
    ]


def test_historical_weekend_start_and_veterans_without_observed_friday():
    html = "<h2>2022</h2><h3>New Year</h3><p>Early Close Only: Friday, December 31, 2021</p><h2>2023</h2><h3>Veterans Day</h3><p></p>"
    rows = parse_sifma(html, "archive.html")
    assert rows[0]["date"] == "2021-12-31" and rows[0]["sifma_status"] == "early_close"
    days = calendar_rows(rows, [], date(2023, 11, 10), date(2023, 11, 13))
    assert [r["is_business_day"] for r in days] == [True, False, False, True]


def test_nyfed_exception_overrides_early_close_and_carter_stays_open():
    source = [
        dict(date="2023-04-07", sifma_status="early_close", source_file="s", holiday="Good Friday")
    ]
    exceptions = [
        dict(
            date="2023-04-07",
            is_business_day=False,
            source_file="official_notice",
            reason="Good Friday repo exception",
        )
    ]
    days = calendar_rows(source, exceptions, date(2023, 4, 6), date(2023, 4, 10))
    assert [r["is_business_day"] for r in days] == [True, False, False, False, True]
    assert "official_notice" in days[1]["source_files"]
    assert calendar_rows(
        [],
        [dict(date="2025-01-09", is_business_day=True, source_file="notice", reason="Carter")],
        date(2025, 1, 9),
        date(2025, 1, 9),
    )[0]["is_business_day"]


def test_missing_business_day_blocks_even_when_neighbors_have_same_rate():
    days = calendar_rows([], [], date(2024, 2, 26), date(2024, 2, 28))
    rates = [
        dict(effectiveDate=d, type="SOFR", percentRate="5") for d in ("2024-02-26", "2024-02-28")
    ]
    index = [dict(effectiveDate=r["date"], type="SOFRAI", index="1") for r in days]
    with pytest.raises(ValueError, match="Missing SOFR"):
        validate_coverage(days, rates, index)


def test_carter_notice_consolidates_early_close_without_removing_publication():
    exception = dict(
        date="2025-01-09",
        is_business_day=True,
        source_file="nyfed_carter_2025.html",
        reason="Carter notice confirms SIFMA early close and normal SOFR publication",
        sifma_status="early_close",
    )
    row = calendar_rows([], [exception], date(2025, 1, 9), date(2025, 1, 9))[0]
    assert row["sifma_status"] == "early_close"
    assert row["calendar_page_status"] == "ordinary_weekday"
    assert row["is_business_day"] is True
    assert "nyfed_carter_2025.html" in row["source_files"]


@pytest.mark.parametrize("change", ["duplicate", "weekend", "nan", "missing_index"])
def test_invalid_source_population_blocks(change):
    days = calendar_rows([], [], date(2024, 3, 1), date(2024, 3, 4))
    rates = [
        dict(effectiveDate=d, type="SOFR", percentRate="5") for d in ("2024-03-01", "2024-03-04")
    ]
    index = [dict(effectiveDate=d, type="SOFRAI", index="1") for d in ("2024-03-01", "2024-03-04")]
    if change == "duplicate":
        rates.append(dict(rates[0]))
    if change == "weekend":
        rates.append(dict(effectiveDate="2024-03-02", type="SOFR", percentRate="5"))
    if change == "nan":
        rates[0]["percentRate"] = "NaN"
    if change == "missing_index":
        index.pop()
    with pytest.raises(ValueError):
        validate_coverage(days, rates, index)
