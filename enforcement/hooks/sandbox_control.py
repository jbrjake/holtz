#!/usr/bin/env python3
"""`holtz-start` / `holtz-stop` — the human's switch for the audit boundary.

The daemon provably cannot authenticate a same-user socket peer: a process can
fork a connected fd into an exec of a genuine hook, or load code into one. So
caller identity is not the boundary. The boundary is the **Claude Code Bash
sandbox** — the agent's commands run inside it with unix sockets denied, and
hooks run outside it — and sahjhan's fuse (>= 0.21.0) refuses every privileged
operation until the project's settings confirm that boundary is configured.

Which leaves one question: who turns it on? Not the agent. Claude Code's
permission model correctly refuses to let the agent edit its own sandbox
settings, and letting it would defeat the purpose anyway. Not a wrapper script
either — a `!` bang line is sandboxed exactly like tool-Bash, so it cannot
reach the socket to start the daemon.

The answer is this hook. `UserPromptSubmit` fires on a message the *human*
typed, and hooks run outside the sandbox, so this process can write the
sandbox-protected settings file in either direction while the session is
already confined. The agent cannot submit prompts, so it cannot reach either
verb; the trigger is an exact match on the whole message, so pasted text and
"how do I holtz-stop?" cannot fire it either.

Arming order matters and is not arbitrary: `init`, then start the daemon
(binding the socket **outside** the project tree), then write the settings.
The daemon must exist before the boundary goes up, because once it is up
nothing inside the session can bind that socket. Disarming runs the reverse:
the daemon dies first, so a live daemon is never reachable from a shell that
has just been un-confined.

Neither verb reaches the model — both answer with a UserPromptSubmit block, so
the receipt goes to the human and no turn is spent on it.
"""
from __future__ import annotations

import contextlib
import json
import os
import shutil
import subprocess
import sys
import time
from collections.abc import Callable

sys.path.insert(0, os.path.dirname(__file__))

from _common import (  # noqa: E402
    DaemonError,
    _daemon_request,
    _enforcement_root,
    _get_daemon_socket_path,
    boundary_dir,
    exit_ok,
    exit_prompt_block,
    read_event,
    resolve_config_dir,
)
from _protocol_cache import BOUNDARY_REFUSED  # noqa: E402
from _resolve import ensure_sahjhan  # noqa: E402

ARM_WORD = "holtz-start"
DISARM_WORD = "holtz-stop"

_DAEMON_LOG = "/tmp/sahjhan-daemon.log"
_SETTINGS_REL = os.path.join(".claude", "settings.local.json")
_BACKUP_NAME = "sandbox-settings-backup.json"

# How long to wait for the daemon to bind its socket and write its PID file.
# Generous: on a cold start the ~100MB binary may still be paging in.
_DAEMON_READY_TIMEOUT = 15.0
_POLL_INTERVAL = 0.1

# The daemon's refusal code for a missing boundary is named once, in
# _protocol_cache, and imported by everything that decides on it — the hook
# that raises the boundary and the hooks that fail closed when it is gone are
# reading the same word rather than each spelling a string literal.


# ── the settings we write ────────────────────────────────────────────────────


def sandbox_settings(cwd: str) -> dict:
    """The `sandbox` block that satisfies every check in sahjhan's fuse.

    Every key here is in the *strengthening* direction, which is what makes a
    project-scope file able to set them at all: Claude Code lets any scope
    tighten isolation and only lets operator scopes loosen it, so `enabled`,
    `failIfUnavailable`, `allowUnsandboxedCommands: false` and the deny lists
    survive from `.claude/settings.local.json` while an `allowWrite` would not.

    - `failIfUnavailable` is what converts "the settings demand a sandbox"
      into "it is on, or the session halted" — the fuse reads configuration,
      not kernel state, and this is the gap it closes.
    - `allowUnsandboxedCommands: false` stops a denied socket connection being
      retried outside the sandbox.
    - `denyWrite` on the plugin tree is what stops a confined agent planting a
      `sitecustomize.py` or a sibling `json.py` for a genuine hook to import
      later; `denyWrite` on the boundary directory stops it squatting the
      socket path between daemon restarts.
    """
    deny_write = [_enforcement_root(), boundary_dir(cwd)]
    return {
        "enabled": True,
        "allowUnsandboxedCommands": False,
        "failIfUnavailable": True,
        "filesystem": {"denyWrite": deny_write},
    }


def _read_json(path: str) -> dict | None:
    """Return a parsed JSON object, or None when absent//unusable."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _write_json(path: str, doc: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2)
        f.write("\n")


def _apply_settings(cwd: str) -> None:
    """Install the boundary into the project's settings, backing up what was there.

    The whole prior `sandbox` block is saved and replaced rather than merged
    key-by-key: a leftover `excludedCommands` or `allowUnixSockets` from the
    user's own experimenting would trip the fuse, and silently inheriting one
    is how an armed session ends up refusing to serve for reasons nobody can
    see. Everything *outside* `sandbox` is left untouched.

    An existing backup is never overwritten. Typing `holtz-start` twice is an
    ordinary thing to do, and re-backing-up would capture the block we wrote
    ourselves — after which `holtz-stop` would faithfully "restore" the
    sandbox instead of removing it.
    """
    settings_path = os.path.join(cwd, _SETTINGS_REL)
    doc = _read_json(settings_path) or {}
    bdir = boundary_dir(cwd)
    os.makedirs(bdir, mode=0o700, exist_ok=True)
    backup_path = os.path.join(bdir, _BACKUP_NAME)
    if not os.path.exists(backup_path):
        _write_json(backup_path, {
            "had_file": os.path.isfile(settings_path),
            "had_sandbox": "sandbox" in doc,
            "sandbox": doc.get("sandbox"),
        })
    doc["sandbox"] = sandbox_settings(cwd)
    _write_json(settings_path, doc)


def _restore_settings(cwd: str) -> None:
    """Put the project's `sandbox` settings back the way `holtz-start` found them."""
    settings_path = os.path.join(cwd, _SETTINGS_REL)
    doc = _read_json(settings_path)
    if doc is None:
        return
    backup_path = os.path.join(boundary_dir(cwd), _BACKUP_NAME)
    backup = _read_json(backup_path) or {}
    if backup.get("had_sandbox"):
        doc["sandbox"] = backup.get("sandbox")
    else:
        doc.pop("sandbox", None)

    if not doc and not backup.get("had_file", True):
        # The file exists only because we made it, and it is now empty.
        # Leaving `{}` behind in someone's project is litter, not a setting.
        with contextlib.suppress(OSError):
            os.remove(settings_path)
    else:
        _write_json(settings_path, doc)

    # Consume the backup, so the next `holtz-start` captures what the project
    # actually looks like rather than replaying a stale snapshot.
    with contextlib.suppress(OSError):
        os.remove(backup_path)


# ── daemon lifecycle ─────────────────────────────────────────────────────────


def _daemon_env(sock_path: str) -> dict[str, str]:
    """Environment for the daemon: same socket path every hook resolves to."""
    return {**os.environ, "SAHJHAN_DAEMON_SOCKET": sock_path}


def _daemon_alive(sock_path: str) -> bool:
    """Is something already serving on this socket?

    `status` is the one op sahjhan's fuse exempts, so this answers "is there a
    daemon" without depending on whether the boundary is up yet.
    """
    try:
        _daemon_request(sock_path, {"op": "status"})
    except DaemonError:
        return True  # it answered; a refusal still proves it is alive
    except (OSError, ConnectionError, ValueError):
        return False
    return True


def _wait_for(predicate: Callable[[], bool], timeout: float = _DAEMON_READY_TIMEOUT) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(_POLL_INTERVAL)
    return predicate()


def _start_daemon(binary: str, config_dir: str, cwd: str, sock_path: str) -> str | None:
    """Launch the daemon detached. Returns an error message, or None on success.

    `daemon start` is foreground-only — it does not fork — so it goes into its
    own session with its output on a log file rather than a pipe nobody will
    drain. Started here rather than by the agent so the socket is bound before
    the sandbox confines anything, and so the daemon inherits the *human's*
    environment rather than the agent's.
    """
    os.makedirs(os.path.dirname(sock_path), mode=0o700, exist_ok=True)
    try:
        log = open(_DAEMON_LOG, "a", encoding="utf-8")  # noqa: SIM115 - owned by the child
    except OSError as exc:
        return f"cannot open {_DAEMON_LOG}: {exc}"
    try:
        subprocess.Popen(  # noqa: S603
            [binary, "--config-dir", config_dir, "daemon", "start"],
            cwd=cwd,
            env=_daemon_env(sock_path),
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=log,
            start_new_session=True,
        )
    except OSError as exc:
        return f"cannot launch the daemon: {exc}"
    finally:
        log.close()

    if not _wait_for(lambda: _daemon_alive(sock_path)):
        return (
            f"the daemon did not come up within {_DAEMON_READY_TIMEOUT:.0f}s — "
            f"see {_DAEMON_LOG}"
        )
    return None


def _record_init_pid(cwd: str) -> None:
    """Copy `daemon.pid` to `daemon-init-pid`, the file death detection reads.

    `_daemon_lifecycle.py` compares the live daemon against *this* PID to tell
    "the daemon that holds our session key" from "a restarted daemon with a
    different key". The PID file stays in `data_dir` even though the socket
    moved out — consumers watch it there, and it guards nothing.
    """
    data_dir = os.path.join(cwd, "docs", "holtz", ".sahjhan")
    src = os.path.join(data_dir, "daemon.pid")
    if _wait_for(lambda: os.path.isfile(src), timeout=5.0):
        with contextlib.suppress(OSError):
            shutil.copyfile(src, os.path.join(data_dir, "daemon-init-pid"))


def _needs_init(cwd: str) -> bool:
    """Has `sahjhan init` already run here?

    `init` is not idempotent — it exits with a usage error when the ledger it
    would create already exists — and typing `holtz-start` a second time is an
    ordinary thing to do. So ask the same question sahjhan asks, of the same
    artifact: does the default ledger exist under `data_dir`? Matching on the
    exit code instead would swallow every other usage error along with it.
    """
    ledger = os.path.join(cwd, "docs", "holtz", ".sahjhan", "ledger.jsonl")
    return not os.path.isfile(ledger)


def _clear_audit_markers(cwd: str) -> None:
    """Remove the files that make a *deliberate* teardown look like a crash.

    Without this, the next tool call after `holtz-stop` finds a dead init PID,
    writes a `terminated` marker and blocks every write-path tool with "the
    audit died" — leaving the human unable to work in a project they just
    asked to have handed back.
    """
    data_dir = os.path.join(cwd, "docs", "holtz", ".sahjhan")
    for name in ("daemon-init-pid", "terminated"):
        with contextlib.suppress(OSError):
            os.remove(os.path.join(data_dir, name))


# ── the two verbs ────────────────────────────────────────────────────────────


def _check_boundary(sock_path: str) -> str | None:
    """Ask the daemon whether it can see the boundary. Returns its reason, or None.

    The fuse is evaluated per request against the settings on disk, so this is
    the real verdict rather than a restatement of what we just wrote — and it
    catches the case the arming hook *cannot* fix, where a lower-precedence
    scope (`~/.claude/settings.json`, a committed `.claude/settings.json`)
    allowlists the socket or excludes commands from the sandbox.
    """
    try:
        _daemon_request(sock_path, {"op": "enforcement_read"})
    except DaemonError as exc:
        if exc.error == BOUNDARY_REFUSED:
            return (
                "HOLTZ-START INCOMPLETE — the daemon still refuses to serve:\n"
                f"  {exc.reason or exc}\n\n"
                "The boundary was written to .claude/settings.local.json, so "
                "the offending value lives in a scope holtz does not own — "
                "most likely ~/.claude/settings.json or a committed "
                ".claude/settings.json. Fix it there and type holtz-start again."
            )
        if exc.error == "auth_failed":
            # Not a boundary problem, but reported here because it is the
            # other way an armed audit silently does nothing: a stale
            # trusted-callers.toml makes every hook's daemon call fail, the
            # enforcement cache is never freshened, and every gate fails open
            # — with no symptom, because each hook still exits 0.
            return (
                "HOLTZ-START INCOMPLETE — the daemon does not recognize its "
                f"own hooks ({exc.reason or 'auth_failed'}).\n"
                "  Every gate would fail open and nothing would look wrong: "
                "each hook still exits 0.\n"
                "  `hash_mismatch` means enforcement/trusted-callers.toml is "
                "stale — regenerate it with scripts/hash-trusted-callers.sh.\n"
                "  `pid_resolution_failed` means the hook was invoked by a "
                "path the daemon cannot resolve under --config-dir; hooks.json "
                "must call it by absolute path.\n\n"
                "  Fix it, then type holtz-start again."
            )
        return None  # not_found simply means nothing is stored yet
    except (OSError, ConnectionError, ValueError) as exc:
        return f"HOLTZ-START INCOMPLETE — the daemon is unreachable: {exc}"
    return None


def arm(cwd: str) -> str:
    """Start the daemon, then raise the boundary. Returns the receipt."""
    binary = ensure_sahjhan()
    if binary is None:
        return "HOLTZ-START FAILED: the sahjhan binary is unavailable."

    config_dir, found = resolve_config_dir(cwd)
    if not found:
        return f"HOLTZ-START FAILED: enforcement config not found (looked in {config_dir})."

    sock_path = _get_daemon_socket_path(cwd)

    if _needs_init(cwd):
        try:
            init = subprocess.run(  # noqa: S603
                [binary, "--config-dir", config_dir, "init"],
                cwd=cwd, capture_output=True, text=True, timeout=30,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return f"HOLTZ-START FAILED: `sahjhan init` did not run: {exc}"
        if init.returncode != 0:
            return (
                f"HOLTZ-START FAILED: `sahjhan init` exited {init.returncode}: "
                f"{init.stderr.strip()}"
            )

    if not _daemon_alive(sock_path):
        error = _start_daemon(binary, config_dir, cwd, sock_path)
        if error:
            return f"HOLTZ-START FAILED: {error}"
        _record_init_pid(cwd)

    _apply_settings(cwd)

    refusal = _check_boundary(sock_path)
    if refusal:
        return refusal

    return (
        "HOLTZ ARMED. The agent's shell is sandboxed and cannot reach the "
        f"daemon socket ({sock_path}); hooks, which run outside the sandbox, "
        "still can.\n"
        "  • Start the audit with /holtz.\n"
        "  • Every session in this project stays sandboxed until you type "
        "holtz-stop, which also ends the audit.\n"
        "  • On Linux the socket block additionally needs the optional "
        "@anthropic-ai/sandbox-runtime seccomp filter; macOS denies sockets "
        "by default."
    )


def disarm(cwd: str) -> str:
    """Stop the daemon, then lower the boundary. Returns the receipt."""
    binary = ensure_sahjhan()
    config_dir, _ = resolve_config_dir(cwd)
    sock_path = _get_daemon_socket_path(cwd)

    stopped = True
    if binary is not None and _daemon_alive(sock_path):
        try:
            result = subprocess.run(  # noqa: S603
                [binary, "--config-dir", config_dir, "daemon", "stop"],
                cwd=cwd, env=_daemon_env(sock_path),
                capture_output=True, text=True, timeout=15,
            )
            stopped = result.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            stopped = False

    if not stopped:
        # Deliberately do NOT lower the boundary: a reachable daemon plus an
        # un-confined shell is the one combination this whole design exists to
        # prevent. Typing holtz-stop again is safe and retries the stop.
        return (
            "HOLTZ-STOP FAILED: the daemon would not stop, so the sandbox is "
            "still up — lowering it around a live daemon is the one thing this "
            f"protects against. Check {_DAEMON_LOG} and type holtz-stop again."
        )

    _clear_audit_markers(cwd)
    _restore_settings(cwd)
    return (
        "HOLTZ STOPPED. The daemon is down and the sandbox settings are back "
        "the way they were — this project is yours again.\n"
        "  The session key died with the daemon, so the audit it was holding "
        "is over; a new daemon has a new key and cannot resume that ledger. "
        "To pause an audit and come back to it, use `sahjhan transition "
        "pause` / `resume` instead, which keep the daemon alive."
    )


def main() -> None:
    event = read_event()
    prompt = (event.get("prompt") or "").strip()
    if prompt not in (ARM_WORD, DISARM_WORD):
        exit_ok()

    cwd = event.get("cwd", os.getcwd())
    exit_prompt_block(arm(cwd) if prompt == ARM_WORD else disarm(cwd))


if __name__ == "__main__":
    main()
