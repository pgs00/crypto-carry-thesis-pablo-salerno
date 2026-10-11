"""The diagnostic must not turn historical observations into active rules."""

import hashlib
import importlib.util
import json
from decimal import Decimal
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[2] / "scripts/diagnose_historical_rules_exposure.py"
SPEC = importlib.util.spec_from_file_location("historical_rules_exposure", SCRIPT)
diagnostic = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(diagnostic)


def test_published_market_zero_is_unknown_semantics_without_modulo():
    assert diagnostic.quantity_candidate(Decimal("1.23"), "stepSize", Decimal(0)) == (
        None, "published_zero_semantics_unresolved"
    )
    assert diagnostic.quantity_candidate(Decimal("1.23"), "minQty", Decimal(0)) == (
        None, "published_zero_semantics_unresolved"
    )


def test_quantity_limits_are_order_limits():
    assert diagnostic.quantity_candidate(Decimal("0.007"), "stepSize", Decimal("0.001"))[0] is False
    assert diagnostic.quantity_candidate(Decimal("0.0075"), "stepSize", Decimal("0.001"))[0] is True
    assert diagnostic.quantity_candidate(Decimal("120"), "maxQty", Decimal("120"))[0] is False
    assert diagnostic.quantity_candidate(Decimal("120.001"), "maxQty", Decimal("120"))[0] is True


def test_decimal_tier_boundaries_and_derived_deductions():
    rows = [
        {"floor_usdt": "0", "cap_usdt": "100", "maintenance_rate": "0.01"},
        {"floor_usdt": "100", "cap_usdt": "1000", "maintenance_rate": "0.02"},
    ]
    tiers = diagnostic.derive_tiers(rows)
    assert tiers[1]["deduction"] == Decimal("1")
    assert diagnostic.maintenance_candidate(Decimal("100"), tiers) == (Decimal("1"), 0)
    assert diagnostic.maintenance_candidate(Decimal("100.01"), tiers) == (Decimal("1.0002"), 1)
    assert diagnostic.maintenance_candidate(Decimal(0), tiers) == (Decimal(0), None)
    with pytest.raises(ValueError, match="notional outside"):
        diagnostic.maintenance_candidate(Decimal("1000.01"), tiers)


def test_no_discontinuous_brackets_silently_accepted():
    with pytest.raises(ValueError, match="contiguous"):
        diagnostic.derive_tiers([
            {"floor_usdt": "0", "cap_usdt": "100", "maintenance_rate": "0.01"},
            {"floor_usdt": "101", "cap_usdt": "1000", "maintenance_rate": "0.02"},
        ])


def test_candidate_matrix_preserves_capture_and_unknown_knowledge():
    fact = {
        "id": "SPOT_OBS", "parameter": "MARKET_LOT_SIZE.stepSize", "symbol": "BTCUSDT",
        "market": "spot", "value_original": "0", "value_normalized": "0",
        "unit": "BTC", "status": "observacion_puntual", "source_ids": ["S"],
        "temporal": {"kind": "capture", "observed_at_utc": "2022-01-02T00:00:00Z"},
        "knowledge": {"known_from_utc": None}, "applicability": {},
    }
    row = diagnostic.integration_row(fact, {"S": {"original_url": "https://example.test"}})
    assert row["estado_documental"] == "observacion_puntual"
    assert row["loadable_by_rulebook"] is False
    assert row["known_from_utc"] is None
    assert "valid_from" not in row
    assert "cero" in row["semantica_pendiente"]


def test_market_max_notional_flag_is_respected():
    fact = {"parameter": "NOTIONAL.maxNotional", "applicability": {
        "flags": {"applyMaxToMarket": False}}}
    assert diagnostic.notional_applies(fact) is False
    fact["applicability"]["flags"]["applyMaxToMarket"] = True
    assert diagnostic.notional_applies(fact) is True
    assert diagnostic.notional_applies({"parameter": "MIN_NOTIONAL.notional",
                                       "applicability": {"flags": {}}}) is None


def test_source_paths_cannot_escape_root(tmp_path):
    with pytest.raises(ValueError, match="escapes"):
        diagnostic.inside(tmp_path, "../outside.txt")


def test_output_integrity_is_read_only_and_detects_tampering(tmp_path):
    item = tmp_path / "data.csv"
    item.write_bytes(b"run_id,value\nreference,0\n")
    manifest = {"files": [{"path": item.name, "bytes": item.stat().st_size,
                           "sha256": hashlib.sha256(item.read_bytes()).hexdigest()}]}
    seal = tmp_path / "manifest.json"
    seal.write_text(json.dumps(manifest), encoding="utf-8")
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    assert diagnostic.verify_output(tmp_path)["passed"] is True
    assert before == {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    item.write_bytes(b"run_id,value\nreference,1\n")
    with pytest.raises(ValueError, match="differs from manifest"):
        diagnostic.verify_output(tmp_path)
