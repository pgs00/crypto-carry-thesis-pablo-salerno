import hashlib
import importlib
import zipfile

import pytest


def _archives(tmp_path, trades=None, klines=None):
    paths = [tmp_path / "trades.zip", tmp_path / "klines.zip"]
    contents = [
        trades
        if trades is not None
        else (
            "id,price,qty,quote_qty,time,is_buyer_maker\n"
            "10,100,2,200,1000,false\n"
            "12,101,3,0.303,2000,true\n"
            "13,102,1,102,61000,false\n"
        ),
        klines
        if klines is not None
        else (
            "0,100,101,100,101,5,59999,503,2,2,200,0\n"
            "60000,102,102,102,102,1,119999,102,1,1,102,0\n"
        ),
    ]
    for path, content in zip(paths, contents):
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("data.csv", content)
    return paths


def _reconcile(*paths):
    return importlib.import_module("crypto_carry.data.reconcile").reconcile_futures_archives(*paths)


def test_reconciliation_distinguishes_id_gaps_from_corrupt_quote_field(tmp_path):
    paths = _archives(tmp_path)
    before = [path.read_bytes() for path in paths]
    result = _reconcile(*paths)
    assert result["market_values_match"] is True
    assert result["historical_certified"] is False
    assert result["trade_count"] == 3
    assert result["id_gap_count"] == 1
    assert result["absent_id_count"] == 1
    assert result["quote_field_mismatch_count"] == 1
    assert result["quote_field_examples"][0]["computed_quote"] == "303"
    assert result["quote_field_examples"][0]["reported_quote"] == "0.303"
    assert result["inputs"][0]["sha256"] == hashlib.sha256(before[0]).hexdigest()
    assert [path.read_bytes() for path in paths] == before


@pytest.mark.parametrize(
    "trades",
    [
        "10,100,2,200,1000,false\n13,102,1,102,61000,false\n",
        "10,100,2,200,1000,false\n12,101,3,303,2000,true\n",
        "10,99,2,198,1000,false\n12,101,3,303,2000,true\n13,102,1,102,61000,false\n",
    ],
)
def test_missing_or_wrong_trades_do_not_reconcile(tmp_path, trades):
    result = _reconcile(*_archives(tmp_path, trades=trades))
    assert result["market_values_match"] is False
    assert result["mismatching_minutes"] >= 1


@pytest.mark.parametrize(
    "trades",
    [
        "10,100,2,200,1000,false\n10,100,2,200,1000,false\n",
        "10,100,2,200,2000,false\n11,100,2,200,1000,false\n",
        "10,NaN,2,200,1000,false\n",
        "10,100,-2,-200,1000,false\n",
    ],
)
def test_invalid_trade_order_or_values_are_rejected(tmp_path, trades):
    with pytest.raises(ValueError):
        _reconcile(*_archives(tmp_path, trades=trades))


def test_missing_kline_minute_cannot_look_like_complete_comparison(tmp_path):
    paths = _archives(
        tmp_path,
        klines=(
            "0,100,101,100,101,5,59999,503,2,2,200,0\n120000,102,102,102,102,0,179999,0,0,0,0,0\n"
        ),
    )
    result = _reconcile(*paths)
    assert result["market_values_match"] is False
    assert result["missing_kline_minutes"] == 1


@pytest.mark.parametrize(
    "trades",
    [
        "id,qty,price,quote_qty,time,is_buyer_maker\n10,100,2,200,1000,false\n",
        "10,100,2,200,1000,false,unexpected\n",
    ],
)
def test_incompatible_trade_schema_is_rejected(tmp_path, trades):
    with pytest.raises(ValueError):
        _reconcile(*_archives(tmp_path, trades=trades))


def test_incompatible_kline_header_is_rejected(tmp_path):
    paths = _archives(
        tmp_path,
        klines=(
            "open_time,high,open,low,close,volume,close_time,quote_volume,count,taker_buy_volume,taker_buy_quote_volume,ignore\n"
            "0,100,101,100,101,5,59999,503,2,2,200,0\n"
        ),
    )
    with pytest.raises(ValueError):
        _reconcile(*paths)


def test_source_changed_after_fingerprinting_cannot_reconcile(tmp_path, monkeypatch):
    module = importlib.import_module("crypto_carry.data.reconcile")
    paths = _archives(tmp_path)
    replacement = tmp_path / "replacement.zip"
    with zipfile.ZipFile(replacement, "w") as archive:
        archive.writestr(
            "data.csv",
            "10,100,2,200,1000,false\n12,101,3,303,2000,true\n13,102,1,102,61000,false\n",
        )
    identity = module._identity
    replaced = False

    def replace_after_first_hash(path):
        nonlocal replaced
        result = identity(path)
        if path == paths[0] and not replaced:
            replaced = True
            path.write_bytes(replacement.read_bytes())
        return result

    monkeypatch.setattr(module, "_identity", replace_after_first_hash)
    with pytest.raises(ValueError, match="changed"):
        module.reconcile_futures_archives(*paths)


def test_extreme_decimal_precision_cannot_silently_hide_volume(tmp_path):
    paths = _archives(
        tmp_path,
        trades="10,1,1,1,1000,false\n11,1,1e-60,1e-60,2000,false\n",
        klines="0,1,1,1,1,1,59999,1,2,1,1,0\n",
    )
    with pytest.raises(ArithmeticError):
        _reconcile(*paths)
