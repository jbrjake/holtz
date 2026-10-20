"""Shared protocol enforcement cache — read/write state, detect commands, compute obligations.

Used by commit_gate.py (PreToolUse) and protocol_tracker.py (PostToolUse).
"""
from __future__ import annotations

import base64
import json
import os
import re
import shlex
import sys
from collections.abc import Iterable
from datetime import datetime, timezone
from typing import Any, NamedTuple

sys.path.insert(0, os.path.dirname(__file__))

from _shell_norm import shell_segments  # noqa: E402

_ENFORCEMENT_FRESHNESS_MINUTES = 30


def _read_perspectives_total() -> int:
    """Read perspective count from protocol.toml, falling back to 13."""
    toml_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "protocol.toml")
    try:
        import tomllib  # Python 3.11+
    except ModuleNotFoundError:
        try:
            import tomli as tomllib  # type: ignore[no-redef]  # pip install tomli for <3.11
        except ModuleNotFoundError:
            return 13
    try:
        with open(toml_path, "rb") as f:
            cfg = tomllib.load(f)
        values = cfg.get("sets", {}).get("perspective", {}).get("values", [])
        return len(values) if values else 13
    except (OSError, KeyError, ValueError):
        return 13


def empty_cache() -> dict[str, Any]:
    return {
        "active": True,
        "state": "",
        # Keyed by actor — see ORCHESTRATOR and pending_commits below.
        "unregistered_commits": {},
        # The gate's own predicate, resolved from protocol.toml [queries] by
        # protocol_tracker. The key IS the query name: block, derivation and
        # gate all say the same word, which is what enforcement_lint H8 checks.
        "pattern_analysis_overdue": False,
        "perspective": "",
        "perspectives_done": 0,
        "perspectives_total": _read_perspectives_total(),
        # Keyed by actor — see ORCHESTRATOR and stall_counts below.
        "stall": {},
        "last_refresh": "",
        "last_sahjhan_cmd": "",
    }


# The daemon's refusal code when its sandbox fuse trips: the boundary that
# keeps the agent off this socket is not configured. Named once here, so the
# hooks that must fail closed on it and the hook that arms it say the same
# word. A live daemon is the only thing that can produce it, which is what
# keeps the fail-closed path from firing outside a real audit.
BOUNDARY_REFUSED = "sandbox_required"

# The daemon's refusal when a conditional mutation's ``expect_version`` does not
# match what it holds (sahjhan 0.27.0, #49). Named once, because the retry that
# handles it and the writer that opts into it have to say the same word: the
# compare runs inside the daemon's own vault lock, so this code is the only
# signal a caller gets that it lost a race, and matching on the prose instead
# would go quiet the day the message is reworded.
VERSION_CONFLICT = "version_conflict"

# The daemon's answer to a read when nothing is stored yet — the one ``None``
# a writer may treat as "create it".
NOT_FOUND = "not_found"


def read_cache_with_boundary(
    cwd: str,
) -> tuple[dict[str, Any] | None, str | None, str | None]:
    """Read enforcement state, its version, and a missing-boundary refusal.

    Returns ``(cache, boundary_refusal, version)``. The refusal is the daemon's
    own machine-readable reason when it declined because the sandbox boundary
    is absent, and ``None`` otherwise.

    ``version`` is the opaque CAS token for the blob as *stored*, which a
    caller hands back as ``expect_version`` to make its write conditional on
    nothing having changed since this read. It is third rather than second
    because every gate here reads the first two and none of them writes.
    ``None`` means the daemon did not offer one, and a write carrying ``None``
    is unconditional — the pre-0.27.0 behaviour.

    The token hashes the stored bytes, not the bytes this call returns: the
    daemon overlays ``state`` from the ledger on read, so a *transition* moves
    what you see here without invalidating the token. Only a write does that.

    The two have to be told apart because they mean opposite things. A cache
    of ``None`` from an unreachable daemon means "no audit here" and allowing
    is right. A ``None`` because the daemon *refused* means an audit is very
    much running and its protection just evaporated — treating that as "no
    audit" is how a tripped fuse deletes enforcement instead of enforcing it.

    Only catches expected daemon-unreachable errors. Bugs in parsing code
    (e.g., bad base64, unexpected JSON structure) are NOT caught — they
    should crash visibly rather than silently disabling all enforcement.
    """
    cache, boundary, version, _failed = read_cache_for_write(cwd)
    return cache, boundary, version


def read_cache_for_write(
    cwd: str,
) -> tuple[dict[str, Any] | None, str | None, str | None, bool]:
    """``read_cache_with_boundary``, plus whether the read failed.

    A whole-blob writer needs the one distinction no gate does. ``None`` from
    a daemon that answered ``not_found`` means nothing is stored yet, and the
    writer is what creates the cache. ``None`` from a read that did not
    establish what is stored — unreachable, refused, errored, unreadable —
    means the daemon may hold state this caller cannot see, and writing
    ``empty_cache()`` over it erased every pending commit and stall count.
    The fourth element is True for that second case only.

    An unplaceable socket (``socket_unplaceable``) is decided here, before any
    connect, because every gate reads through this function: while an audit is
    active it is a ``home_unresolved`` boundary refusal, so each consumer fails
    closed, and with no audit it reads as no daemon.
    """
    from _common import (
        HOME_UNRESOLVED,
        DaemonError,
        _daemon_request,
        _get_daemon_socket_path,
        audit_active,
        socket_unplaceable,
    )
    if socket_unplaceable():
        return None, (HOME_UNRESOLVED if audit_active(cwd) else None), None, True
    try:
        sock_path = _get_daemon_socket_path(cwd)
        try:
            resp = _daemon_request(sock_path, {"op": "enforcement_read"})
        except DaemonError as exc:
            if exc.error == BOUNDARY_REFUSED:
                return None, exc.reason or BOUNDARY_REFUSED, None, True
            if exc.error == NOT_FOUND:
                return None, None, None, False
            raise
        version = resp.get("version")
        return json.loads(base64.b64decode(resp["data"])), None, version, False
    except (OSError, ConnectionError, RuntimeError, KeyError, json.JSONDecodeError, ValueError):
        # OSError/ConnectionError: daemon socket unreachable
        # RuntimeError: daemon returned an error (from _daemon_request)
        # KeyError: daemon response missing "data" field
        # json.JSONDecodeError: daemon sent invalid/empty JSON (corrupt or dead)
        # ValueError: base64 decode failure (corrupt daemon response)
        return None, None, None, True


def read_cache(cwd: str) -> dict[str, Any] | None:
    """Read enforcement state from the sahjhan daemon.

    Returns None if the daemon is unreachable or has no enforcement state
    (fail-open, same behavior as the old "file not found" path).

    Callers that gate behavior should use ``read_cache_with_boundary`` — this
    one cannot distinguish "nothing is running" from "the daemon refused",
    and those need opposite answers.
    """
    return read_cache_with_boundary(cwd)[0]


def _mutate(cwd: str, request: dict[str, Any]) -> dict[str, Any]:
    """Send one enforcement mutation, mapping unreachability to RuntimeError.

    The three mutations differ only in their op and payload key, so the
    connect-and-translate wrapper is here rather than three times over. A
    ``DaemonError`` propagates unchanged: it is already a ``RuntimeError``, and
    its ``error`` code is what a caller reads to tell ``version_conflict``
    (re-read and retry) from every other refusal (give up).
    """
    from _common import _daemon_request, _get_daemon_socket_path
    sock_path = _get_daemon_socket_path(cwd)
    try:
        return _daemon_request(sock_path, request)
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(f"sahjhan daemon unreachable: {exc}") from exc


def _encoded(payload: dict[str, Any]) -> str:
    return base64.b64encode(json.dumps(payload).encode()).decode()


def _conditional(request: dict[str, Any], expect_version: str | None) -> dict[str, Any]:
    """The request, made conditional only when a token was actually held.

    Omitted rather than sent as ``None``: an absent ``expect_version`` is the
    unconditional mutation, which is what a caller that never got a token from
    its read must still be able to perform.
    """
    if expect_version is not None:
        request["expect_version"] = expect_version
    return request


def write_cache(
    cwd: str, cache: dict[str, Any], expect_version: str | None = None
) -> None:
    """Write enforcement state to the sahjhan daemon.

    The daemon sets last_refresh to the current UTC timestamp.
    Raises RuntimeError if the daemon is unreachable.

    ``expect_version`` makes the write conditional on the stored blob still
    being the one the caller read. This is the mechanism for a change that
    genuinely spans the whole blob — discharging a commit from whichever
    actor's bucket holds it — where a per-actor merge cannot express what
    changed. The compare happens inside the daemon's vault lock, so it closes
    the race rather than moving it: a caller that lost raises ``DaemonError``
    with ``error == VERSION_CONFLICT`` and can re-read and retry.
    """
    _mutate(cwd, _conditional(
        {"op": "enforcement_write", "data": _encoded(cache)}, expect_version,
    ))


def update_cache(cwd: str, patch: dict[str, Any]) -> dict[str, Any]:
    """Atomically replace whole top-level fields of enforcement state.

    Sends a partial dict whose keys replace the stored ones outright, whatever
    their shape. Returns the full state afterwards. Raises RuntimeError if the
    daemon is unreachable or no state exists.

    Right wherever the caller owns the entire key — a scalar like
    ``pattern_analysis_overdue``, or a map no other actor writes. For the
    per-actor maps (``stall``, ``unregistered_commits``) it is the defect item
    42 is about: replacing the key means sending a whole map computed from a
    snapshot, and a sibling's write landing in between is overwritten. Use
    ``merge_cache`` there.
    """
    resp = _mutate(cwd, {"op": "enforcement_update", "patch": _encoded(patch)})
    return json.loads(base64.b64decode(resp["data"]))


def merge_cache(
    cwd: str, patch: dict[str, Any], expect_version: str | None = None
) -> dict[str, Any]:
    """Atomically merge a patch into enforcement state, recursing into objects.

    RFC 7386 (sahjhan 0.27.0, #49), which is what makes a per-actor write
    expressible: ``{"stall": {actor: 3}}`` changes that actor's entry and
    leaves every sibling exactly as the daemon holds it, so a caller never has
    to send a map it computed from a snapshot. Returns the full state
    afterwards. Raises RuntimeError if the daemon is unreachable or no state
    exists.

    Two rules decide how a patch is spelled:

    - ``None`` **deletes** the key, at any depth. That is how a clear is sent;
      a merge cannot store a JSON null, so there is no ambiguity to resolve.
    - Arrays **replace** wholesale — they are not merged element-wise. A patch
      naming one actor's commit list therefore carries that actor's *whole*
      list. It is a per-actor write, not an append, so an actor racing
      **itself** off one stale snapshot still loses a write; the merge buys
      safety from siblings only. ``expect_version`` is what covers that case.
    """
    resp = _mutate(cwd, _conditional(
        {"op": "enforcement_merge", "patch": _encoded(patch)}, expect_version,
    ))
    return json.loads(base64.b64decode(resp["data"]))


def is_enforcement_fresh(
    cache: dict[str, Any] | None,
    threshold_minutes: int = _ENFORCEMENT_FRESHNESS_MINUTES,
) -> bool:
    """Check if enforcement should be active based on sahjhan command recency.

    Returns True if a sahjhan command was run within the threshold window,
    indicating an active audit session. Returns False if the cache is
    missing, the timestamp is absent/unparseable, or the timestamp is stale.
    """
    if cache is None:
        return False
    ts = cache.get("last_sahjhan_cmd", "")
    if not ts:
        return False
    try:
        from datetime import timedelta
        last = datetime.fromisoformat(ts)
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)  # noqa: UP017
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=threshold_minutes)  # noqa: UP017
        return last >= cutoff
    except (ValueError, TypeError):
        return False


def parse_status_text(text: str) -> dict[str, Any]:
    """Parse the text output of ``sahjhan status`` into a dict.

    Returns a dict with keys: current_state, terminal, event_count,
    run_number, sets (dict of set_name → {complete, total}),
    available_transitions (list of str), current_perspective.
    """
    result: dict[str, Any] = {
        "current_state": "",
        "terminal": False,
        "event_count": 0,
        "run_number": "0",
        "ledger_name": "",
        "ledger_source": "",
        "sets": {},
        "available_transitions": [],
        "current_perspective": "unknown",
    }

    lines = text.strip().splitlines()
    for line in lines:
        stripped = line.strip()

        # "Ledger: run-31 (active-ledger marker)"
        m = re.match(r"^Ledger:\s+(\S+)(?:\s+\((.+)\))?", stripped)
        if m:
            ledger_name = m.group(1)
            result["ledger_name"] = ledger_name
            result["ledger_source"] = m.group(2) or ""
            # Extract run number from "run-N" pattern
            rm = re.match(r"^run-(\d+)$", ledger_name)
            if rm:
                result["run_number"] = rm.group(1)
            continue

        # "state: fix_loop (59 events, chain valid)"
        m = re.match(r"^state:\s+(\S+)\s+\((\d+)\s+events", stripped)
        if m:
            result["current_state"] = m.group(1)
            result["event_count"] = int(m.group(2))
            continue

        # "  perspective: 3/13 [✓ component, ..."
        m = re.match(r"^\s*(\w[\w-]*):\s+(\d+)/(\d+)\s+\[(.+)\]", stripped)
        if m:
            set_name = m.group(1)
            complete = int(m.group(2))
            total = int(m.group(3))
            members_text = m.group(4)
            result["sets"][set_name] = {"complete": complete, "total": total}
            # Parse individual members to find the first incomplete one
            if set_name == "perspective":
                for member in members_text.split(","):
                    member = member.strip()
                    if member.startswith("\u2713"):
                        continue  # ✓ = complete
                    # First member without ✓ is the current perspective
                    # Strip any prefix markers (· etc)
                    name = re.sub(r"^[·\s]+", "", member).strip()
                    if name:
                        result["_first_incomplete_perspective"] = name
                        break
            continue

        # "  fix_commit: ready" or "  fix_commit: blocked"
        # BH-013: Use \s* (not \s+) because `stripped` has no leading whitespace.
        m = re.match(r"^\s*(\w[\w_]*):\s+(ready|blocked)", stripped)
        if m:
            transition = m.group(1)
            status = m.group(2)
            if status == "ready":
                result["available_transitions"].append(transition)
            continue

    # Terminal states
    terminal_states = {"finalized"}
    result["terminal"] = result["current_state"] in terminal_states

    # Extract current perspective from sets
    perspective_set = result["sets"].get("perspective", {})
    if perspective_set:
        result["perspectives_done"] = perspective_set.get("complete", 0)
        result["perspectives_total"] = perspective_set.get("total", 13)
        if "_first_incomplete_perspective" in result:
            result["current_perspective"] = result.pop("_first_incomplete_perspective")
        elif perspective_set.get("complete", 0) == perspective_set.get("total", 13):
            result["current_perspective"] = "all_complete"

    return result


def _split_shell_segments(cmd: str) -> list[str]:
    """Split a shell command on operators (&&, ||, ;, |, &) but not redirects.

    Segmentation and indirection are ``_shell_norm``'s — this used to hold
    its own ``re.split``, with a comment that argued for the hole and for
    single ownership in the same breath ("avoid splitting on single &" …
    "Must match _sahjhan_bootstrap.py's split pattern to avoid divergence").

    What stays here is what only this caller wants: the redirect strip and
    the leading export/assignment strip, applied per segment.
    """
    result = []
    for seg in shell_segments(cmd):
        # Strip shell redirections: 2>&1, >&2, 2>/dev/null, etc. The shared
        # splitter keeps them (a redirect target is evidence to another
        # caller); the predicates built on these segments only want the
        # command, so they come off here.
        seg = re.sub(r'\d*>&?\d+', '', seg)
        seg = re.sub(r'\d*>/dev/null', '', seg).strip()
        if not seg:
            continue
        # Strip all leading env var assignments (FOO=bar, export X=1, etc.)
        # Handles quoted values with spaces: FOO="bar baz", FOO='bar baz'.
        # Uses + quantifier to handle multiple assignments in one pass.
        seg = re.sub(
            r'^(?:(?:export\s+)?\w+=(?:"[^"]*"|\'[^\']*\'|\S*)\s*)+',
            '', seg,
        ).strip()
        # After stripping, segment may be empty (e.g., "export FOO=bar")
        if seg:
            result.append(seg)
    return result


def is_git_commit(cmd: str) -> bool:
    """Detect git commit commands (not amend).

    Only matches ``git commit`` at the start of a shell segment (after
    ;, &&, ||, |, or start of string). Does not match git commit inside
    echo, comments, or quoted strings.

    Checks for ``--amend`` as a CLI flag (word boundary), not as a
    substring of the commit message.
    """
    for segment in _split_shell_segments(cmd):
        seg = segment.strip()
        # Strip leading env var assignments (VAR=x git commit ...)
        # Handles quoted values: VAR="foo bar" git commit ...
        stripped_seg = re.sub(r"""^\s*(?:\w+=(?:"[^"]*"|'[^']*'|\S*)\s+)*""", "", seg)
        if not re.match(r"git\s+commit\b(?!-)", stripped_seg):
            continue
        # This segment starts with git commit — check for --amend
        stripped = re.sub(r'-m\s+(?:"[^"]*"|\'[^\']*\'|\S+)', '', seg)
        if not re.search(r"(?<!\w)--amend\b", stripped):
            return True
    return False


# Commands that only inspect the tree. Deliberately narrow: this is a list
# of ways to *look at the repository*, not a list of harmless programs. A
# command earns a place here by being unable to change the tree — which is
# why `echo`, `awk` and `xargs` are absent (they either aren't inspection or
# can be steered into writing), and why the entries that CAN write under a
# flag carry an explicit flag check below.
_READ_ONLY_COMMANDS = frozenset({
    "cat", "cd", "cmp", "column", "cut", "diff", "dirname", "basename",
    "du", "file", "find", "git", "grep", "egrep", "fgrep", "head", "jq",
    "ls", "nl", "od", "pwd", "readlink", "realpath", "rg", "ag", "sed",
    "sort", "stat", "strings", "tail", "tr", "tree", "true", "type",
    "uniq", "wc", "which", "xxd",
})

# Subcommands of `git` that read the repository without changing it.
# Omissions are deliberate: `branch`, `tag`, `config`, `remote`, `stash`
# and `checkout` all have writing forms that share the reading spelling.
_READ_ONLY_GIT_SUBCOMMANDS = frozenset({
    "blame", "cat-file", "describe", "diff", "grep", "log", "ls-files",
    "ls-tree", "rev-list", "rev-parse", "shortlog", "show", "status",
})

# Flags that turn a read-only command into a writing one.
#
# Every spelling a flag has must be listed. Matching is `p == flag or
# p.startswith(flag)`, which reaches a flag's *argument* (`-i.bak`,
# `--output=x`) but not its other name: `"--in-place".startswith("-i")` is
# False, because the second dash comes before the letter. So a table carrying
# only the short form classifies the long form as read-only, and the direction
# that costs something is exactly this one — a write that accrues no stall.
# The reverse, listing a spelling a given tool does not have, costs a nudge.
_WRITING_FLAGS = {
    "sed": ("-i", "--in-place"),
    "find": (
        "-delete", "-exec", "-execdir", "-ok", "-okdir",
        "-fprint", "-fprintf", "-fls",
    ),
    # `git diff --output=<file>` writes the diff to a path, and `diff` is on
    # the read-only subcommand list. The prefix match also catches
    # `--output-indicator-*`, which only reads — the cheap direction.
    "git": ("--output",),
    "sort": ("-o", "--output"),
    "tree": ("-o", "--output"),
}

# Redirections that produce no file: fd duplication (2>&1, >&2) and the
# bit bucket. Everything else containing `>` is treated as a write.
_HARMLESS_REDIRECT_RE = re.compile(r'\d*>&\d+|\d*>>?\s*/dev/null')


def _segment_is_read_only(seg: str) -> bool:
    """True if one shell segment only inspects the tree."""
    try:
        parts = shlex.split(seg)
    except ValueError:
        return False  # unbalanced quotes — can't reason, assume it writes
    if not parts:
        return False
    head = os.path.basename(parts[0].lstrip("\\").strip("\"'"))
    if head not in _READ_ONLY_COMMANDS:
        return False
    for flag in _WRITING_FLAGS.get(head, ()):
        if any(p == flag or p.startswith(flag) for p in parts[1:]):
            return False
    if head == "git":
        subcommands = [p for p in parts[1:] if not p.startswith("-")]
        if not subcommands or subcommands[0] not in _READ_ONLY_GIT_SUBCOMMANDS:
            return False
    return True


def is_read_only_cmd(cmd: str) -> bool:
    """True if every segment of ``cmd`` only inspects the tree.

    Used by the stall counter, which asks "how many commands have gone by
    without the protocol moving?" Reading cannot move the protocol and has
    no event to emit, so counting it produces a block the reader cannot
    avoid except by running a protocol command purely to reset a number.
    Same reasoning that already exempts test and lint commands.

    Conservative by construction: an unrecognized command, an unparseable
    segment, or any write redirect anywhere on the line disqualifies the
    whole line. Misreading a write as a read would let real work escape the
    counter; misreading a read as a write only costs a nudge.
    """
    if not cmd.strip():
        return False
    if ">" in _HARMLESS_REDIRECT_RE.sub("", cmd):
        return False
    segments = _split_shell_segments(cmd)
    return bool(segments) and all(_segment_is_read_only(seg) for seg in segments)


def named_query_sql(config_dir: str, name: str) -> str | None:
    """The SQL of a `[queries.<name>]` predicate, read from the protocol config.

    Reading it rather than restating it is the whole point: there is one
    predicate, and every consumer resolves the same one.
    """
    try:
        import tomllib  # Python 3.11+
    except ModuleNotFoundError:
        try:
            import tomli as tomllib  # type: ignore[no-redef]
        except ModuleNotFoundError:
            return None
    try:
        with open(os.path.join(config_dir, "protocol.toml"), "rb") as fh:
            queries = tomllib.load(fh).get("queries", {})
    except (OSError, tomllib.TOMLDecodeError):
        return None
    sql = queries.get(name, {}).get("sql")
    return sql if isinstance(sql, str) else None


def query_named_rows(
    binary: str, config_dir: str, cwd: str, name: str,
) -> list[dict[str, Any]] | None:
    """Run a `[queries.<name>]` predicate and return its rows.

    Runs sahjhan's generic `query` primitive — the same ledger the gates
    evaluate, the same SQL the gates use, so block condition and evidence
    cannot drift apart. Returns None on any failure (binary or daemon
    unavailable, timeout, non-zero exit, malformed output, or the query
    missing from the config) so callers can decide what an unanswerable
    question means for them rather than being handed a fabricated answer.

    ``None`` and ``[]`` are different answers and callers must treat them so:
    the first is "the ledger could not be asked", the second is "the ledger
    says nothing matches".
    """
    import subprocess

    sql = named_query_sql(config_dir, name)
    if sql is None:
        return None
    try:
        result = subprocess.run(
            [binary, "--config-dir", config_dir, "query", sql, "--format", "json"],
            capture_output=True, text=True, timeout=5, cwd=cwd,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    try:
        rows = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    return rows if isinstance(rows, list) else None


def query_named_predicate(
    binary: str, config_dir: str, cwd: str, name: str,
) -> bool | None:
    """Evaluate a `[queries.<name>]` predicate against the active ledger.

    None on any failure, for the reasons ``query_named_rows`` gives — plus
    one of its own: a predicate that returns no row at all has not answered
    "false", it has failed to answer.
    """
    rows = query_named_rows(binary, config_dir, cwd, name)
    if rows is None:
        return None
    try:
        # A boolean predicate renders as the string "true"/"false", which is
        # also exactly what the gate's `expect` compares against.
        return str(next(iter(rows[0].values()))).lower() == "true"
    except (StopIteration, IndexError, TypeError, AttributeError):
        return None


# What the ledger says each resolution registered, by name. `fix_commit` and
# `merge_finding` both auto-emit `finding_resolved` with `commit_hash` stamped
# from `git rev-parse --short=7 HEAD`, so the ledger has always been able to
# say which commit a transition registered — the cache could not, and that is
# the difference item 32 turned on. `hardening_batch.py` asks the same
# question for its own reason; resolving the name rather than restating the
# SQL is what keeps there being one of it (H7).
#
# The rows carry the finding id as well, for item 50: see the query's own
# comment in `protocol.toml`, and `pending_commits_discharged` below.
FINDING_RESOLUTIONS_QUERY = "finding_resolutions"

# git's own floor for an unambiguous abbreviation, and the width the emit
# stamps. Below it a "hash" is a prefix of everything — an empty string would
# discharge every bucket — so anything shorter is not an answer.
MIN_ABBREV = 7


class Resolutions(NamedTuple):
    """The two things a `finding_resolved` row can identify a fix by.

    Both come off one query and one round-trip, because they are two readings
    of one fact — "this fix is registered" — and a caller that fetched them
    separately could be handed a ledger that moved in between.
    """

    #: Hashes, as stamped at `HEAD` when the transition ran.
    commits: list[str]
    #: The finding ids those resolutions closed. What a rewrite preserves.
    findings: list[str]


def registered_resolutions(
    binary: str, config_dir: str, cwd: str,
) -> Resolutions | None:
    """What the ledger records every finding resolution against.

    None when the ledger could not be asked. Empty lists are an answer: nothing
    is registered, so no charge may be discharged.
    """
    rows = query_named_rows(binary, config_dir, cwd, FINDING_RESOLUTIONS_QUERY)
    if rows is None:
        return None
    hashes = []
    findings = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        value = str(row.get("commit_hash") or "").strip()
        if len(value) >= MIN_ABBREV:
            hashes.append(value)
        # `sahjhan query --format json` spells an absent optional column as the
        # four-character string "NULL", so `_optional`'s lesson applies: an id
        # is only an id if it is one, and the empty string would be a substring
        # of every commit message ever written.
        finding = str(row.get("id") or "").strip()
        if finding and finding != "NULL":
            findings.append(finding)
    return Resolutions(hashes, findings)


def same_commit(left: str, right: str) -> bool:
    """Whether two abbreviations name one commit.

    The tracker charges whatever width `git commit` printed (7 in this repo,
    wider in a repo with more objects); the ledger stamps `--short=7`. So the
    two ends legitimately differ in length and one is a prefix of the other.
    """
    if len(left) < MIN_ABBREV or len(right) < MIN_ABBREV:
        return False
    return left.startswith(right) or right.startswith(left)


def _segment_is_sahjhan(seg: str) -> bool:
    """True if a single shell segment invokes the sahjhan CLI.

    phase-recon.md prescribes ``nohup sahjhan ... daemon start &`` for the
    daemon-start step. Skip ``nohup``/``env`` wrappers and leading env-var
    assignments so the downstream hooks (commit_gate, bash_guard,
    protocol_tracker) still treat it as a sahjhan invocation — otherwise
    protocol_tracker never stamps last_sahjhan_cmd, enforcement looks stale,
    and the stall counter ticks on a legitimate setup command.
    """
    parts = seg.split()
    idx = 0
    while idx < len(parts):
        tok = parts[idx]
        if tok in ("nohup", "env"):
            idx += 1
        elif "=" in tok and not tok.startswith("-"):
            # env var assignment form: ``env FOO=bar sahjhan …`` or
            # bare ``FOO=bar sahjhan …``
            idx += 1
        else:
            break
    # Quoting is spelling, not meaning: ``"$SAH" status`` resolves to a
    # quoted path, and a quoted path names the same binary as a bare one.
    p0 = parts[idx].strip("\"'") if idx < len(parts) else ""
    return bool(parts) and (
        p0 == "sahjhan"
        or p0.endswith("/sahjhan")
        or "/sahjhan-" in p0
        or p0.startswith("sahjhan-")
    )


def is_sahjhan_cmd(cmd: str) -> bool:
    """Detect commands that are exclusively sahjhan CLI invocations.

    Returns True only when ALL non-empty segments are sahjhan commands.
    A chained command like ``git commit; sahjhan status`` returns False
    because the git-commit segment is not a sahjhan invocation.

    Handles shell redirections (2>&1) and leading export/env-var prefixes
    by stripping them before segment analysis.
    """
    segments = _split_shell_segments(cmd)
    if not segments:
        return False
    return all(_segment_is_sahjhan(seg) for seg in segments)


def contains_sahjhan_cmd(cmd: str) -> bool:
    """Detect commands where AT LEAST ONE segment invokes the sahjhan CLI.

    Unlike ``is_sahjhan_cmd`` (every segment), this matches wrapped re-sync
    calls like ``cd repo && sahjhan status | head``. Used by the stall
    ("N commands without protocol event") nudge — a re-sync prompt, not a
    security gate — so any line that actually runs a sahjhan enforcement
    subcommand is allowed to clear it (holtz #70 item 1). The security gates
    (TDD, managed-path) keep using the stricter checks.
    """
    return any(_segment_is_sahjhan(seg) for seg in _split_shell_segments(cmd))


def sahjhan_segments(cmd: str) -> list[str]:
    """The segments of ``cmd`` that actually invoke the sahjhan CLI.

    What a caller wants when it needs to read a sahjhan command's *arguments*
    rather than merely detect one: the words in `cd repo && echo "run
    transition fix_commit"` are not arguments to anything, and a scan over the
    whole line cannot tell them from the ones that ran.
    """
    return [seg for seg in _split_shell_segments(cmd) if _segment_is_sahjhan(seg)]


# ── The stall counter's actor (P3.2) ──
#
# The counter asks one actor "how many commands have you run without the
# protocol moving?", and until now it asked the whole run at once. On the
# audited run that meant 54 distinct actors driving one number: 112 of 114
# denials fired at exactly stall=16, and a subagent that had done nothing but
# read was blocked by traffic it never generated. It cut the other way too —
# any sibling running `sahjhan status` for its own reasons wiped the count,
# so the number a gate read was neither a fair charge nor a reliable one.
#
# Claude Code puts `agent_id` on a hook event fired from inside a subagent and
# omits it on the main thread, so the orchestrator is the empty-string actor:
# a real bucket like every other, never a wildcard that could swallow a
# subagent's count. Verified against the shipped binary, whose own hook-input
# documentation states `agent_type` is "present when the hook fires from
# within a subagent (alongside agent_id)".
ORCHESTRATOR = ""


def event_actor(event: dict[str, Any]) -> str:
    """Which actor made this tool call — a subagent, or the orchestrator."""
    return str(event.get("agent_id") or ORCHESTRATOR)


def event_auditor(event: dict[str, Any]) -> str:
    """Whose audit this tool call belongs to: ``justine`` or ``holtz``.

    Read off ``agent_type``, which the host sets on a hook event from inside a
    subagent — the same shipped-binary fact ``ORCHESTRATOR`` rests on. The
    plugin's Justine agent arrives as ``justine`` or, dispatched by its
    qualified name, ``holtz:justine``, so the last ``:``-segment decides.
    Everything else — the orchestrator, the merge agent, a fix subagent — is
    working Holtz's run.
    """
    agent_type = str(event.get("agent_type") or "")
    return "justine" if agent_type.rsplit(":", 1)[-1] == "justine" else "holtz"


def _actor_patch(
    cache: dict[str, Any] | None, key: str, whole: dict[str, Any], actor: str
) -> dict[str, Any]:
    """``whole`` narrowed to the single entry it changed, for a merge patch.

    Item 42: the per-actor maps were read, changed and written back whole, so
    a sibling's write landing inside that window was overwritten. The functions
    that compute ``whole`` are honest about the *value* they return — one
    actor's entry differs, all others are copied through — and a merge naming
    only that entry is what makes the same true of the **write**.

    ``actor`` absent from ``whole`` is a clear, which RFC 7386 spells ``null``.

    The exception is the pre-keying shape: a bare int under ``stall``, a flat
    list under ``unregistered_commits``, written by a holtz older than the
    keying. ``stall_counts`` and ``pending_commits`` migrate it into the
    orchestrator's bucket precisely so a run upgrading mid-flight is not handed
    a free reset — and RFC 7386 replaces a scalar with the patch object rather
    than merging into it, which would drop that migration silently. So when the
    daemon still holds the old shape the patch is the whole migrated map, which
    under the very same replace rule lands exactly what ``update_cache`` sent.
    There is no sibling to lose in that case: the old shape has one bucket.
    """
    if isinstance((cache or {}).get(key), dict):
        return {actor: whole.get(actor)}
    return whole


def stall_patch(
    cache: dict[str, Any] | None, whole: dict[str, int], actor: str
) -> dict[str, Any]:
    """A merge patch carrying ``actor``'s stall entry and no other actor's."""
    return {"stall": _actor_patch(cache, "stall", whole, actor)}


def pending_commits_patch(
    cache: dict[str, Any] | None, whole: dict[str, list[str]], actor: str
) -> dict[str, Any]:
    """A merge patch carrying ``actor``'s commit bucket and no other actor's.

    The bucket is sent entire, because RFC 7386 replaces arrays rather than
    concatenating them. So this is a per-actor write and not an append: two of
    one actor's own commits racing off a single snapshot still lose one, which
    is what ``expect_version`` exists for.
    """
    return {"unregistered_commits": _actor_patch(
        cache, "unregistered_commits", whole, actor,
    )}


def stall_counts(cache: dict[str, Any] | None) -> dict[str, int]:
    """Per-actor stall counts, tolerating a cache written before keying.

    A run that upgrades mid-flight has an int stored here. That int was the
    whole run's count, which is the orchestrator's as far as anything can now
    tell, so it lands in that bucket rather than being discarded — losing it
    would hand a stalled run a free reset at exactly the wrong moment.
    """
    raw = (cache or {}).get("stall", {})
    if isinstance(raw, bool):
        return {}
    if isinstance(raw, int):
        return {ORCHESTRATOR: raw} if raw else {}
    if not isinstance(raw, dict):
        return {}
    return {
        str(k): int(v) for k, v in raw.items()
        if isinstance(v, int) and not isinstance(v, bool)
    }


def stall_count(cache: dict[str, Any] | None, actor: str = ORCHESTRATOR) -> int:
    """How many commands this actor has run without a protocol event."""
    return stall_counts(cache).get(actor, 0)


def stall_bumped(cache: dict[str, Any] | None, actor: str, delta: int) -> dict[str, int]:
    """The counts with ``actor`` charged ``delta`` more commands."""
    counts = stall_counts(cache)
    counts[actor] = counts.get(actor, 0) + delta
    return counts


def stall_cleared(cache: dict[str, Any] | None, actor: str) -> dict[str, int]:
    """The counts with ``actor`` re-synced, copying every other actor through.

    Clearing is per-actor for the same reason charging is: a protocol event is
    evidence about the actor that emitted it and about nobody else.

    This describes the value, which is all it can describe. Whether the *write*
    leaves the siblings alone is decided by the caller: send this through
    ``stall_patch`` and ``merge_cache`` and it does, because the patch never
    names them; send it as an ``update_cache`` value and it replaces the map
    with these counts, and a sibling's bump landing since the read is gone.
    """
    counts = stall_counts(cache)
    counts.pop(actor, None)
    return counts


# ── The pending-commit block's actor (P0.3, D41) ──
#
# Same argument as the stall counter one section up, arrived at from the other
# end. The block asks "is there a commit you have not registered?", and asking
# it of the whole run meant the first fix subagent to commit refused every
# other one — while naming `transition fix_commit` as the way out, which is
# the orchestrator's transition, gated on `git log -1` and a tree hash taken
# at the project root. The blocked actor could not reach its own escape.
#
# Clearing is per *commit*, decided by the ledger (see protocol_tracker's
# fix_commit branch). It used to be run-global on the argument that the
# transition registers whatever commit is at HEAD, and that after a
# fast-forward that commit was authored by a subagent the transition cannot
# name. The cache cannot name it — but `fix_commit` auto-emits
# `finding_resolved` stamped with that very hash, so the ledger names it, and
# the question was unasked rather than unanswerable. While it went unasked one
# subagent's registration discharged every sibling's charge: the deny
# direction was keyed and the allow direction, the one that loses the gate,
# was not.
#
# Where the ledger cannot be reached the discharge falls back to the
# orchestrator's bucket alone. That is the safe direction of a fallback:
# losing a clear costs a nudge, losing a charge loses the gate.


def pending_commits(cache: dict[str, Any] | None) -> dict[str, list[str]]:
    """Per-actor unregistered commits, tolerating a cache written before keying.

    A run that upgrades mid-flight has a flat list stored here. That list was
    the whole run's, which is the orchestrator's as far as anything can now
    tell, so it lands in that bucket rather than being discarded — dropping it
    would hand a real pending commit a free pass at exactly the wrong moment.
    """
    raw = (cache or {}).get("unregistered_commits", {})
    if isinstance(raw, list):
        return {ORCHESTRATOR: [str(h) for h in raw]} if raw else {}
    if not isinstance(raw, dict):
        return {}
    return {
        str(k): [str(h) for h in v]
        for k, v in raw.items()
        if isinstance(v, list) and v
    }


def pending_commits_for(
    cache: dict[str, Any] | None, actor: str = ORCHESTRATOR
) -> list[str]:
    """The commits this actor has made and not yet had registered."""
    return pending_commits(cache).get(actor, [])


def pending_commits_appended(
    cache: dict[str, Any] | None, actor: str, commit_hash: str
) -> dict[str, list[str]]:
    """The buckets with ``commit_hash`` charged to ``actor``, others copied through.

    A statement about the value. ``pending_commits_patch`` + ``merge_cache`` is
    what makes it a statement about the write as well — and note that even then
    the merge sends ``actor``'s whole list, because RFC 7386 replaces arrays.
    """
    buckets = pending_commits(cache)
    buckets.setdefault(actor, []).append(commit_hash)
    return buckets


def pending_commits_discharged(
    cache: dict[str, Any] | None,
    registered: list[str],
    rewritten: Iterable[str] = (),
) -> dict[str, list[str]]:
    """The buckets with every registered or rewritten commit removed.

    A charge is discharged by the commit it names being registered, so this
    removes commits rather than emptying buckets: an actor holding a second,
    unregistered commit stays charged for that one. Both arms obey that — a
    rewrite discharges the charge it moved and not its author's others.

    ``registered`` is matched by hash. A registered hash that no bucket holds
    discharges nothing, and inventing a nearest match would discharge a commit
    nobody registered.

    ``rewritten`` is the item-50 arm: the charges whose commits *were*
    registered under a hash the loop then rewrote. Deciding which those are
    needs git, so it is the caller's — see ``protocol_tracker``'s
    ``_rewritten_charges``, which reads each charged commit's own message for a
    finding id the ledger resolved, the relation `fix_commit`'s gate already
    uses. Passing it as a separate argument rather than folding it into
    ``registered`` keeps this function pure and keeps the two matches
    distinguishable: one is a hash the ledger stamped, the other is a hash the
    ledger never saw.
    """
    discharged = set(rewritten)
    buckets = pending_commits(cache)
    return {
        actor: kept
        for actor, commits in buckets.items()
        if (kept := [
            c for c in commits
            if c not in discharged
            and not any(same_commit(c, r) for r in registered)
        ])
    }


def pending_commits_cleared(
    cache: dict[str, Any] | None, actor: str
) -> dict[str, list[str]]:
    """The buckets with ``actor``'s emptied, copying every other actor through.

    The one caller is the ledger-unreachable fallback inside the discharge,
    which is cross-actor by nature and so goes out as a whole-blob
    ``write_cache`` rather than a merge. What keeps that write from overwriting
    a sibling is ``expect_version``: the daemon compares the token inside its
    own lock and refuses a stale writer, which then re-reads and re-derives.
    """
    buckets = pending_commits(cache)
    buckets.pop(actor, None)
    return buckets


def is_fix_loop_state(cache: dict[str, Any] | None) -> bool:
    """Check if the current protocol state is fix_loop."""
    if cache is None:
        return False
    return cache.get("state") == "fix_loop"


def compute_obligations(
    cache: dict[str, Any] | None,
    config_dir: str = "",
    actor: str = ORCHESTRATOR,
) -> list[dict[str, Any]]:
    """Compute current protocol obligations from cache state.

    When ``config_dir`` is given, the ``Run ...`` / ``sahjhan ...`` command
    hints in obligation messages include ``--config-dir <config_dir>`` so
    Claude can execute them directly in the plugin-installed layout.
    Without it (legacy callers / tests), hints stay bare.

    ``actor`` selects whose stall count is read. The commit obligation and the
    pattern nudge are facts about the run and read the same for everyone; the
    stall is a charge against one actor's own commands.
    """
    if cache is None or not cache.get("active"):
        return []

    state = cache.get("state", "")
    if state not in ("fix_loop", "pattern_analysis"):
        return []

    obligations: list[dict[str, Any]] = []
    commits = pending_commits_for(cache, actor)
    stall = stall_count(cache, actor)
    overdue = cache.get("pattern_analysis_overdue", False)
    perspective = cache.get("perspective", "?")
    p_done = cache.get("perspectives_done", 0)
    p_total = cache.get("perspectives_total", 13)

    cfg = f" --config-dir {config_dir}" if config_dir else ""

    if commits:
        obligations.append({
            "msg": f"{len(commits)} unregistered commits. sahjhan{cfg} fix_commit required. "
                   f"{perspective} ({p_done}/{p_total})",
            "blocks_commit": True,
            "blocks_all": False,
        })

    if stall > 15:
        obligations.append({
            "msg": f"{stall} commands without a protocol event. Run any sahjhan{cfg} "
                   f"command (e.g. status) to re-sync — it may be part of a larger shell line.",
            "blocks_commit": True,
            "blocks_all": True,
        })

    if overdue and not commits and state == "fix_loop":
        obligations.append({
            "msg": f"pattern_check due (3+ fixes). sahjhan{cfg} transition pattern_check",
            "blocks_commit": False,
            "blocks_all": False,
        })

    return obligations


def format_injection(obligations: list[dict[str, Any]], cache: dict[str, Any] | None) -> str:
    """Format obligations into terse injection text. Max ~30 tokens."""
    if not obligations:
        return ""
    ob = obligations[0]
    blocks = "BLOCKED" if ob.get("blocks_commit") or ob.get("blocks_all") else "PROTOCOL"
    return f"{blocks}: {ob['msg']}"


def format_block(obligations: list[dict[str, Any]], key: str) -> str:
    """The block message of the first obligation that sets ``key``.

    A block prints the remedy for what blocked, and ``obligations[0]`` is not
    always that: with a pending commit and a stall, the commit comes first and
    the stall is what refuses a non-commit command — so leading with the list
    printed ``fix_commit``, which does nothing for a stall.
    """
    blocking = next(o for o in obligations if o.get(key))
    return f"BLOCKED: {blocking['msg']}"


def format_state_line(cache: dict[str, Any] | None) -> str:
    """One-line state summary for primer injection. Max ~20 tokens."""
    if cache is None or not cache.get("active"):
        return ""
    state = cache.get("state", "?")
    perspective = cache.get("perspective", "?")
    p_done = cache.get("perspectives_done", 0)
    p_total = cache.get("perspectives_total", 13)
    # The run's total, not this actor's: the primer describes the run.
    commits = sum(len(v) for v in pending_commits(cache).values())
    parts = [f"Protocol: {state}", f"{perspective} {p_done}/{p_total}"]
    if commits:
        parts.append(f"{commits} pending commits")
    if cache.get("pattern_analysis_overdue", False):
        parts.append("pattern_check due")
    return " | ".join(parts)
