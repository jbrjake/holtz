"""Adversarial review: tests exposing real bugs found through code analysis.

Each test documents a specific bug with root cause analysis and demonstrates
the failure before the fix is applied.
"""
from __future__ import annotations

import importlib.util
import os
import sys
import textwrap
from pathlib import Path
from types import ModuleType

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_ENFORCEMENT_HOOKS = Path(REPO_ROOT) / "enforcement" / "hooks"

sys.path.insert(0, os.path.join(REPO_ROOT, "enforcement", "hooks"))


# ── Module loading helpers ──


def _load_module(name: str, path: Path) -> ModuleType:
    """Load a module from an absolute path using importlib."""
    spec = importlib.util.spec_from_file_location(name, str(path))
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_with_enforcement_deps(module_name: str, filename: str) -> ModuleType:
    """Load an enforcement hook module with proper sibling dependencies.

    Temporarily injects enforcement _common, _resolve, _protocol_cache into
    sys.modules so the target module's imports resolve correctly.
    """
    saved: dict[str, object] = {}

    # Load and inject enforcement _common
    saved["_common"] = sys.modules.get("_common")
    common = _load_module("_common_adv", _ENFORCEMENT_HOOKS / "_common.py")
    sys.modules["_common"] = common

    # Load and inject _resolve
    saved["_resolve"] = sys.modules.get("_resolve")
    resolve = _load_module("_resolve_adv", _ENFORCEMENT_HOOKS / "_resolve.py")
    sys.modules["_resolve"] = resolve

    # Load and inject _protocol_cache
    saved["_protocol_cache"] = sys.modules.get("_protocol_cache")
    pcache = _load_module("_protocol_cache_adv", _ENFORCEMENT_HOOKS / "_protocol_cache.py")
    sys.modules["_protocol_cache"] = pcache

    # Load and inject lens_evidence (needed by lens_quiz)
    saved["lens_evidence"] = sys.modules.get("lens_evidence")
    evidence_path = _ENFORCEMENT_HOOKS / "lens_evidence.py"
    if evidence_path.exists():
        evidence = _load_module("lens_evidence_adv", evidence_path)
        sys.modules["lens_evidence"] = evidence

    try:
        mod = _load_module(
            f"{module_name}_adv_review",
            _ENFORCEMENT_HOOKS / filename,
        )
        return mod
    finally:
        for mod_name, original in saved.items():
            if original is None:
                sys.modules.pop(mod_name, None)
            else:
                sys.modules[mod_name] = original  # type: ignore[assignment]


# ═══════════════════════════════════════════════════════════════════════
# Bug 1: _split_shell_segments fails on quoted env var values with spaces
#
# Root cause: The env-var stripping regex uses \w+=\S* which stops at
# the first space inside a quoted value. FOO="bar baz" gets partially
# stripped to 'baz" <rest>', corrupting the segment.
#
# Impact: is_git_commit and is_sahjhan_cmd fail to recognize commands
# that follow a quoted env var with spaces, creating an enforcement
# bypass in commit_gate and protocol_tracker.
# ═══════════════════════════════════════════════════════════════════════


class TestSplitShellSegmentsQuotedEnvVars:
    """_split_shell_segments must handle quoted env var values with spaces."""

    def test_double_quoted_env_var_value_with_spaces(self):
        """FOO="bar baz" sahjhan status → segment should be 'sahjhan status'."""
        from _protocol_cache import _split_shell_segments
        segments = _split_shell_segments('FOO="bar baz" sahjhan status')
        assert len(segments) == 1
        assert segments[0].startswith("sahjhan"), (
            f"Quoted env var with spaces corrupted segment: {segments[0]!r}"
        )

    def test_single_quoted_env_var_value_with_spaces(self):
        """FOO='bar baz' git commit -m 'fix' → segment should start with 'git'."""
        from _protocol_cache import _split_shell_segments
        segments = _split_shell_segments("FOO='bar baz' git commit -m 'fix: thing'")
        assert len(segments) == 1
        assert segments[0].startswith("git"), (
            f"Single-quoted env var with spaces corrupted segment: {segments[0]!r}"
        )

    def test_export_quoted_env_var(self):
        """export FOO="bar baz" && git commit → git commit segment preserved."""
        from _protocol_cache import _split_shell_segments
        segments = _split_shell_segments('export FOO="bar baz" && git commit -m "fix: x"')
        # Should have git commit as one of the segments
        has_git = any(s.startswith("git") for s in segments)
        assert has_git, (
            f"Quoted export broke segment parsing: {segments!r}"
        )


class TestIsGitCommitQuotedEnvVarBypass:
    """is_git_commit must detect commits after quoted env var assignments."""

    def test_double_quoted_env_var_bypass(self):
        """FOO="bar baz" git commit -m "fix" IS a real git commit."""
        from _protocol_cache import is_git_commit
        assert is_git_commit('FOO="bar baz" git commit -m "fix: thing"'), (
            "Quoted env var with spaces allowed git commit to bypass detection"
        )

    def test_single_quoted_env_var_bypass(self):
        """MSG='hello world' git commit -m "$MSG" IS a real git commit."""
        from _protocol_cache import is_git_commit
        assert is_git_commit("MSG='hello world' git commit -m 'fix: thing'"), (
            "Single-quoted env var with spaces allowed git commit to bypass detection"
        )


class TestIsSahjhanCmdQuotedEnvVarBypass:
    """is_sahjhan_cmd must detect sahjhan after quoted env var assignments."""

    def test_double_quoted_env_var(self):
        """FOO="bar baz" sahjhan status is a sahjhan command."""
        from _protocol_cache import is_sahjhan_cmd
        assert is_sahjhan_cmd('FOO="bar baz" sahjhan status'), (
            "Quoted env var with spaces broke sahjhan command detection"
        )


# ═══════════════════════════════════════════════════════════════════════
# Bug 5: Newline-separated commands bypass commit gate and protocol tracking
#
# Root cause: _split_shell_segments, _is_tdd_cmd, _is_test_cmd, and
# _is_sleep_cmd split on &&, ||, ;, | but NOT on \n (newline).
# However, _sahjhan_bootstrap.py DOES split on \n. This dual-parser
# divergence means "echo\ngit commit" bypasses commit_gate while
# "echo\nrm enforcement/foo.py" is correctly blocked by bootstrap.
#
# Impact: Newline-separated git commits bypass the commit gate entirely.
# The commit happens but is invisible to enforcement tracking.
# ═══════════════════════════════════════════════════════════════════════


class TestNewlineSeparatedCommandBypass:
    """Commands separated by newlines must be detected, not treated as one segment."""

    def test_newline_git_commit_detected(self):
        """echo hello\\ngit commit -m 'fix: x' IS a git commit."""
        from _protocol_cache import is_git_commit
        assert is_git_commit("echo hello\ngit commit -m 'fix: x'"), (
            "Newline-separated git commit was not detected — commit gate bypassed"
        )

    def test_newline_sahjhan_detected(self):
        """echo hello\\nsahjhan status — contains a non-sahjhan segment."""
        from _protocol_cache import is_sahjhan_cmd
        # The whole command is NOT exclusively sahjhan (echo is non-sahjhan)
        assert not is_sahjhan_cmd("echo hello\nsahjhan status"), (
            "Mixed newline command should not be classified as pure sahjhan"
        )

    def test_newline_tdd_cmd_detected(self):
        """echo hello\\npytest IS a TDD command."""
        tracker = _load_with_enforcement_deps("protocol_tracker", "protocol_tracker.py")
        assert tracker._is_tdd_cmd("echo hello\npytest"), (
            "Newline-separated pytest was not detected as TDD"
        )

    def test_newline_sleep_detected(self):
        """echo hello\\nsleep 60 IS a sleep command."""
        tracker = _load_with_enforcement_deps("protocol_tracker", "protocol_tracker.py")
        assert tracker._is_sleep_cmd("echo hello\nsleep 60"), (
            "Newline-separated sleep was not detected"
        )


# ═══════════════════════════════════════════════════════════════════════
# Bug 2: _is_tdd_cmd doesn't handle chained commands
#
# Root cause: _is_tdd_cmd checks cmd.strip().startswith("pytest") etc.
# on the FULL command string. A chained command like "cd /foo && pytest"
# starts with "cd", not "pytest", so it's not recognized.
#
# Impact: Legitimate TDD commands chained with cd or other prefixes
# incorrectly increment the stall counter in protocol_tracker.
# ═══════════════════════════════════════════════════════════════════════


class TestIsTddCmdChainedCommands:
    """_is_tdd_cmd must recognize test commands in chained shell commands."""

    @staticmethod
    def _load_is_tdd_cmd():
        tracker = _load_with_enforcement_deps("protocol_tracker", "protocol_tracker.py")
        return tracker._is_tdd_cmd

    def test_cd_then_pytest(self):
        """cd /project && python -m pytest is a TDD command."""
        _is_tdd_cmd = self._load_is_tdd_cmd()
        assert _is_tdd_cmd("cd /project && python -m pytest"), (
            "Chained cd + pytest not recognized as TDD — stall counter incorrectly incremented"
        )

    def test_cd_then_ruff(self):
        """cd /project && ruff check . is a TDD command."""
        _is_tdd_cmd = self._load_is_tdd_cmd()
        assert _is_tdd_cmd("cd /project && ruff check ."), (
            "Chained cd + ruff not recognized as TDD"
        )

    def test_cd_then_mypy(self):
        """cd /project && mypy src/ is a TDD command."""
        _is_tdd_cmd = self._load_is_tdd_cmd()
        assert _is_tdd_cmd("cd /project && mypy src/"), (
            "Chained cd + mypy not recognized as TDD"
        )

    def test_git_add_then_pytest(self):
        """git add . && python -m pytest is a TDD command."""
        _is_tdd_cmd = self._load_is_tdd_cmd()
        assert _is_tdd_cmd("git add . && python -m pytest --tb=short"), (
            "Chained git add + pytest not recognized as TDD"
        )


# ═══════════════════════════════════════════════════════════════════════
# Bug 3: _is_test_cmd in commit_gate.py doesn't handle chained commands
#
# Root cause: Same as Bug 2 — checks cmd.strip().startswith("pytest")
# on the full string, missing chained commands.
#
# Impact: Test commands chained with cd/other prefixes may be blocked
# by the commit gate when protocol obligations exist, even though
# test commands should always be allowed.
# ═══════════════════════════════════════════════════════════════════════


class TestIsTestCmdChainedCommands:
    """_is_test_cmd in commit_gate must recognize chained test commands."""

    @staticmethod
    def _load_is_test_cmd():
        gate = _load_with_enforcement_deps("commit_gate", "commit_gate.py")
        return gate._is_test_cmd

    def test_cd_then_pytest(self):
        """cd /project && pytest is a test command."""
        _is_test_cmd = self._load_is_test_cmd()
        assert _is_test_cmd("cd /project && pytest"), (
            "Chained cd + pytest not recognized — test command may be blocked by commit gate"
        )

    def test_cd_then_python_m_pytest(self):
        """cd /project && python -m pytest is a test command."""
        _is_test_cmd = self._load_is_test_cmd()
        assert _is_test_cmd("cd /project && python -m pytest --tb=short"), (
            "Chained cd + python -m pytest not recognized"
        )


# ═══════════════════════════════════════════════════════════════════════
# Bug 4: _extract_symbol_body doesn't handle async def methods
#
# Root cause: The method pattern regex is ^\s+def\s+{method_name}\b
# which requires literal "def" after whitespace. An async method like
# "    async def bar(self):" has "async" before "def", so the regex
# doesn't match, and verify_answer_freshness returns False (stale).
#
# Impact: Quiz questions referencing async methods are falsely dropped
# as stale, reducing quiz difficulty and potentially allowing subagents
# to pass with less real knowledge.
# ═══════════════════════════════════════════════════════════════════════


class TestExtractSymbolBodyAsyncDef:
    """_extract_symbol_body must handle async def methods."""

    @staticmethod
    def _get_extract():
        mod = _load_with_enforcement_deps("lens_quiz", "lens_quiz.py")
        return mod._extract_symbol_body

    def test_async_method_found(self):
        """async def method inside a class should be found via Class.method lookup."""
        extract = self._get_extract()
        source = textwrap.dedent("""\
            class MyService:
                def sync_method(self):
                    return 1

                async def fetch_data(self, url):
                    response = await self.client.get(url)
                    return response.json()

                def other_method(self):
                    return 2
        """)
        body = extract(source, "MyService.fetch_data")
        assert body is not None, (
            "async def method not found — quiz freshness check will falsely mark as stale"
        )
        assert "await" in body
        assert "response.json()" in body

    def test_async_toplevel_function(self):
        """Top-level async def function should be found."""
        extract = self._get_extract()
        source = textwrap.dedent("""\
            async def process_batch(items):
                results = []
                for item in items:
                    result = await transform(item)
                    results.append(result)
                return results
        """)
        body = extract(source, "process_batch")
        assert body is not None, (
            "Top-level async def not found by _extract_symbol_body"
        )
        assert "await transform" in body


class TestVerifyAnswerFreshnessAsyncDef:
    """verify_answer_freshness must not falsely mark async method questions as stale."""

    @staticmethod
    def _get_verify():
        mod = _load_with_enforcement_deps("lens_quiz", "lens_quiz.py")
        return mod.verify_answer_freshness

    def test_async_method_not_stale(self, tmp_path):
        """A question about an async method should NOT be marked stale."""
        verify = self._get_verify()
        # Create a source file with an async method
        source_file = tmp_path / "service.py"
        source_file.write_text(textwrap.dedent("""\
            class DataService:
                async def fetch_records(self, query):
                    conn = await self.pool.acquire()
                    try:
                        return await conn.fetch(query)
                    finally:
                        await self.pool.release(conn)
        """))

        question = {
            "source": "service.py::DataService.fetch_records",
            "q": "What does fetch_records do after acquiring a connection?",
            "a": "B",
            "opts": ["pool.close", "conn.fetch", "pool.drop", "conn.log"],
        }

        result = verify(question, str(tmp_path))
        assert result is True, (
            "async def method falsely marked as stale — "
            "quiz question will be dropped, reducing quiz difficulty"
        )


# ═══════════════════════════════════════════════════════════════════════
# Bug 6: Shell expansion in redirect targets bypasses write protection
#
# Root cause: _check_bash_write extracts the redirect target as the
# first whitespace-delimited token after > or >>, then compares it
# literally against protected paths. Shell expansion ($VAR, $(cmd),
# `cmd`) defeats this because the literal token doesn't match but
# expands to a protected path at runtime.
#
# Impact: An agent can bypass write protection with patterns like:
#   TARGET=enforcement/...; echo injected > $TARGET
#   bash -c "echo test > $(printf enforcement/...)"
# ═══════════════════════════════════════════════════════════════════════


class TestShellExpansionRedirectBypass:
    """Write guard must block shell expansion in redirect targets near protected paths."""

    @staticmethod
    def _check(command):
        bootstrap = _load_module("bootstrap_adv", _ENFORCEMENT_HOOKS / "_sahjhan_bootstrap.py")
        return bootstrap._check_bash_write(command)

    def test_env_var_redirect_to_protected_path(self):
        """TARGET=enforcement/...; echo > $TARGET must be blocked."""
        result = self._check(
            "TARGET=enforcement/docs/holtz/STATUS.md; echo injected > $TARGET"
        )
        assert result is not None, (
            "Env var redirect to protected path was not blocked — "
            "agent can bypass write protection with variable indirection"
        )

    def test_command_substitution_in_redirect(self):
        """bash -c 'echo > $(printf enforcement/...)' must be blocked."""
        result = self._check(
            'bash -c "echo test > $(printf enforcement/docs/holtz/STATUS.md)"'
        )
        assert result is not None, (
            "Command substitution in bash -c with protected path was not blocked"
        )

    def test_sh_c_with_protected_path(self):
        """sh -c 'echo > enforcement/...' must be blocked."""
        result = self._check(
            'sh -c "echo test > enforcement/docs/holtz/STATUS.md"'
        )
        assert result is not None, (
            "sh -c with protected path literal was not blocked — "
            "bash/sh were missing from the interpreter check"
        )

    def test_safe_env_var_redirect_allowed(self):
        """echo > $UNRELATED_VAR must NOT be blocked (no protected path in command)."""
        result = self._check("echo test > $SOME_OUTPUT_FILE")
        assert result is None, (
            f"Unrelated env var redirect was incorrectly blocked: {result}"
        )

    def test_literal_redirect_still_blocked(self):
        """echo > enforcement/... must still be blocked (regression check)."""
        result = self._check("echo test > enforcement/docs/holtz/STATUS.md")
        assert result is not None, (
            "Literal redirect to protected path was not blocked"
        )


# ═══════════════════════════════════════════════════════════════════════
# Bug 7: Write/Edit tools bypass MANAGED_DOCS protection
#
# Root cause: The path-resolution section in main() checks PROTECTED
# (enforcement/, bin/sahjhan, etc.) and MANAGED_DATA (docs/holtz/.sahjhan/)
# but not MANAGED_DOCS (STATUS.md, PUNCHLIST.md, etc.). The MANAGED_DOCS
# list was only used inside _check_bash_write() for Bash commands.
#
# Impact: An agent can use Write or Edit tools to directly overwrite
# sahjhan-rendered documents (STATUS.md, PUNCHLIST.md, SUMMARY.md,
# MERGE-REPORT.md, PUNCHLIST-MERGED.md) without being blocked.
# Bash redirect to the same paths IS blocked, creating an inconsistency.
# ═══════════════════════════════════════════════════════════════════════


import pytest

from hook_runner import run_hook


@pytest.mark.hook_e2e
class TestManagedDocsWriteEditBypass:
    """Write/Edit tools must be blocked on MANAGED_DOCS, not just Bash redirects."""

    HOOK = "enforcement/hooks/_sahjhan_bootstrap.py"

    def test_write_to_status_md_blocked(self):
        """Write tool targeting STATUS.md must be blocked."""
        event = {
            "tool_name": "Write",
            "tool_input": {"file_path": "docs/holtz/STATUS.md"},
            "cwd": "/tmp/fake-cwd",
        }
        output = run_hook(self.HOOK, event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny", (
            "Write to STATUS.md was allowed — MANAGED_DOCS not enforced for Write tool"
        )

    def test_edit_to_punchlist_md_blocked(self):
        """Edit tool targeting PUNCHLIST.md must be blocked."""
        event = {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": "docs/holtz/PUNCHLIST.md",
                "old_string": "OPEN",
                "new_string": "RESOLVED",
            },
            "cwd": "/tmp/fake-cwd",
        }
        output = run_hook(self.HOOK, event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny", (
            "Edit to PUNCHLIST.md was allowed — agent can forge punchlist status changes"
        )

    def test_write_to_summary_md_blocked(self):
        """Write tool targeting SUMMARY.md must be blocked."""
        event = {
            "tool_name": "Write",
            "tool_input": {"file_path": "docs/holtz/SUMMARY.md"},
            "cwd": "/tmp/fake-cwd",
        }
        output = run_hook(self.HOOK, event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_write_to_merge_report_blocked(self):
        """Write tool targeting MERGE-REPORT.md must be blocked."""
        event = {
            "tool_name": "Write",
            "tool_input": {"file_path": "docs/holtz/MERGE-REPORT.md"},
            "cwd": "/tmp/fake-cwd",
        }
        output = run_hook(self.HOOK, event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_write_to_punchlist_merged_blocked(self):
        """Write tool targeting PUNCHLIST-MERGED.md must be blocked."""
        event = {
            "tool_name": "Write",
            "tool_input": {"file_path": "docs/holtz/PUNCHLIST-MERGED.md"},
            "cwd": "/tmp/fake-cwd",
        }
        output = run_hook(self.HOOK, event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_write_to_non_managed_doc_allowed(self):
        """Write to docs/holtz/notes.md must still be allowed."""
        event = {
            "tool_name": "Write",
            "tool_input": {"file_path": "docs/holtz/my-notes.md"},
            "cwd": "/tmp/fake-cwd",
        }
        output = run_hook(self.HOOK, event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow", (
            "Non-managed doc was blocked — MANAGED_DOCS check is over-broad"
        )
