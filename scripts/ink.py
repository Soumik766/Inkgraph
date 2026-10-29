#!/usr/bin/env python3
"""inkgraph CLI entry point. Run `python3 ink.py --help`."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from inklib.cli import main  # noqa: E402

if __name__ == "__main__":
    main()
