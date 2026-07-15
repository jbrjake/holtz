"""#71: the TDD gate must cover ordinary-source writes via Bash.

The enforcement's TDD "failing test before you touch source" gate was enforced
only against the Write/Edit tools. Bash is an unguarded write primitive:
``cat > src/foo.py`` heredocs, ``tee``, and ``sed -i`` wrote source with no
failing test recorded, bypassing the whole contract (the forensic log in #71).

Two halves are tested here:

  * The *parser* (``_bash_write_targets`` / ``_strip_heredoc_bodies``) — it must
    find real write targets while NOT over-blocking quoted or heredoc *data*
    (the false-positive class #71 itself documents: an issue-body heredoc that
    merely quotes ``x > y`` or ``sahjhan pause`` must not be read as a command).
  * The *gate* — a bash write to in-repo source in fix_loop is routed through
    the same ``sahjhan hook eval`` TDD gate as Write/Edit, while docs/out-of-repo
    writes stay exempt and non-writes never reach the eval.
"""
from __future__ import annotations

import os
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENFORCEMENT_HOOKS_DIR = os.path.join(REPO_ROOT, "enforcement", "hooks")
sys.path.insert(0, ENFORCEMENT_HOOKS_DIR)
sys.path.insert(0, os.path.join(REPO_ROOT, "tests"))

from _sahjhan_bootstrap import (  # noqa: E402
    _bash_write_targets,
    _strip_heredoc_bodies,
)
from test_sahjhan_integration import (  # noqa: E402
    _create_mock_binary,
    _mock_env,
    assert_allowed,
    assert_blocked,
    run_enforcement_hook,
)

# ---------------------------------------------------------------------------
# Parser: heredoc-body stripping
# ---------------------------------------------------------------------------


class TestStripHeredocBodies:
    def test_body_and_terminator_dropped(self):
        cmd = "cat > f.py <<'EOF'\nimport os\nx > y\nEOF\necho done"
        out = _strip_heredoc_bodies(cmd)
        assert "import os" not in out
        assert "x > y" not in out
        assert "cat > f.py <<'EOF'" in out
        assert "echo done" in out

    def test_unquoted_and_dash_delimiters(self):
        cmd = "cat <<-END\n\tinert\n\tEND\ncat <<END2\ndata\nEND2"
        out = _strip_heredoc_bodies(cmd)
        assert "inert" not in out
        assert "data" not in out

    def test_no_heredoc_is_identity(self):
        cmd = "echo hi > f.py && grep x g.py"
        assert _strip_heredoc_bodies(cmd) == cmd


# ---------------------------------------------------------------------------
# Parser: write-target extraction — MUST detect
# ---------------------------------------------------------------------------


class TestWriteTargetsDetected:
    @pytest.mark.parametrize("cmd,expected", [
        ("cat > src/foo.py", "src/foo.py"),
        ("cat >> src/foo.py", "src/foo.py"),
        ("printf 'x' > foo.py", "foo.py"),
        ("echo hi >foo.py", "foo.py"),                       # no space after >
        ("cat > 'my file.py'", "my file.py"),                # quoted target
        ("python gen.py > out.py", "out.py"),
        ("cat x | tee foo.py", "foo.py"),
        ("cat x | tee -a foo.py", "foo.py"),
        ("sed -i 's/a/b/' foo.py", "foo.py"),
        ("sed -i.bak 's/a/b/' foo.py", "foo.py"),
    ])
    def test_detected(self, cmd, expected):
        assert expected in _bash_write_targets(cmd), \
            f"{cmd!r} should yield write target {expected!r}"

    def test_heredoc_redirect_target_detected(self):
        cmd = "cat > src/widget.py <<'PY'\nprint('hi')\nPY"
        assert "src/widget.py" in _bash_write_targets(cmd)

    def test_multiple_targets_in_one_line(self):
        targets = _bash_write_targets("echo a > one.py; echo b >> two.py")
        assert "one.py" in targets and "two.py" in targets


# ---------------------------------------------------------------------------
# Parser: MUST NOT over-block (the #71 false-positive class)
# ---------------------------------------------------------------------------


class TestWriteTargetsNotOverBlocked:
    def test_heredoc_body_redirect_is_data_not_target(self):
        # The body's `x > y.py` is inert data — only the opener target counts.
        cmd = "cat > docs/note.md <<'EOF'\nrun x > y.py to redirect\nEOF"
        targets = _bash_write_targets(cmd)
        assert "y.py" not in targets

    @pytest.mark.parametrize("cmd", [
        'echo "text with > y.py inside"',      # > inside double quotes
        "echo 'a > b.py'",                      # > inside single quotes
        "pytest 2>&1",                          # stderr dup, not a file write
        "make test > /dev/null 2>&1 || true",   # /dev/null is out-of-repo anyway
        "echo a->b.py",                         # arrow, not a redirect
        "grep -r 'foo' src/",                   # no write primitive
        "git diff > /tmp/scratch.diff",         # out-of-repo target
        "cat > $TARGET",                        # shell expansion target
        "cat > `mktemp`",                       # command substitution target
    ])
    def test_no_source_target(self, cmd):
        # Either no target at all, or only non-source (out-of-repo) targets —
        # never an in-repo *.py source path.
        targets = _bash_write_targets(cmd)
        assert not any(t.endswith("b.py") or t.endswith("y.py") for t in targets), \
            f"{cmd!r} over-blocked: {targets}"

    def test_issue_body_heredoc_quoting_commands_yields_no_targets(self):
        # The #71 self-demonstrating case: writing an issue body (to docs) whose
        # heredoc DATA quotes shell/CLI tokens must not spawn spurious targets.
        cmd = (
            "cat > docs/holtz/patterns-brief.md <<'BRIEF'\n"
            "A `cat > src/foo.py` heredoc bypassed the gate.\n"
            "`sahjhan pause` and `tee x.py` are quoted here as prose.\n"
            "sed -i 's/a/b/' bar.py  # also just prose\n"
            "BRIEF"
        )
        targets = _bash_write_targets(cmd)
        assert "src/foo.py" not in targets
        assert "x.py" not in targets
        assert "bar.py" not in targets


# ---------------------------------------------------------------------------
# Gate behavior via the real hook subprocess (mirrors the Write/Edit TDD tests)
# ---------------------------------------------------------------------------

# Mock sahjhan: `hook eval` returns a scripted decision; `status` reports
# fix_loop so the freshness/read path sees an active run.
_SCRIPT = (
    'case "$*" in\n'
    '  *hook*eval*)\n'
    "    echo '%s'\n"
    '    exit %d\n'
    '    ;;\n'
    '  *status*)\n'
    '    echo "state: fix_loop (1 events, chain valid)"\n'
    '    exit 0\n'
    '    ;;\n'
    'esac\n'
    'exit 0'
)
_BLOCK_JSON = (
    '{"data":{"decision":"block","messages":[{"action":"block",'
    '"message":"TDD violation: write and run a failing test before editing '
    'source files."}]}}'
)
_ALLOW_JSON = '{"data":{"decision":"allow"}}'


def _setup_fix_loop(tmp_path, eval_json, eval_exit):
    (tmp_path / "enforcement").mkdir(parents=True, exist_ok=True)
    (tmp_path / "enforcement" / "protocol.toml").write_text("")
    _create_mock_binary(tmp_path, _SCRIPT % (eval_json, eval_exit))
    from datetime import datetime, timezone

    from _protocol_cache import empty_cache, write_cache
    cache = empty_cache()
    cache["state"] = "fix_loop"
    cache["last_sahjhan_cmd"] = datetime.now(timezone.utc).isoformat()  # noqa: UP017
    write_cache(str(tmp_path), cache)


def _bash_event(command, cwd):
    return {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": str(cwd)}


class TestBashSourceWriteGate:
    def test_heredoc_source_write_blocked(self, tmp_path, mock_daemon):
        """The headline #71 bypass: cat > src/foo.py heredoc is now gated."""
        _setup_fix_loop(tmp_path, _BLOCK_JSON, 1)
        cmd = "cat > src/widget.py <<'PY'\nprint('fix')\nPY"
        code, output, _ = run_enforcement_hook(
            "_sahjhan_bootstrap.py", _bash_event(cmd, tmp_path),
            cwd=str(tmp_path), env=_mock_env(tmp_path),
        )
        assert_blocked(code, output, "widget.py")

    def test_append_source_write_blocked(self, tmp_path, mock_daemon):
        _setup_fix_loop(tmp_path, _BLOCK_JSON, 1)
        code, output, _ = run_enforcement_hook(
            "_sahjhan_bootstrap.py", _bash_event("echo x >> src/widget.py", tmp_path),
            cwd=str(tmp_path), env=_mock_env(tmp_path),
        )
        assert_blocked(code, output, "TDD")

    def test_source_write_allowed_once_gate_satisfied(self, tmp_path, mock_daemon):
        """When a failing test is recorded (eval allows), the bash write proceeds."""
        _setup_fix_loop(tmp_path, _ALLOW_JSON, 0)
        cmd = "cat > src/widget.py <<'PY'\nprint('fix')\nPY"
        code, output, _ = run_enforcement_hook(
            "_sahjhan_bootstrap.py", _bash_event(cmd, tmp_path),
            cwd=str(tmp_path), env=_mock_env(tmp_path),
        )
        assert_allowed(code, output)

    def test_docs_write_exempt(self, tmp_path, mock_daemon):
        """A bash write to docs/ is allowed even when the gate would block."""
        _setup_fix_loop(tmp_path, _BLOCK_JSON, 1)
        cmd = "cat > docs/holtz/patterns-brief.md <<'MD'\n# notes\nMD"
        code, output, _ = run_enforcement_hook(
            "_sahjhan_bootstrap.py", _bash_event(cmd, tmp_path),
            cwd=str(tmp_path), env=_mock_env(tmp_path),
        )
        assert_allowed(code, output)

    def test_out_of_repo_write_exempt(self, tmp_path, mock_daemon):
        """A bash write outside the project tree (session notes) is allowed."""
        _setup_fix_loop(tmp_path, _BLOCK_JSON, 1)
        outside = str(tmp_path.parent / "session-notes.md")
        code, output, _ = run_enforcement_hook(
            "_sahjhan_bootstrap.py", _bash_event(f"echo hi > {outside}", tmp_path),
            cwd=str(tmp_path), env=_mock_env(tmp_path),
        )
        assert_allowed(code, output)

    def test_non_write_command_never_gated(self, tmp_path, mock_daemon):
        """A read/search bash command in fix_loop is allowed (no write target)."""
        _setup_fix_loop(tmp_path, _BLOCK_JSON, 1)
        code, output, _ = run_enforcement_hook(
            "_sahjhan_bootstrap.py", _bash_event("grep -r foo src/ | head", tmp_path),
            cwd=str(tmp_path), env=_mock_env(tmp_path),
        )
        assert_allowed(code, output)

    def test_heredoc_data_does_not_over_block(self, tmp_path, mock_daemon):
        """Writing a docs file whose heredoc body quotes `> src/x.py` is allowed —
        the inert body must not be read as a source write (#71 over-block class)."""
        _setup_fix_loop(tmp_path, _BLOCK_JSON, 1)
        cmd = (
            "cat > docs/note.md <<'EOF'\n"
            "To bypass, someone ran: cat > src/secret.py\n"
            "EOF"
        )
        code, output, _ = run_enforcement_hook(
            "_sahjhan_bootstrap.py", _bash_event(cmd, tmp_path),
            cwd=str(tmp_path), env=_mock_env(tmp_path),
        )
        assert_allowed(code, output)

    def test_no_active_audit_allows_source_write(self, tmp_path):
        """Outside an active audit (no daemon/cache), bash writes are not gated."""
        # No mock_daemon fixture → read_cache returns None → fast allow.
        (tmp_path / "enforcement").mkdir(parents=True, exist_ok=True)
        code, output, _ = run_enforcement_hook(
            "_sahjhan_bootstrap.py",
            _bash_event("cat > src/widget.py <<'PY'\nx=1\nPY", tmp_path),
            cwd=str(tmp_path), env=_mock_env(tmp_path),
        )
        assert_allowed(code, output)
