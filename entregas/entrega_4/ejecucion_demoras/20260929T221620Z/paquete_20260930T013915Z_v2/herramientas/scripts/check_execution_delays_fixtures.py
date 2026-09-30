"""Compare exact previous/current projections on deterministic native fixtures."""

import argparse
import hashlib
import inspect
import json
import sys
import tempfile
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--code-root', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    if a.output.exists():
        raise FileExistsError(a.output)
    root = Path(__file__).resolve().parents[1]
    sys.path[:0] = [str(a.code_root.resolve()/'src'), str(root/'tests'),
                    str(root/'tests/integration')]
    import test_next_minute_vwap as fixtures
    from conftest import FixedRules

    from crypto_carry.config import timestamp
    from crypto_carry.reporting import _plain
    from crypto_carry.strategy import Backtest

    samples = []
    original = Backtest.run

    def capture(self, *args, **kwargs):
        result = original(self, *args, **kwargs)
        values = {k: _plain(getattr(result,k)) for k in (
            'daily','fills','orders','order_rows','positions','signals','risk_events',
            'opportunities','renewal_diagnostics','durations','status','reasons','pairs',
            'reservations','native_fill_count','native_reconciliation_count')}
        values['ledger'] = _plain(result.ledger.rows)
        values['funding'] = _plain(result.ledger.funding_rows)
        samples.append(dict(config=result.config.to_dict(), config_digest=result.config.digest(),
            digests={k:hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':')).encode()).hexdigest()
                     for k,v in values.items()}, fills=len(result.fills),
            actions=sorted({r['action'] for r in result.order_rows}),
            purposes=sorted({r['purpose'] for r in result.order_rows})))
        return result

    Backtest.run = capture
    names = [
        'test_vwap_legs_fill_at_successive_window_ends_and_reconcile',
        'test_partial_first_leg_expires_then_unwinds_only_received_inventory',
        'test_funding_precedes_fill_at_the_same_timestamp',
        'test_cancellation_inside_committed_window_fills_then_unwinds_inventory',
        'test_partial_closing_order_retries_only_the_actual_remainder',
        'test_partial_correction_that_reaches_tolerance_is_not_closed_at_expiry',
        'test_committed_close_fills_before_simultaneous_liquidation_observation',
        'test_partitioned_and_checkpoint_replay_match_continuous',
    ]
    output = []
    with tempfile.TemporaryDirectory(prefix='execution_compat_fixture_') as tmp:
        for name in names:
            samples.clear()
            fn = getattr(fixtures,name)
            args = dict(start=timestamp('2024-01-01T00:00:00Z'),rules=FixedRules(),tmp_path=Path(tmp))
            fn(**{k:args[k] for k in inspect.signature(fn).parameters})
            output.append(dict(fixture=name, samples=list(samples)))
    a.output.write_text(json.dumps(output,indent=2)+'\n',encoding='utf8')
    print('Passed fixtures',len(output),'projections',sum(len(r['samples']) for r in output))


if __name__ == '__main__':
    main()
