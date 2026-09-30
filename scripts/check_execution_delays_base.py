"""Compare repaired full BASE controls to immutable original economic evidence."""

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'src')]

from crypto_carry.config import Config  # noqa: E402
from crypto_carry.reporting import verify_run  # noqa: E402
from scripts.execution_delays import BASES  # noqa: E402
from scripts.return_capital.common import (  # noqa: E402
    parquet,
    read_csv,
    read_json,
    sha256,
    write_json,
)

FILES = ('equity_daily.csv','positions.parquet','fills.parquet','orders.parquet',
         'risk_events.parquet','ledger.parquet','funding_payments.parquet',
         'signals.parquet','renewal_diagnostics.parquet','forecast_evaluation.csv',
         'opportunity_daily.csv')


def ordered_economic_digest(rows, ignored=('run_id','units')):
    records=[json.dumps({k:v for k,v in row.items() if k not in ignored},
                        sort_keys=True,ensure_ascii=False,default=str,separators=(',',':'))
             for row in rows]
    return hashlib.sha256('\n'.join(records).encode('utf8')).hexdigest()


def compare(reference, candidate):
    if not verify_run(reference)['valid'] or not verify_run(candidate)['valid']:
        raise ValueError('Unverified control or original run')
    if Config.load(reference/'effective_config.toml').to_dict() != Config.load(candidate/'effective_config.toml').to_dict():
        raise ValueError('BASE control configuration changed')
    result = []
    for filename in FILES:
        loader = parquet if filename.endswith('.parquet') else read_csv
        old, new = loader(reference/filename), loader(candidate/filename)
        ignored = ('run_id','units')
        a,b = ordered_economic_digest(old,ignored=ignored),ordered_economic_digest(new,ignored=ignored)
        result.append(dict(file=filename,original_rows=len(old),control_rows=len(new),
            original_digest=a,control_digest=b,exact_equal=a==b,ignored_fields=ignored,
            row_order='original_persisted'))
    return dict(passed=all(r['exact_equal'] for r in result),original_run_id=reference.name,
        control_run_id=candidate.name,original_manifest_sha256=sha256(reference/'run_manifest.json'),
        control_manifest_sha256=sha256(candidate/'run_manifest.json'),comparisons=result)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--work',type=Path,required=True)
    p.add_argument('--data-root',type=Path,default=Path('D:/Backtesting'))
    a=p.parse_args()
    output=a.work/'control_compatibilidad_base_completa.json'
    if output.exists():
        raise FileExistsError(output)
    comparisons=[]
    for strategy,rid in BASES.items():
        state=read_json(a.work/'controles_base'/f'CONTROL_BASE__{strategy}.json')
        if state['status']!='ejecutado':
            raise ValueError('Unfinished BASE control')
        row=compare(a.data_root/'outputs'/rid,Path(state['path']))
        row['strategy']=strategy
        comparisons.append(row)
    result=dict(passed=all(r['passed'] for r in comparisons),comparisons=comparisons,
        scope='Full continuous BASE portfolios, exact economic projections in original persisted order, no rounding; controls are separate runs',
        original_references_preserved=True,approved_repair='controles/aprobacion_reparacion.md')
    write_json(output,result)
    if not result['passed']:
        raise ValueError('BASE controls differ; inspect all comparisons before scenarios')
    print('Both complete BASE controls exactly match original economic projections')


if __name__=='__main__':
    main()
