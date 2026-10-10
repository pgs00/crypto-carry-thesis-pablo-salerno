"""Offline, read-only verification of the fixed historical-rules publication.

Only the standard library is imported. The original documentary functions are
compiled from authenticated bytes with a non-main module name, without pycache.
Current HEAD, branch, index and current trading code are not historical evidence.
"""

from __future__ import annotations

import argparse
import copy
import csv
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
from email.utils import parsedate_to_datetime
from pathlib import Path, PurePosixPath, PureWindowsPath
from types import SimpleNamespace

EVIDENCE_RELATIVE = "data/research/historical-rules-followup-20260924T234206Z"
PUBLICATION_COMMIT = "894059e4ce318e51f25211d04be9f0202de90ae7"
PARENT_COMMIT = "80feefc45872d2c48c33f3fbc3ebc9eb402eee6a"
ORIGINAL_SCRIPT_SHA256 = "36793185c648a6b2029a04a7c90f422f008b0d1e84f4333020bfc69cc30049fb"
MANIFEST_SHA256 = "629915f074a29fed6a7686e9b9af2a9279e0ff0601c1121c965c46539f5c99fb"
ARCHIVED_RESULTS = {
    "verificacion_resultados.json":
        "91363668ce7fc3167a8adc8270d21774e14914b4526ffdf9e600b997b98a0486",
    "verificacion_resultados.txt":
        "8dc1a506dcf57fffc31650261cafe878487cbbd395f85960a2fa6ba5f7f39308",
}
EXCLUDED = {"manifest.json", *ARCHIVED_RESULTS}
DATA_ERRORS = (OSError, ValueError, KeyError, TypeError, IndexError, ArithmeticError)


class VerificationError(ValueError):
    """An invalid documentary input, never a successful verification."""


def safe_path(base: Path, relative: str) -> Path:
    """Reject traversal, absolute/drive/ADS paths and resolved symlink escapes."""
    if not isinstance(relative, str) or not relative or "\\" in relative or ":" in relative:
        raise VerificationError(f"unsafe_path: {relative!r} (base {base})")
    parts = PurePosixPath(relative).parts
    if (PurePosixPath(relative).is_absolute() or PureWindowsPath(relative).drive
            or ".." in parts or "\x00" in relative):
        raise VerificationError(f"unsafe_path: {relative!r} (base {base})")
    path = base / relative
    if not path.resolve().is_relative_to(base.resolve()):
        raise VerificationError(f"unsafe_path: {path} resolves outside {base}")
    return path


def sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise VerificationError(f"invalid_json_or_missing: {path}: {exc}") from exc


def source_path(root: Path, evidence: Path, source: dict) -> Path:
    if source["local_base"] not in {"repository", "package"}:
        raise VerificationError(f"invalid_local_base: {source['id']}")
    return safe_path(root if source["local_base"] == "repository" else evidence,
                     source["local_file"])


def load_documentary_checks(root: Path, evidence: Path) -> SimpleNamespace:
    """Execute only the pinned script definitions; never run its main/self_tests."""
    path = safe_path(evidence, "verificar_fuentes.py")
    content = path.read_bytes()
    if hashlib.sha256(content).hexdigest() != ORIGINAL_SCRIPT_SHA256:
        raise VerificationError(f"untrusted_original_verifier: {path}")
    namespace = {"__name__": "sealed_documentary_checks", "__file__": str(path)}
    exec(compile(content, str(path), "exec", optimize=0), namespace)
    namespace.update(ROOT=root, B=evidence,
                     path_at=lambda source: source_path(root, evidence, source))
    return SimpleNamespace(**namespace)


def negative_checks(original, doc, sources, coverage):
    """Exercise the original financial/temporal checks using in-memory copies."""
    outcomes = []

    def trial(name, fact_id, field, value, expected, nested=None):
        copied = copy.deepcopy(doc)
        fact = next(f for f in copied["facts"] if f["id"] == fact_id)
        target = fact[nested] if nested else fact
        target[field] = value
        errors = original.validate_facts(copied, sources)
        outcomes.append({"test": name, "passed": any(expected in e for e in errors),
                         "expected_error": expected, "detected_errors": errors})

    trial("VIP", "FEE_A1_BTCUSDT", "vip", "VIP1", "scope_mismatch", "profile")
    trial("market", "FEE_A1_BTCUSDT", "market", "spot", "scope_mismatch")
    trial("uncertain_exact", "EVENT_MINBTC26_BTCUSDT", "kind", "exact_event",
          "rollout_promoted_to_exact", "temporal")
    trial("unproved_knowledge", "TIERS_MARG23_BTCUSDT_after", "known_from_utc",
          "2023-12-24T09:35:00Z", "publication_after_claimed_knowledge", "knowledge")
    trial("no_data", "FEE_SPOT26_BTCUSDT", "source_ids", ["SPOT25"],
          "source_without_usable_data")
    trial("unknown_zero", "PENDING_FEE_DATE_BTCUSDT", "value_normalized", "0",
          "unknown_as_number")
    trial("percent_conversion", "FEE_A1_BTCUSDT", "value_normalized", "0.04", "rate_conversion")
    trial("inverted_interval", "BTC_SPOT_ZERO", "valid_to_exclusive_utc",
          "2022-01-01T00:00:00Z", "inverted_interval", "temporal")
    copied = copy.deepcopy(doc)
    fact = copy.deepcopy(next(f for f in copied["facts"] if f["id"] == "BTC_SPOT_ZERO"))
    fact.update(id="CONTRADICTORY_TEST", value_original="0.1%", value_normalized="0.001",
                conversion={"percent": "0.1", "basis_points": "10"})
    copied["facts"].append(fact)
    errors = original.validate_facts(copied, sources)
    outcomes.append({"test": "contradictory_overlap", "passed": any(
        "contradictory_overlap" in e for e in errors), "detected_errors": errors})
    rows = copy.deepcopy(coverage)
    rows.append(copy.deepcopy(next(r for r in rows if r["status"] == "intervalo_respaldado")))
    errors, _ = original.validate_coverage(doc, rows)
    outcomes.append({"test": "duplicate_coverage", "passed": "coverage_double_count" in errors,
                     "detected_errors": errors})
    return outcomes


def _git(root, *args, check=True):
    return subprocess.run(
        ["git", "--no-optional-locks", "--no-replace-objects", "-C", str(root), *args],
        capture_output=True, check=check,
        env={**os.environ, "GIT_NO_LAZY_FETCH": "1", "GIT_TERMINAL_PROMPT": "0"},
    )


def _tree(root, reference):
    entries = {}
    for row in _git(root, "ls-tree", "-rz", reference).stdout.split(b"\0"):
        if row:
            info, path = row.split(b"\t", 1)
            mode, kind, oid = info.split()
            entries[path.decode("utf-8")] = (mode, kind, oid)
    return entries


def git_provenance(root, evidence, manifest, sources, baseline, errors):
    result = {"publication_commit": PUBLICATION_COMMIT, "parent_commit": PARENT_COMMIT,
              "expected_manifest_sha256": MANIFEST_SHA256, "git_status": "unchecked"}
    if not (root / ".git").exists() or not shutil.which("git"):
        result["reason"] = "No .git at explicit root or Git executable unavailable; content only."
        return result
    for reference in (PUBLICATION_COMMIT, PARENT_COMMIT):
        found = _git(root, "cat-file", "-e", reference + "^{commit}", check=False)
        if found.returncode:
            result["reason"] = f"Reference unavailable offline: {reference}"
            return result
    published, parent = _tree(root, PUBLICATION_COMMIT), _tree(root, PARENT_COMMIT)
    parents = _git(root, "rev-list", "--parents", "-n", "1", PUBLICATION_COMMIT).stdout.decode().split()
    if parents != [PUBLICATION_COMMIT, PARENT_COMMIT]:
        errors.append("publication_parent_mismatch")
    protected = baseline["protected_files"]
    for entry in protected:
        path = entry["path"]
        safe_path(root, path)
        if path not in parent or parent[path] != published.get(path):
            errors.append(f"protected_historical_blob_changed: {path}")
    result["protected_reference_paths"] = len(protected)
    result["protected_reference_method"] = "Parent/publication blob identity; current code is not compared."
    paths = {f"{EVIDENCE_RELATIVE}/{entry['path']}": safe_path(evidence, entry["path"])
             for entry in manifest["files"]}
    paths.update({f"{EVIDENCE_RELATIVE}/{name}": safe_path(evidence, name) for name in EXCLUDED})
    paths.update({s["local_file"]: source_path(root, evidence, s) for s in sources.values()
                  if s["local_base"] == "repository"})
    # Git's object ID is a hash of the complete blob bytes with its length header.
    # Compare every relevant published object, independently of checkout filters.
    count = 0
    for relative, path in paths.items():
        entry = published.get(relative)
        if not entry or entry[1] != b"blob" or entry[0] == b"120000":
            errors.append(f"published_blob_missing_or_symlink: {relative}")
            continue
        if not path.is_file():
            continue  # The documentary layer already reports the exact missing path.
        content = path.read_bytes()
        oid = hashlib.sha1(b"blob " + str(len(content)).encode() + b"\0" + content).hexdigest()
        if oid.encode() != entry[2]:
            errors.append(f"published_blob_mismatch: {relative}")
        count += 1
    result.update(git_status="verified" if not errors else "failed", compared_publication_blobs=count,
                  current_head=_git(root, "rev-parse", "HEAD").stdout.decode().strip())
    return result


def verify(*, root: Path, evidence: Path, temp_dir: Path) -> dict:
    """Return three separate audits. Never write evidence, Git state or temp files."""
    root, evidence, temp_dir = Path(root).resolve(), Path(evidence).resolve(), Path(temp_dir).resolve()
    errors = []
    result = {"schema": "historical_rules_publication_v1", "checked_at_utc":
              dt.datetime.now(dt.timezone.utc).isoformat(), "root": str(root), "evidence": str(evidence),
              "documentary_integrity": {"passed": False}, "provenance": {"git_status": "unchecked"},
              "original_session_audit": {"reproduced": False}, "negative_tests": [], "errors": errors,
              "interpretation_limit": "Hashes and documentary checks do not certify first publication "
              "or historical continuity. The original physical Git index is not reconstructed."}
    try:
        if not evidence.is_relative_to(root):
            raise VerificationError(f"unsafe_path: evidence {evidence} outside root {root}")
        if not temp_dir.is_dir() or temp_dir.is_relative_to(evidence):
            raise VerificationError(f"unsafe_temp_dir: {temp_dir}; use an existing directory outside evidence")
        manifest_path = safe_path(evidence, "manifest.json")
        manifest = read_json(manifest_path)
        if sha256(manifest_path) != MANIFEST_SHA256:
            errors.append(f"expected_manifest_hash_mismatch: {manifest_path}")
        if manifest["schema"] != "byte_manifest_v1" or set(manifest["exclusions"]) != EXCLUDED:
            errors.append("manifest_schema_or_exclusions_mismatch")
        names = [entry["path"] for entry in manifest["files"]]
        if len(names) != len(set(names)):
            errors.append("duplicate_manifest_path")

        def file_check(path, expected_hash, size=None):
            if not path.is_file():
                errors.append(f"missing_file: {path}")
            elif ((size is not None and path.stat().st_size != size)
                  or sha256(path) != expected_hash):
                errors.append(f"file_hash_or_size_mismatch: {path}")

        for entry in manifest["files"]:
            file_check(safe_path(evidence, entry["path"]), entry["sha256"], entry["bytes"])
        actual = set()
        for path in evidence.rglob("*"):
            relative = path.relative_to(evidence).as_posix()
            safe_path(evidence, relative)
            if path.is_file() and relative not in EXCLUDED:
                actual.add(relative)
        if actual != set(names):
            errors.append(f"manifest_file_set_mismatch: extra={sorted(actual-set(names))}; "
                          f"missing={sorted(set(names)-actual)}")
        for name, expected_hash in ARCHIVED_RESULTS.items():
            file_check(safe_path(evidence, name), expected_hash)
        original = load_documentary_checks(root, evidence)
        source_doc = read_json(safe_path(evidence, "fuentes.json"))
        sources = {s["id"]: s for s in source_doc["sources"]}
        if len(sources) != len(source_doc["sources"]):
            errors.append("duplicate_source_id")
        for source in sources.values():
            path = source_path(root, evidence, source)
            file_check(path, source["sha256"], source["bytes"])
            for relative in source.get("raw_tool_records", []):
                raw_path = safe_path(evidence, relative)
                if relative not in names or not raw_path.is_file():
                    errors.append(f"missing_or_uncatalogued_raw_tool_record: {raw_path}")
            if source.get("metadata_file"):
                metadata_path = safe_path(evidence, source["metadata_file"])
                metadata = read_json(metadata_path)
                if metadata["sha256"] != source["sha256"] or metadata["final_url"] != source["final_url"]:
                    errors.append(f"source_metadata_mismatch: {metadata_path}")
                if source["capture_utc"]:
                    headers = {k.lower(): v for k, v in metadata["headers"].items()}
                    captured = parsedate_to_datetime(headers["memento-datetime"])
                    match = re.search(r"/web/(\d{14})", source["final_url"])
                    if (captured.isoformat().replace("+00:00", "Z") != source["capture_utc"]
                            or not match or captured.strftime("%Y%m%d%H%M%S") != match[1]):
                        errors.append(f"memento_url_mismatch: {metadata_path}")
                if metadata.get("extraction"):
                    extraction = metadata["extraction"]
                    file_check(safe_path(evidence, extraction["text_path"]), extraction["text_sha256"])
            if source["type"] == "archive_index" and path.is_file():
                if not all(isinstance(row, list) and len(row) == 5 for row in read_json(path)):
                    errors.append(f"cdx_unhandled_pagination: {path}")
        doc = read_json(safe_path(evidence, "reglas_historicas.json"))
        if doc.get("loadable_by_rulebook") is not False:
            errors.append("registry_must_remain_nonloadable")
        errors.extend(original.validate_facts(doc, sources))
        with safe_path(evidence, "cobertura.csv").open(encoding="utf-8", newline="") as handle:
            coverage = list(csv.DictReader(handle))
        coverage_errors, result["coverage"] = original.validate_coverage(doc, coverage)
        errors.extend(coverage_errors)
        # Original covered-interval duplicate check is preserved; also reject duplicate zero-day rows.
        if len({tuple(row.items()) for row in coverage}) != len(coverage):
            errors.append("duplicate_coverage_row")
        # Corrupt inputs already fail: do not use them as fixtures for self-tests.
        if not errors:
            result["negative_tests"] = negative_checks(original, doc, sources, coverage)
        errors.extend("negative_test_failed: " + row["test"] for row in result["negative_tests"]
                      if not row["passed"])
        result["documentary_integrity"].update(passed=not errors, manifest_members=len(names),
                                               sources=len(sources), facts=len(doc["facts"]),
                                               coverage_rows=len(coverage))
        baseline = read_json(safe_path(evidence, "estado_inicial.json"))
        archived = read_json(safe_path(evidence, "verificacion_resultados.json"))
        result["original_session_audit"].update(
            recorded_at_utc=archived["checked_at_utc"], recorded_passed=archived["passed"],
            recorded_head=archived["head"], recorded_index_sha256=baseline["git_index_sha256"],
            original_results_sha256=ARCHIVED_RESULTS["verificacion_resultados.json"],
            statement="Archived record only; current index/branch/HEAD are not compared to that session.",
        )
        if baseline["head"] != PARENT_COMMIT or archived["manifest_sha256"] != MANIFEST_SHA256:
            errors.append("original_session_reference_mismatch")
        git_errors = []
        result["provenance"] = git_provenance(root, evidence, manifest, sources, baseline, git_errors)
        errors.extend(git_errors)
    except DATA_ERRORS as exc:
        errors.append(f"{type(exc).__name__}: {exc}")
    except subprocess.CalledProcessError as exc:
        errors.append(f"git_command_failed: {exc.cmd}: {exc.stderr.decode('utf-8', errors='replace')}")
    result["passed"] = not errors
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--evidence", required=True, type=Path)
    parser.add_argument("--temp-dir", required=True, type=Path,
                        help="Existing directory outside evidence; checks currently need no temp files.")
    parser.add_argument("--output", type=Path, help="Optional NEW JSON file outside evidence (exclusive create).")
    args = parser.parse_args(argv)
    if args.output:
        output = args.output.resolve()
        if output.is_relative_to(args.evidence.resolve()) or output.exists():
            parser.error(f"Output must be a NEW path outside evidence: {output}")
    result = verify(root=args.root, evidence=args.evidence, temp_dir=args.temp_dir)
    serialized = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        with args.output.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(serialized)
    print(serialized, end="")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
