"""Single local B6 coordinator: four economic jobs, persistent queue, automatic delivery."""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

for _key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_key] = "1"
os.environ.update(PYTHONDONTWRITEBYTECODE="1", MPLBACKEND="Agg", PYTHONIOENCODING="utf-8")
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from scripts.stability_uncertainty_contract import (  # noqa: E402
    TASKS,
    THREAD_ENV,
    launch_capacity,
    prepare,
    read,
    save,
    sha,
)


def resources(data_root):
    command = r"""
$cpu = Get-CimInstance Win32_Processor
$mem = Get-CimInstance Win32_OperatingSystem
$perf = Get-CimInstance Win32_PerfFormattedData_PerfOS_Memory
$disk = Get-CimInstance Win32_PerfFormattedData_PerfDisk_PhysicalDisk | Where-Object {$_.Name -eq '_Total'}
$procs = @(Get-CimInstance Win32_Process | Where-Object {$_.Name -match '^python'} |
 Select-Object ProcessId,ParentProcessId,CreationDate,CommandLine,WorkingSetSize,PageFileUsage,ReadTransferCount,WriteTransferCount,KernelModeTime,UserModeTime)
[pscustomobject]@{physical=$cpu.NumberOfCores;logical=$cpu.NumberOfLogicalProcessors;cpu=$cpu.LoadPercentage;
 available_gib=$mem.FreePhysicalMemory/1MB;total_gib=$mem.TotalVisibleMemorySize/1MB;
 paging_mbps=$perf.PagesInputPersec*4096/1MB;disk_bytes_per_second=$disk.DiskBytesPersec;
 disk_queue=$disk.CurrentDiskQueueLength;processes=$procs} | ConvertTo-Json -Compress -Depth 5
"""
    result = json.loads(
        subprocess.check_output(
            ["powershell", "-NoProfile", "-Command", command],
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    )
    result["disk_free_gib"] = shutil.disk_usage(data_root).free / 2**30
    result["candidate_disk_free_gib"] = shutil.disk_usage(ROOT).free / 2**30
    result["disk_free_gib"] = min(result["disk_free_gib"], result["candidate_disk_free_gib"])
    return result


def process_tree(pid, records):
    ids = {pid}
    for _ in records:
        ids.update(p["ProcessId"] for p in records if p["ParentProcessId"] in ids)
    return [p for p in records if p["ProcessId"] in ids]


def existing_jobs(records):
    ancestors = {os.getpid(), os.getppid()}
    for _ in records:
        ancestors.update(p["ParentProcessId"] for p in records if p["ProcessId"] in ancestors)
    return [
        p
        for p in records
        if p["ProcessId"] not in ancestors
        and re.search(
            r"(?:coordinate_|run_|package_|verify_)?stability_uncertainty"
            r"(?:_bootstrap|_report|_synthesis)?\.py",
            p["CommandLine"] or "",
        )
    ]


def stage(candidate, name, arguments, progress, progress_path):
    token = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    log = candidate / "controles/coordinacion_local" / f"{name}__{token}.txt"
    log.parent.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, "-B", "-u", "-X", "utf8", *arguments]
    started = time.monotonic()
    progress.update(status=name, stage_log=str(log), active=[])
    save(progress_path, progress)
    with log.open("x", encoding="utf-8") as stream:
        process = subprocess.Popen(
            command,
            cwd=ROOT,
            env=os.environ.copy(),
            stdout=stream,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        progress["stage_pid"] = process.pid
        save(progress_path, progress)
        result = process.wait()
    progress["stages"].append(
        dict(
            stage=name,
            command=command,
            exit_code=result,
            seconds=time.monotonic() - started,
            log=str(log),
        )
    )
    progress["stage_pid"] = None
    save(progress_path, progress)
    if result:
        raise RuntimeError(f"{name} failed; no automatic retry; inspect {log}")


def coordinate(args):
    import msvcrt

    from scripts.run_stability_uncertainty import validate_completed

    candidate = args.candidate.resolve()
    candidate.mkdir(parents=True, exist_ok=True)
    lock_path = Path(tempfile.gettempdir()) / (
        "b6-" + hashlib.sha256(str(candidate).casefold().encode()).hexdigest()[:16] + ".lock"
    )
    lock = lock_path.open("a+b")
    if lock.tell() == 0:
        lock.write(b"0")
        lock.flush()
    lock.seek(0)
    try:
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        raise SystemExit("Another B6 coordinator owns the lock; nothing launched") from None
    progress_path = candidate / "progreso_local.json"
    control = candidate / "controles/coordinacion_local"
    control.mkdir(parents=True, exist_ok=True)
    progress = dict(
        schema="b6-local-v1",
        pid=os.getpid(),
        started_utc=datetime.now(UTC).isoformat(),
        status="preflight",
        thread_environment=THREAD_ENV,
        worker_budget_gib=4,
        reserve_gib=6,
        target_portfolios=4,
        maximum_work_processes=6,
        lock_path=str(lock_path),
        coordinator_sha256=sha(Path(__file__)),
        reused=[],
        completed=[],
        blocked=[],
        active=[],
        stages=[],
    )
    active = []
    started = time.monotonic()
    try:
        r = resources(args.data_root)
        others = existing_jobs(r["processes"])
        if others:
            raise RuntimeError(
                "Existing coordinator/worker identified by PID, creation and command: "
                + str(others)
            )
        progress["initial_resources"] = r
        closure = candidate.parent / "cierre_actual.json"
        if closure.exists() and read(closure).get("status") == "completado":
            from scripts.package_stability_uncertainty import finalize

            result = finalize(candidate, args.data_root)
            print(json.dumps(result, ensure_ascii=False), flush=True)
            return
        prepare(candidate, args.data_root)
        progress["preflight_seconds"] = time.monotonic() - started
        save(progress_path, progress)
        queue = []
        for task in TASKS:
            path = candidate / "ejecuciones" / ("__".join(task) + ".json")
            if path.exists():
                state = read(path)
                if state.get("status") == "ejecutado":
                    validate_completed(state, candidate, args.data_root, *task)
                    progress["reused"].append(dict(task=task, run_id=state["run_id"]))
                else:
                    progress["blocked"].append(
                        dict(
                            task=task,
                            reason="Incomplete attempt; no complete compatible checkpoint",
                            state=str(path),
                        )
                    )
            else:
                queue.append(task)
        if progress["blocked"]:
            raise RuntimeError("Incomplete attempts preserved; do not replay them implicitly")
        logs = candidate / "logs_corridas"
        logs.mkdir(exist_ok=True)
        previous_rate = None
        sample_time, sample_fraction = time.monotonic(), 0.0
        completed = len(progress["reused"])
        throttle_until = 0
        while queue or active:
            for job in active[:]:
                result = job["process"].poll()
                if result is None:
                    continue
                job["stream"].close()
                active.remove(job)
                if result:
                    progress["blocked"].append(
                        dict(task=job["task"], exit_code=result, log=str(job["log"]))
                    )
                    continue
                state = read(candidate / "ejecuciones" / ("__".join(job["task"]) + ".json"))
                validate_completed(state, candidate, args.data_root, *job["task"])
                progress["completed"].append(
                    dict(task=job["task"], run_id=state["run_id"], seconds=state["total_seconds"])
                )
                completed += 1
            r = resources(args.data_root)
            now = time.monotonic()
            fractions = []
            residents = []
            active_state = []
            for job in active:
                tree = process_tree(job["process"].pid, r["processes"])
                resident = sum(int(p["WorkingSetSize"] or 0) for p in tree) / 2**30
                residents.append(resident)
                matches = re.findall(
                    r"\] ([0-9.]+)%", job["log"].read_text(encoding="utf-8", errors="replace")
                )
                fraction = float(matches[-1]) / 100 if matches else 0
                fractions.append(fraction)
                active_state.append(
                    dict(
                        task=job["task"],
                        pid=job["process"].pid,
                        log=str(job["log"]),
                        fraction=fraction,
                        resident_gib=resident,
                        process_tree=tree,
                    )
                )
            aggregate = completed + sum(fractions)
            rate = (aggregate - sample_fraction) / max(now - sample_time, 1)
            if now - sample_time >= 90:
                if previous_rate and rate < 0.8 * previous_rate:
                    throttle_until = now + 90
                previous_rate = rate
                sample_time, sample_fraction = now, aggregate
            cap = launch_capacity(
                available_gib=r["available_gib"],
                resident_gib=residents,
                physical=r["physical"],
                cpu=r["cpu"] or 0,
                disk_free_gib=r["disk_free_gib"],
                paging_mbps=r["paging_mbps"] or 0,
                ramped=now - started >= 30,
            )
            if now < throttle_until:
                cap = len(active)
            while queue and len(active) < cap:
                task = queue.pop(0)
                token = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
                log = logs / ("__".join(task) + "__" + token + ".txt")
                stream = log.open("x", encoding="utf-8")
                command = [
                    sys.executable,
                    "-B",
                    "-u",
                    "-X",
                    "utf8",
                    str(ROOT / "scripts/run_stability_uncertainty.py"),
                    "--candidate",
                    str(candidate),
                    "--data-root",
                    str(args.data_root),
                    "--raw-root",
                    str(args.raw_root),
                    "--scenario",
                    task[0],
                    "--strategy",
                    task[1],
                ]
                process = subprocess.Popen(
                    command,
                    cwd=ROOT,
                    stdout=stream,
                    stderr=subprocess.STDOUT,
                    env=os.environ.copy(),
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
                active.append(
                    dict(task=task, process=process, stream=stream, log=log, command=command)
                )
                active_state.append(dict(task=task, pid=process.pid, log=str(log), command=command))
            progress.update(
                status="replays",
                resources=r,
                launch_cap=cap,
                pending=queue,
                active=active_state,
                elapsed_seconds=now - started,
                aggregate_portfolios_per_hour=rate * 3600,
            )
            save(progress_path, progress)
            with (control / "recursos.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(
                    json.dumps(
                        dict(
                            utc=datetime.now(UTC).isoformat(),
                            **r,
                            active=active_state,
                            launch_cap=cap,
                            aggregate_portfolios_per_hour=rate * 3600,
                        )
                    )
                    + "\n"
                )
            if queue or active:
                time.sleep(30)
        if progress["blocked"]:
            raise RuntimeError("One or more portfolios failed; useful completed jobs preserved")
        stages = [
            (
                "bootstrap",
                [
                    "scripts/stability_uncertainty_bootstrap.py",
                    "--candidate",
                    str(candidate),
                    "--data-root",
                    str(args.data_root),
                ],
            ),
            (
                "financial_report",
                [
                    "scripts/stability_uncertainty_report.py",
                    "--candidate",
                    str(candidate),
                    "--data-root",
                    str(args.data_root),
                ],
            ),
            (
                "synthesis",
                [
                    "scripts/stability_uncertainty_synthesis.py",
                    "--candidate",
                    str(candidate),
                    "--data-root",
                    str(args.data_root),
                ],
            ),
            (
                "finalize",
                [
                    "scripts/package_stability_uncertainty.py",
                    "--candidate",
                    str(candidate),
                    "--data-root",
                    str(args.data_root),
                ],
            ),
        ]
        for name, arguments in stages:
            stage(candidate, name, arguments, progress, progress_path)
        progress.update(status="completado", finished_utc=datetime.now(UTC).isoformat(), active=[])
        save(progress_path, progress)
    except Exception as exc:
        progress.update(
            status="bloqueado",
            reason=f"{type(exc).__name__}: {exc}",
            active=[
                dict(task=j["task"], pid=j["process"].pid, log=str(j["log"]))
                for j in active
                if j["process"].poll() is None
            ],
        )
        save(progress_path, progress)
        raise
    finally:
        lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
        lock.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, default=Path("D:/Backtesting"))
    parser.add_argument("--raw-root", type=Path, required=True)
    args = parser.parse_args()
    coordinate(args)
