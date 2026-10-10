import gzip
import hashlib
import json

import pytest

from scripts.return_capital.common import read_csv
from scripts.verify_cost_capacity import same_rows


def test_forecast_evidence_compression_preserves_original_bytes_and_rows(tmp_path):
    from scripts.cost_capacity_sources import forecast_bytes, forecast_rows

    original = b'symbol,forecast,reason\r\nBTCUSDT,0.0034,"quoted, reason"\r\n'
    path = tmp_path/"forecast_evaluation.csv"
    path.write_bytes(original)
    expected_rows = read_csv(path)
    expected_sha = hashlib.sha256(original).hexdigest()
    assert forecast_bytes(tmp_path) == original
    path.unlink()
    (tmp_path/"forecast_evaluation.csv.gz").write_bytes(gzip.compress(original, mtime=0))
    assert hashlib.sha256(forecast_bytes(tmp_path)).hexdigest() == expected_sha
    assert forecast_rows(tmp_path) == expected_rows


def test_forecast_evidence_rejects_ambiguous_plain_and_compressed_files(tmp_path):
    from scripts.cost_capacity_sources import forecast_bytes

    (tmp_path/"forecast_evaluation.csv").write_bytes(b"valid original")
    (tmp_path/"forecast_evaluation.csv.gz").write_bytes(gzip.compress(b"different content", mtime=0))
    with pytest.raises(ValueError, match="Ambiguous forecast"):
        forecast_bytes(tmp_path)


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


def test_missing_margin_has_no_evaluable_change_or_false_flat_label():
    from pathlib import Path

    from crypto_carry.config import Config, timestamp
    from scripts.cost_capacity_docs import margin_tier_label
    from scripts.cost_capacity_report import margin_observations, summarize_margin

    config = Config.load(Path(__file__).resolve().parents[2]/"configs/entrega_4/reglas_historicas/BASE_E3.toml")
    rows = margin_observations([dict(symbol="BTCUSDT", time_ns=timestamp(config.start),
                                    short="1", mark_price=None)], config)
    result = next(r for r in summarize_margin(rows, config)
                  if r["period"] == "full" and r["symbol"] == "BTCUSDT")
    assert rows[0]["observed_tier_change"] is None
    assert result["evaluable_transitions"] == 0
    assert result["observed_tier_changes"] is None
    assert result["active_snapshots"] == 1
    assert margin_tier_label(result) == "ND: corto activo sin tramo evaluable"
    flat = dict(result, active_snapshots=0)
    assert margin_tier_label(flat) == "sin corto observado"


def test_daily_margin_uses_saved_quantity_mark_and_resets_missing_flat_or_gap():
    from decimal import Decimal as D
    from pathlib import Path

    from crypto_carry.config import DAY, Config, timestamp
    from scripts.cost_capacity_report import daily_margin_observations, summarize_margin

    config = Config.load(Path(__file__).resolve().parents[2]/"configs/entrega_4/reglas_historicas/BASE_E3.toml")
    start = timestamp(config.start)+DAY-1
    fixtures = [(0, "1", "40000"), (1, "1", "50000"), (2, "1", "60000"),
                (3, "0", ""), (4, "1", "60000"), (5, "1", ""),
                (6, "1", "40000"), (8, "1", "40000")]
    raw = [dict(time_ns=start+day*DAY, BTCUSDT_short=q, BTCUSDT_mark=mark,
                ETHUSDT_short="0", ETHUSDT_mark="") for day, q, mark in fixtures]
    rows = daily_margin_observations(raw, config)
    assert [r["tier_floor"] for r in rows] == [D(0), D(0), D(50000), D(50000), None, D(0), D(0)]
    assert [r["observed_tier_change"] for r in rows] == [None, False, True, None, None, None, None]
    assert rows[2]["short_notional"] == D(60000)
    assert rows[2]["maintenance_usdt"] == D(300)
    assert rows[2]["frequency"] == "persisted daily closes; not full intraday series"
    result = next(r for r in summarize_margin(rows, config)
                  if r["period"] == "full" and r["symbol"] == "BTCUSDT")
    assert result["active_snapshots"] == 7
    assert result["non_evaluable"] == 1
    assert result["evaluable_transitions"] == 2
    assert result["observed_tier_changes"] == 1
    assert result["max_observed_notional"] == D(60000)
