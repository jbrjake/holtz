"""Entry point for `python -m token_profiler`."""

from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    """CLI entry point (stub — wired up in Task 6)."""
    _ = argv or sys.argv[1:]
    print("token_profiler: not yet wired up — see Task 6 (CLI module)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
