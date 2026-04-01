"""Resolve and bootstrap the Sahjhan binary for the current platform."""
from __future__ import annotations

import contextlib
import hashlib
import os
import platform
import tempfile
import time
from urllib.request import urlopen

# ── Pinned version and integrity checksums ──

SAHJHAN_VERSION = "0.7.1"
_RELEASE_BASE = "https://github.com/jbrjake/sahjhan/releases/download"
_BOOTSTRAP_COOLDOWN = 3600  # seconds before retrying after failure

SAHJHAN_CHECKSUMS: dict[str, str] = {
    "aarch64-apple-darwin": "e062f9fee3a3e5e37c94c4146fdda0f540e8aaff8767fa6aae340bc716b96383",
    "x86_64-apple-darwin": "ba720f59bfae475010ded49f818f1f29da270c03b739bb067963fe3f7906886e",
    "x86_64-unknown-linux-gnu": "d7462e1906bfd6c1e2433ae68672a112f0304be5b5cc13b8c9cb9edc46e6336f",
    "aarch64-unknown-linux-gnu": "aefb1423b93b331a9ec6a00a218b1ae78d714ee8467c58b34d5adc6ca937f2d3",
}

# ── Platform resolution ──


def platform_triple() -> str:
    """Return the Rust target triple for the current platform."""
    arch = platform.machine()
    system = platform.system().lower()
    if arch == "arm64":
        arch = "aarch64"
    return {
        "darwin": f"{arch}-apple-darwin",
        "linux": f"{arch}-unknown-linux-gnu",
    }.get(system, f"{arch}-{system}")


def sahjhan_binary() -> str:
    """Return the absolute path to the Sahjhan binary for this platform.

    Uses CLAUDE_PLUGIN_ROOT if set, otherwise resolves relative to this
    file's location (enforcement/hooks/ -> repo root).
    """
    triple = platform_triple()
    root = os.environ.get(
        "CLAUDE_PLUGIN_ROOT",
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    )
    return os.path.join(root, "bin", f"sahjhan-{triple}")


# ── Self-bootstrap ──


def ensure_sahjhan() -> str | None:
    """Return path to the Sahjhan binary, downloading if needed.

    Returns the binary path if available (already present or successfully
    downloaded). Returns None if the binary cannot be obtained.

    Download is skipped if a recent failure marker exists (< 1 hour old).
    """
    path = sahjhan_binary()
    if os.path.isfile(path) and not _version_stale(path):
        return path
    return _bootstrap(path)


def _version_stale(binary_path: str) -> bool:
    """Check if the installed binary's version doesn't match SAHJHAN_VERSION.

    Returns False (not stale) if:
    - No version file exists (manual vendor — trust it)
    - Version file matches SAHJHAN_VERSION
    Returns True if version file exists but doesn't match.
    """
    version_file = os.path.join(os.path.dirname(binary_path), ".sahjhan-version")
    try:
        with open(version_file, encoding="utf-8") as f:
            return f.read().strip() != SAHJHAN_VERSION
    except OSError:
        return False


def _bootstrap(dest: str) -> str | None:
    """Download the Sahjhan binary, verify checksum, install atomically.

    Returns dest path on success, None on failure.
    """
    bin_dir = os.path.dirname(dest)
    if _recently_failed(bin_dir):
        return None

    triple = platform_triple()
    expected_hash = SAHJHAN_CHECKSUMS.get(triple)
    if not expected_hash:
        return None  # unsupported platform

    url = f"{_RELEASE_BASE}/v{SAHJHAN_VERSION}/sahjhan-{triple}"

    try:
        os.makedirs(bin_dir, exist_ok=True)
    except OSError:
        return None

    fd = None
    tmp_path = None
    try:
        fd, tmp_path = tempfile.mkstemp(dir=bin_dir, prefix=".sahjhan-download-")
        sha = hashlib.sha256()
        with urlopen(url, timeout=30) as resp, os.fdopen(fd, "wb") as f:  # noqa: S310
            fd = None  # os.fdopen takes ownership
            while True:
                chunk = resp.read(8192)
                if not chunk:
                    break
                f.write(chunk)
                sha.update(chunk)

        if sha.hexdigest() != expected_hash:
            os.unlink(tmp_path)
            _mark_failed(bin_dir)
            return None

        os.chmod(tmp_path, 0o755)
        os.rename(tmp_path, dest)
        tmp_path = None  # rename succeeded, don't clean up

        # Write version marker
        version_file = os.path.join(bin_dir, ".sahjhan-version")
        with open(version_file, "w", encoding="utf-8") as f:
            f.write(SAHJHAN_VERSION + "\n")

        # Clear any failure marker
        _clear_failed(bin_dir)
        return dest
    except Exception:
        if fd is not None:
            os.close(fd)
        if tmp_path is not None:
            with contextlib.suppress(OSError):
                os.unlink(tmp_path)
        _mark_failed(bin_dir)
        return None


def _recently_failed(bin_dir: str) -> bool:
    """Check if a bootstrap attempt failed within the cooldown period."""
    marker = os.path.join(bin_dir, ".sahjhan-bootstrap-failed")
    try:
        with open(marker, encoding="utf-8") as f:
            written_at = float(f.read().strip())
        return time.time() - written_at < _BOOTSTRAP_COOLDOWN
    except (OSError, ValueError):
        return False


def _mark_failed(bin_dir: str) -> None:
    """Write a failure marker to prevent immediate retry."""
    marker = os.path.join(bin_dir, ".sahjhan-bootstrap-failed")
    with contextlib.suppress(OSError), open(marker, "w", encoding="utf-8") as f:
        f.write(str(time.time()) + "\n")


def _clear_failed(bin_dir: str) -> None:
    """Remove the failure marker after a successful download."""
    marker = os.path.join(bin_dir, ".sahjhan-bootstrap-failed")
    with contextlib.suppress(OSError):
        os.unlink(marker)
