"""Minute execution reports disclose the model limits without changing tick runs."""

import json
from pathlib import Path

from crypto_carry.config import Config
from crypto_carry.data.prescribed import research_assumptions
from crypto_carry.robustness import scenario_configs


def _minute_config(**changes):
    values = {
        "analysis_mode": "prescribed_research",
        "fee_profile": "prescribed_fixed_no_discounts",
        "execution_model": "minute_open",
        "order_timeout_seconds": 120,
        "leg_delay_seconds": 1,
    }
    values.update(changes)
    return Config(**values)


def test_minute_robustness_omits_incompatible_execution_scenarios():
    minute = scenario_configs(_minute_config())

    assert not [scenario for scenario in minute if scenario.dimension == "execution"]
    assert all(scenario.config.execution_model == "minute_open" for scenario in minute)
    assert {scenario.value for scenario in minute if scenario.dimension == "cost"} == {
        "1",
        "2",
        "3",
    }
    assert {
        "funding-proxy-plus-10",
        "funding-proxy-minus-10",
        "futures-fee-0p0004",
        "maintenance-2",
        "liquidation-fee-0p03",
    } <= {scenario.name for scenario in minute}

    tick = scenario_configs(Config())
    assert len(tick) == 30
    assert {scenario.value for scenario in tick if scenario.dimension == "execution"} == {
        "first_trade",
        "vwap",
    }


def test_actual_minute_profiles_only_generate_forward_start_scenarios():
    root = Path(__file__).resolve().parents[2]
    expected = {
        "download_minutes_2022_2023_d.toml": {"2023-01-01T00:00:00Z"},
        "download_minutes_2025_2026_d.toml": set(),
    }

    for name, expected_starts in expected.items():
        base = Config.load(root / "configs" / name)
        scenarios = scenario_configs(base)
        start_scenarios = [scenario for scenario in scenarios if scenario.dimension == "start"]

        assert {scenario.value for scenario in start_scenarios} == expected_starts
        assert all(base.start <= scenario.config.start < base.end for scenario in start_scenarios)


def test_minute_research_assumptions_disclose_bar_execution_limits():
    declaration = research_assumptions(_minute_config())

    assert declaration["execution_model"] == "minute_open"
    minute = declaration["methodology"]["minute_execution"]
    assert minute["source_price"] == "one-minute bar open assigned to the opening boundary"
    assert minute["first_trade_time_known"] is False
    assert minute["fill_reference_id"] == "bar:<symbol>:<market>:<open_ns>"
    assert minute["fill_reference_is_trade_id"] is False
    assert minute["order_timeout_seconds"] == 120
    assert minute["configured_leg_delay_seconds"] == 1
    assert "strictly later available minute open" in minute["actual_leg_delay"]
    assert minute["participation_volume"] == (
        "prior closed one-minute volume; approximation of rolling 60 seconds"
    )
    assert minute["volume_available_before_bar_close"] is False
    assert minute["liquidation_intrabar_path_modeled"] is False
    assert minute["risk_mark"] == "last available closed one-minute mark"

    tick = research_assumptions(_minute_config(execution_model="first_trade"))
    assert "execution_model" not in tick
    assert "minute_execution" not in tick["methodology"]


def test_next_minute_vwap_assumptions_disclose_closed_window_and_capacity():
    declaration = research_assumptions(
        _minute_config(execution_model="next_minute_vwap", signal_price_model="closed_minute")
    )

    assert declaration["execution_model"] == "next_minute_vwap"
    minute = declaration["methodology"]["minute_execution"]
    assert minute["source_price"] == "quote-volume divided by base-volume for the eligible minute"
    assert minute["eligible_window"] == "the first full minute beginning at or after submission"
    assert minute["fill_time"] == "eligible minute close, after price and volume are known"
    assert minute["volume_cap"] == "1% of observed eligible-minute base volume"
    assert minute["remainder"] == "unfilled quantity expires at the eligible minute close"


def test_next_minute_vwap_manifest_labels_execution_truthfully(tmp_path):
    from crypto_carry.reporting import write_run

    config = _minute_config(execution_model="next_minute_vwap", signal_price_model="closed_minute")
    run = write_run(
        tmp_path,
        config,
        [],
        {"status": "incomplete_data", "issues": [], "coverage": [], "funding_mark_audit": []},
        "historical_assumptions",
    )
    conventions = json.loads((run / "run_manifest.json").read_text(encoding="utf-8"))["conventions"]
    assert "quote volume divided by base volume" in conventions["execution"]
    assert "first full minute" in conventions["execution"]
    assert conventions["fill_time"] == "eligible minute close, after price and volume are known"
    assert conventions["capacity"] == "1% of eligible-minute base volume; remainder expires"


def test_minute_run_manifest_and_report_label_execution_truthfully(tmp_path):
    from crypto_carry.reporting import write_run

    config = _minute_config()
    run = write_run(
        tmp_path,
        config,
        [],
        {
            "status": "incomplete_data",
            "issues": ["fixture has no market rows"],
            "coverage": [],
            "funding_mark_audit": [],
        },
        "historical_assumptions",
    )

    manifest = json.loads((run / "run_manifest.json").read_text(encoding="utf-8"))
    conventions = manifest["conventions"]
    assert "one-minute bar open" in conventions["execution"]
    assert "opening boundary" in conventions["execution"]
    assert conventions["fill_reference_ids"] == (
        "bar:<symbol>:<market>:<open_ns>; source-bar references, not individual trade IDs"
    )
    assert conventions["order_timeout"] == "120 seconds from submission"
    assert "configured delay 1 second" in conventions["leg_delay"]
    assert "strictly later available minute open" in conventions["leg_delay"]
    assert "prior closed one-minute volume" in conventions["participation"]
    assert "approximation of rolling 60 seconds" in conventions["participation"]
    assert conventions["liquidation_path"] == (
        "no intrabar high/low path; risk uses the last available closed one-minute mark"
    )

    report = (run / "report.md").read_text(encoding="utf-8")
    for disclosure in (
        "open de la barra de un minuto",
        "bar:<symbol>:<market>:<open_ns>",
        "timeout de la orden es de 120 segundos",
        "demora configurada entre patas es de 1 segundo",
        "open de minuto disponible estrictamente posterior",
        "volumen del minuto cerrado anterior",
        "aproximación del volumen móvil de 60 segundos",
        "no modelan una trayectoria intraminuto de máximos y mínimos",
        "no son IDs de operaciones individuales",
    ):
        assert disclosure in report
    assert "Minute execution convention" not in report
    assert "For minute execution" not in report
    assert "Minute liquidation" not in report


def test_minute_report_treats_each_evaluation_window_as_an_independent_run(tmp_path):
    from crypto_carry.reporting import write_run

    config = _minute_config(
        start="2022-09-01T00:00:00Z",
        end="2023-09-01T00:00:00Z",
    )
    quality = {
        "status": "incomplete_data",
        "issues": ["fixture has no market rows"],
        "coverage": [],
        "funding_mark_audit": [],
    }
    run = write_run(tmp_path / "minute", config, [], quality, "historical_assumptions")
    report = (run / "report.md").read_text(encoding="utf-8")

    assert (
        "una sola ventana de evaluación independiente "
        "[2022-09-01T00:00:00Z, 2023-09-01T00:00:00Z)" in report
    )
    assert "El capital se reinicia en 10000 USDT por estrategia" in report
    assert "no hay una trayectoria continua de cartera durante los años excluidos" in report
    assert "no compara por sí mismo ventanas por minuto reiniciadas independientemente" in report
    assert "clasificación anterior/posterior a 2024 es descriptiva dentro de esta corrida" in report
    assert "positions are not reset between regimes" not in report
    assert "Alcance de la ventana de evaluación por minuto" in report
    assert "Minute evaluation window scope" not in report
    assert "For minute evaluation windows" not in report
    assert "corrida anual" not in report

    tick_config = Config(start="2022-09-01T00:00:00Z", end="2023-09-01T00:00:00Z")
    tick = write_run(
        tmp_path / "tick",
        tick_config,
        [],
        {"status": "incomplete_data", "issues": [], "coverage": []},
        "historical",
    )
    tick_report = (tick / "report.md").read_text(encoding="utf-8")
    assert "No hay reinicio de posiciones al cambiar de régimen" in tick_report


def test_documented_closure_is_disclosed_as_ex_post_coverage_evidence(tmp_path):
    from crypto_carry.config import timestamp
    from crypto_carry.data.market_calendar import BINANCE_SPOT_HALT_SOURCE, quality_closures
    from crypto_carry.reporting import write_run

    config = _minute_config(
        start="2023-03-01T00:00:00Z",
        end="2023-04-01T00:00:00Z",
    )
    quality = {
        "status": "incomplete_data",
        "issues": [],
        "coverage": [],
        "funding_mark_audit": [],
        "documented_closures": quality_closures(
            config.symbols, timestamp(config.start), timestamp(config.end)
        ),
    }
    run = write_run(tmp_path, config, [], quality, "historical_assumptions")

    for name in ("report.md", "data_quality_report.md"):
        text = (run / name).read_text(encoding="utf-8")
        assert "Cierres documentados de mercado" in text
        assert "evidencia ex post de cobertura" in text
        assert "No se clasifican como datos faltantes" in text
        assert "no generan barras sintéticas" in text
        assert "no se entregaron anticipadamente a la estrategia" in text
        assert "BTCUSDT, ETHUSDT" in text
        assert "2023-03-24T11:28:00" in text
        assert BINANCE_SPOT_HALT_SOURCE in text
