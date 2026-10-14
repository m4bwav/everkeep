#!/usr/bin/env python3
"""everkeep's command-line tool. Standard library only, Python 3.10 or newer. `python keep.py --help` lists commands."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from everkeep.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
