"""Mutate real bytes/cells in one isolated copy, then invoke the full verifier."""

import argparse
import json
import shutil
import subprocess
import sys
import time
from decimal import Decimal as D
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
sys.dont_write_bytecode = True

import pyarrow as pa  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402

from scripts.package_stress_counterfactual import no_links  # noqa: E402
from scripts.return_capital.common import read_json, sha256, write_json  # noqa: E402
from scripts.stress_counterfactual_audit import record_digest  # noqa: E402
from scripts.stress_counterfactual_delivery import bytes_hash, table_digest  # noqa: E402

CASES = ("approved_protocol", "redirected_run", "false_technical_label", "altered_fill_cell",
         "refreshed_intervention_price", "omitted_minute_snapshot", "omitted_h3_witness",
         "future_availability", "h3_aggregate", "refreshed_report_metrics")


class Mutation:
    def __init__(self, package):
        self.package = package
        self.before = {}

    def write(self, path, content):
        path = path.resolve()
        if not path.is_relative_to(self.package.resolve()) or not path.is_file():
            raise ValueError("Mutation must overwrite an existing file inside the isolated copy")
        self.before.setdefault(path, path.read_bytes())
        path.write_bytes(content)

    def json(self, path, value):
        self.write(path, (json.dumps(value, indent=2, ensure_ascii=False, default=str) + "\n").encode())

    def parquet(self, path, rows, schema):
        stream = pa.BufferOutputStream()
        pq.write_table(pa.Table.from_pylist(rows, schema=schema), stream, compression="zstd")
        self.write(path, stream.getvalue().to_pybytes())
        if pq.ParquetFile(path).read().schema != schema:
            raise ValueError("Tamper construction changed Parquet schema")

    def reseal_copy(self):
        manifest = self.package / "manifiesto_paquete.json"
        if not manifest.exists():
            return
        value = read_json(manifest)
        for member in value["members"]:
            path = self.package / member["path"]
            member.update(sha256=sha256(path), bytes=path.stat().st_size)
        self.json(manifest, value)
        self.write(self.package / "manifiesto_paquete.sha256", (sha256(manifest) + "\n").encode())

    def proof(self, destination):
        proof = []
        for path, old in self.before.items():
            current = path.read_bytes()
            if current == old:
                continue
            relative = path.relative_to(self.package)
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(current)
            proof.append(dict(path=relative.as_posix(), before_sha256=bytes_hash(old),
                after_sha256=bytes_hash(current), before_bytes=len(old), after_bytes=len(current),
                retained_mutated_bytes=str(target)))
        if not proof:
            raise ValueError("No bytes changed; not a valid negative test")
        return proof

    def restore(self):
        for path, value in self.before.items():
            path.write_bytes(value)
            if path.read_bytes() != value:
                raise ValueError("Isolated-copy restoration failed")


def economic_item(package):
    batch = read_json(package / "indice_corridas.json")
    return batch, next(r for r in batch["runs"] if r["scenario"] == "SH_P90" and r["strategy"] == "conditional")


def refresh_journal(mutation, item, batch, changed):
    package = mutation.package
    folder = package / "intervenciones" / item["run_id"]
    path = folder / "manifiesto_evidencia.json"
    manifest = read_json(path)
    for name in changed:
        manifest["files"][name] = sha256(folder / name)
    mutation.json(path, manifest)
    item["evidence_manifest_sha256"] = sha256(path)
    mutation.json(package / "indice_corridas.json", batch)
    provenance = package / "evidencia_mercado/testigos" / (item["run_id"] + ".json")
    value = read_json(provenance)
    value["evidence_manifest_sha256"] = item["evidence_manifest_sha256"]
    mutation.json(provenance, value)


def mutate(case, mutation):
    package = mutation.package
    if case == "approved_protocol":
        path = package / "protocolo_tecnico.md"
        mutation.write(path, path.read_bytes() + b"\nChanged test protocol.\n")
        return "approved bytes changed, outer seal refreshed only"
    if case == "refreshed_report_metrics":
        path = package / "resultados/metricas.parquet"
        original = pq.ParquetFile(path).read()
        rows = original.to_pylist()
        row = next(r for r in rows if r["scenario"] == "SH_P90" and r["strategy"] == "conditional" and r["period"] == "full")
        row["final_equity_usdt"] = str(D(row["final_equity_usdt"]) + 1)
        row["net_pnl_usdt"] = str(D(row["net_pnl_usdt"]) + 1)
        mutation.parquet(path, rows, original.schema)
        catalogue = package / "resultados/catalogo.json"
        value = read_json(catalogue)
        value["metricas"]["semantic_sha256"] = table_digest(rows)
        mutation.json(catalogue, value)
        # Keep its CSV self-consistent, so recomputation is what rejects it.
        import csv
        import io
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        mutation.write(package / "resultados/metricas.csv", stream.getvalue().encode())
        return "valid typed financial cells, CSV and catalog refreshed"
    batch, item = economic_item(package)
    if case == "redirected_run":
        item["path"] = next(r["path"] for r in batch["runs"] if r["scenario"] == "BASE_E3")
        mutation.json(package / "indice_corridas.json", batch)
        return "index points to another existing authenticated directory"
    if case == "false_technical_label":
        item["technical_control"] = True
        mutation.json(package / "indice_corridas.json", batch)
        return "economic scenario falsely excluded as technical"
    if case == "altered_fill_cell":
        path = package / item["path"] / "fills.parquet"
        original = pq.ParquetFile(path).read()
        rows = original.to_pylist()
        rows[0]["price"] = str(D(rows[0]["price"]) + 1)
        mutation.parquet(path, rows, original.schema)
        return "real price cell changed with original Parquet schema; inner original manifest preserved"
    folder = package / "intervenciones" / item["run_id"]
    if case == "refreshed_intervention_price":
        name = "intervenciones.parquet"
        path = folder / name
        original = pq.ParquetFile(path).read()
        rows = original.to_pylist()
        value = json.loads(rows[0]["modified_json"])
        value["close"] = str(D(value["close"]) + D(".01"))
        rows[0]["modified_json"] = json.dumps(value, sort_keys=True)
        rows[0]["modified_record_sha256"] = record_digest(value)
        mutation.parquet(path, rows, original.schema)
        changed = [name]
    elif case == "omitted_minute_snapshot":
        name = "observaciones_ventanas.parquet"
        path = folder / name
        original = pq.ParquetFile(path).read()
        rows = original.to_pylist()
        position = next(i for i, r in enumerate(rows) if int(r["time_ns"]) % 60_000_000_000 == 0)
        rows.pop(position)
        mutation.parquet(path, rows, original.schema)
        state_path = folder / "estado_capa.json"
        state = read_json(state_path)
        state["observation_rows"] = len(rows)
        mutation.json(state_path, state)
        changed = [name, "estado_capa.json"]
    elif case in ("omitted_h3_witness", "future_availability"):
        name = "oportunidad_ventanas.parquet"
        path = folder / name
        original = pq.ParquetFile(path).read()
        rows = original.to_pylist()
        if case == "omitted_h3_witness":
            rows.pop(0)
        else:
            value = json.loads(rows[0]["evidence_json"])
            value["future_bar"]["available_at"] = int(value["time_ns"]) + 1
            rows[0]["evidence_json"] = json.dumps(value, sort_keys=True)
        mutation.parquet(path, rows, original.schema)
        changed = [name]
    elif case == "h3_aggregate":
        import csv
        import io
        name = "h3_minutos/" + item["run_id"] + ".csv"
        path = folder / name
        rows = list(csv.DictReader(io.StringIO(path.read_text(encoding="utf-8"))))
        row = next(r for r in rows if int(r["minutos_elegibles"]) > 0)
        row["suma_forecast_elegible"] = str(D(row["suma_forecast_elegible"]) + D(".001"))
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        mutation.write(path, stream.getvalue().encode())
        changed = [name]
    else:
        raise ValueError("Unknown negative-test case")
    refresh_journal(mutation, item, batch, changed)
    return "valid changed cells/row population; journal hashes and identity references refreshed in test copy"


def invoke_included_verifier(package, output, log):
    command = [sys.executable, "-I", "-B", "-X", "utf8",
               str(package / "herramientas/scripts/check_stress_verifier_case.py"),
               str(package), "--output", str(output)]
    with log.open("x", encoding="utf-8") as stream:
        checked = subprocess.run(command, cwd=output.parent, stdout=stream,
                                 stderr=subprocess.STDOUT, check=False)
    if checked.returncode != 0 or not output.is_file():
        raise RuntimeError("Included verifier process failed; not a valid rejection: " + str(log))
    result = read_json(output)
    expected_source = package / "herramientas/scripts/verify_stress_counterfactual.py"
    if (result.get("schema") != "stress_verifier_attempt_v1"
            or result.get("verifier_invoked") is not True or result.get("python_isolated") is not True
            or Path(result["verifier_file"]).resolve() != expected_source.resolve()
            or result["verifier_sha256"] != sha256(expected_source)
            or type(result["passed"]) is not bool or type(result["rejected"]) is not bool
            or result["passed"] == result["rejected"]):
        raise RuntimeError("Invalid included-verifier attempt record; not a valid rejection")
    return result, command


def run(source, destination, cases):
    if destination.exists() or destination.resolve().is_relative_to(source.resolve()):
        raise ValueError("Use a new isolated destination outside the original evidence")
    no_links(source)
    destination.mkdir(parents=True)
    copy = destination / "paquete_prueba"
    shutil.copytree(source, copy)
    # The same real isolated copy first proves portability in an isolated Python
    # process; no second full test package is needed for the mutations below.
    portable_output = destination / "verificacion_portable.json"
    baseline, command = invoke_included_verifier(copy, portable_output, destination / "verificacion_portable.txt")
    if not baseline["passed"] or baseline["rejected"]:
        raise ValueError("Included tools did not verify the isolated unmodified copy")
    portable = dict(passed=True, isolated_python=True, working_directory=str(destination),
                    command=command, output_sha256=sha256(portable_output),
                    original_checkout_or_data_arguments=False)
    write_json(destination / "portabilidad.json", portable)
    print("PORTABLE VERIFIED", str(copy), flush=True)
    original_seal = sha256(source / "manifiesto_paquete.json") if (source / "manifiesto_paquete.json").exists() else None
    records = []
    for case in cases:
        mutation = Mutation(copy)
        result = dict(case=case, construction_passed=False, bytes_changed=False, verifier_invoked=False, rejected=False)
        start = time.perf_counter()
        try:
            result["construction"] = mutate(case, mutation)
            mutation.reseal_copy()
            result["changed_files"] = mutation.proof(destination / "evidencia_adulterada" / case)
            result.update(construction_passed=True, bytes_changed=True)
            write_json(destination / (case + "_construction.json"), result)
            # Construction exceptions are deliberately outside this rejection handler.
            attempted, case_command = invoke_included_verifier(copy,
                destination / (case + "_verifier.json"), destination / (case + "_verifier.txt"))
            result["verifier_invoked"] = attempted["verifier_invoked"]
            result["verifier_command"] = case_command
            result["verifier_attempt_sha256"] = sha256(destination / (case + "_verifier.json"))
            if attempted["rejected"]:
                result.update(rejected=True, rejection_type=attempted["rejection_type"], reason=attempted["reason"])
            if not result["rejected"]:
                raise AssertionError("Verifier accepted the constructed tamper: " + case)
        finally:
            mutation.restore()
            result["seconds"] = time.perf_counter() - start
            write_json(destination / (case + "_result.json"), result)
        records.append(result)
        print("REJECTED", case, result["reason"], flush=True)
    if original_seal is not None and sha256(source / "manifiesto_paquete.json") != original_seal:
        raise ValueError("Original seal changed during isolated tests")
    final = dict(passed=all(r["construction_passed"] and r["bytes_changed"] and r["verifier_invoked"] and r["rejected"] for r in records),
        cases=records, original_package=str(source), isolated_copy=str(copy), original_seal_sha256=original_seal,
        original_files_modified=False, full_verifier_called_each_case=True,
        portable_verification=portable,
        construction_errors_are_not_rejections=True, restored_copy_preserved=True)
    write_json(destination / "pruebas_negativas.json", final)
    return final


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--cases", nargs="+", choices=CASES, default=list(CASES))
    args = parser.parse_args()
    result = run(args.source.resolve(), args.destination.resolve(), args.cases)
    print(json.dumps(dict(passed=result["passed"], cases=len(result["cases"]))))


if __name__ == "__main__":
    main()
