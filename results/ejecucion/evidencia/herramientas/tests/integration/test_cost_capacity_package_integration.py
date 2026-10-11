"""Artifact integration: corrupt disposable copies and renew affected hashes."""

import csv
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

PACKAGE = os.environ.get("COST_CAPACITY_PACKAGE")
pytestmark = pytest.mark.skipif(not PACKAGE, reason="requires COST_CAPACITY_PACKAGE sealed 18-result artifact")


def read(path):
    return json.loads(path.read_text(encoding="utf8"))


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+"\n", encoding="utf8")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def csv_change(path, field, value):
    with path.open(encoding="utf8", newline="") as f:
        reader = csv.DictReader(f)
        fields, rows = reader.fieldnames, list(reader)
    rows[0][field] = value
    with path.open("w", encoding="utf8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def rehash(package, run=None):
    if run:
        manifest = read(run/"run_manifest.json")
        for name in manifest["output_hashes"]:
            if (run/name).is_file():
                manifest["output_hashes"][name] = sha(run/name)
        save(run/"run_manifest.json", manifest)
        digest = sha(run/"run_manifest.json")
        (run/"run_manifest.sha256").write_text(digest+"\n", encoding="ascii")
        index = read(package/"indice_corridas.json")
        for item in index["runs"]:
            if item["run_id"] == run.name:
                item["manifest_sha256"] = digest
        save(package/"indice_corridas.json", index)
        originals = package/"fuentes/archivos_originales.csv"
        with originals.open(encoding="utf8",newline="") as f:
            reader=csv.DictReader(f)
            fields, rows=reader.fieldnames,list(reader)
        for row in rows:
            if row["run_id"] == run.name:
                target=package/row["package_path"]
                row.update(sha256=sha(target),bytes=str(target.stat().st_size))
                if row.get("transfer") == "exact_bytes" and "source_sha256" in row:
                    row.update(source_sha256=sha(target), source_bytes=str(target.stat().st_size))
        with originals.open("w",encoding="utf8",newline="") as f:
            writer=csv.DictWriter(f,fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
    seal = read(package/"manifiesto_paquete.json")
    for item in seal["members"]:
        path = package/item["path"]
        item.update(bytes=path.stat().st_size, sha256=sha(path))
    save(package/"manifiesto_paquete.json", seal)
    (package/"manifiesto_paquete.sha256").write_text(sha(package/"manifiesto_paquete.json")+"\n", encoding="ascii")


@pytest.mark.parametrize("mutation,expected", [
    ("configuration", "configuration"), ("participation", "configuration"),
    ("fee", "Scenario fee"), ("selection", "Selection threshold"),
    ("quantity", "quantity"), ("denominator", "VWAP reference"),
    ("period", "period denominator"), ("h2", "H2"), ("h3", "H3 contract"),
    ("ledger_cash", "Ledger flow"), ("late_order", "Order window"),
])
def test_semantic_corruption_after_hash_renewal(tmp_path, mutation, expected):
    package = tmp_path/"discardable"
    shutil.copytree(Path(PACKAGE), package)
    index = read(package/"indice_corridas.json")
    item = next(r for r in index["runs"] if r["scenario"]=="C02" and r["strategy"]=="conditional")
    run = package/item["path"]
    changed_run = None
    if mutation in {"configuration", "participation"}:
        path=run/"effective_config.toml"
        field = "cost_multiplier" if mutation=="configuration" else "max_volume_participation"
        lines=path.read_text(encoding="utf8").splitlines()
        path.write_text("\n".join(f'{field} = "0.123"' if line.startswith(field+' =') else line for line in lines)+"\n",encoding="utf8")
        changed_run=run
    elif mutation in {"fee", "quantity", "selection", "ledger_cash", "late_order"}:
        filename = ("signals" if mutation=="selection" else "ledger" if mutation=="ledger_cash"
                    else "orders" if mutation=="late_order" else "fills")+".parquet"
        path=run/filename
        source=pq.read_table(path)
        rows=source.to_pylist()
        field,value={"fee":("fee_rate",".009"),"quantity":("quantity","999999"),
                     "selection":("estimated_cycle_cost",".009"),
                     "ledger_cash":("cash_spot_change","123456789"),
                     "late_order":("submitted_at",None)}[mutation]
        target=next(r for r in rows if r.get(field) is not None)
        if mutation=="late_order":
            for row in rows:
                if row["order_id"]==target["order_id"]:
                    row[field]=str(int(row["window_end"])+1) if isinstance(row[field],str) else int(row["window_end"])+1
        else:
            target[field]=value
        pq.write_table(pa.Table.from_pylist(rows,schema=source.schema),path)
        changed_run=run
    elif mutation=="denominator":
        path=package/"fuentes/volumen"/(run.name+".json")
        rows=read(path)
        fill=pq.read_table(run/"fills.parquet").to_pylist()[0]
        target=next(r for r in rows if (r["symbol"],r["market"],int(r["open_time"])) == (fill["symbol"],fill["market"],int(fill["window_start"])))
        target["base_volume"]="1"
        save(path,rows)
    elif mutation=="period":
        csv_change(package/"tablas/metricas.csv","days","999")
    elif mutation=="h2":
        csv_change(package/"tablas/h2.csv","verdict","invented")
    elif mutation=="h3":
        csv_change(package/"tablas/h3_resumen.csv","h3_descriptive","invented")
    rehash(package,changed_run)
    result=subprocess.run([sys.executable,"-B","-X","utf8",str(package/"herramientas/scripts/verify_cost_capacity.py"),
        "--package",str(package),"--output",str(tmp_path/"audit.json")],cwd=tmp_path,capture_output=True,text=True,
        encoding="utf8",env={**os.environ,"PYTHONPATH":"","PYTHONDONTWRITEBYTECODE":"1"},
        creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0),timeout=240)
    assert result.returncode != 0
    assert expected.lower() in (result.stdout+result.stderr).lower(), result.stdout+result.stderr
    assert not (tmp_path/"audit.json").exists()
