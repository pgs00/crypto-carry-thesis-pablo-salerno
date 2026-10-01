import json
from decimal import Decimal

import pytest

from crypto_carry.config import Config, timestamp
from crypto_carry.data.prescribed import prescribed_rules, research_assumptions
from crypto_carry.data.rules import RuleBook


def research_config(**kwargs):
    return Config(
        analysis_mode="prescribed_research", fee_profile="prescribed_fixed_no_discounts", **kwargs
    )


def test_strict_rulebook_never_accepts_prescribed_evidence():
    research_book = prescribed_rules(research_config())
    strict_book = RuleBook(research_book.records)

    assert strict_book.get("BTCUSDT", "spot", timestamp("2022-01-01T00:00:00Z")) is None


@pytest.mark.parametrize("status", ["verified", "current_snapshot"])
def test_historical_rule_with_unknown_knowledge_time_is_never_selected(status):
    config = Config(
        analysis_mode="prescribed_research", fee_profile="prescribed_fixed_no_discounts"
    )
    record = dict(prescribed_rules(config).records[0], known_from=None, evidence_status=status)
    book = RuleBook([record])
    assert book.get(record["symbol"], record["market"], timestamp(config.start)) is None


def test_research_fee_label_cannot_claim_historical_promotions():
    with pytest.raises(ValueError, match="fee_profile"):
        Config(analysis_mode="prescribed_research")


def test_prescribed_rules_require_explicit_research_opt_in():
    with pytest.raises(ValueError, match="prescribed_research"):
        prescribed_rules(Config())

    rule = prescribed_rules(research_config()).get(
        "BTCUSDT", "spot", timestamp("2022-01-01T00:00:00Z")
    )
    assert rule is not None
    assert rule.step == Decimal("0.00001")


def test_prescribed_rulebook_contains_complete_fixed_table():
    book = prescribed_rules(research_config())
    at = timestamp("2024-06-01T00:00:00Z")

    expected = {
        ("BTCUSDT", "spot"): (
            "0.00001",
            "0.01",
            "0.00001",
            "128.52621715",
            "10",
            "9000000",
            "0.001",
        ),
        ("ETHUSDT", "spot"): (
            "0.0001",
            "0.01",
            "0.0001",
            "3277.54882761",
            "10",
            "9000000",
            "0.001",
        ),
        ("BTCUSDT", "futures"): ("0.001", "0.1", "0.001", "120", "100", "100000000", "0.0005"),
        ("ETHUSDT", "futures"): ("0.001", "0.01", "0.001", "2000", "20", "100000000", "0.0005"),
    }
    for key, values in expected.items():
        rule = book.get(*key, at)
        assert rule is not None
        assert (
            tuple(
                str(getattr(rule, field))
                for field in (
                    "step",
                    "tick",
                    "min_qty",
                    "max_qty",
                    "min_notional",
                    "max_notional",
                    "taker_fee",
                )
            )
            == values
        )
        assert rule.operational

    btc = book.get("BTCUSDT", "futures", at)
    eth = book.get("ETHUSDT", "futures", at)
    assert btc is not None and eth is not None
    assert [(t.floor, t.cap, t.rate, t.deduction) for t in btc.tiers] == [
        (Decimal("0"), Decimal("50000"), Decimal("0.004"), Decimal("0")),
        (Decimal("50000"), Decimal("100000000"), Decimal("0.01"), Decimal("300")),
    ]
    assert [(t.floor, t.cap, t.rate, t.deduction) for t in eth.tiers] == [
        (Decimal("0"), Decimal("50000"), Decimal("0.0065"), Decimal("0")),
        (Decimal("50000"), Decimal("100000000"), Decimal("0.01"), Decimal("175")),
    ]
    assert btc.liquidation_fee == eth.liquidation_fee == Decimal("0.0125")
    assert btc.liquidation_regular_fee and eth.liquidation_regular_fee
    assert btc.liquidation_fee_basis == eth.liquidation_fee_basis == "execution_notional"


def test_maintenance_multiplier_scales_rates_and_deductions_continuously():
    config = research_config(research_maintenance_multiplier=Decimal("2"))
    book = prescribed_rules(config)
    at = timestamp(config.start)

    btc = book.get("BTCUSDT", "futures", at)
    eth = book.get("ETHUSDT", "futures", at)
    assert btc is not None and eth is not None
    assert [(t.rate, t.deduction) for t in btc.tiers] == [
        (Decimal("0.008"), Decimal("0")),
        (Decimal("0.02"), Decimal("600")),
    ]
    assert [(t.rate, t.deduction) for t in eth.tiers] == [
        (Decimal("0.0130"), Decimal("0")),
        (Decimal("0.02"), Decimal("350")),
    ]
    for rule in (btc, eth):
        first, second = rule.tiers
        assert (
            first.cap * first.rate - first.deduction
            == second.floor * second.rate - second.deduction
        )


@pytest.mark.parametrize(
    "override",
    [
        {"analysis_mode": "unknown"},
        {"funding_proxy_stress_bps": Decimal("NaN")},
        {"funding_proxy_stress_bps": Decimal("10000")},
        {"funding_proxy_stress_bps": Decimal("-10000")},
        {"research_futures_taker_fee": Decimal("-0.1")},
        {"research_futures_taker_fee": Decimal("1")},
        {"research_maintenance_multiplier": Decimal("0")},
        {"research_liquidation_fee": Decimal("-0.1")},
        {"research_liquidation_fee": Decimal("1")},
        {"research_futures_taker_fee": Decimal("0.0004")},
    ],
)
def test_invalid_or_strict_research_configuration_is_rejected(override):
    with pytest.raises(ValueError):
        Config(**override)


def test_research_assumptions_are_versioned_serializable_and_honest_about_provenance():
    declaration = research_assumptions(research_config())

    json.dumps(declaration)
    assert declaration["version"] == "prescribed-research-rules-v1"
    assert declaration["declared_at"] == "2026-09-18T00:00:00Z"
    assert declaration["methodology"]["historical_reconstruction"] is False
    assert declaration["methodology"]["rules_are_model_constraints"] is True
    assert all(record["evidence_status"] == "prescribed" for record in declaration["rules"])
    assert all(record["known_from"] == "2026-09-18T00:00:00Z" for record in declaration["rules"])
    assert all(
        record["source_publication_time"] == "2026-09-18T00:00:00Z"
        for record in declaration["rules"]
    )
    assert set(declaration["provenance"]) == {
        "docs/research/public_rules_alternatives_20260918.json",
        "docs/research/public_rules_alternatives_20260918.md",
        "docs/research/fees_followup_20260918.md",
        "docs/research/historical_market_rules.md",
        "docs/research/methodology_two_days_20260918.md",
    }
