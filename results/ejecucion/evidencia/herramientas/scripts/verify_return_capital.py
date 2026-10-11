"""Portable verifier: supply source paths explicitly for complete recomputation."""

import argparse
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True

from return_capital.common import write_json  # noqa: E402
from return_capital.package import check_e3_cycles  # noqa: E402
from return_capital.verification import new_destination, verify  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True)
    for name in ("parent", "correction", "intraday", "e3", "output"):
        parser.add_argument("--" + name, type=Path)
    args = parser.parse_args(argv)
    names = ("parent", "correction", "intraday", "e3")
    supplied = [getattr(args, key) is not None for key in names]
    if any(supplied) and not all(supplied):
        parser.error("Complete mode requires all four explicit dependencies")
    dependencies = {key: getattr(args, key).resolve() for key in names} if all(supplied) else None
    if args.output:
        new_destination(args.output, [args.package, *(dependencies or {}).values()])
    result = verify(args.package, dependencies)
    if dependencies:
        from return_capital.common import read_csv

        check_e3_cycles(read_csv(args.package / "tablas/ciclos_vida.csv"), dependencies["e3"])
        result["e3_cycle_identity"] = "exact"
    if args.output:
        write_json(args.output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
