"""Reproduce generated artifacts from an isolated package copy and compare hashes."""

import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
PACKAGE = PROJECT / "entregas/entrega_3/paquete_redaccion"
WORK = (
    PROJECT / ".superpowers/entrega3" / ("portabilidad_" + datetime.now().strftime("%Y%m%d_%H%M%S"))
)
COPIED = WORK / "paquete_redaccion"
OUTPUT = WORK / "regenerado"
shutil.copytree(PACKAGE, COPIED, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
logs = []
for script in ("reproducir.py", "diccionario.py"):
    command = [sys.executable, "-I", str(COPIED / "scripts" / script), "--destino", str(OUTPUT)]
    # Python isolation removes local imports, so the tiny wrapper explicitly adds only
    # the copied script directory; it never adds the project or its engine package.
    wrapper = "import runpy,sys; sys.path.insert(0,sys.argv[1]); sys.argv=sys.argv[2:]; runpy.run_path(sys.argv[0],run_name='__main__')"
    command = [
        sys.executable,
        "-I",
        "-c",
        wrapper,
        str(COPIED / "scripts"),
        str(COPIED / "scripts" / script),
        "--destino",
        str(OUTPUT),
    ]
    result = subprocess.run(command, cwd=COPIED, capture_output=True, text=True, encoding="utf-8")
    logs.append(
        dict(script=script, exit_code=result.returncode, stdout=result.stdout, stderr=result.stderr)
    )
    if result.returncode:
        raise RuntimeError(logs[-1])
compared = []
for path in sorted(OUTPUT.rglob("*")):
    if not path.is_file():
        continue
    relative = path.relative_to(OUTPUT)
    generated = hashlib.sha256(path.read_bytes()).hexdigest()
    expected = hashlib.sha256((PACKAGE / relative).read_bytes()).hexdigest()
    assert generated == expected, relative
    compared.append(dict(archivo=relative.as_posix(), sha256=generated))
record = dict(
    carpeta_aislada=str(WORK), python_isolated=True, comandos=logs, archivos_identicos=compared
)
(PACKAGE / "evidencia/portabilidad.json").write_text(
    json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)
print(json.dumps(dict(archivos_identicos=len(compared), carpeta_aislada=str(WORK)), indent=2))
