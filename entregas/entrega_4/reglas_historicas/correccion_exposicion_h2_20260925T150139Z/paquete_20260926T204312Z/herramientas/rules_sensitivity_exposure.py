"""Pure E3 editorial exposure from persisted positions, without economic replay.

Classify the complete trajectory before clipping periods. Quantities and states
come from positions.parquet in persisted order, not a join that reorders ties.
The archived E3 classifier is the methodological reference; source files remain
unchanged. Raw counters deliberately retain dust inventory and its price risk.
"""

from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal as D
from decimal import InvalidOperation

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
