"""Fixed-position funding-price comparisons, with no strategy replay."""

from collections import defaultdict
from dataclasses import replace
from decimal import Decimal as D

from crypto_carry.data.funding_proxy import resolve_funding_mark

BPS = D(10000)


def paired_proxy(funding, mark, config):
    """Force the existing resolver on a copy, including officially priced events."""
    if config.analysis_mode != "prescribed_research" or config.funding_proxy_stress_bps != 0:
        raise ValueError("This comparison requires prescribed research with zero stress")
    if funding.settlement_mark_price is not None:
        _positive(funding.settlement_mark_price)
    return resolve_funding_mark(replace(funding, settlement_mark_price=None), mark, config)


def _positive(value):
    if not value.is_finite() or value <= 0:
        raise ValueError("Price must be positive and finite")


def relative_error_bps(proxy, official):
    _positive(proxy)
    _positive(official)
    return (proxy / official - 1) * BPS


def price_stats(errors):
    """Use the linear quantile at rank (n - 1) * 0.95, without float rounding."""
    output = dict(paired_observations=len(errors))
    fields = ("bias_bps", "mae_bps", "p95_abs_bps", "max_abs_bps")
    if not errors:
        return {**output, **dict.fromkeys(fields)}
    if any(not value.is_finite() for value in errors):
        raise ValueError("Nonfinite price error")
    absolute = sorted(abs(value) for value in errors)
    rank = D(len(errors) - 1) * D(".95")
    lower = int(rank)
    upper = min(lower + 1, len(errors) - 1)
    return dict(
        **output,
        bias_bps=sum(errors, D(0)) / len(errors),
        mae_bps=sum(absolute, D(0)) / len(errors),
        p95_abs_bps=absolute[lower] + (absolute[upper] - absolute[lower]) * (rank - lower),
        max_abs_bps=absolute[-1],
    )


def positions_before(events, ledger):
    """Settlement precedes every fill at its timestamp; retain source row order."""
    by_symbol = defaultdict(list)
    for row in ledger:
        by_symbol[row["symbol"]].append(row)
    output = {}
    for symbol in {event["symbol"] for event in events}:
        ordered = sorted(by_symbol[symbol], key=lambda row: int(row["time_ns"]))
        selected = sorted(
            (event for event in events if event["symbol"] == symbol),
            key=lambda event: int(event["funding_time"]),
        )
        index, last = 0, None
        for event in selected:
            t = int(event["funding_time"])
            while index < len(ordered) and int(ordered[index]["time_ns"]) < t:
                last = ordered[index]
                index += 1
            key = (symbol, t)
            if key in output:
                raise ValueError("Duplicate funding observation")
            short = D(str(last["short"])) if last else D(0)
            if not short.is_finite() or short < 0:
                raise ValueError("Invalid saved short quantity")
            output[key] = dict(
                short_before=short,
                prior_ledger_event_id=last["event_id"] if last else None,
                prior_ledger_time_ns=int(last["time_ns"]) if last else None,
            )
    return output


def event_impact(short, rate, base_price, proxy, method, p95_abs_bps):
    """Perturb missing prices around their proxy, leaving known prices unchanged."""
    for price in (base_price, proxy):
        _positive(price)
    if method not in {"exact", "previous_closed_1m"}:
        raise ValueError("Unknown funding price method")
    if not short.is_finite() or short < 0 or not rate.is_finite():
        raise ValueError("Invalid position or funding rate")
    if not p95_abs_bps.is_finite() or not 0 <= p95_abs_bps < BPS:
        raise ValueError("Invalid price perturbation")
    if method == "previous_closed_1m" and base_price != proxy:
        raise ValueError("Saved proxy differs from the reconstructed minute close")
    baseline = short * base_price * rate
    missing = method == "previous_closed_1m"
    direction = D((rate > 0) - (rate < 0))
    shift = direction * p95_abs_bps / BPS if missing else D(0)
    favorable = base_price * (1 + shift)
    adverse = base_price * (1 - shift)
    result = dict(
        base_funding_usdt=baseline,
        known_proxy_delta_usdt=short * rate * (proxy - base_price) if not missing else None,
        favorable_price=favorable,
        adverse_price=adverse,
        favorable_delta_usdt=short * rate * (favorable - base_price),
        adverse_delta_usdt=short * rate * (adverse - base_price),
    )
    if result["favorable_delta_usdt"] < 0 or result["adverse_delta_usdt"] > 0:
        raise ValueError("Sensitivity direction contradicts cashflow sign")
    return result


def scenario_totals(events, capital, final_equity):
    """Translate fixed cashflow changes into total return, without reinvestment."""
    _positive(capital)
    baseline_funding = sum((row["base_funding_usdt"] for row in events), D(0))
    result = []
    for scenario in ("base", "favorable", "adverse"):
        delta = (
            D(0)
            if scenario == "base"
            else sum((row[f"{scenario}_delta_usdt"] for row in events), D(0))
        )
        result.append(
            dict(
                scenario=scenario,
                capital_usdt=capital,
                base_final_equity_usdt=final_equity,
                base_funding_usdt=baseline_funding,
                delta_usdt=delta,
                adjusted_funding_usdt=baseline_funding + delta,
                adjusted_final_equity_usdt=final_equity + delta,
                delta_return_bps=delta / capital * BPS,
                delta_return_percentage_points=delta / capital * 100,
                net_return=(final_equity + delta) / capital - 1,
            )
        )
    return result
