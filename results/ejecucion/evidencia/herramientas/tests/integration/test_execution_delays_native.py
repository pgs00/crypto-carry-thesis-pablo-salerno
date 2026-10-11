"""Native fills and causal risk under independently specified delay fixtures."""

from dataclasses import replace
from decimal import Decimal as D

import pytest
from conftest import warmup
from test_next_minute_vwap import bars
from test_next_minute_vwap import config as window_config

from crypto_carry.config import SECOND
from crypto_carry.events import event_key
from crypto_carry.models import Fill, Funding, Mark, MinuteBar, State
from crypto_carry.strategy import Backtest


def config(start, **changes):
    return window_config(start, sizing_model="joint_quantity", **changes)


def rows(start, end=3000):
    return sorted(warmup(start) + bars(start, range(0, end+1, 60)), key=event_key)


@pytest.mark.parametrize('delay,spot,perp', [(0,120,180),(60,180,300),(300,420,780)])
def test_each_opening_leg_receives_delay_and_preserves_submitted_time(start,rules,delay,spot,perp):
    cfg = config(start,seconds=3000,research_execution_delay_seconds=delay)
    result = Backtest(cfg,rules).run(rows(start))
    fills = [f for f in result.fills if f['symbol']=='BTCUSDT']
    assert [(f['purpose'], (f['time_ns']-start)//SECOND) for f in fills] == [
        ('open_spot',spot),('open_perp',perp)]
    submitted = [o for o in result.order_rows if o['symbol']=='BTCUSDT' and o['action']=='submitted']
    assert [o['submitted_at'] for o in submitted] == [start+60*SECOND,start+spot*SECOND]
    if delay:
        assert all(o['eligible_at']==o['submitted_at']+delay*SECOND for o in submitted)
        assert all(o['deadline']==o['window_end'] for o in submitted)
    assert result.native_fill_count==len(result.fills)
    assert result.ledger.reconcile(result.spot_prices(),result.mark_prices())['difference']==0


class CloseAt240(Backtest):
    def process(self,time_ns,records,native):
        super().process(time_ns,records,native)
        if time_ns==self.start+240*SECOND:
            self._close('BTCUSDT','synthetic_preventive_close')


@pytest.mark.parametrize('delay,perp,spot',[(60,360,480),(300,600,960),(900,1200,2160)])
def test_close_only_delays_both_close_legs_but_not_opening(start,rules,delay,perp,spot):
    cfg=config(start,seconds=3000,research_execution_delay_seconds=delay,
               research_execution_delay_scope='close_only')
    result=CloseAt240(cfg,rules).run(rows(start))
    assert [(f['purpose'],(f['time_ns']-start)//SECOND) for f in result.fills if f['symbol']=='BTCUSDT']==[
        ('open_spot',120),('open_perp',180),('close_perp',perp),('close_spot',spot)]
    assert result.ledger.positions['BTCUSDT'].short==0
    assert result._spot_is_dust('BTCUSDT')


def test_funding_keeps_charging_waiting_short_including_fill_boundary(start,rules):
    cfg=config(start,seconds=900,research_execution_delay_seconds=60,
               research_execution_delay_scope='close_only')
    market=rows(start,900)+[Funding('BTCUSDT',start+s*SECOND,start+(s+60)*SECOND,
        D('.001'),D(8),D('100.3'),'synthetic',True) for s in (300,360,420)]
    result=CloseAt240(cfg,rules).run(sorted(market,key=event_key))
    assert [r['time_ns'] for r in result.ledger.funding_rows if r['symbol']=='BTCUSDT']==[
        start+300*SECOND,start+360*SECOND]


def test_liquidation_displaces_waiting_preventive_close_without_client_delay(start,rules):
    cfg=config(start,seconds=1500,research_execution_delay_seconds=300,
               research_execution_delay_scope='close_only')
    market=[replace(r,open=D(200),high=D(200),low=D(200),close=D(200))
        if isinstance(r,Mark) and r.symbol=='BTCUSDT' and r.available_at>=start+300*SECOND
        else r for r in rows(start,1500)]
    result=CloseAt240(cfg,rules).run(market)
    fills=[f for f in result.fills if f['symbol']=='BTCUSDT']
    assert [(f['purpose'],(f['time_ns']-start)//SECOND) for f in fills]==[
        ('open_spot',120),('open_perp',180),('liquidate',360),('close_spot',720)]
    assert any(r['purpose']=='close_perp' and r['status']=='cancelled' and
               r['time_ns']==start+300*SECOND for r in result.order_rows)
    assert next(f for f in fills if f['purpose']=='liquidate')['delay_applied_seconds']==0
    assert result.ledger.positions['BTCUSDT'].short==0


@pytest.mark.parametrize('cancel_second,expected_fill',[(90,False),(120,False),(150,True)])
def test_cancellation_boundaries_follow_base_policy_during_delay(start,rules,cancel_second,expected_fill):
    class Cancel(Backtest):
        def process(self,time_ns,records,native):
            super().process(time_ns,records,native)
            if time_ns==self.start+cancel_second*SECOND:
                assert self._pending('BTCUSDT')
                assert self.reservations['BTCUSDT']>0
                self._close('BTCUSDT','fixture_cancel')
    cfg=config(start,seconds=900,research_execution_delay_seconds=60)
    market=rows(start,900)
    if cancel_second%60:
        t=start+cancel_second*SECOND
        market.append(Mark('BTCUSDT',t-60*SECOND,t-1,t,D('100.3'),D('100.3'),D('100.3'),D('100.3')))
    result=Cancel(cfg,rules).run(sorted(market,key=event_key))
    fills=[f for f in result.fills if f['symbol']=='BTCUSDT' and f['purpose']=='open_spot']
    assert bool(fills)==expected_fill
    assert result.ledger.positions['BTCUSDT'].short==0
    assert result._spot_is_dust('BTCUSDT')


def test_delayed_correction_cannot_extend_preventive_deadline(start,rules):
    cfg=config(start,seconds=1200,research_execution_delay_seconds=300)
    result=Backtest(cfg,rules)
    result.now=start-1
    result.resuming=True
    result.pairs['BTCUSDT'].state=State.HOLDING
    for market,side,q in [('spot','BUY',D(1)),('futures','SELL',D('.979'))]:
        result.ledger.apply_fill(Fill('seed-'+market,'seed-'+market,'BTCUSDT',market,side,q,
            D('100.3'),D('100.3'),start-1,'synthetic',D(0)),
            rules.items['BTCUSDT',market],D('100.3'))
    result.run(sorted(bars(start,range(0,1201,60)),key=event_key))
    correction=next(r for r in result.order_rows if r['purpose']=='correct' and r['action']=='submitted')
    assert correction['window_start']==start+300*SECOND
    assert any(r['purpose']=='correct' and r['status']=='cancelled' and
        r['time_ns']==start+60*SECOND for r in result.order_rows)
    assert not any(f['purpose']=='correct' for f in result.fills)
    assert any(r.get('cause')=='hedge_correction_deadline' and r['time_ns']==start+60*SECOND
               for r in result.risk_events)


def test_ohlc4_fill_is_distinct_from_unchanged_closed_signal_and_future_sizing(start,rules):
    cfg=config(start,seconds=600,research_minute_price_model='ohlc4')
    market=[replace(r,open=D(100),high=D(110),low=D(90),close=D(104),
                    base_volume=D(10),quote_volume=D(1020))
        if isinstance(r,MinuteBar) and r.symbol=='BTCUSDT' and r.market=='spot'
        and r.end_time==start+120*SECOND else r for r in rows(start,600)]
    result=Backtest(cfg,rules).run(market,stop_at=start+120*SECOND)
    fill=next(f for f in result.fills if f['symbol']=='BTCUSDT')
    assert D(fill['reference_price'])==101 and D(fill['price'])==D('101.02')
    assert D(fill['window_vwap'])==102 and D(fill['window_ohlc4'])==101
    assert fill['reference_price_model']=='ohlc4'
    assert result.closed_bars['BTCUSDT','spot'].price==104
    baseline=Backtest(config(start),rules).run(rows(start,600),stop_at=start+60*SECOND)
    order=next(o for o in result.order_rows if o['action']=='submitted')
    assert order['quantity']==baseline.order_rows[0]['quantity']


def test_checkpoint_pending_delay_and_exclusive_end_preserve_inventory(start,rules,tmp_path):
    cfg=config(start,seconds=780,research_execution_delay_seconds=300)
    market=rows(start,780)
    whole=Backtest(cfg,rules).run(market)
    partial=Backtest(cfg,rules).run(market,stop_at=start+180*SECOND)
    checkpoint=tmp_path/'pending.json'
    partial.checkpoint(checkpoint)
    restored=Backtest.load_checkpoint(checkpoint,cfg,rules).run(market)
    assert restored.fills==whole.fills
    assert restored.order_rows==whole.order_rows
    assert restored.ledger.rows==whole.ledger.rows
    assert not any(f['time_ns']>=start+780*SECOND for f in whole.fills)
    assert whole.ledger.positions['BTCUSDT'].short==0
    assert whole.ledger.positions['BTCUSDT'].spot>0
    assert any(o.status=='pending' and o.window_end==start+780*SECOND for o in whole.orders.values())


def test_invalid_ohlc_in_delayed_vwap_halts_before_any_inventory_mutation(start,rules):
    cfg=config(start,seconds=600,research_execution_delay_seconds=60)
    market=[replace(r,high=D(99)) if isinstance(r,MinuteBar) and r.symbol=='BTCUSDT'
            and r.market=='spot' and r.end_time==start+180*SECOND else r for r in rows(start,600)]
    result=Backtest(cfg,rules).run(market)
    assert result.status=='incomplete_data'
    assert not result.fills
    assert result.ledger.positions['BTCUSDT'].spot==0
    assert any('OHLC' in reason for reason in result.reasons)


@pytest.mark.parametrize('changes',[
    {'research_minute_price_model':'ohlc4'}, {'research_execution_delay_seconds':60},
    {'research_execution_delay_seconds':300},
    {'research_execution_delay_seconds':900,'research_execution_delay_scope':'close_only'},
])
def test_execution_options_preserve_market_opportunity_and_forecast_inputs(start,rules,changes):
    market=rows(start)
    baseline=Backtest(config(start,seconds=3000),rules).run(market)
    variant=Backtest(config(start,seconds=3000,**changes),rules).run(market)
    assert variant.opportunities==baseline.opportunities
    assert variant.all_funding==baseline.all_funding
    columns=('symbol','anchor','history_start','forecast','no_change','valid','basis')
    assert [[r[k] for k in columns] for r in variant.signals]==[
        [r[k] for k in columns] for r in baseline.signals]


@pytest.mark.parametrize('delay',[0,300])
def test_partial_committed_close_retries_as_liquidation_after_escalation(start,rules,delay):
    cfg=config(start,seconds=1800,research_execution_delay_seconds=delay,
               research_execution_delay_scope='close_only')
    risk_second,end_second=270+delay,300+delay
    market=[replace(r,open=D(200),high=D(200),low=D(200),close=D(200))
        if isinstance(r,Mark) and r.symbol=='BTCUSDT' and r.available_at>=start+risk_second*SECOND
        else r for r in rows(start,1800)]
    market=[replace(r,base_volume=D(1000),quote_volume=D(100300))
        if isinstance(r,MinuteBar) and r.symbol=='BTCUSDT' and r.market=='futures'
        and r.end_time==start+end_second*SECOND else r for r in market]
    t=start+risk_second*SECOND
    market.append(Mark('BTCUSDT',t-60*SECOND,t-1,t,D(200),D(200),D(200),D(200)))
    result=CloseAt240(cfg,rules).run(sorted(market,key=event_key))
    retry=next(r for r in result.order_rows if r['symbol']=='BTCUSDT'
        and r['action']=='submitted' and r['submitted_at']==start+end_second*SECOND)
    assert retry['purpose']=='liquidate'
    assert retry['window_start']==start+end_second*SECOND
    assert retry['delay_applied_seconds']==0
    assert any(f['liquidation'] and f['time_ns']==start+(end_second+60)*SECOND
               for f in result.fills if f['symbol']=='BTCUSDT')
    assert result.ledger.positions['BTCUSDT'].short==0
    assert result.ledger.positions['BTCUSDT'].liquidation_fees>0


def test_partial_correction_cannot_restore_holding_after_liquidation(start,rules):
    cfg=config(start,seconds=300,research_execution_delay_scope='close_only',
               research_execution_delay_seconds=300)
    result=Backtest(cfg,rules)
    result.now=start-1
    result.resuming=True
    result.pairs['BTCUSDT'].state=State.HOLDING
    for market,side,q in [('spot','BUY',D(1)),('futures','SELL',D('.979'))]:
        result.ledger.apply_fill(Fill('seed-'+market,'seed-'+market,'BTCUSDT',market,side,q,
            D('100.3'),D('100.3'),start-1,'synthetic',D(0)),
            rules.items['BTCUSDT',market],D('100.3'))
    market=[replace(r,base_volume=D('1.7'),quote_volume=D('170.51'))
        if isinstance(r,MinuteBar) and r.symbol=='BTCUSDT' and r.market=='futures'
        and r.end_time==start+60*SECOND else r for r in bars(start,range(0,301,60))]
    market=[replace(r,open=D(200),high=D(200),low=D(200),close=D(200))
        if isinstance(r,Mark) and r.symbol=='BTCUSDT' and r.available_at>=start+30*SECOND
        else r for r in market]
    t=start+30*SECOND
    market.append(Mark('BTCUSDT',t-60*SECOND,t-1,t,D(200),D(200),D(200),D(200)))
    result.run(sorted(market,key=event_key))
    assert any(r['action']=='submitted' and r['purpose']=='liquidate' and
               r['submitted_at']==start+60*SECOND for r in result.order_rows)
    assert not any(r.get('cause')=='hedge_corrected' and r['time_ns']>=t
                   for r in result.risk_events)


def test_zero_fill_reduction_cannot_restore_holding_after_liquidation(start,rules):
    class ReduceAtStart(Backtest):
        def process(self,time_ns,records,native):
            super().process(time_ns,records,native)
            if time_ns==start:
                self.pairs['BTCUSDT'].state=State.REBALANCING
                self._submit('BTCUSDT','futures','BUY',D('.5'),'reduce_perp')

    cfg=config(start,seconds=300,research_execution_delay_seconds=300,
               research_execution_delay_scope='close_only')
    result=ReduceAtStart(cfg,rules)
    result.now=start-1
    result.resuming=True
    result.pairs['BTCUSDT'].state=State.HOLDING
    for market,side in [('spot','BUY'),('futures','SELL')]:
        result.ledger.apply_fill(Fill('seed-'+market,'seed-'+market,'BTCUSDT',market,side,D(1),
            D('100.3'),D('100.3'),start-1,'synthetic',D(0)),rules.items['BTCUSDT',market],D('100.3'))
    market=[replace(r,base_volume=D(0),quote_volume=D(0),trade_count=0)
        if isinstance(r,MinuteBar) and r.symbol=='BTCUSDT' and r.market=='futures'
        and r.end_time==start+60*SECOND else r for r in bars(start,range(0,301,60))]
    t=start+30*SECOND
    market=[replace(r,open=D(200),high=D(200),low=D(200),close=D(200))
        if isinstance(r,Mark) and r.symbol=='BTCUSDT' and r.available_at>=t else r for r in market]
    market.append(Mark('BTCUSDT',t-60*SECOND,t-1,t,D(200),D(200),D(200),D(200)))
    result.run(sorted(market,key=event_key))
    assert not any(r['purpose']=='reduce_perp' for r in result.fills)
    assert any(r['purpose']=='liquidate' and r['submitted_at']==start+60*SECOND
               and r['action']=='submitted' for r in result.order_rows)
    assert not any(r.get('cause')=='rebalance_first_leg_failed' and r['time_ns']>=t for r in result.risk_events)
