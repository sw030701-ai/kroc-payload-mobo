"""Run via the installed package; see README for environment setup."""

import sys

from kroc_mobo.cli import main

if __name__ == "__main__":
    main(["pilot", *sys.argv[1:]])
