"""Historical snapshot and tamper controls, using only approved postprocessing."""

import os
import shutil
from pathlib import Path

import pytest

from scripts.return_capital.common import read_csv, read_json, sha256, write_csv, write_json
from scripts.sofr_benchmark.calculation import PREVIOUS_HASH
from scripts.sofr_benchmark.integrity import new_destination
from scripts.sofr_benchmark.package import build
from scripts.sofr_benchmark.verification import verify

ROOT = Path(__file__).resolve().parents[2]
INPUTS = Path(
    os.environ.get("SOFR_INPUTS", ROOT / "entregas/entrega_4/retorno_capital/20260927T154653Z_sofr/distribucion_20261010")
)
PREVIOUS = Path(
    os.environ.get(
        "SOFR_PREVIOUS",
        ROOT / "entregas/entrega_4/retorno_capital/20260927T143928Z/distribucion_20261010",
    )
)


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    if not INPUTS.exists() or not PREVIOUS.exists():
        pytest.skip("Set SOFR_INPUTS and SOFR_PREVIOUS for explicit archived inputs")
    output = tmp_path_factory.mktemp("sofr-package") / "new"
    build(
        output, PREVIOUS, INPUTS / "documentos", INPUTS / "fuentes_publicas", Path(__file__).parent
    )
    return output


def reseal_for_negative_test(package):
    """Attacker changes bytes and refreshes hashes: arithmetic checks must still fail."""
    path = package / "manifiesto_paquete.json"
    manifest = read_json(path)
    for member in manifest["members"]:
        file = package / member["path"]
        member.update(bytes=file.stat().st_size, sha256=sha256(file))
    write_json(path, manifest)
    (package / "manifiesto_paquete.sha256").write_text(sha256(path), encoding="utf-8")


def test_compact_and_complete_verify_authorized_snapshot_without_engine(built):
    for previous in (None, PREVIOUS):
        audit = verify(built, previous)
        assert audit["status"] == "passed" and audit["engine_executed"] is False
        assert audit["account_days"] == 1704 and audit["index_checks"] == 2326
        assert audit["unexplained_missing_dates"] == 0
        assert audit["previous_manifest_sha256"] == PREVIOUS_HASH
    rows = read_csv(built / "tablas/metricas_sofr_periodos.csv")
    assert len(rows) == 8


def test_builder_refuses_existing_or_overlapping_sources(built):
    with pytest.raises(ValueError):
        build(
            built,
            PREVIOUS,
            INPUTS / "documentos",
            INPUTS / "fuentes_publicas",
            Path(__file__).parent,
        )
    with pytest.raises(ValueError):
        new_destination(PREVIOUS / "nested-new", [PREVIOUS])


@pytest.mark.parametrize(
    "target",
    ["interest", "initial", "calendar", "comparison", "h2", "figure", "report", "approval", "rate"],
)
def test_rehashed_tampering_is_rejected(built, tmp_path, target):
    output = tmp_path / "tampered"
    shutil.copytree(built, output)
    if target == "approval":
        file = output / "documentos/aprobacion.json"
        content = read_json(file)
        content["cagr_day_basis"] = 360
        write_json(file, content)
    elif target == "rate":
        file = output / "fuentes_publicas/sofr_serie.json"
        content = read_json(file)
        content["refRates"].pop(7)
        write_json(file, content)
        registry = read_json(output / "fuentes_publicas/fuentes.json")
        for row in registry:
            if row["file"] == file.name:
                row.update(bytes=file.stat().st_size, sha256=sha256(file))
        write_json(output / "fuentes_publicas/fuentes.json", registry)
    elif target == "report":
        file = output / "reporte.md"
        file.write_text(file.read_text(encoding="utf-8") + "\nFalse result\n", encoding="utf-8")
    else:
        relative, field = {
            "interest": ("tablas/cartera_sofr_diaria.csv", "interest_usd"),
            "initial": ("tablas/control_bloque_inicial.csv", "account_days"),
            "calendar": ("tablas/calendario_verificado.csv", "is_business_day"),
            "comparison": ("tablas/comparacion_periodos.csv", "cagr365"),
            "h2": ("reutilizado/h2_reutilizado.csv", "period"),
            "figure": ("figuras/fuentes/capital.csv", "sofr_usd"),
        }[target]
        file = output / relative
        rows = read_csv(file)
        rows[0][field] = "999"
        write_csv(file, rows)
    reseal_for_negative_test(output)
    with pytest.raises(ValueError):
        verify(output)
