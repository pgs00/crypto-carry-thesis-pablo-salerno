from copy import deepcopy
from decimal import Decimal as D
from pathlib import Path

import pytest

from crypto_carry.config import Config, timestamp
from crypto_carry.data.prescribed import prescribed_rules
from crypto_carry.ledger import Ledger
from crypto_carry.models import Fill


def fixture():
    config = Config.load(Path(__file__).resolve().parents[2]/"configs/entrega_4/reglas_historicas/BASE_E3.toml").changed(cost_multiplier=D(2))
    ledger = Ledger(config, "conditional")
    now = timestamp(config.start)
    rule = prescribed_rules(config).get("BTCUSDT", "spot", now)
    fill = Fill(fill_id="a", order_id="order-a", symbol="BTCUSDT", market="spot", side="buy",
                quantity=D(1), price=D(1000), time_ns=now, fee_rate=D(".002"),
                reference_price=D(1000), trade_id="trade-a")
    assert ledger.apply_fill(fill, rule, D(1000))
    return config, deepcopy(ledger.rows)


def test_ledger_audit_reconciles_base_fee_and_gross_cash():
    from scripts.cost_capacity_ledger import audit_ledger

    config, ledger = fixture()
    result = audit_ledger(config, ledger, [], [])
    assert result["final_free_spot"] == D(9000)
    assert result["final_inventory"]["BTCUSDT"]["spot"] == D(".998")
    assert "asset_cash" not in result["final_inventory"]["BTCUSDT"]


@pytest.mark.parametrize("field", ["cash_spot_change", "free_spot", "spot", "collateral", "debt", "fee"])
def test_ledger_audit_rejects_mutation(field):
    from scripts.cost_capacity_ledger import audit_ledger

    config, ledger = fixture()
    ledger[0][field] = D(123456789)
    with pytest.raises(ValueError):
        audit_ledger(config, ledger, [], [])


def test_intermediate_pre_fill_snapshot_allowed_but_effective_final_state_must_match():
    from scripts.cost_capacity_ledger import audit_ledger

    config, ledger = fixture()
    initial=dict(symbol="BTCUSDT",time_ns=ledger[0]["time_ns"],spot=D(0),short=D(0),average=D(0),collateral=D(0))
    final=dict(initial,spot=D(".998"))
    audit_ledger(config,ledger,[],[initial,final])
    with pytest.raises(ValueError,match="Effective final position"):
        audit_ledger(config,ledger,[],[initial,initial])
