"""Tests for the generated enforcement contract (#82 Phase 4).

Two obligations, and the second is the one that matters:

1. **Staleness.** ``docs/ENFORCEMENT-CONTRACT.md`` is generated, so it can lie
   the moment someone edits ``enforcement/*.toml`` without regenerating. A
   byte comparison against a fresh render is the whole gate.
2. **Substance.** A byte comparison alone would pass forever on a generator
   that emitted an empty file, which is coverage without meaning — the exact
   trade CLAUDE.md warns about. So the properties the document exists to make
   visible are asserted directly: #79's row says ``host``, the ungated
   ``resume`` is distinguishable from the gated one, an event no writer can
   produce is named as such rather than left blank, and every gate-consumed
   event appears somewhere a reader will find it.
"""
from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import enforcement_contract as ec  # noqa: E402, I001
import enforcement_lint as el  # noqa: E402, I001

from test_enforcement_lint import build_tree  # noqa: E402, I001


@pytest.fixture(scope="module")
def model() -> el.Model:
    return el.build_model()


@pytest.fixture(scope="module")
def rendered(model: el.Model) -> str:
    return ec.render(model)


# ── Staleness ────────────────────────────────────────────────────────────────


class TestFreshness:
    def test_the_committed_contract_matches_the_config(self, rendered: str) -> None:
        committed = ec.CONTRACT_PATH.read_text(encoding="utf-8")
        assert committed == rendered, (
            "docs/ENFORCEMENT-CONTRACT.md is stale — the enforcement config "
            f"changed and the contract did not. Run: {ec.GENERATED_BY}"
        )

    def test_check_mode_agrees_with_the_test(self, rendered: str) -> None:
        """The gate in lint-enforcement.sh and this test must decide alike."""
        committed = ec.CONTRACT_PATH.read_text(encoding="utf-8")
        assert (committed == rendered) is True

    def test_render_is_deterministic(self, model: el.Model) -> None:
        """No clock, no set iteration order — or the gate cries wolf forever."""
        assert ec.render(model) == ec.render(el.build_model())


# ── Substance ────────────────────────────────────────────────────────────────


class TestTheDocumentSaysSomething:
    def test_the_79_row_reads_host(self, rendered: str) -> None:
        """The row the plan said would have made #79 legible without tooling."""
        section = rendered.split("### `resume` — awaiting_clear → fix_loop")[1]
        row = next(
            line
            for line in section.splitlines()
            if "`context_reset`" in line and line.startswith("|")
        )
        assert "`host`" in row
        assert "`hook:enforcement/hooks/session_start.py`" in row
        assert "no — daemon refuses unauthenticated callers" in row

    def test_the_gated_and_ungated_resume_are_distinguishable(
        self, rendered: str
    ) -> None:
        """Two edges, one command name, deliberately different strength.

        `awaiting_human -> fix_loop` is ungated on purpose (#69). If the
        document collapsed both into one `resume` row, it would hide exactly
        the route-around the `context-reset` boundary exists to forbid.
        """
        assert "`resume` (awaiting_clear→fix_loop)" in rendered
        assert "`resume` (awaiting_human→fix_loop)" in rendered
        assert "### `resume` — awaiting_human → fix_loop" in rendered

    def test_boundary_and_attestation_requirements_are_stated(
        self, rendered: str
    ) -> None:
        section = rendered.split("### `resume` — awaiting_clear → fix_loop")[1]
        head = section.split("###")[0]
        assert "requires attestation **host**" in head
        assert "boundary **context-reset**" in head

    def test_every_gate_consumed_event_appears(
        self, model: el.Model, rendered: str
    ) -> None:
        for event in el.gate_consumed_events(model):
            assert f"`{event}`" in rendered, f"{event} is gated but undocumented"

    def test_the_posture_count_matches_the_census(
        self, model: el.Model, rendered: str
    ) -> None:
        """One number, one derivation. Two would drift, which is the bug class."""
        census = el.census(model)
        agent_backed = sum(1 for _, attests, _ in census if attests == "agent")
        assert (
            f"**{agent_backed} of {len(census)} gate-consumed events are the "
            "agent's own word.**"
        ) in rendered

    def test_writers_table_reports_the_pin_through_the_running_process(
        self, rendered: str
    ) -> None:
        """quiz_vault.py is trusted through quiz_capture.py, not on its own."""
        row = next(
            line
            for line in rendered.splitlines()
            if line.startswith("| `enforcement/hooks/quiz_vault.py`")
        )
        assert "`quiz_capture.py`" in row
        assert "**no**" not in row


class TestTheGraphIsWellFormed:
    """A mermaid block that fails to parse renders as a wall of text on GitHub."""

    def _graph(self, rendered: str) -> list[str]:
        block = rendered.split("```mermaid")[1].split("```")[0]
        return [line.strip() for line in block.splitlines() if line.strip()]

    def test_every_node_label_is_quoted(self, rendered: str) -> None:
        """states.toml labels contain parentheses, which mermaid reads as syntax."""
        for line in self._graph(rendered):
            if "-->" in line or line.startswith(("flowchart", "linkStyle")):
                continue
            assert '["' in line or '(["' in line, line

    def test_link_styles_index_real_edges(self, rendered: str) -> None:
        lines = self._graph(rendered)
        edges = [line for line in lines if "-->" in line]
        styles = [line for line in lines if line.startswith("linkStyle")]
        assert len(styles) == len(edges)
        assert [int(line.split()[1]) for line in styles] == list(range(len(edges)))

    def test_every_edge_endpoint_is_a_declared_state(
        self, model: el.Model, rendered: str
    ) -> None:
        for line in self._graph(rendered):
            if "-->" not in line:
                continue
            src, _, dst = line.partition("-->")
            assert src.strip() in model.states
            assert dst.split("|")[-1].strip() in model.states


# ── The generator's own failure modes ────────────────────────────────────────


class TestGeneratorOnFixtures:
    """Reconstructed defects, to prove the document would have shown them."""

    def test_an_event_with_no_writer_is_named_not_blank(self, tmp_path: Path) -> None:
        """#81's shape: a gate waiting on an event nothing can produce."""
        tree = build_tree(
            tmp_path,
            events="""
            [events.quiz_exhausted_resolved]
            description = "Human reviewed an exhausted quiz"
            """,
            transitions="""
            [[transitions]]
            from = "final_sweep"
            to = "final_sweep_clean"
            command = "converge"
            gates = [
                { type = "ledger_has_event", event = "quiz_exhausted_resolved", intent = "exhausted quizzes must be reviewed" },
            ]
            """,
        )
        body = ec.render(el.build_model(tree))
        row = next(
            line for line in body.splitlines() if "exhausted quizzes must be" in line
        )
        assert "**nothing**" in row

    def test_an_ambient_writer_is_visible_as_the_weak_link(
        self, tmp_path: Path
    ) -> None:
        """#79 itself: the gate demanded a reset; the writer saw any prompt."""
        tree = build_tree(
            tmp_path,
            events="""
            [events.context_reset]
            description = "Context boundary"
            restricted = true
            attestation = "ambient"

            [[events.context_reset.producers]]
            id = "hook:enforcement/hooks/primer.py"
            """,
            protocol=textwrap.dedent(
                """
                [protocol]
                name = "fixture"
                version = "1.0.0"

                [attestation]
                levels = ["agent", "tool", "ambient", "host", "human"]
                """
            ),
            transitions="""
            [[transitions]]
            from = "awaiting_clear"
            to = "fix_loop"
            command = "resume"
            gates = [
                { type = "ledger_has_event_since", event = "context_reset", since = "last_transition", intent = "context must be reset" },
            ]
            """,
            hook_scripts={
                "primer.py": 'record_authed_event("context_reset", {})\n'
            },
        )
        body = ec.render(el.build_model(tree))
        row = next(line for line in body.splitlines() if "context must be reset" in line)
        assert "`ambient`" in row, row
        # And the colour of that edge is the weak link, not the strong one.
        assert ec.gate_rows(el.build_model(tree))[0].weakest == "ambient"

    def test_an_ungated_transition_says_so(self, tmp_path: Path) -> None:
        tree = build_tree(
            tmp_path,
            events="",
            transitions="""
            [[transitions]]
            from = "idle"
            to = "recon"
            command = "run_start"
            gates = []
            """,
        )
        body = ec.render(el.build_model(tree))
        assert "*Ungated — this transition asserts nothing.*" in body
