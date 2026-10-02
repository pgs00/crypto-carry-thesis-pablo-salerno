"""Append a traceable global matrix revision without rewriting sealed matrices."""

import argparse
import csv
import shutil
from datetime import UTC, datetime
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def update(status,package):
    folder=ROOT/'docs/entrega_4'
    target=folder/'matriz_avance.csv'
    history=folder/'historial_avance'
    token=datetime.now(UTC).strftime('%Y%m%dT%H%M%S%fZ')
    history.mkdir(exist_ok=True)
    shutil.copyfile(target,history/(token+'_anterior.csv'))
    with target.open(encoding='utf8',newline='') as f:
        reader=csv.DictReader(f)
        fields,rows=reader.fieldnames,list(reader)
    for row in rows:
        if row['id']=='B4':
            row.update(estado=status,paquete_vigente=package,
                origen='Encargo explícito bloque 4 y reparación de prioridad de liquidación aprobada',
                evidencia=package+('/reporte.md; '+package+'/manifiesto_paquete.json'
                    if status=='ejecutado' else '/progreso.md'),
                limitacion='Seis variantes por dos estrategias, sin cruces; LC es regla causal global de cierre, distinta de propuesta antigua por episodios; drawdown diario y casos intradía acotados',
                actualizado_utc=datetime.now(UTC).isoformat(),publicacion='preparado localmente; sin commit/push')
        elif row['id'] in ('B5','B6','REVISION'):
            row.update(estado='pendiente')
    with target.open('w',encoding='utf8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    with (history/'cambios.md').open('a',encoding='utf8') as f:
        f.write(f'\n- {token}: bloque 4 `{status}`, referencia `{package}`. '
                'LC aplica globalmente a close_perp/close_spot. Shocks y escenario sin interrupción '
                'NO ejecutados aquí; bloques 5 y 6 y revisión transversal/redacción pendientes. '
                'Referencias y sellos anteriores conservados; archivos locales, sin commit/push.\n')
    return target


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--status',choices=('en_ejecucion','ejecutado','bloqueado'),required=True)
    p.add_argument('--package',required=True)
    a=p.parse_args()
    print(update(a.status,a.package))
