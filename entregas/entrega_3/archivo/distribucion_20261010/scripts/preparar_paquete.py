"""Stage a portable, immutable subset of verified runs without resimulating."""

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from crypto_carry.execution_revision import verify_execution_revision

PROJECT = next(
    (path for path in Path(__file__).resolve().parents if (path / "src/crypto_carry").is_dir()),
    Path.cwd(),
)
REVISION = "revision_eb5ed744b30836a39fd694fa"
AUDIT = "basis_audit_afd512e8a542f331ffa9ac3f"


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def prepare(root, destination):
    revision = root / "outputs" / REVISION
    verified = verify_execution_revision(revision)
    if not verified["valid"] or verified["status"] != "complete":
        raise ValueError(verified)
    audit = PROJECT / "outputs" / AUDIT
    am = load(audit / "basis_audit_manifest.json")
    if (
        digest(audit / "basis_audit_manifest.json")
        != (audit / "basis_audit_manifest.sha256").read_text().strip()
    ):
        raise ValueError("Basis audit manifest checksum mismatch")
    for name, expected in am["output_hashes"].items():
        if digest(audit / name) != expected:
            raise ValueError(f"Basis audit checksum mismatch: {name}")
    if am["corrected_revision"]["id"] != REVISION:
        raise ValueError("Audit and execution revision disagree")
    destination.mkdir(parents=True, exist_ok=False)
    provenance = []

    def copy(source, relative):
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        checksum = digest(source)
        if checksum != digest(target):
            raise ValueError(f"Copy mismatch: {target}")
        provenance.append(
            dict(
                original=str(source.resolve()),
                archivo=relative,
                sha256=checksum,
                bytes=target.stat().st_size,
            )
        )

    rm = load(revision / "revision_manifest.json")
    for source in sorted(revision.iterdir()):
        if source.suffix in {".csv", ".json", ".sha256"}:
            copy(source, "evidencia/revision/" + source.name)
    copy(
        revision / "execution_revision_report.md",
        "evidencia/originales/execution_revision_report.txt",
    )
    report = (revision / "execution_revision_report.md").read_text(encoding="utf-8")
    for source in revision.glob("*.csv"):
        report = report.replace(f"]({source.name})", f"](revision/{source.name})")
    for item in rm["input_runs"]:
        run = Path(item["path"])
        for name in ("run_manifest.json", "run_manifest.sha256", "effective_config.toml"):
            copy(run / name, f"evidencia/corridas/{run.name}/{name}")
        report = report.replace(
            f"../{run.name}/report.md", f"corridas/{run.name}/run_manifest.json"
        )
        if item["scenario"] != "vwap_joint":
            continue
        for name in (
            "metrics.csv",
            "equity_daily.csv",
            "pnl_components.csv",
            "execution_summary.csv",
            "h1_summary.csv",
            "forecast_evaluation.csv",
            "opportunity_daily.csv",
            "research_assumptions.json",
            "funding_mark_audit.json",
            "run_summary.csv",
        ):
            copy(run / name, f"evidencia/corridas/{run.name}/{name}")
    (destination / "evidencia/execution_revision_report.md").write_text(
        "> Copia de consulta: enlaces a las corridas adaptados al paquete. "
        "El original íntegro está en `originales/execution_revision_report.txt`.\n\n" + report,
        encoding="utf-8",
    )
    for name in (
        "basis_audit_summary.csv",
        "basis_audit_sample.csv",
        "basis_audit_sources.csv",
        "basis_report_reconciliation.csv",
        "report_preservation_comparison.csv",
        "basis_audit_manifest.json",
        "basis_audit_manifest.sha256",
    ):
        copy(audit / name, "evidencia/basis/" + name)
    copy(audit / "basis_audit_report.md", "evidencia/originales/basis_audit_report.txt")
    report = (
        (audit / "basis_audit_report.md")
        .read_text(encoding="utf-8")
        .replace(
            f"D:/Backtesting/outputs/{REVISION}/execution_revision_report.md",
            "execution_revision_report.md",
        )
    )
    (destination / "evidencia/basis_audit_report.md").write_text(
        "> Copia de consulta: enlace al informe corregido adaptado al paquete. "
        "El original íntegro está en `originales/basis_audit_report.txt`.\n\n" + report,
        encoding="utf-8",
    )
    academic = PROJECT.parent / "Informes"
    for path in sorted(academic.iterdir()):
        if path.name.startswith(("Entrega 1", "Entrega 2")) and path.suffix in {".docx", ".pdf"}:
            copy(path, "antecedentes/" + path.name)
    for relative in (
        "src/crypto_carry/nautilus_adapter.py",
        "src/crypto_carry/strategy.py",
        "src/crypto_carry/evaluation.py",
        "src/crypto_carry/data/funding_proxy.py",
        "src/crypto_carry/data/prescribed.py",
        "src/crypto_carry/execution_revision.py",
    ):
        copy(PROJECT / relative, "evidencia/codigo/" + Path(relative).name)
    for name in (
        "public_rules_alternatives_20260918.json",
        "public_rules_alternatives_20260918.md",
        "fees_followup_20260918.md",
        "historical_market_rules.md",
        "methodology_two_days_20260918.md",
    ):
        source = PROJECT / "docs/research" / name
        if source.is_file():
            # Text snapshots preserve historical external references without broken package links.
            copy(
                source, "evidencia/procedencia/" + name + (".txt" if source.suffix == ".md" else "")
            )
    copy(PROJECT / "docs/sources/Prompt_Codex_Paquete_Entrega_3.md", "evidencia/instructivo.md")
    copy(Path(__file__), "scripts/preparar_paquete.py")
    (destination / "fuentes_originales.json").write_text(
        json.dumps(
            dict(
                revision=REVISION,
                basis_audit=AUDIT,
                preparation_verification=verified,
                files=provenance,
            ),
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=Path("D:/Backtesting"))
    parser.add_argument(
        "--destination", type=Path, default=PROJECT / "entregas/entrega_3/paquete_redaccion"
    )
    args = parser.parse_args()
    print(prepare(args.data_root.resolve(), args.destination.resolve()))
