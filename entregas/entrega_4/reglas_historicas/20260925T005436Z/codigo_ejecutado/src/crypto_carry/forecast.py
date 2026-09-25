"""Duration-aware funding forecasts using only information available at decision time."""

from dataclasses import dataclass
from decimal import Decimal

from .config import HOUR, Config
from .models import Funding

D = Decimal


@dataclass(frozen=True)
class Forecast:
    value: Decimal
    no_change: Decimal
    anchor: int
    available_at: int
    history_start: int
    valid: bool
    reason: str


def weight(age_hours: Decimal, half_life_hours: Decimal) -> Decimal:
    """Return the exponential half-life weight for a non-negative age."""
    if age_hours < 0:
        raise ValueError("age_hours must be non-negative")
    if half_life_hours <= 0:
        raise ValueError("half_life_hours must be positive")
    return D(2) ** (-age_hours / half_life_hours)


def _invalid(anchor: int, decision_time: int, history_start: int, reason: str) -> Forecast:
    return Forecast(D(0), D(0), anchor, decision_time, history_start, False, reason)


def forecast(history: list[Funding], anchor: int, decision_time: int, config: Config) -> Forecast:
    """Forecast the configured horizon from verified, contiguous funding intervals."""
    if decision_time < anchor:
        return _invalid(anchor, decision_time, anchor, "Decision precedes forecast anchor")
    if not history:
        return _invalid(anchor, decision_time, anchor, "Funding history is empty")

    rows = sorted(history, key=lambda item: item.funding_time)
    lower = anchor - config.window_hours * HOUR
    relevant = [row for row in rows if row.funding_time <= anchor]
    if not relevant or relevant[-1].funding_time != anchor:
        return _invalid(anchor, decision_time, lower, "Anchor funding is missing")

    included_indexes = [index for index, row in enumerate(relevant) if row.funding_time > lower]
    if not included_indexes:
        return _invalid(anchor, decision_time, lower, "Forecast window has no observations")
    first = included_indexes[0]
    if first == 0:
        return _invalid(
            anchor, decision_time, relevant[0].funding_time, "Missing window antecedent"
        )

    antecedent = relevant[first - 1]
    if antecedent.funding_time > lower:
        return _invalid(anchor, decision_time, antecedent.funding_time, "Missing oldest antecedent")

    checked = relevant[first - 1 :]
    available_at = max(row.available_at for row in checked)
    for row in checked:
        if row.available_at > decision_time:
            return _invalid(
                anchor,
                decision_time,
                antecedent.funding_time,
                "Funding is not available at decision time",
            )
        if not row.interval_verified:
            return _invalid(
                anchor, decision_time, antecedent.funding_time, "Funding interval is unverified"
            )
        if row.interval_hours <= 0:
            return _invalid(
                anchor, decision_time, antecedent.funding_time, "Funding interval must be positive"
            )

    weighted_rates = D(0)
    weighted_hours = D(0)
    for index in included_indexes:
        row = relevant[index]
        previous = relevant[index - 1]
        actual_ns = row.funding_time - previous.funding_time
        if actual_ns <= 0:
            return _invalid(
                anchor, decision_time, antecedent.funding_time, "Actual intervals must be positive"
            )
        actual_hours = D(actual_ns) / D(HOUR)
        if actual_hours != row.interval_hours:
            return _invalid(
                anchor,
                decision_time,
                antecedent.funding_time,
                "Funding gap or non-contiguous interval",
            )
        age_hours = D(anchor - row.funding_time) / D(HOUR)
        observation_weight = weight(age_hours, D(config.half_life_hours))
        weighted_rates += observation_weight * row.funding_rate
        weighted_hours += observation_weight * actual_hours

    if weighted_hours <= 0:
        return _invalid(
            anchor, decision_time, antecedent.funding_time, "Weighted duration is not positive"
        )
    last = relevant[-1]
    horizon = D(config.horizon_hours)
    value = horizon * weighted_rates / weighted_hours
    no_change = horizon * last.funding_rate / last.interval_hours
    return Forecast(value, no_change, anchor, available_at, antecedent.funding_time, True, "")
