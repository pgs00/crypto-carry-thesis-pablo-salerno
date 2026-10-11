"""Create a new SOFR benchmark evidence version from approved inputs."""

import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.sofr_benchmark.package import main  # noqa: E402

if __name__ == "__main__":
    main()
