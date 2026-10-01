"""Reject fabricated economics even when outer file hashes are renewed elsewhere."""

from copy import deepcopy
from decimal import Decimal as D
from pathlib import Path

import pytest

from crypto_carry.config import SECOND, Config, timestamp


def fixture(model='ohlc4', delay=0, scope='all_client', purpose='open_spot'):
    cfg=Config.load(Path(__file__).resolve().parents[2]/
        'configs/entrega_4/reglas_historicas/BASE_E3.toml').changed(
            research_minute_price_model=model,research_execution_delay_seconds=delay,
            research_execution_delay_scope=scope)
    t=timestamp(cfg.start)
    applied=delay if purpose!='liquidate' and (scope=='all_client' or purpose in
        ('close_spot','close_perp')) else 0
    start=t+applied*SECOND
    end=start+60*SECOND
    meta=dict(reference_price_model=model,delay_configured_seconds=delay,delay_scope=scope,
              delay_applied_seconds=applied,eligible_at=start,generated_at=t)
    order=dict(order_id='a',symbol='BTCUSDT',market='spot',side='BUY',quantity='.1',
        filled_quantity='0',remaining_quantity='.1',status='pending',submitted_at=t,
        window_start=start,window_end=end,deadline=end,time_ns=t,record_type='event',
        action='submitted',purpose=purpose,event_sequence=0,**meta)
    filled=dict(order,filled_quantity='.1',remaining_quantity='0',status='filled',time_ns=end,
                action='filled',event_sequence=1,fill_at=end)
    terminal=dict(filled,record_type='final',action=None,event_sequence=None)
    price='101.02' if model=='ohlc4' else '102.02'
    fill=dict(order_id='a',fill_id='fa',symbol='BTCUSDT',market='spot',side='BUY',
        quantity='.1',price=price,reference_price='101' if model=='ohlc4' else '102',
        fee_rate='.001',slippage_rate='.0001',liquidation=False,time_ns=end,
        window_start=start,window_end=end,window_base_volume='10',window_quote_volume='1020',
        window_ohlc4='101',window_vwap='102',window_open='100',window_high='110',
        window_low='90',window_close='104',window_available_at=end,submitted_at=t,
        deadline=end,purpose=purpose,fill_sequence=0,capacity_used='.1',fill_at=end,**meta)
    ledger=dict(event_id='fill:fa',symbol='BTCUSDT',kind='spot_buy',quantity='.1',
        price=price,fee=str(D('.1')*D(price)*D('.001')),base_fee_quantity='.0001',
        liquidation_fee=None,time_ns=end)
    window=dict(symbol='BTCUSDT',market='spot',open_time=start,end_time=end,available_at=end,
        open='100',high='110',low='90',close='104',base_volume='10',quote_volume='1020',
        present=True,trade_count=10)
    return cfg,[order,filled,terminal],[fill],[ledger],[window]


def test_audit_independently_checks_reference_and_eligible_window():
    from scripts.execution_delays_audit import audit_execution
    a=audit_execution(*fixture())
    assert a['fills_conciliados'][0]['reference_price']==101
    b=audit_execution(*fixture('vwap',300))
    assert b['ordenes'][0]['delay_applied_seconds']==300
    assert b['ordenes'][0]['submission_to_fill_seconds']==360


@pytest.mark.parametrize('target,field,value',[
    (2,'reference_price','102'),(2,'reference_price_model','vwap'),
    (2,'quantity','.2'),(2,'fee_rate','.1'),(2,'fill_sequence',99),
    (2,'purpose','liquidate'),(2,'window_ohlc4','102'),(4,'low','105'),
    (4,'base_volume','1'),(1,'deadline',1),(1,'event_sequence',20),
    (1,'delay_applied_seconds',60),(1,'eligible_at',1),
])
def test_semantic_mutations_are_rejected(target,field,value):
    from scripts.execution_delays_audit import audit_execution
    data=deepcopy(fixture())
    data[target][0][field]=value
    with pytest.raises(ValueError):
        audit_execution(*data)


def test_no_fill_latency_is_none_and_preventive_deadline_is_named():
    from scripts.execution_delays_audit import audit_execution
    cfg,orders,_,_,windows=fixture('vwap',300,purpose='correct')
    for order in orders:
        order.update(market='futures',side='BUY')
    windows[0]['market']='futures'
    cancellation=dict(orders[0],action='hedge_correction_deadline',status='cancelled',
                       time_ns=orders[0]['submitted_at']+60*SECOND,event_sequence=1,
                       cancel_requested_at=orders[0]['submitted_at']+60*SECOND,
                       cancel_effective_at=orders[0]['submitted_at']+60*SECOND)
    final=dict(cancellation,record_type='final',action=None,event_sequence=None)
    result=audit_execution(cfg,[orders[0],cancellation,final],[],[],windows)
    order=result['ordenes'][0]
    assert order['submission_to_fill_seconds'] is None
    assert order['shortfall_cause']=='preventive_correction_deadline'


@pytest.mark.parametrize('mutation',['cancel_then_fill','liquidate_spot','fill_submission',
    'remove_events','event_fill_time','fill_at','cancel_time','expiry_time'])
def test_cross_record_mutations_rejected(mutation):
    from scripts.execution_delays_audit import audit_execution
    cfg,orders,fills,ledger,windows=fixture('vwap',300)
    if mutation=='cancel_then_fill':
        orders[1].update(status='cancelled',action='fixture_cancel',time_ns=orders[0]['submitted_at']+1)
    elif mutation=='liquidate_spot':
        cfg,orders,fills,ledger,windows=fixture()
        for r in orders+fills:
            r['purpose']='liquidate'
    elif mutation=='fill_submission':
        for k in ('submitted_at','generated_at','eligible_at'):
            fills[0][k]-=1
    elif mutation=='remove_events':
        orders=orders[-1:]
    elif mutation=='event_fill_time':
        orders[1]['time_ns']+=1
    elif mutation=='fill_at':
        fills[0]['fill_at']+=1
    elif mutation=='cancel_time':
        orders[-1]['cancel_effective_at']=1
    elif mutation=='expiry_time':
        orders[-1]['expired_at']=1
    with pytest.raises(ValueError):
        audit_execution(cfg,orders,fills,ledger,windows)


def test_old_window_expiration_is_rejected():
    from scripts.execution_delays_audit import audit_execution
    cfg,orders,_,_,windows=fixture('vwap',300)
    expired=dict(orders[0],status='expired',action='timeout',event_sequence=1,
        time_ns=orders[0]['submitted_at']+60*SECOND,expired_at=orders[0]['submitted_at']+60*SECOND)
    final=dict(expired,record_type='final',event_sequence=None,action=None)
    with pytest.raises(ValueError,match='deadline'):
        audit_execution(cfg,[orders[0],expired,final],[],[],windows)


def test_renumbering_fills_cannot_change_original_ledger_order():
    from scripts.execution_delays_audit import audit_execution
    cfg,orders,fills,ledger,windows=fixture()
    cfg=cfg.changed(max_volume_participation=D('.02'))
    other_orders,other_fills,other_ledger=deepcopy((orders,fills,ledger))
    for r in other_orders+other_fills:
        r['order_id']='b'
    other_fills[0]['fill_id']='fb'
    other_fills[0]['capacity_used']='.2'
    other_ledger[0]['event_id']='fill:fb'
    combined=[orders[0],other_orders[0],orders[1],other_orders[1],orders[-1],other_orders[-1]]
    for i,r in enumerate(combined[:4]):
        r['event_sequence']=i
    for i,r in enumerate(fills+other_fills):
        r['fill_sequence']=i
    audit_execution(cfg,combined,fills+other_fills,ledger+other_ledger,windows)
    altered=other_fills+fills
    for i,r in enumerate(altered):
        r['fill_sequence']=i
    with pytest.raises(ValueError,match='sequence'):
        audit_execution(cfg,combined,altered,ledger+other_ledger,windows)


def test_same_market_purpose_must_match_original_causal_transition():
    from scripts.execution_delays_audit import audit_execution
    cfg,orders,fills,ledger,windows=fixture()
    risk=[dict(order_id='a',symbol='BTCUSDT',time_ns=orders[0]['time_ns'],
               kind='transition',state='OPENING_SPOT',previous='FLAT',cause='entry')]
    audit_execution(cfg,orders,fills,ledger,windows,risk_events=risk)
    for r in orders+fills:
        r['purpose']='increase_spot'
    with pytest.raises(ValueError,match='causal'):
        audit_execution(cfg,orders,fills,ledger,windows,risk_events=risk)


@pytest.mark.parametrize('final_time',['before_submission','after_deadline'])
def test_pending_final_requires_unfinished_future_window(final_time):
    from scripts.execution_delays_audit import audit_execution
    cfg,orders,_,_,windows=fixture('vwap',300)
    final=dict(orders[0],record_type='final',event_sequence=None,action=None)
    final['time_ns']=(orders[0]['submitted_at']-1 if final_time=='before_submission'
                      else timestamp(cfg.end)-1)
    with pytest.raises(ValueError):
        audit_execution(cfg,[orders[0],final],[],[],windows)


def test_replaced_state_cannot_justify_new_reduction_purpose():
    from scripts.execution_delays_audit import validate_causal_purposes
    cfg,orders,_,_,_=fixture(purpose='close_perp')
    t=orders[0]['submitted_at']
    risk=[dict(symbol='BTCUSDT',kind='transition',state='REBALANCING',time_ns=t-60*SECOND),
          dict(symbol='BTCUSDT',kind='transition',state='CLOSING_PERP',time_ns=t)]
    validate_causal_purposes(orders,risk)
    for row in orders:
        row['purpose']='reduce_perp'
    with pytest.raises(ValueError,match='causal'):
        validate_causal_purposes(orders,risk)


def test_per_asset_opportunity_cannot_change_under_complete_execution_variant():
    from scripts.execution_delays_report import h3_replay_invariance
    reference=[dict(date='2022-01-01',symbol='BTCUSDT',minutos_totales='1440',
        minutos_conocidos='1440',minutos_desconocidos='0',minutos_elegibles='10',suma_forecast_elegible='.04')]
    assert h3_replay_invariance(reference,reference,True)['h3_replay_projection_equal']
    actual=[dict(reference[0],minutos_elegibles='11')]
    with pytest.raises(ValueError,match='opportunity'):
        h3_replay_invariance(actual,reference,True)
    assert not h3_replay_invariance(actual,reference,False)['h3_replay_projection_equal']
