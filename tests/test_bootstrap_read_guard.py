"""Tests for _sahjhan_bootstrap.py read-guard enforcement."""
from __future__ import annotations

import json
import subprocess
import sys

HOOK = "enforcement/hooks/_sahjhan_bootstrap.py"


def _run_hook(event: dict) -> dict:
    """Run the bootstrap hook with a given event dict, return parsed output."""
    result = subprocess.run(
        [sys.executable, HOOK],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        timeout=10,
    )
    return json.loads(result.stdout)


class TestReadGuard:
    def test_read_quiz_bank_blocked(self):
        event = {
            "tool_name": "Read",
            "tool_input": {"file_path": "enforcement/quiz-bank.json"},
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "block"

    def test_read_session_key_blocked(self):
        event = {
            "tool_name": "Read",
            "tool_input": {"file_path": "docs/holtz/.sahjhan/session.key"},
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "block"

    def test_read_normal_file_allowed(self):
        event = {
            "tool_name": "Read",
            "tool_input": {"file_path": "README.md"},
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"

    def test_bash_cat_quiz_bank_blocked(self):
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "cat enforcement/quiz-bank.json"},
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "block"

    def test_bash_python_open_session_key_blocked(self):
        event = {
            "tool_name": "Bash",
            "tool_input": {
                "command": "python3 -c \"print(open('docs/holtz/.sahjhan/session.key').read())\""
            },
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "block"

    def test_bash_without_guarded_path_allowed(self):
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "git status"},
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"

    def test_path_traversal_blocked(self):
        event = {
            "tool_name": "Read",
            "tool_input": {"file_path": "hooks/../enforcement/quiz-bank.json"},
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "block"

    def test_write_to_protected_still_blocked(self):
        """Existing write protection must still work."""
        import os
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        event = {
            "tool_name": "Write",
            "tool_input": {"file_path": "enforcement/hooks/lens_quiz.py"},
            "cwd": repo_root,
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "block"

    def test_sed_inplace_to_protected_blocked(self):
        """BH-008: sed -i to protected enforcement/ path must be blocked."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "sed -i 's/old/new/g' enforcement/events.toml"},
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "block"

    def test_perl_inplace_to_protected_blocked(self):
        """BH-008: perl -pi to protected enforcement/ path must be blocked."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "perl -pi -e 's/old/new/g' enforcement/states.toml"},
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "block"

    def test_patch_to_protected_blocked(self):
        """BH-008: patch to protected enforcement/ path must be blocked."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "patch enforcement/hooks/primer.py < fix.patch"},
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "block"

    def test_read_per_ledger_session_key_blocked(self):
        """BH-015: per-ledger session keys must be guarded."""
        event = {
            "tool_name": "Read",
            "tool_input": {
                "file_path": "docs/holtz/.sahjhan/ledgers/run-26/session.key"
            },
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "block"

    def test_read_per_ledger_session_key_absolute_blocked(self):
        """BH-015: absolute path to per-ledger session key must be guarded."""
        event = {
            "tool_name": "Read",
            "tool_input": {
                "file_path": "/tmp/fake-cwd/docs/holtz/.sahjhan/ledgers/run-26/session.key"
            },
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "block"

    def test_bash_cat_per_ledger_session_key_blocked(self):
        """BH-015: Bash access to per-ledger session keys must be guarded."""
        event = {
            "tool_name": "Bash",
            "tool_input": {
                "command": "cat docs/holtz/.sahjhan/ledgers/run-26/session.key"
            },
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "block"

    def test_bash_xxd_per_ledger_session_key_blocked(self):
        """BH-015: xxd access to per-ledger session keys must be guarded."""
        event = {
            "tool_name": "Bash",
            "tool_input": {
                "command": "xxd /abs/path/.sahjhan/ledgers/run-26/session.key"
            },
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "block"

    def test_bash_python_compute_proof_blocked(self):
        """BH-015: Python code computing proofs from per-ledger keys must be blocked."""
        event = {
            "tool_name": "Bash",
            "tool_input": {
                "command": (
                    "python3 -c \"from _common import compute_event_proof; "
                    "compute_event_proof('ctx', {}, '.sahjhan/ledgers/run-26/session.key')\""
                )
            },
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "block"

    def test_bash_case_insensitive_quiz_bank_blocked(self):
        """BH-020: alternate-case paths must be blocked on case-insensitive FS."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "cat enforcement/QUIZ-BANK.JSON"},
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "block"

    def test_bash_case_insensitive_session_key_blocked(self):
        """BH-020: alternate-case .sahjhan/SESSION.KEY must be blocked."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "xxd docs/holtz/.SAHJHAN/SESSION.KEY"},
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "block"

    # --- BH-001 (run 27): Bash writes to managed docs/holtz/ files ---

    def test_bash_redirect_to_managed_status_blocked(self):
        """BH-001: Bash redirect to docs/holtz/STATUS.md must be blocked."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": 'echo "hacked" > docs/holtz/STATUS.md'},
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "block"

    def test_bash_redirect_to_managed_punchlist_blocked(self):
        """BH-001: Bash redirect to docs/holtz/PUNCHLIST.md must be blocked."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": 'cat /dev/null > docs/holtz/PUNCHLIST.md'},
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "block"

    def test_bash_tee_to_managed_summary_blocked(self):
        """BH-001: tee to docs/holtz/SUMMARY.md must be blocked."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "echo foo | tee docs/holtz/SUMMARY.md"},
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "block"

    def test_bash_cp_to_managed_merge_report_blocked(self):
        """BH-001: cp to docs/holtz/MERGE-REPORT.md must be blocked."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "cp /tmp/evil.md docs/holtz/MERGE-REPORT.md"},
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "block"

    # --- BH-002 (run 27): Interpreter execution bypass ---

    def test_bash_python_c_write_enforcement_blocked(self):
        """BH-002: python -c writing to enforcement/ must be blocked."""
        event = {
            "tool_name": "Bash",
            "tool_input": {
                "command": "python3 -c \"open('enforcement/hooks/test.py','w').write('pwned')\""
            },
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "block"

    def test_bash_dd_write_enforcement_blocked(self):
        """BH-002: dd to enforcement/ must be blocked."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "dd if=/dev/zero of=enforcement/states.toml bs=1 count=100"},
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "block"

    def test_bash_redirect_with_quoted_gt_bypass_blocked(self):
        """BH-002: quoted > before real redirect must not bypass guard."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": 'echo ">" > enforcement/hooks/test.py'},
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "block"

    # --- BH-004 (run 27): Chained command bypass ---

    def test_bash_chained_cp_enforcement_blocked(self):
        """BH-004: chained cp to enforcement/ must be blocked."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "true && cp /dev/null enforcement/hooks/test.py"},
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "block"

    def test_bash_sahjhan_cmd_with_guarded_path_allowed(self):
        """sahjhan commands referencing quiz-bank.json should be allowed since
        sahjhan itself needs to read the quiz bank."""
        # Actually NO - the bootstrap hook doesn't know about sahjhan commands.
        # The read guard blocks ALL bash commands referencing guarded paths.
        # sahjhan reads files directly, not through bash cat.
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "cat enforcement/quiz-bank.json | wc -l"},
            "cwd": "/tmp/fake-cwd",
        }
        output = _run_hook(event)
        assert output["hookSpecificOutput"]["permissionDecision"] == "block"
