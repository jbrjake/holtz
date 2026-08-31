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

SAHJHAN_VERSION = "0.24.0"
_RELEASE_BASE = "https://github.com/jbrjake/sahjhan/releases/download"
_BOOTSTRAP_COOLDOWN = 3600  # seconds before retrying after failure

SAHJHAN_CHECKSUMS: dict[str, str] = {
    "aarch64-apple-darwin": "00c235beaccfb3417dce49c1e159a45e34af502b25d0cf4e2a6761a427829ad9",
    "x86_64-apple-darwin": "c6bc89912c6cdc51c90a5385e5833a385573467b5cca839ceeace9844ad1ee31",
    "x86_64-unknown-linux-gnu": "83cde6d70b56d32cc54afbb0fc58bc93766c5f9eb07bb657cd80304becde0a34",
    "aarch64-unknown-linux-gnu": "3b8da70a8e5863691b6b4a2b58dff4dbc46c94309046de17dfc9fb126b67bbb8",
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

        # Create platform-neutral `sahjhan` symlink so bare invocations via
        # PATH (Claude Code prepends the plugin's bin/ to PATH) resolve to
        # the platform binary. Without this, the SKILL.md instructions that
        # say ``sahjhan init`` fail with "command not found" after a fresh
        # bootstrap download on machines that don't ship with a pre-made
        # symlink.
        link_path = os.path.join(bin_dir, "sahjhan")
        with contextlib.suppress(OSError):
            if os.path.islink(link_path) or os.path.exists(link_path):
                os.unlink(link_path)
            os.symlink(os.path.basename(dest), link_path)

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
