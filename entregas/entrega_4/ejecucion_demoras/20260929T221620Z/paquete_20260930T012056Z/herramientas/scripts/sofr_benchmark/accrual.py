"""A separate ACT/360 account and explicit published-index rounding checks."""

from datetime import date, timedelta
from decimal import Decimal as D
from decimal import localcontext

from scripts.return_capital.common import number, truth, utc_ns

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
