"""Independent expectations for the authorized execution-price/delay contract."""

from dataclasses import replace
from decimal import Decimal as D
from pathlib import Path

import pytest

from crypto_carry import execution
from crypto_carry.config import SECOND, Config, timestamp
from crypto_carry.models import MinuteBar

BASE = Path(__file__).resolve().parents[2] / 'configs/entrega_4/reglas_historicas/BASE_E3.toml'


def test_defaults_preserve_base_canonical_and_digest():
    base = Config.load(BASE)
    cfg = base.changed(research_minute_price_model='vwap',
                       research_execution_delay_seconds=0,
                       research_execution_delay_scope='all_client')
    assert cfg.to_dict() == base.to_dict()
    assert cfg.digest() == base.digest()
    assert not any(k.startswith('research_execution') for k in cfg.to_dict())


@pytest.mark.parametrize('changes', [
    {'research_execution_delay_seconds': -1},
    {'research_execution_delay_seconds': True},
    {'research_execution_delay_seconds': 1.5},
    {'research_execution_delay_scope': 'liquidate'},
    {'research_minute_price_model': 'open'},
    {'research_minute_price_model': 'ohlc4', 'execution_model': 'first_trade'},
])
def test_rejects_invalid_or_unapproved_execution_routes(changes):
    with pytest.raises(ValueError):
        Config.load(BASE).changed(**changes)


@pytest.mark.parametrize('purpose', ['open_spot', 'open_perp', 'increase_spot',
    'increase_perp', 'reduce_perp', 'reduce_spot', 'correct', 'close_perp', 'close_spot',
    'liquidate'])
@pytest.mark.parametrize('scope', ['all_client', 'close_only'])
def test_purpose_classification_excludes_liquidations(purpose, scope):
    cfg = Config.load(BASE).changed(research_execution_delay_seconds=300,
                                   research_execution_delay_scope=scope)
    expected = 0 if purpose == 'liquidate' or (scope == 'close_only' and
        purpose not in ('close_perp', 'close_spot')) else 300
    assert execution.order_delay_seconds(cfg, purpose) == expected
    with pytest.raises(ValueError, match='purpose'):
        execution.order_delay_seconds(cfg, 'unknown_client_category')


@pytest.mark.parametrize('offset,delay,want_start,want_end', [
    (20*SECOND,60,120,180), (0,60,60,120), (0,0,0,60),
    (1,60,120,180), (-1,60,60,120), (20*SECOND,300,360,420),
    (20*SECOND,900,960,1020),
])
def test_eligibility_and_single_window_nanosecond_boundaries(offset,delay,want_start,want_end):
    origin = timestamp('2024-01-01T12:00:00Z')
    cfg = Config.load(BASE).changed(research_execution_delay_seconds=delay)
    meta = execution.order_execution_metadata(cfg, 'close_spot', origin+offset)
    assert meta['eligible_at'] == origin+offset+delay*SECOND
    assert execution.minute_window(meta['eligible_at']) == (
        origin+want_start*SECOND, origin+want_end*SECOND)


def test_ohlc4_has_its_own_reference_without_mutating_close_or_volumes():
    b = MinuteBar('BTCUSDT','spot',0,60*SECOND,60*SECOND,
                  D(100),D(110),D(90),D(104),D(10),D(1020),10)
    assert hasattr(execution, 'minute_ohlc4')
    assert execution.minute_ohlc4(b) == D(101)
    assert execution.minute_vwap(b) == D(102)
    assert b.price == D(104) and b.quote_volume == D(1020)
    assert execution.minute_ohlc4(replace(b, base_volume=D(0), quote_volume=D(0), trade_count=0)) is None
    for changed in ({'open':D(111)}, {'low':D(105)}, {'close':D(0)}, {'high':D('NaN')}):
        with pytest.raises(ValueError, match='OHLC'):
            execution.minute_ohlc4(replace(b, **changed))


def test_matrix_is_closed_and_derived_without_other_economic_changes():
    from scripts.execution_delays import CHANGES, scenario_configs, validate_variant
    base = Config.load(BASE)
    assert set(CHANGES) == {'E_OHLC4','L01','L05','LC01','LC05','LC15'}
    for name, cfg in scenario_configs(base).items():
        validate_variant(base, name, cfg)
        assert cfg.research_decision_fee_mode == base.research_decision_fee_mode
        for changed in ({'cost_multiplier':D(2)}, {'capital':D(50000)},
                        {'horizon_hours':72}, {'research_decision_fee_mode':'base_e3_total'}):
            with pytest.raises(ValueError, match='Unauthorized'):
                validate_variant(base, name, cfg.changed(**changed))
    with pytest.raises(ValueError):
        validate_variant(base, 'L15', base)
    with pytest.raises(ValueError):
        validate_variant(base, 'E_OHLC4', base.changed(research_minute_price_model='ohlc4',
                                                     research_execution_delay_seconds=60))
