"""Relocate sealed inputs and reject rehashed semantic corruptions in owned temporaries."""

import argparse
import csv
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path


def sha(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def verify_command(package, parent, cwd):
    command = [sys.executable, "-B", "-X", "utf8",
               str(package / "herramientas/verify_rules_sensitivity_correction.py"),
               "--package", str(package), "--parent", str(parent)]
    started = time.monotonic()
    result = subprocess.run(command, cwd=cwd, capture_output=True, encoding="utf-8")
    return dict(command=command, cwd=str(cwd), exit_code=result.returncode,
                elapsed_seconds=time.monotonic()-started,
                result=json.loads(result.stdout), stderr=result.stderr)


def reseal_fixture(package):
    """Only a disposable test copy: source and final seals must never be changed."""
    path = package / "manifiesto_paquete.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    for member in manifest["members"]:
        target = package / member["path"]
        member.update(size=target.stat().st_size, sha256=sha(target))
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (package / "manifiesto_paquete.sha256").write_text(sha(path) + "\n", encoding="ascii")


def alter_csv(package, name, column, mode, selector=None):
    target = package / "comparacion" / name
    with target.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fields, rows = reader.fieldnames, list(reader)
    row = next((row for row in rows if selector and selector(row)), rows[0])
    before = row[column]
    if mode == "add_one":
        row[column] = str(Decimal(before) + 1)
    elif mode == "subtract_ns":
        row[column] = str(int(before) - 1)
    elif mode == "flip":
        row[column] = "False" if before == "True" else "True"
    else:
        row[column] = mode
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return dict(table=name, column=column, before=before, after=row[column])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--parent", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    package, parent = args.package.resolve(), args.parent.resolve()
    if args.output.exists() or any(args.output.resolve().is_relative_to(p) for p in (package, parent)):
        raise ValueError("Use a NEW external audit output")
    original_hashes = dict(correction=sha(package / "manifiesto_paquete.json"),
                           parent=sha(parent / "manifiesto_paquete.json"))
    record = dict(started_at=datetime.now(UTC).isoformat(), original_manifest_hashes=original_hashes)
    # Both roots are moved for this one portability audit; copies are not deliverables.
    with tempfile.TemporaryDirectory(prefix="e4_rules_portability_") as directory:
        work = Path(directory).resolve()
        if not work.is_relative_to(Path(tempfile.gettempdir()).resolve()):
            raise ValueError("Owned temporary escapes the intended temporary root")
        copied = work / "correction relocated"
        copied_parent = work / "parent relocated"
        shutil.copytree(package, copied)
        shutil.copytree(parent, copied_parent)
        before_files = {p.relative_to(copied).as_posix(): sha(p)
                        for p in copied.rglob("*") if p.is_file()}
        positive = verify_command(copied, copied_parent, work)
        after_files = {p.relative_to(copied).as_posix(): sha(p)
                       for p in copied.rglob("*") if p.is_file()}
        positive["correction_bytes_unchanged"] = before_files == after_files
        if positive["exit_code"] != 0 or not positive["correction_bytes_unchanged"]:
            raise ValueError(f"Relocated verification failed: {positive}")
        record["relocated_verification"] = positive
        print("Relocated correction AND parent: passed, no Git or source-root dependency", flush=True)
        cases = [
            ("interval_boundary", "exposicion_intervalos.csv", "end_ns", "subtract_ns", None, "interval"),
            ("interval_classification", "exposicion_intervalos.csv", "exposure", "unhedged",
             lambda row: row["exposure"] == "dust", "interval"),
            ("interval_duration", "exposicion_intervalos.csv", "seconds", "add_one", None, "interval"),
            ("summary_duration", "exposicion_periodo.csv", "invested_seconds", "add_one", None, "summary"),
            ("h2_condition", "h2.csv", "cagr_positive", "flip", None, "cagr_positive"),
            ("comparison_number", "antes_despues.csv", "invested_fraction", "add_one", None, "before/after"),
            ("figure_source_number", "figuras/exposicion_datos.csv", "raw_invested_fraction", "add_one", None, "figure"),
            ("financial_value", "metricas_cartera_periodo.csv", "final_equity_usdt", "add_one", None, "financial preservation"),
        ]

        def check_case(case):
            name, table, column, mode, selector, expected = case
            clone = work / name
            shutil.copytree(copied, clone)
            mutation = alter_csv(clone, table, column, mode, selector)
            reseal_fixture(clone)
            result = verify_command(clone, copied_parent, work)
            detected = (result["exit_code"] == 1 and result["result"].get("status") == "failed"
                        and expected.lower() in result["result"].get("error", "").lower())
            print(f"{name}: {'detected' if detected else 'FAILED'}", flush=True)
            return dict(name=name, detected=detected, mutation=mutation,
                        test_manifest_rehashed=True, expected_error_contains=expected, **result)

        with ThreadPoolExecutor(max_workers=2) as pool:
            record["semantic_corruptions"] = list(pool.map(check_case, cases))
        # TemporaryDirectory removes only this verified, task-owned absolute root.
        if not work.resolve().is_relative_to(Path(tempfile.gettempdir()).resolve()):
            raise ValueError("Refuse cleanup outside the owned temporary root")
    record["temporary_copies_removed"] = not work.exists()
    record["original_manifest_hashes_after"] = dict(
        correction=sha(package / "manifiesto_paquete.json"), parent=sha(parent / "manifiesto_paquete.json"))
    record["original_manifests_unchanged"] = original_hashes == record["original_manifest_hashes_after"]
    record["status"] = "passed" if (all(r["detected"] for r in record["semantic_corruptions"])
                                         and record["original_manifests_unchanged"]
                                         and record["temporary_copies_removed"]) else "failed"
    record["ended_at"] = datetime.now(UTC).isoformat()
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(record, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps(dict(status=record["status"], corruption_cases=len(cases),
                          output=str(args.output)), ensure_ascii=False))
    return 0 if record["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
