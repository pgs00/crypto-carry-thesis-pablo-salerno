"""Publication contract: the sealed historical package is never rewritten."""

import copy
import csv
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
REL = Path("data/research/historical-rules-followup-20260924T234206Z")
EXTERNAL = Path("data/research/fee-archive-followup-20260918")
SCRIPT = ROOT / "scripts/verify_historical_rules_publication.py"
REFERENCE = "894059e4ce318e51f25211d04be9f0202de90ae7"


def test_read_only_command_exists():
    assert SCRIPT.is_file(), "The read-only publication verifier must exist"


@pytest.fixture(scope="module")
def verifier():
    assert SCRIPT.is_file(), "The read-only publication verifier must exist"
    spec = importlib.util.spec_from_file_location("publication_verifier", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def export(tmp_path):
    root = tmp_path / "relocated_export"
    shutil.copytree(ROOT / REL, root / REL)
    (root / EXTERNAL).mkdir(parents=True)
    for name in ("A1.html", "A2.html", "A3.html"):
        shutil.copy2(ROOT / EXTERNAL / name, root / EXTERNAL / name)
    return root


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot(root):
    return {str(p.relative_to(root)): digest(p) for p in root.rglob("*") if p.is_file()}


def check(verifier, root, tmp_path):
    return verifier.verify(root=root, evidence=root / REL, temp_dir=tmp_path)


def test_intact_relocated_export_is_read_only_and_git_is_unchecked(verifier, export, tmp_path):
    before = snapshot(export)
    result = check(verifier, export, tmp_path)
    assert result["passed"], result
    assert result["documentary_integrity"]["passed"]
    assert result["provenance"]["git_status"] == "unchecked"
    assert result["original_session_audit"]["reproduced"] is False
    assert result["original_session_audit"]["recorded_passed"] is True
    assert all(row["passed"] for row in result["negative_tests"])
    assert len(result["negative_tests"]) >= 10
    assert snapshot(export) == before


@pytest.mark.parametrize("relative", [
    REL / "originales/SPOT26.body", REL / "reglas_historicas.json",
    REL / "extraidos/A1.txt", REL / "README.md", EXTERNAL / "A1.html",
    EXTERNAL / "A2.html", EXTERNAL / "A3.html", REL / "verificacion_resultados.json",
])
def test_mutated_members_sources_registry_extractions_and_session_fail(
    verifier, export, tmp_path, relative
):
    path = export / relative
    path.write_bytes(path.read_bytes() + b"\nmutation\n")
    result = check(verifier, export, tmp_path)
    assert not result["passed"]
    assert any(path.name in error for error in result["errors"]), result


def test_missing_external_dependency_names_the_path(verifier, export, tmp_path):
    (export / EXTERNAL / "A2.html").unlink()
    result = check(verifier, export, tmp_path)
    assert not result["passed"]
    assert any("A2.html" in error and "missing" in error for error in result["errors"])


@pytest.mark.parametrize("location", ["manifest", "source", "metadata", "extraction", "raw_tool"])
def test_path_traversal_is_rejected_before_open(verifier, export, tmp_path, location):
    if location == "manifest":
        path = export / REL / "manifest.json"
        doc = read(path)
        doc["files"][0]["path"] = "../../../../escape-secret.txt"
    elif location in {"source", "metadata"}:
        path = export / REL / "fuentes.json"
        doc = read(path)
        doc["sources"][0]["local_file" if location == "source" else "metadata_file"] = (
            "../../../../escape-secret.txt"
        )
    elif location == "raw_tool":
        path = export / REL / "fuentes.json"
        doc = read(path)
        next(s for s in doc["sources"] if s.get("raw_tool_records"))["raw_tool_records"] = [
            "../../../../escape-secret.txt"
        ]
    else:
        path = export / REL / "originales/SPOT26.meta.json"
        doc = read(path)
        doc["extraction"]["text_path"] = "../../../../escape-secret.txt"
    write(path, doc)
    result = check(verifier, export, tmp_path)
    assert not result["passed"]
    assert any("unsafe_path" in error for error in result["errors"]), result


def test_symlink_escape_is_rejected(verifier, export, tmp_path):
    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    member = export / REL / "README.md"
    member.unlink()
    try:
        member.symlink_to(outside)
    except OSError as exc:
        if sys.platform != "win32":
            pytest.skip(f"OS cannot create a symlink: {exc}")
        # Windows directory junctions need no symlink privilege and also escape resolve().
        junction = export / REL / "outside_junction"
        subprocess.run(["cmd", "/c", "mklink", "/J", str(junction), str(outside.parent)],
                       check=True, capture_output=True)
    result = check(verifier, export, tmp_path)
    assert not result["passed"]
    assert any("unsafe_path" in error for error in result["errors"]), result


def test_manifest_hash_cannot_be_reissued_to_hide_mutation(verifier, export, tmp_path):
    path = export / REL / "manifest.json"
    doc = read(path)
    doc["files"][0]["sha256"] = "0" * 64
    write(path, doc)
    result = check(verifier, export, tmp_path)
    assert not result["passed"]
    assert any("expected_manifest" in error for error in result["errors"])


def test_duplicate_coverage_detected_beyond_file_hash(verifier, export, tmp_path):
    path = export / REL / "cobertura.csv"
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    rows.append(copy.deepcopy(next(r for r in rows if r["status"] == "intervalo_respaldado")))
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0])
        writer.writeheader()
        writer.writerows(rows)
    result = check(verifier, export, tmp_path)
    assert not result["passed"]
    assert "coverage_double_count" in result["errors"]


@pytest.mark.parametrize("case, expected", [
    ("vip", "scope_mismatch"), ("market", "scope_mismatch"),
    ("rate", "rate_conversion"), ("no_data", "source_without_usable_data"),
    ("false_exact", "rollout_promoted_to_exact"),
    ("deduction", "derived_deduction"), ("margin", "tier_rate_conversion"),
])
def test_documentary_financial_rejections_and_equivalence(verifier, export, tmp_path, case, expected):
    path = export / REL / "reglas_historicas.json"
    doc = read(path)
    facts = {row["id"]: row for row in doc["facts"]}
    target = facts["FEE_A1_BTCUSDT"]
    if case == "vip":
        target["profile"]["vip"] = "VIP1"
    elif case == "market":
        target["market"] = "spot"
    elif case == "rate":
        target["value_normalized"] = "0.04"
    elif case == "no_data":
        facts["FEE_SPOT26_BTCUSDT"]["source_ids"] = ["SPOT25"]
    elif case == "false_exact":
        facts["EVENT_MINBTC26_BTCUSDT"]["temporal"].update(
            kind="exact_event", effective_at_utc="2026-04-14T06:30:00Z",
            earliest_utc=None, latest_utc=None,
        )
    elif case == "deduction":
        next(f for f in doc["facts"] if f["proof"].get("kind") == "derived_tiers")[
            "value_normalized"
        ][0] = "99"
    else:
        facts["TIERS_MARG23_BTCUSDT_after"]["value_normalized"][0]["maintenance_rate"] = "0.9"
    write(path, doc)
    sources = {s["id"]: s for s in read(export / REL / "fuentes.json")["sources"]}
    original = verifier.load_documentary_checks(export, export / REL)
    direct = original.validate_facts(doc, sources)
    assert any(expected in error for error in direct)
    result = check(verifier, export, tmp_path)
    assert not result["passed"]
    assert all(error in result["errors"] for error in direct)


def test_untrusted_original_script_never_executes(verifier, export, tmp_path):
    sentinel = tmp_path / "executed.txt"
    path = export / REL / "verificar_fuentes.py"
    path.write_text(f"open({str(sentinel)!r}, 'w').write('executed')", encoding="utf-8")
    result = check(verifier, export, tmp_path)
    assert not result["passed"]
    assert any("untrusted_original_verifier" in error for error in result["errors"])
    assert not sentinel.exists()


def test_output_is_new_and_cannot_be_inside_evidence(verifier, export, tmp_path):
    for target in [export / REL / "new.json", export / REL / "verificacion_resultados.json"]:
        run = subprocess.run([
            sys.executable, "-B", "-X", "utf8", str(SCRIPT), "--root", str(export),
            "--evidence", str(export / REL),
            "--temp-dir", str(tmp_path), "--output", str(target),
        ], capture_output=True, text=True, encoding="utf-8", check=False)
        assert run.returncode != 0
    output = tmp_path / "new_result.json"
    command = [sys.executable, "-B", "-X", "utf8", str(SCRIPT), "--root", str(export),
               "--evidence", str(export / REL), "--temp-dir", str(tmp_path), "--output", str(output)]
    first = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", check=False)
    assert first.returncode == 0, first.stderr + first.stdout
    assert json.loads(first.stdout) == read(output)
    before = output.read_bytes()
    second = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", check=False)
    assert second.returncode != 0
    assert output.read_bytes() == before


def test_later_unrelated_commit_and_code_change_preserve_published_provenance(verifier, tmp_path):
    clone = tmp_path / "clone"
    subprocess.run(["git", "clone", "--quiet", "--no-hardlinks", "--no-checkout", str(ROOT), str(clone)],
                   check=True, capture_output=True)
    subprocess.run(["git", "-C", str(clone), "-c", "core.autocrlf=false", "checkout", "--quiet", REFERENCE],
                   check=True, capture_output=True)
    (clone / "unrelated.txt").write_text("legitimate later work\n", encoding="utf-8")
    protected = read(clone / REL / "estado_inicial.json")["protected_files"]
    code = next(f["path"] for f in protected if f["path"].startswith("src/") and f["path"].endswith(".py"))
    with (clone / code).open("ab") as handle:
        handle.write(b"\n# legitimate later code evolution\n")
    subprocess.run(["git", "-C", str(clone), "add", "--", "unrelated.txt", code], check=True)
    subprocess.run(["git", "-C", str(clone), "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                    "commit", "--quiet", "-m", "Temporary acceptance fixture only"], check=True)
    before = snapshot(clone / REL)
    index = (clone / ".git/index").read_bytes()
    head = subprocess.check_output(["git", "-C", str(clone), "rev-parse", "HEAD"])
    result = check(verifier, clone, tmp_path)
    assert result["passed"], result
    assert result["provenance"]["git_status"] == "verified"
    assert result["provenance"]["protected_reference_paths"] == 717
    assert snapshot(clone / REL) == before
    assert (clone / ".git/index").read_bytes() == index
    assert subprocess.check_output(["git", "-C", str(clone), "rev-parse", "HEAD"]) == head
