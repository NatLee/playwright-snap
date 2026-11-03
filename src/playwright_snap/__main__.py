"""``python -m playwright_snap``: the same as the ``playwright-snap`` command."""
from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
