import json

from scripts.return_capital.common import read_csv
from scripts.verify_cost_capacity import same_rows


def test_block3_csv_lists_have_canonical_roundtrip(tmp_path):
    from decimal import Decimal
    from scripts.build_cost_capacity import write_table

    rows = [dict(episode="one", states=["OPENING", "CLOSING"], related=[],
                 balances={"BTCUSDT": {"spot": Decimal(".998")}})]
    write_table(tmp_path, "episodios", rows)
    saved = read_csv(tmp_path/"tablas/episodios.csv")
    assert saved[0]["states"] == json.dumps(rows[0]["states"], separators=(",", ":"))
    same_rows(saved, rows, "episodes")


def test_missing_margin_mark_is_nd_instead_of_zero():
    from decimal import Decimal
    from pathlib import Path

    from crypto_carry.config import Config, timestamp
    from scripts.cost_capacity_report import margin_observations

    config = Config.load(Path(__file__).resolve().parents[2]/"configs/entrega_4/reglas_historicas/BASE_E3.toml")
    result = margin_observations([dict(symbol="BTCUSDT", time_ns=timestamp(config.start),
                                      short=Decimal(1), mark_price=None)], config)[0]
    assert result["short_notional"] is None
    assert result["maintenance_usdt"] is None
    assert "missing mark" in result["reason"]
