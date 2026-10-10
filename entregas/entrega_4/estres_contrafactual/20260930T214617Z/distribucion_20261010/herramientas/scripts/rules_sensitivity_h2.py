"""Pure, offline H2 postprocessing and an independent contract validator.

Only a strictly positive conditional CAGR and a strictly superior conditional
Sharpe support H2. Unknown metrics remain unknown; incomparability takes
precedence over a numerical verdict. No financial input is changed.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation, localcontext


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
