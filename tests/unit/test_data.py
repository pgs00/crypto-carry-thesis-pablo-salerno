"""Market-rule knowledge time, validity and immutable snapshot contracts."""
from decimal import Decimal

import pytest

from crypto_carry.data.rules import RuleBook


def _rule_record(*, evidence_status="verified", valid_from=0, valid_to=None, known_from=0):
    return {
        "symbol": "BTCUSDT",
        "market": "spot",
        "rule_type": "market",
        "valid_from": valid_from,
        "valid_to": valid_to,
        "known_from": known_from,
        "source_url": "https://example.invalid/dated-evidence",
        "source_publication_time": known_from,
        "retrieved_at": known_from,
        "evidence_status": evidence_status,
        "values": {
            "step": "0.001",
            "tick": "0.01",
            "min_qty": "0.001",
            "max_qty": "1000",
            "min_notional": "5",
            "max_notional": "10000000",
            "taker_fee": "0.001",
            "tiers": [],
            "liquidation_fee": "0",
            "liquidation_regular_fee": True,
            "liquidation_fee_basis": "execution_notional",
            "operational": True,
        },
    }


def test_rulebook_requires_validity_knowledge_and_verified_evidence():
    book = RuleBook([_rule_record(valid_from=100, valid_to=300, known_from=200)])
    assert book.get("BTCUSDT", "spot", 199) is None
    assert book.get("BTCUSDT", "spot", 200) is not None
    assert book.get("BTCUSDT", "spot", 300) is None

    current = RuleBook(
        [_rule_record(evidence_status="current_snapshot", valid_from=500, known_from=500)]
    )
    assert current.get("BTCUSDT", "spot", 499) is None
    assert current.get("BTCUSDT", "spot", 500) is not None

    synthetic = RuleBook([_rule_record(evidence_status="synthetic")])
    assert synthetic.get("BTCUSDT", "spot", 100) is None
    assert (
        RuleBook([_rule_record(evidence_status="synthetic")], allow_synthetic=True).get(
            "BTCUSDT", "spot", 100
        )
        is not None
    )


def test_rulebook_rejects_overlapping_snapshots_and_reports_boundaries():
    with pytest.raises(ValueError, match="Overlapping market-rule"):
        RuleBook([_rule_record(valid_from=0, valid_to=200), _rule_record(valid_from=100)])

    book = RuleBook([_rule_record(valid_from=100, valid_to=300, known_from=200)])
    assert book.transition_times(50, 350) == [100, 200, 300]


def test_rulebook_snapshot_is_independent_of_mutable_input_values():
    record = _rule_record(valid_from=100, valid_to=300, known_from=200)
    book = RuleBook([record])
    record["values"]["taker_fee"] = "0.25"

    assert book.get("BTCUSDT", "spot", 200).taker_fee == Decimal("0.001")
    assert book.records[0]["values"]["taker_fee"] == "0.001"


def test_rulebook_queries_do_not_reuse_future_or_expired_snapshots():
    first = _rule_record(valid_from=100, valid_to=300, known_from=200)
    second = _rule_record(valid_from=300, valid_to=500, known_from=350)
    second["values"]["taker_fee"] = "0.002"
    book = RuleBook([first, second])

    for at, expected in ((400, "0.002"), (200, "0.001"), (300, None), (199, None), (500, None)):
        rule = book.get("BTCUSDT", "spot", at)
        assert (rule.taker_fee if rule else None) == (Decimal(expected) if expected else None)
