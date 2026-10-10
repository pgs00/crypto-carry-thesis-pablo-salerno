"""Approval bytes, rather than convenient defaults, select the scenario."""

import json
import shutil
from decimal import Decimal as D
from pathlib import Path

import pytest

from scripts.stress_counterfactual_contract import load_spec

APPROVED = Path(__file__).resolve().parents[2] / (
    "entregas/entrega_4/estres_contrafactual/20260930T214617Z/paquete_20261001T211248Z")


@pytest.fixture
def approval_copy(tmp_path):
    approval = json.loads((APPROVED / "aprobacion_recibida.json").read_text(encoding="utf-8"))
    for name in (*approval["approved_files_sha256"], "aprobacion_recibida.json",
                 "identidad_propuesta.json"):
        destination = tmp_path / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(APPROVED / name, destination)
    return tmp_path


def test_approved_decimal_magnitudes_and_calendar_are_loaded_without_recalibration(approval_copy):
    spec = load_spec(approval_copy, "SH_MAX")
    assert spec["magnitudes"] == {"BTCUSDT": D("0.005498931623931669"),
                                  "ETHUSDT": D("0.014434038177835395")}
    assert len(spec["episodes"]) == 233
    assert len(load_spec(approval_copy, "CF_SIN_INTERRUPCION")["volumes"]) == 306


def test_changed_approved_calendar_is_rejected_before_running(approval_copy):
    path = approval_copy / "tablas/calendario_shocks_propuesto.csv"
    original = path.read_bytes()
    path.write_bytes(original.replace(b"1673683380000000000", b"1673683320000000000", 1))
    assert path.read_bytes() != original
    with pytest.raises(ValueError, match="approved"):
        load_spec(approval_copy, "SH_P90")


def test_missing_family_approval_is_not_inferred_from_an_existing_proposal(approval_copy):
    path = approval_copy / "aprobacion_recibida.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    value["families"] = ["SH_P90", "SH_MAX"]
    path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(ValueError, match="approved"):
        load_spec(approval_copy, "CF_SIN_INTERRUPCION")


def test_control_zero_uses_same_calendar_but_zero_magnitude(approval_copy):
    spec = load_spec(approval_copy, "CONTROL_CERO")
    assert spec["episodes"] == load_spec(approval_copy, "SH_P90")["episodes"]
    assert all(v == 0 for v in spec["magnitudes"].values())
    assert load_spec(approval_copy, "CONTROL_APAGADO")["kind"] == "off"
    with pytest.raises(ValueError, match="scenario"):
        load_spec(approval_copy, "SH_BETTER")
