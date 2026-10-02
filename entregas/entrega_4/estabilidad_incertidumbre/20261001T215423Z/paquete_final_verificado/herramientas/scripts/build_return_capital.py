"""Build the explicitly authorized BASE_E3 return/capital derivative."""

import sys

sys.dont_write_bytecode = True

from return_capital.package import main  # noqa: E402

if __name__ == "__main__":
    main()
