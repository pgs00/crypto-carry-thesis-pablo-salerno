"""Recalculate the published senal scenarios from daily observations."""

from bisect import bisect_left, bisect_right
from collections import Counter, defaultdict
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation, localcontext
from decimal import Decimal as D

import numpy as np
from crypto_carry.config import HOUR, Config, timestamp

from .common import scenario_metrics

SCENARIOS = {
    "BASE_E3": {},
    "H072": {"horizon_hours": 72, "holding_hours": 72},
    "H336": {"horizon_hours": 336, "holding_hours": 336},
    "V012": {"half_life_hours": 12},
    "V048": {"half_life_hours": 48},
    "B025": {"basis_max": D("0.0025")},
    "B100": {"basis_max": D("0.01")},
}


def recalculate(root):
    return {
        "results/senal/evidencia/tablas/metricas.csv": scenario_metrics(root, "senal", SCENARIOS)
    }


CHANGES = {key: value for key, value in SCENARIOS.items() if key != "BASE_E3"}


def validate_variant(base: Config, scenario: str, candidate: Config) -> dict:
    if scenario not in CHANGES:
        raise ValueError(f"Unknown closed-matrix scenario: {scenario}")
    before, after = base.to_dict(), candidate.to_dict()
    diff = {
        key: {"before": before.get(key), "after": after.get(key)}
        for key in before.keys() | after.keys()
        if before.get(key) != after.get(key)
    }
    expected = base.changed(**CHANGES[scenario]).to_dict()
    if after != expected:
        raise ValueError(f"Unauthorized configuration diff for {scenario}: {diff}")
    return diff


def scenario_configs(base: Config) -> dict[str, Config]:
    return {name: base.changed(**changes) for name, changes in CHANGES.items()}


SECOND = 1_000_000_000


SYMBOLS = ("BTCUSDT", "ETHUSDT")


EXPOSURES = {"covered", "unhedged", "dust", "flat"}


def iso(value):
    """The archived E3 UTC representation, using only the standard library."""
    seconds, nanos = divmod(int(value), SECOND)
    prefix = datetime.fromtimestamp(seconds, UTC).strftime("%Y-%m-%dT%H:%M:%S")
    return f"{prefix}.{nanos:09d}Z"


def _quantity(row, field, context, *, optional=False):
    value = row.get(field)
    if value in (None, ""):
        if optional:
            return D(0)
        raise ValueError(f"{context}: missing {field} metadata")
    try:
        number = D(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{context}: invalid {field} metadata") from exc
    if not number.is_finite() or number < 0:
        raise ValueError(f"{context}: nonfinite or negative {field} metadata")
    return number


def exposure_intervals(positions, start_ns, end_ns, tolerance, symbols=SYMBOLS):
    """Classify effective states exactly as E3; retain pre-cut dust knowledge.

    The caller supplies the actual full sample bounds and configured tolerance.
    Missing essential metadata fails explicitly; optional E3 dust fields may be
    absent because persisted state and historical dust memory establish dust.
    """
    start_ns, end_ns = int(start_ns), int(end_ns)
    tolerance = D(str(tolerance))
    if end_ns <= start_ns or not tolerance.is_finite() or tolerance < 0:
        raise ValueError("Invalid exposure sample bounds or hedge tolerance")
    symbols = tuple(symbols)
    if not symbols or len(set(symbols)) != len(symbols):
        raise ValueError("Exposure symbols must be nonempty and unique")
    rows = list(positions)
    for row in rows:
        if row.get("symbol") not in symbols:
            raise ValueError(f"Unknown exposure symbol: {row.get('symbol')}")
        if row.get("time_ns") in (None, ""):
            raise ValueError(f"{row['symbol']}: missing time_ns metadata")
    rows.sort(key=lambda row: int(row["time_ns"]))  # Stable: persisted order breaks ties.
    output = []
    for symbol in symbols:
        values = {
            int(row["time_ns"]): row
            for row in rows
            if row["symbol"] == symbol and int(row["time_ns"]) < end_ns
        }
        if not values or min(values) > start_ns:
            values[start_ns] = dict(symbol=symbol, spot="0", short="0", state="FLAT")
        times = sorted(values)
        known_dust = D(0)
        for index, lower in enumerate(times):
            upper = times[index + 1] if index + 1 < len(times) else end_ns
            row = values[lower]
            context = f"{symbol} [{lower}, {upper})"
            spot = _quantity(row, "spot", context)
            short = _quantity(row, "short", context)
            state = row.get("state")
            if state in (None, ""):
                raise ValueError(f"{context}: missing state metadata")
            dust_spot = _quantity(row, "dust_spot", context, optional=True)
            dust = (
                spot > 0
                and short == 0
                and (dust_spot > 0 or state in {"FLAT", "COOLDOWN"} or spot <= known_dust)
            )
            if dust:
                exposure, known_dust = "dust", spot
            elif spot > 0 and short > 0 and abs(spot - short) / spot <= tolerance:
                exposure = "covered"
            elif spot > 0 or short > 0:
                exposure = "unhedged"
            else:
                exposure = "flat"
            lower = max(start_ns, lower)
            if lower >= upper:
                continue
            raw_invested = spot > 0 or short > 0
            error = abs(spot - short) / spot if spot > 0 else (D(1) if short > 0 else D(0))
            output.append(
                dict(
                    symbol=symbol,
                    start_ns=lower,
                    end_ns=upper,
                    start_utc=iso(lower),
                    end_exclusive_utc=iso(upper),
                    seconds=D(upper - lower) / SECOND,
                    exposure=exposure,
                    spot=spot,
                    short=short,
                    state=state,
                    collateral_usdt=_quantity(row, "collateral", context, optional=True),
                    raw_invested=raw_invested,
                    raw_unhedged=raw_invested and error > tolerance,
                )
            )
    return sorted(output, key=lambda row: (row["start_ns"], row["symbol"]))


def _flag(value):
    if value in (True, "True", "true", "1", 1):
        return True
    if value in (False, "False", "false", "0", 0):
        return False
    raise ValueError(f"Missing or invalid raw exposure flag: {value}")


def _summary_row(period, symbol, durations, calendar):
    result = dict(period=period, symbol=symbol, **durations, calendar_seconds=calendar)
    result["cash_seconds"] = result["no_inventory_seconds"]
    if symbol == "PORTFOLIO":
        # Explicit aliases retain correspondence with archived E3 table columns.
        result["any_covered_seconds"] = result["covered_seconds"]
        result["any_unhedged_seconds"] = result["unhedged_seconds"]
        result["cash_or_dust_seconds"] = result["no_active_seconds"]
    for key, value in list(result.items()):
        if key.endswith("_seconds") and key != "calendar_seconds":
            if not D(0) <= value <= calendar:
                raise ValueError(f"Invalid exposure duration: {period}/{symbol}/{key}")
            result[key.removesuffix("_seconds") + "_fraction"] = value / calendar
    if result["invested_seconds"] + result["no_active_seconds"] != calendar:
        raise ValueError("Active and inactive exposure do not partition calendar")
    if result["no_active_seconds"] != result["dust_only_seconds"] + result["no_inventory_seconds"]:
        raise ValueError("Inactive exposure does not partition dust-only and inventory-free time")
    if result["raw_invested_seconds"] != result["invested_seconds"] + result["dust_only_seconds"]:
        raise ValueError("Raw inventory does not reconcile with active and dust-only time")
    return result


def exposure_summary(intervals, periods):
    """Clip classified trajectories and integrate portfolio temporal unions.

    Covered and unhedged unions may overlap across symbols; their sum is not
    invested time. dust_seconds means any dust, whereas dust_only_seconds means
    dust with no active asset. cash_seconds aliases strictly inventory-free time.
    """
    grouped = defaultdict(list)
    for original in intervals:
        row = dict(original)
        row["start_ns"], row["end_ns"] = int(row["start_ns"]), int(row["end_ns"])
        if row["exposure"] not in EXPOSURES or row["start_ns"] >= row["end_ns"]:
            raise ValueError("Invalid exposure classification or interval bounds")
        if D(str(row["seconds"])) != D(row["end_ns"] - row["start_ns"]) / SECOND:
            raise ValueError("Exposure interval seconds do not match exact bounds")
        row["raw_invested"] = _flag(row.get("raw_invested"))
        row["raw_unhedged"] = _flag(row.get("raw_unhedged"))
        grouped[row["symbol"]].append(row)
    if not grouped:
        raise ValueError("Missing classified exposure trajectory")
    for symbol, rows in grouped.items():
        rows.sort(key=lambda row: row["start_ns"])
        if any(a["end_ns"] != b["start_ns"] for a, b in zip(rows, rows[1:])):
            raise ValueError(f"Gap or overlap in exposure trajectory: {symbol}")
    output = []
    for period, start, end in periods:
        start, end = int(start), int(end)
        if start >= end:
            raise ValueError(f"Empty exposure period: {period}")
        calendar = D(end - start) / SECOND
        endpoints = {start, end}
        totals = {}
        for symbol, rows in sorted(grouped.items()):
            if rows[0]["start_ns"] > start or rows[-1]["end_ns"] < end:
                raise ValueError(f"Incomplete exposure coverage: {period}/{symbol}")
            durations = dict.fromkeys(
                (
                    "covered_seconds",
                    "unhedged_seconds",
                    "dust_seconds",
                    "flat_seconds",
                    "invested_seconds",
                    "raw_invested_seconds",
                    "raw_unhedged_seconds",
                    "dust_only_seconds",
                    "no_active_seconds",
                    "no_inventory_seconds",
                ),
                D(0),
            )
            for row in rows:
                lower, upper = max(start, row["start_ns"]), min(end, row["end_ns"])
                if lower >= upper:
                    continue
                endpoints.update((lower, upper))
                seconds = D(upper - lower) / SECOND
                exposure = row["exposure"]
                durations[exposure + "_seconds"] += seconds
                for key, flag in (
                    ("invested", exposure in {"covered", "unhedged"}),
                    ("raw_invested", row["raw_invested"]),
                    ("raw_unhedged", row["raw_unhedged"]),
                    ("dust_only", exposure == "dust"),
                    ("no_active", exposure in {"dust", "flat"}),
                    ("no_inventory", exposure == "flat"),
                ):
                    durations[key + "_seconds"] += seconds * flag
            totals[symbol] = durations
        portfolio = dict.fromkeys(
            (
                "invested_seconds",
                "unhedged_seconds",
                "covered_seconds",
                "both_covered_seconds",
                "raw_invested_seconds",
                "raw_unhedged_seconds",
                "dust_seconds",
                "dust_only_seconds",
                "no_active_seconds",
                "no_inventory_seconds",
            ),
            D(0),
        )
        pointers = dict.fromkeys(grouped, 0)
        times = sorted(endpoints)
        for lower, upper in zip(times, times[1:]):
            current = []
            for symbol, rows in grouped.items():
                while rows[pointers[symbol]]["end_ns"] <= lower:
                    pointers[symbol] += 1
                current.append(rows[pointers[symbol]])
            states = [row["exposure"] for row in current]
            active = any(state in {"covered", "unhedged"} for state in states)
            dust = "dust" in states
            seconds = D(upper - lower) / SECOND
            for key, flag in (
                ("invested", active),
                ("unhedged", "unhedged" in states),
                ("covered", "covered" in states),
                ("both_covered", all(state == "covered" for state in states)),
                ("raw_invested", any(row["raw_invested"] for row in current)),
                ("raw_unhedged", any(row["raw_unhedged"] for row in current)),
                ("dust", dust),
                ("dust_only", dust and not active),
                ("no_active", not active),
                ("no_inventory", all(state == "flat" for state in states)),
            ):
                portfolio[key + "_seconds"] += seconds * flag
        totals["PORTFOLIO"] = portfolio
        output.extend(
            _summary_row(period, symbol, values, calendar) for symbol, values in totals.items()
        )
    return output


def _number(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        result = Decimal(str(value))
    except InvalidOperation, ValueError:
        return None
    return result if result.is_finite() else None


def _difference(a, b):
    if a is None or b is None:
        return None
    # Decimal's default precision must not round persisted numeric evidence.
    with localcontext() as context:
        context.prec = (
            max(a.adjusted(), b.adjusted()) - min(a.as_tuple().exponent, b.as_tuple().exponent) + 3
        )
        return a - b


def _pairs(rows):
    index = {}
    for row in rows:
        key = row["scenario"], row["period"], row["strategy"]
        if key in index:
            raise ValueError(f"duplicate scenario/period/strategy: {key}")
        if key[2] not in {"conditional", "permanent"}:
            raise ValueError(f"unknown strategy: {key[2]}")
        index[key] = row
    return {
        (scenario, period): (
            index.get((scenario, period, "conditional")),
            index.get((scenario, period, "permanent")),
        )
        for scenario, period in sorted({key[:2] for key in index})
    }


def _valid_window(row):
    if not row:
        return False
    try:
        start = datetime.fromisoformat(row.get("start_utc", ""))
        end = datetime.fromisoformat(row.get("end_exclusive_utc", ""))
        return start.utcoffset() is not None and end.utcoffset() is not None and start < end
    except TypeError, ValueError:
        return False


def _context(scenario, period, conditional, permanent):
    issues = []
    identity = {"scenario": scenario, "period": period}
    for name, row in (("conditional", conditional), ("permanent", permanent)):
        identity[f"{name}_run_id"] = row.get("run_id", "") if row else ""
        for key in ("start_utc", "end_exclusive_utc"):
            identity[f"{name}_{key}"] = row.get(key) if row else None
        if row is None:
            issues.append(f"missing_{name}_portfolio")
        elif row.get("coverage_complete") is not True and row.get("coverage_complete") != "True":
            issues.append(f"incomplete_{name}_coverage")
    comparable = (
        _valid_window(conditional)
        and _valid_window(permanent)
        and conditional["start_utc"] == permanent["start_utc"]
        and conditional["end_exclusive_utc"] == permanent["end_exclusive_utc"]
    )
    for key in ("start_utc", "end_exclusive_utc"):
        identity[key] = conditional[key] if comparable else None
    if conditional is not None and permanent is not None and not comparable:
        issues.append("noncomparable_window")
    return identity, issues


def _metric_issues(cagr, sc, sp, conditional, permanent):
    issues = []
    for name, value, source, field in (
        ("conditional_cagr", cagr, conditional, "cagr"),
        ("conditional_sharpe", sc, conditional, "sharpe"),
        ("permanent_sharpe", sp, permanent, "sharpe"),
    ):
        if value is None:
            issue = f"undefined_or_nonfinite_{name}"
            detail = source.get(f"{field}_reason") if source else None
            issues.append(f"{issue} ({detail})" if detail else issue)
    return issues


def h2_comparison(rows) -> list[dict]:
    """Evaluate every scenario/period pair without modifying source metrics."""
    output = []
    for (scenario, period), (conditional, permanent) in _pairs(rows).items():
        result, issues = _context(scenario, period, conditional, permanent)
        cond, perm = conditional or {}, permanent or {}
        cagr, sc, sp = (
            _number(cond.get("cagr")),
            _number(cond.get("sharpe")),
            _number(perm.get("sharpe")),
        )
        positive = None if cagr is None else cagr > 0
        superior = None if sc is None or sp is None else sc > sp
        issues += _metric_issues(cagr, sc, sp, conditional, permanent)
        if issues:
            verdict, reason = "no_concluyente", "; ".join(issues)
        elif positive and superior:
            verdict, reason = "favorable", "cagr_positive_and_sharpe_superior"
        else:
            verdict = "no_favorable"
            reason = "; ".join(
                item
                for item, failed in (
                    ("cagr_not_positive", not positive),
                    ("sharpe_not_superior", not superior),
                )
                if failed
            )
        result.update(
            conditional_cagr=cagr,
            conditional_sharpe=sc,
            permanent_sharpe=sp,
            sharpe_difference=_difference(sc, sp),
            cagr_positive=positive,
            sharpe_superior=superior,
            verdict=verdict,
            reason=reason,
        )
        output.append(result)
    return output


def _check(actual, key, expected):
    if key not in actual:
        raise ValueError(f"H2 missing field {key}")
    value = actual[key]
    if isinstance(expected, bool):
        valid = value is expected or value == str(expected)
    elif expected is None:
        valid = value is None or value == ""
    elif isinstance(expected, Decimal):
        valid = _number(value) == expected
    else:
        valid = value == expected
    if not valid:
        raise ValueError(f"H2 {key}: {value!r} != {expected!r}")


def validate_h2_rows(actual, metrics):
    """Raise ValueError unless rows obey provenance, completeness and explicit H2.

    This does not call the constructor, nor compare against its output. Numeric
    predicates and the verdict are independently evaluated from source metrics.
    Native rows and CSV string rows are supported; blank booleans mean unknown.
    """
    sources = _pairs(metrics)
    supplied = {}
    for row in actual:
        key = row.get("scenario"), row.get("period")
        if key in supplied:
            raise ValueError(f"duplicate H2 scenario/period: {key}")
        supplied[key] = row
    if set(supplied) != set(sources):
        raise ValueError("H2 scenario/period coverage differs from source metrics")
    for (scenario, period), (conditional, permanent) in sources.items():
        row = supplied[scenario, period]
        identity, problems = _context(scenario, period, conditional, permanent)
        for key, value in identity.items():
            _check(row, key, value)
        cond, perm = conditional or {}, permanent or {}
        cagr = _number(cond.get("cagr"))
        conditional_sharpe = _number(cond.get("sharpe"))
        permanent_sharpe = _number(perm.get("sharpe"))
        _check(row, "conditional_cagr", cagr)
        _check(row, "conditional_sharpe", conditional_sharpe)
        _check(row, "permanent_sharpe", permanent_sharpe)
        _check(row, "sharpe_difference", _difference(conditional_sharpe, permanent_sharpe))
        cagr_positive = cagr > 0 if cagr is not None else None
        sharpe_superior = (
            conditional_sharpe > permanent_sharpe
            if conditional_sharpe is not None and permanent_sharpe is not None
            else None
        )
        _check(row, "cagr_positive", cagr_positive)
        _check(row, "sharpe_superior", sharpe_superior)
        problems.extend(
            _metric_issues(cagr, conditional_sharpe, permanent_sharpe, conditional, permanent)
        )
        if problems:
            _check(row, "verdict", "no_concluyente")
            _check(row, "reason", "; ".join(problems))
            continue
        # Independent gate: superiority alone cannot support H2.
        if cagr_positive is True and sharpe_superior is True:
            _check(row, "verdict", "favorable")
            _check(row, "reason", "cagr_positive_and_sharpe_superior")
        else:
            _check(row, "verdict", "no_favorable")
            failures = []
            if cagr_positive is False:
                failures.append("cagr_not_positive")
            if sharpe_superior is False:
                failures.append("sharpe_not_superior")
            _check(row, "reason", "; ".join(failures))


def decimal(value):
    return D(0) if value in (None, "") else D(str(value))


def yes(value):
    return str(value).lower() in {"true", "1"}


def minute_flags(times, data, forecasts, cost, config):
    """Operate on current closed bars; portfolio state is deliberately absent."""
    published = np.array([r["time_ns"] for r in forecasts], dtype=np.int64)
    if np.any(published[1:] <= published[:-1]):
        raise ValueError("Forecast publications must be strictly increasing")
    indices = np.searchsorted(published, times, side="right") - 1
    valid_fc = np.array([yes(r["valid"]) for r in forecasts])[np.maximum(indices, 0)] & (
        indices >= 0
    )
    funding_pass = (
        np.array([decimal(r["forecast"]) > cost for r in forecasts])[np.maximum(indices, 0)]
        & valid_fc
    )
    spot, future = data["spot"], data["future"]
    spot_known = np.isfinite(spot) | data["known_spot_missing"]
    future_known = np.isfinite(future) | data["known_future_missing"]
    complete = spot_known & future_known & data["mark_present"] & valid_fc
    operational = (
        np.isfinite(spot)
        & np.isfinite(future)
        & (spot > 0)
        & (future > 0)
        & (data["spot_volume"] > 0)
        & (data["future_volume"] > 0)
    )
    # Resolve the rare exact threshold ties with decimal arithmetic.
    low = future - spot * (1 + float(config.basis_min))
    high = future - spot * (1 + float(config.basis_max))
    basis_pass = (low >= 0) & (high <= 0)
    ties = np.flatnonzero((np.abs(low) < 1e-8) | (np.abs(high) < 1e-8))
    for index in ties:
        if spot[index] > 0:
            observed = D(str(future[index])) / D(str(spot[index])) - 1
            basis_pass[index] = config.basis_min <= observed <= config.basis_max
    return dict(
        complete=complete,
        eligible=complete & operational & funding_pass & basis_pass,
        forecast_index=indices,
        funding_pass=funding_pass,
        basis_pass=basis_pass,
        operational=operational,
        known_closure=data["known_spot_missing"] | data["known_future_missing"],
        forecast_valid=valid_fc,
        unknown_market_data=~(spot_known & future_known & data["mark_present"]),
    )


def summarize_day(times, flags, forecasts):
    good = len(times) == 1440 and len(np.unique(times)) == 1440 and bool(flags["complete"].all())
    total = D(0)
    for index in np.unique(flags["forecast_index"]):
        count = int(np.count_nonzero(flags["eligible"] & (flags["forecast_index"] == index)))
        if index >= 0:
            total += decimal(forecasts[index]["forecast"]) * count
    return dict(
        complete=good,
        expected_minutes=1440,
        observed_minutes=len(times),
        valid_minutes=int(flags["complete"].sum()),
        eligible_minutes=int(flags["eligible"].sum()),
        unknown_market_minutes=int(flags["unknown_market_data"].sum()),
        invalid_forecast_minutes=int((~flags["forecast_valid"]).sum()),
        known_closure_missing_minutes=int(flags["known_closure"].sum()),
        nonoperational_minutes=int((flags["complete"] & ~flags["operational"]).sum()),
        funding_failed_minutes=int((flags["complete"] & ~flags["funding_pass"]).sum()),
        basis_failed_minutes=int(
            (flags["complete"] & flags["operational"] & ~flags["basis_pass"]).sum()
        ),
        opportunity_sum=total,
        opportunity=total / 1440 if good else None,
        eligible_fraction=D(int(flags["eligible"].sum())) / 1440 if good else None,
        reason="" if good else "incomplete_required_minute_or_forecast",
    )


def h1_summaries(rows, periods):
    output = []
    for period, start, end in periods:
        asset_rows = []
        for symbol in SYMBOLS:
            group = [r for r in rows if r["symbol"] == symbol and start <= int(r["time_ns"]) < end]
            valid = [r for r in group if yes(r["horizon_valid"])]
            result = dict(
                period=period,
                symbol=symbol,
                total_observations=len(group),
                valid_observations=len(valid),
                excluded_observations=len(group) - len(valid),
                exclusion_counts=dict(
                    Counter(r["reason"] for r in group if not yes(r["horizon_valid"]))
                ),
                mae_ewma=sum((decimal(r["absolute_error_ewma"]) for r in valid), D(0)) / len(valid)
                if valid
                else None,
                mae_no_change=sum((decimal(r["absolute_error_no_change"]) for r in valid), D(0))
                / len(valid)
                if valid
                else None,
            )
            asset_rows.append(result)
        output.extend(asset_rows)
        output.append(
            dict(
                period=period,
                symbol="EQUAL_WEIGHT",
                **{
                    key: sum(r[key] for r in asset_rows)
                    for key in ("total_observations", "valid_observations", "excluded_observations")
                },
                exclusion_counts=dict(
                    sum((Counter(r["exclusion_counts"]) for r in asset_rows), Counter())
                ),
                **{
                    key: sum((r[key] for r in asset_rows), D(0)) / 2
                    if all(r[key] is not None for r in asset_rows)
                    else None
                    for key in ("mae_ewma", "mae_no_change")
                },
            )
        )
    return output


def h1_observations(signals, history, config):
    """Future observations are labels only; cohort membership uses signal time."""
    output = []
    for symbol in SYMBOLS:
        funding = history[symbol]
        times = [r.funding_time for r in funding]
        sums = [D(0)]
        bad = [0]
        for i, row in enumerate(funding):
            sums.append(sums[-1] + row.funding_rate)
            good = row.interval_verified and (
                i == 0 or D(row.funding_time - times[i - 1]) / HOUR == row.interval_hours
            )
            bad.append(bad[-1] + int(not good))
        for signal in signals:
            if signal["symbol"] != symbol:
                continue
            now = int(signal["time_ns"])
            end = now + config.horizon_hours * HOUR
            reason = ""
            left, right = bisect_right(times, now), bisect_right(times, end)
            following = bisect_left(times, end)
            if not yes(signal["valid"]):
                reason = "invalid_forecast_history"
            elif end >= timestamp(config.end):
                reason = "horizon_outside_sample"
            elif left == 0 or following == len(times):
                reason = "funding_calendar_boundary_unverified"
            elif bad[following + 1] - bad[left]:
                reason = "missing_or_unverified_funding_interval"
            observed = sums[right] - sums[left] if not reason else None
            ewma, nc = decimal(signal["forecast"]), decimal(signal["no_change"])
            output.append(
                dict(
                    symbol=symbol,
                    time_ns=now,
                    signal_utc=iso(now),
                    anchor=int(signal["anchor"]),
                    history_start=int(signal["history_start"]),
                    horizon_end=end,
                    horizon_end_utc=iso(end),
                    forecast=ewma,
                    no_change=nc,
                    realized=observed,
                    horizon_valid=not reason,
                    realized_funding_events=right - left if not reason else None,
                    reason=reason,
                    error_ewma=ewma - observed if observed is not None else None,
                    error_no_change=nc - observed if observed is not None else None,
                    absolute_error_ewma=abs(ewma - observed) if observed is not None else None,
                    absolute_error_no_change=abs(nc - observed) if observed is not None else None,
                )
            )
    return sorted(output, key=lambda r: (r["time_ns"], r["symbol"]))
