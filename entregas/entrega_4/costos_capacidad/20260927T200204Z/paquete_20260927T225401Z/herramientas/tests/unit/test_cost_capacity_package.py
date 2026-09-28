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
