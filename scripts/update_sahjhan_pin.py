#!/usr/bin/env python3
"""Point `_resolve.py`'s pin at a freshly vendored sahjhan.

`vendor-sahjhan.sh <version>` downloads binaries and writes the
`bin/.sahjhan-version` marker, but the pin that actually governs at runtime is
`_resolve.SAHJHAN_VERSION` — `ensure_sahjhan()` reads it, and re-downloads the
version it names. So vendoring alone did not switch versions: it left the
resolver pointing at the old one, and the next hook invocation quietly restored
the old binary *and rewrote the marker back*, leaving every pin in agreement at
the version nobody asked for. Nothing detected it, because the marker is
runtime state the resolver itself maintains — it self-heals to whatever the
resolver decides.

This closes that by construction: vendoring updates the resolver, so there is
one update path for the version and its checksums rather than two that must be
remembered in the right order.

Usage::

    python3 scripts/update_sahjhan_pin.py <version> [bin_dir]
"""
from __future__ import annotations

import hashlib
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RESOLVE = REPO_ROOT / "enforcement" / "hooks" / "_resolve.py"
TARGETS = (
    "aarch64-apple-darwin",
    "x86_64-apple-darwin",
    "x86_64-unknown-linux-gnu",
    "aarch64-unknown-linux-gnu",
)


def checksums(bin_dir: Path) -> dict[str, str]:
    """sha256 of each vendored target, or a failure if one is missing."""
    out: dict[str, str] = {}
    for triple in TARGETS:
        binary = bin_dir / f"sahjhan-{triple}"
        if not binary.exists():
            raise SystemExit(f"missing vendored binary: {binary}")
        out[triple] = hashlib.sha256(binary.read_bytes()).hexdigest()
    return out
def render(source: str, version: str, sums: dict[str, str]) -> str:
    """Rewrite the version and checksum pins in `_resolve.py` source."""
    source, n = re.subn(
        r'^SAHJHAN_VERSION = "[^"]*"$',
        f'SAHJHAN_VERSION = "{version}"',
        source,
        count=1,
        flags=re.MULTILINE,
    )
    if n != 1:
        raise SystemExit("could not find SAHJHAN_VERSION in _resolve.py")

    body = "\n".join(f'    "{t}": "{sums[t]}",' for t in TARGETS)
    source, n = re.subn(
        r"^SAHJHAN_CHECKSUMS: dict\[str, str\] = \{\n.*?^\}$",
        f"SAHJHAN_CHECKSUMS: dict[str, str] = {{\n{body}\n}}",
        source,
        count=1,
        flags=re.MULTILINE | re.DOTALL,
    )
    if n != 1:
        raise SystemExit("could not find SAHJHAN_CHECKSUMS in _resolve.py")
    return source


def native_version(bin_dir: Path) -> str:
    """The version the platform-native vendored binary reports, or ``""``.

    Only this one can be asked: the other three targets do not execute here,
    and are covered by their checksums from the same vendor run.
    """
    sys.path.insert(0, str(RESOLVE.parent))
    from _resolve import platform_triple  # noqa: PLC0415

    binary = bin_dir / f"sahjhan-{platform_triple()}"
    try:
        result = subprocess.run(
            [str(binary), "--version"], capture_output=True, text=True, timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    found = re.search(r"\b(\d+\.\d+\.\d+)\b", result.stdout)
    return found.group(1) if found else ""


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("Usage: update_sahjhan_pin.py <version> [bin_dir]")
    version = sys.argv[1]
    bin_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else REPO_ROOT / "bin"

    # Pinning hashes whatever bytes sit in `bin_dir`, and the fast path in
    # `ensure_sahjhan` then trusts them on a marker-string match. So the bytes
    # must be the version being named before their hashes are written down.
    reported = native_version(bin_dir)
    if reported != version:
        raise SystemExit(
            f"refusing to pin sahjhan v{version}: the vendored binary in "
            f"{bin_dir} reports {('v' + reported) if reported else 'no version'}. "
            "Re-run the vendor step for the version you mean."
        )

    updated = render(RESOLVE.read_text(encoding="utf-8"), version, checksums(bin_dir))
    RESOLVE.write_text(updated, encoding="utf-8")
    print(f"Pinned _resolve.py to sahjhan v{version}")


if __name__ == "__main__":
    main()
