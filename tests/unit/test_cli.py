import json

from crypto_carry.cli import main
from crypto_carry.config import Config
from crypto_carry.robustness import scenario_configs


def test_doctor_checks_real_installed_engine_without_network(tmp_path, capsys):
    config = tmp_path / "base.toml"
    config.write_text(Config().to_toml(), encoding="utf-8")
    assert main(["--root", str(tmp_path), "doctor", "--config", str(config)]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["nautilus_trader"] == "1.231.0"
    assert output["data_budget_bytes"] == 20_000_000_000


def test_missing_historical_inputs_yield_incomplete_status_without_running_engine(
    tmp_path, monkeypatch, capsys
):
    from crypto_carry import cli

    config = tmp_path / "base.toml"
    config.write_text(Config().to_toml(), encoding="utf-8")
    captured = {}

    def save(root, config, backtests, quality, **kwargs):
        captured.update(quality=quality, backtests=backtests, kwargs=kwargs)
        return root / "outputs" / "diagnostic"

    monkeypatch.setattr(cli, "write_run", save)
    assert main(["--root", str(tmp_path), "backtest", "--config", str(config)]) == 2
    assert captured["backtests"] == []
    assert captured["quality"]["status"] == "incomplete_data"
    assert captured["kwargs"]["data_kind"] == "historical"


def test_report_run_id_cannot_escape_outputs(tmp_path, capsys):
    assert main(["--root", str(tmp_path), "report", "--run-id", "../../elsewhere"]) == 1
    assert "run-id" in capsys.readouterr().err


def test_cli_report_restores_a_missing_derived_file(tmp_path):
    from crypto_carry.reporting import write_run

    run = write_run(
        tmp_path,
        Config(),
        [],
        {"status": "incomplete_data", "issues": ["missing inputs"]},
        "historical",
    )
    path = run / "report.md"
    original = path.read_bytes()
    path.unlink()
    assert main(["--root", str(tmp_path), "report", "--run-id", run.name]) == 0
    assert path.read_bytes() == original


def test_robustness_index_has_a_working_report_command_and_checks_subruns(tmp_path):
    from crypto_carry.robustness import run_robustness

    path = run_robustness(tmp_path, Config(), selected=["baseline"])
    assert main(["--root", str(tmp_path), "report", "--run-id", path.name]) == 0
    manifest = json.loads((path / "run_manifest.json").read_text())
    subrun = tmp_path / "outputs" / manifest["baseline_run_id"]
    (subrun / "metrics.csv").write_text("corruption", encoding="utf-8")
    assert main(["--root", str(tmp_path), "report", "--run-id", path.name]) == 1


def test_robustness_is_predefined_one_factor_at_a_time_and_preserves_baseline():
    base = Config()
    scenarios = scenario_configs(base)
    assert len(scenarios) == 30
    for item in scenarios:
        changes = {k for k, v in item.config.to_dict().items() if v != base.to_dict()[k]}
        assert changes <= set(item.changed_fields)
        assert len(changes) <= 1 or changes == {"horizon_hours", "holding_hours"}
    assert {s.config.capital for s in scenarios if s.dimension == "aum"} == {10000, 100000, 1000000}
    assert base == Config()


def test_short_range_does_not_fail_because_of_unrequested_future_start_scenarios():
    base = Config(start="2022-01-01T00:00:00Z", end="2022-01-03T00:00:00Z")
    scenarios = scenario_configs(base)
    assert any(s.name == "cost-2" for s in scenarios)
    assert not any(s.dimension == "start" for s in scenarios)
