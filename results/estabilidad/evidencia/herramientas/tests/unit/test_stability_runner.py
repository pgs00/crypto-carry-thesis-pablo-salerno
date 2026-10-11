"""B6 closed matrix and true initial-state controls, without historical replays."""

import importlib.util
from decimal import Decimal as D
from pathlib import Path

import pytest
from conftest import warmup

from crypto_carry.config import HOUR, SECOND, Config, iso
from crypto_carry.events import event_key
from crypto_carry.mark_gap_study import GapAuditedBacktest
from crypto_carry.models import Funding, Mark, MinuteBar

ROOT = Path(__file__).resolve().parents[2]


def contract():
    assert importlib.util.find_spec("scripts.stability_uncertainty_contract"), "B6 missing"
    from scripts import stability_uncertainty_contract

    return stability_uncertainty_contract


def test_closed_matrix_changes_only_start_and_rejects_extra_variants():
    api = contract()
    base = Config.load(ROOT / "configs/entrega_4/reglas_historicas/BASE_E3.toml")
    configs = api.scenario_configs(base)
    assert list(configs) == ["I2023", "I2024"]
    for name, cfg in configs.items():
        assert set(api.validate_variant(base, name, cfg)) == {"start"}
        assert cfg.history_start == base.history_start
        assert cfg.window_hours + 24 == 360
        assert cfg.capital == D(10000)
        with pytest.raises(ValueError):
            api.validate_variant(base, name, cfg.changed(holding_hours=336))
    with pytest.raises(ValueError):
        api.validate_variant(base, "BASE", base)


def test_changed_input_is_detected_before_resume(tmp_path):
    api = contract()
    path = tmp_path / "input.bin"
    path.write_bytes(b"original")
    inventory = [api.file_record(path)]
    api.check_inventory(inventory)
    path.write_bytes(b"adulterated")
    with pytest.raises(ValueError, match="changed"):
        api.check_inventory(inventory)


def test_replay_reader_window_contract_uses_360_hours(monkeypatch, start):
    api = contract()
    cfg = Config.load(ROOT / "configs/entrega_4/reglas_historicas/BASE_E3.toml").changed(
        start=iso(start), end=iso(start + 600 * SECOND)
    )
    observed = {}

    def reader(root, begin, end, hours, **kwargs):
        observed.update(begin=begin, end=end, hours=hours, kwargs=kwargs)
        return iter(())

    class EmptyRun:
        def __init__(self, config, rules, strategy, enabled, inputs):
            observed.update(config=config, strategy=strategy, enabled=enabled)

        def run(self, rows):
            list(rows)

    monkeypatch.setattr(api, "iter_records", reader)
    monkeypatch.setattr(api, "GapAuditedBacktest", EmptyRun)
    api.simulate(cfg, Path("."), "conditional", {})
    assert observed["begin"] == start
    assert observed["end"] == start + 600 * SECOND
    assert observed["hours"] == 360
    assert observed["kwargs"]["include_closed_bars"] is True


@pytest.mark.parametrize("strategy", ["conditional", "permanent"])
def test_real_cash_restart_no_prewarm_operations_first_fill_and_exclusive_end(
    start, rules, strategy
):
    contract()
    base = Config.load(ROOT / "configs/entrega_4/reglas_historicas/BASE_E3.toml")
    cfg = base.changed(start=iso(start), end=iso(start + 600 * SECOND))
    bt = GapAuditedBacktest(cfg, rules, strategy, strategy == "conditional")
    assert bt.equity() == D(10000)
    assert all(p.spot == p.short == p.collateral == 0 for p in bt.ledger.positions.values())
    assert not bt.orders and not bt.reservations
    rows = warmup(start)
    # Real engine receives funding preload; normal entry waits for available information.
    for offset in range(-60, 661, 60):
        end = start + offset * SECOND
        for symbol in cfg.symbols:
            for market, price in [("spot", D(100)), ("futures", D("100.3"))]:
                rows.append(
                    MinuteBar(
                        symbol,
                        market,
                        end - 60 * SECOND,
                        end,
                        end,
                        price,
                        price,
                        price,
                        price,
                        D(100000),
                        D(100000) * price,
                        100,
                        "fixture",
                    )
                )
            rows.append(
                Mark(
                    symbol,
                    end - 60 * SECOND,
                    end - 1,
                    end,
                    D("100.3"),
                    D("100.3"),
                    D("100.3"),
                    D("100.3"),
                )
            )
    bt.run(sorted(rows, key=event_key))
    assert bt.now == start + 600 * SECOND - 1
    assert bt.fills and min(int(r["time_ns"]) for r in bt.fills) == start + 120 * SECOND
    assert all(start <= int(r["time_ns"]) < start + 600 * SECOND for r in bt.fills + bt.daily)
    assert min(int(r["time_ns"]) for r in bt.signals) >= start + 60 * SECOND
    assert (
        bt.history
        and min(f.funding_time for f in rows if isinstance(f, Funding)) >= start - 360 * HOUR
    )
    assert all(int(r["time_ns"]) >= start for r in bt.ledger.rows)
    assert abs(bt.ledger.reconcile(bt.spot_prices(), bt.mark_prices())["difference"]) <= D("1E-8")


def test_launch_budget_reserves_growth_and_never_exceeds_four():
    api = contract()
    assert (
        api.launch_capacity(
            available_gib=30,
            resident_gib=[],
            physical=8,
            cpu=20,
            disk_free_gib=100,
            paging_mbps=0,
            ramped=True,
        )
        == 4
    )
    assert (
        api.launch_capacity(
            available_gib=18,
            resident_gib=[],
            physical=8,
            cpu=20,
            disk_free_gib=100,
            paging_mbps=0,
            ramped=False,
        )
        == 2
    )
    assert (
        api.launch_capacity(
            available_gib=7,
            resident_gib=[1, 1],
            physical=8,
            cpu=20,
            disk_free_gib=100,
            paging_mbps=0,
            ramped=True,
        )
        == 2
    )
    assert (
        api.launch_capacity(
            available_gib=30,
            resident_gib=[1, 1],
            physical=8,
            cpu=95,
            disk_free_gib=100,
            paging_mbps=0,
            ramped=True,
        )
        == 2
    )
