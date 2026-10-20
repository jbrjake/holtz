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

import hashlib
import importlib.util
import json
import os
import socket
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any, NoReturn

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
bash_output: Callable[[dict], str] = _mod.bash_output
bash_exit_code: Callable[[dict], int] = _mod.bash_exit_code
exit_ok: Callable[..., NoReturn] = _mod.exit_ok
exit_warn: Callable[..., NoReturn] = _mod.exit_warn
exit_block: Callable[[str], NoReturn] = _mod.exit_block
exit_prompt_block: Callable[[str], NoReturn] = _mod.exit_prompt_block
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
# awaiting_human (#69): a reversible pause so the agent can yield to answer a
# user question mid-audit. Stop is allowed, but — like awaiting_clear — the
# daemon must survive so `sahjhan transition resume` continues the run.
STOP_ALLOWED_STATES = {"idle", "finalized", "awaiting_clear", "awaiting_human", ""}
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


BOUNDARY_MESSAGE = (
    "AUDIT BOUNDARY MISSING: the sahjhan daemon refuses to serve because this "
    "session is not sandboxed ({reason}). Enforcement, the lens quiz, and every "
    "restricted event are unavailable until it is — an audit run this way would "
    "prove nothing, so nothing proceeds.\n\n"
    "Only a human can fix it: ask the user to type `holtz-start` (the bare word, "
    "on its own line, in the normal input box). Do not attempt to change sandbox "
    "settings yourself — you cannot, by design."
)


# The refusal `read_cache_for_write` answers with when the socket cannot be
# placed at all. Not a daemon reason code: no daemon was reached.
HOME_UNRESOLVED = "home_unresolved"

HOME_MESSAGE = (
    "AUDIT BOUNDARY UNAVAILABLE: `~` does not resolve to an absolute path in "
    "this environment (HOME is unset or relative), so the daemon socket cannot "
    "be placed outside the project and no hook can reach this audit's "
    "enforcement. An audit run this way would prove nothing, so nothing "
    "proceeds.\n\n"
    "Only a human can fix it: ask the user to restart Claude Code with HOME set "
    "to their home directory. `holtz-start` cannot fix this — it needs the "
    "same path."
)


def exit_boundary_missing(reason: str, hook_type: str = "PreToolUse") -> NoReturn:
    """Refuse the call because the audit boundary is not in place.

    Reached only when a *live* daemon answered with sahjhan's `sandbox_required`
    refusal, which is a fact rather than an inference: the daemon read the
    project's settings and could not confirm the agent is confined.

    What that fact does *not* say is that an audit is still running. The
    daemon is `nohup`'d and torn down only on `finalized`/`idle`, so it
    outlives the session that started it, and its refusal then reaches every
    session in the project and every linked worktree — the socket is anchored
    at the project, not the cwd. Callers therefore ask `audit_abandoned` first
    and let those sessions past; what remains here is a live audit whose
    boundary came down, which is the case this exists for.

    ``HOME_UNRESOLVED`` is the one refusal no daemon issued, and the one
    ``holtz-start`` cannot repair, so it carries its own message.
    """
    message = (
        HOME_MESSAGE if reason == HOME_UNRESOLVED
        else BOUNDARY_MESSAGE.format(reason=reason)
    )
    if hook_type == "PreToolUse":
        exit_block(message)
    exit_warn(message, hook_type)


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
    from _protocol_cache import is_enforcement_fresh, read_cache_with_boundary  # noqa: PLC0415

    if audit_active(cwd):
        cache, boundary, _version = read_cache_with_boundary(cwd)
        # Checked before freshness on purpose: a refusing daemon serves no
        # cache, so `is_enforcement_fresh` is False and this degrade path
        # would otherwise wave through exactly the situation it exists for.
        if boundary:
            exit_boundary_missing(boundary, hook_type)
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


def read_hook_eval(
    stdout: str, returncode: int, stderr: str,
) -> tuple[dict[str, Any] | None, str]:
    """A ``sahjhan --json hook eval`` reply's payload, or why there is none.

    Returns ``(payload, "")`` for a reply a hook can act on and
    ``(None, reason)`` for one it cannot, with ``reason`` ready for
    ``exit_enforcement_error``. Both tool hooks read the reply here, so they
    cannot disagree about which replies are usable or what to call the ones
    that are not.

    Stdout is read whatever the exit code: the CLI exits 1 on a ``block`` and
    still prints the whole reply, so the code is a secondary signal and the
    JSON is the answer. What is unusable is an empty stdout (an argument the
    binary does not know exits 2 and writes only to stderr), bytes that are
    not JSON, and JSON that is not an object — each named with the exit code
    and, when stdout is empty, the engine's own first line of stderr.

    A config or ledger that fails to load is not a decision either: no rule
    ran. The engine answers ``ok: false`` with no ``data`` — ``config_error``
    (exit 3) for a ``protocol.toml`` that does not parse, a missing config dir
    or an unregistered ledger; ``integrity_error`` (exit 2) for a ledger never
    initialised or a sealed config file edited since. ``ok`` is checked before
    ``data`` is unwrapped, because the unwrap falls back to the whole reply and
    the hooks default a missing ``decision`` to ``allow``. The engine's message
    is passed on whole: for a broken seal it is the only place the ways past
    are written.
    """
    def unusable(detail: str) -> tuple[None, str]:
        return None, f"Hook eval returned no usable reply (exit {returncode}: {detail})"

    if not stdout.strip():
        first = next((ln.strip() for ln in stderr.splitlines() if ln.strip()), "")
        return unusable(first or "no output")
    try:
        data = json.loads(stdout)
    except ValueError:
        return unusable("stdout is not JSON")
    if isinstance(data, dict) and data.get("ok") is False:
        error = data.get("error")
        error = error if isinstance(error, dict) else {}
        code = str(error.get("code") or "ok: false")
        message = str(error.get("message") or "").strip()
        return None, (
            f"Hook eval ran no rules (exit {returncode}, {code})"
            + (f": {message}" if message else "")
        )
    payload = data.get("data", data) if isinstance(data, dict) else data
    if not isinstance(payload, dict):
        return unusable(f"a JSON {type(payload).__name__} where an object belongs")
    return payload, ""


def _linked_worktree_main(git_link: str, fallback: str) -> str:
    """The main worktree behind a `.git` *file*, or ``fallback``.

    Two different things put a file where `.git` would normally be a
    directory, and only one of them is part of this project. A linked
    worktree's gitdir carries a ``commondir`` naming the shared repository; a
    submodule's does not, because a submodule *is* its own repository and
    deserves its own daemon. Following the ``gitdir:`` pointer without that
    check would hand every submodule the superproject's socket.
    """
    try:
        with open(git_link, encoding="utf-8") as fh:
            pointer = fh.read()
    except OSError:
        return fallback
    _, sep, rest = pointer.partition("gitdir:")
    if not sep:
        return fallback
    gitdir = rest.strip().splitlines()[0].strip() if rest.strip() else ""
    if not gitdir:
        return fallback
    if not os.path.isabs(gitdir):
        gitdir = os.path.join(os.path.dirname(git_link), gitdir)

    try:
        with open(os.path.join(gitdir, "commondir"), encoding="utf-8") as fh:
            common = fh.read().strip()
    except OSError:
        return fallback  # a submodule, or a gitdir we cannot read
    if not common:
        return fallback
    if not os.path.isabs(common):
        common = os.path.join(gitdir, common)
    # `commondir` names the shared `.git`; the main worktree contains it.
    return os.path.realpath(os.path.dirname(os.path.realpath(common)))


def project_anchor(cwd: str) -> str:
    """The path every system-owned path for ``cwd``'s project hangs off.

    The main worktree of the repository containing ``cwd`` — so a subdirectory,
    and a linked worktree, both resolve to the one place. Anything that is not
    in a repository at all anchors on itself.

    This walks the filesystem rather than shelling out to ``git rev-parse``.
    Every hook calls it, including the ones whose whole job is to report that
    the toolchain is broken, so it must be cheap and it must not raise.
    """
    current = os.path.realpath(cwd)
    while True:
        git_path = os.path.join(current, ".git")
        if os.path.isdir(git_path):
            return current
        if os.path.isfile(git_path):
            return _linked_worktree_main(git_path, current)
        parent = os.path.dirname(current)
        if parent == current:
            return os.path.realpath(cwd)
        current = parent


def audit_data_dir(cwd: str) -> str:
    """Where this project's audit state lives, from anywhere inside it.

    Anchored on the project rather than on the process cwd, for the same
    reason ``boundary_dir`` is and defined in terms of the same expression:
    ``.gitignore`` carries ``docs/holtz/.sahjhan/``, so a checkout produced by
    ``git worktree add`` does not contain it. A fix subagent runs with its
    worktree as cwd, and a cwd-relative probe therefore answers "no audit
    here" for the three actors the fix loop dispatches — turning off manifest
    verification, daemon-death detection, and the fail-closed degrade path for
    exactly the callers enforcement is for.

    The socket was already anchored (D40). The probe next to it was not.
    """
    return os.path.join(project_anchor(cwd), "docs", "holtz", ".sahjhan")


def audit_active(cwd: str) -> bool:
    """Whether an audit's state directory exists for ``cwd``'s project.

    One named fact with several consumers, rather than several careful copies
    of one path expression. Every site that used to build the path inline is
    deciding this same question.
    """
    return os.path.isdir(audit_data_dir(cwd))


def audit_abandoned(cwd: str) -> bool:
    """Whether this project's audit is over, whatever a daemon still answers.

    Two facts settle it, and death detection already writes both: the
    ``terminated`` marker, and a recorded init PID whose process is gone.
    Either one means the session key the ledger is signed with is lost, so
    there is no run left for a gate to protect. Both are read, not just the
    marker: the marker is written by whichever hook notices first, so a gate
    reading only the marker would still refuse the call that was about to
    produce it.

    Freshness cannot answer this question, which is why it is asked
    separately. ``is_enforcement_fresh`` reads the enforcement cache, and the
    caller here has just been refused one — so at exactly this moment
    freshness is False for a live audit and an abandoned one alike.

    Two absences are deliberately answered "not abandoned". No audit directory
    at all means a daemon is answering for a project whose state is gone, and
    no init PID recorded means pre-init or legacy — neither is evidence of
    death, and reading either as death would hand the release to the audits
    death detection cannot see.
    """
    data_dir = audit_data_dir(cwd)
    if not os.path.isdir(data_dir):
        return False
    if os.path.isfile(os.path.join(data_dir, "terminated")):
        return True
    init_pid = _read_init_pid(cwd)
    return init_pid is not None and not _is_process_alive(init_pid)


def boundary_dir(cwd: str | None = None) -> str:
    """Return this project's out-of-tree directory for daemon state.

    Holds the daemon socket and the sandbox-settings backup — the two things
    that must survive *outside* the project the agent is confined to. Inside
    the tree, the socket path sits in agent-writable territory: deletable, and
    squattable between daemon restarts. sahjhan's fuse refuses to serve at all
    when the socket resolves inside the project root (``socket_inside_project``),
    so this is not merely tidiness.

    Keyed by a digest of the *project anchor* rather than of the process cwd,
    and short enough to stay inside the 104-byte macOS ``AF_UNIX`` limit. Two
    checkouts of the same repo still get different sockets — that is what the
    digest is for — while a fix subagent working in a linked worktree resolves
    the socket the main daemon is bound to (P0.3 / D40). Keyed on cwd, that
    subagent found nothing listening, and since ``tdd_evidence`` is
    ``restricted`` its courier could not write one, so the per-actor TDD gate
    could never open for it.

    If ``~`` cannot be resolved the result is a relative path, and a relative
    socket path names a different file from every cwd — so it is never read
    through. ``socket_unplaceable`` names the case, and the cache reader asks
    it before connecting: while an audit is active (``audit_active``) that is
    a boundary refusal and every consumer fails closed; with no audit it reads
    as no daemon. ``holtz-start`` refuses to arm on it.
    """
    if cwd is None:
        cwd = os.getcwd()
    key = hashlib.sha256(project_anchor(cwd).encode()).hexdigest()[:12]
    return os.path.join(os.path.expanduser("~"), ".holtz", "run", key)


def socket_unplaceable() -> bool:
    """Whether the daemon socket has nowhere safe to go.

    True when no ``SAHJHAN_DAEMON_SOCKET`` override names one and ``~`` does
    not expand to an absolute path — HOME unset on a uid with no passwd entry,
    or HOME itself relative. ``boundary_dir`` would then hand back a path
    relative to whichever cwd asks.
    """
    if os.environ.get("SAHJHAN_DAEMON_SOCKET"):
        return False
    return not os.path.isabs(os.path.expanduser("~"))


def _get_daemon_socket_path(cwd: str | None = None) -> str:
    """Return the path to the sahjhan daemon Unix socket.

    Checks SAHJHAN_DAEMON_SOCKET env var first — the same override the Rust
    daemon honors since sahjhan 0.21.0, which is how ``holtz-start`` binds the
    socket where this resolves it. Test fixtures use it too (short tmp paths,
    for the macOS AF_UNIX 104-char limit).

    Both sides derive the default from one expression, so an arming hook and a
    consumer hook cannot drift onto different sockets. When they do disagree —
    a hook firing with a different cwd — the socket is simply unreachable, and
    the consumer fails closed rather than talking to the wrong daemon.
    """
    override = os.environ.get("SAHJHAN_DAEMON_SOCKET")
    if override:
        return override
    return os.path.join(boundary_dir(cwd), "daemon.sock")


class DaemonError(RuntimeError):
    """A request that reached the daemon and was refused by it.

    The wire protocol answers with a structured ``error`` code alongside the
    human-readable ``message``, but this was collapsing both into a bare
    ``RuntimeError(message)``. Callers that need to tell refusals apart —
    ``auth_failed`` means enforcement is broken, ``not_found`` just means
    nothing is stored yet — were left with nothing but the prose to match on.
    Subclasses RuntimeError, so every existing ``except RuntimeError`` handler
    behaves exactly as before.
    """

    def __init__(self, message: str, error: str = "", reason: str = "") -> None:
        super().__init__(message)
        self.error = error
        self.reason = reason


def _daemon_request(sock_path: str, request: dict) -> dict:
    """Send a JSON request to the sahjhan daemon and return the response.

    Raises DaemonError (a RuntimeError) if the daemon refuses the request, and
    OSError if the socket is unreachable. The two are different facts: a
    refusal proves the daemon is alive.
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
        raise DaemonError(
            f"sahjhan daemon error: {response.get('message', 'unknown error')}",
            error=str(response.get("error") or ""),
            reason=str(response.get("reason") or ""),
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
    pid_file = os.path.join(audit_data_dir(cwd), "daemon-init-pid")
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
    marker = os.path.join(audit_data_dir(cwd), "terminated")
    with open(marker, "w", encoding="utf-8") as f:
        f.write("reason: daemon_pid_dead\n")
        f.write(f"init_pid: {init_pid}\n")
        f.write(f"detected_by: {detected_by}\n")
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")  # noqa: UP017
        f.write(f"detected_at: {ts}\n")
