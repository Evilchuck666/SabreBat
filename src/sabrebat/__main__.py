"""Allow ``python -m sabrebat``."""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
