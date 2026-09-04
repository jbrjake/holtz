"""W11 / item 42 — a write names the actor it is about, and nobody else.

The tracker read the per-actor maps (`stall`, `unregistered_commits`), changed
one actor's entry, and wrote the **whole map** back. The daemon's
`enforcement_update` replaces a top-level key outright, so every sibling's
entry was overwritten with whatever this caller's snapshot remembered — and the
snapshot at the widest site is taken *before two 5 s subprocesses*. The
functions computing those maps say "every other actor untouched", which was
true of the value they returned and false of the write that carried it.

**Why the interleave is driven from the daemon rather than by racing hooks.**
A hook's read and its write are two separate connections with the hook's own
work in between, and nothing outside the hook can reliably land a sibling's
write in that window — a test that spawned two hook subprocesses and hoped
would pass or fail on machine load, which is the one thing this suite has
learned not to build. So `MockEnforcementDaemon.after_read` applies the
sibling's change *at the moment the read is answered*: same window, decided by
the test instead of by the scheduler. The hook under test is the real one, run
as a subprocess, exactly as Claude Code runs it.

**Why the mock and not a real daemon.** A real daemon refuses every enforcement
mutation from a test process (`auth_failed` — the caller is pytest, not a
hash-pinned hook), so there is no way to seed a starting state or read the
result back. The mock's merge and version rules are a port of sahjhan's own
`src/daemon/enforcement.rs`, pinned case by case against the engine's unit
tests in `TestTheMockMergesLikeTheEngine`.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENFORCEMENT_HOOKS_DIR = os.path.join(REPO_ROOT, "enforcement", "hooks")
sys.path.insert(0, ENFORCEMENT_HOOKS_DIR)

from git_env import scrubbed_env  # noqa: E402
from hook_runner import run_hook  # noqa: E402

ORCHESTRATOR = ""

#: Three actors, four commits. The two counts a careless `len()` would confuse
#: are deliberately unequal (V3): an assertion that reads the bucket dimension
#: when it meant the commit dimension gets 3 where it wanted 4, rather than
#: passing on a coincidence. `agent-a` is the actor holding two.
SEEDED_COMMITS: tuple[tuple[str, str], ...] = (
    ("agent-a", "aaa1111"),
    ("agent-b", "bbb2222"),
    (ORCHESTRATOR, "ccc3333"),
    ("agent-a", "ddd4444"),
)


def seeded_cache() -> dict:
    """A live fix-loop cache with three actors charged and stalled.

    Built as a literal rather than through `empty_cache()` so the shape under
    test is the one being asserted about, not one a helper decides. Written
    straight onto the daemon's state for the same reason the module docstring
    gives: a test process cannot ask a daemon to store anything.
    """
    buckets: dict[str, list[str]] = {}
    for actor, commit in SEEDED_COMMITS:
        buckets.setdefault(actor, []).append(commit)
    return {
        "active": True,
        "state": "fix_loop",
        "unregistered_commits": buckets,
        "pattern_analysis_overdue": False,
        "perspective": "security",
        "perspectives_done": 1,
        "perspectives_total": 13,
        "stall": {"agent-a": 3, "agent-b": 1, ORCHESTRATOR: 2},
        "last_refresh": "",
        "last_sahjhan_cmd": datetime.now(timezone.utc).isoformat(),  # noqa: UP017
    }


def tracker(tmp_path, command: str, actor: str, *, stdout: str = "") -> dict:
    """Run the real PostToolUse tracker for one Bash line, as Claude Code does."""
    return run_hook(
        os.path.join(ENFORCEMENT_HOOKS_DIR, "protocol_tracker.py"),
        {
            "tool_name": "Bash",
            "tool_input": {"command": command},
            "tool_response": {"exit_code": 0, "stdout": stdout, "output": stdout},
            "cwd": str(tmp_path),
            "agent_id": actor,
        },
        cwd=str(tmp_path),
        env=scrubbed_env(),
    )


def bump_of(actor: str, to: int):
    """A sibling landing a stall bump, for `after_read`."""
    def _apply(daemon) -> None:
        daemon.state["stall"][actor] = to
    return _apply


def commit_by(actor: str, commit: str):
    """A sibling landing a commit charge, for `after_read`."""
    def _apply(daemon) -> None:
        daemon.state["unregistered_commits"].setdefault(actor, []).append(commit)
    return _apply


# ── V1 + V2: each colliding writer, against a sibling in its own window ──────


class TestASiblingsWriteSurvivesThisActors:
    """V1/V2 — one interleave per writer, because they use different mechanisms.

    `stall_bumped` and `pending_commits_appended` go out as RFC 7386 merges
    naming one actor. `stall_cleared` on the sahjhan path rides the whole-blob
    write, which is guarded by `expect_version` instead. One test shape cannot
    cover all three, which is what V2 says.
    """

    def test_bump_leaves_a_siblings_bump_alone(self, tmp_path, mock_daemon):
        """V1. agent-a reads, agent-b bumps, agent-a writes: b's bump survives."""
        mock_daemon.state = seeded_cache()
        mock_daemon.after_read = bump_of("agent-b", 9)

        tracker(tmp_path, "touch some_file.py", "agent-a")

        assert mock_daemon.state["stall"] == {
            "agent-a": 4,          # 3 + 1, this actor's own charge
            "agent-b": 9,          # the sibling that landed inside the window
            ORCHESTRATOR: 2,       # never mentioned by either
        }

    def test_double_bump_leaves_a_siblings_bump_alone(self, tmp_path, mock_daemon):
        """The sleep path charges 2, and must lose no more than the single one."""
        mock_daemon.state = seeded_cache()
        mock_daemon.after_read = bump_of("agent-b", 9)

        tracker(tmp_path, "sleep 60", "agent-a")

        assert mock_daemon.state["stall"] == {
            "agent-a": 5, "agent-b": 9, ORCHESTRATOR: 2,
        }

    def test_commit_registration_leaves_a_siblings_commit_alone(
        self, tmp_path, mock_daemon
    ):
        """V2 — `pending_commits_appended`, whose values are lists.

        RFC 7386 replaces arrays wholesale, so this patch carries agent-a's
        *whole* bucket. What it must not carry is agent-b's.
        """
        mock_daemon.state = seeded_cache()
        mock_daemon.after_read = commit_by("agent-b", "eee5555")

        tracker(
            tmp_path,
            'git commit -m "fix(x): BH-101"',
            "agent-a",
            stdout="[dev fff6666] fix(x): BH-101\n 1 file changed",
        )

        buckets = mock_daemon.state["unregistered_commits"]
        assert buckets["agent-a"] == ["aaa1111", "ddd4444", "fff6666"]
        assert buckets["agent-b"] == ["bbb2222", "eee5555"], (
            "the sibling's commit landed inside agent-a's read-write window"
        )
        assert buckets[ORCHESTRATOR] == ["ccc3333"]

    def test_commit_registration_clears_only_this_actors_stall(
        self, tmp_path, mock_daemon
    ):
        """V2 — `stall_cleared`, which a merge spells as a `null` deletion.

        Deleted, not zeroed: the readers treat 0 and absent alike, so a test
        that accepted either would not notice the patch storing a null the
        daemon would serve back.
        """
        mock_daemon.state = seeded_cache()
        mock_daemon.after_read = bump_of("agent-b", 9)

        tracker(
            tmp_path,
            'git commit -m "fix(x): BH-101"',
            "agent-a",
            stdout="[dev fff6666] fix(x): BH-101\n 1 file changed",
        )

        assert mock_daemon.state["stall"] == {"agent-b": 9, ORCHESTRATOR: 2}
        assert "agent-a" not in mock_daemon.state["stall"]

    def test_a_sahjhan_resync_leaves_a_siblings_bump_alone(
        self, tmp_path, mock_daemon
    ):
        """V2 — `stall_cleared` on the whole-blob path, guarded by expect_version.

        This is the site whose snapshot is taken before two 5 s subprocesses.
        It stays a whole-blob write because the discharge it also performs is
        cross-actor; what keeps the sibling is the version compare inside the
        daemon's lock, not a narrower patch.
        """
        mock_daemon.state = seeded_cache()
        mock_daemon.after_read = bump_of("agent-b", 9)

        tracker(tmp_path, "sahjhan status", "agent-a")

        assert mock_daemon.state["stall"] == {"agent-b": 9, ORCHESTRATOR: 2}


# ── V6: the edge the merge does not cover ───────────────────────────────────


class TestAnActorRacingItself:
    """V6 — the merge buys safety from siblings, not from a second self.

    A merge patch is per-key, not read-modify-write: two of one actor's own
    writes computed from a single snapshot both say "set my entry to 4", and
    the second is not a conflict, it is agreement. So the unit must not ship
    believing the merge closed this. `expect_version` is what closes it, on
    the one path that carries it.
    """

    def test_the_conditional_write_is_refused_and_the_retry_lands(
        self, tmp_path, mock_daemon
    ):
        """The refusal is asserted, not just the outcome.

        A conditional write that is refused and then retried leaves exactly the
        state an unconditional write would have, so the stored value cannot
        distinguish "retried" from "clobbered and got lucky". The daemon's own
        log of what it refused is what can.
        """
        mock_daemon.state = seeded_cache()
        mock_daemon.after_read = bump_of("agent-a", 8)

        tracker(tmp_path, "sahjhan status", "agent-a")

        assert ("enforcement_write", "version_conflict") in mock_daemon.log, (
            f"expected the stale write to be refused; daemon saw {mock_daemon.log}"
        )
        writes = [outcome for op, outcome in mock_daemon.log
                  if op == "enforcement_write"]
        assert writes[-1] == "ok", (
            f"expected the retry to land after the refusal; writes were {writes}"
        )
        # And the retry re-derived rather than re-sending: this actor's own
        # re-sync still clears its counter, off the value it read back.
        assert "agent-a" not in mock_daemon.state["stall"]

    def test_a_merge_is_not_made_conditional(self, tmp_path, mock_daemon):
        """The per-actor merges are unconditional, and that is the design.

        A version compare on a patch that names one actor would refuse a write
        that could not have collided — every sibling's write moves the token.
        The self-race it would catch is charged the *same* value either way (a
        stall bump is idempotent in its effect on the gate), which is why V6
        records the exposure rather than closing it here.
        """
        mock_daemon.state = seeded_cache()
        mock_daemon.after_read = bump_of("agent-b", 9)

        tracker(tmp_path, "touch some_file.py", "agent-a")

        assert ("enforcement_merge", "ok") in mock_daemon.log
        assert "version_conflict" not in [o for _op, o in mock_daemon.log]


# ── unchanged behaviour: green before, during and after ─────────────────────


class TestThePreKeyingShapeIsStillMigrated:
    """A cache written before the maps were keyed must not be dropped.

    `stall_counts` and `pending_commits` migrate a bare int and a flat list
    into the orchestrator's bucket, on the stated grounds that losing them
    hands a stalled run a free reset and a real pending commit a free pass.
    RFC 7386 *replaces* a scalar with a patch object rather than merging into
    it, so a per-actor patch over the old shape would drop the migration
    silently — `_actor_patch` sends the whole migrated map in that case, which
    the same replace rule lands exactly as the old write did.

    These assert behaviour this unit does not change, so they are green before
    it, under its non-vacuity mutation, and after.
    """

    def test_a_bare_int_stall_migrates_to_the_orchestrators_bucket(
        self, tmp_path, mock_daemon
    ):
        cache = seeded_cache()
        cache["stall"] = 5
        mock_daemon.state = cache

        tracker(tmp_path, "touch some_file.py", ORCHESTRATOR)

        assert mock_daemon.state["stall"] == {ORCHESTRATOR: 6}

    def test_a_flat_commit_list_migrates_to_the_orchestrators_bucket(
        self, tmp_path, mock_daemon
    ):
        cache = seeded_cache()
        cache["unregistered_commits"] = ["old1111"]
        mock_daemon.state = cache

        tracker(
            tmp_path,
            'git commit -m "fix(x): BH-101"',
            ORCHESTRATOR,
            stdout="[dev fff6666] fix(x): BH-101\n 1 file changed",
        )

        assert mock_daemon.state["unregistered_commits"] == {
            ORCHESTRATOR: ["old1111", "fff6666"],
        }


class TestTheChargeStillLandsWithoutAnInterleave:
    """The ordinary path, with nothing racing — the bookkeeping still happens.

    Guards the direction the fix could fail in silently: a patch narrowed until
    it names nothing would pass every interleave test above, because leaving
    the siblings alone is most easily achieved by writing nothing at all.
    """

    def test_a_stalling_command_charges_this_actor(self, tmp_path, mock_daemon):
        mock_daemon.state = seeded_cache()
        tracker(tmp_path, "touch some_file.py", "agent-b")
        assert mock_daemon.state["stall"]["agent-b"] == 2

    def test_a_commit_charges_this_actor(self, tmp_path, mock_daemon):
        mock_daemon.state = seeded_cache()
        tracker(
            tmp_path,
            'git commit -m "fix(x): BH-101"',
            "agent-b",
            stdout="[dev fff6666] fix(x): BH-101\n 1 file changed",
        )
        assert mock_daemon.state["unregistered_commits"]["agent-b"] == [
            "bbb2222", "fff6666",
        ]

    def test_the_seeding_keeps_buckets_and_commits_unequal(self):
        """V3 — the fixture's own guard, so a wrong-dimension `len()` fails.

        Asserted rather than assumed: the counts are what make every `len()`
        above mean something, and a later edit that balanced them would quietly
        remove that property from every test in the file.
        """
        buckets = {actor for actor, _ in SEEDED_COMMITS}
        assert len(buckets) == 3
        assert len(SEEDED_COMMITS) == 4
