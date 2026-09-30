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

PACKAGE = os.environ.get("EXECUTION_DELAYS_PACKAGE")
pytestmark = pytest.mark.skipif(not PACKAGE, reason="requires EXECUTION_DELAYS_PACKAGE sealed 14-result artifact")


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
    ("configuration", "configuration"), ("reference", "Selected reference"),
    ("delay", "execution metadata"), ("purpose", "causal"),
    ("window", "window"), ("quantity", "quantity"), ("volume", "Unmodified VWAP"),
    ("fee", "Scenario fee"), ("sequence", "sequence"),
    ("cancel_then_fill", "sequence"), ("early_expiration", "deadline"),
    ("fill_metadata", "timestamp"), ("period", "period denominator"),
    ("h2", "H2"), ("h3", "H3 contract"),
    ("ledger_cash", "Ledger flow"), ("incident", "incidentes_resumen"),
    ("parquet_result", "Parquet table metricas"),
    ("control_duplicate", "control strategy coverage"),
    ("base_manifest", "Preserved BASE"),
    ("control_sequence", "Complete BASE controls"),
    ("catalog_missing", "transfer catalog"),
    ("catalog_label", "transfer catalog"),
    ("h1_missing", "Reused H1/H3 population"),
])
def test_semantic_corruption_with_renewed_hashes(tmp_path,mutation,expected):
    package=tmp_path/'discardable'
    shutil.copytree(Path(PACKAGE),package)
    index=read(package/'indice_corridas.json')
    # Earliest variant so all failures exercise packaged code without stale imports.
    item=next(r for r in index['runs'] if r['scenario']=='E_OHLC4' and r['strategy']=='conditional')
    run=package/item['path']
    changed=None

    def alter(name,callback):
        path=run/(name+'.parquet')
        source=pq.read_table(path)
        rows=source.to_pylist()
        callback(rows)
        # Persist the intended corruption in the actual physical artifact schema.
        # Native execution metadata such as delay/sequence is stored as text.
        for field in source.schema:
            if pa.types.is_string(field.type):
                for row in rows:
                    if row.get(field.name) is not None:
                        row[field.name]=str(row[field.name])
        pq.write_table(pa.Table.from_pylist(rows,schema=source.schema),path)
        assert pq.read_table(path).to_pylist()!=source.to_pylist(), 'Mutation did not change persisted records'

    if mutation=='configuration':
        path=run/'effective_config.toml'
        path.write_text(path.read_text(encoding='utf8').replace('research_execution_delay_seconds = 0',
                        'research_execution_delay_seconds = 60'),encoding='utf8')
        changed=run
    elif mutation in {'reference','delay','quantity','fee','fill_metadata'}:
        field,value={'reference':('reference_price','1'),'delay':('delay_applied_seconds',999),
            'quantity':('quantity','999999'),'fee':('fee_rate','.009'),
            'fill_metadata':('fill_at',1)}[mutation]
        alter('fills',lambda rows:rows[0].update({field:value}))
        changed=run
    elif mutation=='sequence':
        def reverse(rows):
            pair=next((i for i in range(len(rows)-1) if rows[i]['time_ns']==rows[i+1]['time_ns']),None)
            assert pair is not None,'Need actual simultaneous fills for this attack'
            rows[pair],rows[pair+1]=rows[pair+1],rows[pair]
            for i,row in enumerate(rows):
                row['fill_sequence']=i
        alter('fills',reverse)
        changed=run
    elif mutation=='purpose':
        orders=pq.read_table(run/'orders.parquet').to_pylist()
        target=next(r for r in orders if r.get('action')=='submitted' and r['purpose']=='open_spot')
        def change_purpose(rows):
            for row in rows:
                if row['order_id']==target['order_id']:
                    row['purpose']='increase_spot'
        alter('orders',change_purpose)
        alter('fills',change_purpose)
        changed=run
    elif mutation in {'window','cancel_then_fill','early_expiration'}:
        def change_order(rows):
            if mutation=='window':
                rows[0]['window_start']+=1
            elif mutation=='cancel_then_fill':
                row=next(r for r in rows if r.get('action') in ('filled','partial_fill'))
                row.update(action='fabricated_cancellation',status='cancelled')
            else:
                row=next(r for r in rows if r.get('action')=='timeout')
                row['time_ns']-=60_000_000_000
                row['expired_at']=row['time_ns']
                events=sorted((r for r in rows if r['record_type']=='event'),
                              key=lambda r:(r['time_ns'],int(r['event_sequence'])))
                for i,event in enumerate(events):
                    event['event_sequence']=i
                rows[:]=events+[r for r in rows if r['record_type']!='event']
        alter('orders',change_order)
        changed=run
    elif mutation=='volume':
        path=package/'fuentes/volumen'/(run.name+'.json')
        rows=read(path)
        fill=pq.read_table(run/'fills.parquet').to_pylist()[0]
        row=next(r for r in rows if (r['symbol'],r['market'],r['open_time'])==
            (fill['symbol'],fill['market'],fill['window_start']))
        # Change actual source volume without touching recorded participation/reference.
        row['base_volume']='1'
        save(path,rows)
    elif mutation=='ledger_cash':
        alter('ledger',lambda rows:rows[0].update(cash_spot_change='123456789'))
        changed=run
    elif mutation in {'period','h2','h3','incident'}:
        name,field,value={
            'period':('metricas','days','999'), 'h2':('h2','verdict','invented'),
            'h3':('h3_resumen','h3_descriptive','invented'),
            'incident':('incidentes_resumen','max_loss_from_start_usdt','123456789')}[mutation]
        csv_change(package/'tablas'/(name+'.csv'),field,value)
    elif mutation=='parquet_result':
        path=package/'tablas/metricas.parquet'
        source=pq.read_table(path)
        rows=source.to_pylist()
        rows[0]['net_pnl_usdt']='123456789'
        pq.write_table(pa.Table.from_pylist(rows,schema=source.schema),path)
    elif mutation=='control_duplicate':
        path=package/'documentos/control_compatibilidad_base_completa.json'
        proof=read(path)
        proof['comparisons']=[proof['comparisons'][0]]*2
        save(path,proof)
    elif mutation=='base_manifest':
        base=next(r for r in index['runs'] if r['scenario']=='BASE_E3')
        changed=package/base['path']
        path=changed/'run_manifest.json'
        proof=read(path)
        proof['fabricated_note']='Not the original authenticated manifest'
        save(path,proof)
    elif mutation=='control_sequence':
        proof_path=package/'documentos/control_compatibilidad_base_completa.json'
        proof=read(proof_path)
        control=package/'evidencia_control'/proof['comparisons'][0]['control_run_id']
        path=control/'ledger.parquet'
        source=pq.read_table(path)
        rows=source.to_pylist()
        rows[0],rows[1]=rows[1],rows[0]
        pq.write_table(pa.Table.from_pylist(rows,schema=source.schema),path)
        rehash(package,control)
        digest=sha(control/'run_manifest.json')
        proof['comparisons'][0]['control_manifest_sha256']=digest
        save(proof_path,proof)
        state_path=package/'controles_base'/('CONTROL_BASE__'+proof['comparisons'][0]['strategy']+'.json')
        state=read(state_path)
        state['manifest_sha256']=digest
        save(state_path,state)
    elif mutation in {'catalog_missing','catalog_label'}:
        path=package/'fuentes/archivos_originales.csv'
        with path.open(encoding='utf8',newline='') as stream:
            reader=csv.DictReader(stream)
            fields,rows=reader.fieldnames,list(reader)
        if mutation=='catalog_missing':
            rows.pop()
        else:
            rows[0]['source_name']='invented'
        with path.open('w',encoding='utf8',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
    elif mutation=='h1_missing':
        removed='hipotesis_base/h1_observaciones.csv'
        (package/removed).unlink()
        path=package/'manifiesto_paquete.json'
        proof=read(path)
        proof['members']=[r for r in proof['members'] if r['path']!=removed]
        save(path,proof)
    rehash(package,changed)
    result=subprocess.run([sys.executable,'-B','-X','utf8',str(package/'herramientas/scripts/verify_execution_delays.py'),
        '--package',str(package),'--output',str(tmp_path/'audit.json')],cwd=tmp_path,
        capture_output=True,text=True,encoding='utf8',timeout=300,
        env={**os.environ,'PYTHONPATH':'','PYTHONDONTWRITEBYTECODE':'1'},
        creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    assert result.returncode!=0
    assert expected.lower() in (result.stdout+result.stderr).lower(),result.stdout+result.stderr
    assert not (tmp_path/'audit.json').exists()
