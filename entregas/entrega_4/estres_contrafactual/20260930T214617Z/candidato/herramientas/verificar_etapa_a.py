"""Verifica la preparación pendiente, sin motor, simulaciones o modificación de fuentes."""

import argparse
import ast
import csv
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from urllib.parse import unquote

from auditar_etapa_a import read, rows, save, sha

sys.dont_write_bytecode = True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root, candidate = args.root.resolve(), args.candidate.resolve()
    proposal = read(candidate / "protocolo_propuesto.json")
    assert not proposal["approval_received"] and proposal["economic_runs"] == 0
    assert proposal["economic_portfolios_proposed"] == 6
    expected_status = "protocolo_preparado_pendiente_aprobacion"
    assert proposal["status"] == expected_status
    assert not list(candidate.glob("manifiesto_paquete*")), "El candidato no debe sellarse"
    identity = read(candidate / "identidad_propuesta.json")
    for name, digest in identity["sha256"].items():
        assert sha(candidate / name) == digest, name
    for path in candidate.rglob("*.json"):
        read(path)
    for path in candidate.rglob("*.csv"):
        with path.open(encoding="utf-8-sig", newline="") as stream:
            parsed = list(csv.reader(stream))
            assert parsed and all(len(r) == len(parsed[0]) for r in parsed), path
    for path in (candidate / "herramientas").glob("*.py"):
        ast.parse(path.read_text(encoding="utf-8"))
    sealed = read(candidate / "controles/sellos_entrada.json")
    count = 0
    for package in sealed:
        folder = root / package["path"]
        assert sha(folder / "manifiesto_paquete.json") == package["manifest_sha256"]
        manifest = read(folder / "manifiesto_paquete.json")
        for member in manifest.get("members", manifest.get("files")):
            assert sha(folder / member["path"]) == member["sha256"], member["path"]
            count += 1
    sources = read(candidate / "controles/entradas_masivas.json")
    for source in sources:
        if source["key"] == "processed_manifest_semantics":
            assert sha(source["path"]) == source["file_sha256"]
            semantic = {k: v for k, v in read(source["path"]).items()
                        if k != "source_manifest_sha256"}
            digest = hashlib.sha256(json.dumps(semantic, sort_keys=True).encode()).hexdigest()
        else:
            digest = sha(source["path"])
        assert digest == source["expected"]
    comp = read(candidate / "controles/compatibilidad_recalculada.json")
    assert comp["passed"] and len(comp["comparisons"]) == 2
    assert all(len(r["comparisons"]) == 11 and all(c["exact_equal"] and
               c["row_order"] == "original_persisted" for c in r["comparisons"])
               for r in comp["comparisons"])
    ledgers = read(candidate / "controles/conciliacion_referencias.json")
    assert len(ledgers) == 4 and all(r["passed"] and r["daily_links"] == 1704 for r in ledgers)
    equations = []
    for record in read(candidate / "controles/identidades_corridas.json"):
        folder = Path(record["path"])
        assert sha(folder / "run_manifest.json") == record["manifest_sha256"]
        manifest = read(folder / "run_manifest.json")
        for name, digest in manifest["output_hashes"].items():
            assert sha(folder / name) == digest
        if record["run_id"] in {c["control_run_id"] for c in comp["comparisons"]}:
            assert all(sha(root / name) == digest for name, digest in manifest["code_files"].items())
        max_equity, max_pnl = Decimal(0), Decimal(0)
        daily = rows(folder / "equity_daily.csv")
        for row in daily:
            equity = Decimal(row["free_spot"]) + Decimal(row["free_futures"]) - Decimal(row["debt"])
            pnl = Decimal(0)
            for symbol in ("BTCUSDT", "ETHUSDT"):
                def n(key):
                    return Decimal(row[symbol + "_" + key])
                upnl = n("short") * (n("average") - n("mark"))
                spot = n("spot") * n("spot_price")
                equity += n("collateral") + spot + upnl
                pnl += (n("realized_spot") + spot - n("spot_cost") + n("realized_futures")
                        + upnl + n("funding") - n("fees") - n("liquidation_fees"))
            max_equity = max(max_equity, abs(equity - Decimal(row["equity"])))
            max_pnl = max(max_pnl, abs(Decimal(row["equity"]) - Decimal("10000") - pnl))
        assert max_equity <= Decimal("1E-8") and max_pnl <= Decimal("1E-8")
        equations.append(dict(run_id=record["run_id"], daily_rows=len(daily),
             max_equity_residual=str(max_equity), max_pnl_residual=str(max_pnl), passed=True))
    assert equations == read(candidate / "controles/conciliacion_equity_pnl_diaria.json")
    calibration = read(candidate / "controles/calibracion.json")
    assert calibration["passed"] and calibration["episode_rows_equal"] == 466
    risk = Path(calibration["source"])
    for name in ("calibracion_episodios.csv", "calibracion_escenarios_pendientes.csv"):
        assert sha(candidate / "tablas" / name) == sha(risk / "figuras/fuentes" / name)
    for r in rows(candidate / "tablas/calibracion_escenarios_pendientes.csv"):
        if r["valuation"] == "original_reconstructed":
            for scenario, field in [("SH_P90", "p90_adverse_fraction"),
                                    ("SH_MAX", "maximum_adverse_fraction")]:
                assert proposal["shocks"]["magnitudes_fraction"][scenario][r["symbol"]] == r[field]
    schedule = rows(candidate / "tablas/calendario_shocks_propuesto.csv")
    assert len(schedule) == 233
    for r in schedule:
        a, b, e = [int(r[k]) for k in ["first_bar_open_ns", "plateau_end_open_ns", "recovery_end_open_ns"]]
        minute = 60_000_000_000
        assert a % minute == b % minute == e % minute == 0
        assert a == (int(r["base_start_ns"]) + minute - 1) // minute * minute
        assert b == max(a + minute, (int(r["base_end_ns"]) + minute - 1) // minute * minute)
        assert e - b == 60 * minute
    sample = rows(candidate / "tablas/muestra_volumen_previa.csv")
    volumes = rows(candidate / "tablas/volumen_cf_propuesto.csv")
    assert len(sample) == 720 and len(volumes) == 306
    for r in volumes:
        group = [Decimal(v["base_volume"]) for v in sample if
                 (v["symbol"], v["hour_utc"]) == (r["symbol"], r["hour_utc"])]
        assert len(group) == 120
        ordered = sorted(group)
        median = (ordered[59] + ordered[60]) / 2
        assert median == Decimal(r["median_base_volume"])
        assert median * Decimal("0.01") == Decimal(r["gross_cap_base"])
    matrix = {r["id"]: r for r in rows(root / "docs/entrega_4/matriz_avance.csv")}
    old = rows(root / "docs/entrega_4/historial_avance/20260930T214617Z_etapa_a_anterior.csv")
    assert all(matrix[r["id"]] == r for r in old if r["id"] != "B5")
    assert all(matrix[k]["estado"] == expected_status for k in ("B5", "B5_SHOCKS", "B5_CF"))
    assert all(matrix[k]["estado"] == "pendiente" for k in ("B6", "REVISION", "ALCANCE_REPARACION_B2_B3"))
    missing = []
    docs = list(candidate.glob("*.md")) + [root / "docs/entrega_4/inventario_limpieza_bloque5_20260930.md"]
    for path in docs:
        text = path.read_text(encoding="utf-8")
        assert "\ufffd" not in text and "Ã" not in text, path
        for target in re.findall(r"\]\(([^\s)]+)(?:\s+[^)]*)?\)", text):
            if "://" in target or target.startswith("#"):
                continue
            resolved = path.parent / unquote(target.split("#")[0])
            if not resolved.exists() and resolved.resolve() != args.output.resolve():
                missing.append(dict(source=str(path), target=target))
    assert not missing, missing
    backup = read(candidate / "controles/respaldo_caches.json")
    assert backup["backup_verified"] and len(backup["files"]) == 8
    for item in backup["files"]:
        assert sha(root / item["source"]) == sha(item["backup"]) == item["sha256"]
    assert read(candidate / "controles/aislamiento_limpieza.json")["exit_code"] == 0
    env = dict(os.environ, GIT_OPTIONAL_LOCKS="0", PYTHONDONTWRITEBYTECODE="1")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, env=env).decode().strip()
    initial = read(candidate / "controles/estado_inicial.json")
    assert head == initial["head"]
    assert sha(root / ".git/index") == initial["initial_index_sha256"]
    changed = subprocess.check_output(["git", "diff", "--name-only"], cwd=root, env=env).decode().splitlines()
    assert set(changed) == {"docs/entrega_4/matriz_avance.csv", "docs/entrega_4/historial_avance/cambios.md"}
    assert not subprocess.check_output(["git", "diff", "--cached", "--name-only"], cwd=root, env=env)
    check = subprocess.run(["git", "diff", "--check"], cwd=root, env=env, capture_output=True)
    assert check.returncode == 0, check.stdout + check.stderr
    ruff = subprocess.run([sys.executable, "-B", "-m", "ruff", "check", "--no-cache",
                           str(candidate / "herramientas"), "--config", str(root / "pyproject.toml")],
                          cwd=root, env=env, capture_output=True)
    assert ruff.returncode == 0, ruff.stdout + ruff.stderr
    save(args.output, dict(passed=True, utc=datetime.now(timezone.utc).isoformat(),
        sealed_dependencies=len(sealed), members_authenticated=count, input_identities=len(sources),
        exact_ordered_comparisons=22, reconciled_runs=4, calibration_rows=466,
        daily_equity_pnl_checks=6816, max_equity_residual="1E-23",
        proposed_calendar_rows=233, prevolume_rows=720, volume_assumptions=306,
        new_economic_runs=0, new_scenario_implementation=False, approval_received=False,
        head=head, index_sha256=sha(root / ".git/index"), tracked_paths_changed=changed,
        missing_links=missing, ruff=ruff.stdout.decode().strip(), git_diff_check=True,
        previous_sources_intact=True, cleanup_originals_removed=0, cleanup_originals_moved=0,
        scope="Local etapa A; does not claim a portable sealed delivery or stage B execution"))
    print("ETAPA A VERIFIED; approval pending; 0 new economic runs")


if __name__ == "__main__":
    main()
