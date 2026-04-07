"""Bridge to hooks/_common.py shared utilities + enforcement-specific helpers.

Enforcement hooks live in enforcement/hooks/ but need access to the
shared exit helpers in hooks/_common.py. Uses importlib to avoid
self-import (both files are named _common.py).

Also provides enforcement-specific utilities:
- resolve_config_dir(): Find the enforcement config directory correctly
  regardless of whether running as a plugin or in local dev.
- compute_event_proof(): Get HMAC proof from the sahjhan daemon via socket.
- record_authed_event(): Record a restricted event with daemon-signed proof.
"""
from __future__ import annotations

import importlib.util
import json
import os
import socket
import subprocess
from datetime import datetime, timezone

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
exit_stop_warn = _mod.exit_stop_warn
exit_stop_block = _mod.exit_stop_block
mask_fenced_blocks = _mod.mask_fenced_blocks


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


def _active_ledger(cwd: str) -> str | None:
    """Detect the active run ledger name from .sahjhan/active-run marker."""
    active_file = os.path.join(cwd, "docs", "holtz", ".sahjhan", "active-run")
    try:
        with open(active_file, encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return None


def write_active_run_marker(cwd: str, ledger_name: str) -> None:
    """Write the active-run marker file so hooks can find the active ledger.

    No-op if the .sahjhan data directory doesn't exist (no active audit).
    """
    data_dir = os.path.join(cwd, "docs", "holtz", ".sahjhan")
    if not os.path.isdir(data_dir):
        return
    marker = os.path.join(data_dir, "active-run")
    with open(marker, "w", encoding="utf-8") as f:
        f.write(ledger_name.strip() + "\n")


def exit_enforcement_error(
    cwd: str,
    reason: str,
    hook_type: str = "PreToolUse",
) -> None:
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
                exit_warn(f"ENFORCEMENT DEGRADED: {reason}")
    # No active audit or stale enforcement — fail-open
    if hook_type == "PreToolUse":
        exit_ok("PreToolUse")
    else:
        exit_ok()


def _get_daemon_socket_path(cwd: str | None = None) -> str:
    """Return the path to the sahjhan daemon Unix socket."""
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
    ledger: str | None = None,
) -> subprocess.CompletedProcess[str]:
    """Record a restricted event with daemon-signed HMAC proof via sahjhan authed-event.

    Args:
        event_type: The restricted event type name.
        fields: Dict of field name -> value pairs.
        cwd: Working directory for the sahjhan command.
        ledger: Optional ledger name (e.g., "run-25").

    Returns:
        The CompletedProcess from the sahjhan call.
    """
    from _resolve import ensure_sahjhan

    proof = compute_event_proof(event_type, fields, cwd=cwd)
    binary = ensure_sahjhan()
    if binary is None:
        raise OSError("Sahjhan binary unavailable")
    config_dir, _ = resolve_config_dir(cwd)
    cmd = [binary, "--config-dir", config_dir]
    if ledger:
        cmd.extend(["--ledger", ledger])
    cmd.extend(["authed-event", event_type, "--proof", proof])
    for k, v in fields.items():
        cmd.extend(["--field", f"{k}={v}"])
    return subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, timeout=10)


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
    except (OSError, ProcessLookupError):
        return False


def _write_terminated_marker(
    cwd: str,
    init_pid: int,
    detected_by: str = "unknown",
) -> None:
    """Write the audit-terminated marker and update enforcement cache.

    Called when daemon death is detected. The marker file prevents
    repeated PID checks on subsequent hook invocations. The cache
    update ensures stop_hook allows stop.
    """
    data_dir = os.path.join(cwd, "docs", "holtz", ".sahjhan")
    marker = os.path.join(data_dir, "terminated")
    with open(marker, "w", encoding="utf-8") as f:
        f.write(f"reason: daemon_pid_dead\n")
        f.write(f"init_pid: {init_pid}\n")
        f.write(f"detected_by: {detected_by}\n")
        f.write(f"detected_at: {datetime.now(timezone.utc).isoformat()}Z\n")

    cache_path = os.path.join(data_dir, "enforcement-cache.json")
    try:
        with open(cache_path, encoding="utf-8") as f:
            cache = json.load(f)
    except (OSError, json.JSONDecodeError):
        cache = {}
    cache["state"] = "terminated"
    cache["terminated_reason"] = "daemon_pid_dead"
    cache["active"] = False
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(cache, f)
