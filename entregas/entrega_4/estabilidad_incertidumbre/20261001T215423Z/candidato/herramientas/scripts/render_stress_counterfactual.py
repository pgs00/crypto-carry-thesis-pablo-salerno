"""Render the single block-5 candidate after numerical derivation."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from scripts.return_capital.common import read_json  # noqa: E402
from scripts.stress_counterfactual_delivery import load_tables  # noqa: E402
from scripts.stress_counterfactual_docs import write_docs  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate", type=Path)
    args = parser.parse_args()
    candidate = args.candidate.resolve()
    if (candidate / "manifiesto_paquete.json").exists():
        raise ValueError("Cannot edit sealed report")
    write_docs(candidate, load_tables(candidate / "resultados"), read_json(candidate / "indice_corridas.json"))
    print("RENDERED unsealed candidate")


if __name__ == "__main__":
    main()
