"""W25 / item 39 + item 49 row d — both hooks read `hook eval` one way.

`post_tool_hook` read the reply only ``if result.returncode == 0``, so a
non-zero exit fell through with ``eval_data = {}``: no auto-records, no
warning, nothing. A version fault — the binary refusing an argument it does
not know — exits 2 with an empty stdout, and every ``source_edit``,
``file_read`` and ``file_search`` stopped being recorded without a word. The
predicates that count them (the edit-accumulation warning, the stall
monitors) then read zero forever. `pre_tool_hook` handled the same reply
correctly, so the two hooks disagreed about one command's output.

A JSON *list* on stdout reached ``data.get`` in both hooks and raised
``AttributeError``, outside either except tuple: a traceback out of a hook.

A config or ledger that fails to load is not a decision. The engine answers
``ok: false`` with ``config_error`` or ``integrity_error`` and no ``data``, and
a reader that falls back to the whole reply for a missing ``data`` takes that
envelope for a payload whose ``decision`` defaults to ``allow`` — the same
silence, for a malformed ``protocol.toml`` or an unopened ledger.

The same two hooks disagreed about who is asking. `pre_tool_hook` always
passes ``--agent-id``; `post_tool_hook` never did, so every PostToolUse rule
and monitor was structurally run-global. Dormant only because no PostToolUse
rule templates ``{{agent_id}}`` today — the agreement test below is what keeps
that dormancy from going live silently.

Every test drives the real hook as a subprocess against a stand-in binary at
the path `sahjhan_binary()` resolves, which logs its argv so the test can read
exactly what each hook invoked — except the last class, which puts the pinned
engine itself at that path, so the replies are the ones holtz ships against.
"""
from __future__ import annotations

import os
import platform
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENFORCEMENT_HOOKS_DIR = os.path.join(REPO_ROOT, "enforcement", "hooks")
sys.path.insert(0, os.path.join(REPO_ROOT, "tests"))

from git_env import scrubbed_env  # noqa: E402
from hook_runner import run_hook  # noqa: E402

#: The degraded-mode marker `exit_enforcement_error` prefixes. Spelled out
#: rather than imported so an unmodified tree fails these tests on behaviour,
#: not at collection.
DEGRADED = "ENFORCEMENT DEGRADED: "

#: `sahjhan --json hook eval` replies no hook can act on, each as the body of
#: the stand-in's `hook eval` branch. The version fault is the one the engine
#: really produces: clap refuses an unknown flag with exit 2 and prints only to
#: stderr.
UNUSABLE_REPLIES = {
    "version_fault": (
        "echo \"error: unexpected argument '--agent-id' found\" >&2\n    exit 2"
    ),
    "json_list": "echo '[]'\n    exit 0",
    "data_is_a_list": "echo '{\"data\": []}'\n    exit 0",
    "not_json": "echo 'not json'\n    exit 0",
    "config_error": (
        "echo '{\"command\":\"hook_eval\",\"error\":{\"code\":\"config_error\","
        "\"message\":\"Configuration error: cannot read enforcement/protocol.toml: "
        "No such file or directory (os error 2)\"},\"ok\":false,\"schema_version\":1}'"
        "\n    exit 3"
    ),
    "integrity_error": (
        "echo '{\"command\":\"hook_eval\",\"error\":{\"code\":\"integrity_error\","
        "\"message\":\"Cannot open ledger: I/O error: No such file or directory "
        "(os error 2)\"},\"ok\":false,\"schema_version\":1}'\n    exit 2"
    ),
}

#: The engine's refusal for a sealed config edited after ``init``, as sahjhan
#: prints it: the files that moved, then the only two ways past. ``printf %s``
#: rather than ``echo``, which expands the JSON's ``\n`` escapes under dash.
SEAL_REFUSAL = (
    "printf '%s\\n' '{\"command\":\"hook_eval\",\"error\":{\"code\":\"integrity_error\","
    "\"message\":\"config integrity violation:\\n  - states.toml (expected: "
    "f51f63fb0fbf..., found: d814618523d0...)\\n\\nRun \\u0027sahjhan reseal\\u0027 "
    "with a valid session key to update the seal,\\nor restore the files above to "
    "their sealed contents.\"},\"ok\":false,\"schema_version\":1}'\n    exit 2"
)

#: What the engine prints for an Edit that the auto-record rule matches.
SUCCESS_REPLY = (
    "echo '{\"command\":\"hook_eval\",\"data\":{\"auto_records\":"
    "[{\"event_type\":\"source_edit\",\"fields\":{\"file\":\"src/app.py\"}}],"
    "\"decision\":\"allow\",\"messages\":[],\"monitor_warnings\":[]},"
    "\"ok\":true,\"schema_version\":1}'\n    exit 0"
)


def _triple() -> str:
    arch = platform.machine()
    if arch == "arm64":
        arch = "aarch64"
    system = platform.system().lower()
    return {
        "darwin": f"{arch}-apple-darwin",
        "linux": f"{arch}-unknown-linux-gnu",
    }.get(system, f"{arch}-{system}")


def _stand_in(tmp_path: Path, hook_eval_body: str) -> Path:
    """A sahjhan whose `hook eval` runs ``hook_eval_body``; the rest exit 0.

    Every invocation's argv is appended to ``argv.log``, one argument per line
    and a ``----`` line after each call, so an empty argument (the
    orchestrator's ``--agent-id ""``) survives as an empty line.
    """
    log = tmp_path / "argv.log"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    binary = bin_dir / f"sahjhan-{_triple()}"
    binary.write_text(
        "#!/bin/sh\n"
        f"printf '%s\\n' \"$@\" >> '{log}'\n"
        f"echo ---- >> '{log}'\n"
        'case "$*" in\n'
        "  *'hook eval'*)\n"
        f"    {hook_eval_body}\n"
        "    ;;\n"
        "esac\n"
        "exit 0\n"
    )
    binary.chmod(0o755)
    return log


def _calls(log: Path) -> list[list[str]]:
    """Each logged invocation's argv, in order."""
    if not log.exists():
        return []
    calls: list[list[str]] = [[]]
    for line in log.read_text().split("\n")[:-1]:
        if line == "----":
            calls.append([])
        else:
            calls[-1].append(line)
    return [c for c in calls if c]


def _hook_eval_argv(log: Path) -> list[str]:
    evals = [c for c in _calls(log) if "hook" in c and "eval" in c]
    assert len(evals) == 1, f"expected one `hook eval` call, got {_calls(log)}"
    return evals[0]


def _fresh_state() -> dict:
    now = datetime.now(timezone.utc).isoformat()  # noqa: UP017
    return {
        "active": True,
        "state": "fix_loop",
        "unregistered_commits": {},
        "pattern_analysis_overdue": False,
        "perspective": "component",
        "perspectives_done": 1,
        "perspectives_total": 13,
        "stall": {},
        "last_refresh": now,
        "last_sahjhan_cmd": now,
    }


def _edit_event(tmp_path: Path, agent_id: str | None = None) -> dict:
    source = tmp_path / "src" / "app.py"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("x = 1\n")
    event = {
        "tool_name": "Edit",
        "tool_input": {"file_path": str(source), "old_string": "x", "new_string": "y"},
        "cwd": str(tmp_path),
    }
    if agent_id is not None:
        event["agent_id"] = agent_id
    return event


def _run(hook: str, tmp_path: Path, event: dict) -> dict:
    env = scrubbed_env(CLAUDE_PLUGIN_ROOT=str(tmp_path))
    return run_hook(
        os.path.join(ENFORCEMENT_HOOKS_DIR, hook), event,
        cwd=str(tmp_path), env=env, timeout=30,
    )


def _post_context(output: dict) -> str:
    return str(output.get("hookSpecificOutput", {}).get("additionalContext", ""))


def _pre_denial(output: dict) -> str:
    hso = output.get("hookSpecificOutput", {})
    if hso.get("permissionDecision") != "deny":
        return ""
    return str(hso.get("permissionDecisionReason", ""))


@pytest.fixture
def live_audit(tmp_path, mock_daemon):
    """A fresh, active audit — the only state in which degrading is loud."""
    mock_daemon.state = _fresh_state()
    return tmp_path


@pytest.mark.hook_e2e
class TestPostToolUseDoesNotDegradeInSilence:
    """V3, V4, V5 — the PostToolUse half, one reply shape per test."""

    def test_a_version_fault_says_so(self, live_audit):
        """V3 — exit 2, empty stdout: a warning naming the exit and the cause.

        Silence is the defect, so the assertion is on the message, not on the
        absence of a crash: the unmodified hook exits 0 cleanly here and says
        nothing at all.
        """
        _stand_in(live_audit, UNUSABLE_REPLIES["version_fault"])
        output = _run("post_tool_hook.py", live_audit, _edit_event(live_audit))
        context = _post_context(output)
        assert output["_returncode"] == 0, output
        assert DEGRADED in context, f"no degraded-mode signal: {output}"
        assert "exit 2" in context, context
        assert "unexpected argument" in context, (
            "the engine's own diagnosis should reach the model — it is the "
            "difference between 'reinstall the binary' and 'wait it out'"
        )

    def test_a_json_list_warns_rather_than_raising(self, live_audit):
        """V5 — ``[]`` on stdout: exit 0, a warning, and no traceback."""
        _stand_in(live_audit, UNUSABLE_REPLIES["json_list"])
        output = _run("post_tool_hook.py", live_audit, _edit_event(live_audit))
        assert "Traceback" not in output["_stderr"], output["_stderr"]
        assert output["_returncode"] == 0, output
        assert DEGRADED in _post_context(output), output

    def test_the_success_path_still_records_the_edit(self, live_audit):
        """V4 — a usable reply's auto-record still reaches the ledger.

        Read off the stand-in's argv log: the hook must have run
        ``event source_edit`` with the enriched fields, and warned about
        nothing.
        """
        log = _stand_in(live_audit, SUCCESS_REPLY)
        output = _run("post_tool_hook.py", live_audit, _edit_event(live_audit))
        assert DEGRADED not in _post_context(output), output
        records = [c for c in _calls(log) if c[2:4] == ["event", "source_edit"]]
        assert len(records) == 1, _calls(log)
        assert "--field" in records[0] and "edit_type=partial" in records[0], records


@pytest.mark.hook_e2e
class TestTheTwoHooksAgree:
    """V6 and row d — one reply, one answer, from either side of the tool call."""

    @pytest.mark.parametrize("reply", sorted(UNUSABLE_REPLIES))
    def test_they_degrade_on_the_same_replies_for_the_same_reason(
        self, live_audit, reply,
    ):
        """Pre blocks and Post warns — and the reason after the marker matches.

        A hook cannot choose its own severity here: PreToolUse can still stop
        the call, PostToolUse fires after the work is done. What must not
        differ is *whether* each degrades and *what it says caused it*.
        """
        _stand_in(live_audit, UNUSABLE_REPLIES[reply])
        pre = _pre_denial(_run("pre_tool_hook.py", live_audit, _edit_event(live_audit)))
        post = _post_context(_run("post_tool_hook.py", live_audit, _edit_event(live_audit)))
        assert DEGRADED in pre, f"pre_tool_hook did not degrade on {reply}: {pre!r}"
        assert DEGRADED in post, f"post_tool_hook did not degrade on {reply}: {post!r}"
        assert pre.split(DEGRADED, 1)[1] == post.split(DEGRADED, 1)[1]

    @pytest.mark.parametrize("agent_id", ["a7f3c2", None], ids=["subagent", "orchestrator"])
    def test_they_name_the_same_actor(self, live_audit, agent_id):
        """Row d — both pass ``--agent-id``, with the same value.

        The orchestrator is the empty-string actor, a real bucket, so the flag
        is passed with ``""`` rather than omitted.
        """
        expected = agent_id or ""
        seen = {}
        for hook in ("pre_tool_hook.py", "post_tool_hook.py"):
            log = _stand_in(live_audit, SUCCESS_REPLY)
            log.unlink(missing_ok=True)
            _run(hook, live_audit, _edit_event(live_audit, agent_id))
            argv = _hook_eval_argv(log)
            assert "--agent-id" in argv, f"{hook} did not pass --agent-id: {argv}"
            seen[hook] = argv[argv.index("--agent-id") + 1]
        assert seen == {"pre_tool_hook.py": expected, "post_tool_hook.py": expected}


@pytest.mark.hook_e2e
class TestALoadFailureIsNotAnAllow:
    """Item 39's config-fault half — ``ok: false`` is a reason, never a payload."""

    @pytest.mark.parametrize(
        ("reply", "exit_code"), [("config_error", 3), ("integrity_error", 2)],
    )
    def test_the_warning_names_the_exit_the_code_and_the_engine_message(
        self, live_audit, reply, exit_code,
    ):
        """No rule ran, and the warning says which load failed and why."""
        _stand_in(live_audit, UNUSABLE_REPLIES[reply])
        output = _run("post_tool_hook.py", live_audit, _edit_event(live_audit))
        context = _post_context(output)
        assert output["_returncode"] == 0, output
        assert DEGRADED in context, f"a load failure read as an allow: {output}"
        assert f"exit {exit_code}" in context, context
        assert reply in context, context
        assert "No such file or directory" in context, (
            "the engine's own message should reach the model — it names the "
            "file that did not load"
        )

    def test_the_seal_refusal_carries_the_engine_s_way_past_it(self, live_audit):
        """A sealed file edited mid-audit blocks, and the block names the escape.

        No holtz path reseals a ledger: ``reseal`` needs the session key. The
        engine's message is the only place the two ways past are written, so
        it reaches the model whole rather than as its first line, which is
        just ``config integrity violation:``.
        """
        _stand_in(live_audit, SEAL_REFUSAL)
        denial = _pre_denial(_run("pre_tool_hook.py", live_audit, _edit_event(live_audit)))
        assert DEGRADED in denial, f"a seal refusal read as an allow: {denial!r}"
        assert "states.toml" in denial, denial
        assert "sahjhan reseal" in denial, denial
        assert "restore the files above" in denial, denial


def _pinned_engine() -> str:
    """The sahjhan `_resolve.SAHJHAN_VERSION` names, fetched if it is missing."""
    sys.path.insert(0, ENFORCEMENT_HOOKS_DIR)
    from _resolve import ensure_sahjhan  # noqa: PLC0415

    binary = ensure_sahjhan()
    if not binary:
        pytest.skip("sahjhan binary not available")
    return binary


@pytest.mark.slow
@pytest.mark.hook_e2e
class TestThePinnedEngineReportsALoadFailure:
    """Driven — the pinned engine, a project whose config or ledger will not load.

    The stand-ins above prove the hooks read ``ok: false`` as a failure; this
    proves the engine holtz pins sends one. Against an engine that answers a
    load failure with an allow, both hooks pass the call in silence.
    """

    @pytest.mark.parametrize(
        ("project", "code"),
        [("malformed_protocol", "config_error"), ("ledger_never_opened", "integrity_error")],
    )
    def test_both_hooks_degrade(self, live_audit, project, code):
        config = live_audit / "enforcement"
        config.mkdir()
        if project == "malformed_protocol":
            (config / "protocol.toml").write_text("garbage = [\n")
        else:
            for toml in Path(REPO_ROOT, "enforcement").glob("*.toml"):
                shutil.copy(toml, config / toml.name)
        bin_dir = live_audit / "bin"
        bin_dir.mkdir()
        # No version marker beside it, so `ensure_sahjhan` uses it as found.
        (bin_dir / f"sahjhan-{_triple()}").symlink_to(_pinned_engine())

        pre = _pre_denial(_run("pre_tool_hook.py", live_audit, _edit_event(live_audit)))
        post = _post_context(_run("post_tool_hook.py", live_audit, _edit_event(live_audit)))
        assert DEGRADED in pre, f"pre_tool_hook let the call through: {pre!r}"
        assert DEGRADED in post, f"post_tool_hook said nothing: {post!r}"
        assert code in pre, pre
        assert pre.split(DEGRADED, 1)[1] == post.split(DEGRADED, 1)[1]
