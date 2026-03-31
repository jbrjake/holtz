"""Integration test: profile Run 14 session end-to-end.

Requires actual session JSONL at ~/.claude/projects/. Tests are skipped
on machines where the session file is not available. These tests validate
the full extraction→analysis→report pipeline against real session data.

BH-012: Machine-specific — depends on session file at a specific absolute
path. Always skipped on CI and other developer machines.
"""

import importlib.util
import json
import os
import tempfile
from pathlib import Path

import pytest
from token_profiler.analyze import build_run_profile, build_session_profile
from token_profiler.extract import discover_subagents, extract_session
from token_profiler.report import generate_markdown
from token_profiler.viewer import generate_html

# Mark all session-dependent tests as machine_specific
pytestmark = pytest.mark.machine_specific

# ---------------------------------------------------------------------------
# Session paths
# ---------------------------------------------------------------------------

# BH-014: configurable via env var so other developers can run with their data
SESSION_PATH = Path(
    os.environ.get(
        "HOLTZ_TEST_SESSION_JSONL",
        os.path.expanduser(
            "~/.claude/projects/-Users-jonr-Documents-non-nitro-repos-holtz/"
            "8ab6ac7a-eaaf-48e7-a6c5-9786f81887f5.jsonl"
        ),
    )
)
JUSTINE_SUBAGENT = "agent-a919e2838d64ac37a"

PLUGIN_PATH = Path(__file__).parent.parent / "skills" / "holtz" / "scripts" / "profiler_plugin.py"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def skip_if_no_session():
    if not SESSION_PATH.exists():
        pytest.skip("Run 14 session JSONL not available")


@pytest.fixture
def main_turns(skip_if_no_session):
    return extract_session(SESSION_PATH)


@pytest.fixture
def holtz_plugin():
    spec = importlib.util.spec_from_file_location("holtz_plugin", str(PLUGIN_PATH))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.HoltzProfilerPlugin()


# ---------------------------------------------------------------------------
# Test 1: extract main session
# ---------------------------------------------------------------------------


class TestExtractMainSession:
    def test_extract_main_session(self, main_turns):
        """Extracts turns, verifies count, first turn context, and model."""
        # Run 14 had 276 turns
        assert len(main_turns) >= 250, f"Expected >= 250 turns, got {len(main_turns)}"

        # First turn context_window ~31,707
        first_cw = main_turns[0].context_window
        assert abs(first_cw - 31707) <= 200, (
            f"First turn context_window expected ~31,707 (+/-200), got {first_cw}"
        )

        # Model is claude-opus-4-6
        assert main_turns[0].model == "claude-opus-4-6", (
            f"Expected model 'claude-opus-4-6', got {main_turns[0].model!r}"
        )


# ---------------------------------------------------------------------------
# Test 2: discover subagents
# ---------------------------------------------------------------------------


class TestDiscoverSubagents:
    def test_discover_subagents(self, skip_if_no_session):
        """Finds at least 3 subagent JSONLs."""
        subagent_paths = discover_subagents(SESSION_PATH)
        assert len(subagent_paths) >= 3, (
            f"Expected >= 3 subagent JSONLs, found {len(subagent_paths)}"
        )
        assert all(p.suffix == ".jsonl" for p in subagent_paths)


# ---------------------------------------------------------------------------
# Test 3: extract Justine subagent
# ---------------------------------------------------------------------------


class TestExtractJustine:
    def test_extract_justine(self, skip_if_no_session):
        """Extracts Justine subagent, verifies non-trivial turn count."""
        subagent_paths = discover_subagents(SESSION_PATH)
        justine_path = None
        for p in subagent_paths:
            if JUSTINE_SUBAGENT in p.stem:
                justine_path = p
                break
        assert justine_path is not None, (
            f"Justine subagent {JUSTINE_SUBAGENT} not found among "
            f"{[p.stem for p in subagent_paths]}"
        )

        justine_turns = extract_session(justine_path)
        # Justine had substantial activity (66 extracted turns)
        assert len(justine_turns) >= 50, (
            f"Expected >= 50 Justine turns, got {len(justine_turns)}"
        )

        # Verify content looks like Justine
        assert "justine" in justine_turns[0].assistant_text.lower(), (
            "First turn text should mention Justine"
        )


# ---------------------------------------------------------------------------
# Test 4: build main session profile
# ---------------------------------------------------------------------------


class TestBuildMainProfile:
    def test_build_main_profile(self, main_turns, holtz_plugin):
        """Builds SessionProfile, verifies summary metrics."""
        profile = build_session_profile(
            session_id="8ab6ac7a",
            raw_turns=main_turns,
            session_type="main",
            plugin=holtz_plugin,
        )

        assert profile.summary is not None

        # Total API calls >= 250 (Run 14 had 276)
        assert profile.summary.total_api_calls >= 250

        # No compaction events (Run 14 didn't compact)
        assert len(profile.compaction_events) == 0

        # Hottest turns should be non-empty
        assert len(profile.summary.hottest_turns) > 0

        # Peak context window > 200,000
        assert profile.summary.peak_context_window > 200_000, (
            f"Peak context {profile.summary.peak_context_window} should be > 200K"
        )


# ---------------------------------------------------------------------------
# Test 5: build run profile with subagents
# ---------------------------------------------------------------------------


class TestBuildRunProfileWithSubagents:
    def test_build_run_profile_with_subagents(self, main_turns, holtz_plugin, skip_if_no_session):
        """Builds full RunProfile with main + all subagents."""
        main_profile = build_session_profile(
            session_id="8ab6ac7a",
            raw_turns=main_turns,
            session_type="main",
            plugin=holtz_plugin,
        )

        all_sessions = [main_profile]
        subagent_paths = discover_subagents(SESSION_PATH)
        for sub_path in subagent_paths:
            sub_turns = extract_session(sub_path)
            sub_profile = build_session_profile(
                session_id=sub_path.stem,
                raw_turns=sub_turns,
                session_type="subagent",
                plugin=holtz_plugin,
            )
            all_sessions.append(sub_profile)

        run_profile = build_run_profile(run_id="run-14", sessions=all_sessions)

        # Multiple sessions in profile
        assert len(run_profile.sessions) > 1, (
            f"Expected multiple sessions, got {len(run_profile.sessions)}"
        )

        # cross_session_summary populated
        assert run_profile.cross_session_summary is not None
        css = run_profile.cross_session_summary
        assert css.total_billed_tokens > 0
        assert len(css.session_breakdown) == len(all_sessions)


# ---------------------------------------------------------------------------
# Test 6: Holtz plugin detects session
# ---------------------------------------------------------------------------


class TestHoltzPluginDetectsSession:
    def test_holtz_plugin_detects_session(self, main_turns, holtz_plugin):
        """Holtz plugin detects the Run 14 session."""
        assert holtz_plugin.detect(main_turns) is True


# ---------------------------------------------------------------------------
# Test 7: Holtz plugin labels steps
# ---------------------------------------------------------------------------


class TestHoltzPluginLabelsSteps:
    def test_holtz_plugin_labels_steps(self, main_turns, holtz_plugin):
        """Plugin labels include 'step-0-4' and at least 3 different steps."""
        labels = holtz_plugin.label_phases(main_turns)
        unique_steps = set(labels.values())

        assert "step-0-4" in unique_steps, (
            f"Expected 'step-0-4' in steps, got {sorted(unique_steps)}"
        )

        # At least 3 distinct steps (excluding 'unknown')
        non_unknown = {s for s in unique_steps if s != "unknown"}
        assert len(non_unknown) >= 3, (
            f"Expected >= 3 non-unknown steps, got {sorted(non_unknown)}"
        )


# ---------------------------------------------------------------------------
# Test 8: generate full output
# ---------------------------------------------------------------------------


class TestGenerateFullOutput:
    def test_generate_full_output(self, main_turns, holtz_plugin, skip_if_no_session):
        """Generates profile.json, profile.md, profile.html in a temp directory."""
        # Build the full run profile
        main_profile = build_session_profile(
            session_id="8ab6ac7a",
            raw_turns=main_turns,
            session_type="main",
            plugin=holtz_plugin,
        )

        all_sessions = [main_profile]
        subagent_paths = discover_subagents(SESSION_PATH)
        for sub_path in subagent_paths:
            sub_turns = extract_session(sub_path)
            sub_profile = build_session_profile(
                session_id=sub_path.stem,
                raw_turns=sub_turns,
                session_type="subagent",
                plugin=holtz_plugin,
            )
            all_sessions.append(sub_profile)

        run_profile = build_run_profile(run_id="run-14", sessions=all_sessions)

        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir)

            # Write profile.json
            from dataclasses import asdict

            profile_data = asdict(run_profile)
            json_path = out_dir / "profile.json"
            with open(json_path, "w") as f:
                json.dump(profile_data, f, indent=2, default=str)

            # Write profile.md
            md_content = generate_markdown(run_profile)
            md_path = out_dir / "profile.md"
            with open(md_path, "w") as f:
                f.write(md_content)

            # Write profile.html
            html_content = generate_html(run_profile)
            html_path = out_dir / "profile.html"
            with open(html_path, "w") as f:
                f.write(html_content)

            # All 3 files exist
            assert json_path.exists(), "profile.json was not created"
            assert md_path.exists(), "profile.md was not created"
            assert html_path.exists(), "profile.html was not created"

            # profile.json is valid JSON with sessions
            with open(json_path) as f:
                data = json.load(f)
            assert "sessions" in data, "profile.json missing 'sessions' key"
            assert len(data["sessions"]) > 1, "profile.json should have multiple sessions"

            # profile.md has required sections
            md_text = md_path.read_text()
            assert "## Summary" in md_text
            assert "## Heat Map" in md_text
            assert "## Phase Breakdown" in md_text
            assert "## Compaction Events" in md_text
            assert "## Methodology" in md_text

            # profile.html contains PROFILE_DATA
            html_text = html_path.read_text()
            assert "PROFILE_DATA" in html_text, "profile.html should contain PROFILE_DATA"
            assert len(html_text) > 1000, "profile.html seems too small"


# ---------------------------------------------------------------------------
# Test 9 (portable): full pipeline on synthetic JSONL — no external files
# ---------------------------------------------------------------------------


def _write_synthetic_session(path: Path) -> None:
    """Write a minimal but realistic synthetic session JSONL to *path*.

    Layout:
    - 3 assistant turns (each with 1 tool_use block + 1 text block)
    - 3 matching user turns (each with 1 tool_result block)
    - Context window grows realistically across turns

    Token counts are chosen so that all summary assertions fire:
      turn 0: input=10000, cache_read=5000  → cw=15000, output=200
      turn 1: input=14000, cache_read=6000  → cw=20000, output=300
      turn 2: input=20000, cache_read=8000  → cw=28000, output=400
    """
    records: list[dict] = []

    turns = [
        {
            "rid": "req-aaa-001",
            "input": 10000,
            "cache_creation": 0,
            "cache_read": 5000,
            "output": 200,
            "tool_id": "toolu_001",
            "tool_name": "Read",
            "tool_input": {"file_path": "/tmp/foo/bar.py"},
            "text": "I will read the file.",
            "ts": "2026-01-01T10:00:00Z",
        },
        {
            "rid": "req-bbb-002",
            "input": 14000,
            "cache_creation": 0,
            "cache_read": 6000,
            "output": 300,
            "tool_id": "toolu_002",
            "tool_name": "Bash",
            "tool_input": {"command": "ls /tmp", "description": "List tmp directory"},
            "text": "Running ls now.",
            "ts": "2026-01-01T10:01:00Z",
        },
        {
            "rid": "req-ccc-003",
            "input": 20000,
            "cache_creation": 0,
            "cache_read": 8000,
            "output": 400,
            "tool_id": "toolu_003",
            "tool_name": "Grep",
            "tool_input": {"pattern": "def \\w+", "path": "/tmp"},
            "text": "Searching for functions.",
            "ts": "2026-01-01T10:02:00Z",
        },
    ]

    tool_result_content = "x" * 2000  # 2 000 chars of fake output

    for _i, t in enumerate(turns):
        # Assistant record (single chunk per request — no streaming split needed)
        records.append({
            "type": "assistant",
            "requestId": t["rid"],
            "timestamp": t["ts"],
            "message": {
                "model": "claude-opus-4-6",
                "stop_reason": "tool_use",
                "usage": {
                    "input_tokens": t["input"],
                    "cache_creation_input_tokens": t["cache_creation"],
                    "cache_read_input_tokens": t["cache_read"],
                    "output_tokens": t["output"],
                },
                "content": [
                    {
                        "type": "text",
                        "text": t["text"],
                    },
                    {
                        "type": "tool_use",
                        "id": t["tool_id"],
                        "name": t["tool_name"],
                        "input": t["tool_input"],
                    },
                ],
            },
        })

        # User record (tool_result for the preceding assistant turn)
        records.append({
            "type": "user",
            "message": {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": t["tool_id"],
                        "is_error": False,
                        "content": tool_result_content,
                    }
                ],
            },
        })

    with open(path, "w") as fh:
        for rec in records:
            fh.write(json.dumps(rec) + "\n")


class TestPortableIntegration:
    """Full pipeline (extract → analyze → report) using only synthetic data.

    No external files required; runs on any machine.
    """

    def test_extract_yields_turns(self, tmp_path):
        """extract_session returns the expected number of RawTurn objects."""
        session_file = tmp_path / "synthetic.jsonl"
        _write_synthetic_session(session_file)

        turns = extract_session(session_file)

        assert len(turns) == 3, f"Expected 3 turns, got {len(turns)}"
        # Model propagated correctly
        assert turns[0].model == "claude-opus-4-6"
        # Each turn has a text block and a tool_use block → content_blocks >= 2
        for t in turns:
            assert len(t.content_blocks) >= 2

    def test_build_session_profile_non_zero_totals(self, tmp_path):
        """build_session_profile produces a non-zero summary from synthetic data."""
        session_file = tmp_path / "synthetic.jsonl"
        _write_synthetic_session(session_file)

        turns = extract_session(session_file)
        profile = build_session_profile(
            session_id="synthetic-001",
            raw_turns=turns,
            session_type="main",
        )

        assert profile.summary is not None
        assert profile.summary.total_api_calls == 3
        assert profile.summary.peak_context_window > 0, "peak_context_window must be > 0"
        assert profile.summary.total_output_tokens > 0, "total_output_tokens must be > 0"
        # session_cost > 0 because delta * remaining > 0 for at least first turn
        assert profile.summary.total_session_cost > 0, "total_session_cost must be > 0"
        assert len(profile.summary.hottest_turns) > 0

    def test_run_profile_has_sessions(self, tmp_path):
        """build_run_profile wraps the session in a RunProfile with valid cross-session summary."""
        session_file = tmp_path / "synthetic.jsonl"
        _write_synthetic_session(session_file)

        turns = extract_session(session_file)
        session_profile = build_session_profile(
            session_id="synthetic-001",
            raw_turns=turns,
            session_type="main",
        )
        run_profile = build_run_profile(run_id="synthetic-run", sessions=[session_profile])

        assert len(run_profile.sessions) == 1
        assert run_profile.cross_session_summary is not None
        assert run_profile.cross_session_summary.total_billed_tokens > 0

    def test_generate_markdown_has_required_sections(self, tmp_path):
        """generate_markdown produces output with all required section headers."""
        session_file = tmp_path / "synthetic.jsonl"
        _write_synthetic_session(session_file)

        turns = extract_session(session_file)
        session_profile = build_session_profile(
            session_id="synthetic-001",
            raw_turns=turns,
            session_type="main",
        )
        run_profile = build_run_profile(run_id="synthetic-run", sessions=[session_profile])

        md = generate_markdown(run_profile)

        required_sections = [
            "## Summary",
            "## Heat Map",
            "## Phase Breakdown",
            "## Compaction Events",
            "## Methodology",
        ]
        for section in required_sections:
            assert section in md, f"Markdown missing section: {section!r}"

    def test_full_pipeline_end_to_end(self, tmp_path):
        """Full pipeline: write JSONL → extract → profile → markdown, no external deps."""
        session_file = tmp_path / "synthetic.jsonl"
        _write_synthetic_session(session_file)

        # Stage 1: extract
        turns = extract_session(session_file)
        assert len(turns) == 3

        # Stage 2: build session profile
        session_profile = build_session_profile(
            session_id="synthetic-001",
            raw_turns=turns,
            session_type="main",
        )
        assert session_profile.summary is not None

        # Stage 3: build run profile
        run_profile = build_run_profile(run_id="synthetic-run", sessions=[session_profile])
        assert run_profile.cross_session_summary is not None

        # Stage 4: generate report
        md = generate_markdown(run_profile)

        # Write to tmp_path to exercise file I/O path
        report_path = tmp_path / "report.md"
        report_path.write_text(md)
        assert report_path.exists()

        # Summary totals are non-zero
        css = run_profile.cross_session_summary
        assert css.total_billed_tokens > 0
        assert css.total_session_cost_tokens > 0

        # Required sections present
        for section in ("## Summary", "## Heat Map", "## Phase Breakdown",
                        "## Compaction Events", "## Methodology"):
            assert section in md, f"Missing section: {section!r}"

        # No compaction events (monotonically increasing context window)
        assert session_profile.compaction_events == []

        # Tool results were paired — tool attributions exist on at least one turn
        turns_with_tool_attrs = [
            pt for pt in session_profile.turns
            if any(a.tool_name != "_assistant_overhead" for a in pt.tool_attributions)
        ]
        assert len(turns_with_tool_attrs) > 0, "Expected at least one turn with tool attributions"
