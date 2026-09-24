"""Entry point for ``python -m fintrack`` and ``uv run -m fintrack``."""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
