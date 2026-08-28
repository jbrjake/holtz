"""F2 — drive several fix actors through record → courier → edit, in loop order.

Five separate defects (items 19, 1, 32, 35, 42) share one cause: no test drives
more than one actor, so every one of them was invisible to a green suite. This
module builds the situation once.

**The ordering is the fixture.** A three-wide fix loop dispatches its subagents
together, so *both* `test_failed_before_fix` rows land before *either* courier
runs. Record-then-courier per actor, one actor at a time, is the sequential
shape the loop does not produce, and item 19 does not reproduce under it.

**What makes it useful is that it can name an actor's own row.** `len(rows) == 2`
and `agent_a_finding != agent_b_finding` are what let items 19 and 32 through:
`!=` passes when the code lands on a third wrong answer, and a count passes when
two quantities coincide. So every accessor here returns rows keyed by actor, and
the default seeding uses **three actors and four recorded failing tests** — the
two counts a careless assertion would confuse are deliberately unequal.

The orchestrator is the empty-string actor. It is a real actor and never a
wildcard, so it is in the default seeding rather than being a special case tests
have to remember to add.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from git_env import scrubbed_env  # noqa: E402
from hook_runner import run_hook  # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENFORCEMENT_HOOKS_DIR = os.path.join(REPO_ROOT, "enforcement", "hooks")

ORCHESTRATOR = ""

#: (actor, finding_id, test_name) — three actors, four rows. `agent-a` holds
#: two unpaired rows so "one courier per actor" and "one courier per row" give
#: different answers, which is what item 19's `LIMIT 1` row loss needs.
DEFAULT_SEEDING: tuple[tuple[str, str, str], ...] = (
    ("agent-a", "BH-101", "test_alpha"),
    ("agent-b", "BH-102", "test_beta"),
    (ORCHESTRATOR, "BH-103", "test_gamma"),
    ("agent-a", "BH-104", "test_delta"),
)


def record_command(finding_id: str, test_name: str) -> str:
    """The full-field recording command the engine actually accepts.

    Deliberately not the string `phase-fix-loop.md` teaches: that one omits
    `project`, `run` and `auditor` and exits 4 (item 31 / W03). A fixture built
    on the taught form would record nothing and every assertion below would be
    vacuous.
    """
    return (
        "sahjhan event test_failed_before_fix "
        f"--field finding_id={finding_id} "
        f"--field test_name={test_name} "
        "--field project=holtz "
        "--field run=1 "
        "--field auditor=holtz"
    )


@dataclass
class TwoActors:
    """Several actors sharing one ledger, driven through the fix-loop steps."""

    daemon: dict

    # ── plumbing ────────────────────────────────────────────────────────────

    @property
    def project_root(self) -> str:
        return str(self.daemon["project_root"])

    def env(self, **overrides: str) -> dict[str, str]:
        return scrubbed_env(
            SAHJHAN_DAEMON_SOCKET=str(self.daemon["sock_path"]),
            CLAUDE_PLUGIN_ROOT=REPO_ROOT,
            **overrides,
        )

    def sahjhan(self, *args: str, check: bool = True) -> subprocess.CompletedProcess:
        result = subprocess.run(
            [self.daemon["binary"], "--config-dir", self.daemon["config_dir"], *args],
            capture_output=True, text=True, cwd=self.project_root, timeout=15,
            env=self.env(),
        )
        if check and result.returncode != 0:
            raise RuntimeError(
                f"sahjhan {' '.join(args)} failed ({result.returncode})\n"
                f"stdout: {result.stdout}\nstderr: {result.stderr}"
            )
        return result

    def query(self, sql: str) -> list[dict]:
        result = self.sahjhan("query", sql, "--format", "json")
        return json.loads(result.stdout) if result.stdout.strip() else []

    def hook(self, hook_name: str, event: dict) -> dict:
        return run_hook(
            os.path.join(ENFORCEMENT_HOOKS_DIR, hook_name),
            {"cwd": self.project_root, **event},
            cwd=self.project_root,
            env=self.env(),
        )

    def bootstrap(self) -> None:
        """Put the ledger in `fix_loop` with an active run.

        Reuses `test_e2e_audit_flow`'s fast-forward rather than restating the
        transition sequence: two expressions of "how a test reaches fix_loop"
        is how one of them silently stops matching the protocol.
        """
        from test_e2e_audit_flow import _fast_forward_to_fix_loop  # noqa: PLC0415

        _fast_forward_to_fix_loop(self.daemon)
        self.freshen()

    def freshen(self) -> None:
        """Make `is_enforcement_fresh` true, so gates actually evaluate.

        `pre_tool_hook` skips `hook eval` entirely on a stale cache and exits
        `allow`. Without this the TDD-gate tests below pass **vacuously** — an
        `allow` that means "the gate never ran" is indistinguishable from an
        `allow` the gate decided, and that is precisely the shape item 1 hides
        in. `test_the_gate_still_bites` is the guard that catches it; this is
        what lets that guard mean something.
        """
        self.hook("protocol_tracker.py", {
            "tool_name": "Bash",
            "tool_input": {"command": "sahjhan status"},
            "tool_response": {"exit_code": 0, "output": "fix_loop"},
        })

    # ── the fix-loop steps, per actor ───────────────────────────────────────

    def record(self, finding_id: str, test_name: str) -> None:
        """Step: the actor records its failing test on the ledger."""
        self.sahjhan(*record_command(finding_id, test_name).split()[1:])

    def courier(self, actor: str, finding_id: str, test_name: str) -> dict:
        """Step: the PostToolUse courier names the actor behind that record.

        The command text is the same line the actor ran, because that is what
        Claude Code hands the hook — the courier's job is to attribute it, and
        replaying it here is what makes the attribution testable.
        """
        return self.hook("tdd_courier.py", {
            "tool_name": "Bash",
            "tool_input": {"command": record_command(finding_id, test_name)},
            "tool_response": {"exit_code": 0, "stdout": "", "stderr": ""},
            "agent_id": actor,
        })

    def edit(self, actor: str, path: str = "src.py") -> dict:
        """Step: the actor edits source, and the TDD gate decides."""
        return self.hook("pre_tool_hook.py", {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": os.path.join(self.project_root, path),
                "old_string": "x = 1",
                "new_string": "x = 2",
            },
            "agent_id": actor,
        })

    def sibling_fix_commit(self, finding_id: str) -> None:
        """A `fix_commit` landing for ``finding_id``, as the orchestrator's is.

        Records the run-global `state_transition` **and** the `finding_resolved`
        that `fix_commit` auto-emits — both, because the two halves are what
        item 1's window turns on: the transition is what used to revoke every
        actor's authorisation, and the resolution is what now consumes only the
        actor whose finding it names.

        Recorded as events rather than driven through `sahjhan transition
        fix_commit`, whose own gates (suite green, blast radius, hardening) are
        a different subject and would have to be faked to get here.
        """
        self.sahjhan(
            "event", "state_transition",
            "--field", "from=fix_loop", "--field", "to=fix_loop",
            "--field", "command=fix_commit",
            "--field", "run=1", "--field", "auditor=holtz",
            "--field", "project=holtz",
        )
        self.sahjhan(
            "event", "finding_resolved",
            "--field", "project=holtz", "--field", "run=1",
            "--field", "auditor=holtz", "--field", "phase=fix_loop",
            "--field", "step=10", "--field", f"id={finding_id}",
            "--field", "commit_hash=abc1234",
        )

    # ── the loop's own ordering ─────────────────────────────────────────────

    def seed_concurrently(
        self,
        seeding: tuple[tuple[str, str, str], ...] = DEFAULT_SEEDING,
    ) -> tuple[tuple[str, str, str], ...]:
        """Every actor records **before** any courier runs.

        This is the ordering a three-wide dispatch produces and the ordering
        under which item 19 misattributes. Returns the seeding so a caller can
        assert against the same tuples it drove.
        """
        for _actor, finding_id, test_name in seeding:
            self.record(finding_id, test_name)
        return seeding

    def run_couriers(
        self,
        seeding: tuple[tuple[str, str, str], ...] = DEFAULT_SEEDING,
    ) -> None:
        """One courier per recorded row, in the order the rows were written."""
        for actor, finding_id, test_name in seeding:
            self.courier(actor, finding_id, test_name)

    # ── what the ledger says afterwards ─────────────────────────────────────

    def evidence_rows(self) -> list[dict]:
        return self.query(
            "SELECT agent_id, finding_id, test_name, seq FROM events "
            "WHERE type='tdd_evidence' ORDER BY seq"
        )

    def evidence_for(self, actor: str) -> list[dict]:
        """Every evidence row attributed to one actor.

        The accessor tests should reach for: it supports "A's row names A's
        finding" as a positive claim about a value, rather than an inequality
        against a value that must not appear.
        """
        return [r for r in self.evidence_rows() if (r.get("agent_id") or "") == actor]

    def findings_recorded(self) -> list[dict]:
        return self.query(
            "SELECT finding_id, test_name, seq FROM events "
            "WHERE type='test_failed_before_fix' ORDER BY seq"
        )
