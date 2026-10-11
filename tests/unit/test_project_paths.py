"""Recorded historical routes resolve without weakening evidence identities."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.project_paths import HISTORICAL_ROOT, PATH_MOVES, ROOT, resolve_recorded_path


def test_runtime_map_matches_the_documented_migration():
    registry = json.loads((ROOT / "docs/procedencia/rutas.json").read_text(encoding="utf-8"))
    assert registry["paths"] == PATH_MOVES


@pytest.mark.parametrize("prefix", ["", HISTORICAL_ROOT + "/", "\\\\?\\" + HISTORICAL_ROOT.replace("/", "\\") + "\\"])
def test_historical_windows_and_relative_routes_use_the_new_project(prefix, tmp_path):
    old = "entregas/entrega_4/reglas_historicas/20260925T005436Z"
    assert resolve_recorded_path(prefix + old + "/indice_corridas.json", tmp_path) == (
        tmp_path / "data/evidence/reglas_historicas/indice_corridas.json"
    )


def test_external_data_and_unlisted_historical_paths_remain_explicit():
    external = "D:/Backtesting/outputs/run_original/run_manifest.json"
    unknown = "entregas/entrega_4/reglas_historicas/failed_attempt/file.json"
    assert resolve_recorded_path(external) == Path(external)
    assert resolve_recorded_path(unknown) == Path(unknown)


def test_historical_path_cannot_escape_its_mapped_source():
    with pytest.raises(ValueError, match="escapes"):
        resolve_recorded_path("entregas/entrega_4/reglas_historicas/20260925T005436Z/../../secret")


def test_recorded_dependencies_exist_and_keep_their_original_identity():
    source = ROOT / "results/senal/evidencia/documentos/autenticacion_referencias.json"
    references = json.loads(source.read_text(encoding="utf-8"))
    for reference in references:
        package = resolve_recorded_path(reference["path"])
        assert package.is_dir(), reference["dependency"]
        descriptor = package / "procedencia/derivacion.json"
        manifest_path = descriptor if descriptor.is_file() else package / "manifiesto_paquete.json"
        manifest = json.loads(manifest_path.read_text())
        if "original_manifest_sha256" in manifest:
            assert manifest["original_manifest_sha256"] == reference["manifest_sha256"]


@pytest.mark.parametrize("exported", [False, True])
def test_synthesis_isolated_cli_help_uses_the_adjacent_route_helper(tmp_path, exported):
    script = ROOT / "scripts/stability_uncertainty_synthesis.py"
    if exported:
        tools = tmp_path / "herramientas/scripts"
        tools.mkdir(parents=True)
        for name in (script.name, "project_paths.py"):
            shutil.copyfile(ROOT / "scripts" / name, tools / name)
        script = tools / script.name
    result = subprocess.run(
        [sys.executable, "-B", "-I", "-X", "utf8", str(script), "--help"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert "--candidate" in result.stdout
