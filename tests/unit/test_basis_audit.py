"""Independent source-audit boundary and corruption fixtures."""

import importlib.util
from decimal import Decimal
from pathlib import Path

import pytest

from crypto_carry.config import Config
from crypto_carry.risk import basis, entry_basis

SCRIPT = Path(__file__).resolve().parents[2] / "data/research/basis-audit-20260919/verify_basis.py"
SPEC = importlib.util.spec_from_file_location("basis_auditor", SCRIPT)
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)

D = Decimal
OPEN = 1756684800000000000
END = OPEN + 60_000_000_000


def raw(price="100", unit="ms", offset=0):
    scale = 1_000_000 if unit == "ms" else 1_000
    opening = (OPEN + offset) // scale
    return audit.parse_kline(
        [
            str(opening),
            "100",
            "101",
            "99",
            price,
            "2",
            str(opening + 60_000_000_000 // scale - 1),
            "200",
            "4",
            "1",
            "100",
            "0",
        ],
        unit,
    )


@pytest.mark.parametrize(
    "future,expected,classification,eligible",
    [
        ("99.95", "-0.0005", "negative", False),
        ("100", "0", "zero", True),
        ("100.5", "0.005", "positive_eligible", True),
        ("100.51", "0.0051", "above_max", False),
    ],
)
def test_manual_basis_units_and_inclusive_boundaries(future, expected, classification, eligible):
    result = audit.raw_basis(D("100"), D(future))
    assert result == D(expected)
    assert audit.classify(result) == classification
    assert basis(D("100"), D(future)) == result
    assert entry_basis(result, Config()) is eligible
    if future == "99.95":
        assert result * 100 == D("-0.05")
        assert result * 10000 == D("-5")


def test_millisecond_and_microsecond_sources_have_identical_exclusive_end():
    milliseconds, microseconds = raw(unit="ms"), raw(unit="us")
    for field in ("open_time", "end_time", "available_at"):
        assert milliseconds[field] == microseconds[field]
    assert milliseconds["reported_close_ns"] == END - 1_000_000
    assert microseconds["reported_close_ns"] == END - 1_000
    assert audit.pair_issues(milliseconds, microseconds, END + 1_000_000) == []


@pytest.mark.parametrize(
    "spot,future,now,reason",
    [
        (None, raw(), END, "source_missing:spot"),
        (raw(), raw(offset=60_000_000_000), END, "future_bar:futures"),
        (raw(offset=-60_000_000_000), raw(), END, "interval_mismatch"),
        (
            raw(offset=-60_000_000_000),
            raw(offset=-60_000_000_000),
            END,
            "not_latest_closed_minute:spot",
        ),
    ],
)
def test_invalid_observations_are_not_valid_history(spot, future, now, reason):
    assert reason in audit.pair_issues(spot, future, now)


def test_subtolerance_sign_change_is_still_a_classification_error():
    result = audit.compare_basis(D("-1e-15"), "0")
    assert not result["exceeds_tolerance"]
    assert result["classification_changed"]


def test_malformed_or_incomplete_kline_is_rejected():
    with pytest.raises(ValueError, match="12"):
        audit.parse_kline(["1", "2"], "ms")
    values = [
        "1756684800000",
        "100",
        "101",
        "99",
        "100",
        "1",
        "1756684800123",
        "100",
        "1",
        "1",
        "100",
        "0",
    ]
    with pytest.raises(ValueError, match="interval"):
        audit.parse_kline(values, "ms")


def test_deterministic_sample_has_temporal_coverage_and_extreme_cases():
    rows = [
        dict(decision_time_ns=i, basis_independent=str(D(i - 179) / 100000)) for i in range(365)
    ]
    sample = audit.select_sample(rows)
    assert len(sample) == 20
    assert len({r["decision_time_ns"] for r in sample}) == 20
    assert {0, 179, 364}.issubset({r["decision_time_ns"] for r in sample})
    assert sample == audit.select_sample(list(reversed(rows)))


def test_funding_diagnostic_does_not_block_permanent_entry():
    filters = {name: "pass" for name in audit.ENTRY_ORDER}
    filters["funding"] = "fail"
    assert audit.first_rejection(filters, funding_enabled=False) is None
    assert audit.first_rejection(filters, funding_enabled=True) == "funding"
    filters["basis_negative"] = "fail"
    assert audit.first_rejection(filters, funding_enabled=False) == "basis_negative"


def test_stage_comparison_locates_price_or_selection_corruption():
    source = raw()
    normalized = {**source, "close": "101"}
    assert "source_to_normalized:close" in audit.price_chain_issues(source, normalized, D("101"))
    assert "normalized_to_signal:close" in audit.price_chain_issues(source, source, D("99"))


def test_duplicate_source_open_is_rejected(tmp_path):
    import zipfile

    path = tmp_path / "sample.zip"
    line = "1756684800000,100,101,99,100,1,1756684859999,100,1,1,100,0\n"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("sample.csv", line + line)
    with pytest.raises(ValueError, match="duplicate"):
        audit.read_original_rows(path, "ms", {OPEN})
