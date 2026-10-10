"""Deterministic old/current-code controls; never counted as sensitivities."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from time import monotonic


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--code-root", type=Path, required=True)
    p.add_argument("--data-root", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--fixed", action="store_true")
    args = p.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    sys.path.insert(0, str(args.code_root / "src"))
    sys.path.insert(1, str(Path(__file__).resolve().parents[1]))
    from crypto_carry.config import Config, timestamp
    from crypto_carry.data.prescribed import prescribed_rules
    from crypto_carry.data.replay import iter_records
    from crypto_carry.mark_gap_study import GapAuditedBacktest
    from crypto_carry.reporting import _plain
    from scripts.run_signal_sensitivity import peak_memory_bytes

    base = Config.load(args.data_root / "outputs/run_ad71d751b20623006c195ff3/effective_config.toml")
    windows = [("2022-01-01", "2022-01-15", "realized"),
               ("2024-03-01", "2024-03-15", "realized")]
    if not args.fixed:
        windows += [("2024-03-01", "2024-03-15", "base_e3"),
                    ("2023-03-20", "2023-03-26", "base_e3_promo")]
    output = []
    for start, end, mode in windows:
        changes = dict(start=start+"T00:00:00Z", end=end+"T00:00:00Z")
        if mode == "base_e3_promo":
            changes.update(research_decision_fee_mode="base_e3",
                           research_spot_fee_schedule="btc_promo_2022_2023")
        else:
            changes["research_decision_fee_mode"] = "base_e3_total" if args.fixed else mode
        config = base.changed(**changes)
        for strategy in ("conditional", "permanent"):
            began = monotonic()
            backtest = GapAuditedBacktest(config, prescribed_rules(config), strategy,
                                          strategy == "conditional")
            backtest.run(iter_records(args.data_root, timestamp(config.start), timestamp(config.end),
                         config.window_hours+24, data_dir=config.data_dir,
                         execution_model=config.execution_model, include_closed_bars=True,
                         mark_gap_method=config.mark_gap_method))
            fields = {k: _plain(getattr(backtest, k)) for k in (
                "daily", "fills", "order_rows", "positions", "signals", "risk_events",
                "opportunities", "renewal_diagnostics", "durations", "all_funding",
                "native_fill_count", "native_reconciliation_count", "status", "reasons")}
            fields["ledger"] = _plain(backtest.ledger.rows)
            fields["funding_payments"] = _plain(backtest.ledger.funding_rows)
            # Only newly declared metadata, not costs/components or economics.
            excluded = {"decision_fee_mode", "scenario_spot_taker_fee", "scenario_futures_taker_fee",
                        "scenario_slippage_per_order"} if args.fixed else set()
            for row in fields["signals"] + fields["renewal_diagnostics"]:
                for k in excluded:
                    row.pop(k, None)
            def digest(value):
                return hashlib.sha256(json.dumps(value, sort_keys=True,
                                                  separators=(",", ":")).encode()).hexdigest()
            result = dict(window=[start, end], mode=mode, fixed=args.fixed, strategy=strategy,
                          config_digest=config.digest(), config_dict=config.to_dict(),
                          seconds=monotonic()-began, peak_bytes=peak_memory_bytes(),
                          excluded_metadata=sorted(excluded), fills=len(backtest.fills),
                          status=backtest.status,
                          reconciliation=str(backtest.ledger.reconcile(backtest.spot_prices(),
                                             backtest.mark_prices())["difference"]),
                          digests={k: digest(v) for k, v in fields.items()})
            output.append(result)
            print(start, mode, strategy, "fills", result["fills"], "seconds", result["seconds"], flush=True)
    args.output.write_text(json.dumps(output, indent=2)+"\n", encoding="utf8")


if __name__ == "__main__":
    main()
