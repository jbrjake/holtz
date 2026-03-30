"""Bridge to hooks/_common.py shared utilities.

Enforcement hooks live in enforcement/hooks/ but need access to the
shared exit helpers in hooks/_common.py. Uses importlib to avoid
self-import (both files are named _common.py).
"""
from __future__ import annotations

import importlib.util
import os
import subprocess

_HOOKS_COMMON = os.path.join(
    os.path.dirname(__file__), '..', '..', 'hooks', '_common.py'
)
_spec = importlib.util.spec_from_file_location("hooks._common", _HOOKS_COMMON)
if _spec is None or _spec.loader is None:
    raise RuntimeError(f"Cannot load hooks/_common.py from {_HOOKS_COMMON}")
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

# Re-export all public names
read_event = _mod.read_event
exit_ok = _mod.exit_ok
exit_warn = _mod.exit_warn
exit_block = _mod.exit_block
exit_stop_allow = _mod.exit_stop_allow
exit_stop_block = _mod.exit_stop_block
mask_fenced_blocks = _mod.mask_fenced_blocks


def _active_ledger(cwd: str) -> str | None:
    """Detect the active run ledger name from .sahjhan/active-run marker."""
    active_file = os.path.join(cwd, "docs", "holtz", ".sahjhan", "active-run")
    try:
        with open(active_file, encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return None


def _get_session_key_path(cwd: str | None = None, ledger: str | None = None) -> str:
    """Find the session key path via sahjhan config, falling back to default location."""
    if cwd is None:
        cwd = os.getcwd()
    default = os.path.join(cwd, "docs", "holtz", ".sahjhan", "session.key")
    try:
        from _resolve import sahjhan_binary
        binary = sahjhan_binary()
        if os.path.isfile(binary):
            import subprocess
            cmd = [binary, "--config-dir", os.path.join(cwd, "enforcement")]
            if ledger:
                cmd.extend(["--ledger", ledger])
            cmd.extend(["config", "session-key-path"])
            result = subprocess.run(
                cmd,
                capture_output=True, text=True, timeout=5, cwd=cwd,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
    except (OSError, subprocess.SubprocessError, ImportError):
        pass
    return default


def compute_event_proof(event_type: str, fields: dict[str, str], key_path: str | None = None) -> str:
    """Compute HMAC-SHA256 proof for a restricted event.

    Args:
        event_type: The event type name (e.g., "quiz_answered").
        fields: Dict of field name -> value pairs.
        key_path: Path to the session key file. If None, auto-discovers.

    Returns:
        Hex-encoded HMAC-SHA256 digest.
    """
    import hashlib
    import hmac as hmac_mod

    if key_path is None:
        key_path = _get_session_key_path()
    with open(key_path, "rb") as f:
        key = f.read()
    for k, v in fields.items():
        if "\0" in k or "\0" in v:
            raise ValueError(
                f"Null byte in HMAC field: key={k!r} value={v!r}. "
                "Null bytes would collide with the field separator."
            )
    parts = [event_type] + [f"{k}={v}" for k, v in sorted(fields.items())]
    payload = "\0".join(parts).encode()
    return hmac_mod.new(key, payload, hashlib.sha256).hexdigest()


def record_authed_event(
    event_type: str,
    fields: dict[str, str],
    cwd: str,
    ledger: str | None = None,
) -> subprocess.CompletedProcess[str]:
    """Record a restricted event with HMAC proof via sahjhan authed-event.

    Args:
        event_type: The restricted event type name.
        fields: Dict of field name -> value pairs.
        cwd: Working directory for the sahjhan command.
        ledger: Optional ledger name (e.g., "run-25").

    Returns:
        The CompletedProcess from the sahjhan call.
    """
    from _resolve import sahjhan_binary

    key_path = _get_session_key_path(cwd, ledger=ledger)
    proof = compute_event_proof(event_type, fields, key_path)
    binary = sahjhan_binary()
    cmd = [binary, "--config-dir", os.path.join(cwd, "enforcement")]
    if ledger:
        cmd.extend(["--ledger", ledger])
    cmd.extend(["authed-event", event_type, "--proof", proof])
    for k, v in fields.items():
        cmd.extend(["--field", f"{k}={v}"])
    return subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, timeout=10)
