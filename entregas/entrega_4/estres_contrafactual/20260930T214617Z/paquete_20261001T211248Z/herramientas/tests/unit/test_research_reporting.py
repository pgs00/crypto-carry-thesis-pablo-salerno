"""Research reporting keeps observed inputs and prescribed assumptions explicit."""

import json
from dataclasses import asdict
from decimal import Decimal as D

import pytest

from crypto_carry.config import HOUR, Config, timestamp
from crypto_carry.data.prescribed import prescribed_rules
from crypto_carry.models import Funding
from crypto_carry.strategy import Backtest


def research_config(**changes):
    return Config(
        analysis_mode="prescribed_research",
        fee_profile="prescribed_fixed_no_discounts",
        start="2024-01-01T00:00:00Z",
        end="2024-01-02T00:00:00Z",
        **changes,
    )


def quality(config, audit):
    return {
        "status": "complete",
        "issues": [],
        "start": config.start,
        "end": config.end,
        "analysis_mode": config.analysis_mode,
        "historical_certified": False,
        "full_baseline_coverage": False,
        "research_assumptions": {"validated": True},
        "funding_mark_audit": audit,
        "coverage": [],
    }


def funding(config, method, *, stress="0", warmup=False):
    start = timestamp(config.start)
    funding_time = start - HOUR if warmup else start + HOUR
    return Funding(
        "BTCUSDT",
        funding_time,
        funding_time,
        D("0.001"),
        D("8"),
        D("100"),
        "funding.parquet",
        True,
        method,
        "funding.parquet" if method == "exact" else "marks.parquet",
        funding_time if method == "exact" else funding_time - 1,
        funding_time,
        None if method == "exact" else D("100.01"),
        D(stress),
    )


def test_research_run_persists_hashed_assumptions_and_used_mark_provenance(tmp_path):
    from crypto_carry.reporting import regenerate_report, verify_run, write_run

    config = research_config()
    backtests = [
        Backtest(config, prescribed_rules(config), "conditional", True),
        Backtest(config, prescribed_rules(config), "permanent", False),
    ]
    observed = [
        funding(config, "exact"),
        funding(config, "previous_closed_1m"),
        funding(config, "not_required_before_start", warmup=True),
    ]
    for backtest in backtests:
        backtest.all_funding = list(observed)
    audit = [asdict(item) for item in observed]
    run = write_run(
        tmp_path,
        config,
        backtests,
        quality(config, audit),
        "historical_assumptions",
        inputs={"observed": "a" * 64},
    )

    manifest = json.loads((run / "run_manifest.json").read_text(encoding="utf-8"))
    assert {"research_assumptions.json", "funding_mark_audit.json"} <= set(
        manifest["output_hashes"]
    )
    assumptions = json.loads((run / "research_assumptions.json").read_text(encoding="utf-8"))
    assert assumptions["analysis_mode"] == "prescribed_research"
    assert assumptions["methodology"]["historical_reconstruction"] is False
    mark_audit = json.loads((run / "funding_mark_audit.json").read_text(encoding="utf-8"))
    assert mark_audit["validated_count"] == 3
    assert mark_audit["engine_consumed_count"] == 6
    assert mark_audit["exact_consumed_count"] == 2
    assert mark_audit["proxy_consumed_count"] == 2
    assert mark_audit["warmup_not_required_count"] == 2
    assert mark_audit["counts_by_strategy"] == {
        "conditional": {"exact": 1, "not_required_before_start": 1, "previous_closed_1m": 1},
        "permanent": {"exact": 1, "not_required_before_start": 1, "previous_closed_1m": 1},
    }
    assert {(row["strategy"], row["funding_filter_enabled"]) for row in mark_audit["consumed"]} == {
        ("conditional", True),
        ("permanent", False),
    }
    assert {row["settlement_mark_method"] for row in mark_audit["consumed"]} == {
        "exact",
        "previous_closed_1m",
        "not_required_before_start",
    }
    report = (run / "report.md").read_text(encoding="utf-8")
    assert "PRECIOS OBSERVADOS CON SUPUESTOS PRESCRIPTOS" in report
    assert "no certifica una reconstrucción histórica" in report
    assert "2 exactos, 2 proxies causales y 2 observaciones de precalentamiento" in report
    assert "reglas históricas" not in report
    assert "SINTÉTICO" not in report
    assert verify_run(run)["valid"] is True
    assert regenerate_report(run) == run / "report.md"


@pytest.mark.parametrize(
    ("config", "data_kind"),
    [
        (Config(), "historical_assumptions"),
        (research_config(), "historical"),
        (research_config(), "synthetic"),
    ],
)
def test_reporting_rejects_analysis_mode_and_data_kind_mismatches(tmp_path, config, data_kind):
    from crypto_carry.reporting import write_run

    with pytest.raises(ValueError, match="analysis_mode|data_kind"):
        write_run(tmp_path, config, [], {"status": "incomplete_data"}, data_kind)


def test_research_sensitivities_are_one_factor_changes_and_keep_both_cost_multipliers():
    from crypto_carry.robustness import scenario_configs

    base = research_config()
    scenarios = scenario_configs(base)
    expected = {
        "funding-proxy-plus-10": ("funding_proxy_stress_bps", D("10")),
        "funding-proxy-minus-10": ("funding_proxy_stress_bps", D("-10")),
        "futures-fee-0p0004": ("research_futures_taker_fee", D("0.0004")),
        "maintenance-2": ("research_maintenance_multiplier", D("2")),
        "liquidation-fee-0p03": ("research_liquidation_fee", D("0.03")),
    }
    by_name = {scenario.name: scenario for scenario in scenarios}
    for name, (field, value) in expected.items():
        scenario = by_name[name]
        assert scenario.changed_fields == (field,)
        assert getattr(scenario.config, field) == value
        differing = {
            key
            for key, base_value in base.to_dict().items()
            if scenario.config.to_dict()[key] != base_value
        }
        assert differing == {field}
    assert {s.value for s in scenarios if s.dimension == "cost"} >= {"2", "3"}


def test_robustness_default_infers_research_data_kind_and_prescribed_rules(tmp_path, monkeypatch):
    from crypto_carry import robustness

    config = research_config()
    captured = []

    def validate(current, root, scope):
        return quality(current, [])

    def save(root, current, backtests, evidence, data_kind, **kwargs):
        captured.append(
            (data_kind, len(backtests), backtests[0].rules.records if backtests else [])
        )
        path = root / "outputs" / f"run-{len(captured)}"
        path.mkdir(parents=True)
        return path

    monkeypatch.setattr(robustness, "validate_data", validate)
    monkeypatch.setattr(robustness, "input_hashes", lambda root, current: {})
    monkeypatch.setattr(robustness, "iter_records", lambda *args, **kwargs: [])
    monkeypatch.setattr("crypto_carry.reporting.write_run", save)
    monkeypatch.setattr(robustness, "_cost_plot", lambda *args, **kwargs: None)
    monkeypatch.setattr(robustness, "_index_report", lambda *args, **kwargs: "report\n")
    monkeypatch.setattr(robustness, "verify_robustness", lambda path: {"valid": True})

    robustness.run_robustness(tmp_path, config, selected=["baseline"])
    assert captured[0][0] == "historical_assumptions"
    assert captured[0][1] == 2
    assert captured[0][2]
