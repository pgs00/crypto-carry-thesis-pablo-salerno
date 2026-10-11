"""One approved B6 portfolio per process, using the corrected standard engine."""

import argparse
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

for _key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_key] = "1"
os.environ.update(PYTHONDONTWRITEBYTECODE="1", MPLBACKEND="Agg", PYTHONIOENCODING="utf-8")
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

import pyarrow as pa  # noqa: E402

from crypto_carry.config import Config, timestamp  # noqa: E402
from crypto_carry.data.prescribed import research_assumptions  # noqa: E402
from crypto_carry.reporting import _code_identity, verify_run, write_run  # noqa: E402
from scripts.continuous_delivery.portfolio import financial_daily  # noqa: E402
from scripts.run_signal_sensitivity import peak_memory_bytes  # noqa: E402
from scripts.stability_uncertainty_contract import (  # noqa: E402
    BASES,
    STARTS,
    THREAD_ENV,
    read,
    save,
    sha,
    simulate,
    validate_variant,
    verify_contract,
)

pa.set_cpu_count(1)
pa.set_io_thread_count(1)


def run_inputs(candidate):
    return dict(
        read(candidate / "input_hashes.json"),
        b6_protocol_sha256=sha(candidate / "protocolo_ejecucion.json"),
    )


def validate_completed(state, candidate, data_root, scenario, strategy):
    protocol = verify_contract(candidate)
    cfg = Config.load(candidate / "configuraciones" / f"{scenario}.toml")
    validate_variant(
        Config.load(data_root / "outputs" / BASES[strategy] / "effective_config.toml"),
        scenario,
        cfg,
    )
    path = Path(state["path"])
    manifest = read(path / "run_manifest.json")
    if (
        state["status"] != "ejecutado"
        or manifest["run_id"] != state["run_id"]
        or manifest["config"] != cfg.to_dict()
        or manifest["code_hash"] != protocol["engine_code_hash"]
        or manifest["input_hashes"] != run_inputs(candidate)
        or manifest["label"] != f"E4-estabilidad-{scenario}"
        or manifest["strategies"]
        != [dict(strategy=strategy, funding_filter_enabled=strategy == "conditional")]
        or manifest["status"] not in {"complete", "insolvent"}
        or sha(path / "run_manifest.json") != state["manifest_sha256"]
        or not verify_run(path)["valid"]
    ):
        raise ValueError("Incompatible or corrupt completed B6 portfolio")
    return state


def run_one(candidate, data_root, raw_root, scenario, strategy):
    import msvcrt

    if scenario not in STARTS or strategy not in BASES:
        raise ValueError("Outside closed B6 matrix")
    protocol = verify_contract(candidate)
    state_path = candidate / "ejecuciones" / f"{scenario}__{strategy}.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    # OS lock survives neither worker death nor process termination; PID reuse cannot own it.
    lock = (state_path.parent / f"{scenario}__{strategy}.lock").open("a+b")
    if lock.tell() == 0:
        lock.write(b"0")
        lock.flush()
    lock.seek(0)
    try:
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        raise RuntimeError("Portfolio already has an active writer") from None
    try:
        if state_path.exists():
            previous = read(state_path)
            if previous.get("status") == "ejecutado":
                return validate_completed(previous, candidate, data_root, scenario, strategy)
            raise ValueError(
                "Incomplete attempt preserved; no compatible complete checkpoint. Explicit recovery required"
            )
        cfg = Config.load(candidate / "configuraciones" / f"{scenario}.toml")
        validate_variant(
            Config.load(data_root / "outputs" / BASES[strategy] / "effective_config.toml"),
            scenario,
            cfg,
        )
        attempt = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        state = dict(
            scenario=scenario,
            strategy=strategy,
            status="en_ejecucion",
            pid=os.getpid(),
            attempt=attempt,
            started_utc=datetime.now(UTC).isoformat(),
            config_hash=cfg.digest(),
            code_hash=protocol["engine_code_hash"],
            thread_environment=THREAD_ENV,
            arrow_cpu_count=pa.cpu_count(),
            arrow_io_thread_count=pa.io_thread_count(),
        )
        save(state_path, state)
        started = time.monotonic()
        try:
            inputs = run_inputs(candidate)
            backtest = simulate(cfg, data_root, strategy, inputs)
            replay_seconds = time.monotonic() - started
            if backtest.status not in {"complete", "insolvent"}:
                raise ValueError("Unfinished economic state: " + backtest.status)
            if backtest.status == "complete" and backtest.now != timestamp(cfg.end) - 1:
                raise ValueError("Exclusive economic end not reached")
            difference = backtest.ledger.reconcile(backtest.spot_prices(), backtest.mark_prices())[
                "difference"
            ]
            if abs(difference) > cfg.accounting_tolerance:
                raise ArithmeticError("Ledger reconciliation failed")
            daily, _ = financial_daily(backtest.daily, cfg)
            verify_contract(candidate)
            quality = read(data_root / "outputs" / BASES[strategy] / "data_quality.json")
            quality["research_assumptions"] = research_assumptions(cfg)
            quality["reused_market_validation"] = dict(
                run_id=BASES[strategy],
                input_hashes_verified=True,
                scope="Same authenticated market inputs; economic start differs; 360h funding preload",
            )
            path = write_run(
                data_root,
                cfg,
                [backtest],
                quality,
                "historical_assumptions",
                label=f"E4-estabilidad-{scenario}",
                inputs=inputs,
                output_root=raw_root / scenario / strategy / attempt,
            )
            if _code_identity()[0] != protocol["engine_code_hash"]:
                raise ValueError("Economic code changed during materialization")
            state.update(
                status="ejecutado",
                engine_status=backtest.status,
                run_id=path.name,
                path=str(path),
                manifest_sha256=sha(path / "run_manifest.json"),
                replay_seconds=replay_seconds,
                total_seconds=time.monotonic() - started,
                peak_process_bytes=peak_memory_bytes(),
                final_equity=str(backtest.equity()),
                ledger_difference=str(difference),
                daily_reconciled=len(daily),
                max_daily_residual=str(
                    max((abs(r["reconciliation_residual_usdt"]) for r in daily), default=0)
                ),
                fills=len(backtest.fills),
                native_fills=backtest.native_fill_count,
                finished_utc=datetime.now(UTC).isoformat(),
            )
            save(state_path, state)
            print(f"COMPLETE {scenario}/{strategy} {path.name}", flush=True)
            return state
        except Exception as exc:
            save(state_path, dict(state, status="fallido", reason=f"{type(exc).__name__}: {exc}"))
            raise
    finally:
        lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
        lock.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--data-root", default=Path("D:/Backtesting"), type=Path)
    parser.add_argument("--raw-root", required=True, type=Path)
    parser.add_argument("--scenario", choices=tuple(STARTS), required=True)
    parser.add_argument("--strategy", choices=tuple(BASES), required=True)
    args = parser.parse_args()
    run_one(
        args.candidate.resolve(),
        args.data_root.resolve(),
        args.raw_root.resolve(),
        args.scenario,
        args.strategy,
    )
