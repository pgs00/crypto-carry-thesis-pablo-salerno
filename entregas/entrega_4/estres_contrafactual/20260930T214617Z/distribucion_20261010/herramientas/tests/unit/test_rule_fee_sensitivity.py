"""Independent numerical expectations for realized versus decision tariffs."""

from dataclasses import replace
from decimal import Decimal as D
from pathlib import Path

import pytest

from crypto_carry.config import Config, timestamp
from crypto_carry.costs import cycle_cost, realized_taker_fee
from crypto_carry.data.prescribed import prescribed_rules
from crypto_carry.margin import maintenance

ROOT = Path(__file__).resolve().parents[2]


def configured(name):
    return Config.load(ROOT / "configs/entrega_4/reglas_historicas" / f"{name}.toml")


@pytest.mark.parametrize(
    "name,symbol,at,actual_spot,actual_future,decision",
    [
        ("BASE_E3", "BTCUSDT", "2022-08-01T00:00:00Z", ".001", ".0005", ".0034"),
        ("BTC_PROMO_REALIZADA", "BTCUSDT", "2022-08-01T00:00:00Z", "0", ".0005", ".0034"),
        ("BTC_PROMO_DECISION", "BTCUSDT", "2022-08-01T00:00:00Z", "0", ".0005", ".0014"),
        ("BTC_PROMO_DECISION", "ETHUSDT", "2022-08-01T00:00:00Z", ".001", ".0005", ".0034"),
        ("BTC_PROMO_DECISION", "BTCUSDT", "2022-07-08T13:59:59Z", ".001", ".0005", ".0034"),
        ("BTC_PROMO_DECISION", "BTCUSDT", "2022-07-08T14:00:00Z", "0", ".0005", ".0014"),
        ("BTC_PROMO_DECISION", "BTCUSDT", "2023-03-21T23:59:59Z", "0", ".0005", ".0014"),
        ("BTC_PROMO_DECISION", "BTCUSDT", "2023-03-22T00:00:00Z", ".001", ".0005", ".0034"),
        ("FUT4_REALIZADA", "BTCUSDT", "2022-08-01T00:00:00Z", ".001", ".0004", ".0034"),
        ("FUT4_DECISION", "ETHUSDT", "2022-08-01T00:00:00Z", ".001", ".0004", ".0032"),
        ("MARGEN_2X", "BTCUSDT", "2022-08-01T00:00:00Z", ".001", ".0005", ".0034"),
    ],
)
def test_realized_tariffs_and_entry_cost_are_separate(
    name, symbol, at, actual_spot, actual_future, decision
):
    config = configured(name)
    book = prescribed_rules(config)
    now = timestamp(at)
    spot, future = (book.get(symbol, market, now) for market in ("spot", "futures"))
    assert spot.taker_fee == D(actual_spot)
    assert future.taker_fee == D(actual_future)
    assert realized_taker_fee(spot, config, now) == D(actual_spot)
    assert realized_taker_fee(future, config, now) == D(actual_future)
    assert cycle_cost(spot, future, config) == D(decision)


def test_zero_fees_and_bps_do_not_fall_back_to_default(rules, start):
    config = Config(slippage=D(".0001"))
    spot = replace(rules.get("BTCUSDT", "spot", start), taker_fee=D(0))
    future = replace(rules.get("BTCUSDT", "futures", start), taker_fee=D(0))
    assert cycle_cost(spot, future, config) == D(".0004")  # Four one-bp fills.
    assert realized_taker_fee(spot, config, start) == 0


def test_schedule_and_decision_modes_are_opt_in_and_strict_mode_stays_strict():
    legacy = configured("BASE_E3")
    assert "research_spot_fee_schedule" not in legacy.to_dict()
    assert "research_decision_fee_mode" not in legacy.to_dict()
    assert legacy.to_toml() == (
        ROOT / "configs/entrega_4/reglas_historicas/BASE_E3.toml"
    ).read_text(encoding="utf-8")
    with pytest.raises(ValueError):
        Config(research_spot_fee_schedule="btc_promo_2022_2023")
    with pytest.raises(ValueError):
        Config(research_decision_fee_mode="base_e3")
    with pytest.raises(ValueError):
        legacy.changed(research_spot_fee_schedule="interpolate_history")
    with pytest.raises(ValueError):
        legacy.changed(research_decision_fee_mode="future_exit_tariff")


@pytest.mark.parametrize("symbol,notional,base_mm,stress_mm", [
    ("BTCUSDT", "49999", "199.996", "399.992"),
    ("BTCUSDT", "50000", "200", "400"),
    ("BTCUSDT", "50001", "200.01", "400.02"),
    ("ETHUSDT", "50000", "325", "650"),
    ("ETHUSDT", "50001", "325.01", "650.02"),
])
def test_maintenance_stress_doubles_deduction_and_rate_at_tier_boundaries(
    symbol, notional, base_mm, stress_mm
):
    now = timestamp("2024-01-01T00:00:00Z")
    base, stress = configured("BASE_E3"), configured("MARGEN_2X")
    assert base.leverage == stress.leverage == D(2)
    assert maintenance(D(1), D(notional), prescribed_rules(base).get(symbol, "futures", now)) == D(base_mm)
    assert maintenance(D(1), D(notional), prescribed_rules(stress).get(symbol, "futures", now)) == D(stress_mm)


def test_separate_output_destination_preserves_original_manifest_bytes(tmp_path):
    from crypto_carry.reporting import verify_run, write_run

    source_root = tmp_path / "market_data_root"
    destination = tmp_path / "new_delivery"
    config = configured("BASE_E3").changed(data_dir="data")
    manifests = source_root / "data/manifests"
    manifests.mkdir(parents=True)
    content = b'{"provenance":"read from data root, not output root"}\r\n'
    (manifests / "processed.json").write_bytes(content)
    quality = {"status": "incomplete_data", "issues": ["test fixture only"], "coverage": []}
    run = write_run(source_root, config, [], quality, "historical_assumptions", output_root=destination)
    assert run.parent == destination
    assert (run / "source_manifests/processed.json").read_bytes() == content
    assert (manifests / "processed.json").read_bytes() == content
    assert not (source_root / "outputs").exists()
    assert verify_run(run)["valid"]
