"""``A & B`` is two commands, and every command-keyed guard read only ``A``.

Bash's ``&`` separates one command from the next exactly as ``;`` does. Eight
sites in this tree split a Bash line into segments, in two different spellings
of one regex, and every one of them omitted single ``&``. So a guard that
inspects the first token of each segment inspected ``A`` and never saw ``B``.

One typed character reached ``sahjhan reseal``/``sign``/``vault read``, the
human-only ``event quiz_exhausted_resolved`` attestation channel, the fix-loop
commit gate, ``is_git_commit`` (making a commit invisible to both the gate and
``protocol_tracker``), the anti-gaming long-``sleep`` guard, the daemon-recovery
allowlist that is live for every Bash call, and the self-protection guard on
``enforcement/hooks/`` — the directory whose own docstring is "DO NOT MODIFY.
This hook protects itself."

That is the class of #81 (the ``!`` incident), one token past where that fix
stopped. The fix is a single segmentation owner in ``_shell_norm``; these tests
pin the behaviour and pin that the ownership stays single.

Two things here look like duplication and are not:

* The ``&`` cases are stated *both* at the pure-function level and through the
  real hook subprocess. The subprocess is what Claude Code runs; the pure form
  is what says which guard is wrong when it goes red.
* The redirect cases restate idioms ``test_contract_commands.py`` already
  covers. Adding ``&`` to a character class is exactly the change that breaks
  ``2>&1``, so the hazard is asserted next to the change that creates it.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOKS_DIR = os.path.join(REPO_ROOT, "enforcement", "hooks")
sys.path.insert(0, HOOKS_DIR)

from _shell_norm import shell_segments  # noqa: E402

# --------------------------------------------------------------------------
# The owner itself
# --------------------------------------------------------------------------

class TestSegmentationOwner:
    """``_shell_norm.shell_segments`` decides where a command ends."""

    @pytest.mark.parametrize("command,expected", [
        ("true & sahjhan reseal", ["true", "sahjhan reseal"]),
        ("true && sahjhan reseal", ["true", "sahjhan reseal"]),
        ("true ; sahjhan reseal", ["true", "sahjhan reseal"]),
        ("true | sahjhan reseal", ["true", "sahjhan reseal"]),
        ("true || sahjhan reseal", ["true", "sahjhan reseal"]),
        ("true\nsahjhan reseal", ["true", "sahjhan reseal"]),
    ])
    def test_every_separator_yields_both_commands(self, command, expected):
        assert shell_segments(command) == expected

    def test_the_two_character_operator_still_wins(self):
        """``&&`` must not degrade into two ``&`` splits with an empty middle."""
        assert shell_segments("a && b") == ["a", "b"]

    @pytest.mark.parametrize("command", [
        "sahjhan status &",
        "nohup sahjhan daemon start &",
        "nohup sahjhan daemon start > /dev/null 2>&1 &",
    ])
    def test_a_trailing_ampersand_is_one_command(self, command):
        """Backgrounding terminates a command; it does not begin a second one.

        This is what the empty-segment drop buys, and it is load-bearing:
        ``nohup … &`` is a spelling the skill files teach, and
        ``_is_recovery_command`` requires *every* segment to be recovery.
        """
        assert len(shell_segments(command)) == 1


class TestARedirectIsNotASeparator:
    """V5. Adding ``&`` to the class is what threatens ``2>&1``.

    Unhandled, ``foo 2>&1`` splits into ``foo 2>`` and ``1`` — and since the
    guards read the first token of each segment, the invented second segment
    is a command name that was never typed.
    """

    @pytest.mark.parametrize("command", [
        "sahjhan status 2>&1",
        "sahjhan status 1>&2",
        "sahjhan status >&2",
        "sahjhan status 2>&-",
        "sahjhan status &>/dev/null",
        "sahjhan status &>>/tmp/out.log",
        "sahjhan status >/dev/null 2>&1",
    ])
    def test_a_redirect_operator_stays_inside_one_segment(self, command):
        assert shell_segments(command) == [command]

    def test_a_redirect_and_a_separator_together(self):
        assert shell_segments("foo 2>&1 & bar") == ["foo 2>&1", "bar"]

    def test_a_detached_ampersand_after_a_redirect_still_separates(self):
        """``>`` then a space then ``&`` is a redirect and then a separator."""
        assert shell_segments("foo > bar & baz") == ["foo > bar", "baz"]

    def test_the_segment_keeps_the_bytes_it_was_written_with(self):
        """The redirect is masked for the split, not stripped from the result.

        ``_check_bash_write`` scans each segment for redirect *targets*, so a
        segment handed back without its redirect would hide a real write.
        """
        assert shell_segments("echo x > enforcement/hooks/evil.py") == [
            "echo x > enforcement/hooks/evil.py"
        ]


class TestSegmentationHasOneOwner:
    """V6. Grep for the construct, not for a literal.

    The tree carried the same split in two spellings — padded
    ``\\s*(?:…)\\s*`` and bare — so a grep for either read clean while four
    sites survived. That is how this stayed at "four sites" through a review.
    The invariant is structural: no module outside ``_shell_norm`` decides
    where a command ends.
    """

    _SPLIT_CALL_RE = re.compile(r"(?:^|[^\w.])re\.split\(|_re\.split\(")

    def test_no_module_outside_shell_norm_splits_on_shell_operators(self):
        offenders = []
        for root in (
            os.path.join(REPO_ROOT, "enforcement"),
            os.path.join(REPO_ROOT, "hooks"),
        ):
            for dirpath, _dirs, files in os.walk(root):
                if "__pycache__" in dirpath:
                    continue
                for name in files:
                    if not name.endswith(".py") or name == "_shell_norm.py":
                        continue
                    path = os.path.join(dirpath, name)
                    with open(path, encoding="utf-8") as fh:
                        for lineno, line in enumerate(fh, 1):
                            if not self._SPLIT_CALL_RE.search(line):
                                continue
                            if "&&" in line:
                                offenders.append(
                                    f"{os.path.relpath(path, REPO_ROOT)}:{lineno}: {line.strip()}"
                                )
        assert not offenders, (
            "Segmentation has one owner (_shell_norm.shell_segments). These "
            "sites decide it themselves, and a split that disagrees with the "
            "owner is a hole rather than a nuisance:\n  "
            + "\n  ".join(offenders)
        )


# --------------------------------------------------------------------------
# Driven through the real hook subprocess
# --------------------------------------------------------------------------

def _decision(command: str, cwd: str = REPO_ROOT) -> tuple[str, str]:
    """Run the PreToolUse bootstrap hook the way Claude Code runs it."""
    from hook_runner import run_hook

    event = {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": cwd}
    output = run_hook(
        os.path.join(HOOKS_DIR, "_sahjhan_bootstrap.py"), event, cwd=cwd, timeout=20
    )
    payload = output.get("hookSpecificOutput", {})
    return payload.get("permissionDecision", ""), payload.get(
        "permissionDecisionReason", ""
    )


@pytest.mark.hook_e2e
class TestAmpersandDoesNotReachBlockedSubcommands:
    """V1. The five driven lines from the unit, as a regression fixture.

    Each pair is baseline-then-bypass: the direct spelling was always denied,
    and the ``&`` spelling was allowed. A test that only asserted the second
    half would pass against a hook that denies everything.
    """

    @pytest.mark.parametrize("command", [
        "sahjhan reseal --proof X",
        "sahjhan event quiz_exhausted_resolved --field project=holtz",
    ])
    def test_the_direct_spelling_is_denied(self, command):
        decision, _ = _decision(command)
        assert decision == "deny", "Baseline: the direct spelling must be denied"

    @pytest.mark.parametrize("command", [
        "true & sahjhan reseal --proof X",
        "true & sahjhan event quiz_exhausted_resolved --field project=holtz",
    ])
    def test_one_ampersand_does_not_reach_it(self, command):
        decision, _ = _decision(command)
        assert decision == "deny", (
            "A single '&' put a blocked subcommand past the guard: " + command
        )

    def test_an_allowed_subcommand_after_an_ampersand_is_still_allowed(self):
        """The guard reads the second segment — it must not merely deny it."""
        decision, reason = _decision("true & sahjhan status")
        assert decision == "allow", reason


@pytest.mark.hook_e2e
class TestAmpersandDoesNotReachProtectedPaths:
    """V1, the fifth line. ``enforcement/hooks/`` protects the hooks themselves."""

    def test_the_direct_spelling_is_denied(self):
        decision, _ = _decision("rm -rf enforcement/hooks")
        assert decision == "deny", "Baseline: the direct spelling must be denied"

    def test_one_ampersand_does_not_reach_it(self):
        decision, _ = _decision("true & rm -rf enforcement/hooks")
        assert decision == "deny", (
            "A single '&' reached the directory whose own docstring is "
            "'DO NOT MODIFY. This hook protects itself.'"
        )

    def test_ordinary_work_after_an_ampersand_is_still_allowed(self):
        decision, reason = _decision("true & grep -rn TODO src/")
        assert decision == "allow", reason


@pytest.mark.hook_e2e
class TestIndirectionDoesNotReachProtectedPaths:
    """V2. ``_check_bash_write`` parsed the raw string.

    ``_shell_norm``'s docstring claims ownership of indirection, and the
    sahjhan guard consulted it — but the guard protecting the directory that
    holds both of them did not. Two spellings walked past on that difference.
    """

    @pytest.mark.parametrize("command", [
        'eval "rm -rf enforcement/hooks"',
        "T=docs/holtz/.sahjhan; rm -rf $T",
        'eval "rm -rf docs/holtz/.sahjhan"',
        'bash -c "rm -rf enforcement/hooks"',
        'T=enforcement/hooks; rm -rf $T',
    ])
    def test_indirect_spellings_are_denied(self, command):
        decision, _ = _decision(command)
        assert decision == "deny", (
            f"Indirection reached a protected path: {command}"
        )

    def test_an_interpreter_flag_is_not_the_shell_builtin(self):
        """``node --eval`` is not ``eval``, and resolving it as one hid a write.

        The wrapper pattern matched ``eval`` inside ``--eval`` and rewrote
        ``node --eval "…"`` to ``node --require(…)``. That deleted the very
        flag the protected-path guard looks for to recognise an inline
        interpreter write, turning a block into an allow. Found by this
        unit's own regression run, not by review.
        """
        from _shell_norm import resolve_indirection

        cmd = "node --eval \"require('fs').writeFileSync('enforcement/x', 'y')\""
        assert resolve_indirection(cmd) == cmd
        decision, _ = _decision(cmd)
        assert decision == "deny"

    def test_ordinary_indirection_is_still_allowed(self):
        decision, reason = _decision('OUT=/tmp/x; grep -rn TODO src/ > $OUT')
        assert decision == "allow", reason


@pytest.mark.hook_e2e
class TestTheTwoGuardsTheReviewDidNotName:
    """V6b. Without these, V1–V3 can all pass with the allowlist still open.

    ``_daemon_lifecycle`` is registered under the ``Bash|Write|Edit|
    NotebookEdit`` matcher, so its recovery allowlist is consulted for every
    Bash call once an audit is terminated. Its docstring says a chained
    segment doing anything else "is denied" — but ``_DAEMON_RECOVERY_RE``
    ends ``(?:\\s+\\S+)*``, so in an unsplit segment ``rm -rf x`` reads as
    three more arguments to ``daemon start``.
    """

    def test_daemon_recovery_does_not_swallow_a_chained_command(self):
        import _daemon_lifecycle as dl

        def recovery(cmd: str) -> bool:
            return dl._is_recovery_command(
                {"tool_name": "Bash", "tool_input": {"command": cmd}}
            )

        assert recovery("sahjhan daemon start"), "Baseline: real recovery is exempt"
        assert not recovery("sahjhan daemon start && rm -rf x"), (
            "Baseline: '&&' was already refused"
        )
        assert not recovery("sahjhan daemon start & rm -rf x"), (
            "'&' classified arbitrary work as pure daemon recovery"
        )

    def test_the_taught_recovery_spellings_are_still_exempt(self):
        """The fix must not deny the recovery the primer tells a user to run."""
        import _daemon_lifecycle as dl

        for cmd in (
            "sahjhan daemon start",
            "nohup sahjhan daemon start &",
            "nohup sahjhan daemon start > /dev/null 2>&1 &",
            "sahjhan daemon stop",
        ):
            assert dl._is_recovery_command(
                {"tool_name": "Bash", "tool_input": {"command": cmd}}
            ), f"Recovery spelling wrongly denied: {cmd}"

    def test_a_long_sleep_behind_an_ampersand_is_detected(self):
        """The anti-gaming guard on timing gates."""
        import protocol_tracker as pt

        assert pt._is_sleep_cmd("sleep 600"), "Baseline"
        assert pt._is_sleep_cmd("true && sleep 600"), "Baseline: '&&' was caught"
        assert pt._is_sleep_cmd("true & sleep 600"), (
            "'&' defeated the guard against gaming timing gates"
        )
        assert not pt._is_sleep_cmd("true & sleep 1"), (
            "Short sleeps stay allowed — the guard is >5s, not any sleep"
        )


class TestSignalLosingSitesBehindAnAmpersand:
    """The other two of the eight. These lose evidence rather than open a hole.

    A commit the tracker cannot see is a commit the fix-loop gate cannot key
    on, and a test run it cannot see is TDD evidence that was never recorded.
    """

    def test_a_commit_behind_an_ampersand_is_visible(self):
        """V3. ``is_git_commit`` feeds both the commit gate and the tracker."""
        from _protocol_cache import is_git_commit

        assert is_git_commit("git commit -m x"), "Baseline"
        assert is_git_commit("true && git commit -m x"), "Baseline: '&&' was seen"
        assert is_git_commit("true & git commit -m x"), (
            "A commit behind '&' was invisible to the gate and the tracker"
        )

    def test_a_test_run_behind_an_ampersand_is_recorded(self):
        import commit_gate
        import protocol_tracker as pt

        assert pt._is_tdd_cmd("true & pytest tests/"), (
            "TDD evidence behind '&' was silently not recorded"
        )
        assert commit_gate._is_test_cmd("true & pytest tests/")

    def test_a_non_test_command_is_still_not_a_test_run(self):
        """Non-vacuity: the detectors must not have become 'always true'."""
        import commit_gate
        import protocol_tracker as pt

        assert not pt._is_tdd_cmd("true & echo pytest-is-mentioned-here")
        assert not commit_gate._is_test_cmd("true & echo pytest-is-mentioned-here")


class TestTheBootstrapTriggerSeesTheSecondSegment:
    """The eighth site. Missing it only skipped a download, but it is the same
    parser answering the same question, and a divergent eighth is PAT-001."""

    def test_a_sahjhan_command_behind_an_ampersand_is_found(self):
        from _sahjhan_bootstrap import _extract_sahjhan_subcmd

        segs = shell_segments("true & sahjhan init")
        assert any(_extract_sahjhan_subcmd(s) is not None for s in segs)


def test_the_hooks_still_import_and_run_standalone():
    """A shared import that fails at runtime is worse than eight copies.

    ``_shell_norm`` is imported by five hooks that Claude Code invokes as
    bare subprocesses, and there are two ``_common.py`` in this tree — an
    import that resolves in-process can still be wrong in a subprocess.
    """
    for hook in ("_daemon_lifecycle.py", "commit_gate.py", "protocol_tracker.py"):
        result = subprocess.run(
            [sys.executable, "-c",
             f"import sys; sys.path.insert(0, {HOOKS_DIR!r}); "
             f"import {os.path.splitext(hook)[0]}"],
            capture_output=True, text=True, timeout=30, cwd=REPO_ROOT,
        )
        assert result.returncode == 0, f"{hook} failed to import: {result.stderr}"


def test_json_tool_input_cannot_carry_the_mask():
    """The mask is NUL because a JSON string from the harness cannot hold one.

    If it could, a command containing it would survive the round trip as a
    literal ``&`` and re-open the split it was masking.
    """
    with pytest.raises(json.JSONDecodeError):
        json.loads('"a\x00b"')
