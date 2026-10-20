"""W25 / item 49 — the lower tail: small defects, one class per row.

Row d (``post_tool_hook`` never passed ``--agent-id``) landed with item 39 and
is pinned in ``test_hook_eval_reply.py``. The rest are here, each driven as a
subprocess where the thing under test is a hook's decision, and each RED on
the unmodified tree for the reason its docstring names.

Rulings that shape three of them (Jon, 2026-09-23): D-m, row a fails closed
while an audit is active; D-n, row c migrates; D-o, row g derives ``project``
and ``run`` and takes ``auditor`` from the acting agent.
"""
from __future__ import annotations

import ast
import os
import platform
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENFORCEMENT_HOOKS_DIR = os.path.join(REPO_ROOT, "enforcement", "hooks")
sys.path.insert(0, os.path.join(REPO_ROOT, "tests"))
sys.path.insert(0, ENFORCEMENT_HOOKS_DIR)

from _shell_norm import resolve_indirection  # noqa: E402
from git_env import scrubbed_env  # noqa: E402
from hook_runner import run_hook  # noqa: E402

ORCHESTRATOR = ""
SIBLING = "a7f3c2"


# ── Shared drivers ──────────────────────────────────────────────────────────


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()  # noqa: UP017


def _fix_loop_cache(**overrides) -> dict:
    cache = {
        "active": True,
        "state": "fix_loop",
        "unregistered_commits": {},
        "pattern_analysis_overdue": False,
        "perspective": "component",
        "perspectives_done": 1,
        "perspectives_total": 13,
        "stall": {},
        "last_refresh": _now(),
        "last_sahjhan_cmd": _now(),
    }
    cache.update(overrides)
    return cache


def _hook(name: str, event: dict, cwd: Path, env: dict | None = None) -> dict:
    return run_hook(
        os.path.join(ENFORCEMENT_HOOKS_DIR, name), event,
        cwd=str(cwd), env=env if env is not None else scrubbed_env(), timeout=30,
    )


def _bash(command: str, cwd: Path, actor: str = ORCHESTRATOR, **extra) -> dict:
    event = {
        "tool_name": "Bash",
        "tool_input": {"command": command},
        "tool_response": {"exit_code": 0, "stdout": "", "output": ""},
        "cwd": str(cwd),
        **extra,
    }
    if actor:
        event["agent_id"] = actor
    return event


def _denial(output: dict) -> str:
    hso = output.get("hookSpecificOutput", {})
    if hso.get("permissionDecision") != "deny":
        return ""
    return str(hso.get("permissionDecisionReason", ""))


def _context(output: dict) -> str:
    return str(output.get("hookSpecificOutput", {}).get("additionalContext", ""))


def _triple() -> str:
    arch = platform.machine()
    if arch == "arm64":
        arch = "aarch64"
    system = platform.system().lower()
    return {
        "darwin": f"{arch}-apple-darwin",
        "linux": f"{arch}-unknown-linux-gnu",
    }.get(system, f"{arch}-{system}")


def _stand_in(root: Path, body: str) -> Path:
    """A sahjhan at ``root/bin`` that logs its argv and runs ``body``.

    One argument per line and a ``----`` after each call, so fields survive
    intact for the test to read back.
    """
    log = root / "argv.log"
    bin_dir = root / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    binary = bin_dir / f"sahjhan-{_triple()}"
    binary.write_text(
        "#!/bin/sh\n"
        f"printf '%s\\n' \"$@\" >> '{log}'\n"
        f"echo ---- >> '{log}'\n"
        f"{body}\n"
    )
    binary.chmod(0o755)
    return log


def _calls(log: Path) -> list[list[str]]:
    if not log.exists():
        return []
    calls: list[list[str]] = [[]]
    for line in log.read_text().split("\n")[:-1]:
        if line == "----":
            calls.append([])
        else:
            calls[-1].append(line)
    return [c for c in calls if c]


def _docstring(path: str, function: str) -> str:
    """A function's docstring read off the source, not off an import.

    Two ``_common.py`` modules exist; importing the wrong one succeeds and
    answers a different question.
    """
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == function:
            return ast.get_docstring(node) or ""
    raise AssertionError(f"{function} not found in {path}")


def _string_constant(path: str, name: str) -> str:
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == name for t in node.targets
        ):
            value = ast.literal_eval(node.value)
            assert isinstance(value, str)
            return value
    raise AssertionError(f"{name} not found in {path}")


# ── Row a · an unresolvable `~` fails closed while an audit is active ──────


def _home_unresolved_env(**extra: str) -> dict:
    """An environment in which ``~`` expands to a relative path.

    A relative ``HOME`` reaches the same code as an unset one on a uid with
    no passwd entry — ``os.path.expanduser`` hands back something that is not
    absolute — and unlike that case it can be produced without root.
    """
    env = scrubbed_env(HOME="relative-home", **extra)
    env.pop("SAHJHAN_DAEMON_SOCKET", None)
    return env


@pytest.mark.hook_e2e
class TestRowAUnresolvedHomeFailsClosed:
    """With ``~`` unresolvable the socket path is relative to each hook's cwd.

    A hook at the arming cwd reached the refusing daemon and failed closed; a
    hook anywhere else — a subdirectory, a linked worktree — resolved a
    different relative path, found nothing, read "no audit" and allowed. The
    docstring called the whole case "failing closed".
    """

    def test_a_live_audit_blocks_and_names_home(self, tmp_path):
        (tmp_path / "docs" / "holtz" / ".sahjhan").mkdir(parents=True)
        output = _hook("commit_gate.py", _bash("ls", tmp_path), tmp_path,
                       env=_home_unresolved_env())
        reason = _denial(output)
        assert reason, f"an active audit with no reachable boundary allowed: {output}"
        assert "HOME" in reason, reason
        assert "ask the user to type `holtz-start`" not in reason, (
            "holtz-start needs the same path, so naming it as the fix sends "
            "the user round a loop"
        )

    def test_no_audit_is_left_alone(self, tmp_path):
        """The refusal is scoped by ``audit_active`` — a project with no audit
        must not be bricked by its environment."""
        output = _hook("commit_gate.py", _bash("ls", tmp_path), tmp_path,
                       env=_home_unresolved_env())
        assert _denial(output) == "", output

    def test_holtz_start_refuses_and_names_home(self, tmp_path):
        """The arming side says so too, before starting anything.

        A stand-in binary, so the unmodified tree cannot leave a real
        ``nohup``'d daemon bound at a relative path behind it.
        """
        _stand_in(tmp_path, "exit 0")
        output = _hook(
            "sandbox_control.py", {"prompt": "holtz-start", "cwd": str(tmp_path)},
            tmp_path, env=_home_unresolved_env(CLAUDE_PLUGIN_ROOT=str(tmp_path)),
        )
        reason = str(output.get("reason", ""))
        assert reason.startswith("HOLTZ-START FAILED"), output
        assert "HOME" in reason, reason

    def test_the_docstring_says_what_the_code_does(self):
        """``boundary_dir``'s account of this case names the mechanism that
        decides it, and no longer credits the fuse with it."""
        doc = _docstring(os.path.join(ENFORCEMENT_HOOKS_DIR, "_common.py"), "boundary_dir")
        assert "socket_unplaceable" in doc and "audit_active" in doc, doc
        assert "trips the fuse" not in doc, doc


# ── Row b · a failed read does not become an empty write ────────────────────


@pytest.mark.hook_e2e
class TestRowBAFailedReadWritesNothing:
    """``_apply_sahjhan_cmd`` built ``empty_cache()`` for any ``None`` read.

    ``None`` meant both "nothing is stored yet" (``not_found`` — the one case
    that must create the cache, and the tracker is its only creator) and "the
    read did not complete". A transient read failure followed by a successful
    write therefore persisted an empty cache over every pending commit and
    stall count.
    """

    def test_pending_commits_and_stall_survive_a_failed_read(self, tmp_path, mock_daemon):
        mock_daemon.state = _fix_loop_cache(
            unregistered_commits={ORCHESTRATOR: ["abc1234"], SIBLING: ["def5678"]},
            stall={ORCHESTRATOR: 7, SIBLING: 3},
        )
        mock_daemon.fail_reads = 1
        _hook("protocol_tracker.py", _bash("sahjhan status", tmp_path), tmp_path)
        assert mock_daemon.state["unregistered_commits"] == {
            ORCHESTRATOR: ["abc1234"], SIBLING: ["def5678"],
        }
        assert mock_daemon.state["stall"] == {ORCHESTRATOR: 7, SIBLING: 3}

    def test_nothing_stored_is_still_created(self, tmp_path, mock_daemon):
        """The creation path is untouched: ``not_found`` still writes the first
        cache. Green before the change, under it, and after."""
        assert mock_daemon.state is None
        _hook("protocol_tracker.py", _bash("sahjhan status", tmp_path), tmp_path)
        assert isinstance(mock_daemon.state, dict), "the first cache was not created"


# ── Row c · a pre-keying scalar stall migrates (D-n) ────────────────────────


@pytest.mark.hook_e2e
class TestRowCTheScalarStallMigrates:
    """RULED D-n: the old scalar lands in the orchestrator's bucket.

    Each number is distinct from every other quantity in play — the migrated
    16, the sibling's 1, the threshold of 15 — so a charge landing in the
    wrong bucket, a reset, or a sum cannot pass for the ruled outcome.
    """

    MIGRATED = 16

    def test_a_sibling_neither_inherits_nor_resets_it(self, tmp_path, mock_daemon):
        mock_daemon.state = _fix_loop_cache(stall=self.MIGRATED)
        _hook("protocol_tracker.py", _bash("touch x.py", tmp_path, SIBLING), tmp_path)
        assert mock_daemon.state["stall"] == {ORCHESTRATOR: self.MIGRATED, SIBLING: 1}

    def test_only_the_orchestrator_is_blocked_by_it(self, tmp_path, mock_daemon):
        mock_daemon.state = _fix_loop_cache(stall=self.MIGRATED)
        orchestrator = _denial(_hook("commit_gate.py", _bash("ls", tmp_path), tmp_path))
        sibling = _denial(_hook("commit_gate.py", _bash("ls", tmp_path, SIBLING), tmp_path))
        assert f"{self.MIGRATED} commands without a protocol event" in orchestrator
        assert sibling == ""

    def test_the_orchestrators_escape_clears_its_bucket_alone(self, tmp_path, mock_daemon):
        mock_daemon.state = _fix_loop_cache(stall={ORCHESTRATOR: self.MIGRATED, SIBLING: 1})
        _hook("protocol_tracker.py", _bash("sahjhan status", tmp_path), tmp_path)
        assert mock_daemon.state["stall"] == {SIBLING: 1}


# ── Row e · the block prints the obligation that blocked ────────────────────


@pytest.mark.hook_e2e
class TestRowEThePrintedEscapeIsTheBlockingOnes:
    """``blocks_all`` was ``any(...)`` but the message was ``obligations[0]``.

    With a pending commit *and* a stall, the stall is what blocks a non-commit
    command — and the message printed was the commit's ``fix_commit``
    remedy, which does nothing for a stall.
    """

    def _state(self) -> dict:
        return _fix_loop_cache(
            unregistered_commits={ORCHESTRATOR: ["abc1234"]},
            stall={ORCHESTRATOR: 16},
        )

    def test_the_stall_block_prints_the_stall_remedy(self, tmp_path, mock_daemon):
        mock_daemon.state = self._state()
        reason = _denial(_hook("commit_gate.py", _bash("ls", tmp_path), tmp_path))
        assert "16 commands without a protocol event" in reason, reason
        assert "fix_commit required" not in reason, reason

    def test_and_the_remedy_it_prints_runs(self, tmp_path, mock_daemon):
        """The escape is read out of the block and driven: the gate lets it
        through, and the tracker clears the stall it names."""
        mock_daemon.state = self._state()
        reason = _denial(_hook("commit_gate.py", _bash("ls", tmp_path), tmp_path))
        match = re.search(r"sahjhan --config-dir (\S+) command \(e\.g\. (\w+)\)", reason)
        assert match, reason
        escape = f"sahjhan --config-dir {match.group(1)} {match.group(2)}"
        assert _denial(_hook("commit_gate.py", _bash(escape, tmp_path), tmp_path)) == ""
        _hook("protocol_tracker.py", _bash(escape, tmp_path), tmp_path)
        assert mock_daemon.state["stall"].get(ORCHESTRATOR, 0) == 0
        assert mock_daemon.state["unregistered_commits"] == {ORCHESTRATOR: ["abc1234"]}


# ── Row f · the comment names the command the message names ─────────────────


class TestRowFTheBoundaryCommentAgreesWithTheMessage:
    """``commit_gate``'s comment named ``holtz-stop`` — which tears the
    boundary *down* — as the escape from a block whose message correctly says
    ``holtz-start``."""

    def test_they_name_the_same_word(self):
        source = Path(ENFORCEMENT_HOOKS_DIR, "commit_gate.py").read_text().splitlines()
        anchor = next(
            i for i, line in enumerate(source)
            if "if boundary and not audit_abandoned(cwd):" in line
        )
        comment = []
        for line in reversed(source[:anchor]):
            if not line.strip().startswith("#"):
                break
            comment.append(line)
        in_comment = set(re.findall(r"holtz-(?:start|stop)", "\n".join(comment)))
        message = _string_constant(os.path.join(ENFORCEMENT_HOOKS_DIR, "_common.py"),
                                   "BOUNDARY_MESSAGE")
        in_message = set(re.findall(r"holtz-(?:start|stop)", message))
        assert in_message == {"holtz-start"}, in_message
        assert in_comment == in_message, (in_comment, in_message)


# ── Row g · a violation is permanent only once it is on the ledger ──────────


_VERIFY_JSON = (
    '{"schema_version":1,"ok":true,"command":"manifest_verify",'
    '"data":{"clean":false,"tracked_count":2,"mismatches":['
    '{"path":"docs/holtz/STATUS.md","expected":"aaaa1111bbbb2222cccc",'
    '"actual":"dddd3333eeee4444ffff"}]}}'
)


def _guard_binary(root: Path, event_exit: int) -> Path:
    return _stand_in(root, (
        'case "$*" in\n'
        f"  *'manifest verify'*) echo '{_VERIFY_JSON}'; exit 2 ;;\n"
        "  *query*) echo '[]'; exit 0 ;;\n"
        f"  *'event protocol_violation'*) exit {event_exit} ;;\n"
        "esac\n"
        "exit 0"
    ))


def _violation_argv(log: Path) -> list[str]:
    writes = [c for c in _calls(log) if c[2:4] == ["event", "protocol_violation"]]
    assert len(writes) == 1, _calls(log)
    return writes[0]


def _fields(argv: list[str]) -> dict[str, str]:
    return dict(
        argv[i + 1].split("=", 1) for i, a in enumerate(argv) if a == "--field"
    )


@pytest.mark.hook_e2e
class TestRowGTheViolationRecord:
    """``bash_guard`` wrote the violation under ``contextlib.suppress`` with no
    return-code check, then called it "permanent" regardless — and wrote
    ``project=holtz``, ``run=0``, ``auditor=holtz`` into every project's
    ledger, three lines under a "derived, never mirrored" comment."""

    def _run(self, tmp_path, mock_daemon, event_exit: int, **event_extra) -> tuple[str, Path]:
        mock_daemon.state = _fix_loop_cache()
        (tmp_path / "docs" / "holtz" / ".sahjhan" / "active-ledger").write_text("run-7\n")
        log = _guard_binary(tmp_path, event_exit)
        output = _hook(
            "bash_guard.py", _bash("ls", tmp_path, **event_extra), tmp_path,
            env=scrubbed_env(CLAUDE_PLUGIN_ROOT=str(tmp_path)),
        )
        return _context(output), log

    def test_a_failed_write_is_not_called_permanent(self, tmp_path, mock_daemon):
        context, _ = self._run(tmp_path, mock_daemon, event_exit=1)
        assert "PROTOCOL VIOLATION" in context, context
        assert "permanent" not in context, context
        assert "could not be recorded" in context, context

    def test_a_recorded_write_is(self, tmp_path, mock_daemon):
        context, _ = self._run(tmp_path, mock_daemon, event_exit=0)
        assert "permanent" in context, context

    def test_project_and_run_are_derived(self, tmp_path, mock_daemon):
        _, log = self._run(tmp_path, mock_daemon, event_exit=0)
        fields = _fields(_violation_argv(log))
        assert fields["project"] == os.path.basename(os.path.realpath(tmp_path))
        assert fields["run"] == "7"

    @pytest.mark.parametrize(("agent_type", "auditor"), [
        (None, "holtz"),
        ("holtz:justine", "justine"),
        ("justine", "justine"),
        ("holtz:merge-agent", "holtz"),
    ], ids=["orchestrator", "namespaced-justine", "bare-justine", "merge-agent"])
    def test_the_auditor_is_the_acting_agent(self, tmp_path, mock_daemon, agent_type, auditor):
        extra = {"agent_type": agent_type} if agent_type else {}
        _, log = self._run(tmp_path, mock_daemon, event_exit=0, **extra)
        assert _fields(_violation_argv(log))["auditor"] == auditor


# ── Row h · an option's `k=v` operand is not a shell assignment ─────────────


class TestRowHFieldOperandsAreNotAssignments:
    """``resolve_indirection`` collected ``--field k=v`` as ``k=v`` and then
    substituted ``$k`` elsewhere on the line — so a guard reasoned about a
    command string nobody typed."""

    def test_a_field_operand_is_not_substituted(self):
        cmd = (
            'sahjhan event finding --field finding_id=BH-001 '
            '--field note="duplicate of $finding_id"'
        )
        assert resolve_indirection(cmd) == cmd

    def test_a_real_assignment_still_is(self):
        """Non-vacuity partner: the same line with a genuine assignment."""
        cmd = 'SAH=/opt/bin/sahjhan; "$SAH" status'
        assert "/opt/bin/sahjhan" in resolve_indirection(cmd).split(";", 1)[1]
