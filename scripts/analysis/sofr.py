"""SOFR ACT/360 accrual, official calendars and persisted carry comparisons.

Rates, calendars and balances are inputs; no downloads or package writing occur.
"""

import math
import re
import statistics
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal as D
from decimal import localcontext
from html.parser import HTMLParser

from .capital import RUNS, number, truth, utc_ns

INDEX_QUANTUM = D("0.00000001")


def business_dates(calendar):
    dates = [date.fromisoformat(r["date"]) for r in calendar if truth(r["is_business_day"])]
    if len(dates) != len(set(dates)):
        raise ValueError("Duplicate business date")
    return sorted(dates)


def rate_mapping(rates, dates):
    mapping = {}
    for ordinal, row in enumerate(rates):
        day = date.fromisoformat(row["effectiveDate"])
        if day in mapping or row.get("type", "SOFR") != "SOFR":
            raise ValueError("Duplicate or non-SOFR rate")
        mapping[day] = ordinal, row, number(row["percentRate"]) / 100
    if set(mapping) != set(dates):
        raise ValueError("Rates must cover exactly the documented business dates")
    return mapping


def build_account(rates, calendar, start, end, capital="10000"):
    with localcontext(prec=50):
        dates = business_dates(calendar)
        mapping = rate_mapping(rates, dates)
        if start >= end or not dates or dates[0] > start or dates[-1] < end:
            raise ValueError("Account boundaries lack source business dates")
        principal = number(capital)
        if principal <= 0:
            raise ValueError("Nonpositive initial capital")
        blocks, daily = [], []
        for source_start, source_end in zip(dates, dates[1:]):
            if source_end <= start or source_start >= end:
                continue
            begin, finish = max(start, source_start), min(end, source_end)
            ordinal, row, rate = mapping[source_start]
            n = (finish - begin).days
            factor = 1 + rate * n / 360
            if factor <= 0:
                raise ValueError("Nonpositive block factor")
            closing = principal * factor
            block_id = f"SOFR:{source_start}:{source_end}"
            common = dict(
                block_id=block_id,
                rate_effective_date=str(source_start),
                rate_publication_date_expected=str(source_end),
                rate_source_row=ordinal,
                percentRate=row["percentRate"],
                annual_decimal_rate=rate,
                revisionIndicator=row.get("revisionIndicator", ""),
            )
            blocks.append(
                dict(
                    **common,
                    source_start=str(source_start),
                    source_end=str(source_end),
                    source_days=(source_end - source_start).days,
                    accrual_start=str(begin),
                    accrual_end_exclusive=str(finish),
                    accrual_days=n,
                    start_clipped=begin != source_start,
                    end_clipped=finish != source_end,
                    principal_start=principal,
                    block_factor=factor,
                    interest_usd=closing - principal,
                    balance_end=closing,
                    capitalized_at_end=finish == source_end,
                )
            )
            for elapsed in range(n):
                day = begin + timedelta(days=elapsed)
                tomorrow = day + timedelta(days=1)
                opening = principal * (1 + rate * elapsed / 360)
                balance = principal * (1 + rate * (elapsed + 1) / 360)
                capitalize = tomorrow == source_end
                daily.append(
                    dict(
                        date=str(day),
                        benchmark_boundary_utc=str(tomorrow) + "T00:00:00Z",
                        carry_close_time_ns=utc_ns(str(tomorrow) + "T00:00:00Z") - 1,
                        currency="USD",
                        cost_basis="hypothetical_gross",
                        **common,
                        block_principal=principal,
                        elapsed_days_in_block=elapsed + 1,
                        balance_open=opening,
                        balance_close=balance,
                        interest_usd=balance - opening,
                        accrued_in_block=balance - principal,
                        capitalized_at_close=capitalize,
                        principal_after_close=balance if capitalize else principal,
                        pending_interest_after_close=D(0) if capitalize else balance - principal,
                    )
                )
            principal = closing
        if len(daily) != (end - start).days:
            raise ValueError("Incomplete daily accrual coverage")
        return blocks, daily


def index_checks(rates, calendar, indexes, start, end):
    with localcontext(prec=50):
        dates = business_dates(calendar)
        mapping = rate_mapping(rates, dates)
        if start not in dates or end not in dates or start >= end:
            raise ValueError("Index comparisons require two actual business boundaries")
        official = {date.fromisoformat(r["effectiveDate"]): number(r["index"]) for r in indexes}
        if len(official) != len(indexes) or set(official) != set(dates):
            raise ValueError("Official Index population differs from business calendar")
        if any(v <= 0 or v.quantize(INDEX_QUANTUM) != v for v in official.values()):
            raise ValueError("Official Index invalid or beyond published precision")
        relevant = [d for d in dates if start <= d <= end]
        cumulative, result = D(1), []
        for a, b in zip(relevant, relevant[1:]):
            factor = 1 + mapping[a][2] * (b - a).days / 360
            cumulative *= factor
            for scope, origin, calculated in (
                ("business_block", a, factor),
                ("cumulative_from_anchor", start, cumulative),
            ):
                lo, hi = rounding_interval(official[origin], official[b])
                compatible = lo <= calculated <= hi
                row = dict(
                    scope=scope,
                    start=str(origin),
                    end=str(b),
                    days=(b - origin).days,
                    index_start=official[origin],
                    index_end=official[b],
                    published_ratio=official[b] / official[origin],
                    calculated_factor=calculated,
                    factor_lower_from_rounding=lo,
                    factor_upper_from_rounding=hi,
                    signed_error_vs_published_ratio=calculated - official[b] / official[origin],
                    published_quantum=INDEX_QUANTUM,
                    compatible_with_rounding=compatible,
                )
                if not compatible:
                    raise ValueError(f"SOFR Index rounding interval violated: {row}")
                result.append(row)
        return result


def rounding_interval(start_index, end_index):
    with localcontext(prec=50):
        x, y = number(start_index), number(end_index)
        half = INDEX_QUANTUM / 2
        if x <= half or y <= half:
            raise ValueError("Index values must exceed the rounding half-quantum")
        return (y - half) / (x + half), (y + half) / (x - half)


def period_summary(daily, start, end):
    with localcontext(prec=50):
        selected = sorted(
            [r for r in daily if start <= date.fromisoformat(r["date"]) < end],
            key=lambda r: r["date"],
        )
        n = (end - start).days
        if n <= 0 or len(selected) != n or len({r["date"] for r in selected}) != n:
            raise ValueError("Incomplete or duplicate period days")
        first, last = number(selected[0]["balance_open"]), number(selected[-1]["balance_close"])
        if first <= 0 or last <= 0:
            raise ValueError("Nonpositive period balance")
        return dict(
            start_utc=str(start) + "T00:00:00Z",
            end_exclusive_utc=str(end) + "T00:00:00Z",
            days=n,
            equity_start=first,
            equity_end=last,
            pnl_usd=last - first,
            net_return=last / first - 1,
            cagr=(last / first) ** (D(365) / n) - 1,
            accrual_day_basis=360,
            cagr_day_basis=365,
        )


DATE_TEXT = re.compile(
    r"(January|February|March|April|May|June|July|August|September|October|November|December) \d{1,2}, \d{4}"
)


class Elements(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tag, self.parts, self.rows = None, [], []

    def handle_starttag(self, tag, attrs):
        # attrs is required by HTMLParser; the calendar uses tag text only.
        if self.tag is None and tag in {"h2", "h3", "p", "span"}:
            self.tag, self.parts = tag, []

    def handle_data(self, value):
        if self.tag:
            self.parts.append(value)

    def handle_endtag(self, tag):
        if self.tag == tag:
            self.rows.append((tag, " ".join("".join(self.parts).split())))
            self.tag = None


def parse_sifma(html, source_file, current=False):
    parser = Elements()
    parser.feed(html)
    active, year, holiday, result = False, None, None, []
    for ordinal, (tag, text) in enumerate(parser.rows):
        if tag == "h2":
            if current:
                active = text == "U.S. Holiday Recommendations"
                year = 2026
            else:
                active = text.isdigit() and 2022 <= int(text) <= 2025
                year = int(text) if text.isdigit() else None
            holiday = None
        elif tag == "h3" and active:
            holiday = text
        elif active and holiday and tag in {"span", "p"}:
            match = DATE_TEXT.search(text)
            if not match:
                continue
            if tag == "p" and not text.startswith("Early Close"):
                raise ValueError("Unrecognized calendar date statement")
            day = datetime.strptime(match[0], "%B %d, %Y").date()
            result.append(
                dict(
                    date=str(day),
                    sifma_status="early_close" if tag == "p" else "full_close",
                    holiday=holiday,
                    source_file=source_file,
                    source_year=year,
                    source_element=ordinal,
                    source_text=text,
                )
            )
    if not result:
        raise ValueError("No applicable official US calendar dates")
    return result


def calendar_rows(holidays, exceptions, start, end):
    known = defaultdict(list)
    for row in holidays:
        known[date.fromisoformat(row["date"])].append(row)
    overrides = {date.fromisoformat(r["date"]): r for r in exceptions}
    if len(overrides) != len(exceptions):
        raise ValueError("Duplicate calendar exception")
    rows = []
    day = start
    while day <= end:
        entries = known[day]
        states = {r["sifma_status"] for r in entries}
        if not states <= {"full_close", "early_close"} or len(states) > 1:
            raise ValueError("Conflicting SIFMA calendar statements")
        state = next(iter(states), "ordinary_weekday" if day.weekday() < 5 else "weekend")
        page_state = state
        business = day.weekday() < 5 and state != "full_close"
        reason = " | ".join(sorted({r["holiday"] for r in entries})) or state
        sources = sorted({r["source_file"] for r in entries}) or [
            "sifma_2026.html" if day.year == 2026 else "sifma_archivo.html"
        ]
        if day in overrides:
            event = overrides[day]
            business = truth(event["is_business_day"])
            reason = event["reason"]
            sources.append(event["source_file"])
            if "sifma_status" in event:
                if event["sifma_status"] not in {"early_close", "full_close"}:
                    raise ValueError("Invalid notice-sourced SIFMA status")
                state = event["sifma_status"]
        rows.append(
            dict(
                date=str(day),
                weekday=day.weekday(),
                sifma_status=state,
                calendar_page_status=page_state,
                nyfed_exception=day in overrides,
                is_business_day=business,
                reason=reason,
                source_files=sources,
            )
        )
        day += timedelta(days=1)
    return rows


def validate_coverage(days, rates, indexes):
    expected = {r["date"] for r in days if truth(r["is_business_day"])}
    if len({r["date"] for r in days}) != len(days):
        raise ValueError("Duplicate calendar day")
    mappings = []
    for rows, label, field in ((rates, "SOFR", "percentRate"), (indexes, "SOFRAI", "index")):
        mapping = {}
        for ordinal, row in enumerate(rows):
            day = date.fromisoformat(row["effectiveDate"]).isoformat()
            if row["type"] != label or day in mapping:
                raise ValueError("Duplicate date or wrong source type: " + label)
            value = number(row[field])
            if label == "SOFRAI" and value <= 0:
                raise ValueError("Nonpositive official index")
            mapping[day] = ordinal, row
        missing, unexpected = expected - mapping.keys(), mapping.keys() - expected
        if missing:
            raise ValueError(f"Missing {label} on documented business date: {sorted(missing)}")
        if unexpected:
            raise ValueError(
                f"Unexpected {label} outside documented business dates: {sorted(unexpected)}"
            )
        mappings.append(mapping)
    rate_map, index_map = mappings
    return [
        dict(
            r,
            sofr_present=r["date"] in rate_map,
            index_present=r["date"] in index_map,
            sofr_source_row=rate_map[r["date"]][0] if r["date"] in rate_map else None,
            index_source_row=index_map[r["date"]][0] if r["date"] in index_map else None,
            coverage_status="verified",
        )
        for r in days
    ]


CAPITAL_FIELDS = (
    "capital_deployed_usdt_daily_mean",
    "capital_deployed_usdt_daily_max",
    "capital_utilization_daily_mean",
    "capital_utilization_daily_max",
    "invested_fraction",
)


def window(row):
    start, end = [date.fromisoformat(row[k][:10]) for k in ("start_utc", "end_exclusive_utc")]
    if any(
        utc_ns(row[k]) != utc_ns(str(d) + "T00:00:00Z")
        for k, d in (("start_utc", start), ("end_exclusive_utc", end))
    ):
        raise ValueError("Period must use exact UTC midnight boundaries")
    if int(row["days"]) != (end - start).days or not truth(row["coverage_complete"]):
        raise ValueError("Invalid persisted period coverage")
    return start, end


def compare_periods(daily, metrics):
    known, periods = {}, {}
    for row in metrics:
        strategy, period = row["strategy"], row["period"]
        if strategy not in RUNS or row["run_id"] != RUNS[strategy] or row["scenario"] != "BASE_E3":
            raise ValueError("Unapproved carry run or scenario")
        key = strategy, period
        if key in known:
            raise ValueError("Duplicate persisted period")
        known[key] = row
        boundaries = window(row)
        if period in periods and periods[period] != boundaries:
            raise ValueError("Carry strategies have different period boundaries")
        periods[period] = boundaries
    if not periods or set(known) != {(s, p) for s in RUNS for p in periods}:
        raise ValueError("Comparison requires both original carry strategies")
    result, differences = [], []
    with localcontext(prec=50):
        for period, (start, end) in periods.items():
            summary = period_summary(daily, start, end)
            metadata = dict(
                period=period,
                start_utc=summary["start_utc"],
                end_exclusive_utc=summary["end_exclusive_utc"],
                days=summary["days"],
                cagr_day_basis=365,
                nominal_USDT_USD_parity="1",
            )
            benchmark = dict(
                **metadata,
                portfolio="sofr",
                run_id="",
                currency="USD",
                cost_basis="hypothetical_gross",
                opening_balance=summary["equity_start"],
                closing_balance=summary["equity_end"],
                pnl=summary["pnl_usd"],
                net_return=summary["net_return"],
                cagr365=summary["cagr"],
                accrual_day_basis=360,
                sharpe_rf0_carry="",
                sharpe_reason="not_calculated_for_benchmark",
                **{k: "" for k in CAPITAL_FIELDS},
            )
            for strategy in RUNS:
                source = known[strategy, period]
                result.append(
                    dict(
                        **metadata,
                        portfolio=strategy,
                        run_id=source["run_id"],
                        currency="USDT",
                        cost_basis="net_modeled_costs",
                        opening_balance=source["starting_equity_usdt"],
                        closing_balance=source["final_equity_usdt"],
                        pnl=source["net_pnl_usdt"],
                        net_return=source["net_return"],
                        cagr365=source["cagr"],
                        accrual_day_basis="",
                        sharpe_rf0_carry=source["sharpe"],
                        sharpe_reason=source["sharpe_reason"],
                        **{k: source.get(k, "") for k in CAPITAL_FIELDS},
                    )
                )
                differences.append(
                    dict(
                        **metadata,
                        carry_strategy=strategy,
                        carry_run_id=source["run_id"],
                        comparison="carry_net_modeled_minus_sofr_hypothetical_gross",
                        pnl_carry_minus_sofr_nominal=number(source["net_pnl_usdt"])
                        - summary["pnl_usd"],
                        return_difference_pp=100
                        * (number(source["net_return"]) - summary["net_return"]),
                        cagr365_difference_pp=100 * (number(source["cagr"]) - summary["cagr"]),
                    )
                )
            result.append(benchmark)
    return result, differences


def align_daily(daily, carry):
    if not daily or len({r["date"] for r in daily}) != len(daily):
        raise ValueError("Missing or duplicate SOFR daily observations")
    mapping = {(r["strategy"], r["date"]): r for r in carry}
    if len(mapping) != len(carry) or set(mapping) != {(s, r["date"]) for s in RUNS for r in daily}:
        raise ValueError("Carry daily population does not match SOFR")
    first = daily[0]
    initial = dict(
        date=first["date"],
        boundary_utc=first["date"] + "T00:00:00Z",
        carry_close_time_ns="",
        observation="initial",
        sofr_usd=first["balance_open"],
    )
    initial.update({s + "_usdt": mapping[s, first["date"]]["starting_equity_usdt"] for s in RUNS})
    result = [initial]
    for row in daily:
        aligned = dict(
            date=row["date"],
            boundary_utc=row["benchmark_boundary_utc"],
            carry_close_time_ns=row["carry_close_time_ns"],
            observation="daily_close",
            sofr_usd=row["balance_close"],
        )
        for strategy in RUNS:
            source = mapping[strategy, row["date"]]
            if source["run_id"] != RUNS[strategy] or int(source["time_ns"]) != int(
                row["carry_close_time_ns"]
            ):
                raise ValueError("Carry daily run or timestamp mismatch")
            aligned[strategy + "_usdt"] = source["equity_usdt"]
        result.append(aligned)
    return result


def published_sofr(rows):
    """Recompute the published account from its compact daily rate observations."""
    principal = D(10000)
    pending = D(0)
    for r in rows:
        pending += principal * D(r["annual_decimal_rate"]) / D(360)
        if r["capitalized_at_close"] == "True":
            principal += pending
            pending = D(0)
    final = principal + pending
    return {
        "final_equity_usdt": final,
        "net_return": final / D(10000) - 1,
        "cagr": math.expm1(math.log(float(final / D(10000))) * 365 / len(rows)),
    }


def cash_sensitivity(carry, daily_rates, fraction):
    """Accrue hypothetical cash remuneration using original lagged balances."""
    rates = {r["date"]: r for r in daily_rates}
    out = {"cash_fraction": D(fraction)}
    for strategy in ["conditional", "permanent"]:
        rows = sorted([r for r in carry if r["strategy"] == strategy], key=lambda r: r["date"])
        with localcontext() as context:
            context.prec = 50
            capitalized = D(0)
            pending = D(0)
            lagged_cash = D(10000)
            prior_equity = D(10000)
            returns = []
            for row in rows:
                rate = rates[row["date"]]
                pending += (
                    (D(fraction) * lagged_cash + capitalized) * D(rate["annual_decimal_rate"]) / 360
                )
                adjusted = D(row["equity_usdt"]) + capitalized + pending
                returns.append(float(adjusted / prior_equity - 1))
                prior_equity = adjusted
                if rate["capitalized_at_close"] == "True":
                    capitalized += pending
                    pending = D(0)
                lagged_cash = max(D(row["free_cash_usdt"]) - D(row["debt_usdt"]), D(0))
            out[strategy + "_CAGR365_percent"] = (
                (adjusted / 10000) ** (D(365) / len(rows)) - 1
            ) * 100
            out[strategy + "_Sharpe_rf0"] = (
                statistics.mean(returns) / statistics.stdev(returns) * math.sqrt(365)
            )
    return out
