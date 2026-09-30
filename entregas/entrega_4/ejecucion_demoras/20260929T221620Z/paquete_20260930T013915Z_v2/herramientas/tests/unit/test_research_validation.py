import json

import pytest
from test_validation_scope import _case, _entry, _rows, _save, _write_rows

from crypto_carry.cli import main
from crypto_carry.config import timestamp
from crypto_carry.data.validate import validate_data


def research(config):
    return config.changed(
        analysis_mode="prescribed_research", fee_profile="prescribed_fixed_no_discounts"
    )


def missing_marks(root):
    config, manifest = _case(root)
    entry = _entry(manifest, "funding")
    rows = _rows(root, entry)
    # Keep one non-null exact observation so the storage schema stays string.
    for row in rows[1:]:
        row["settlement_mark_price"] = None
    _write_rows(root, entry, rows)
    _save(root, manifest)
    (root / config.rules_file).unlink()
    return config, manifest


def test_research_validation_resolves_only_economic_marks_and_does_not_certify_history(tmp_path):
    config, _ = missing_marks(tmp_path)
    strict = validate_data(config, tmp_path)
    assert strict["status"] == "incomplete_data"
    result = validate_data(research(config), tmp_path)
    assert result["status"] == "complete", result["issues"]
    assert result["analysis_mode"] == "prescribed_research"
    assert result["historical_certified"] is False
    assert result["full_baseline_coverage"] is False
    proxy = [
        r
        for r in result["funding_mark_audit"]
        if r["settlement_mark_method"] == "previous_closed_1m"
    ]
    assert len(proxy) == 3
    assert all(r["funding_time"] >= timestamp(config.sample_start) for r in proxy)
    assert all(r["settlement_mark_available_at"] <= r["funding_time"] for r in proxy)


@pytest.mark.parametrize("defect", ["candle", "hash", "trades", "calendar", "future_candle"])
def test_research_approval_cannot_waive_other_integrity_gates(tmp_path, defect):
    config, manifest = missing_marks(tmp_path)
    if defect in {"candle", "hash", "future_candle"}:
        entry = _entry(manifest, "marks")
        rows = _rows(tmp_path, entry)
        if defect == "candle":
            rows.pop(0)
            _write_rows(tmp_path, entry, rows)
        elif defect == "future_candle":
            rows[0]["available_at"] += 1
            _write_rows(tmp_path, entry, rows)
        else:
            entry["sha256"] = "0" * 64
    elif defect == "trades":
        _entry(manifest, "trades")["trade_id_continuous"] = False
    else:
        (tmp_path / "data/manifests/download.json").unlink()
    _save(tmp_path, manifest)
    assert validate_data(research(config), tmp_path)["status"] == "incomplete_data"


def test_cli_selects_research_report_even_when_data_are_incomplete(tmp_path, monkeypatch, capsys):
    from crypto_carry import cli
    from crypto_carry.config import Config

    path = tmp_path / "research.toml"
    path.write_text(research(Config()).to_toml(), encoding="utf-8")
    captured = {}

    def save(root, config, backtests, quality, **kwargs):
        captured.update(kwargs, quality=quality, backtests=backtests)
        return root / "outputs" / "diagnostic"

    monkeypatch.setattr(cli, "write_run", save)
    assert main(["--root", str(tmp_path), "backtest", "--config", str(path)]) == 2
    assert captured["data_kind"] == "historical_assumptions"
    assert captured["backtests"] == []
    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "incomplete_data"
    assert output["data_kind"] == "historical_assumptions"


def test_preflight_does_not_require_a_historical_rule_file_for_research(tmp_path):
    from crypto_carry.config import Config
    from crypto_carry.preflight import _rules_check

    result = _rules_check(research(Config()), tmp_path)
    assert result["ready"] is True
    assert result["analysis_mode"] == "prescribed_research"


def test_demo_rejects_research_config_before_running_engine(tmp_path, monkeypatch, capsys):
    from crypto_carry import cli
    from crypto_carry.config import Config

    path = tmp_path / "research.toml"
    path.write_text(research(Config()).to_toml(), encoding="utf-8")

    def forbidden(*args, **kwargs):
        raise AssertionError("engine must not run for an invalid command/config pair")

    monkeypatch.setattr(cli, "Backtest", forbidden)
    assert main(["--root", str(tmp_path), "demo", "--config", str(path)]) == 1
    assert "backtest" in capsys.readouterr().err
