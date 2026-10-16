"""Literal basis units and inclusive entry bounds from the original contract."""
from decimal import Decimal as D

import pytest

from crypto_carry.config import Config
from crypto_carry.risk import basis, entry_basis


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
    result = basis(D("100"), D(future))
    assert result == D(expected)
    assert entry_basis(result, Config()) is eligible
    if future == "99.95":
        assert result * 100 == D("-0.05")
        assert result * 10000 == D("-5")
