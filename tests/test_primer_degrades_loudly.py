"""W13 / items 37 + 17 — the primer says so when it could not find out.

Two defects with one root: the primer's three failure paths all called
`exit_ok()`, which emits **no `additionalContext` at all** — byte-identical to
what the primer emits when there is genuinely nothing to say (no audit here, a
terminal run). So "I have nothing for you" and "I could not find out" were
indistinguishable, in the hook whose entire job is re-injecting state after a
`/clear`, and on which the `awaiting_clear → resume` design depends.

The aggravating half is the **ordering** (item 37). The daemon-death check and
the enforcement-health probe sat *after* the `sahjhan status` subprocess, so a
status that hung or exited non-zero skipped both — the hook whose job is
reporting daemon death stayed silent in exactly the case where the daemon died
during a slow status. Neither check needs the binary or the ledger (one reads a
pid file, one opens a socket), so nothing forced them to queue behind it.

`99999999` as the dead pid follows `test_daemon_lifecycle`; the tree already
treats it as the "no such process" convention.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENFORCEMENT_HOOKS_DIR = os.path.join(REPO_ROOT, "enforcement", "hooks")
sys.path.insert(0, ENFORCEMENT_HOOKS_DIR)

from git_env import scrubbed_env  # noqa: E402
from hook_runner import run_hook  # noqa: E402

DEAD_PID = "99999999"

#: The marker every degraded notice carries. Spelled out here rather than
#: imported from `primer`, because a module-level import of a constant the fix
#: adds turns the RED run into a collection error — every test in the file
#: fails on `ImportError` and none of them says anything about the defect.
#: `test_the_marker_is_the_one_production_emits` does the import instead, so
#: the tie to production is asserted in one place that can fail on its own.
DEGRADED = "SAHJHAN PRIMER DEGRADED"


def _mock_binary(tmp_path: Path, body: str, *, executable: bool = True) -> Path:
    """A stand-in sahjhan at the path `sahjhan_binary()` resolves to.

    Same construction as `test_sahjhan_integration._create_mock_binary`, with
    the executable bit as a parameter — an unrunnable binary is how the
    `OSError` arm of the status handler is reached without waiting out a
    timeout.
    """
    import platform

    arch = platform.machine()
    if arch == "arm64":
        arch = "aarch64"
    system = platform.system().lower()
    triple = {
        "darwin": f"{arch}-apple-darwin",
        "linux": f"{arch}-unknown-linux-gnu",
    }.get(system, f"{arch}-{system}")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    binary = bin_dir / f"sahjhan-{triple}"
    binary.write_text(f"#!/bin/sh\n{body}\n")
    binary.chmod(0o755 if executable else 0o644)
    return binary


def _status_binary(tmp_path: Path, body: str, **kwargs) -> Path:
    """A mock sahjhan whose `status` runs ``body`` and everything else exits 0.

    Hanging bodies use ``exec sleep``, not ``sleep``: `subprocess.run` kills the
    shell it started, and a plain `sleep` is a *child* of that shell, so it
    survives the timeout and keeps running. Two of those per file run is enough
    load to flake the healthy-run guard in this very file — a fixture
    manufacturing the conditions its own control is measured under.
    """
    return _mock_binary(tmp_path, (
        'case "$*" in\n'
        '  *status*)\n'
        f'{body}\n'
        '    ;;\n'
        'esac\n'
        'exit 0'
    ), **kwargs)


def _audit_dir(tmp_path: Path) -> Path:
    d = tmp_path / "docs" / "holtz" / ".sahjhan"
    d.mkdir(parents=True, exist_ok=True)
    (tmp_path / "enforcement").mkdir(parents=True, exist_ok=True)
    return d


def _seed_cache(tmp_path: Path, state: str = "fix_loop") -> None:
    """A fresh enforcement cache, so the freshness gate does not short-circuit."""
    from _protocol_cache import empty_cache, write_cache

    cache = empty_cache()
    cache["state"] = state
    cache["last_sahjhan_cmd"] = datetime.now(timezone.utc).isoformat()  # noqa: UP017
    write_cache(str(tmp_path), cache)


def primer(tmp_path: Path) -> dict:
    """Run the real UserPromptSubmit hook, as Claude Code runs it."""
    env = scrubbed_env(CLAUDE_PLUGIN_ROOT=str(tmp_path))
    sock = os.environ.get("SAHJHAN_DAEMON_SOCKET")
    if sock:
        env["SAHJHAN_DAEMON_SOCKET"] = sock
    return run_hook(
        os.path.join(ENFORCEMENT_HOOKS_DIR, "primer.py"),
        {"user_message": "continue", "cwd": str(tmp_path)},
        cwd=str(tmp_path),
        env=env,
        timeout=30,
    )


def context_of(output: dict) -> str:
    return output.get("hookSpecificOutput", {}).get("additionalContext", "")


# ── V1: three degrade paths, three notices ──────────────────────────────────


class TestEachDegradePathSaysSo:
    """V1 — one test per path, because they degrade for unrelated reasons.

    Each asserts the shared `DEGRADED` marker *and* something only that path
    could have said. The marker alone would let one path's notice satisfy all
    three tests, which is how a "fixed everywhere" claim ships covering one.
    """

    def test_the_marker_is_the_one_production_emits(self):
        """The literal above is the hook's own constant, not a stale copy."""
        import primer

        assert primer.DEGRADED == DEGRADED

    def test_a_suppressed_binary_says_so(self, tmp_path, mock_daemon):
        """Path 3: `_recently_failed` withholds the binary for an hour.

        The one degrade path that never had a chance to read anything, and the
        one most likely to persist across many prompts — a whole hour of a
        resume hook silently emitting nothing.
        """
        _audit_dir(tmp_path)
        _seed_cache(tmp_path)
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir(exist_ok=True)
        (bin_dir / ".sahjhan-bootstrap-failed").write_text(
            f"{datetime.now(timezone.utc).timestamp()}\n"  # noqa: UP017
        )

        context = context_of(primer(tmp_path))

        assert DEGRADED in context
        assert "binary is unavailable" in context

    def test_a_status_that_cannot_be_run_says_so(self, tmp_path, mock_daemon):
        """Path 1, the `OSError` arm — and it is named, not collapsed.

        The handler catches `OSError` and `TimeoutExpired` together, and they
        call for opposite responses: a timeout says the machine was loaded, an
        `OSError` says the binary or its path is wrong. Three sessions could
        not falsify anything about the load-flaky primer tests because the one
        message covered both, so the notice names which fired.
        """
        _audit_dir(tmp_path)
        _seed_cache(tmp_path)
        _status_binary(tmp_path, '    echo "state: fix_loop"\n    exit 0',
                       executable=False)

        context = context_of(primer(tmp_path))

        assert DEGRADED in context
        assert "did not complete (PermissionError)" in context, (
            f"the notice must name which exception fired; got: {context}"
        )

    def test_a_status_that_times_out_says_so(self, tmp_path, mock_daemon):
        """Path 1, the `TimeoutExpired` arm. Costs the primer's own 5 s.

        Unavoidable: the timeout is production's and this unit does not change
        it — the handoff's standing rule is that instrumentation and a timeout
        change must not ride in one commit, or the next green run is again
        unattributable.
        """
        _audit_dir(tmp_path)
        _seed_cache(tmp_path)
        _status_binary(tmp_path, "    exec sleep 20")

        context = context_of(primer(tmp_path))

        assert DEGRADED in context
        assert "did not complete (TimeoutExpired)" in context

    def test_a_status_that_exits_nonzero_says_so(self, tmp_path, mock_daemon):
        """Path 2: a corrupt ledger or unreadable config.

        Not covered by item 17's proposed fix, which named only the timeout —
        this is the path a broken ledger takes, and it was as silent as the
        other two.
        """
        _audit_dir(tmp_path)
        _seed_cache(tmp_path)
        _status_binary(tmp_path, '    echo "boom" >&2\n    exit 3')

        context = context_of(primer(tmp_path))

        assert DEGRADED in context
        assert "exited 3" in context


# ── V2: the ordering, which is why 37 outranks 17 ───────────────────────────


class TestDeathDetectionDoesNotQueueBehindStatus:
    """V2 — the terminated marker is written even when status never returns.

    This is the whole of item 37. The marker is what every other hook reads to
    decide the audit is over (`stop_hook`, `_daemon_lifecycle`, the primer's
    own first branch), so a status call that hangs used to leave the entire
    session believing a dead audit was live.
    """

    def test_the_marker_is_written_when_status_hangs(self, tmp_path):
        """The mock status sleeps past the primer's timeout; the marker lands.

        Fast on the fixed ordering and slow on the broken one, which is the
        shape you want: the death check now runs first and returns before the
        subprocess is ever started, so nothing waits out the sleep.
        """
        audit = _audit_dir(tmp_path)
        (audit / "daemon-init-pid").write_text(f"{DEAD_PID}\n")
        _status_binary(tmp_path, "    exec sleep 20")

        output = primer(tmp_path)

        assert (audit / "terminated").is_file(), (
            "death detection must not queue behind a call that can hang"
        )
        assert "AUDIT TERMINATED" in context_of(output)

    def test_the_marker_is_written_when_status_exits_nonzero(self, tmp_path):
        """The same claim for the other skipped path — a status that fails."""
        audit = _audit_dir(tmp_path)
        (audit / "daemon-init-pid").write_text(f"{DEAD_PID}\n")
        _status_binary(tmp_path, '    echo "boom" >&2\n    exit 3')

        output = primer(tmp_path)

        assert (audit / "terminated").is_file()
        assert "AUDIT TERMINATED" in context_of(output)

    def test_the_marker_is_written_when_the_binary_is_suppressed(self, tmp_path):
        """And when there is no binary at all to ask.

        The death check reads a pid file. Nothing about it ever needed the
        binary, so a bootstrap failure taking the death report with it was pure
        ordering.
        """
        audit = _audit_dir(tmp_path)
        (audit / "daemon-init-pid").write_text(f"{DEAD_PID}\n")
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir(exist_ok=True)
        (bin_dir / ".sahjhan-bootstrap-failed").write_text(
            f"{datetime.now(timezone.utc).timestamp()}\n"  # noqa: UP017
        )

        output = primer(tmp_path)

        assert (audit / "terminated").is_file()
        assert "AUDIT TERMINATED" in context_of(output)


# ── unchanged behaviour: green before, during and after ─────────────────────


class TestSilenceStillMeansNothingToSay:
    """The other half of the fix, and the direction it could fail in.

    "Degrade loudly" is most easily over-implemented as "say something always",
    which would put a notice on every prompt of every project — and destroy the
    distinction the unit exists to create. These pin the cases that must stay
    silent, and they are green before this change, under its non-vacuity
    mutation, and after.
    """

    def test_no_audit_directory_stays_silent(self, tmp_path):
        assert context_of(primer(tmp_path)) == ""

    def test_a_terminal_run_stays_silent(self, tmp_path, mock_daemon):
        _audit_dir(tmp_path)
        _seed_cache(tmp_path, state="finalized")
        _status_binary(
            tmp_path, '    echo "state: finalized (100 events, chain valid)"\n    exit 0'
        )

        assert context_of(primer(tmp_path)) == ""

    def test_a_healthy_run_still_injects_its_state(self, tmp_path, mock_daemon):
        """The success path is untouched — and must not carry the marker."""
        _audit_dir(tmp_path)
        _seed_cache(tmp_path)
        _status_binary(
            tmp_path, '    echo "state: fix_loop (50 events, chain valid)"\n    exit 0'
        )

        context = context_of(primer(tmp_path))

        assert "fix_loop" in context
        assert DEGRADED not in context
