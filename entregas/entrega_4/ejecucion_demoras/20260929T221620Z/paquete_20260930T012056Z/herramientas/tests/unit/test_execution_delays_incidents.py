"""Bounded incident sampling cannot include terminal post-close states or global claims."""

from decimal import Decimal as D
from pathlib import Path

import numpy as np

from crypto_carry.config import SECOND, Config, timestamp


def test_top_five_are_preselected_by_duration_time_and_symbol():
    from scripts.execution_delays_incidents import select_cases
    cfg=Config.load(Path(__file__).resolve().parents[2]/
        'configs/entrega_4/reglas_historicas/BASE_E3.toml')
    t=timestamp(cfg.start)
    episodes=[dict(episode_id=str(i),symbol='ETHUSDT' if i%2 else 'BTCUSDT',
        start_ns=t+i*SECOND,end_ns=t+(i+10)*SECOND,seconds=D(10)) for i in range(7)]
    cases=select_cases(episodes,[],cfg)
    assert [c['episode_id'] for c in cases]==['0','1','2','3','4']
    assert all(c['selection']=='top5_duration' for c in cases)


def test_incident_end_uses_pre_close_and_no_margin_after_short_closed():
    from scripts.execution_delays_incidents import value_case
    cfg=Config.load(Path(__file__).resolve().parents[2]/
        'configs/entrega_4/reglas_historicas/BASE_E3.toml')
    t=timestamp(cfg.start)
    common=dict(symbol='BTCUSDT',free_futures='0',debt='0',short='0',average='0',collateral='0')
    ledger=[dict(common,time_ns=t,event_id='buy',kind='spot_buy',free_spot='9000',spot='10'),
            dict(common,time_ns=t+60*SECOND,event_id='sell',kind='spot_sell',free_spot='12000',spot='0')]
    prices={}
    for symbol in cfg.symbols:
        for label in ('spot','mark'):
            prices[symbol,label]=dict(available_at=np.array([t,t+60*SECOND],dtype=np.int64),
                close=np.array([100.,90.]),base_volume=np.array([1.,1.]),
                open_time=np.array([t-60*SECOND,t],dtype=np.int64),
                source_id=np.array([0,0],dtype=np.int64),estimated=np.array([0,0]))
    case=dict(case_id='fixture',symbol='BTCUSDT',start_ns=t,end_ns=t+60*SECOND,
              selection='top5_duration',episode_id='fixture')
    detail,summary=value_case(cfg,ledger,case,prices)
    assert detail[-1]['phase']=='pre'
    assert detail[-1]['equity_usdt']==9900
    assert summary['max_loss_from_start_usdt']==100
    assert all(r['margin_headroom_usdt'] is None and r['margin_reason']=='no_open_short' for r in detail)


def test_carried_spot_is_not_labeled_observed_executable_price():
    from scripts.execution_delays_incidents import price_quality_name
    assert price_quality_name(2)=='carried_expected_minute_absent'
    assert price_quality_name(3)=='carried_zero_volume_omitted'


def test_march_day_is_selected_for_covered_exposure_too():
    from scripts.execution_delays_incidents import select_cases
    cfg=Config.load(Path(__file__).resolve().parents[2]/
        'configs/entrega_4/reglas_historicas/BASE_E3.toml')
    t=timestamp('2023-03-24T00:00:00Z')
    cases=select_cases([], [dict(symbol='BTCUSDT',exposure='covered',start_ns=t,
                                 end_ns=t+60*SECOND)],cfg)
    assert len(cases)==1 and cases[0]['selection']=='prespecified_2023_03_24'


def test_march_day_retains_dust_price_exposure_without_counting_it_as_active():
    from scripts.execution_delays_incidents import select_cases
    cfg=Config.load(Path(__file__).resolve().parents[2]/
        'configs/entrega_4/reglas_historicas/BASE_E3.toml')
    t=timestamp('2023-03-24T00:00:00Z')
    cases=select_cases([], [dict(symbol='BTCUSDT',exposure='dust',start_ns=t,
                                 end_ns=t+60*SECOND)],cfg)
    assert len(cases)==1
    assert cases[0]['selected_exposure_classes']==['dust']


def test_missing_valuation_start_cannot_be_reported_as_zero_loss():
    from scripts.execution_delays_incidents import value_case
    cfg=Config.load(Path(__file__).resolve().parents[2]/
        'configs/entrega_4/reglas_historicas/BASE_E3.toml')
    t=timestamp(cfg.start)
    ledger=[dict(symbol='BTCUSDT',free_futures='0',debt='0',short='0',average='0',
        collateral='0',time_ns=t,event_id='buy',kind='spot_buy',free_spot='9000',spot='10')]
    detail,summary=value_case(cfg,ledger,dict(case_id='missing',symbol='BTCUSDT',
        start_ns=t,end_ns=t+60*SECOND),{})
    assert all(r['equity_usdt'] is None for r in detail)
    assert all(r['loss_from_start_usdt'] is None for r in detail)
    assert summary['observed_max_loss_from_start_usdt'] is None
    assert summary['spot_carried_observations']==0
    assert summary['spot_missing_reference_observations']==len(detail)


def boundary_fixture():
    cfg=Config.load(Path(__file__).resolve().parents[2]/
        'configs/entrega_4/reglas_historicas/BASE_E3.toml')
    t=timestamp(cfg.start)
    prices={(s,label):dict(available_at=np.array([t,t+60*SECOND],dtype=np.int64),
        close=np.array([100.,100.]),base_volume=np.array([1.,1.]),
        open_time=np.array([t-60*SECOND,t],dtype=np.int64),
        source_id=np.array([0,0],dtype=np.int64),estimated=np.array([0,0]))
        for s in cfg.symbols for label in ('spot','mark')}
    case=dict(case_id='boundary',symbol='BTCUSDT',start_ns=t,end_ns=t+60*SECOND,
              selection='top5_duration',episode_id='boundary')
    common=dict(symbol='BTCUSDT',free_futures='0',debt='0',short='1',average='100',
                collateral='50',spot='2',free_spot='9750')
    return cfg,t,prices,case,common


def test_funding_before_same_timestamp_closing_fill_is_retained():
    from scripts.execution_delays_incidents import value_case
    cfg,t,prices,case,common=boundary_fixture()
    ledger=[dict(common,time_ns=t,event_id='open',kind='futures_sell'),
        dict(common,time_ns=t+60*SECOND,event_id='funding',kind='funding',collateral='10'),
        dict(common,time_ns=t+60*SECOND,event_id='hedge',kind='futures_sell',
             short='2',collateral='110',free_spot='9650')]
    detail,summary=value_case(cfg,ledger,case,prices)
    assert summary['max_loss_from_start_usdt']==40
    assert abs(summary['minimum_observed_margin_headroom_usdt']-9.6)<1e-12
    assert detail[-1]['ledger_state_index']==2
    assert summary['end_ledger_event_id']=='hedge'


def test_other_asset_movement_after_opening_is_not_absorbed_in_initial_equity():
    from scripts.execution_delays_incidents import value_case
    cfg,t,prices,case,common=boundary_fixture()
    common.update(spot='1',short='0',collateral='0',average='0',free_spot='9899')
    ledger=[dict(common,time_ns=t,event_id='btc',kind='spot_buy'),
        dict(common,time_ns=t,event_id='eth',kind='spot_buy',symbol='ETHUSDT',free_spot='9798'),
        dict(common,time_ns=t+60*SECOND,event_id='hedge',kind='futures_sell',
             short='1',average='100',collateral='50',free_spot='9748')]
    detail,summary=value_case(cfg,ledger,case,prices)
    assert detail[0]['equity_usdt']==9999
    assert summary['max_loss_from_start_usdt']==1
    assert summary['start_ledger_event_id']=='btc'


def test_calendar_case_includes_pre_and_all_post_states_at_both_boundaries():
    from scripts.execution_delays_incidents import value_case
    cfg,t,prices,case,common=boundary_fixture()
    case['selection']='prespecified_2023_03_24'
    ledger=[dict(common,time_ns=t,event_id='open',kind='futures_sell'),
        dict(common,time_ns=t+60*SECOND,event_id='funding',kind='funding',collateral='10')]
    detail,summary=value_case(cfg,ledger,case,prices)
    assert [r['ledger_state_index'] for r in detail]==[0,1,1,2]
    assert summary['start_boundary_policy']=='calendar_pre_timestamp'
    assert summary['end_boundary_policy']=='calendar_all_inclusive_states'


def test_sample_end_excludes_reference_first_available_at_terminal_boundary():
    from dataclasses import replace

    from crypto_carry.config import iso
    from scripts.execution_delays_incidents import value_case
    cfg,t,prices,case,common=boundary_fixture()
    cfg=replace(cfg,end=iso(t+60*SECOND))
    common.update(spot='1',short='0',collateral='0',average='0',free_spot='9900')
    ledger=[dict(common,time_ns=t,event_id='open',kind='spot_buy')]
    prices['BTCUSDT','spot']['close'][1]=10
    detail,summary=value_case(cfg,ledger,case,prices)
    assert detail[-1]['time_ns']==t+60*SECOND-1
    assert summary['end_ns']==t+60*SECOND
    assert summary['max_loss_from_start_usdt']==0
    assert summary['end_boundary_policy']=='terminal_exclusive_before_end'


def test_state_only_end_keeps_pre_timestamp_and_identifies_missing_movement():
    from scripts.execution_delays_incidents import value_case
    cfg,t,prices,case,common=boundary_fixture()
    common.update(spot='.001',short='0',collateral='0',average='0',free_spot='9999.9')
    ledger=[dict(common,time_ns=t,event_id='open',kind='spot_buy'),
        dict(common,time_ns=t+60*SECOND,event_id='other',kind='spot_buy',symbol='ETHUSDT',
             spot='1',free_spot='9898.9')]
    case.update(end_spot_target='.001',end_short_target='0')
    detail,summary=value_case(cfg,ledger,case,prices)
    assert detail[-1]['ledger_state_index']==1
    assert summary['end_boundary_policy']=='pre_timestamp_no_quantity_movement'
    assert summary['end_ledger_event_id'] is None


def test_compact_source_export_preserves_spot_fields_when_first_row_is_mark(tmp_path):
    from scripts.execution_delays_incidents import price_arrays, write_sources
    from scripts.return_capital.common import parquet
    cfg,t,_,_,_=boundary_fixture()
    common=dict(symbol=cfg.symbols[0],available_at=t,open_time=t-60*SECOND,
                source_id=1,close='100',estimation_method='official')
    path=tmp_path/'mixed.parquet'
    write_sources(path,[dict(common,label='mark'),dict(common,label='spot',base_volume='12')])
    assert price_arrays(parquet(path))[cfg.symbols[0],'spot']['base_volume'].tolist()==[12.]
