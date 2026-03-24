"""Integration test: profile Run 14 session end-to-end.

Requires actual session JSONL at ~/.claude/projects/. Skip if not available.
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

# ---------------------------------------------------------------------------
# Session paths
# ---------------------------------------------------------------------------

SESSION_PATH = Path(
    os.path.expanduser(
        "~/.claude/projects/-Users-jonr-Documents-non-nitro-repos-holtz/"
        "8ab6ac7a-eaaf-48e7-a6c5-9786f81887f5.jsonl"
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
# Test 7: Holtz plugin labels phases
# ---------------------------------------------------------------------------


class TestHoltzPluginLabelsPhases:
    def test_holtz_plugin_labels_phases(self, main_turns, holtz_plugin):
        """Plugin labels include 'recon' and at least 3 different phases."""
        labels = holtz_plugin.label_phases(main_turns)
        unique_phases = set(labels.values())

        assert "recon" in unique_phases, (
            f"Expected 'recon' in phases, got {sorted(unique_phases)}"
        )

        # At least 3 distinct phases (excluding 'unknown')
        non_unknown = {p for p in unique_phases if p != "unknown"}
        assert len(non_unknown) >= 3, (
            f"Expected >= 3 non-unknown phases, got {sorted(non_unknown)}"
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
