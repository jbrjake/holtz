"""Bridge to hooks/_common.py shared utilities + enforcement-specific helpers.

Enforcement hooks live in enforcement/hooks/ but need access to the
shared exit helpers in hooks/_common.py. Uses importlib to avoid
self-import (both files are named _common.py).

Also provides enforcement-specific utilities:
- resolve_config_dir(): Find the enforcement config directory correctly
  regardless of whether running as a plugin or in local dev.
- compute_event_proof(): Get HMAC proof from the sahjhan daemon via socket.
- record_authed_event(): Record a restricted event by asking the daemon to
  append it directly over the authenticated socket (record_event op).
"""
from __future__ import annotations

import importlib.util
import json
import os
import socket
from collections.abc import Callable
from datetime import datetime, timezone
from typing import NoReturn

_HOOKS_COMMON = os.path.join(
    os.path.dirname(__file__), '..', '..', 'hooks', '_common.py'
)
_spec = importlib.util.spec_from_file_location("hooks._common", _HOOKS_COMMON)
if _spec is None or _spec.loader is None:
    raise RuntimeError(f"Cannot load hooks/_common.py from {_HOOKS_COMMON}")
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

# Re-export all public names. The `importlib` loader gives mypy `Any` for
# every attribute on `_mod`, which loses the `NoReturn` annotation on the
# exit helpers and lets callers' narrowing silently disappear. Annotate
# the re-exports so mypy knows these never return.
read_event: Callable[..., dict] = _mod.read_event
exit_ok: Callable[..., NoReturn] = _mod.exit_ok
exit_warn: Callable[..., NoReturn] = _mod.exit_warn
exit_block: Callable[[str], NoReturn] = _mod.exit_block
exit_stop_allow: Callable[[], NoReturn] = _mod.exit_stop_allow
exit_stop_warn: Callable[[str], NoReturn] = _mod.exit_stop_warn
exit_stop_block: Callable[[str], NoReturn] = _mod.exit_stop_block
mask_fenced_blocks: Callable[[str], str] = _mod.mask_fenced_blocks

# Two sets because "allowed to stop [the turn]" ≠ "safe to kill daemon".
# awaiting_clear allows stop (the turn is done) but the daemon must
# survive — it holds the HMAC session key for the resuming session.
# When adding states, decide: does the audit resume after this? If yes,
# put it in STOP_ALLOWED only. If the audit is over, put it in both.
# Shared by stop_hook.py (stop gating + daemon cleanup) and
# _sahjhan_bootstrap.py (graduated `sahjhan daemon stop` policy, #57).
STOP_ALLOWED_STATES = {"idle", "finalized", "awaiting_clear", ""}
DAEMON_CLEANUP_STATES = {"idle", "finalized", ""}


def _enforcement_root() -> str:
    """Return the root directory containing enforcement/.

    Uses CLAUDE_PLUGIN_ROOT if set (plugin context), otherwise resolves
    relative to this file's location (enforcement/hooks/ → repo root).
    """
    return os.environ.get(
        "CLAUDE_PLUGIN_ROOT",
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    )


def resolve_config_dir(cwd: str) -> tuple[str, bool]:
    """Resolve the enforcement config directory.

    Returns (config_dir_path, config_found) where config_found indicates
    whether protocol.toml actually exists at the resolved path.

    Search order:
    1. Persisted config-dir from {cwd}/docs/holtz/.sahjhan/config-dir
       (written by future sahjhan versions after ``sahjhan init --config-dir``)
    2. CLAUDE_PLUGIN_ROOT/enforcement (plugin context — the normal case)
    3. File-relative fallback (local dev — enforcement/ is in the repo root)
    4. {cwd}/enforcement (legacy fallback — configs copied into project)

    The persisted path takes priority because it reflects the explicit
    --config-dir the user passed to ``sahjhan init``, which may differ
    from both the plugin root and cwd.
    """
    def _has_config(path: str) -> bool:
        return os.path.isfile(os.path.join(path, "protocol.toml"))

    # 1. Persisted config-dir (future sahjhan feature, see jbrjake/sahjhan#20)
    persisted = os.path.join(cwd, "docs", "holtz", ".sahjhan", "config-dir")
    try:
        with open(persisted, encoding="utf-8") as f:
            path = f.read().strip()
        if path and _has_config(path):
            return path, True
    except OSError:
        pass

    # 2. CLAUDE_PLUGIN_ROOT/enforcement (plugin context)
    plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if plugin_root:
        candidate = os.path.join(plugin_root, "enforcement")
        if _has_config(candidate):
            return candidate, True

    # 3. File-relative (local dev: this file is enforcement/hooks/_common.py)
    file_relative = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    )
    if _has_config(file_relative):
        return file_relative, True

    # 4. {cwd}/enforcement (legacy: configs copied into project root)
    cwd_candidate = os.path.join(cwd, "enforcement")
    if _has_config(cwd_candidate):
        return cwd_candidate, True

    # Nothing found — return the best-guess path with found=False
    if plugin_root:
        return os.path.join(plugin_root, "enforcement"), False
    return cwd_candidate, False


def exit_enforcement_error(
    cwd: str,
    reason: str,
    hook_type: str = "PreToolUse",
) -> NoReturn:
    """Block if active audit + fresh enforcement, else allow.

    Replaces exit_ok() at daemon-failure fallback paths. During an active,
    fresh audit, daemon failures are blocks (PreToolUse) or warnings
    (PostToolUse). Outside audits or with stale enforcement, fail-open
    as before.
    """
    from _protocol_cache import is_enforcement_fresh, read_cache  # noqa: PLC0415

    data_dir = os.path.join(cwd, "docs", "holtz", ".sahjhan")
    if os.path.isdir(data_dir):
        cache = read_cache(cwd)
        if is_enforcement_fresh(cache):
            if hook_type == "PreToolUse":
                exit_block(f"ENFORCEMENT DEGRADED: {reason}")
            else:
                exit_warn(f"ENFORCEMENT DEGRADED: {reason}", hook_type)
    # No active audit or stale enforcement — fail-open
    if hook_type == "PreToolUse":
        exit_ok("PreToolUse")
    else:
        exit_ok()


def _get_daemon_socket_path(cwd: str | None = None) -> str:
    """Return the path to the sahjhan daemon Unix socket.

    Checks SAHJHAN_DAEMON_SOCKET env var first (used by test fixtures
    to work around macOS AF_UNIX 104-char path limit).
    """
    override = os.environ.get("SAHJHAN_DAEMON_SOCKET")
    if override:
        return override
    if cwd is None:
        cwd = os.getcwd()
    return os.path.join(cwd, "docs", "holtz", ".sahjhan", "daemon.sock")


def _daemon_request(sock_path: str, request: dict) -> dict:
    """Send a JSON request to the sahjhan daemon and return the response.

    Raises RuntimeError if the daemon is unreachable or returns an error.
    """
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(5)
    try:
        sock.connect(sock_path)
        sock.sendall((json.dumps(request) + "\n").encode())
        response = json.loads(sock.makefile().readline())
    finally:
        sock.close()
    if not response.get("ok"):
        raise RuntimeError(
            f"sahjhan daemon error: {response.get('message', 'unknown error')}"
        )
    return response


def compute_event_proof(event_type: str, fields: dict[str, str], **kwargs: object) -> str:
    """Get HMAC-SHA256 proof from the sahjhan daemon via Unix socket.

    Connects directly to the daemon socket so the daemon can authenticate
    this process via SO_PEERCRED / LOCAL_PEERCRED without a parent-PID hop.

    Args:
        event_type: The event type name (e.g., "quiz_answered").
        fields: Dict of field name -> value pairs.
        **kwargs: Accepted for backward compat (key_path ignored).
            cwd: Optional working directory for socket path resolution.
                 When running in a worktree, pass the main project dir
                 so the socket resolves to the main daemon, not a temp dir.

    Returns:
        Hex-encoded HMAC-SHA256 digest.
    """
    for k, v in fields.items():
        if "\0" in k or "\0" in v:
            raise ValueError(
                f"Null byte in HMAC field: key={k!r} value={v!r}. "
                "Null bytes would collide with the field separator."
            )
    cwd = kwargs.get("cwd")
    sock_path = _get_daemon_socket_path(cwd if isinstance(cwd, str) else None)
    response = _daemon_request(sock_path, {
        "op": "sign",
        "event_type": event_type,
        "fields": dict(sorted(fields.items())),
    })
    return response["proof"]


def record_authed_event(
    event_type: str,
    fields: dict[str, str],
    cwd: str,
) -> dict:
    """Record a restricted event by asking the daemon to append it directly.

    Sends the ``record_event`` op over the daemon socket. This hook process
    is authenticated by the daemon via SO_PEERCRED against
    trusted-callers.toml — the same peer-identity check that authorizes
    ``sign`` and ``enforcement_write``. No HMAC proof or ``sahjhan
    authed-event`` courier is involved: that courier is the bare sahjhan
    binary, which the daemon cannot resolve to a trusted hook script (its
    cmdline has no script → ancestor walk yields pid_resolution_failed), so
    its submit is always rejected even when the sign succeeds. Recording over
    this already-authenticated connection avoids that failure — and a
    daemon-side rejection now surfaces as a raised RuntimeError instead of a
    swallowed non-zero exit code.

    Requires sahjhan >= 0.15.0 (the ``record_event`` op).

    Args:
        event_type: The restricted event type name.
        fields: Dict of field name -> value pairs.
        cwd: Working directory for daemon socket path resolution.

    Returns:
        The daemon response dict; ``data`` holds the new ledger seq.

    Raises:
        RuntimeError: the daemon rejected the event (unknown type, invalid
            field, ledger error) or otherwise returned ``ok: false``.
        OSError: the daemon socket is unreachable.
    """
    sock_path = _get_daemon_socket_path(cwd)
    return _daemon_request(
        sock_path,
        {
            "op": "record_event",
            "event_type": event_type,
            "fields": dict(sorted(fields.items())),
        },
    )


def _read_init_pid(cwd: str) -> int | None:
    """Read the daemon PID recorded at audit initialization.

    Returns None if the file is missing or corrupt. This PID identifies
    the specific daemon instance that holds the session key — if this
    PID is dead, the key is gone and the audit is unrecoverable.
    """
    pid_file = os.path.join(cwd, "docs", "holtz", ".sahjhan", "daemon-init-pid")
    try:
        with open(pid_file, encoding="utf-8") as f:
            return int(f.read().strip())
    except (OSError, ValueError):
        return None


def _is_process_alive(pid: int) -> bool:
    """Check if a process is alive using signal 0."""
    try:
        os.kill(pid, 0)
        return True
    except PermissionError:
        return True  # EPERM → process exists, we just can't signal it
    except (OSError, ProcessLookupError):
        return False


def _write_terminated_marker(
    cwd: str,
    init_pid: int,
    detected_by: str = "unknown",
) -> None:
    """Write the audit-terminated marker file.

    Called when daemon death is detected. The marker file prevents
    repeated PID checks on subsequent hook invocations. All callers
    (stop_hook, primer, _daemon_lifecycle) check this marker before
    read_cache(), so no daemon-side state update is needed.
    """
    data_dir = os.path.join(cwd, "docs", "holtz", ".sahjhan")
    marker = os.path.join(data_dir, "terminated")
    with open(marker, "w", encoding="utf-8") as f:
        f.write("reason: daemon_pid_dead\n")
        f.write(f"init_pid: {init_pid}\n")
        f.write(f"detected_by: {detected_by}\n")
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")  # noqa: UP017
        f.write(f"detected_at: {ts}\n")
