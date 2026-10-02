"""Local incident valuation only: original ledger, causal prices, explicit coverage."""

from collections import defaultdict
from decimal import Decimal as D

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from crypto_carry.config import DAY, SECOND, Config, iso, timestamp
from crypto_carry.data.prescribed import prescribed_rules
from scripts.intraday_risk_math import equity_value, short_margin
from scripts.intraday_risk_price_quality import REASON_DICTIONARY, quality_codes
from scripts.intraday_risk_sources import account_history, observation_grid, price_at
from scripts.return_capital.common import parquet, read_json, sha256

MINUTE = 60*SECOND


def price_quality_name(code):
    return REASON_DICTIONARY[str(int(code))]['name']


def select_cases(episodes, intervals, config):
    cases=[]
    for rank,row in enumerate(sorted(episodes,key=lambda r:(-D(r['seconds']),
                                 int(r['start_ns']),r['symbol']))[:5],1):
        case=dict(row,case_id='top5-'+str(rank)+'-'+row['episode_id'],
                  selection='top5_duration',rank=rank)
        for boundary in ('start','end'):
            target=next((r for r in intervals if r['symbol']==row['symbol'] and
                         int(r['start_ns'])==int(row[boundary+'_ns'])),None)
            if target is not None:
                for quantity in ('spot','short'):
                    case[boundary+'_'+quantity+'_target']=target[quantity]
        cases.append(case)
    day=timestamp('2023-03-24T00:00:00Z')
    for symbol in config.symbols:
        exposed=[r for r in intervals if r['symbol']==symbol and r['exposure'] in
                 ('covered','unhedged','dust') and int(r['start_ns'])<day+DAY and int(r['end_ns'])>day]
        if exposed:
            cases.append(dict(case_id='20230324-'+symbol,episode_id=None,symbol=symbol,
                selection='prespecified_2023_03_24',rank=None,start_ns=day,end_ns=day+DAY-1,
                selected_exposure_classes=sorted({r['exposure'] for r in exposed})))
    return cases


def extract_case_sources(data, config, cases, inputs):
    """Exact Decimal/text source rows plus prior valid references, no bulk export."""
    manifest=read_json(data/config.data_dir/'manifests/processed.json')
    intervals=[(int(c['start_ns'])-DAY,int(c['end_ns'])) for c in cases]
    found=[]
    for index,entry in enumerate(manifest['entries']):
        if entry['dataset'] not in {'minute_bars','marks'} or (
            entry['dataset']=='minute_bars' and entry['market']!='spot'):
            continue
        month=entry['date']
        relevant=[(a,b) for a,b in intervals if iso(a)[:7]<=month<=iso(b)[:7]]
        if not relevant:
            continue
        name=entry['path']
        if inputs.get(name)!=entry['sha256'] or sha256(data/name)!=entry['sha256']:
            raise ValueError('Incident price partition authentication failed: '+name)
        parquet=pq.ParquetFile(data/name)
        names=[k for k in ('symbol','market','available_at','open_time','end_time','close_time',
                          'close','base_volume','estimation_method','source_file')
               if k in parquet.schema_arrow.names]
        table=parquet.read(columns=names)
        mask=None
        for a,b in relevant:
            current=pc.and_(pc.greater_equal(table['available_at'],a),pc.less_equal(table['available_at'],b))
            mask=current if mask is None else pc.or_(mask,current)
        for row in table.filter(mask).to_pylist():
            found.append(dict(row,label='spot' if entry['dataset']=='minute_bars' else 'mark',
                source_id=index,source_path=name,source_sha256=entry['sha256']))
    return sorted(found,key=lambda r:(r['symbol'],r['label'],int(r['available_at'])))


def price_arrays(source_rows):
    grouped=defaultdict(list)
    for row in source_rows:
        grouped[row['symbol'],row['label']].append(row)
    result={}
    for key,rows in grouped.items():
        rows=sorted(rows,key=lambda r:int(r['available_at']))
        if len({int(r['available_at']) for r in rows})!=len(rows):
            raise ValueError('Duplicated incident price source')
        values={k:np.asarray([int(r[k]) for r in rows],dtype=np.int64)
                for k in ('available_at','open_time','source_id')}
        values['close']=np.asarray([float(r['close']) for r in rows])
        if key[1]=='spot':
            values['base_volume']=np.asarray([float(r['base_volume']) for r in rows])
        values['estimated']=np.asarray([r.get('estimation_method','official') not in
                                       ('official',None,'') for r in rows],dtype=np.int8)
        result[key]=values
    return result


def case_grid(ledger, history, case, *, sample_end):
    """Anchor episode cuts to its asset's ledger movement, preserving tied events."""
    lower,upper=int(case['start_ns']),int(case['end_ns'])
    terminal=upper>=sample_end
    upper=min(upper,sample_end-1)
    grid=observation_grid(lower,upper+1,history,[],extra_times=[lower,upper])
    policy=dict(start_ledger_event_id=None,end_ledger_event_id=None,
                start_boundary_policy='calendar_pre_timestamp',
                end_boundary_policy=('terminal_exclusive_before_end' if terminal else
                                     'calendar_all_inclusive_states'),
                last_observed_time_ns=upper)
    if case.get('selection')=='prespecified_2023_03_24':
        return grid,policy
    keep=np.ones(len(grid['time_ns']),dtype=bool)
    quantities=(D(0),D(0))
    candidates={'start':[],'end':[]}
    for index,row in enumerate(ledger,1):
        if row['symbol']!=case['symbol']:
            continue
        after=(D(str(row['spot'])),D(str(row['short'])))
        if after!=quantities:
            for boundary,t in (('start',lower),('end',upper)):
                if int(row['time_ns'])!=t:
                    continue
                target=tuple(case.get(boundary+'_'+q+'_target') for q in ('spot','short'))
                if any(q is None for q in target) or after==tuple(D(str(q)) for q in target):
                    candidates[boundary].append((index,row['event_id']))
        quantities=after
    for boundary,t in (('start',lower),('end',upper)):
        if boundary=='end' and terminal:
            continue
        at=grid['time_ns']==t
        if candidates[boundary]:
            anchor,identity=candidates[boundary][-1]
            keep[at]&=(grid['state_index'][at]>=anchor if boundary=='start'
                       else grid['state_index'][at]<anchor)
            policy[boundary+'_ledger_event_id']=identity
            policy[boundary+'_boundary_policy']=('post_asset_movement' if boundary=='start'
                                                  else 'before_asset_movement')
        else:
            indices=np.flatnonzero(at)
            if len(indices)>1:
                keep[indices[:-1] if boundary=='start' else indices[1:]]=False
            policy[boundary+'_boundary_policy']=('post_timestamp_no_quantity_movement' if boundary=='start'
                                                  else 'pre_timestamp_no_quantity_movement')
    if not keep.any():
        raise ValueError('Incident boundary leaves no causal state')
    grid={k:v[keep] for k,v in grid.items()}
    return grid,policy


def value_case(config, ledger, case, prices):
    history=account_history(ledger,config.capital,config.symbols)
    lower=int(case['start_ns'])
    grid,boundaries=case_grid(ledger,history,case,sample_end=timestamp(config.end))
    time,index=grid['time_ns'],grid['state_index']
    refs={}
    qualities={}
    for symbol in config.symbols:
        for label in ('spot','mark'):
            values=prices.get((symbol,label))
            if values is None:
                values=dict(available_at=np.array([],dtype=np.int64),close=np.array([]),
                            base_volume=np.array([]),source_id=np.array([],dtype=np.int64))
            refs[symbol,label]=price_at(values,time,require_volume=label=='spot')
            qualities[symbol,label]=quality_codes(values,time,require_volume=label=='spot')
    spot=np.column_stack([refs[s,'spot']['price'] for s in config.symbols])
    mark=np.column_stack([refs[s,'mark']['price'] for s in config.symbols])
    states={k:history[k][index] for k in ('free_spot','free_futures','debt','spot','short','average','collateral')}
    equity=equity_value(**states,spot_price=spot,mark_price=mark)
    asset=config.symbols.index(case['symbol'])
    q=states['short'][:,asset]
    rule=prescribed_rules(config).get(case['symbol'],'futures',lower)
    rates,deductions=np.full(len(q),np.nan),np.full(len(q),np.nan)
    for tier in rule.tiers:
        selected=np.isnan(rates)&(q*mark[:,asset]>=float(tier.floor))&(q*mark[:,asset]<=float(tier.cap))
        rates[selected],deductions[selected]=float(tier.rate),float(tier.deduction)
    margin=short_margin(q,states['average'][:,asset],states['collateral'][:,asset],
                       mark[:,asset],rates,deductions)

    def finite(value):
        return float(value) if np.isfinite(value) else None

    details=[]
    symbol=case['symbol']
    for i,t in enumerate(time):
        sr,mr=refs[symbol,'spot'],refs[symbol,'mark']
        open_short=q[i]>0
        details.append(dict(case_id=case['case_id'],symbol=symbol,time_ns=int(t),time_utc=iso(t),
            phase=('regular','pre','post')[int(grid['phase'][i])],sequence=int(grid['sequence'][i]),
            ledger_state_index=int(index[i]),equity_usdt=finite(equity[i]),
            pnl_from_start_usdt=finite(equity[i]-equity[0]),
            loss_from_start_usdt=(max(0.,float(equity[0]-equity[i]))
                                 if np.isfinite(equity[0]-equity[i]) else None),
            spot_quantity=float(states['spot'][i,asset]),short_quantity=float(q[i]),
            spot_price=finite(spot[i,asset]),mark_price=finite(mark[i,asset]),
            spot_value_usdt=finite(states['spot'][i,asset]*spot[i,asset]),
            short_notional_usdt=finite(q[i]*mark[i,asset]),
            spot_reference_available_at=int(sr['available_at'][i]),
            mark_reference_available_at=int(mr['available_at'][i]),
            spot_source_id=int(sr['source_id'][i]),mark_source_id=int(mr['source_id'][i]),
            spot_quality=price_quality_name(qualities[symbol,'spot'][i]),
            mark_quality=price_quality_name(qualities[symbol,'mark'][i]),
            mark_estimated=bool(mr.get('estimated',np.zeros(len(time)))[i]),
            margin_balance_usdt=finite(margin['margin_balance'][i]) if open_short else None,
            maintenance_usdt=finite(margin['maintenance'][i]) if open_short else None,
            margin_headroom_usdt=finite(margin['headroom'][i]) if open_short else None,
            margin_reason=str(margin['reason'][i]),
            collateral_usdt=float(states['collateral'][i,asset]),
            free_spot_usdt=float(states['free_spot'][i]),free_futures_usdt=float(states['free_futures'][i]),
            debt_usdt=float(states['debt'][i])))
        # Portfolio equity needs every held asset, not only the case's symbol.
        for a,asset_symbol in enumerate(config.symbols):
            details[-1][asset_symbol+'_spot_quantity']=float(states['spot'][i,a])
            details[-1][asset_symbol+'_short_quantity']=float(states['short'][i,a])
            for label in ('spot','mark'):
                reference=refs[asset_symbol,label]
                prefix=asset_symbol+'_'+label
                details[-1][prefix+'_price']=finite(reference['price'][i])
                details[-1][prefix+'_available_at']=int(reference['available_at'][i])
                details[-1][prefix+'_source_id']=int(reference['source_id'][i])
                details[-1][prefix+'_quality']=price_quality_name(qualities[asset_symbol,label][i])
    valid=np.isfinite(equity)
    losses=[r['loss_from_start_usdt'] for r in details if r['loss_from_start_usdt'] is not None]
    headrooms=[r['margin_headroom_usdt'] for r in details if r['margin_headroom_usdt'] is not None]
    summary=dict(case,**boundaries,observations=len(details),
        frequency='one minute plus each original ledger state; explicit asset/calendar boundary policies',
        valuation_coverage_complete=bool(valid.all()),
        max_loss_from_start_usdt=max(losses,default=None) if valid.all() else None,
        observed_max_loss_from_start_usdt=max(losses,default=None),
        minimum_observed_margin_headroom_usdt=min(headrooms,default=None),
        short_observations=int((q>0).sum()),margin_evaluable_observations=len(headrooms),
        spot_carried_observations=sum(r['spot_quality'].startswith('carried_') for r in details),
        mark_carried_observations=sum(r['mark_quality'].startswith('carried_') for r in details),
        spot_missing_reference_observations=sum(r['spot_quality']=='no_causal_valid_reference' for r in details),
        mark_missing_reference_observations=sum(r['mark_quality']=='no_causal_valid_reference' for r in details),
        valuation_all_active_references_current=all(
            bool(np.all((states['spot'][:,a]==0)|(qualities[s,'spot']==0))) and
            bool(np.all((states['short'][:,a]==0)|(qualities[s,'mark']==0)))
            for a,s in enumerate(config.symbols)),
        scope='selected local case only; no global intraday maximum; carried spot is valuation, not execution')
    return details,summary


def derive_cases(config,ledger,cases,source_rows):
    details,summaries=[],[]
    prices=price_arrays(source_rows)
    for case in cases:
        rows,summary=value_case(config,ledger,case,prices)
        details.extend(rows)
        summaries.append(summary)
    return details,summaries


def write_sources(path,rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    # Decimal prices remain exact source strings; timestamps remain int64.
    columns=list(dict.fromkeys(k for row in rows for k in row))
    normalized=[{k:row.get(k) for k in columns} for row in rows]
    pq.write_table(pa.Table.from_pylist(normalized),path,compression='zstd')


def attach_cases(result, run, item, source_rows):
    config = Config.load(run/'effective_config.toml')
    cases=select_cases(result['episodios_descubiertos'],result['exposicion_intervalos'],config)
    details,summaries=derive_cases(config,parquet(run/'ledger.parquet'),cases,source_rows)
    events=[]
    for kind in ('orders','fills','risk_events','funding_payments'):
        for row in parquet(run/(kind+'.parquet')):
            if kind=='orders' and row.get('record_type')!='event':
                continue
            t=int(row['time_ns'])
            for case in cases:
                if row.get('symbol')==case['symbol'] and int(case['start_ns'])-3600*SECOND<=t<=int(case['end_ns']):
                    events.append(dict(case_id=case['case_id'],kind=kind,time_ns=t,
                        within_case=t>=int(case['start_ns']),record=row))
    identity={k:item[k] for k in ('scenario','strategy','run_id')}
    for name,rows in (('incidentes_seleccion',cases),('incidentes_detalle',details),
                      ('incidentes_resumen',summaries),('incidentes_eventos',events)):
        result[name]=[dict(row,**identity) for row in rows]
    return result
