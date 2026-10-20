"""W19 / item 40 — four files disagreed about whether `NotebookEdit` is a write.

`hooks.toml`'s auto-record counts it as a `source_edit`, so it accrues toward
the accumulation and stall gates. But `hooks.json` registered `pre_tool_hook.py`
under `Write|Edit` only, the TDD gate's `tools` listed `["Edit", "Write"]`, and
`pre_tool_hook.py:99`'s branch naming `NotebookEdit` was therefore dead code.
A notebook write counted toward the gates it could never be stopped by.

**And a fourth, which the punchlist did not name.** `NotebookEdit`'s tool input
carries `notebook_path`, not `file_path` — confirmed in the installed
`claude` binary (2.1.259), which destructures that key by name. The hook read
`tool_input["file_path"]` alone, so even a correctly registered and correctly
gated `NotebookEdit` arrived with an empty path: the managed-path guard could
not match, and `hook eval` ran with no `--file`, which is the argument every
path filter in the TDD gate is written against. Registration without the path
is a no-op, which is why V2 below is the test that would have caught it.

Zero notebooks live in this repo; the exposure is entirely downstream.
"""
from __future__ import annotations

import json
import os
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_DIR = os.path.join(REPO_ROOT, "enforcement")
HOOKS_JSON = os.path.join(REPO_ROOT, "hooks", "hooks.json")
PRE_TOOL_HOOK = os.path.join(CONFIG_DIR, "hooks", "pre_tool_hook.py")

sys.path.insert(0, os.path.join(REPO_ROOT, "tests"))

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - 3.10 and below
    import tomli as tomllib  # type: ignore[no-redef]


def _notebook_event(path: str) -> dict:
    """The shape Claude Code actually sends. `notebook_path`, not `file_path`."""
    return {
        "tool_name": "NotebookEdit",
        "tool_input": {"notebook_path": path, "new_source": "x = 1"},
    }


# ── V3: the files must agree ─────────────────────────────────────────────────


class TestTheFourFilesAgree:
    """The consistency check, because the disagreement is the defect.

    Each file on its own reads as deliberate. Only side by side does
    "recorded as a source edit, exempt from the gate that governs source
    edits" become visible.
    """

    def _tdd_gate(self) -> dict:
        with open(os.path.join(CONFIG_DIR, "hooks.toml"), "rb") as fh:
            hooks = tomllib.load(fh)["hooks"]
        gates = [
            h for h in hooks
            if h.get("event") == "PreToolUse" and "TDD violation" in h.get("message", "")
        ]
        assert len(gates) == 1, f"expected exactly one TDD gate, found {len(gates)}"
        return gates[0]

    def _auto_record_source_edit(self) -> dict:
        with open(os.path.join(CONFIG_DIR, "hooks.toml"), "rb") as fh:
            hooks = tomllib.load(fh)["hooks"]
        rules = [
            h for h in hooks
            if h.get("auto_record", {}).get("event_type") == "source_edit"
        ]
        assert len(rules) == 1, f"expected one source_edit rule, found {len(rules)}"
        return rules[0]

    def _pre_tool_hook_matcher(self) -> str:
        with open(HOOKS_JSON, encoding="utf-8") as fh:
            registered = json.load(fh)
        for entries in registered.get("hooks", {}).values():
            for entry in entries:
                for hook in entry.get("hooks", []):
                    # The command is an interpreter line with a quoted path, so
                    # a substring is the honest match here — `endswith` reads
                    # tighter and silently finds nothing.
                    if "/pre_tool_hook.py" in hook.get("command", ""):
                        return entry.get("matcher", "")
        raise AssertionError("pre_tool_hook.py is not registered at all")

    def test_the_gate_governs_every_tool_the_recorder_counts(self):
        """The core of item 40. A tool whose writes accrue toward the stall and
        accumulation gates must be a tool the TDD gate can refuse — otherwise
        it is a way to spend the budget without paying the price."""
        recorded = set(self._auto_record_source_edit()["tools"])
        gated = set(self._tdd_gate()["tools"])
        assert recorded == gated, (
            f"auto-record counts {sorted(recorded)} as source edits but the TDD "
            f"gate governs {sorted(gated)} — the difference is a write that "
            "accrues toward a gate it can never be stopped by"
        )

    def test_the_hook_is_registered_for_every_tool_its_gate_governs(self):
        """A gate the harness never fires the hook for is not a gate.

        This is the half a subprocess test cannot see: the hook decides
        correctly when it runs, and Claude Code decides whether it runs.
        """
        matcher = set(self._pre_tool_hook_matcher().split("|"))
        gated = set(self._tdd_gate()["tools"])
        assert gated <= matcher, (
            f"the TDD gate governs {sorted(gated)} but hooks.json only fires "
            f"pre_tool_hook.py for {sorted(matcher)} — the branch is dead code"
        )

    def test_the_hooks_own_branch_names_the_same_tools(self):
        """`pre_tool_hook.py`'s exemption branch is the third statement of the
        same list, and the one a reader is most likely to trust."""
        with open(PRE_TOOL_HOOK, encoding="utf-8") as fh:
            source = fh.read()
        gated = set(self._tdd_gate()["tools"])
        marker = 'if tool_name in ('
        start = source.index(marker) + len(marker)
        named = {
            token.strip().strip('"\'')
            for token in source[start:source.index(")", start)].split(",")
            if token.strip()
        }
        assert named == gated, (
            f"pre_tool_hook.py's branch names {sorted(named)}, the TDD gate "
            f"governs {sorted(gated)}"
        )


# ── V1/V2: the hook must be able to see the notebook it is handed ────────────


class TestTheNotebookPathIsRead:
    """Registration without the path is a no-op, and reads as a fix.

    Every assertion in this class fails on an empty path in a way that looks
    like a *decision* — allow, exempt, not-managed — which is why the path is
    asserted here rather than left to the gate tests to imply.
    """

    def test_the_hook_extracts_notebook_path(self):
        import importlib.util

        spec = importlib.util.spec_from_file_location("_pth", PRE_TOOL_HOOK)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        sys.modules["_pth"] = module
        spec.loader.exec_module(module)
        assert module._write_target(_notebook_event("/repo/nb.ipynb")["tool_input"]) == (
            "/repo/nb.ipynb"
        ), "a NotebookEdit arrives with an empty path — the guard cannot match it"

    def test_an_edit_still_uses_file_path(self):
        """The unchanged-behaviour arm: `Edit`/`Write` keep their own key, and
        a notebook key must never shadow one that is present."""
        import importlib.util

        spec = importlib.util.spec_from_file_location("_pth2", PRE_TOOL_HOOK)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        sys.modules["_pth2"] = module
        spec.loader.exec_module(module)
        assert module._write_target({"file_path": "/repo/a.py"}) == "/repo/a.py"
        assert module._write_target({}) == ""


@pytest.mark.hook_e2e
class TestTheManagedPathGuardCoversNotebooks:
    """V2 — driven as a subprocess, which is the interface Claude Code uses."""

    def test_a_notebook_edit_to_a_managed_doc_is_blocked(self, tmp_path):
        from hook_runner import run_hook

        managed = tmp_path / "docs" / "holtz" / "STATUS.md"
        managed.parent.mkdir(parents=True, exist_ok=True)
        managed.write_text("x\n", encoding="utf-8")
        event = _notebook_event(str(managed))
        event["cwd"] = str(tmp_path)
        out = run_hook(PRE_TOOL_HOOK, event, cwd=str(tmp_path))
        decision = out.get("hookSpecificOutput", {}).get("permissionDecision")
        assert decision == "deny", out


@pytest.mark.slow
@pytest.mark.integration
class TestTheTddGateCoversNotebooks:
    """V1 — against a daemon that authenticates, in `fix_loop`, with no failing
    test recorded. The state the gate exists for."""

    def test_a_notebook_edit_is_blocked_with_no_failing_test(self, two_actors):
        event = _notebook_event(os.path.join(two_actors.project_root, "src", "a.ipynb"))
        out = two_actors.hook("pre_tool_hook.py", event)
        decision = out.get("hookSpecificOutput", {}).get("permissionDecision")
        assert decision == "deny", out

    def test_a_notebook_edit_under_tests_stays_exempt(self, two_actors):
        """Non-vacuity, and the shape a widened gate breaks first: the TDD
        gate's `tests/**` exemption has to keep working for the new tool, or
        writing the failing test the gate demands is itself blocked."""
        event = _notebook_event(
            os.path.join(two_actors.project_root, "tests", "test_a.ipynb")
        )
        out = two_actors.hook("pre_tool_hook.py", event)
        decision = out.get("hookSpecificOutput", {}).get("permissionDecision")
        assert decision != "deny", out
