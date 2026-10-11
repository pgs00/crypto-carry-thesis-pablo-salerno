"""Actual native journals must pass the separate portable formula/coverage auditor."""

import json

import pytest
from test_stress_counterfactual_native import cf_fixture, config, market, shock

from crypto_carry.models import MinuteBar
from crypto_carry.stress_counterfactual import ScenarioBacktest, plain_bar
from scripts.return_capital.common import parquet, read_json
from scripts.run_stress_counterfactual import export_observations
from scripts.stress_counterfactual_audit import (
    audit_interventions,
    audit_observation_population,
    audit_opportunity,
    audit_witness_sources,
)
from scripts.stress_counterfactual_report import decode_interventions, window_diagnostics


@pytest.mark.parametrize("kind", ["shock", "counterfactual"])
def test_actual_saved_native_journal_passes_separate_diagnostics(start, rules, tmp_path, kind):
    if kind == "shock":
        spec, raw, seconds = shock(start), market(start), 4800
    else:
        start, spec, raw = cf_fixture()
        seconds = 9600
    cfg = config(start, seconds=seconds, sizing_model="joint_quantity")
    backtest = ScenarioBacktest(cfg, rules, scenario=spec).run(raw)
    export_observations(tmp_path, backtest)
    sources = {(r.symbol, r.market, r.open_time): dict(plain_bar(r), present=True)
               for r in raw if isinstance(r, MinuteBar)}
    interventions = decode_interventions(tmp_path / "intervenciones.parquet")
    assert audit_interventions(spec, sources, interventions, backtest.now)["passed"]
    witnesses = [json.loads(r["evidence_json"]) for r in parquet(tmp_path / "oportunidad_ventanas.parquet")]
    state = read_json(tmp_path / "estado_capa.json")
    assert audit_observation_population(spec, state, parquet(tmp_path / "observaciones_ventanas.parquet"),
                                        witnesses, start, backtest.now)["passed"]
    for witness in witnesses:
        audit_witness_sources(spec, sources, witness)
        audit_opportunity(witness, cfg)
    result = window_diagnostics(tmp_path, spec, cfg, sources)
    assert result["ventanas_resumen"]
    assert result["garantias_simultaneas"]
