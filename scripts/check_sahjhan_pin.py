#!/usr/bin/env python3
"""Pre-release guard: the sahjhan pin has exactly one source of truth.

Background (the footgun this closes): the pinned sahjhan version lived in TWO
committed places — `enforcement/hooks/_resolve.py` (`SAHJHAN_VERSION`, the one
installed plugins actually use) and the `bin/.sahjhan-version` marker file. On
the v0.135.0 release the marker was left at the old value while the resolver
was bumped, and the discrepancy shipped: two sources of truth silently drifted.

The marker is *runtime state* — the bootstrap (`_resolve._bootstrap`) and
`scripts/vendor-sahjhan.sh` both write it to match `SAHJHAN_VERSION` — so it
must never be committed. This check enforces that, plus verifies any vendored
binary present matches the pinned checksum.

Exit 0 = consistent. Exit 1 = a release-blocking inconsistency, printed to
stderr. Wired into `scripts/pre-release-check.sh`.
"""
from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "enforcement" / "hooks"))

import _resolve  # noqa: E402  (path set above)

MARKER = REPO_ROOT / "bin" / ".sahjhan-version"


def _is_git_tracked(path: Path) -> bool:
    try:
        rel = path.relative_to(REPO_ROOT)
    except ValueError:
        return False  # outside the repo — cannot be tracked here
    result = subprocess.run(
        ["git", "ls-files", "--error-unmatch", str(rel)],
        cwd=REPO_ROOT,
        capture_output=True,
    )
    return result.returncode == 0


def check() -> list[str]:
    """Return a list of failure messages (empty = all good)."""
    failures: list[str] = []
    pinned = _resolve.SAHJHAN_VERSION

    # 1. The marker must not be committed — it is runtime state and a second
    #    committed copy is exactly what drifted on v0.135.0.
    if _is_git_tracked(MARKER):
        failures.append(
            "bin/.sahjhan-version is git-tracked. It is runtime state (written "
            "to match SAHJHAN_VERSION by the bootstrap and vendor-sahjhan.sh) "
            "and must stay untracked so it can never drift from the pin in "
            "_resolve.py. Fix: git rm --cached bin/.sahjhan-version"
        )

    # 2. If a marker exists in the working tree, it must match the pin.
    if MARKER.exists():
        marker_val = MARKER.read_text().strip()
        if marker_val != pinned:
            failures.append(
                f"bin/.sahjhan-version says {marker_val!r} but "
                f"_resolve.SAHJHAN_VERSION is {pinned!r}. Re-vendor with the "
                f"pinned version (scripts/vendor-sahjhan.sh {pinned})."
            )

    # 3. Any vendored binary present must match the pinned checksum, so a
    #    release can't ship a binary that doesn't match its own pin.
    for triple, expected in _resolve.SAHJHAN_CHECKSUMS.items():
        binary = REPO_ROOT / "bin" / f"sahjhan-{triple}"
        if not binary.exists():
            continue
        actual = hashlib.sha256(binary.read_bytes()).hexdigest()
        if actual != expected:
            failures.append(
                f"bin/sahjhan-{triple} sha256 {actual} != pinned {expected} "
                f"(_resolve.SAHJHAN_CHECKSUMS). Vendored binary does not match "
                f"the pin for v{pinned}."
            )

    return failures


def main() -> None:
    failures = check()
    if failures:
        for f in failures:
            print(f"FAIL: {f}", file=sys.stderr)
        sys.exit(1)
    print(f"PASS: sahjhan pin consistent (v{_resolve.SAHJHAN_VERSION}, single source of truth).")
    sys.exit(0)


if __name__ == "__main__":
    main()
