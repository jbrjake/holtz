"""Tests for scripts/enforcement_lint.py — the holtz-domain falsifier (#82).

The analyzer is enforcement code, so it is held to the enforcement testing
rules: **no check ships without a test proving it fires on a real historical
defect**, and a matching negative test asserting it passes on current `dev`.

Each fixture below reconstructs the *tree* a defect lived in, not just its
config, because the checks assert things about files — that a declared writer
exists, is registered in ``hooks.json``, is hash-pinned. A config-only fixture
would prove the check parses, not that it catches anything.

Historical defects reproduced here:

* **#73** — a gate consumed ``quiz_posed``/``quiz_answered`` whose writer's
  channel closed before the consumer ran (H1's shape; the temporal half is
  sahjhan's L2).
* **#79** — ``events.toml`` said ``context_reset`` means "after /clear" while
  its only writer fired on every ``UserPromptSubmit``, and the event was
  writable by the party the gate constrained (H5).
* **#81** — ``quiz_exhausted_resolved`` gates ``converge`` with no writer
  anywhere (H1), and claims a human acted while an agent may record it (H5).
* the stale-manifest class — a restricted event's writer that no entrypoint
  reaches, or that nothing hash-pins (H4).
"""
from __future__ import annotations

import hashlib
import json
import sys
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import enforcement_lint as el  # noqa: E402, I001


# ── Fixture tree ─────────────────────────────────────────────────────────────


def _write(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(body).lstrip("\n"), encoding="utf-8")
    return path


def build_tree(
    root: Path,
    *,
    events: str,
    transitions: str = "",
    protocol: str = "",
    hooks: str = "",
    renders: str = "",
    skills: dict[str, str] | None = None,
    hook_scripts: dict[str, str] | None = None,
    tool_scripts: dict[str, str] | None = None,
    hooks_json: dict | None = None,
    trusted: list[str] | None = None,
) -> el.Tree:
    """Materialise a minimal holtz-shaped tree and return a Tree pointing at it."""
    config = root / "enforcement"
    _write(config / "events.toml", events)
    _write(config / "transitions.toml", transitions)
    _write(
        config / "protocol.toml",
        protocol
        or """
        [protocol]
        name = "fixture"
        version = "1.0.0"
        """,
    )
    _write(config / "hooks.toml", hooks)
    if renders:
        _write(config / "renders.toml", renders)

    for name, body in (skills or {}).items():
        _write(root / "skills" / name, body)
    for name, body in (hook_scripts or {}).items():
        _write(config / "hooks" / name, body)
    # enforcement/scripts holds gate helpers — invoked by path, never fired by
    # the harness. They are `tool:` producers, not `hook:` ones.
    for name, body in (tool_scripts or {}).items():
        _write(config / "scripts" / name, body)

    _write(root / "hooks" / "hooks.json", json.dumps(hooks_json or {"hooks": {}}))

    lines = ["[callers]"]
    for name in trusted or []:
        # The daemon keys the manifest by the caller's path relative to the
        # config dir, so a tool lands under `scripts/`, a hook under `hooks/`.
        subdir = "scripts" if (config / "scripts" / name).exists() else "hooks"
        digest = hashlib.sha256(
            (config / subdir / name).read_bytes()
        ).hexdigest()
        lines.append(f'"{subdir}/{name}" = "sha256:{digest}"')
    _write(config / "trusted-callers.toml", "\n".join(lines) + "\n")

    # Every path must be overridden. Leaving `hooks_json` at its default let
    # the real repo's registrations leak into the fixture, so a hook the
    # fixture never registered still looked registered.
    return el.Tree(
        root=root,
        config_dir=config,
        skills_dir=root / "skills",
        hooks_json=root / "hooks" / "hooks.json",
    )


def findings_for(tree: el.Tree, check: str) -> list[el.Finding]:
    return el.run_checks(el.build_model(tree), [check])


# ── H1: a gate consuming an event nothing can write ──────────────────────────


class TestH1Unsatisfiable:
    """#81, live on dev: `converge` waits on an event with no writer."""

    # Faithful to the pre-fix tree: the exhaustion event has a real hook
    # writer, and only the *resolution* event — the escape — has none.
    ISSUE_81 = """
        [events.quiz_exhausted]
        description = "Lens subagent exhausted quiz attempts"
        restricted = true
        fields = [{ name = "perspective", type = "string" }]

        [[events.quiz_exhausted.producers]]
        id = "hook:enforcement/hooks/lens_quiz.py"

        [events.quiz_exhausted_resolved]
        description = "Human reviewed an exhausted quiz"
        fields = [{ name = "resolution", type = "string", pattern = "^human_reviewed$" }]
        """

    CONVERGE_GATE = """
        [[transitions]]
        from = "final_sweep"
        to = "final_sweep_clean"
        command = "converge"
        gates = [
            { type = "query", sql = "SELECT count(*) = 0 FROM events e WHERE e.type='quiz_exhausted' AND e.perspective NOT IN (SELECT r.perspective FROM events r WHERE r.type='quiz_exhausted_resolved')", expect = "true" },
        ]
        """

    def test_fires_on_issue_81(self, tmp_path: Path) -> None:
        tree = build_tree(
            tmp_path, events=self.ISSUE_81, transitions=self.CONVERGE_GATE
        )
        findings = findings_for(tree, "H1")
        assert [f.subject for f in findings] == [
            "events.toml: event 'quiz_exhausted_resolved'"
        ]
        assert findings[0].level == "error"

    def test_reads_event_types_out_of_a_not_in_subquery(self, tmp_path: Path) -> None:
        """The NOT IN (SELECT … type='Y') form is where #81 hid from the eye."""
        tree = build_tree(
            tmp_path, events=self.ISSUE_81, transitions=self.CONVERGE_GATE
        )
        model = el.build_model(tree)
        assert "quiz_exhausted_resolved" in model.consumed

    def test_silent_once_a_producer_is_declared(self, tmp_path: Path) -> None:
        events = self.ISSUE_81 + """
        [[events.quiz_exhausted_resolved.producers]]
        id = "agent:cli"
        """
        tree = build_tree(tmp_path, events=events, transitions=self.CONVERGE_GATE)
        assert findings_for(tree, "H1") == []

    def test_render_only_consumer_warns_rather_than_errors(self, tmp_path: Path) -> None:
        """An empty document section is rot, not a blocked run."""
        tree = build_tree(
            tmp_path,
            events="""
            [events.prediction]
            description = "A predictive recon prediction"
            fields = [{ name = "target", type = "string" }]
            """,
            renders="""
            [[renders]]
            target = "SUMMARY.md"
            template = "templates/summary.md.tera"
            trigger = "on_state"
            state = "converged"
            """,
        )
        _write(
            tree.config_dir / "templates" / "summary.md.tera",
            '{% set p = events | where_eq(attribute="event_type", value="prediction") %}',
        )
        findings = findings_for(tree, "H1")
        assert [f.level for f in findings] == ["warning"]


# ── H2: a declared producer that resolves to nothing ─────────────────────────


class TestH2FalseDeclarations:
    """The declaration is a claim. #79's sin, committed one level up."""

    def test_fires_on_a_writer_that_does_not_exist(self, tmp_path: Path) -> None:
        tree = build_tree(
            tmp_path,
            events="""
            [events.context_reset]
            description = "Context boundary"
            fields = []

            [[events.context_reset.producers]]
            id = "hook:enforcement/hooks/does_not_exist.py"
            """,
        )
        findings = findings_for(tree, "H2")
        assert len(findings) == 1
        assert "does not exist" in findings[0].message

    def test_fires_when_the_named_file_does_not_write_the_event(
        self, tmp_path: Path
    ) -> None:
        tree = build_tree(
            tmp_path,
            events="""
            [events.context_reset]
            description = "Context boundary"
            fields = []

            [[events.context_reset.producers]]
            id = "hook:enforcement/hooks/session_start.py"
            """,
            hook_scripts={"session_start.py": "def main():\n    pass\n"},
        )
        findings = findings_for(tree, "H2")
        assert len(findings) == 1
        assert "does not write this event" in findings[0].message

    def test_fires_when_agent_cli_is_claimed_for_a_restricted_event(
        self, tmp_path: Path
    ) -> None:
        """`sahjhan event` cannot record a restricted type; the daemon refuses."""
        tree = build_tree(
            tmp_path,
            events="""
            [events.quiz_posed]
            description = "Quiz questions posed"
            restricted = true
            fields = []

            [[events.quiz_posed.producers]]
            id = "agent:cli"
            """,
        )
        findings = findings_for(tree, "H2")
        assert len(findings) == 1
        assert "restricted" in findings[0].message

    def test_accepts_a_hook_that_really_writes_it(self, tmp_path: Path) -> None:
        tree = build_tree(
            tmp_path,
            events="""
            [events.context_reset]
            description = "Context boundary"
            fields = []

            [[events.context_reset.producers]]
            id = "hook:enforcement/hooks/session_start.py"
            """,
            hook_scripts={
                "session_start.py": 'record_authed_event("context_reset", {}, cwd)\n'
            },
        )
        assert findings_for(tree, "H2") == []

    def test_fires_on_an_undeclared_named_query(self, tmp_path: Path) -> None:
        """A misnamed query blinds every other check to what the gate consumes."""
        tree = build_tree(
            tmp_path,
            events="""
            [events.finding]
            description = "A punchlist finding"
            fields = []
            """,
            transitions="""
            [[transitions]]
            from = "a"
            to = "b"
            command = "converge"
            gates = [{ type = "query", query = "typo_here", expect = "0" }]
            """,
        )
        findings = findings_for(tree, "H2")
        assert len(findings) == 1
        assert "typo_here" in findings[0].message


# ── H3: a writer nobody declared ─────────────────────────────────────────────


class TestH3UndeclaredWriters:
    def test_fires_on_an_undeclared_hook_writer(self, tmp_path: Path) -> None:
        """A second hook writing an event a gate trusts is #79's shape."""
        tree = build_tree(
            tmp_path,
            events="""
            [events.context_reset]
            description = "Context boundary"
            fields = []

            [[events.context_reset.producers]]
            id = "hook:enforcement/hooks/session_start.py"
            """,
            hook_scripts={
                "session_start.py": 'record_authed_event("context_reset", {}, cwd)\n',
                "primer.py": 'record_authed_event("context_reset", {}, cwd)\n',
            },
        )
        findings = findings_for(tree, "H3")
        assert len(findings) == 1
        assert "primer.py" in findings[0].message

    def test_ignores_extra_skill_files_for_agent_events(self, tmp_path: Path) -> None:
        """`agent:cli` covers the agent writing from anywhere.

        Demanding a declaration per skill file would fail the build every time
        someone added a doc mention, without telling anyone anything new: the
        answer to "who can write this" is already "the agent, at will".
        """
        tree = build_tree(
            tmp_path,
            events="""
            [events.finding]
            description = "A punchlist finding"
            fields = []

            [[events.finding.producers]]
            id = "agent:cli"
            """,
            skills={
                "SKILL.md": "Record it with `sahjhan event finding --field id=BH-001`.\n",
                "phase-audit.md": "Also `sahjhan event finding --field id=BH-002`.\n",
            },
        )
        assert findings_for(tree, "H3") == []

    def test_fires_when_an_agent_path_exists_but_is_not_declared(
        self, tmp_path: Path
    ) -> None:
        tree = build_tree(
            tmp_path,
            events="""
            [events.finding]
            description = "A punchlist finding"
            fields = []

            [[events.finding.producers]]
            id = "engine:emits:fix_commit"
            """,
            transitions="""
            [[transitions]]
            from = "fix_loop"
            to = "fix_loop"
            command = "fix_commit"
            emits = [{ event = "finding", fields = { id = "x" } }]
            """,
            skills={"SKILL.md": "Run `sahjhan event finding --field id=BH-001`.\n"},
        )
        findings = findings_for(tree, "H3")
        assert len(findings) == 1
        assert "agent:cli" in findings[0].message


# ── H4: registered and hash-pinned, or it never runs ─────────────────────────


class TestH4HookRegistration:
    RESTRICTED = """
        [events.context_reset]
        description = "Context boundary"
        restricted = true
        fields = []

        [[events.context_reset.producers]]
        id = "hook:enforcement/hooks/session_start.py"
        """
    WRITER = {"session_start.py": 'record_authed_event("context_reset", {}, cwd)\n'}
    REGISTERED = {
        "hooks": {
            "SessionStart": [
                {
                    "matcher": "*",
                    "hooks": [
                        {
                            "type": "command",
                            "command": 'python3 "${CLAUDE_PLUGIN_ROOT}/enforcement/hooks/session_start.py"',
                        }
                    ],
                }
            ]
        }
    }

    def test_fires_when_the_hook_is_not_registered(self, tmp_path: Path) -> None:
        """A writer the harness never invokes cannot produce anything."""
        tree = build_tree(
            tmp_path,
            events=self.RESTRICTED,
            hook_scripts=self.WRITER,
            trusted=["session_start.py"],
        )
        messages = [f.message for f in findings_for(tree, "H4")]
        assert any("not registered" in m for m in messages)

    def test_fires_when_a_restricted_writer_is_not_hash_pinned(
        self, tmp_path: Path
    ) -> None:
        """The stale-manifest class: enforcement dies silently at runtime."""
        tree = build_tree(
            tmp_path,
            events=self.RESTRICTED,
            hook_scripts=self.WRITER,
            hooks_json=self.REGISTERED,
        )
        messages = [f.message for f in findings_for(tree, "H4")]
        assert any("hash-pinned" in m for m in messages)

    def test_passes_when_registered_and_pinned(self, tmp_path: Path) -> None:
        tree = build_tree(
            tmp_path,
            events=self.RESTRICTED,
            hook_scripts=self.WRITER,
            hooks_json=self.REGISTERED,
            trusted=["session_start.py"],
        )
        assert findings_for(tree, "H4") == []

    def test_an_imported_module_inherits_its_entrypoint(self, tmp_path: Path) -> None:
        """The daemon authenticates the process, not the module.

        `quiz_vault.py` only ever executes inside `quiz_capture.py`, which is
        registered and pinned. Demanding a pin on the module itself reported a
        defect that does not exist.
        """
        events = self.RESTRICTED.replace("session_start.py", "quiz_vault.py")
        tree = build_tree(
            tmp_path,
            events=events,
            hook_scripts={
                "quiz_vault.py": 'record_authed_event("context_reset", {}, cwd)\n',
                "quiz_capture.py": "from quiz_vault import record_bank_generated\n",
            },
            hooks_json={
                "hooks": {
                    "PostToolUse": [
                        {
                            "matcher": "Bash",
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": 'python3 "${CLAUDE_PLUGIN_ROOT}/enforcement/hooks/quiz_capture.py"',
                                }
                            ],
                        }
                    ]
                }
            },
            trusted=["quiz_capture.py"],
        )
        assert findings_for(tree, "H4") == []


class TestToolProducers:
    """`tool:` — a writer invoked by path rather than fired by the harness.

    `verify_suite.py` (#83 P4) is the first: a gate runs it, and the fix loop
    teaches the agent to. Asking the hook question about it — "is it in
    hooks.json?" — produces a permanent false error, because the answer is
    always no and always fine. What it still owes is the pin, since the daemon
    authenticates whichever process connects, however it was started.
    """

    EVENTS = """
        [events.suite_green]
        description = "Suite passed on a named tree"
        restricted = true
        fields = []

        [[events.suite_green.producers]]
        id = "tool:enforcement/scripts/verify_suite.py"
        """
    WRITER = {"verify_suite.py": 'record_authed_event("suite_green", f, cwd)\n'}

    def test_discovered_as_a_tool_not_a_hook(self, tmp_path: Path) -> None:
        """The producer kind follows the directory, and H2 accepts it."""
        tree = build_tree(
            tmp_path, events=self.EVENTS, tool_scripts=self.WRITER,
            trusted=["verify_suite.py"],
        )
        writers = el.build_model(tree).writers["suite_green"]
        assert [w.producer_id for w in writers] == [
            "tool:enforcement/scripts/verify_suite.py"
        ]
        assert findings_for(tree, "H2") == []

    def test_registration_is_not_demanded(self, tmp_path: Path) -> None:
        """Nothing in hooks.json, and that is correct for a gate helper."""
        tree = build_tree(
            tmp_path, events=self.EVENTS, tool_scripts=self.WRITER,
            trusted=["verify_suite.py"],
        )
        assert findings_for(tree, "H4") == []

    def test_a_restricted_tool_must_still_be_hash_pinned(
        self, tmp_path: Path
    ) -> None:
        """`tool:` must not become an escape hatch out of H4.

        Skipping the pin is the stale-manifest class: the daemon refuses the
        caller, the write is swallowed, and the gate it feeds fails open.
        """
        tree = build_tree(tmp_path, events=self.EVENTS, tool_scripts=self.WRITER)
        messages = [f.message for f in findings_for(tree, "H4")]
        assert any("hash-pinned" in m for m in messages), messages

    def test_a_missing_file_is_still_flagged(self, tmp_path: Path) -> None:
        tree = build_tree(tmp_path, events=self.EVENTS)
        messages = [f.message for f in findings_for(tree, "H4")]
        assert any("does not exist" in m for m in messages), messages

    def test_a_tool_that_does_not_write_the_event_is_flagged(
        self, tmp_path: Path
    ) -> None:
        """The declaration is a claim about a file, whatever kind it is."""
        tree = build_tree(
            tmp_path,
            events=self.EVENTS,
            tool_scripts={"verify_suite.py": "# writes nothing\n"},
            trusted=["verify_suite.py"],
        )
        messages = [f.message for f in findings_for(tree, "H2")]
        assert any("does not write this event" in m for m in messages), messages


# ── H5: evidence the constrained party can manufacture ───────────────────────


class TestH5Attestation:
    LEVELS = """
        [protocol]
        name = "fixture"
        version = "1.0.0"

        [attestation]
        levels = ["agent", "tool", "ambient", "host"]
        """

    def test_fires_on_issue_79_shape(self, tmp_path: Path) -> None:
        """An event claiming host provenance that `sahjhan event` can write.

        This is #79 stated as a static fact: the gate exists to force a real
        context reset, and the evidence it turns on was recordable by the agent
        the gate constrains.
        """
        tree = build_tree(
            tmp_path,
            protocol=self.LEVELS,
            events="""
            [events.context_reset]
            description = "Context boundary"
            attestation = "host"
            fields = []
            """,
        )
        findings = findings_for(tree, "H5")
        assert len(findings) == 1
        assert "not restricted" in findings[0].message

    def test_fires_when_a_skill_teaches_a_non_agent_event(
        self, tmp_path: Path
    ) -> None:
        tree = build_tree(
            tmp_path,
            protocol=self.LEVELS,
            events="""
            [events.quiz_answered]
            description = "Lens subagent answered quiz"
            attestation = "tool"
            restricted = true
            fields = []
            """,
            skills={
                "SKILL.md": "Record `sahjhan authed-event quiz_answered --field pass=true`.\n"
            },
        )
        findings = findings_for(tree, "H5")
        assert len(findings) == 1
        assert "skill file teaches" in findings[0].message

    def test_silent_for_agent_attested_events(self, tmp_path: Path) -> None:
        """Self-attestation is fine for bookkeeping; only a mismatch is a bug."""
        tree = build_tree(
            tmp_path,
            protocol=self.LEVELS,
            events="""
            [events.finding]
            description = "A punchlist finding"
            attestation = "agent"
            fields = []
            """,
            skills={"SKILL.md": "Run `sahjhan event finding --field id=BH-001`.\n"},
        )
        assert findings_for(tree, "H5") == []

    def test_silent_without_an_attestation_section(self, tmp_path: Path) -> None:
        """No declared ordering means nothing to compare — no opinion."""
        tree = build_tree(
            tmp_path,
            events="""
            [events.context_reset]
            description = "Context boundary"
            attestation = "host"
            fields = []
            """,
        )
        assert findings_for(tree, "H5") == []


# ── H6: the agent must be able to find the command ───────────────────────────


class TestH6SkillAgreement:
    def test_fires_on_a_transition_no_skill_teaches(self, tmp_path: Path) -> None:
        tree = build_tree(
            tmp_path,
            events="",
            transitions="""
            [[transitions]]
            from = "pattern_analysis"
            to = "fix_loop"
            command = "pattern_done"
            """,
        )
        findings = findings_for(tree, "H6")
        assert len(findings) == 1
        assert findings[0].level == "warning"
        assert "pattern_done" in findings[0].subject

    def test_errors_on_a_skill_teaching_a_transition_that_does_not_exist(
        self, tmp_path: Path
    ) -> None:
        """This one fails at runtime, so it is an error rather than a warning."""
        tree = build_tree(
            tmp_path,
            events="",
            skills={"SKILL.md": "Run `sahjhan transition ghost_command`.\n"},
        )
        findings = findings_for(tree, "H6")
        assert len(findings) == 1
        assert findings[0].level == "error"
        assert "ghost_command" in findings[0].subject

    def test_accepts_an_inline_code_span(self, tmp_path: Path) -> None:
        """Holtz teaches commands mid-sentence, not in fenced blocks.

        Scanning only fences reported eleven documented transitions as
        undocumented — a false-positive rate that would have made the check
        unusable.
        """
        tree = build_tree(
            tmp_path,
            events="",
            transitions="""
            [[transitions]]
            from = "awaiting_clear"
            to = "fix_loop"
            command = "resume"
            """,
            skills={
                "phase-fix-loop.md": (
                    "4. Run `sahjhan --config-dir \"$CLAUDE_PLUGIN_ROOT/enforcement\" "
                    "transition resume` → now you are in `fix_loop`.\n"
                )
            },
        )
        assert findings_for(tree, "H6") == []

    def test_ignores_prose_mentions(self, tmp_path: Path) -> None:
        """Naming an event in a sentence is not a command anyone can run.

        The throwaway prototype matched a bare `event <name>` regex and
        invented producers called `event and` and `event the`.
        """
        tree = build_tree(
            tmp_path,
            events="""
            [events.finding]
            description = "A punchlist finding"
            fields = []
            """,
            skills={
                "notes.md": (
                    "The hook records an event and the gate reads it later; "
                    "escalate the lens for human review (quiz_exhausted_resolved).\n"
                )
            },
        )
        model = el.build_model(tree)
        assert model.writers == {}


# ── H7: a gate predicate with a copy in Python ───────────────────────────────


class TestH7PredicateCopies:
    """#77, as it still sat in the tree after being fixed once.

    The deadlock was two expressions of one fact. The fix made the hook run the
    *ledger* rather than a token-counting mirror — but it ran it from a SQL
    string of its own, so the tree still held two copies and nothing compared
    them. This is the check that would have made the next drift fail at rest.
    """

    PATTERN_CHECK_GATE = """
        [[transitions]]
        from = "fix_loop"
        to = "pattern_analysis"
        command = "pattern_check"
        gates = [
            { type = "query", sql = "SELECT count(*) >= 3 FROM events WHERE type='finding_resolved' AND seq > COALESCE((SELECT MAX(seq) FROM events WHERE type='pattern_analysis_complete'), 0)", expect = "true", intent = "3+ fixes since the last pattern analysis" },
        ]
        """

    # Written the way the real hook wrote it: implicitly concatenated
    # fragments across four lines. A regex would have to reassemble them.
    TRACKER = '''
        _FIXES_SINCE_PATTERN_SQL = (
            "SELECT count(*) AS n FROM events "
            "WHERE type='finding_resolved' "
            "AND seq > COALESCE((SELECT MAX(seq) FROM events "
            "WHERE type='pattern_analysis_complete'), 0)"
        )
        '''

    def test_fires_on_the_third_copy(self, tmp_path: Path) -> None:
        tree = build_tree(
            tmp_path,
            events="",
            transitions=self.PATTERN_CHECK_GATE,
            hook_scripts={"protocol_tracker.py": self.TRACKER},
        )
        findings = findings_for(tree, "H7")
        assert len(findings) == 1
        assert findings[0].level == "error"
        assert "protocol_tracker.py" in findings[0].subject
        assert "pattern_check" in findings[0].message

    def test_silent_once_the_hook_resolves_the_name(self, tmp_path: Path) -> None:
        """The fix is not a tidier copy — it is having no copy at all."""
        tree = build_tree(
            tmp_path,
            events="",
            protocol="""
            [protocol]
            name = "fixture"
            version = "1.0.0"

            [queries.pattern_analysis_overdue]
            sql = "SELECT count(*) >= 3 FROM events WHERE type='finding_resolved' AND seq > COALESCE((SELECT MAX(seq) FROM events WHERE type='pattern_analysis_complete'), 0)"
            intent = "3+ fixes since the last pattern analysis"
            """,
            transitions="""
            [[transitions]]
            from = "fix_loop"
            to = "pattern_analysis"
            command = "pattern_check"
            gates = [
                { type = "query", query = "pattern_analysis_overdue", expect = "true" },
            ]
            """,
            hook_scripts={
                "protocol_tracker.py": 'QUERY = "pattern_analysis_overdue"\n'
            },
        )
        assert findings_for(tree, "H7") == []

    def test_unrelated_sql_in_a_hook_is_left_alone(self, tmp_path: Path) -> None:
        """Sharing SQL keywords is not sharing a fact."""
        tree = build_tree(
            tmp_path,
            events="",
            transitions=self.PATTERN_CHECK_GATE,
            hook_scripts={
                "other.py": '''SQL = "SELECT file_path FROM events WHERE type='file_read'"\n'''
            },
        )
        assert findings_for(tree, "H7") == []


# ── H8: the printed escape must be the fact that blocked ─────────────────────


class TestH8EscapeIdentity:
    """#77's deadlock stated as a property rather than a hand-written test."""

    DRIFTED = """
        [[transitions]]
        from = "fix_loop"
        to = "awaiting_clear"
        command = "iteration_boundary"
        gates = [
            { type = "query", sql = "SELECT count(*) < 3 FROM events WHERE type='state_transition' AND command='fix_commit' AND seq > COALESCE((SELECT MAX(seq) FROM events WHERE type='pattern_analysis_complete'), 0)", expect = "true", intent = "pattern analysis required after 3+ fixes — run pattern_check before iteration_boundary" },
        ]

        [[transitions]]
        from = "fix_loop"
        to = "pattern_analysis"
        command = "pattern_check"
        gates = [
            { type = "query", sql = "SELECT count(*) >= 3 FROM events WHERE type='finding_resolved' AND seq > COALESCE((SELECT MAX(seq) FROM events WHERE type='pattern_analysis_complete'), 0)", expect = "true", intent = "3+ findings resolved since the last pattern analysis" },
        ]
        """

    SHARED = """
        [protocol]
        name = "fixture"
        version = "1.0.0"

        [queries.pattern_analysis_overdue]
        sql = "SELECT count(*) >= 3 FROM events WHERE type='finding_resolved' AND seq > COALESCE((SELECT MAX(seq) FROM events WHERE type='pattern_analysis_complete'), 0)"
        intent = "3+ findings resolved since the last pattern analysis"
        """

    def test_warns_while_the_escape_is_decided_inline(self, tmp_path: Path) -> None:
        """Two inline predicates cannot be proven to be one fact."""
        tree = build_tree(tmp_path, events="", transitions=self.DRIFTED)
        findings = findings_for(tree, "H8")
        assert [f.subject for f in findings] == [
            "transitions.toml: transition 'iteration_boundary'"
        ]
        assert findings[0].level == "warning"
        assert "pattern_check" in findings[0].message

    def test_errors_when_the_block_ignores_the_escape_s_query(
        self, tmp_path: Path
    ) -> None:
        """The escape has a name; the block still decided its own way."""
        transitions = """
            [[transitions]]
            from = "fix_loop"
            to = "awaiting_clear"
            command = "iteration_boundary"
            gates = [
                { type = "query", sql = "SELECT count(*) < 3 FROM events WHERE type='state_transition' AND command='fix_commit'", expect = "true", intent = "run pattern_check first" },
            ]

            [[transitions]]
            from = "fix_loop"
            to = "pattern_analysis"
            command = "pattern_check"
            gates = [
                { type = "query", query = "pattern_analysis_overdue", expect = "true" },
            ]
            """
        tree = build_tree(
            tmp_path, events="", protocol=self.SHARED, transitions=transitions
        )
        findings = findings_for(tree, "H8")
        assert len(findings) == 1
        assert findings[0].level == "error"
        assert "pattern_analysis_overdue" in findings[0].message

    def test_silent_when_both_sides_reference_one_query(self, tmp_path: Path) -> None:
        """Complementary expectations of one predicate cannot deadlock."""
        transitions = """
            [[transitions]]
            from = "fix_loop"
            to = "awaiting_clear"
            command = "iteration_boundary"
            gates = [
                { type = "query", query = "pattern_analysis_overdue", expect = "false", intent = "run pattern_check before leaving the iteration" },
            ]

            [[transitions]]
            from = "fix_loop"
            to = "pattern_analysis"
            command = "pattern_check"
            gates = [
                { type = "query", query = "pattern_analysis_overdue", expect = "true" },
            ]
            """
        tree = build_tree(
            tmp_path, events="", protocol=self.SHARED, transitions=transitions
        )
        assert findings_for(tree, "H8") == []

    def test_a_python_block_must_name_the_query_it_points_at(
        self, tmp_path: Path
    ) -> None:
        """The commit gate's block is the site #77 actually deadlocked."""
        transitions = """
            [[transitions]]
            from = "fix_loop"
            to = "pattern_analysis"
            command = "pattern_check"
            gates = [
                { type = "query", query = "pattern_analysis_overdue", expect = "true" },
            ]
            """
        drifted = (
            'QUERY = "some_other_query"\n'
            'def main():\n'
            '    exit_block("BLOCKED: run sahjhan transition pattern_check")\n'
        )
        tree = build_tree(
            tmp_path,
            events="",
            protocol=self.SHARED
            + '\n[queries.some_other_query]\nsql = "SELECT 1 FROM events"\n',
            transitions=transitions,
            hook_scripts={"commit_gate.py": drifted},
        )
        findings = findings_for(tree, "H8")
        assert [f.level for f in findings] == ["error"]
        assert "commit_gate.py" in findings[0].subject

    def test_a_block_naming_no_query_is_not_this_check_s_business(
        self, tmp_path: Path
    ) -> None:
        """`fix_commit` as an escape means *do the work*, not *the same fact*.

        The unregistered-commit block tells the agent to run `fix_commit`,
        whose gates are additional obligations — a passing suite, a recorded
        blast radius. Demanding it share a predicate would be nonsense, and
        reporting it would train everyone to ignore this check.
        """
        transitions = """
            [[transitions]]
            from = "fix_loop"
            to = "fix_loop"
            command = "fix_commit"
            args = ["item_id"]
            gates = [
                { type = "command_succeeds", cmd = "pytest", intent = "tests must pass" },
            ]
            """
        tree = build_tree(
            tmp_path,
            events="",
            transitions=transitions,
            hook_scripts={
                "commit_gate.py": (
                    "def main():\n"
                    '    exit_block("BLOCKED: run sahjhan transition fix_commit")\n'
                )
            },
        )
        assert findings_for(tree, "H8") == []


# ── H9: a transition that does not record the state it implies ───────────────


class TestH9TransitionStateDecoupling:
    """The `fix_commit`/`finding_resolved` decoupling, generalised.

    That one shipped as a *gate* forcing the agent to type the fact twice,
    which was rejected on the grounds that holtz exists to minimise agent
    tokens; the accepted fix was `emits`. The three deferral transitions were
    never converted and still carry the two-command shape.
    """

    DEFER = """
        [[transitions]]
        from = "fix_loop"
        to = "fix_loop"
        command = "defer_low"
        args = ["item_id"]
        gates = [
            { type = "query", sql = "SELECT count(*) = 0 FROM events WHERE type IN ('finding_resolved', 'finding_deferred') AND id='{{item_id}}'", expect = "true", intent = "finding must not already be resolved or deferred" },
        ]
        """

    def test_fires_when_nothing_records_the_deferral(self, tmp_path: Path) -> None:
        tree = build_tree(tmp_path, events="", transitions=self.DEFER)
        findings = findings_for(tree, "H9")
        assert len(findings) == 1
        assert findings[0].level == "error"
        assert "finding_deferred" in findings[0].message

    def test_silent_once_the_transition_emits_it(self, tmp_path: Path) -> None:
        tree = build_tree(
            tmp_path,
            events="",
            transitions=self.DEFER
            + """
            emits = [
                { event = "finding_deferred", fields = { id = "{{item_id}}", reason = "low_priority" } },
            ]
            """,
        )
        assert findings_for(tree, "H9") == []

    def test_resolves_the_predicate_through_a_named_query(
        self, tmp_path: Path
    ) -> None:
        """Naming the predicate must not blind the check to it."""
        tree = build_tree(
            tmp_path,
            events="",
            protocol="""
            [protocol]
            name = "fixture"
            version = "1.0.0"

            [queries.item_open]
            sql = "SELECT count(*) = 0 FROM events WHERE type IN ('finding_resolved', 'finding_deferred') AND id='{{item_id}}'"
            intent = "finding must not already be resolved or deferred"
            """,
            transitions="""
            [[transitions]]
            from = "fix_loop"
            to = "fix_loop"
            command = "defer_low"
            args = ["item_id"]
            gates = [
                { type = "query", query = "item_open", expect = "true" },
            ]
            """,
        )
        assert len(findings_for(tree, "H9")) == 1

    def test_ignores_a_transition_that_only_reads_the_item(
        self, tmp_path: Path
    ) -> None:
        """Requiring an event to *exist* is not claiming to change its state."""
        tree = build_tree(
            tmp_path,
            events="",
            transitions="""
            [[transitions]]
            from = "perspective_clean"
            to = "audit"
            command = "lens_rotate"
            args = ["completed_perspective"]
            gates = [
                { type = "query", sql = "SELECT count(*) >= 1 FROM events WHERE type='set_member_complete' AND member='{{completed_perspective}}'", expect = "true", intent = "perspective must be marked complete before rotating" },
            ]
            """,
        )
        assert findings_for(tree, "H9") == []


# ── Discovery soundness ──────────────────────────────────────────────────────


class TestWritePathDiscovery:
    """Grepping for event names cannot work — enumerate the verbs."""

    def test_set_complete_writes_set_member_complete(self, tmp_path: Path) -> None:
        """The prototype's one false positive: no write site names the event."""
        tree = build_tree(
            tmp_path,
            events="""
            [events.set_member_complete]
            description = "A completion set member passed clean"
            fields = []
            """,
            skills={
                "SKILL.md": "Run `sahjhan set complete perspective` when clean.\n"
            },
        )
        model = el.build_model(tree)
        assert "set_member_complete" in model.writers

    def test_an_alias_is_a_real_write_path(self, tmp_path: Path) -> None:
        tree = build_tree(
            tmp_path,
            protocol="""
            [protocol]
            name = "fixture"
            version = "1.0.0"

            [aliases]
            "resolve" = "event finding_resolved"
            """,
            events="""
            [events.finding_resolved]
            description = "A finding was resolved"
            fields = []
            """,
            skills={"SKILL.md": "Run `sahjhan resolve --field id=BH-001`.\n"},
        )
        model = el.build_model(tree)
        assert "finding_resolved" in model.writers

    def test_a_hook_block_message_is_a_taught_command(self, tmp_path: Path) -> None:
        """The message an agent reads while stuck is the escape it will run."""
        tree = build_tree(
            tmp_path,
            events="""
            [events.test_failed_before_fix]
            description = "Test demonstrating the bug failed before the fix"
            fields = []
            """,
            hooks="""
            [[hooks]]
            event = "PreToolUse"
            tools = ["Edit"]
            action = "block"
            message = "TDD violation. Record with: sahjhan event test_failed_before_fix --field finding_id=BH-001"

            [hooks.gate]
            type = "ledger_has_event_since"
            event = "test_failed_before_fix"
            since = "last_transition"
            """,
        )
        model = el.build_model(tree)
        assert "test_failed_before_fix" in model.writers
        assert findings_for(tree, "H1") == []

    def test_a_transition_emits_block_is_a_producer(self, tmp_path: Path) -> None:
        tree = build_tree(
            tmp_path,
            events="""
            [events.finding_resolved]
            description = "A finding was resolved"
            fields = []
            """,
            transitions="""
            [[transitions]]
            from = "fix_loop"
            to = "fix_loop"
            command = "fix_commit"
            emits = [{ event = "finding_resolved", fields = { id = "{{item_id}}" } }]
            """,
        )
        model = el.build_model(tree)
        assert any(
            w.producer_id == "engine:emits:fix_commit"
            for w in model.writers["finding_resolved"]
        )

    def test_a_tera_template_is_a_consumer(self, tmp_path: Path) -> None:
        """Both linters called `prediction` dead while SUMMARY.md reads it."""
        tree = build_tree(
            tmp_path,
            events="""
            [events.prediction]
            description = "A predictive recon prediction"
            fields = []
            """,
            renders="""
            [[renders]]
            target = "SUMMARY.md"
            template = "templates/summary.md.tera"
            trigger = "on_state"
            state = "converged"
            """,
        )
        _write(
            tree.config_dir / "templates" / "summary.md.tera",
            '{% set p = events | where_eq(attribute="event_type", value="prediction") %}',
        )
        model = el.build_model(tree)
        assert "prediction" in model.consumed


# ── The live tree ────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def model() -> el.Model:
    """The real enforcement config, parsed once."""
    return el.build_model()


class TestCurrentDev:
    """Negative tests: what the analyzer must NOT say about the real config."""

    @pytest.mark.parametrize("check", ["H2", "H3", "H4", "H5"])
    def test_no_errors(self, model: el.Model, check: str) -> None:
        errors = [f for f in el.run_checks(model, [check]) if f.level == "error"]
        assert errors == [], "\n".join(f.render() for f in errors)

    def test_context_reset_is_host_attested_and_unforgeable(
        self, model: el.Model
    ) -> None:
        """#79's fix, asserted as a property rather than a hook behaviour."""
        spec = model.events["context_reset"]
        assert spec["attestation"] == "host"
        assert spec["restricted"] is True
        assert [p["id"] for p in spec["producers"]] == [
            "hook:enforcement/hooks/session_start.py"
        ]

    def test_the_resume_gate_demands_host_evidence(self, model: el.Model) -> None:
        resume = next(
            t
            for t in model.transitions
            if t["command"] == "resume" and t["from"] == "awaiting_clear"
        )
        assert resume["integrity"]["requires_attestation"] == "host"
        assert resume["boundary"] == "context-reset"

    def test_quiz_bank_generated_cannot_be_forged_or_empty(
        self, model: el.Model
    ) -> None:
        """Leaving recon bankless is unrecoverable, so the gate must be real."""
        spec = model.events["quiz_bank_generated"]
        assert spec["restricted"] is True
        counts = {
            f["name"]: f.get("pattern")
            for f in spec["fields"]
            if f["name"].endswith("_count")
        }
        assert counts == {
            "question_count": r"^[1-9]\d*$",
            "lens_count": r"^[1-9]\d*$",
        }

    def test_every_gate_consumed_event_is_declared(self, model: el.Model) -> None:
        unknown = {
            event
            for event in model.consumed
            if event not in model.events and event not in el.ENGINE_BUILTIN_EVENTS
        }
        assert unknown == set()
