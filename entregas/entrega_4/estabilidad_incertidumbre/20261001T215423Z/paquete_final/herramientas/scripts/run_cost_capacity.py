"""Execute only the authorized block-3 portfolios with per-run resumable records."""

from __future__ import annotations

import argparse
import ctypes
import gc
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from crypto_carry.config import Config, timestamp  # noqa: E402
from crypto_carry.data.prescribed import research_assumptions  # noqa: E402
from crypto_carry.reporting import _code_identity, verify_run, write_run  # noqa: E402
from scripts.cost_capacity_guards import (  # noqa: E402
    export_attempt_h3,
    validate_resume,
    verify_input_root,
)

if __package__:
    from .cost_capacity import BASES, CHANGES, STAGES, simulate, validate_variant
    from .run_historical_rules_sensitivity import digest, read, save, writer_lock
else:
    from run_historical_rules_sensitivity import digest, read, save, writer_lock

    from scripts.cost_capacity import (
        BASES,
        CHANGES,
        STAGES,
        simulate,
        validate_variant,
    )

PROJECT = Path(__file__).resolve().parents[1]


def peak_memory_bytes():
    if os.name != "nt":
        import resource
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024

    class Counters(ctypes.Structure):
        _fields_ = [("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong)] + [
            (name, ctypes.c_size_t) for name in (
                "PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
                "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage", "QuotaNonPagedPoolUsage",
                "PagefileUsage", "PeakPagefileUsage")]

    counters = Counters()
    counters.cb = ctypes.sizeof(counters)
    handle = ctypes.windll.kernel32.GetCurrentProcess
    handle.restype = ctypes.c_void_p
    get_memory = ctypes.windll.psapi.GetProcessMemoryInfo
    get_memory.argtypes = [ctypes.c_void_p, ctypes.POINTER(Counters), ctypes.c_ulong]
    if not get_memory(handle(), ctypes.byref(counters), counters.cb):
        raise OSError("Cannot measure process peak memory")
    return int(counters.PeakWorkingSetSize)


def load_contract(package, data_root, scenario):
    seal = read(package / "protocolo_previo.json")
    if _code_identity()[0] != seal["engine_code_hash"]:
        raise ValueError("Economic code differs from frozen execution identity")
    for name, sha in seal["project_files"].items():
        if digest(PROJECT / name) != sha:
            raise ValueError(f"Predeclared file changed: {name}")
    for name, sha in seal["package_files"].items():
        if digest(package / name) != sha:
            raise ValueError(f"Predeclared package file changed: {name}")
    if not read(package / "control_compatibilidad.json")["passed"]:
        raise ValueError("Compatibility control has not passed")
    base = Config.load(data_root / "outputs" / BASES["conditional"] / "effective_config.toml")
    config = Config.load(package / "configuraciones" / f"{scenario}.toml")
    validate_variant(base, scenario, config)
    inputs = dict(verify_input_root(package, data_root, base),
                  cost_capacity_protocol_sha256=digest(package / "protocolo_previo.json"))
    return config, inputs


def run_one(package, data_root, raw_root, scenario, strategy):
    # OS-backed lock is released even on process death. Other invocations wait,
    # then authenticate and reuse the completed pair rather than racing it.
    with writer_lock(package / f"pair-{scenario}-{strategy}"):
        return _run_one(package, data_root, raw_root, scenario, strategy)


def _run_one(package, data_root, raw_root, scenario, strategy):
    config, inputs = load_contract(package, data_root, scenario)
    code = _code_identity()[0]
    state_path = package / "ejecuciones" / f"{scenario}__{strategy}.json"
    if state_path.exists():
        prior = read(state_path)
        if prior.get("status") == "ejecutado":
            path = Path(prior["path"])
            validate_resume(prior, read(path / "run_manifest.json"), config, code, inputs,
                            scenario, strategy, {digest(p): read(p) for p in
                            package.glob("protocolo_previo*.json")})
            if (not verify_run(path)["valid"]
                    or digest(path / "run_manifest.json") != prior["manifest_sha256"]):
                raise ValueError(f"Corrupt completed run: {path}")
            print(f"RESUMED VERIFIED {scenario}/{strategy}", flush=True)
            return prior
    attempt = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    state = dict(scenario=scenario, strategy=strategy, status="en_ejecucion", attempt=attempt,
                 started_utc=datetime.now(UTC).isoformat(), config_hash=config.digest(),
                 code_hash=code, pid=os.getpid())
    if state_path.exists():
        prior_state = package / "ejecuciones" / f"{scenario}__{strategy}__prior_{attempt}.json"
        prior_state.write_bytes(state_path.read_bytes())
    save(state_path, state)
    started = time.monotonic()
    print(f"START {scenario}/{strategy} {attempt}", flush=True)
    try:
        backtest = simulate(config, data_root, strategy, inputs)
        replay_seconds = time.monotonic() - started
        if code != _code_identity()[0]:
            raise ValueError("Economic source changed during replay")
        if backtest.status not in {"complete", "insolvent"}:
            raise ValueError(f"Unfinished portfolio: {backtest.status}: {backtest.reasons}")
        if backtest.status == "complete" and backtest.now != timestamp(config.end)-1:
            raise ValueError("Replay did not reach exclusive financial end")
        difference = backtest.ledger.reconcile(
            backtest.spot_prices(), backtest.mark_prices())["difference"]
        if abs(difference) > config.accounting_tolerance:
            raise ArithmeticError(f"Final reconciliation failed: {difference}")
        # Validate each daily close before materializing or interpreting this run.
        if __package__:
            from .continuous_delivery.portfolio import financial_daily
        else:
            from continuous_delivery.portfolio import financial_daily
        daily, _ = financial_daily(backtest.daily, config)
        if any(Decimal(r["estimated_cycle_cost"]) != Decimal(".0034")
               for r in backtest.signals if r.get("estimated_cycle_cost") is not None):
            raise ValueError("Entry diagnostics do not retain 34 bp selection cost")
        for fill in backtest.fills:
            nominal = Decimal(".001") if fill["market"] == "spot" else Decimal(".0005")
            if Decimal(fill["fee_rate"]) != nominal * config.cost_multiplier:
                raise ValueError("Realized fee differs from the authorized scenario")
            if not fill.get("liquidation") and Decimal(fill["slippage_rate"]) != config.slippage * config.cost_multiplier:
                raise ValueError("Realized slippage differs from the authorized scenario")
        peak_replay = peak_memory_bytes()
        print(f"REPLAY_COMPLETE seconds={replay_seconds:.2f} peak_bytes={peak_replay}", flush=True)
        quality = read(data_root / "outputs" / BASES[strategy] / "data_quality.json")
        quality["research_assumptions"] = research_assumptions(config)
        quality["reused_market_validation"] = dict(
            run_id=BASES[strategy], input_hashes_verified=True,
            scope="Identical market inputs, original 360h warmup and futures_scaled derivation")
        with writer_lock(package):
            run = write_run(data_root, config, [backtest], quality, "historical_assumptions",
                            label=f"E4-costos-capacidad-{scenario}", inputs=inputs,
                            output_root=raw_root / scenario / strategy / attempt)
            h3_path = export_attempt_h3(package, attempt, run.name, scenario, strategy,
                                        backtest.opportunities)
        if code != _code_identity()[0]:
            raise ValueError("Economic source changed during materialization")
        result = dict(state, status="ejecutado", engine_status=backtest.status,
                      run_id=run.name, path=str(run), manifest_sha256=digest(run/"run_manifest.json"),
                      replay_seconds=replay_seconds, total_seconds=time.monotonic()-started,
                      peak_replay_bytes=peak_replay, peak_process_bytes=peak_memory_bytes(),
                      final_equity=str(backtest.equity()), ledger_difference=str(difference),
                      daily_reconciled=len(daily), max_daily_residual=str(max(
                          (abs(r["reconciliation_residual_usdt"]) for r in daily), default=0)),
                      fills=len(backtest.fills), native_fills=backtest.native_fill_count,
                      h3_path=str(h3_path), h3_sha256=digest(h3_path),
                      finished_utc=datetime.now(UTC).isoformat())
        save(state_path, result)
        print(json.dumps(result), flush=True)
        return result
    except Exception as exc:
        save(state_path, dict(state, status="fallido", engine_status="technical_failure",
                              reason=f"{type(exc).__name__}: {exc}"))
        raise


def batch(package, data_root, raw_root, stage, workers):
    scenarios = STAGES[stage]
    tasks = [(s, strategy) for s in scenarios for strategy in BASES]
    active, finished = [], []
    logs = package / "logs_corridas"
    logs.mkdir(exist_ok=True)
    while tasks or active:
        while tasks and len(active) < workers:
            scenario, strategy = tasks.pop(0)
            token = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
            log_path = logs / f"{scenario}__{strategy}__{token}.txt"
            log = log_path.open("x", encoding="utf-8")
            command = [sys.executable, "-B", "-u", "-X", "utf8", str(Path(__file__).resolve()),
                       "--package", str(package), "--data-root", str(data_root),
                       "--raw-root", str(raw_root), "--scenario", scenario, "--strategy", strategy]
            child = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "MPLBACKEND": "Agg"})
            active.append((child, log, scenario, strategy, command, str(log_path)))
            print(f"LAUNCHED {scenario}/{strategy} pid={child.pid}", flush=True)
        for job in list(active):
            child, log, scenario, strategy, command, log_path = job
            if child.poll() is None:
                continue
            log.close()
            active.remove(job)
            path = package / "ejecuciones" / f"{scenario}__{strategy}.json"
            record = read(path) if path.exists() else dict(
                scenario=scenario, strategy=strategy, status="fallido", reason="No result")
            record.update(command=command, log=log_path, exit_code=child.returncode)
            finished.append(record)
            save(package / f"etapa_{stage}.json", dict(stage=stage, runs=finished))
            print(f"FINISHED {scenario}/{strategy} exit={child.returncode}", flush=True)
            gc.collect()
        if active:
            time.sleep(2)
    return 0 if all(r["status"] == "ejecutado" and r["exit_code"] == 0 for r in finished) else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", required=True, type=Path)
    parser.add_argument("--data-root", required=True, type=Path)
    parser.add_argument("--raw-root", required=True, type=Path)
    parser.add_argument("--stage", choices=tuple(STAGES))
    parser.add_argument("--scenario", choices=tuple(CHANGES))
    parser.add_argument("--strategy", choices=tuple(BASES))
    parser.add_argument("--workers", type=int, choices=(1, 2), default=1)
    args = parser.parse_args()
    package, data, raw = args.package.resolve(), args.data_root.resolve(), args.raw_root.resolve()
    if args.scenario:
        if not args.strategy:
            parser.error("--scenario requires --strategy")
        run_one(package, data, raw, args.scenario, args.strategy)
        return 0
    if not args.stage:
        parser.error("Choose --stage or --scenario")
    return batch(package, data, raw, args.stage, args.workers)


if __name__ == "__main__":
    raise SystemExit(main())
