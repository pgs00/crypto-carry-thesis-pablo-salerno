"""Native replays catch causal, suspension, accounting and restart failures."""

from dataclasses import replace
from decimal import Decimal as D

import pytest
from conftest import warmup
from test_next_minute_vwap import bars, config

from crypto_carry.config import SECOND, timestamp
from crypto_carry.events import event_key
from crypto_carry.models import Funding, Mark, MinuteBar
from crypto_carry.strategy import Backtest
from crypto_carry.stress_counterfactual import ScenarioBacktest

M = 60 * SECOND


def market(start, seconds=4800):
    return sorted(warmup(start) + bars(start, range(0, seconds + 1, 60)), key=event_key)


def shock(start, magnitude=".12"):
    return dict(id="fixture", kind="shock", magnitudes={"BTCUSDT": D(magnitude)},
                episodes=[("BTCUSDT", start + 120 * SECOND, start + 180 * SECOND)])


@pytest.mark.parametrize("spec", [None, {"id": "OFF", "kind": "off"}, "zero"])
def test_off_and_zero_match_every_ordered_economic_record(start, rules, spec):
    if spec == "zero":
        spec = shock(start, "0")
    cfg = config(start, seconds=4800, sizing_model="joint_quantity")
    raw = market(start)
    base = Backtest(cfg, rules).run(raw)
    candidate = ScenarioBacktest(cfg, rules, scenario=spec).run(raw)
    for name in ("fills", "order_rows", "daily", "signals", "renewal_diagnostics",
                 "positions", "risk_events", "opportunities", "all_funding"):
        assert getattr(candidate, name) == getattr(base, name), name
    assert candidate.ledger.rows == base.ledger.rows


def test_zero_shock_preserves_stale_price_decimal_bytes_during_recovery(rules):
    start, cf, raw = cf_fixture()
    spec = dict(id="zero_closure", kind="shock", magnitudes={"BTCUSDT": D(0)},
                episodes=[("BTCUSDT", cf["start"] + M, cf["start"] + 2 * M)])
    cfg = config(start, seconds=9600)
    stop = cf["start"] + 4 * M
    base = Backtest(cfg, rules).run(raw, stop_at=stop)
    zero = ScenarioBacktest(cfg, rules, scenario=spec).run(raw, stop_at=stop)
    assert zero.factor_at("BTCUSDT", stop) == 1
    assert str(zero.spot_prices()["BTCUSDT"]) == str(base.spot_prices()["BTCUSDT"])
    assert zero.trades["BTCUSDT", "spot"].source_file == base.trades["BTCUSDT", "spot"].source_file
    assert zero.trades["BTCUSDT", "spot"].available_at == base.trades["BTCUSDT", "spot"].available_at


def test_pulse_does_not_reprice_committed_fill_or_look_ahead_when_sizing(start, rules):
    cfg = config(start, seconds=600, sizing_model="joint_quantity")
    raw = market(start, 600)
    base = Backtest(cfg, rules).run(raw)
    variant = ScenarioBacktest(cfg, rules, scenario=shock(start)).run(raw)
    first_base = next(f for f in base.fills if f["symbol"] == "BTCUSDT")
    first_variant = next(f for f in variant.fills if f["symbol"] == "BTCUSDT")
    assert first_base == first_variant
    assert first_variant["time_ns"] == start + 120 * SECOND
    # Exclusive end 600: latest available candle opens at 480, recovery step 5.
    assert variant.closed_bars["BTCUSDT", "spot"].close == D("89")
    assert variant.closed_bars["ETHUSDT", "spot"].close == 100
    assert variant.ledger.reconcile(variant.spot_prices(), variant.mark_prices())["difference"] == 0


def cf_fixture():
    start = timestamp("2023-03-24T11:26:00Z")
    lower, upper = start + M, timestamp("2023-03-24T14:00:00Z")
    spec = dict(id="CF_fixture", kind="counterfactual", start=lower, end=upper,
                anchors={s: {"spot": D(101), "futures": D(100)}
                         for s in ("BTCUSDT", "ETHUSDT")},
                volumes={(s, u): (D(4), 7) for s in ("BTCUSDT", "ETHUSDT")
                         for u in range(lower, upper, M)})
    raw = []
    for r in market(start, 9600):
        if isinstance(r, MinuteBar):
            if r.market == "spot" and lower + M <= r.open_time < upper:
                continue
            price = D(101) if r.market == "spot" else D(100)
            r = replace(r, open=price, high=price, low=price, close=price,
                        quote_volume=r.base_volume * price)
        raw.append(r)
    return start, spec, raw


def test_counterfactual_negative_basis_restricts_entries_without_changing_anchor(rules):
    start, spec, raw = cf_fixture()
    result = ScenarioBacktest(config(start, seconds=9600), rules, scenario=spec).run(
        raw, stop_at=spec["end"])
    assert result.status == "complete"
    assert len(result.interventions) == 306
    assert not result.fills
    assert result._observed_basis("BTCUSDT") == D("-0.0099009900990099009900990099")
    assert result.closed_bars["BTCUSDT", "spot"].base_volume == 4
    assert result.closed_bars["BTCUSDT", "spot"].quote_volume == 404
    assert result.closed_bars["BTCUSDT", "spot"].available_at == spec["end"]
    assert all(not r["eligible"] for r in result.opportunities)
    witness = result.opportunity_observations[-1]
    assert witness["forecast"]["available_at"] <= witness["time_ns"]
    assert D(witness["spot_bar"]["close"]) == 101
    assert D(witness["future_bar"]["close"]) == 100
    assert witness["value"] == "0" and witness["eligible"] is False
    assert witness["position_independent"] is True


def test_reopening_prices_cannot_change_any_prior_decision_or_synthetic_bar(rules):
    start, spec, raw = cf_fixture()
    altered = [replace(r, open=D(50), high=D(50), low=D(50), close=D(50),
                       quote_volume=r.base_volume * 50)
               if isinstance(r, MinuteBar) and r.market == "spot" and r.open_time >= spec["end"]
               else r for r in raw]
    cfg = config(start, seconds=9600)
    a = ScenarioBacktest(cfg, rules, scenario=spec).run(raw, stop_at=spec["end"])
    b = ScenarioBacktest(cfg, rules, scenario=spec).run(altered, stop_at=spec["end"])
    for key in ("interventions", "fills", "signals", "order_rows", "opportunities"):
        assert getattr(a, key) == getattr(b, key)


def test_shock_revalues_stale_reference_without_refreshing_or_reopening_spot(rules):
    start, cf, raw = cf_fixture()
    spec = dict(id="closure_shock", kind="shock", magnitudes={"BTCUSDT": D(".12")},
                episodes=[("BTCUSDT", cf["start"] + M, cf["start"] + 2 * M)])
    result = ScenarioBacktest(config(start, seconds=9600), rules, scenario=spec).run(
        raw, stop_at=cf["start"] + 4 * M)
    assert result.status == "complete"
    assert not result._fresh("BTCUSDT")
    assert result.trades["BTCUSDT", "spot"].available_at == cf["start"] + M
    assert result.spot_prices()["BTCUSDT"] == D("89.082")
    assert not any(f["market"] == "spot" and f["window_start"] >= cf["start"] + M
                   for f in result.fills)
    assert result.scenario_observations[-1]["after"]["assets"]["BTCUSDT"][
        "spot_source_available_at"] == cf["start"] + M


def test_cf_missing_future_fails_even_inside_documented_spot_closure(rules):
    start, spec, raw = cf_fixture()
    raw = [r for r in raw if not (isinstance(r, MinuteBar) and r.market == "futures"
           and r.symbol == "BTCUSDT" and r.open_time == spec["start"] + 2 * M)]
    with pytest.raises(ValueError, match="future"):
        ScenarioBacktest(config(start, seconds=9600), rules, scenario=spec).run(raw)


def test_unknown_spot_gap_outside_cf_is_still_a_coverage_failure(rules):
    start, spec, raw = cf_fixture()
    raw = [r for r in raw if not (isinstance(r, MinuteBar) and r.market == "spot"
           and r.symbol == "BTCUSDT" and r.open_time == spec["end"] + M)]
    result = ScenarioBacktest(config(start, seconds=9600), rules, scenario=spec).run(raw)
    assert result.status == "incomplete_data"
    assert any("Missing price minute" in r for r in result.reasons)


def test_checkpoint_restores_pulse_state_recovery_pending_orders_and_ledger(start, rules, tmp_path):
    cfg = config(start, seconds=4800, sizing_model="joint_quantity")
    spec, raw = shock(start, ".002"), market(start)
    whole = ScenarioBacktest(cfg, rules, inputs={"scenario": "fixture"}, scenario=spec).run(raw)
    partial = ScenarioBacktest(cfg, rules, inputs={"scenario": "fixture"}, scenario=spec).run(
        raw, stop_at=start + 120 * SECOND)
    assert partial._pending("BTCUSDT")
    checkpoint = tmp_path / "pulse.json"
    partial.checkpoint(checkpoint)
    restored = ScenarioBacktest.load_checkpoint(checkpoint, cfg, rules,
                                                {"scenario": "fixture"}).run(raw)
    for key in ("fills", "order_rows", "daily", "opportunities", "interventions",
                "scenario_observations", "opportunity_observations"):
        assert getattr(restored, key) == getattr(whole, key), key
    assert restored.ledger.rows == whole.ledger.rows
    assert restored.ledger.positions == whole.ledger.positions
    assert restored.reservations == whole.reservations
    with pytest.raises(ValueError, match="input"):
        ScenarioBacktest.load_checkpoint(checkpoint, cfg, rules, {"scenario": "different"})


def test_recovery_returns_source_without_resetting_inventory_or_ledger(start, rules):
    cfg = config(start, seconds=4800)
    raw = market(start)
    result = ScenarioBacktest(cfg, rules, scenario=shock(start, ".002")).run(raw)
    assert result.closed_bars["BTCUSDT", "spot"].close == 100
    assert result.ledger.positions["BTCUSDT"].spot > 0
    assert result.ledger.positions["BTCUSDT"].short > 0
    assert all(r["kind"] in {"spot_buy", "futures_sell", "transfer"} for r in result.ledger.rows)
    recovery = [r for r in result.scenario_observations
                if r["time_ns"] == start + 240 * SECOND][0]
    assert recovery["before"]["assets"]["BTCUSDT"]["factor"] == D(".998")
    # Bar opening 180 is the first recovery minute and remains at full intensity.
    assert recovery["after"]["assets"]["BTCUSDT"]["factor"] == D(".998")
    assert result.reservations["BTCUSDT"] == 0


def test_cf_checkpoint_inside_synthetic_interval_preserves_anchor_and_reopening(rules, tmp_path):
    start, spec, raw = cf_fixture()
    cfg = config(start, seconds=9600)
    whole = ScenarioBacktest(cfg, rules, inputs={"cf": "approved"}, scenario=spec).run(raw)
    partial = ScenarioBacktest(cfg, rules, inputs={"cf": "approved"}, scenario=spec).run(
        raw, stop_at=spec["start"] + 17 * M)
    checkpoint = tmp_path / "cf.json"
    partial.checkpoint(checkpoint)
    restored = ScenarioBacktest.load_checkpoint(checkpoint, cfg, rules, {"cf": "approved"}).run(raw)
    assert restored.anchor_verified
    assert restored.interventions == whole.interventions
    assert restored.scenario_observations == whole.scenario_observations
    assert restored.opportunity_observations == whole.opportunity_observations
    assert restored.signals == whole.signals and restored.fills == whole.fills
    assert restored.ledger.rows == whole.ledger.rows


def test_layer_preserves_funding_before_partial_close_and_liquidation_retry(start, rules):
    class CloseAt240(ScenarioBacktest):
        def process(self, time_ns, records, native):
            super().process(time_ns, records, native)
            if time_ns == self.start + 240 * SECOND:
                self._close("BTCUSDT", "fixture_close")

    raw = []
    for r in market(start, 1800):
        if isinstance(r, Mark) and r.symbol == "BTCUSDT" and r.available_at >= start + 270 * SECOND:
            r = replace(r, open=D(200), high=D(200), low=D(200), close=D(200))
        if (isinstance(r, MinuteBar) and r.symbol == "BTCUSDT" and r.market == "futures"
                and r.end_time == start + 300 * SECOND):
            r = replace(r, base_volume=D(1000), quote_volume=D(100300))
        raw.append(r)
    t = start + 270 * SECOND
    raw.append(Mark("BTCUSDT", t - M, t - 1, t, D(200), D(200), D(200), D(200)))
    raw.append(Funding("BTCUSDT", start + 300 * SECOND, start + 360 * SECOND,
                       D(".001"), D(8), D(200), "synthetic", True))
    result = CloseAt240(config(start, seconds=1800, sizing_model="joint_quantity"), rules,
                        scenario=shock(start, ".002")).run(sorted(raw, key=event_key))
    retry = next(o for o in result.order_rows if o["symbol"] == "BTCUSDT"
                 and o["action"] == "submitted" and o["submitted_at"] == start + 300 * SECOND)
    assert retry["purpose"] == "liquidate"
    assert any(f["liquidation"] for f in result.fills if f["symbol"] == "BTCUSDT")
    assert any(r["time_ns"] == start + 300 * SECOND for r in result.ledger.funding_rows)
    assert result.ledger.positions["BTCUSDT"].short == 0
    assert result.scenario_observations[-1]["after"]["assets"]["BTCUSDT"]["margin"] is None
    final_close = next(r for r in result.scenario_observations
                       if r["time_ns"] == start + 360 * SECOND)
    assert final_close["before_fills"]["assets"]["BTCUSDT"]["short"] > 0
    assert final_close["before_fills"]["assets"]["BTCUSDT"]["mark"] == 200
    assert final_close["after_fills"]["assets"]["BTCUSDT"]["short"] == 0
    assert final_close["after_fills"]["assets"]["BTCUSDT"]["margin"] is None
    assert abs(result.ledger.reconcile(result.spot_prices(), result.mark_prices())["difference"]) <= D("1E-8")
