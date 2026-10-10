import pytest

from scripts.stress_counterfactual_audit import audit_window_price_sources, audit_witness_sources

M = 60_000_000_000


def original():
    return dict(symbol="BTCUSDT", market="spot", open_time=0, end_time=M, available_at=M,
                open="100", high="100", low="100", close="100", base_volume="1",
                quote_volume="100", trade_count=1, source_file="original", present=True)


def test_h3_witness_cannot_invent_an_unmodified_future():
    source = dict(original(), market="futures")
    bar = {k: v for k, v in source.items() if k != "present"}
    witness = dict(symbol="BTCUSDT", time_ns=M, spot_bar=None, future_bar=bar)
    sources = {("BTCUSDT", "futures", 0): source}
    assert audit_witness_sources(dict(kind="off"), sources, witness)
    bar["close"] = "101"
    with pytest.raises(ValueError, match="source"):
        audit_witness_sources(dict(kind="off"), sources, witness)


def test_stale_shock_valuation_keeps_original_timestamp_with_current_factor():
    from decimal import Decimal as D

    from scripts.stress_counterfactual_audit import record_digest
    source = original()
    raw = {k: v for k, v in source.items() if k != "present"}
    spec = dict(id="SH", kind="shock", magnitudes={"BTCUSDT": D(".1")}, episodes=[("BTCUSDT", M, 4*M)])
    asset = dict(original_spot_available_at=M, original_spot_price="100",
                 original_spot_source="original", original_spot_record_sha256=record_digest(raw),
                 spot_source_available_at=M, spot_price="90", factor=".9")
    snapshot = dict(time_ns=3*M, assets={"BTCUSDT": asset})
    assert audit_window_price_sources(spec, {("BTCUSDT", "spot", 0): source}, snapshot)
    asset["spot_price"] = "91"
    with pytest.raises(ValueError, match="valuation"):
        audit_window_price_sources(spec, {("BTCUSDT", "spot", 0): source}, snapshot)


def test_current_available_bar_cannot_be_hidden_as_missing_in_h3():
    witness = dict(symbol="BTCUSDT", time_ns=M, spot_bar=None, future_bar=None)
    with pytest.raises(ValueError, match="current"):
        audit_witness_sources(dict(kind="off"), {("BTCUSDT", "spot", 0): original()}, witness)


def test_fresh_witness_extract_matches_persisted_schema_for_missing_minutes(tmp_path, monkeypatch):
    from scripts import stress_counterfactual_sources as sources

    present = dict(original(), source_path="part.parquet", source_sha256="source-hash")
    absent = dict(symbol="BTCUSDT", market="spot", open_time=M, end_time=2*M,
                  base_volume=None, quote_volume=None, source_file=None, trade_count=None,
                  present=False, source_path=None, source_sha256=None)
    monkeypatch.setattr(sources, "witness_keys", lambda unused: {
        ("BTCUSDT", "spot", 0), ("BTCUSDT", "spot", M)})
    monkeypatch.setattr(sources, "extract_windows", lambda *unused: [present, absent])
    item = dict(run_id="test_run", evidence_manifest_sha256="evidence-hash")

    fresh = sources.extract_witness_sources(tmp_path, item, tmp_path, None, {})
    persisted = sources.extract_witness_sources(tmp_path, item, tmp_path, None, {})

    assert fresh == persisted
    assert fresh[1]["available_at"] is None
    assert fresh[1]["close"] is None
    assert fresh[1]["present"] is False
