import gzip
import hashlib
import json

import pytest

from scripts.stress_counterfactual_delivery import verify_exports


def test_compact_export_checks_decompressed_bytes_against_original_manifest(tmp_path):
    data = b"a,b\n1,2\n"
    run = tmp_path / "evidencia" / "run_fixture"
    run.mkdir(parents=True)
    manifest = dict(output_hashes={"forecast_evaluation.csv": hashlib.sha256(data).hexdigest()})
    (run / "run_manifest.json").write_text(json.dumps(manifest))
    target = run / "forecast_evaluation.csv.gz"
    target.write_bytes(gzip.compress(data, mtime=0))
    record = dict(run_id="run_fixture", source_name="forecast_evaluation.csv",
                  package_path=target.relative_to(tmp_path).as_posix(),
                  sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
                  source_sha256=hashlib.sha256(data).hexdigest(), source_bytes=len(data),
                  bytes=target.stat().st_size, transfer="lossless_gzip")
    assert verify_exports(tmp_path, [record]) == 1
    target.write_bytes(gzip.compress(b"a,b\n1,3\n", mtime=0))
    record.update(sha256=hashlib.sha256(target.read_bytes()).hexdigest(), bytes=target.stat().st_size)
    with pytest.raises(ValueError, match="original"):
        verify_exports(tmp_path, [record])


def test_export_cannot_escape_package(tmp_path):
    with pytest.raises(ValueError, match="path"):
        verify_exports(tmp_path, [dict(package_path="../elsewhere", run_id="run_x")])


def test_counterfactual_daily_contrast_retains_later_path_changes():
    from scripts.stress_counterfactual_delivery import counterfactual_contrasts
    rows = []
    for scenario, balances in (("BASE_E3", [100, 90, 110]), ("CF_SIN_INTERRUPCION", [100, 98, 115])):
        previous = 100
        for i, balance in enumerate(balances):
            rows.append(dict(scenario=scenario, strategy="conditional", time_ns=i,
                             date=f"2023-03-{23+i}", equity_usdt=str(balance), net_pnl_usdt=str(balance-previous)))
            previous = balance
    result = counterfactual_contrasts(rows)
    assert [r["equity_delta_usdt"] for r in result] == [0, 8, 5]
    assert [r["daily_pnl_delta_usdt"] for r in result] == [0, 8, -3]


def test_cf_action_contrast_ignores_generated_ids_but_preserves_later_price_changes():
    from crypto_carry.config import timestamp
    from scripts.stress_counterfactual_delivery import counterfactual_actions
    before = timestamp("2023-03-24T11:27:59Z")
    after = timestamp("2023-03-26T12:00:00Z")
    rows = []
    for scenario in ("BASE_E3", "CF_SIN_INTERRUPCION"):
        for t in (before, after):
            rows.append(dict(scenario=scenario, strategy="conditional", symbol="BTCUSDT", market="spot",
                side="SELL", purpose="close_spot", time_ns=t, quantity="1", price="100" if scenario=="BASE_E3" or t==before else "101",
                ordinary_fee_usdt=0 if scenario == "BASE_E3" else "0",
                fill_id=scenario+str(t), order_id=scenario, run_id=scenario))
    result = counterfactual_actions(dict(fills_conciliados=rows), timestamp("2026-09-01T00:00:00Z"))
    prior = next(r for r in result if r["phase"] == "previo" and r["record_kind"] == "fills")
    later = next(r for r in result if r["phase"] == "posterior" and r["record_kind"] == "fills")
    assert prior["changed_matching_keys"] == 0
    assert later["changed_matching_keys"] == 1
    assert later["first_difference_time_ns"] == after


def test_cf_action_contrast_rejects_any_change_before_first_synthetic_availability():
    from crypto_carry.config import timestamp
    from scripts.stress_counterfactual_delivery import counterfactual_actions
    t = timestamp("2023-03-24T11:27:59Z")
    rows = [dict(scenario=s, strategy="conditional", symbol="BTCUSDT", time_ns=t,
                 decision_kind="entry", decision=d) for s,d in
            (("BASE_E3", "accepted"), ("CF_SIN_INTERRUPCION", "basis_negative"))]
    with pytest.raises(ValueError, match="before"):
        counterfactual_actions(dict(decisiones=rows), timestamp("2026-09-01T00:00:00Z"))


def test_cf_order_submitted_before_intervention_may_finish_differently_afterwards():
    from crypto_carry.config import timestamp
    from scripts.stress_counterfactual_delivery import counterfactual_actions
    t = timestamp("2023-03-24T11:27:59Z")
    rows = [dict(scenario=s, strategy="conditional", symbol="BTCUSDT", market="spot", side="SELL",
                 purpose="close_spot", submitted_at=t, requested_gross_quantity="1", terminal_status=status,
                 gross_executed_quantity=q) for s,status,q in
            (("BASE_E3", "expired", "0"), ("CF_SIN_INTERRUPCION", "filled", "1"))]
    result = counterfactual_actions(dict(ordenes=rows), timestamp("2026-09-01T00:00:00Z"))
    assert all(r["changed_matching_keys"] == 0 for r in result)
