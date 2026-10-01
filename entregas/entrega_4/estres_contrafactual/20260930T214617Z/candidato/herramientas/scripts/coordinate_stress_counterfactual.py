"""Small local coordinator for the existing frozen block-5 runner and delivery tools."""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

THREAD_ENV = {k: "1" for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS",
                              "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")}
os.environ.update(THREAD_ENV, PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8", MPLBACKEND="Agg")
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    # This coordinator is the sole writer of its progress file.
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    if path.name == "progreso_local.json":
        index_path = path.parent.parents[1] / "indice_versiones.json"
        index = json.loads(index_path.read_text(encoding="utf-8"))
        index.update(status=value["status"], coordinator_pid=value["pid"],
                     progress_path=path.as_posix(), economic_runs=len(value["completed"]) + sum(
                         r["scenario"] in ("SH_P90", "SH_MAX", "CF_SIN_INTERRUPCION") for r in value["reused"]),
                     economic_runs_in_progress=len(value["active"]),
                     reason="Local coordination; original economic code and approved assumptions unchanged")
        index_path.write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def resources():
    command = "$c=Get-CimInstance Win32_Processor; $m=Get-CimInstance Win32_OperatingSystem; "
    command += "[pscustomobject]@{physical=$c.NumberOfCores; logical=$c.NumberOfLogicalProcessors; "
    command += "cpu=$c.LoadPercentage; available_gib=$m.FreePhysicalMemory/1MB; "
    command += "total_gib=$m.TotalVisibleMemorySize/1MB; python=@(Get-CimInstance Win32_Process | "
    command += "Where-Object {$_.Name -match '^python'} | Select-Object ProcessId,ParentProcessId,WorkingSetSize)} "
    command += "| ConvertTo-Json -Compress -Depth 4"
    result = subprocess.check_output(["powershell", "-NoProfile", "-Command", command],
                                     creationflags=subprocess.CREATE_NO_WINDOW, text=True)
    return json.loads(result)


def workers_present():
    command = "@(Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^python' -and "
    command += "($_.CommandLine -match 'run_stress_counterfactual.py|coordinate_stress_counterfactual.py') } "
    command += "| Select-Object ProcessId,ParentProcessId,CommandLine) | ConvertTo-Json -Compress"
    result = subprocess.check_output(["powershell", "-NoProfile", "-Command", command],
                                     creationflags=subprocess.CREATE_NO_WINDOW, text=True).strip()
    parsed = json.loads(result or "[]")
    return parsed if isinstance(parsed, list) else [parsed]


def growth_reserve(active, processes):
    reserve = 0.0
    for job in active:
        ids = {job["process"].pid}
        for _ in range(len(processes)):
            ids.update(p["ProcessId"] for p in processes if p["ParentProcessId"] in ids)
        resident = sum(int(p["WorkingSetSize"] or 0) for p in processes if p["ProcessId"] in ids) / 2**30
        reserve += max(0, 4 - resident)
    return reserve


def worker(args):
    from scripts import run_stress_counterfactual as runner
    c = args.candidate.resolve()
    token = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    save(c / "controles/coordinacion_local" / f"{args.worker[0]}__{args.worker[1]}__{token}.json",
         dict(pid=os.getpid(), utc=datetime.now(UTC).isoformat(), thread_environment=THREAD_ENV,
              runner_file=str(Path(runner.__file__).resolve()),
              change="Only portfolio-specific writer lock; existing run_one and economic code unchanged"))
    original_lock = runner.writer_lock
    runner.writer_lock = lambda unused: original_lock(c / "parallel_replay" / "__".join(args.worker))
    runner.run_one(c, args.data_root.resolve(), args.raw_root.resolve(), *args.worker)


def coordinate(args):
    import msvcrt

    from scripts import run_stress_counterfactual as runner
    from scripts.return_capital.common import sha256

    c = args.candidate.resolve()
    control = c / "controles/coordinacion_local"
    control.mkdir(parents=True, exist_ok=True)
    lock_path = Path(tempfile.gettempdir()) / ("b5-coordinator-" + hashlib.sha256(str(c).encode()).hexdigest()[:16] + ".lock")
    lock = lock_path.open("a+b")
    if lock.tell() == 0:
        lock.write(b"0")
        lock.flush()
    lock.seek(0)
    try:
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        raise SystemExit("Another local coordinator owns the lock; no worker launched") from None
    other = [p for p in workers_present() if p["ProcessId"] not in (os.getpid(), os.getppid())]
    if other:
        raise RuntimeError("Existing worker/coordinator detected; preserve it and do not duplicate: " + str(other))
    frozen = runner.verify_contract(c)
    started = time.monotonic()
    progress = dict(pid=os.getpid(), started_utc=datetime.now(UTC).isoformat(), status="recovering",
                    engine_code_hash=frozen["engine_code_hash"], coordinator_sha256=sha256(Path(__file__)),
                    thread_environment=THREAD_ENV, reserve_gib=6, worker_budget_gib=4,
                    target_workers=4, maximum_workers=6, lock_path=str(lock_path), reused=[], completed=[], active=[], stages=[])
    progress_path = c / "progreso_local.json"
    save(progress_path, progress)
    tasks = []
    for scenario in runner.CONTROLS + runner.SCENARIOS:
        for strategy in runner.STRATEGIES:
            p = c / "ejecuciones" / f"{scenario}__{strategy}.json"
            state = runner.read(p) if p.exists() else {}
            if state.get("status") == "ejecutado":
                runner.validate_completed(state, c, args.data_root, scenario, strategy)
                progress["reused"].append(dict(scenario=scenario, strategy=strategy, run_id=state["run_id"],
                                               total_seconds=state["total_seconds"]))
            elif scenario in runner.CONTROLS:
                raise ValueError("An approved control is missing; no economic worker launched")
            else:
                tasks.append((scenario, strategy))
    runner.gate_controls(c, args.data_root, "SH_P90")
    save(control / "recuperacion.json", dict(progress, resources=resources(),
         previous_coordinator_or_workers_active=False, checkpoints_recovered=0,
         note="Interrupted permanent SH_P90 has no persisted checkpoint; its prior state and log are preserved"))
    active = []
    completed_fraction = 0.0
    last_sample = (time.monotonic(), 0.0)
    last_rate = None
    cap = 4
    last_increase = started
    try:
        while tasks or active:
            for job in active[:]:
                code = job["process"].poll()
                if code is not None:
                    job["stream"].close()
                    if code:
                        raise RuntimeError(f"Worker failed: {job['task']}; inspect {job['log']}")
                    state = runner.read(c / "ejecuciones" / ("__".join(job["task"]) + ".json"))
                    runner.validate_completed(state, c, args.data_root, *job["task"])
                    progress["completed"].append(dict(task=job["task"], run_id=state["run_id"],
                                                       total_seconds=state["total_seconds"]))
                    completed_fraction += 1
                    active.remove(job)
            r = resources()
            fractions = []
            for job in active:
                matches = re.findall(r"\] ([0-9.]+)%", job["log"].read_text(encoding="utf-8", errors="replace"))
                fractions.append(float(matches[-1]) / 100 if matches else 0)
            now = time.monotonic()
            aggregate = completed_fraction + sum(fractions)
            rate = (aggregate - last_sample[1]) / max(now - last_sample[0], 1)
            if now - last_sample[0] >= 90:
                if last_rate and rate < last_rate * .8:
                    cap = max(1, len(active) - 1)
                elif last_rate and rate > last_rate * 1.05 and r["cpu"] < 80 and now - last_increase >= 180:
                    cap = min(6, cap + 1)
                    last_increase = now
                last_rate, last_sample = rate, (now, aggregate)
            # Account for each process tree's resident pages and remaining growth to 4 GiB.
            growth = growth_reserve(active, r["python"])
            while tasks and len(active) < min(cap, r["physical"]) and r["cpu"] < 85:
                if r["available_gib"] < 6 + 4 + growth:
                    break
                task = tasks.pop(0)
                token = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
                log = c / "logs_corridas" / ("__".join(task) + "__local_" + token + ".txt")
                stream = log.open("x", encoding="utf-8")
                command = [sys.executable, "-B", "-u", "-X", "utf8", str(Path(__file__).resolve()),
                           "--candidate", str(c), "--data-root", str(args.data_root), "--raw-root", str(args.raw_root),
                           "--worker", *task]
                process = subprocess.Popen(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT,
                                           env=os.environ.copy(), creationflags=subprocess.CREATE_NO_WINDOW)
                active.append(dict(task=task, process=process, stream=stream, log=log))
                r["available_gib"] -= 4  # Include pending growth before the next OS sample.
            progress.update(status="replays", elapsed_seconds=now - started, resources=r, launch_cap=cap,
                pending=tasks, aggregate_portfolios_per_hour=rate * 3600,
                active=[dict(task=j["task"], pid=j["process"].pid, log=str(j["log"])) for j in active])
            save(progress_path, progress)
            with (control / "recursos.jsonl").open("a", encoding="utf-8") as f:
                f.write(json.dumps(dict(utc=datetime.now(UTC).isoformat(), **r, active=len(active), cap=cap, rate=rate)) + "\n")
            if tasks or active:
                time.sleep(20)
        cache = Path(tempfile.gettempdir()) / "b5_postproceso_20260930T2350Z"
        qa = Path(tempfile.gettempdir()) / ("b5_qa_final_" + datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ"))
        pipeline = [
            ("build", ["scripts/build_stress_counterfactual.py", "--candidate", str(c), "--data-root", str(args.data_root), "--cache-root", str(cache)]),
            ("render", ["scripts/render_stress_counterfactual.py", str(c)]),
            ("snapshot", ["scripts/package_stress_counterfactual.py", str(c), "--snapshot"]),
            ("portable_and_negative", ["scripts/tamper_stress_counterfactual.py", str(c), "--destination", str(qa)]),
        ]
        for name, tail in pipeline:
            log = control / (name + "_" + datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ") + ".txt")
            progress.update(status=name, active=[], stage_log=str(log), qa_path=str(qa))
            save(progress_path, progress)
            before = time.monotonic()
            with log.open("x", encoding="utf-8") as stream:
                proc = subprocess.Popen([sys.executable, "-B", "-u", "-X", "utf8", *tail], cwd=ROOT,
                                        stdout=stream, stderr=subprocess.STDOUT, env=os.environ.copy(),
                                        creationflags=subprocess.CREATE_NO_WINDOW)
                progress["stage_pid"] = proc.pid
                save(progress_path, progress)
                code = proc.wait()
            progress["stages"].append(dict(name=name, seconds=time.monotonic() - before, exit_code=code, log=str(log)))
            if code:
                raise RuntimeError("Delivery stage failed; no seal: " + name)
        progress.update(status="verificado_pendiente_revision_final_y_sello", stage_pid=None,
                        note="Final report review, preservation check and existing sealing gate remain required; no model calls")
        save(progress_path, progress)
    except Exception as exc:
        progress.update(status="fallido", reason=f"{type(exc).__name__}: {exc}",
            active=[dict(task=j["task"], pid=j["process"].pid, log=str(j["log"])) for j in active if j["process"].poll() is None])
        save(progress_path, progress)
        raise
    finally:
        lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
        lock.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--data-root", default=Path("D:/Backtesting"), type=Path)
    parser.add_argument("--raw-root", required=True, type=Path)
    parser.add_argument("--worker", nargs=2)
    args = parser.parse_args()
    if args.worker:
        worker(args)
    else:
        coordinate(args)


if __name__ == "__main__":
    main()
