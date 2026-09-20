"""Add compact provenance snapshots to the draft delivery package."""

import hashlib
import json
import shutil
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
PACKAGE = PROJECT / "entregas/entrega_3/paquete_redaccion"
provenance_path = PACKAGE / "fuentes_originales.json"
provenance = json.loads(provenance_path.read_text(encoding="utf-8"))

paths = {
    "docs/methodology.md": "evidencia/procedencia/methodology.md.txt",
    "docs/escenario_investigacion.md": "evidencia/procedencia/escenario_investigacion.md.txt",
    "docs/sources/Prompt_Codex_Backtesting.md": "evidencia/procedencia/Prompt_Codex_Backtesting.md.txt",
    "docs/sources/Prompt_Codex_Ajuste_Backtesting_1m.md": "evidencia/procedencia/Prompt_Codex_Ajuste_Backtesting_1m.md.txt",
    "entregas/entrega_3/preparar_paquete.py": "scripts/preparar_paquete.py",
}
for name in (
    "reporting",
    "ledger",
    "risk",
    "margin",
    "execution",
    "forecast",
    "portfolio",
    "config",
    "costs",
):
    paths[f"src/crypto_carry/{name}.py"] = f"evidencia/codigo/{name}.py"
for original, relative in paths.items():
    source, target = PROJECT / original, PACKAGE / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    assert digest == hashlib.sha256(target.read_bytes()).hexdigest()
    provenance["files"] = [r for r in provenance["files"] if r["archivo"] != relative]
    provenance["files"].append(
        dict(original=str(source), archivo=relative, sha256=digest, bytes=target.stat().st_size)
    )
provenance_path.write_text(
    json.dumps(provenance, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)
report_path = PACKAGE / "evidencia/execution_revision_report.md"
report = report_path.read_text(encoding="utf-8")
for source in (PACKAGE / "evidencia/revision").glob("*.csv"):
    report = report.replace(f"]({source.name})", f"](revision/{source.name})")
report_path.write_text(report, encoding="utf-8")
print(f"Provenance contains {len(provenance['files'])} source files")
