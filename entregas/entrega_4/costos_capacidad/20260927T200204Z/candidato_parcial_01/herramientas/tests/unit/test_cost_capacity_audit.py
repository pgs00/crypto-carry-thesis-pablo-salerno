from decimal import Decimal as D
from pathlib import Path

import pytest

from crypto_carry.config import SECOND, Config, timestamp


def fixture():
    config = Config.load(Path(__file__).resolve().parents[2] /
                         "configs/entrega_4/reglas_historicas/BASE_E3.toml").changed(
                             max_volume_participation=D(".005"))
    start = timestamp(config.start)
    orders, fills, ledger = [], [], []
    for name, requested, executed in [("a", ".3", ".3"), ("b", ".4", ".2")]:
        orders.append(dict(order_id=name, symbol="BTCUSDT", market="spot", side="BUY",
                           quantity=requested, filled_quantity=executed,
                           remaining_quantity=str(D(requested)-D(executed)),
                           status="filled" if requested == executed else "expired",
                           submitted_at=start, window_start=start, window_end=start+60*SECOND,
                           time_ns=start+60*SECOND, record_type="final", purpose="open_spot"))
        fills.append(dict(order_id=name, fill_id=name, symbol="BTCUSDT", market="spot", side="BUY",
                          quantity=executed, price="100.01", reference_price="100", fee_rate=".001",
                          slippage_rate=".0001", liquidation=False, time_ns=start+60*SECOND,
                          window_start=start, window_end=start+60*SECOND, window_base_volume="100",
                          window_quote_volume="10000"))
        ledger.append(dict(event_id="fill:"+name, symbol="BTCUSDT", kind="spot_buy",
                           quantity=executed, price="100.01", fee=str(D(executed)*D("100.01")*D(".001")),
                           base_fee_quantity=str(D(executed)*D(".001")), liquidation_fee=None))
    windows = [dict(symbol="BTCUSDT", market="spot", open_time=start,
                    end_time=start+60*SECOND, base_volume="100", quote_volume="10000", present=True)]
    return config, orders, fills, ledger, windows


def test_audit_shared_gross_capacity_and_terminal_order_population():
    from scripts.cost_capacity_audit import audit_execution

    data = fixture()
    result = audit_execution(*data)
    assert len(result["ordenes"]) == 2
    assert len(result["capacidad"]) == 1
    assert result["capacidad"][0]["executed_gross_quantity"] == D(".5")
    assert result["capacidad"][0]["capacity_utilization"] == 1
    assert result["ordenes"][1]["shortfall_cause"] == "capacity"
    assert result["ordenes"][1]["gross_executed_quantity"] == D(".2")
    assert result["ordenes"][1]["net_spot_received"] == D(".1998")


@pytest.mark.parametrize("target,field,value", [
    (2, "quantity", ".4"), (2, "fee_rate", ".002"), (2, "price", "100.02"),
    (4, "base_volume", "50"), (3, "fee", "123"),
])
def test_audit_detects_semantic_corruption(target, field, value):
    from scripts.cost_capacity_audit import audit_execution

    data = fixture()
    data[target][0][field] = value
    with pytest.raises(ValueError):
        audit_execution(*data)


def test_unhedged_episodes_are_coalesced_before_top_five():
    from scripts.cost_capacity_audit import exposure_episodes

    rows = [dict(symbol="BTCUSDT", start_ns=i*60*SECOND, end_ns=(i+1)*60*SECOND,
                 exposure="unhedged" if i<2 else "dust", spot=D(1), short=D(0),
                 state="CLOSING_SPOT") for i in range(3)]
    episodes = exposure_episodes(rows)
    assert len(episodes) == 1
    assert episodes[0]["seconds"] == 120


def test_final_snapshot_can_omit_computed_remainder_but_event_must_reconcile():
    from scripts.cost_capacity_audit import audit_execution

    data = fixture()
    event = dict(data[1][1], record_type="event", action="timeout")
    data[1][1]["remaining_quantity"] = None
    data[1].insert(1, event)
    assert audit_execution(*data)["ordenes"][1]["unfilled_quantity"] == D(".2")
    event["remaining_quantity"] = "0.3"
    with pytest.raises(ValueError, match="remainder"):
        audit_execution(*data)
