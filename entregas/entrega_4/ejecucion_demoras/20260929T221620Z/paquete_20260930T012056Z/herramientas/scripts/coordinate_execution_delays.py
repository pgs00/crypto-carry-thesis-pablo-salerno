"""Sequential stage gates around at most two complete historical replay workers."""

import argparse
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'src')]

from scripts.execution_delays import STAGES  # noqa: E402
from scripts.return_capital.common import read_json, write_json  # noqa: E402


def coordinate(work,data,raw):
    # These two controls were started separately after the sequential RAM measurement.
    while True:
        states=[read_json(work/'controles_base'/('CONTROL_BASE__'+s+'.json'))
                for s in ('conditional','permanent')]
        if any(r['status']=='fallido' for r in states):
            raise RuntimeError('A BASE control failed; preserve and inspect it')
        if all(r['status']=='ejecutado' for r in states):
            break
        time.sleep(5)
    commands=[]

    def run(script,args,label):
        command=[sys.executable,'-B','-u','-X','utf8',str(ROOT/'scripts'/script),*map(str,args)]
        path=work/'logs_corridas'/(label+'__'+datetime.now(UTC).strftime('%Y%m%dT%H%M%S%fZ')+'.txt')
        print('START GATE',label,flush=True)
        with path.open('x',encoding='utf8') as log:
            result=subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,
                env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','MPLBACKEND':'Agg'},
                creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        commands.append(dict(command=command,log=str(path),exit_code=result.returncode,
                             finished_utc=datetime.now(UTC).isoformat()))
        write_json(work/'coordinacion_etapas.json',dict(commands=commands))
        if result.returncode:
            raise RuntimeError('Stage stopped at '+label+'; see '+str(path))
        print('PASSED',label,flush=True)

    comparison=work/'control_compatibilidad_base_completa.json'
    if not comparison.exists():
        run('check_execution_delays_base.py',['--work',work,'--data-root',data],'base_completa')
    if not read_json(comparison)['passed']:
        raise ValueError('Full BASE compatibility failed')
    for stage in STAGES:
        gate=work/('control_etapa_'+stage+'.json')
        if gate.exists() and read_json(gate)['passed']:
            print('REUSED PASSED GATE',stage,flush=True)
            continue
        run('run_execution_delays.py',['--package',work,'--data-root',data,'--raw-root',raw,
                                      '--stage',stage,'--workers','2'],stage)
        run('audit_execution_delays_stage.py',['--work',work,'--data-root',data,'--stage',stage],
            'auditoria_'+stage)
    print('ALL THREE STAGES EXECUTED AND RECONCILED',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--work',type=Path,required=True)
    p.add_argument('--data-root',type=Path,required=True)
    p.add_argument('--raw-root',type=Path,required=True)
    a=p.parse_args()
    coordinate(a.work.resolve(),a.data_root.resolve(),a.raw_root.resolve())
