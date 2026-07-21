"""Unit tests for the shape-tolerant Bash PostToolUse helpers (#75).

``hooks/_common.bash_output`` / ``bash_exit_code`` decouple the enforcement
hooks from Claude Code payload-shape drift. Claude Code 2.x delivers Bash
stdout under ``tool_response.stdout`` and omits ``exit_code`` entirely; pre-2.x
used ``tool_response.output`` with an explicit ``exit_code``. Reading only the
pre-2.x keys is what wedged ``recon_complete`` in #75, so these tests pin both
shapes.

The exact 2.x payload below was captured live from Claude Code 2.1.x:

    "tool_response": {"stdout": "...", "stderr": "", "interrupted": false,
                      "isImage": false, "noOutputExpected": false}
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

# Load hooks/_common.py under a unique module name so we don't pollute
# sys.modules['_common'] (the enforcement hooks import the bare name and a
# cached hooks version breaks them under some collection orderings).
_path = Path(__file__).resolve().parent.parent / "hooks" / "_common.py"
_spec = importlib.util.spec_from_file_location("_hooks_common_for_bash_test", str(_path))
if _spec is None or _spec.loader is None:
    raise RuntimeError(f"Cannot load {_path}")
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
bash_output = _mod.bash_output
bash_exit_code = _mod.bash_exit_code


def _cc2x(stdout: str) -> dict:
    """The real Claude Code 2.x Bash PostToolUse tool_response shape."""
    return {
        "tool_response": {
            "stdout": stdout,
            "stderr": "",
            "interrupted": False,
            "isImage": False,
            "noOutputExpected": False,
        }
    }


class TestBashOutput:
    def test_reads_cc2x_stdout(self):
        assert bash_output(_cc2x("hello")) == "hello"

    def test_reads_legacy_output(self):
        assert bash_output({"tool_response": {"exit_code": 0, "output": "hi"}}) == "hi"

    def test_prefers_stdout_over_output(self):
        event = {"tool_response": {"stdout": "new", "output": "old"}}
        assert bash_output(event) == "new"

    def test_missing_tool_response_is_empty(self):
        assert bash_output({}) == ""

    def test_none_tool_response_is_empty(self):
        assert bash_output({"tool_response": None}) == ""

    def test_no_stdout_no_output_is_empty(self):
        assert bash_output(_cc2x("")) == ""


class TestBashExitCode:
    def test_absent_defaults_to_success(self):
        # CC 2.x omits exit_code and only fires PostToolUse on success.
        assert bash_exit_code(_cc2x("ok")) == 0

    def test_explicit_zero(self):
        assert bash_exit_code({"tool_response": {"exit_code": 0, "output": ""}}) == 0

    def test_explicit_nonzero_is_honored(self):
        assert bash_exit_code({"tool_response": {"exit_code": 1, "output": ""}}) == 1

    def test_missing_tool_response_defaults_to_success(self):
        assert bash_exit_code({}) == 0
