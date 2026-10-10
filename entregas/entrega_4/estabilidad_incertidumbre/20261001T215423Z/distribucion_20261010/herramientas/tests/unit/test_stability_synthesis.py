"""Directed fixtures for the saved-state liquidation diagnostic, without replays."""

import hashlib
from pathlib import Path

import pytest


def diagnostic(risks, orders=(), positions=(), **kwargs):
    from scripts.stability_uncertainty_synthesis import diagnose_records

    defaults = dict(complete=True, code_instrumented=True,
                    expected_risk_count=len(risks), expected_order_count=len({
                        x["order_id"] for x in orders}))
    defaults.update(kwargs)
    return diagnose_records(risks, list(orders), list(positions), **defaults)


def test_complete_logged_history_excludes_activation_not_just_liquidation_fills():
    risks = [{"time_ns": 1, "symbol": "ETHUSDT", "kind": "close_requested",
              "cause": "margin", "liquidation": False}]
    assert diagnostic(risks)["status"] == "rama_no_activada"


@pytest.mark.parametrize("override", [dict(complete=False), dict(code_instrumented=False),
                                      dict(expected_risk_count=2),
                                      dict(expected_risk_count=None)])
def test_missing_or_truncated_evidence_stays_indeterminate(override):
    assert diagnostic([], **override)["status"] == "indeterminada"


def test_ordinary_retry_after_escalation_detected_without_liquidation_fill():
    risks = [{"time_ns": 10, "symbol": "ETHUSDT", "kind": "close_requested",
              "cause": "liquidation", "liquidation": True}]
    orders = [dict(time_ns=11, symbol="ETHUSDT", order_id="old", action="timeout",
                   purpose="close_perp", remaining_quantity="0.25", record_type="event"),
              dict(time_ns=12, symbol="ETHUSDT", order_id="retry", action="submitted",
                   purpose="close_perp", quantity="0.25", record_type="event")]
    positions = [dict(time_ns=10, symbol="ETHUSDT", state="LIQUIDATING", short="0.25",
                      snapshot_kind="event")]
    result = diagnostic(risks, orders, positions)
    assert result["status"] == "afectada"
    assert any(x["finding"] == "reintento_ordinario_con_corto" for x in result["events"])


def test_holding_with_residual_short_after_liquidation_is_affected():
    risks = [dict(time_ns=10, symbol="BTCUSDT", kind="close_requested",
                  cause="liquidation", liquidation=True),
             dict(time_ns=12, symbol="BTCUSDT", kind="transition", previous="LIQUIDATING",
                  state="HOLDING", cause="rebalance_first_leg_failed")]
    positions = [dict(time_ns=12, symbol="BTCUSDT", state="HOLDING", short="0.010",
                      snapshot_kind="event")]
    assert diagnostic(risks, positions=positions)["status"] == "afectada"


def test_no_cross_asset_matching_or_inference_from_daily_snapshot():
    risks = [dict(time_ns=10, symbol="BTCUSDT", kind="close_requested",
                  cause="liquidation", liquidation=True),
             dict(time_ns=12, symbol="ETHUSDT", kind="transition", state="HOLDING")]
    positions = [dict(time_ns=12, symbol="ETHUSDT", state="HOLDING", short="1",
                      snapshot_kind="event")]
    assert diagnostic(risks, positions=positions)["status"] == "pendiente_escalada"


def test_boolean_string_is_not_silently_accepted_as_evidence():
    risks = [dict(time_ns=10, symbol="BTCUSDT", kind="close_requested",
                  cause="margin", liquidation="False")]
    with pytest.raises(ValueError, match="boolean"):
        diagnostic(risks)


def test_authenticated_member_rejects_actual_byte_tampering(tmp_path: Path):
    from scripts.stability_uncertainty_synthesis import authenticate_member

    source = tmp_path / "source.csv"
    source.write_text("metric,value\nreturn,1\n", encoding="utf-8")
    entry = dict(path="source.csv", sha256=hashlib.sha256(source.read_bytes()).hexdigest())
    manifest = dict(members=[entry])
    authenticate_member(tmp_path, manifest, "source.csv")
    source.write_text("metric,value\nreturn,2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="SHA256"):
        authenticate_member(tmp_path, manifest, "source.csv")


def test_offline_diagnostic_recomputes_from_compact_inputs(tmp_path: Path):
    from scripts.stability_uncertainty_synthesis import verify_diagnostics, write_json_gz

    source = tmp_path / "fuentes" / "sintesis_diagnostico.json.gz"
    source.parent.mkdir()
    case = dict(block="B2", scenario="H336", strategy="conditional", run_id="fixture",
                risks=[], orders=[], positions=[], complete=True, code_instrumented=True,
                expected_risk_count=0, expected_order_count=0)
    write_json_gz(source, [case])
    result = verify_diagnostics(tmp_path)
    assert result["statuses"] == {"rama_no_activada": 1}
    case["expected_risk_count"] = 1
    write_json_gz(source, [case])
    assert verify_diagnostics(tmp_path)["statuses"] == {"indeterminada": 1}


def test_offline_verifier_requires_authentic_sources(tmp_path: Path):
    from scripts.stability_uncertainty_synthesis import verify

    with pytest.raises((FileNotFoundError, ValueError)):
        verify(tmp_path)
