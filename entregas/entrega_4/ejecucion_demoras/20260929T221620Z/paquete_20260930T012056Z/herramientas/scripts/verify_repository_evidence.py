"""Verify published evidence, archived bytes and current documentation offline."""

import json
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from urllib.parse import unquote

from entregas.entrega_3.archivo.empaquetar import verify_reference_sources
from scripts.analyze_funding_prices import verify_output as verify_funding
from scripts.publish_thesis import ARCHIVE, PUBLISHED, ROOT, digest, require
from scripts.publish_thesis import verify as verify_presentation

CURRENT_DOCS = (
    "README.md",
    "docs/methodology.md",
    "docs/progress.md",
    "docs/repository_cleanup.md",
    "docs/research/README.md",
    "docs/descarga_d.md",
    "docs/fiabilidad.md",
    "docs/data_dictionary.md",
    "docs/escenario_investigacion.md",
    "entregas/entrega_3/README.md",
    "entregas/entrega_3/continua/README.md",
    "entregas/entrega_3/archivo/README.md",
    "data/research/README.md",
    "data/research/basis-audit-20260919/README.md",
    "data/manifests/README.md",
    "data/manifests/data_quality_report.md",
)


def command_json(script, *args):
    result = subprocess.run(
        [sys.executable, "-I", str(script), *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return json.loads(result.stdout)


def check_document_encoding(content, name):
    """Detect replacement bytes in prose and formulas without rejecting URL queries."""
    prose = re.sub(r"https?://[^\s>)]+", "", content)
    damaged = re.search(r"\w\?\w|(?<!\w)\?(?=\w)|(?<=\s)\?(?=\s)", prose)
    require("\ufffd" not in content and not damaged, "Encoding damage in " + name)


def check_links():
    """Check active relative links; immutable historical snapshots keep their context."""
    checked = 0
    for name in CURRENT_DOCS:
        path = ROOT / name
        content = path.read_text(encoding="utf-8")
        check_document_encoding(content, name)
        for match in re.finditer(r"\]\((<[^>]+>|[^\s)]+)\)", content):
            target = match.group(1).strip("<>")
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            require(not re.match(r"[a-zA-Z]:", target), "Drive-specific link in " + name)
            relative, _, fragment = unquote(target).partition("#")
            destination = (path.parent / relative).resolve() if relative else path
            require(destination.is_file(), f"Broken link in {name}: {target}")
            if fragment and destination.suffix == ".md":
                headings = re.findall(r"^#+\s+(.+)$", destination.read_text(encoding="utf-8"), re.M)
                anchors = [re.sub(r"[^\w\- ]", "", h.lower()).replace(" ", "-") for h in headings]
                require(fragment in anchors, f"Broken heading in {name}: {target}")
            checked += 1
    return checked


def verify_cleanup():
    path = ROOT / "docs/repository_cleanup_manifest.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    checked = 0
    for name, expected in record["unchanged_files"].items():
        allowed = {expected["working_tree_sha256"]}
        if expected.get("verified_newline_only_variant"):
            allowed.add(expected["original_git_blob_sha256"])
        require(digest((ROOT / name).read_bytes()) in allowed, "Protected source changed: " + name)
        checked += 1
    for row in record["relocated_files"]:
        require(
            digest((ROOT / row["current"]).read_bytes()) == row["sha256"],
            "Archived source changed: " + row["current"],
        )
        checked += 1
    for row in record["removed_duplicates"]:
        require(not (ROOT / row["removed"]).exists(), "Duplicate was not removed")
        require(
            digest((ROOT / row["preserved"]).read_bytes()) == row["sha256"],
            "Duplicate source was lost",
        )
    local_files = 0
    for row in record["local_market_files"]:
        local = ROOT / row["path"]
        if local.exists():
            require(digest(local.read_bytes()) == row["sha256"], "Local market file changed")
            local_files += 1
    tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().split("\0")
    require(
        not any(name in tracked for name in (r["path"] for r in record["local_market_files"])),
        "Local research market data still tracked",
    )
    probes = [
        "data/raw/probe.zip",
        "data/processed/probe.parquet",
        "data/minutes/probe.zip",
        "outputs/probe.csv",
        "data/research/any/probe.zip",
        "data/research/any/probe.parquet",
    ]
    ignored = (
        subprocess.check_output(["git", "check-ignore", "--no-index", "--", *probes], cwd=ROOT)
        .decode()
        .splitlines()
    )
    require(set(ignored) == set(probes), "Missing massive-data ignore rule")
    return dict(
        protected_or_archived_files=checked,
        removed_duplicates=len(record["removed_duplicates"]),
        local_market_files_unchanged=local_files,
        ignore_rules_verified=len(probes),
    )


def main():
    preserved = verify_cleanup()
    presentation = verify_presentation(PUBLISHED)
    historical = ROOT / "entregas/entrega_3/archivo"
    anchor = verify_reference_sources(
        historical / "paquete_redaccion", historical / "paquete_redaccion_entrega_3.zip"
    )
    old = command_json(historical / "paquete_redaccion/scripts/verificar_paquete.py")
    with zipfile.ZipFile(historical / "paquete_redaccion_entrega_3_v2.zip") as archive:
        require(archive.testzip() is None, "Historical v2 CRC mismatch")
        members = [m for m in archive.infolist() if not m.is_dir()]
        for member in members:
            require(
                archive.read(member) == (historical / member.filename).read_bytes(),
                "Historical v2 member differs",
            )
    funding = verify_funding(ROOT / "data/research/funding-price-sensitivity-20260920")
    work = ROOT / ".superpowers/repository_evidence_verification"
    work.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="current_zip_", dir=work) as directory:
        destination = Path(directory).resolve()
        require(
            destination.is_relative_to(work.resolve()), "Temporary extraction escapes its workspace"
        )
        with zipfile.ZipFile(ARCHIVE) as archive:
            for name in archive.namelist():
                require(
                    (destination / name).resolve().is_relative_to(destination), "ZIP path traversal"
                )
            archive.extractall(destination)
        current = command_json(destination / "verificar.py")
    print(
        json.dumps(
            dict(
                status="verified",
                cleanup=preserved,
                presentation=presentation,
                current_package=current,
                historical_package=old,
                historical_v2_members=len(members),
                original_zip_anchor=anchor,
                funding_sensitivity=funding,
                current_document_links=check_links(),
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
