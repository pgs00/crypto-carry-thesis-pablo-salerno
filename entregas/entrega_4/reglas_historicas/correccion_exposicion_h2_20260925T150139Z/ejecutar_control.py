"""Run an explicitly supplied check and retain its command, exit and UTF-8 output."""

import argparse
import datetime
import json
import subprocess
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True)
    parser.add_argument("--cwd", type=Path)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    folder = Path(__file__).resolve().parent / "controles"
    folder.mkdir(exist_ok=True)
    target = folder / (args.name + ".json")
    log = folder / (args.name + ".log")
    if target.exists() or log.exists():
        raise FileExistsError("Control results are append-only; choose a new name")
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    started = datetime.datetime.now(datetime.UTC)
    result = subprocess.run(command, cwd=args.cwd, capture_output=True, encoding="utf-8", errors="replace")
    ended = datetime.datetime.now(datetime.UTC)
    with log.open("x", encoding="utf-8") as handle:
        handle.write(result.stdout + result.stderr)
    record = dict(command=command, cwd=str(args.cwd or Path.cwd()),
                  started_at=started.isoformat(), ended_at=ended.isoformat(),
                  elapsed_seconds=(ended-started).total_seconds(), exit_code=result.returncode,
                  log=log.name)
    with target.open("x", encoding="utf-8") as handle:
        json.dump(record, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    print(json.dumps(record, ensure_ascii=False))
    print((result.stdout + result.stderr)[-6000:])
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
