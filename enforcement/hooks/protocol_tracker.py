#!/usr/bin/env python3
"""Protocol tracker — updates enforcement cache after Bash commands.

PostToolUse hook for Bash. Detects git commits and sahjhan commands,
updates the enforcement cache file. Never blocks. Pure bookkeeping.
"""
from __future__ import annotations

import contextlib
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))

from _common import (  # noqa: E402
    DaemonError,
    bash_exit_code,
    bash_output,
    exit_ok,
    read_event,
    resolve_config_dir,
)
from _protocol_cache import (  # noqa: E402
    ORCHESTRATOR,
    VERSION_CONFLICT,
    Resolutions,
    contains_sahjhan_cmd,
    empty_cache,
    event_actor,
    is_enforcement_fresh,
    is_git_commit,
    is_read_only_cmd,
    is_sahjhan_cmd,
    merge_cache,
    parse_status_text,
    pending_commits,
    pending_commits_appended,
    pending_commits_cleared,
    pending_commits_discharged,
    pending_commits_patch,
    query_named_predicate,
    read_cache_with_boundary,
    registered_resolutions,
    sahjhan_segments,
    same_commit,
    stall_bumped,
    stall_cleared,
    stall_patch,
    write_cache,
)
from _resolve import ensure_sahjhan  # noqa: E402
from _shell_norm import shell_segments  # noqa: E402


def _is_tdd_cmd(cmd: str) -> bool:
    """Detect test, lint, and type-check commands (TDD workflow).

    Checks each segment of a chained command so that ``cd /project &&
    python -m pytest`` is recognized. Segmentation is ``_shell_norm``'s;
    reading only the first token of ``true & pytest`` loses the evidence
    that the suite ran rather than opening a hole.
    """
    _TDD_PREFIXES = ("pytest", "python -m pytest", "ruff check", "ruff format", "mypy")
    return any(seg.startswith(_TDD_PREFIXES) for seg in shell_segments(cmd))


def _is_sleep_cmd(cmd: str) -> bool:
    """Detect sleep commands used to game timing gates.

    Returns True for sleep >5 seconds. Short sleeps (<=5s) are allowed
    for legitimate polling. Checks each segment of a chained command,
    using ``_shell_norm``'s segmentation — ``true & sleep 600`` is the
    spelling that defeated this guard while ``true && sleep 600`` did
    not. Handles bash sleep suffixes (s/m/h/d).
    """
    _SUFFIX_MULTIPLIER = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    for segment in shell_segments(cmd):
        m = re.match(r"^\s*sleep\s+(\d+(?:\.\d+)?)([smhd])?", segment)
        if m:
            value = float(m.group(1))
            suffix = m.group(2)
            seconds = value * _SUFFIX_MULTIPLIER.get(suffix or "s", 1)
            if seconds > 5:
                return True
    return False


def _parse_commit_hash(output: str) -> str:
    """Extract short commit hash from git commit output."""
    m = re.search(r"\[.*?\s([0-9a-f]{7,})\]", output)
    return m.group(1) if m else "unknown"


def _runs_transition(cmd: str, command: str) -> bool:
    """True iff cmd invokes ``sahjhan ... transition <command>`` (verb-adjacent).

    Distinguishes the *mutating* transition from read-only diagnostics that
    merely mention the command name as a bare token — ``sahjhan gate check
    fix_commit``, ``sahjhan query "... 'fix_commit' ..."``, ``sahjhan status``.
    Only the actual transition should move cache bookkeeping. #77.

    Read only where a sahjhan command's arguments are: adjacency over the
    whole line said yes to ``sahjhan status && echo remember to run transition
    fix_commit``, because a split on whitespace cannot tell an argument from a
    word that was printed. Quoted spans go the same way — they are how the
    diagnostics above carry the name — so the scan sees the segment's bare
    words, which is where the verb has to be for the CLI to act on it.
    """
    for segment in sahjhan_segments(cmd):
        bare = re.sub(r"""'[^']*'|"[^"]*\"""", " ", segment)
        tokens = bare.split()
        if any(
            tok == "transition" and tokens[i + 1] == command
            for i, tok in enumerate(tokens[:-1])
        ):
            return True
    return False


# #77: the authoritative backlog for "pattern analysis overdue" is the ledger,
# NOT a hand-mirrored counter that a hook increments by matching command text.
#
# #82: and not a copy of the ledger query either. This used to hold its own SQL
# string — the same fact the `pattern_check` gate expressed in TOML — so the
# tree carried two expressions of one predicate with nothing comparing them,
# which is precisely the shape that deadlocked in the first place. The name
# below is resolved out of the protocol config at runtime, so the commit gate's
# block, the `pattern_check` gate's readiness and the `iteration_boundary`
# gate's block are all the same object. `enforcement_lint.py` H7 fails the
# build if SQL reappears here; H8 fails it if this name stops matching the
# query the escape is gated on.
PATTERN_OVERDUE_QUERY = "pattern_analysis_overdue"


def _query_pattern_analysis_overdue(
    binary: str, config_dir: str, cwd: str
) -> bool | None:
    """Is pattern analysis overdue, per the gate's own predicate?

    Returns None on any failure so the caller keeps the last known value
    rather than resetting it. Failing to *raise* the flag only delays the
    pattern nudge; it never deadlocks a commit. #77, #82.
    """
    return query_named_predicate(binary, config_dir, cwd, PATTERN_OVERDUE_QUERY)


def _refresh_fields(cwd: str, cache: dict) -> dict:
    """The cache fields ``sahjhan status`` decides, as a patch.

    --no-gates (sahjhan v0.14.0): plain status evaluates transition gates,
    which can run the project's test suite — guaranteed to blow the 5s
    timeout below and silently keep stale bookkeeping (#57). The refresh
    only needs state/sets, never gate readiness.

    pattern_analysis_overdue is re-derived from the gate's own named query here
    (only while it matters — fix_loop/pattern_analysis), never mirrored by
    token-matching the command text. #77, #82.

    Returned as a patch rather than applied in place because the write it feeds
    is now conditional (item 42): a ``version_conflict`` re-reads and re-derives
    the snapshot-dependent fields, and re-running this for the retry would cost
    two more 5 s subprocesses to be told the same thing. Every value here is
    the engine's answer, so it is as true of the re-read cache as of the first.
    An empty patch means the engine could not be asked, and the previous values
    stand — which is the pre-existing behaviour on every failure path below.
    """
    binary = ensure_sahjhan()
    if binary is None:
        return {}
    config_dir, _ = resolve_config_dir(cwd)
    try:
        cmd = [binary, "--config-dir", config_dir, "status", "--no-gates"]
        result = subprocess.run(
            cmd,
            capture_output=True, text=True, timeout=5, cwd=cwd,
        )
    except (OSError, subprocess.TimeoutExpired):
        return {}

    if result.returncode != 0:
        return {}

    status = parse_status_text(result.stdout)
    perspective = status.get("sets", {}).get("perspective", {})
    state = status.get("current_state", "")
    fields = {
        "state": state,
        "perspective": status.get("current_perspective", "?"),
        "perspectives_done": perspective.get("complete", 0),
        "perspectives_total": (
            perspective.get("total", 0) or cache.get("perspectives_total", 13)
        ),
        "active": state not in ("", "idle", "finalized"),
    }

    # Derive the pattern-analysis backlog from the ledger, but only in the
    # states where it's consumed — avoids a subprocess on every recon/audit
    # sahjhan command. Query failure keeps the previous value.
    if state in ("fix_loop", "pattern_analysis"):
        overdue = _query_pattern_analysis_overdue(binary, config_dir, cwd)
        if overdue is not None:
            fields[PATTERN_OVERDUE_QUERY] = overdue
    return fields


def _refresh_from_sahjhan(cwd: str, cache: dict) -> dict:
    """``cache`` with the status-derived fields applied."""
    cache.update(_refresh_fields(cwd, cache))
    return cache


def _stop_daemon(cwd: str) -> None:
    """Best-effort daemon stop after audit finalization."""
    binary = ensure_sahjhan()
    if binary is None:
        return
    config_dir, _ = resolve_config_dir(cwd)
    with contextlib.suppress(OSError, subprocess.TimeoutExpired):
        subprocess.run(
            [binary, "--config-dir", config_dir, "daemon", "stop"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=cwd,
        )


def _registered_resolutions(cwd: str) -> Resolutions | None:
    """What the ledger says `fix_commit` has registered, or None.

    Split from the discharge below because the two answer to different things:
    this is the ledger's answer and does not move when the enforcement blob
    does, whereas the buckets it is subtracted from are re-read on a
    ``version_conflict`` retry. Asking the ledger once and re-deriving the
    buckets per attempt keeps a retry from paying for a second query.
    """
    binary = ensure_sahjhan()
    if binary is None:
        return None
    config_dir, _ = resolve_config_dir(cwd)
    return registered_resolutions(binary, config_dir, cwd)


#: How `fix_commit`'s own gate identifies the commit it is registering:
#: ``git log -1 --format=%B | grep -q '{{item_id}}'``. `%B` and not `%s`
#: because `phase-fix-loop.md` passes the item id as a *second* ``-m``, so it
#: is in the body; the trailing ``--`` because a charged hash is a bare
#: revision and a file of the same name would otherwise make git ambiguous.
_MESSAGE_ARGV = ("git", "log", "-1", "--format=%B")

#: A charge is whatever `_parse_commit_hash` read out of `git commit`'s output,
#: including the literal ``unknown`` it falls back to. Only something shaped
#: like an abbreviation is worth handing to git.
_HASH = re.compile(r"[0-9a-f]{7,40}\Z")


def _commit_message(cwd: str, commit_hash: str) -> str:
    """``commit_hash``'s full message, or ``""`` when git cannot say.

    Every failure is the empty string, and the caller treats that as "no
    match": no repository, a pruned object, a hash that was never one. That is
    the safe direction here — an unanswerable question keeps the charge, and
    keeping a charge costs a nudge while losing one loses the gate.

    A rebase leaves the pre-rewrite commit unreachable, not absent, so this
    resolves it; and a linked worktree shares the object store with the main
    checkout, so the orchestrator's ``cwd`` can read a subagent's commit.
    """
    if not _HASH.match(commit_hash):
        return ""
    try:
        result = subprocess.run(
            [*_MESSAGE_ARGV, commit_hash, "--"],
            capture_output=True, text=True, timeout=5, cwd=cwd,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return result.stdout if result.returncode == 0 else ""


def _rewritten_charges(
    cwd: str, cache: dict, resolutions: Resolutions
) -> list[str]:
    """Charges whose commit names a finding the ledger resolved (item 50).

    The tracker charges the hash `git commit` printed; the ledger stamps the
    hash at `HEAD` when the transition ran. `phase-fix-loop.md` puts a
    `git rebase` between those two moments — and in a three-wide loop the first
    subagent's merge moves the branch, so subagents 2 and 3 rebase every round —
    which makes them different strings for one commit. What the rewrite does not
    change is the message, and `fix_commit` will not register a commit whose
    message does not name the item, so the id is a key both ends already hold.

    Only the charges the hash match missed are looked up: the rest are already
    discharged and a git call for them would buy nothing. Re-run per
    ``version_conflict`` attempt rather than memoised, because the retry re-reads
    the buckets and may find charges this attempt never saw.
    """
    if not resolutions.findings:
        return []
    rewritten = []
    for commits in pending_commits(cache).values():
        for commit_hash in commits:
            if any(same_commit(commit_hash, r) for r in resolutions.commits):
                continue
            message = _commit_message(cwd, commit_hash)
            if message and any(f in message for f in resolutions.findings):
                rewritten.append(commit_hash)
    return rewritten


def _discharge_registered_commits(
    cwd: str, cache: dict, resolutions: Resolutions | None
) -> dict[str, list[str]]:
    """The pending-commit buckets, minus whatever the ledger says is registered.

    `fix_commit` stamps the commit it registered onto the `finding_resolved`
    it emits, so the ledger can name the bucket to discharge even though the
    transition's caller cannot — see `_protocol_cache`'s section on the
    pending-commit block.

    An unreachable ledger (``resolutions is None``) discharges the orchestrator's
    bucket only. It ran the transition, so it is the one actor whose charge the
    command is evidence about without anything having to be looked up.

    Cross-actor by nature: which bucket holds a registered commit is not known
    until it is looked for. That is why this one keeps a whole-blob write and
    takes its safety from ``expect_version`` instead of a per-actor merge —
    there is no single actor the patch could name.
    """
    if resolutions is None:
        return pending_commits_cleared(cache, ORCHESTRATOR)
    return pending_commits_discharged(
        cache, resolutions.commits, _rewritten_charges(cwd, cache, resolutions),
    )


# How many times a conditional whole-blob write re-reads and re-derives before
# giving up. Bounded because this is a PostToolUse hook on every Bash call: a
# loop that retried until it won would hold the tool call open behind a
# contended daemon. Losing the bookkeeping write costs a stall nudge; blocking
# the session costs the session.
_WRITE_ATTEMPTS = 3


def _apply_sahjhan_cmd(
    cwd: str,
    cache: dict | None,
    version: str | None,
    cmd: str,
    actor: str,
    exit_code: int,
) -> dict:
    """Record the effects of a sahjhan enforcement command on the cache.

    Runs for pure sahjhan lines and for wrapped re-sync lines like
    ``cd repo && sahjhan status | head``: refresh state from the daemon,
    clear the caller's stall counter, stamp last_sahjhan_cmd, tear the daemon
    down on finalization, and apply fix_commit / pattern-check bookkeeping.
    #70 item 1.

    Item 42: this is the whole-blob write, and its snapshot is taken *before*
    two 5 s subprocesses — the widest window in the tracker for a sibling to
    land in. It stays a whole-blob write because the discharge below is
    cross-actor and no per-actor patch could express it; what makes it safe is
    ``version``, the token from the read that produced ``cache``. The daemon
    compares it inside the lock that stores, so a caller that lost the race is
    refused rather than silently overwriting the winner, and re-derives against
    what it reads back. ``version`` of ``None`` — no daemon token, or a cache
    this call had to invent — writes unconditionally, exactly as before.
    """
    if cache is None:
        cache = empty_cache()
        version = None
    # The engine's answers, asked for once: a retry re-derives what depends on
    # the snapshot, and nothing here does.
    refreshed = _refresh_fields(cwd, cache)
    # Stop daemon after finalization (teardown safety net). Decided once, off
    # the state this refresh found — the loop below may re-read the blob, and
    # tearing the daemon down a second time is not a thing to decide twice.
    # `refreshed` is empty exactly when the engine could not be asked, which is
    # when the previous value stands.
    if refreshed.get("state", cache.get("state")) == "finalized":
        _stop_daemon(cwd)
    stamp = datetime.now(timezone.utc).isoformat()  # noqa: UP017
    # The ledger's answer, also asked for once — see _registered_resolutions.
    discharging = exit_code == 0 and _runs_transition(cmd, "fix_commit")
    registered = _registered_resolutions(cwd) if discharging else None

    for _attempt in range(_WRITE_ATTEMPTS):
        cache.update(refreshed)
        # Running any sahjhan enforcement subcommand IS the protocol event the
        # stall counter waits for — clear it deterministically, even when the
        # status refresh above could not reach the daemon. Only for this actor:
        # the command is evidence that *it* re-synced, and a sibling's re-sync
        # used to launder away a stall accrued by real unregistered work.
        cache["stall"] = stall_cleared(cache, actor)
        cache["last_sahjhan_cmd"] = stamp
        _apply_transition_bookkeeping(
            cwd, cache, cmd, exit_code, discharging, registered,
        )
        try:
            write_cache(cwd, cache, expect_version=version)
            return cache
        except DaemonError as exc:
            if exc.error != VERSION_CONFLICT:
                return cache
        except RuntimeError:
            return cache
        # Lost the race. Re-read, and re-derive against what the winner left
        # rather than re-sending the snapshot the daemon just refused.
        fresh, _boundary, version = read_cache_with_boundary(cwd)
        if fresh is None:
            return cache
        cache = fresh
    return cache


def _apply_transition_bookkeeping(
    cwd: str,
    cache: dict,
    cmd: str,
    exit_code: int,
    discharging: bool,
    registered: Resolutions | None,
) -> None:
    """The two cache effects a landed transition has, applied to ``cache``.

    Separate from the caller only so a ``version_conflict`` retry can re-apply
    them to a freshly read cache — the discharge subtracts from buckets, so it
    has to be recomputed against the ones the winner left, not the ones this
    call read ten seconds ago. ``cwd`` is threaded in for the same reason: the
    item-50 arm reads the charged commits, and which those are is what the
    retry re-derives.
    """
    # #77: pattern_analysis_overdue is DERIVED from the ledger in _refresh_fields
    # (the same query the pattern_check gate uses), not mirrored by token-matching
    # the command text — a read-only diagnostic that only mentions `fix_commit`/
    # `pattern_check` no longer moves it. The pending-commit registration is still
    # cache-tracked, but it clears solely on the mutating `transition fix_commit`
    # verb, so a diagnostic can't silently clear a real pending commit either.
    #
    # Two conditions, because the verb alone was never enough, and it was
    # wrong about two different things. It was read off the whole line, so an
    # echoed reminder riding on a real sahjhan command was indistinguishable
    # from the command — `_runs_transition` now reads only where a sahjhan
    # command's arguments are. And it was read without the exit code, so a
    # transition the engine *refused* discharged a charge that nothing had
    # registered — the same `exit_code == 0` guard the git-commit branch below
    # already applied, two lines from a path that ignored it. What is then
    # discharged comes from the ledger rather than from the command text.
    if discharging:
        cache["unregistered_commits"] = _discharge_registered_commits(
            cwd, cache, registered,
        )
    # P3.4: the round is over, so the obligation is discharged — say so here
    # rather than hoping the derivation above could reach the ledger. It
    # returns None on timeout or a missing binary, and None keeps the previous
    # value, so a failed query used to hold the flag True through the very
    # transition that satisfies it. This write is clear-only and runs after the
    # refresh: it can release the obligation but never raise one, so it cannot
    # drift into the blocking disagreement #77 deadlocked on. The ledger stays
    # the sole authority for owing a round; the next refresh re-raises the flag
    # if three more findings close.
    #
    # Gated on the engine's answer for the same reason the discharge above is:
    # the round is closed by the transition landing, not by it being attempted,
    # and a refused `pattern_done` that released the obligation would let a run
    # skip the round it was blocked for.
    if exit_code == 0 and _runs_transition(cmd, "pattern_done"):
        cache[PATTERN_OVERDUE_QUERY] = False


def main() -> None:
    event = read_event()

    if event.get("tool_name") != "Bash":
        exit_ok()

    cwd = event.get("cwd", os.getcwd())
    cmd = event.get("tool_input", {}).get("command", "")
    # CC 2.x Bash payloads carry stdout under .stdout and omit exit_code
    # (PostToolUse fires only on success); the helpers read both shapes so
    # git-commit registration below doesn't silently die on 2.x (#75).
    exit_code = bash_exit_code(event)
    output = bash_output(event)
    actor = event_actor(event)

    # The version comes back with the cache because the whole-blob write below
    # is conditional on it — a token fetched separately would name a different
    # read than the snapshot it is meant to guard.
    cache, _boundary, version = read_cache_with_boundary(cwd)

    if is_sahjhan_cmd(cmd):
        _apply_sahjhan_cmd(cwd, cache, version, cmd, actor, exit_code)
        exit_ok()

    if cache is None:
        exit_ok()

    # Stale enforcement: don't track stall for abandoned audits
    if not is_enforcement_fresh(cache):
        exit_ok()

    if is_git_commit(cmd) and exit_code == 0:
        commit_hash = _parse_commit_hash(output)
        # One merge naming only this actor's two entries. Both facts are about
        # the actor that ran the commit and about nobody else, so neither half
        # of the patch mentions a sibling — and the daemon leaves the siblings
        # as it holds them rather than as this snapshot saw them. The commit
        # bucket goes out whole because RFC 7386 replaces arrays; a second
        # commit from *this* actor off the same snapshot would still lose one.
        with contextlib.suppress(RuntimeError):
            merge_cache(cwd, {
                **pending_commits_patch(
                    cache, pending_commits_appended(cache, actor, commit_hash), actor,
                ),
                **stall_patch(cache, stall_cleared(cache, actor), actor),
            })
        exit_ok()

    # A sahjhan enforcement subcommand ran inside a larger shell line
    # (e.g. ``cd repo && sahjhan status | head``). It still re-syncs the
    # protocol, so treat it like a bare sahjhan command rather than penalize
    # the stall counter. Checked after the git-commit branch so a
    # ``git commit && sahjhan status`` line still registers its commit. #70 item 1.
    if contains_sahjhan_cmd(cmd):
        _apply_sahjhan_cmd(cwd, cache, version, cmd, actor, exit_code)
        exit_ok()

    # Test/lint/type-check commands are legitimate TDD activity — don't count
    # as stalling. Neither does reading the tree: an audit subagent's whole
    # job is grep/sed -n/ls, none of which has a protocol event to emit, so
    # counting it accrues a block the reader can only escape by running a
    # protocol command for its side effect and discarding the output.
    #
    # A merge naming this actor's entry, not an update replacing the map: the
    # count is computed from a snapshot, and under the old write a sibling that
    # bumped or re-synced between the read and here was silently reset to what
    # the snapshot remembered.
    with contextlib.suppress(RuntimeError):
        if _is_sleep_cmd(cmd):
            # Sleep to game timing gates gets double stall penalty
            merge_cache(cwd, stall_patch(cache, stall_bumped(cache, actor, 2), actor))
        elif not _is_tdd_cmd(cmd) and not is_read_only_cmd(cmd):
            merge_cache(cwd, stall_patch(cache, stall_bumped(cache, actor, 1), actor))
    exit_ok()


if __name__ == "__main__":
    main()
