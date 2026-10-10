"""Invoke the included full verifier; separate validation rejection from broken execution."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
sys.dont_write_bytecode = True

from scripts.return_capital.common import sha256, write_json  # noqa: E402
from scripts.verify_stress_counterfactual import verify  # noqa: E402


def checked_verification(package):
    # Imports, process errors and unexpected exceptions are deliberately not
    # classified as a successful negative test.
    result = dict(schema="stress_verifier_attempt_v1", verifier_invoked=True,
                  passed=False, rejected=False)
    try:
        details = verify(package, unsealed=True)
    except (ValueError, ArithmeticError) as exc:
        result.update(rejected=True, rejection_type=type(exc).__name__, reason=str(exc))
    else:
        if not details["passed"] or details["partial"]:
            raise RuntimeError("Verifier did not complete full validation")
        result.update(passed=True, verification=details)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    package = args.package.resolve()
    if args.output.resolve().is_relative_to(package):
        raise ValueError("Verification-attempt evidence must be outside the package")
    source = Path(sys.modules[verify.__module__].__file__).resolve()
    if source != ROOT / "scripts/verify_stress_counterfactual.py":
        raise RuntimeError("Verifier imported from another code tree")
    result = checked_verification(package)
    result.update(verifier_file=str(source), verifier_sha256=sha256(source),
                  python_isolated=bool(sys.flags.isolated))
    write_json(args.output, result)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
