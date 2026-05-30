"""Allows `python -m safe_whale` invocation."""

import sys

from safe_whale.cli import main

if __name__ == "__main__":
    sys.exit(main())
