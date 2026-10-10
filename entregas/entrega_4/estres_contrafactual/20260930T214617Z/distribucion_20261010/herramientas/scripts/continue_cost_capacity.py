"""Continue authorized stages only after all preceding runs and audits pass."""

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.cost_capacity import BASES, STAGES  # noqa: E402
from scripts.return_capital.common import read_json, write_json  # noqa: E402


def command(work, name, arguments):
    target = work/(name+".log")
    if target.exists():
        raise FileExistsError("Continuation log already exists")
    cmd = [sys.executable, "-B", "-u", "-X", "utf8", *arguments]
    print("COMMAND", cmd, flush=True)
    with target.open("x", encoding="utf8") as log:
        result = subprocess.run(cmd, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    write_json(work/(name+"_comando.json"), dict(command=cmd, exit_code=result.returncode, log=str(target)))
    if result.returncode:
        raise RuntimeError("Stage or gate failed: "+name)


def wait_previous(work):
    while True:
        paths = [work/"ejecuciones"/f"{s}__{t}.json" for s in STAGES["costos"] for t in BASES]
        states = [read_json(p).get("status") if p.exists() else "pendiente" for p in paths]
        if any(s in {"fallido", "bloqueado"} for s in states):
            raise RuntimeError("Previous cost stage contains failed/blocked run")
        if all(s == "ejecutado" for s in states):
            return
        time.sleep(10)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--raw-root", type=Path, required=True)
    a = parser.parse_args()
    work, data, raw = a.work.resolve(), a.data_root.resolve(), a.raw_root.resolve()
    wait_previous(work)
    for stage in ("costos", "participacion", "capital"):
        if stage != "costos":
            command(work, "etapa_"+stage, [str(ROOT/"scripts/run_cost_capacity.py"),
                "--package", str(work), "--data-root", str(data), "--raw-root", str(raw),
                "--stage", stage, "--workers", "2"])
        command(work, "auditoria_etapa_"+stage, [str(ROOT/"scripts/audit_cost_capacity_stage.py"),
            "--work", str(work), "--data-root", str(data), "--stage", stage])
        print("GATE_PASSED", stage, flush=True)
