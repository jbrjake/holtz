"""Tests for the canonical hook runner itself.

The runner is the only thing standing between a failing hook and a readable
explanation of why. When it drops the hook's stderr, a wrong decision is
indistinguishable from a crashed helper, and every test written against it
inherits the blindness — which is exactly how a silent `exit_ok()` in
`primer.py` stayed unexplained across sessions.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hook_runner import run_hook  # noqa: E402


def _hook(tmp_path, body: str) -> str:
    path = tmp_path / "hook.py"
    path.write_text("import sys, json\n" + body, encoding="utf-8")
    return str(path)


def test_stderr_survives_a_hook_that_printed_valid_json(tmp_path):
    """The case the runner used to drop on the floor.

    A hook can emit a perfectly well-formed decision *and* explain itself on
    stderr. Only the decision used to come back.
    """
    hook = _hook(tmp_path, (
        'print("diagnostic: the status probe timed out", file=sys.stderr)\n'
        'print(json.dumps({"continue": True}))\n'
    ))
    output = run_hook(hook, {})
    assert output["continue"] is True
    assert "the status probe timed out" in output["_stderr"]


def test_the_real_exit_code_comes_back_with_json(tmp_path):
    """`run_enforcement_hook` defaults a missing `_returncode` to 0.

    So while this key was absent on the JSON path, `assert code == 0` was an
    assertion about the default and would have held for a hook exiting 2.
    """
    hook = _hook(tmp_path, (
        'print(json.dumps({"continue": True}))\n'
        'sys.exit(2)\n'
    ))
    output = run_hook(hook, {})
    assert output["_returncode"] == 2


def test_a_hooks_own_keys_are_not_overwritten(tmp_path):
    """The hook is the thing under test; the harness does not correct it."""
    hook = _hook(tmp_path, (
        'print(json.dumps({"_stderr": "mine", "_returncode": 99}))\n'
    ))
    output = run_hook(hook, {})
    assert output["_stderr"] == "mine"
    assert output["_returncode"] == 99


def test_empty_stdout_still_reports_stderr_and_code(tmp_path):
    """The path that already worked, kept working."""
    hook = _hook(tmp_path, (
        'print("boom", file=sys.stderr)\n'
        'sys.exit(3)\n'
    ))
    output = run_hook(hook, {})
    assert output["_empty"] is True
    assert "boom" in output["_stderr"]
    assert output["_returncode"] == 3


def test_unparseable_stdout_reports_the_raw_text(tmp_path):
    hook = _hook(tmp_path, 'print("not json at all")\n')
    output = run_hook(hook, {})
    assert output["_parse_error"] is True
    assert output["_raw_stdout"] == "not json at all"
