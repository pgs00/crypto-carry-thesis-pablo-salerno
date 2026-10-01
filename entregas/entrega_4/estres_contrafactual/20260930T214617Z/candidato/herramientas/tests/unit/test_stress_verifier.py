import json

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from scripts.stress_counterfactual_delivery import save_tables
from scripts.verify_stress_counterfactual import verify_frozen, verify_run_identity, verify_tables


def test_verifier_rejects_changed_equity_even_after_refreshing_table_catalog(tmp_path):
    truth = {"metricas": [dict(period="full", final_equity_usdt="10500", net_pnl_usdt="500")]}
    folder = tmp_path / "resultados"
    save_tables(folder, truth)
    assert verify_tables(folder, truth) == 1
    before = (folder / "metricas.parquet").read_bytes()
    # Construct a valid typed table, and a self-consistent regenerated catalog.
    changed = {"metricas": [dict(period="full", final_equity_usdt="10600", net_pnl_usdt="600")]}
    save_tables(folder, changed)
    assert (folder / "metricas.parquet").read_bytes() != before
    assert pq.read_table(folder / "metricas.parquet").schema == pa.schema([
        ("period", pa.string()), ("final_equity_usdt", pa.string()), ("net_pnl_usdt", pa.string())])
    with pytest.raises(ValueError, match="recomputed"):
        verify_tables(folder, truth)


def test_verifier_rejects_omitting_a_required_recomputed_table(tmp_path):
    save_tables(tmp_path, {"metricas": [dict(value="1")]})
    (tmp_path / "catalogo.json").write_text(json.dumps({}))
    with pytest.raises(ValueError, match="population"):
        verify_tables(tmp_path, {"metricas": [dict(value="1")]})


def test_index_cannot_redirect_recomputation_away_from_authenticated_artifacts(tmp_path):
    (tmp_path / "alternative").mkdir()
    (tmp_path / "alternative/run_manifest.json").write_text("{}")
    item = dict(run_id="run_original", path="alternative")
    with pytest.raises(ValueError, match="canonical"):
        verify_run_identity(tmp_path, item, None, {})


def test_index_cannot_exempt_an_economic_scenario_as_technical(tmp_path):
    folder = tmp_path / "evidencia/run_original"
    folder.mkdir(parents=True)
    (folder / "run_manifest.json").write_text("{}")
    item = dict(run_id="run_original", path="evidencia/run_original", scenario="SH_P90", technical_control=True)
    with pytest.raises(ValueError, match="technical"):
        verify_run_identity(tmp_path, item, None, {})


def test_frozen_revision_verifies_selected_snapshot_without_rewriting_the_prior_one(tmp_path, monkeypatch):
    import hashlib
    monkeypatch.setattr("scripts.verify_stress_counterfactual.authenticate_approval", lambda p: None)
    old = tmp_path / "codigo_ejecutado/source.py"
    new = tmp_path / "codigo_ejecutado_02/source.py"
    for path, content in ((old, b"old source"), (new, b"corrected source")):
        path.parent.mkdir(parents=True)
        path.write_bytes(content)
    frozen = dict(candidate_files={}, code_files={"source.py": hashlib.sha256(new.read_bytes()).hexdigest()},
                  project_files={}, code_snapshot="codigo_ejecutado_02")
    (tmp_path / "protocolo_ejecucion.json").write_text(json.dumps(frozen))
    assert verify_frozen(tmp_path) == frozen
    assert old.read_bytes() == b"old source"
    new.write_bytes(b"altered source")
    with pytest.raises(ValueError, match="snapshot changed"):
        verify_frozen(tmp_path)
