import pytest

from scripts.stress_counterfactual_audit import audit_funding_amounts


def test_funding_uses_quantity_before_simultaneous_closing_fill():
    ledger = [dict(symbol="BTCUSDT", time_ns=10, kind="futures_sell", short="2"),
              dict(symbol="BTCUSDT", time_ns=20, kind="funding", short="2", amount_usdt=".22"),
              dict(symbol="BTCUSDT", time_ns=20, kind="futures_buy", short="0")]
    source = [dict(symbol="BTCUSDT", funding_time=20, economic_window=True,
                   settlement_mark_price="110", funding_rate=".001")]
    assert audit_funding_amounts(ledger, source)[0]["amount_usdt"] == ".22"
    ledger[1]["amount_usdt"] = ".11"
    with pytest.raises(ValueError, match="pre-fill"):
        audit_funding_amounts(ledger, source)


def test_missing_funding_payment_on_open_short_is_rejected():
    ledger = [dict(symbol="BTCUSDT", time_ns=10, kind="futures_sell", short="2")]
    source = [dict(symbol="BTCUSDT", funding_time=20, economic_window=True,
                   settlement_mark_price="110", funding_rate=".001")]
    with pytest.raises(ValueError, match="missing"):
        audit_funding_amounts(ledger, source)
