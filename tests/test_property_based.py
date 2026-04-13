"""Property-based tests — systematic edge case exploration via hypothesis.

Tests that parsers never crash on arbitrary input and that security-critical
invariants hold under generated inputs.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from hypothesis import given, settings, strategies as st

# Add enforcement/hooks to path for direct import
REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT / "enforcement" / "hooks"))

from _sahjhan_bootstrap import (  # noqa: E402
    ALL_PROTECTED,
    _check_bash_write,
    _extract_sahjhan_subcmd,
)

pytestmark = pytest.mark.slow


# ---------------------------------------------------------------------------
# 1a: _extract_sahjhan_subcmd — never crashes on arbitrary input
# ---------------------------------------------------------------------------


class TestExtractSahjhanSubcmdProperties:
    """Property-based tests for _extract_sahjhan_subcmd parser."""

    @given(st.text(min_size=0, max_size=200))
    @settings(max_examples=50)
    def test_never_crashes_on_arbitrary_input(self, segment: str):
        """Parser must never crash on arbitrary input."""
        result = _extract_sahjhan_subcmd(segment)
        assert result is None or (
            isinstance(result, tuple)
            and len(result) == 2
            and isinstance(result[0], str)
            and isinstance(result[1], str)
        )

    @given(
        subcmd=st.sampled_from(["status", "init", "event", "transition",
                                 "daemon", "reset", "gate", "render",
                                 "manifest", "ledger", "set", "defer"]),
        flags=st.lists(
            st.sampled_from(["--verbose", "--json", "--config-dir /tmp/cfg",
                              "-c /path", "--help", "-h"]),
            max_size=2,
        ),
        redirect=st.sampled_from(["", " 2>&1", " >/dev/null", " 2>/dev/null",
                                    " > /tmp/out.log"]),
        wrapper=st.sampled_from(["", "nohup ", "env "]),
        env_prefix=st.sampled_from(["", "FOO=bar ", "A=1 B=2 "]),
    )
    @settings(max_examples=50)
    def test_structured_input_extracts_or_returns_none(
        self, subcmd, flags, redirect, wrapper, env_prefix
    ):
        """Structured sahjhan-like inputs extract correctly or return None."""
        flag_str = " ".join(flags)
        segment = f"{env_prefix}{wrapper}sahjhan {flag_str} {subcmd}{redirect}"
        result = _extract_sahjhan_subcmd(segment)

        if "--help" in flags or "-h" in flags:
            # --help/--version bypass enforcement → return None
            assert result is None, \
                f"--help/--version should return None, got {result} for: {segment}"
        elif result is not None:
            assert result[0] == subcmd, \
                f"Expected subcmd '{subcmd}', got '{result[0]}' for: {segment}"

    @given(
        cmd=st.sampled_from(["git", "ls", "cat", "echo", "python", "npm"]),
        args=st.text(min_size=0, max_size=50),
    )
    @settings(max_examples=50)
    def test_non_sahjhan_commands_return_none(self, cmd, args):
        """Non-sahjhan commands always return None."""
        segment = f"{cmd} {args}"
        result = _extract_sahjhan_subcmd(segment)
        assert result is None, \
            f"Non-sahjhan command should return None: {segment} → {result}"

    @given(
        sub_subcmd=st.sampled_from(["start", "stop", "status", "create",
                                      "checkpoint", "check"]),
    )
    @settings(max_examples=50)
    def test_daemon_sub_subcommand_extraction(self, sub_subcmd):
        """sahjhan daemon <sub> correctly extracts both levels."""
        result = _extract_sahjhan_subcmd(f"sahjhan daemon {sub_subcmd}")
        assert result == ("daemon", sub_subcmd)


# ---------------------------------------------------------------------------
# 1b: _check_bash_write — write to protected path always blocked
# ---------------------------------------------------------------------------


class TestCheckBashWriteProperties:
    """Property-based tests for write protection enforcement."""

    @given(
        cmd=st.sampled_from(["cp", "mv"]),
        protected=st.sampled_from(ALL_PROTECTED),
        source=st.sampled_from(["foo.txt", "/tmp/src", "bar.py"]),
    )
    @settings(max_examples=50)
    def test_cp_mv_to_protected_always_blocked(self, cmd, protected, source):
        """cp/mv to a protected path must always be blocked."""
        command = f"{cmd} {source} {protected}"
        result = _check_bash_write(command)
        assert result is not None, \
            f"{cmd} to {protected} should be blocked: {command}"
        assert "BLOCKED" in result

    @given(
        protected=st.sampled_from(ALL_PROTECTED),
        op=st.sampled_from([">", ">>"]),
        prefix=st.sampled_from(["echo hello", "cat foo", "printf 'x'"]),
    )
    @settings(max_examples=50)
    def test_redirect_to_protected_always_blocked(self, protected, op, prefix):
        """Shell redirect to a protected path must always be blocked."""
        command = f"{prefix} {op} {protected}"
        result = _check_bash_write(command)
        assert result is not None, \
            f"Redirect to {protected} should be blocked: {command}"
        assert "BLOCKED" in result

    @given(
        protected=st.sampled_from(ALL_PROTECTED),
        prefix=st.sampled_from(["echo hello | ", "cat foo | ", ""]),
    )
    @settings(max_examples=50)
    def test_tee_to_protected_always_blocked(self, protected, prefix):
        """tee to a protected path must always be blocked."""
        command = f"{prefix}tee {protected}"
        result = _check_bash_write(command)
        assert result is not None, \
            f"tee to {protected} should be blocked: {command}"
        assert "BLOCKED" in result

    @given(
        protected=st.sampled_from(
            [p for p in ALL_PROTECTED if p.endswith("/")]
        ),
        flags=st.sampled_from(["", "-rf", "-r", "-f"]),
    )
    @settings(max_examples=50)
    def test_rm_of_protected_dir_always_blocked(self, protected, flags):
        """rm of a protected directory must always be blocked."""
        command = f"rm {flags} {protected}" if flags else f"rm {protected}"
        result = _check_bash_write(command)
        assert result is not None, \
            f"rm of {protected} should be blocked: {command}"
        assert "BLOCKED" in result

    @given(st.text(min_size=0, max_size=200))
    @settings(max_examples=50)
    def test_never_crashes_on_arbitrary_input(self, command: str):
        """Write checker must never crash on arbitrary input."""
        result = _check_bash_write(command)
        assert result is None or isinstance(result, str)

    @given(
        cmd=st.sampled_from(["echo hello", "ls -la", "git status",
                              "python -m pytest", "cat README.md"]),
    )
    @settings(max_examples=50)
    def test_safe_commands_allowed(self, cmd):
        """Commands that don't write to protected paths are allowed."""
        result = _check_bash_write(cmd)
        assert result is None, \
            f"Safe command should be allowed: {cmd} → {result}"


# ---------------------------------------------------------------------------
# 1c: Punchlist parser — never crashes on varied markdown
# ---------------------------------------------------------------------------

import validate_punchlist as vp  # noqa: E402


class TestPunchlistParserProperties:
    """Property-based tests for punchlist markdown parser."""

    @given(st.text(min_size=0, max_size=500))
    @settings(max_examples=50)
    def test_parse_never_crashes(self, content: str):
        """Parser must never crash on arbitrary markdown."""
        try:
            result = vp.parse_punchlist(content)
            assert isinstance(result, list)
            for item in result:
                assert isinstance(item, vp.PunchlistItem)
        except Exception as e:
            # Only SystemExit and KeyboardInterrupt should propagate
            if isinstance(e, (SystemExit, KeyboardInterrupt)):
                raise
            pytest.fail(f"Parser crashed on input: {e}")

    @given(
        item_id=st.from_regex(r"BH-\d{3}", fullmatch=True),
        title=st.text(min_size=1, max_size=50).filter(lambda t: "\n" not in t),
        severity=st.sampled_from(list(vp.VALID_SEVERITIES)),
        status=st.sampled_from(list(vp.VALID_STATUSES)),
    )
    @settings(max_examples=50)
    def test_valid_items_parse_correctly(self, item_id, title, severity, status):
        """Well-formed items produce exactly one parsed item."""
        content = (
            f"### {item_id}: {title}\n"
            f"**Severity:** {severity}\n"
            f"**Category:** bug/logic\n"
            f"**Location:** `file.py:1`\n"
            f"**Status:** {status}\n\n"
            f"**Problem:** This is a problem.\n\n"
            f"**Evidence:** Here is evidence.\n\n"
            f"**Discovery Chain:** observed → caused\n\n"
            f"**Acceptance Criteria:**\n- [ ] Fix it\n\n"
            f"**Validation Command:**\n```bash\necho test\n```\n"
        )
        items = vp.parse_punchlist(content)
        assert len(items) == 1
        item = items[0]
        assert item.id == item_id
        assert item.severity == severity
        assert item.status == status


# ---------------------------------------------------------------------------
# 1d: Convergence check — item count consistency
# ---------------------------------------------------------------------------

import convergence_check as cc  # noqa: E402


class TestConvergenceCountProperties:
    """Property-based tests for convergence item counting."""

    @given(
        open_count=st.integers(min_value=0, max_value=5),
        resolved_count=st.integers(min_value=0, max_value=5),
        deferred_count=st.integers(min_value=0, max_value=3),
    )
    @settings(max_examples=50)
    def test_total_equals_sum_of_statuses(
        self, open_count, resolved_count, deferred_count
    ):
        """Total count must equal sum of individual status counts."""
        import tempfile
        items = []
        for i in range(open_count):
            items.append(f"### BH-{i:03d}: Open item {i}\n**Status:** OPEN\n")
        for i in range(resolved_count):
            j = open_count + i
            items.append(f"### BH-{j:03d}: Resolved {i}\n**Status:** RESOLVED\n")
        for i in range(deferred_count):
            j = open_count + resolved_count + i
            items.append(f"### BH-{j:03d}: Deferred {i}\n**Status:** DEFERRED\n")

        with tempfile.TemporaryDirectory() as td:
            punchlist = Path(td) / "PUNCHLIST.md"
            punchlist.write_text("\n".join(items) if items else "# Empty\n")

            if not items:
                counts = cc.count_items(punchlist)
                assert counts["total"] == 0
                return

            counts = cc.count_items(punchlist)
            assert counts["OPEN"] == open_count
            assert counts["RESOLVED"] == resolved_count
            assert counts["DEFERRED"] == deferred_count
            assert counts["total"] == open_count + resolved_count + deferred_count

    @given(
        open_count=st.integers(min_value=0, max_value=5),
        resolved_count=st.integers(min_value=0, max_value=5),
    )
    @settings(max_examples=50)
    def test_convergence_reachable_when_no_open_items(
        self, open_count, resolved_count
    ):
        """If zero open items remain, convergence should be reachable."""
        import tempfile
        items = []
        for i in range(open_count):
            items.append(f"### BH-{i:03d}: Open {i}\n**Status:** OPEN\n")
        for i in range(resolved_count):
            j = open_count + i
            items.append(f"### BH-{j:03d}: Resolved {i}\n**Status:** RESOLVED\n")

        with tempfile.TemporaryDirectory() as td:
            punchlist = Path(td) / "PUNCHLIST.md"
            punchlist.write_text("\n".join(items) if items else "# Empty\n")

            counts = cc.count_items(punchlist)
            if open_count == 0:
                assert counts["OPEN"] == 0, "No open items means convergence is reachable"
            else:
                assert counts["OPEN"] > 0, "Open items remain — convergence not yet reached"
