"""Tests for the Holtz profiler plugin (skills/holtz/scripts/profiler_plugin.py).

The plugin is loaded at runtime via importlib, so it must work as a standalone
file without importing from token_profiler.  We test it here by importing it
directly and feeding it RawTurn instances from the token_profiler models.
"""

from token_profiler.models import ContentBlock, RawTurn, Usage

from profiler_plugin import HoltzProfilerPlugin

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_turn(index: int, assistant_text: str) -> RawTurn:
    """Build a minimal RawTurn with the given assistant_text."""
    return RawTurn(
        request_id=f"req_{index:03d}",
        index=index,
        timestamp=f"2026-03-24T10:{index:02d}:00Z",
        usage=Usage(input_tokens=1000, output_tokens=200),
        stop_reason="end_turn",
        content_blocks=[ContentBlock(type="text", size=len(assistant_text), text_content=assistant_text)],
        tool_results=[],
        assistant_text=assistant_text,
    )


# ---------------------------------------------------------------------------
# detect
# ---------------------------------------------------------------------------


class TestDetect:
    """Tests for HoltzProfilerPlugin.detect()."""

    def test_detects_holtz_session(self):
        plugin = HoltzProfilerPlugin()
        turns = [_make_turn(0, "Running Holtz full audit on this codebase.")]
        assert plugin.detect(turns) is True

    def test_detects_step_0_reference(self):
        plugin = HoltzProfilerPlugin()
        turns = [_make_turn(0, "Starting step 0 reconnaissance.")]
        assert plugin.detect(turns) is True

    def test_detects_full_audit_reference(self):
        plugin = HoltzProfilerPlugin()
        turns = [_make_turn(0, "I'll begin the full audit now.")]
        assert plugin.detect(turns) is True

    def test_rejects_non_holtz_session(self):
        plugin = HoltzProfilerPlugin()
        turns = [
            _make_turn(0, "Let me help you write a function."),
            _make_turn(1, "Here is the implementation."),
        ]
        assert plugin.detect(turns) is False

    def test_detects_within_first_10_turns(self):
        plugin = HoltzProfilerPlugin()
        turns = [_make_turn(i, "unrelated text") for i in range(9)]
        turns.append(_make_turn(9, "This is a holtz audit session."))
        assert plugin.detect(turns) is True

    def test_ignores_holtz_after_turn_10(self):
        plugin = HoltzProfilerPlugin()
        turns = [_make_turn(i, "unrelated text") for i in range(11)]
        turns.append(_make_turn(11, "holtz is mentioned here."))
        assert plugin.detect(turns) is False

    def test_empty_turns(self):
        plugin = HoltzProfilerPlugin()
        assert plugin.detect([]) is False


# ---------------------------------------------------------------------------
# label_phases
# ---------------------------------------------------------------------------


class TestLabelPhases:
    """Tests for HoltzProfilerPlugin.label_phases()."""

    def test_full_step_progression(self):
        """All 7 step groups detected in order, with correct inheritance."""
        plugin = HoltzProfilerPlugin()
        turns = [
            _make_turn(0, "Starting Step 0 reconnaissance of the repo."),
            _make_turn(1, "Reading config files."),  # inherits step-0-4
            _make_turn(2, "Now entering Step 6 Doc Audit of all claims."),
            _make_turn(3, "Step 7 Test Quality review begins."),
            _make_turn(4, "Step 8 Adversarial Code review starts."),
            _make_turn(5, "Step 9 Merging: classify Justine findings now."),
            _make_turn(6, "Step 10 TDD fix loop begins."),
            _make_turn(7, "Writing a failing test."),  # inherits step-10
            _make_turn(8, "convergence check, writing SUMMARY.md"),
        ]
        result = plugin.label_phases(turns)

        assert result[0] == "step-0-4"
        assert result[1] == "step-0-4"  # inherited
        assert result[2] == "step-6"
        assert result[3] == "step-7"
        assert result[4] == "step-8"
        assert result[5] == "step-9"
        assert result[6] == "step-10"
        assert result[7] == "step-10"  # inherited
        assert result[8] == "step-14-15"

    def test_all_turns_get_labels(self):
        """Every turn index gets a label, even those before any step is detected."""
        plugin = HoltzProfilerPlugin()
        turns = [
            _make_turn(0, "Just starting up."),
            _make_turn(1, "Step 0 recon begins."),
            _make_turn(2, "Continuing the work."),
        ]
        result = plugin.label_phases(turns)
        # Turn 0 has no step marker, should get "unknown" or similar default
        assert 0 in result
        assert 1 in result
        assert 2 in result
        assert result[1] == "step-0-4"
        assert result[2] == "step-0-4"  # inherited from turn 1

    def test_step_detected_by_regex_patterns(self):
        """Regex patterns match various phrasings."""
        plugin = HoltzProfilerPlugin()
        turns = [
            _make_turn(0, "Starting recon-procedures scan."),
            _make_turn(1, "I'll examine each doc claim in detail."),
            _make_turn(2, "Test Audit of the test suite quality."),
            _make_turn(3, "Adversarial Audit of source modules."),
            _make_turn(4, "Classify findings from all phases."),
            _make_turn(5, "Creating a failing test for the bug."),
            _make_turn(6, "Final commit and convergence achieved."),
        ]
        result = plugin.label_phases(turns)
        assert result[0] == "step-0-4"
        assert result[1] == "step-6"
        assert result[2] == "step-7"
        assert result[3] == "step-8"
        assert result[4] == "step-9"
        assert result[5] == "step-10"
        assert result[6] == "step-14-15"

    def test_empty_turns(self):
        plugin = HoltzProfilerPlugin()
        assert plugin.label_phases([]) == {}


# ---------------------------------------------------------------------------
# name_subagent
# ---------------------------------------------------------------------------


class TestNameSubagent:
    """Tests for HoltzProfilerPlugin.name_subagent()."""

    def test_justine(self):
        plugin = HoltzProfilerPlugin()
        turns = [_make_turn(0, "Running Justine [initialization] on holtz codebase.")]
        assert plugin.name_subagent(turns) == "justine"

    def test_test_audit(self):
        plugin = HoltzProfilerPlugin()
        turns = [_make_turn(0, "I'll read all four test files in parallel to start the audit.")]
        assert plugin.name_subagent(turns) == "test-audit"

    def test_test_audit_alternative(self):
        plugin = HoltzProfilerPlugin()
        turns = [_make_turn(0, "Reviewing test files for audit completeness.")]
        assert plugin.name_subagent(turns) == "test-audit"

    def test_source_audit(self):
        plugin = HoltzProfilerPlugin()
        turns = [_make_turn(0, "I will analyze source modules for subtle bugs.")]
        assert plugin.name_subagent(turns) == "source-audit"

    def test_source_audit_subtle_bugs(self):
        plugin = HoltzProfilerPlugin()
        turns = [_make_turn(0, "Looking for subtle bugs in the implementation.")]
        assert plugin.name_subagent(turns) == "source-audit"

    def test_unknown_subagent(self):
        plugin = HoltzProfilerPlugin()
        turns = [_make_turn(0, "Hello, I am ready to help.")]
        assert plugin.name_subagent(turns) is None

    def test_empty_turns(self):
        plugin = HoltzProfilerPlugin()
        assert plugin.name_subagent([]) is None


# ---------------------------------------------------------------------------
# optimization_patterns
# ---------------------------------------------------------------------------


class TestOptimizationPatterns:
    """Tests for HoltzProfilerPlugin.optimization_patterns()."""

    def test_returns_four_patterns(self):
        plugin = HoltzProfilerPlugin()
        patterns = plugin.optimization_patterns()
        assert len(patterns) == 4

    def test_pattern_keys(self):
        plugin = HoltzProfilerPlugin()
        patterns = plugin.optimization_patterns()
        for pat in patterns:
            assert "name" in pat
            assert "symptom" in pat
            assert "fix" in pat

    def test_pattern_names(self):
        plugin = HoltzProfilerPlugin()
        patterns = plugin.optimization_patterns()
        names = {p["name"] for p in patterns}
        assert names == {
            "Heavy Early Read",
            "Recon Bloat",
            "Chatty Tool Loop",
            "Subagent Over-delegation",
        }


# ---------------------------------------------------------------------------
# enrich_profile (no-op for now)
# ---------------------------------------------------------------------------


class TestEnrichProfile:
    """Tests for HoltzProfilerPlugin.enrich_profile()."""

    def test_enrich_is_noop(self):
        plugin = HoltzProfilerPlugin()
        # Should accept any argument and do nothing
        result = plugin.enrich_profile(None)
        assert result is None


# ---------------------------------------------------------------------------
# Plugin protocol compliance
# ---------------------------------------------------------------------------


class TestProtocolCompliance:
    """Verify HoltzProfilerPlugin satisfies the structural protocol."""

    def test_has_name_attribute(self):
        plugin = HoltzProfilerPlugin()
        assert hasattr(plugin, "name")
        assert isinstance(plugin.name, str)
        assert plugin.name == "holtz"

    def test_has_all_required_methods(self):
        plugin = HoltzProfilerPlugin()
        required = ["detect", "label_phases", "name_subagent", "enrich_profile", "optimization_patterns"]
        for method_name in required:
            assert hasattr(plugin, method_name)
            assert callable(getattr(plugin, method_name))
