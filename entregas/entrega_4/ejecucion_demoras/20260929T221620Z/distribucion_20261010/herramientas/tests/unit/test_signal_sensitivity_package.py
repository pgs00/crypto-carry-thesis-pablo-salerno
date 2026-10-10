"""Historical package mutation checks; explicit SENAL_PACKAGE selects a new candidate."""

import hashlib
import os
import shutil
from pathlib import Path

import pytest

from crypto_carry.config import Config
from scripts.build_signal_sensitivity import seal
from scripts.report_historical_rules_sensitivity import write_csv
from scripts.return_capital.common import read_csv, read_json, write_json
from scripts.verify_signal_sensitivity import verify


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


@pytest.fixture
def candidate(tmp_path):
    value = os.environ.get("SENAL_PACKAGE")
    if not value:
        pytest.skip("SENAL_PACKAGE must identify the actual new package for historical checks")
    source = Path(value).resolve()
    assert (source/"indice_corridas.json").is_file()
    target = tmp_path/"package"
    shutil.copytree(source, target)
    if not (target/"manifiesto_paquete.json").exists():
        seal(target)
    return target


def reseal_temporary(package):
    manifest = package/"manifiesto_paquete.json"
    data = read_json(manifest)
    data["members"] = [dict(path=p.relative_to(package).as_posix(), bytes=p.stat().st_size,
                            sha256=sha(p)) for p in sorted(package.rglob("*"))
                       if p.is_file() and p.name not in {"manifiesto_paquete.json", "manifiesto_paquete.sha256"}]
    write_json(manifest, data)
    (package/"manifiesto_paquete.sha256").write_text(sha(manifest)+"\n", encoding="ascii")


def test_historical_candidate_verification_does_not_write(candidate):
    before = {p.relative_to(candidate).as_posix(): sha(p) for p in candidate.rglob("*") if p.is_file()}
    assert verify(candidate)["passed"]
    after = {p.relative_to(candidate).as_posix(): sha(p) for p in candidate.rglob("*") if p.is_file()}
    assert after == before


@pytest.mark.parametrize("kind", ["configuration", "h1", "h2", "h3", "h3_duplicate", "period", "financial",
                                 "strategy", "economic_status", "protocol_code", "frozen_runner"])
def test_rehashed_semantic_corruption_is_rejected(candidate, kind):
    if kind == "configuration":
        index = read_json(candidate/"indice_corridas.json")
        item = next(r for r in index["runs"] if r["scenario"] == "H072" and r["strategy"] == "conditional")
        run = candidate/item["path"]
        config = Config.load(run/"effective_config.toml").changed(half_life_hours=12)
        (run/"effective_config.toml").write_text(config.to_toml(), encoding="utf-8")
        manifest = read_json(run/"run_manifest.json")
        manifest["config"] = config.to_dict()
        manifest["output_hashes"]["effective_config.toml"] = sha(run/"effective_config.toml")
        write_json(run/"run_manifest.json", manifest)
        (run/"run_manifest.sha256").write_text(sha(run/"run_manifest.json")+"\n", encoding="ascii")
        item["manifest_sha256"] = sha(run/"run_manifest.json")
        write_json(candidate/"indice_corridas.json", index)
        sources = read_csv(candidate/"fuentes/archivos_originales.csv")
        for row in sources:
            if row["run_id"] == item["run_id"]:
                path = candidate/row["package_path"]
                row.update(sha256=sha(path), bytes=path.stat().st_size)
        write_csv(candidate/"fuentes/archivos_originales.csv", sources)
    elif kind in {"strategy", "economic_status"}:
        index = read_json(candidate/"indice_corridas.json")
        selected = [r for r in index["runs"] if r["scenario"] == "H072"]
        if kind == "strategy":
            selected[0]["strategy"], selected[1]["strategy"] = selected[1]["strategy"], selected[0]["strategy"]
        else:
            selected[0]["engine_status"] = "insolvent"
        write_json(candidate/"indice_corridas.json", index)
    elif kind == "protocol_code":
        path = candidate/"documentos/protocolo_previo.json"
        value = read_json(path)
        value["engine_code_hash"] = "0"*64
        write_json(path, value)
    elif kind == "frozen_runner":
        path = candidate/"herramientas/scripts/run_signal_sensitivity.py"
        path.write_bytes(path.read_bytes()+b"\n# altered runner\n")
    else:
        names = {
            "h1": "hipotesis/H072/h1_observaciones.csv", "h2": "tablas/h2.csv",
            "h3": "hipotesis/BASE_E3/h3_grupos_forecast.csv", "period": "tablas/metricas.csv",
            "h3_duplicate": "hipotesis/BASE_E3/h3_activos_diarios.csv",
            "financial": "tablas/metricas.csv",
        }
        path = candidate/names[kind]
        rows = read_csv(path)
        if kind == "h1":
            row = next(r for r in rows if r["horizon_valid"] == "True")
            row["realized"] = "0.123456789"
        elif kind == "h2":
            rows[0]["verdict"] = "favorable" if rows[0]["verdict"] != "favorable" else "no_favorable"
        elif kind == "h3":
            row = next(r for r in rows if int(r["eligible_minutes"]) > 0)
            row["eligible_minutes"] = str(int(row["eligible_minutes"])-1)
        elif kind == "h3_duplicate":
            rows[1] = dict(rows[0])
        elif kind == "period":
            rows[0]["start_utc"] = "2022-01-02T00:00:00.000000000Z"
        else:
            rows[0]["net_pnl_usdt"] = "123456"
        write_csv(path, rows)
    reseal_temporary(candidate)
    with pytest.raises(ValueError):
        verify(candidate)


def test_verifier_output_refuses_protected_destinations(candidate):
    import subprocess
    import sys

    before = sha(candidate/"indice_corridas.json")
    command = [sys.executable, "-B", str(candidate/"herramientas/scripts/verify_signal_sensitivity.py"),
               "--package", str(candidate), "--output", str(candidate/"indice_corridas.json")]
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode != 0
    assert "outside protected inputs" in result.stderr
    assert sha(candidate/"indice_corridas.json") == before
