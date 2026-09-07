"""P0.5's second route (D29/D34/D35): `fault_injected` batches into one
hardening commit per module.

~22 of the audited run's 62 commits were fault-injection-only — reachable only
by making some other call raise — each taking a full fix cycle, while 51 of its
75 open HIGHs predated the first commit and were never worked at all. The
clause's answer is not to ignore those defects but to stop paying a fix cycle
each: one hardening commit disposes of a whole module's worth.

Three rulings shape what is built here, and none of them was free:

* **D35 — a module is the containing directory.** `location` is free text
  (`file.py:88`, `` `file.py:88` ``, `file.py:88 (function f)` all appear in
  this repo's archived ledgers), so the rule is applied in Python and the
  ledger holds the *result*.
* **The courier closes them (Jon, 2026-08-25).** `EmitConfig`
  (sahjhan `src/config/transitions.rs:101`) produces exactly one event with a
  fixed field map and `emits` is not a fan-out, so no transition can write one
  `finding_resolved` per batched id. A courier can, and does — keeping D29's
  "exactly one definition of closed".
* **The batch runs before `converge`, and `converge` is what compels it
  (Jon, 2026-08-25).** The spec says "at finalize", but `all_critical_resolved`
  gates `converge`, carries no reachability filter and refuses a deferral: a
  `fault_injected` CRITICAL blocks two transitions *upstream* of `finalize`, so
  a batch that ran there could never be reached by the run that needed it.
  Observed against a real daemon, not inferred.

The tests are organised around what would make a batch a lie: a module nobody
filed against, a commit that names the wrong findings, a commit already spent
on another module, and a population read from the command instead of the
ledger.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_DIR = os.path.join(REPO_ROOT, "enforcement")
HOOKS_DIR = os.path.join(REPO_ROOT, "enforcement", "hooks")
SCRIPTS_DIR = os.path.join(REPO_ROOT, "enforcement", "scripts")
sys.path.insert(0, SCRIPTS_DIR)
sys.path.insert(0, HOOKS_DIR)

import hardening_batch as hb  # noqa: E402

_COMMON = ["--field", "project=t", "--field", "run=1", "--field", "auditor=holtz",
           "--field", "phase=audit", "--field", "step=8"]

_SCRIPT = os.path.join(SCRIPTS_DIR, "hardening_batch.py")
_COURIER = os.path.join(HOOKS_DIR, "hardening_batch_courier.py")
_THEORETICAL_COURIER = os.path.join(HOOKS_DIR, "theoretical_courier.py")

_CONVERGENCE_DOC = os.path.join(
    REPO_ROOT, "skills", "holtz", "references", "phase-convergence.md")


def _binary():
    from _resolve import ensure_sahjhan  # noqa: PLC0415

    binary = ensure_sahjhan()
    if not binary:
        pytest.skip("sahjhan binary not available")
    return binary


def _named_query(name):
    from _protocol_cache import named_query_sql  # noqa: PLC0415

    sql = named_query_sql(CONFIG_DIR, name)
    assert sql, f"protocol.toml has no [queries.{name}]"
    return sql


# ── D35: a module is the containing directory ────────────────────────────────


class TestModuleOf:
    """The one place the directory rule is applied. Everything downstream is
    id membership, so this is where a wrong answer becomes a wrong ledger."""

    def test_a_plain_location(self):
        assert hb.module_of("tqdm/std.py:736") == "tqdm"

    def test_siblings_batch_together(self):
        assert hb.module_of("tqdm/utils.py:240") == hb.module_of("tqdm/std.py:736")

    def test_a_subdirectory_is_its_own_module(self):
        """D35's own worked example: `tqdm/contrib/x.py:12` is not `tqdm`."""
        assert hb.module_of("tqdm/contrib/x.py:12") == "tqdm/contrib"

    def test_a_backticked_location(self):
        assert hb.module_of("`tqdm/std.py:736`") == "tqdm"

    def test_a_location_naming_a_symbol(self):
        assert hb.module_of("tqdm/std.py:736 (function update)") == "tqdm"

    def test_a_root_file_is_the_root_module(self):
        assert hb.module_of("setup.py:12") == "."

    def test_a_location_with_no_line(self):
        assert hb.module_of("tqdm/std.py") == "tqdm"

    def test_an_unplaceable_location_has_no_module(self):
        """A finding nobody can place must not be silently bucketed into the
        root module, where an unrelated commit would close it."""
        assert hb.module_of("") is None
        assert hb.module_of("   ") is None
        assert hb.module_of(":88") is None


# ── The board ────────────────────────────────────────────────────────────────


class _Board:
    """A git tree with a ledger, driven the way the skill files drive one."""

    def __init__(self, root, config_dir=CONFIG_DIR, env=None):
        self.binary = _binary()
        self.root = root
        self.config_dir = config_dir
        self.env = env or dict(os.environ)
        subprocess.run(["git", "init", "-q", root], check=True, capture_output=True)
        for args in (["config", "user.email", "t@example.com"],
                     ["config", "user.name", "t"]):
            subprocess.run(["git", "-C", root, *args], check=True, capture_output=True)
        if not os.path.exists(os.path.join(root, "docs", "holtz", ".sahjhan")):
            subprocess.run(
                [self.binary, "--config-dir", config_dir, "init"],
                cwd=root, capture_output=True, text=True, timeout=60, check=True,
            )
        self.commit("root")

    def sah(self, *args, check=True):
        result = subprocess.run(
            [self.binary, "--config-dir", self.config_dir, *args],
            cwd=self.root, capture_output=True, text=True, timeout=60,
        )
        if check:
            assert result.returncode == 0, f"{args}\n{result.stdout}\n{result.stderr}"
        return result

    def git(self, *args, check=True):
        return subprocess.run(["git", "-C", self.root, *args], check=check,
                              capture_output=True, text=True)

    def write(self, rel, text="x\n"):
        path = os.path.join(self.root, rel)
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)

    def commit(self, message, touching=("a.txt",)):
        for rel in touching:
            self.write(rel, message)
        self.git("add", *touching)
        self.git("commit", "-q", "--allow-empty", "-m", message)
        return self.git("rev-parse", "--short=7", "HEAD").stdout.strip()

    def file(self, finding_id, location, reachability="fault_injected",
             severity="HIGH", perspective="component"):
        self.sah("event", "finding", "--field", f"id={finding_id}",
                 "--field", f"severity={severity}", "--field", "category=bug/logic",
                 "--field", f"location={location}", "--field", f"perspective={perspective}",
                 "--field", "predicted_by=none", "--field", f"reachability={reachability}",
                 "--field", "description=x", *_COMMON)

    def resolve(self, finding_id, commit_hash="abc1234"):
        self.sah("event", "finding_resolved", "--field", f"id={finding_id}",
                 "--field", f"commit_hash={commit_hash}", *_COMMON)

    def defer(self, finding_id, reason="low_priority"):
        self.sah("event", "finding_deferred", "--field", f"id={finding_id}",
                 "--field", f"reason={reason}", *_COMMON)

    def resolutions(self):
        result = self.sah("query", "--type", "finding_resolved", "--format", "jsonl")
        rows = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
        return [{**row.get("fields", {}), **{k: v for k, v in row.items()
                                             if k != "fields"}} for row in rows]

    def answer(self, name):
        out = self.sah("query", _named_query(name), "--format", "json").stdout
        return str(list(json.loads(out)[0].values())[0])

    # ── the two ends, both as subprocesses ──

    def show(self):
        """The module -> ids map, through `--show`.

        A subprocess, not an import. Two different `_common.py` modules ship in
        this tree and whichever an earlier test reaches first wins for the whole
        pytest process — the import still *succeeds*, the config resolves to the
        repo root, and every query comes back empty. Negatives would then pass
        vacuously.
        """
        result = subprocess.run(
            [sys.executable, _SCRIPT, "--show", "--cwd", self.root],
            capture_output=True, text=True, timeout=60, env=self.env,
        )
        assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"
        return json.loads(result.stdout)

    def record(self, module):
        """The recorded form, which no longer takes `--cwd` (item 34).

        The flag and `--record` together exit 0 and record nothing, so the
        parser refuses the pair. Pointing the *process* at the board is what
        the agent does anyway — it runs from the project directory — so this
        is the production shape rather than a concession to the check.
        """
        return subprocess.run(
            [sys.executable, _SCRIPT, "--record", "--module", module],
            cwd=self.root,
            capture_output=True, text=True, timeout=60, env=self.env,
        )

    def courier(self, module, output, exit_code=0):
        command = (
            f'python3 "${{CLAUDE_PLUGIN_ROOT}}/enforcement/scripts/hardening_batch.py" '
            f"--record --module {module}"
        )
        return subprocess.run(
            [sys.executable, _COURIER],
            input=json.dumps({
                "tool_name": "Bash",
                "tool_input": {"command": command},
                "tool_response": {"output": output, "exit_code": exit_code},
                "cwd": self.root,
            }),
            capture_output=True, text=True, timeout=60, env=self.env,
            cwd=self.root,
        )

    def defer_by_courier(self):
        """Fire `theoretical_courier.py`, which is the only writer of a
        deferral the theoretical exclusion counts.

        `defer(id, reason="theoretical")` types the same field values through
        the CLI, and the two rows are identical in `fields`. They differ in
        `recorded_by`: the engine stamps the CLI write `agent:cli` and stamps
        this one `hook:hooks/theoretical_courier.py`, because the daemon
        verified the peer against `trusted-callers.toml` before appending.

        Needs a real daemon — `record_event` from an unverified caller is
        refused — so callers use the `live` board, not `board`.
        """
        return subprocess.run(
            [sys.executable, _THEORETICAL_COURIER],
            input=json.dumps({
                "tool_name": "Bash",
                "tool_input": {"command": "sahjhan event finding --field id=x"},
                "tool_response": {"output": "", "exit_code": 0},
                "cwd": self.root,
            }),
            capture_output=True, text=True, timeout=60, env=self.env,
            cwd=self.root,
        )

    def batch(self, module, touching):
        """Make the hardening commit, record it, and let the courier close."""
        ids = self.show()[module]
        self.commit(f"harden {module}: {' '.join(ids)}", touching=touching)
        record = self.record(module)
        assert record.returncode == 0, f"{record.stdout}\n{record.stderr}"
        courier = self.courier(module, record.stdout)
        assert courier.returncode == 0, courier.stderr
        assert "NOT recorded" not in courier.stdout, courier.stdout
        return record.stdout


@pytest.fixture
def board(tmp_path):
    """Read-side only: derivation, refusals and the gate's own answer."""
    return _Board(str(tmp_path))


@pytest.fixture
def live(real_daemon):
    """The write side, against a daemon that authenticates the caller.

    `mock_daemon` reimplements the ops without hash auth, so a mock-only suite
    stays green while a stale `trusted-callers.toml` has silently disabled the
    write. Only this shape catches that.
    """
    return _Board(
        real_daemon["project_root"],
        config_dir=real_daemon["config_dir"],
        env={**os.environ, "SAHJHAN_DAEMON_SOCKET": real_daemon["sock_path"]},
    )


class TestPopulation:
    """Every open finding whose latest filing grades it `fault_injected`,
    grouped by containing directory."""

    def test_open_fault_injected_findings_group_by_directory(self, board):
        board.file("BH-001", "tqdm/std.py:736")
        board.file("BH-002", "tqdm/utils.py:240")
        board.file("BH-003", "tqdm/contrib/x.py:12")
        assert board.show() == {
            "tqdm": ["BH-001", "BH-002"],
            "tqdm/contrib": ["BH-003"],
        }

    def test_a_user_reachable_finding_is_not_in_it(self, board):
        board.file("BH-001", "tqdm/std.py:736")
        board.file("BH-002", "tqdm/utils.py:240", reachability="user_reachable")
        assert board.show() == {"tqdm": ["BH-001"]}

    def test_a_theoretical_finding_is_not_in_it(self, board):
        """Its route is the auto-deferral courier, not a hardening commit."""
        board.file("BH-001", "tqdm/std.py:736")
        board.file("BH-002", "tqdm/utils.py:240", reachability="theoretical")
        assert board.show() == {"tqdm": ["BH-001"]}

    def test_a_resolved_finding_is_not_in_it(self, board):
        board.file("BH-001", "tqdm/std.py:736")
        board.file("BH-002", "tqdm/utils.py:240")
        board.resolve("BH-002")
        assert board.show() == {"tqdm": ["BH-001"]}

    def test_a_deferred_finding_is_not_in_it(self, board):
        """Deferral is the other way off the board, and it already exists."""
        board.file("BH-001", "tqdm/std.py:736")
        board.file("BH-002", "tqdm/utils.py:240")
        board.defer("BH-002")
        assert board.show() == {"tqdm": ["BH-001"]}

    def test_a_regrade_off_fault_injected_leaves_the_population(self, board):
        """Reachability is the latest filing (D25)."""
        board.file("BH-001", "tqdm/std.py:736")
        board.file("BH-002", "tqdm/utils.py:240")
        board.file("BH-002", "tqdm/utils.py:240", reachability="user_reachable")
        assert board.show() == {"tqdm": ["BH-001"]}

    def test_a_regrade_onto_fault_injected_joins_it(self, board):
        board.file("BH-001", "tqdm/std.py:736", reachability="user_reachable")
        board.file("BH-002", "tqdm/utils.py:240")
        board.file("BH-001", "tqdm/std.py:736")
        assert board.show() == {"tqdm": ["BH-001", "BH-002"]}

    def test_a_relocated_finding_moves_module(self, board):
        """The latest filing decides `location` too, so a corrected path must
        move the finding into the batch that will actually harden it."""
        board.file("BH-001", "tqdm/std.py:736")
        board.file("BH-001", "tqdm/contrib/x.py:12")
        assert board.show() == {"tqdm/contrib": ["BH-001"]}


# ── What `--record` refuses ──────────────────────────────────────────────────


class TestRecordRefusals:
    """A batch that cost nothing would retire the board for free. Each refusal
    below is a way that could happen."""

    def test_it_accepts_a_commit_naming_the_whole_module(self, board):
        board.file("BH-001", "tqdm/std.py:736")
        board.file("BH-002", "tqdm/utils.py:240")
        board.commit("harden tqdm: BH-001 BH-002", touching=["tqdm/std.py"])
        result = board.record("tqdm")
        assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"
        assert hb.RECORD_MARKER in result.stdout

    def test_it_refuses_a_module_nobody_filed_against(self, board):
        board.file("BH-001", "tqdm/std.py:736")
        board.commit("harden nothing: BH-001", touching=["other/z.py"])
        result = board.record("other")
        assert result.returncode != 0
        assert "no open fault_injected" in result.stderr

    def test_it_refuses_a_commit_that_names_only_some_of_the_module(self, board):
        """"One hardening commit per module" is the clause. A commit closing
        half a directory would leave the rest to a second commit and the
        saving with it."""
        board.file("BH-001", "tqdm/std.py:736")
        board.file("BH-002", "tqdm/utils.py:240")
        board.commit("harden tqdm: BH-001", touching=["tqdm/std.py"])
        result = board.record("tqdm")
        assert result.returncode != 0
        assert "BH-002" in result.stderr

    def test_it_refuses_a_commit_that_names_another_module(self, board):
        """One commit, one module — otherwise a single commit disposes of the
        whole board and the per-module rule is decoration."""
        board.file("BH-001", "tqdm/std.py:736")
        board.file("BH-003", "tqdm/contrib/x.py:12")
        board.commit("harden everything: BH-001 BH-003", touching=["tqdm/std.py"])
        result = board.record("tqdm")
        assert result.returncode != 0
        assert "BH-003" in result.stderr

    def test_it_refuses_a_commit_already_spent(self, board):
        """The same HEAD must not close two modules. Without this the second
        batch is free."""
        board.file("BH-001", "tqdm/std.py:736")
        commit = board.commit("harden tqdm: BH-001", touching=["tqdm/std.py"])
        board.resolve("BH-999", commit_hash=commit)
        result = board.record("tqdm")
        assert result.returncode != 0
        assert "already" in result.stderr

    def test_it_refuses_an_empty_commit(self, board):
        """A message is cheap; a diff is the work."""
        board.file("BH-001", "tqdm/std.py:736")
        board.git("commit", "-q", "--allow-empty", "-m", "harden tqdm: BH-001")
        result = board.record("tqdm")
        assert result.returncode != 0
        assert "no changes" in result.stderr

    def test_it_refuses_a_finding_it_cannot_place(self, board):
        """An unplaceable finding has no module, so no batch can ever cover
        it and `converge` would block forever. Refusing here names it while
        the escape — re-file it with a real location — is still cheap."""
        board.file("BH-001", "tqdm/std.py:736")
        board.file("BH-002", ":88")
        board.commit("harden tqdm: BH-001", touching=["tqdm/std.py"])
        result = board.record("tqdm")
        assert result.returncode != 0
        assert "BH-002" in result.stderr


# ── The courier is what closes them ──────────────────────────────────────────


@pytest.mark.slow
@pytest.mark.integration
@pytest.mark.hook_e2e
class TestTheCourierCloses:
    """`finding_resolved` is written once per covered id, by the hook — the
    only shape the engine leaves open, since `emits` is not a fan-out."""

    def test_every_id_in_the_module_is_resolved(self, live):
        live.file("BH-001", "tqdm/std.py:736")
        live.file("BH-002", "tqdm/utils.py:240")
        live.batch("tqdm", ["tqdm/std.py"])
        assert sorted(row["id"] for row in live.resolutions()) == ["BH-001", "BH-002"]

    def test_another_module_survives_the_batch(self, live):
        """The negative that must not be an empty set: a dead query and a
        correct exclusion are indistinguishable when both return nothing."""
        live.file("BH-001", "tqdm/std.py:736")
        live.file("BH-003", "tqdm/contrib/x.py:12")
        live.batch("tqdm", ["tqdm/std.py"])
        assert live.show() == {"tqdm/contrib": ["BH-003"]}

    def test_the_hardening_commit_is_the_recorded_hash(self, live):
        live.file("BH-001", "tqdm/std.py:736")
        live.batch("tqdm", ["tqdm/std.py"])
        head = live.git("rev-parse", "--short=7", "HEAD").stdout.strip()
        assert [row["commit_hash"] for row in live.resolutions()] == [head]

    def test_the_resolution_is_stamped_with_the_step_that_teaches_it(self, live):
        live.file("BH-001", "tqdm/std.py:736")
        live.batch("tqdm", ["tqdm/std.py"])
        row = live.resolutions()[0]
        assert row["phase"] == hb.BATCH_PHASE
        assert row["step"] == hb.BATCH_STEP
        assert row["project"] == "t"
        assert row["run"] == "1"
        assert row["auditor"] == "holtz"

    def test_a_failed_command_records_nothing(self, live):
        live.file("BH-001", "tqdm/std.py:736")
        live.commit("harden tqdm: BH-001", touching=["tqdm/std.py"])
        record = live.record("tqdm")
        live.courier("tqdm", record.stdout, exit_code=1)
        assert live.resolutions() == []

    def test_a_command_without_the_marker_records_nothing(self, live):
        """The host says it succeeded; the script never got far enough to
        check the board. Both signals are required."""
        live.file("BH-001", "tqdm/std.py:736")
        live.commit("harden tqdm: BH-001", touching=["tqdm/std.py"])
        result = live.courier("tqdm", "some other output")
        assert live.resolutions() == []
        assert "NOT recorded" in result.stdout

    def test_the_courier_re_derives_rather_than_trusting_the_command(self, live):
        """The command text is the wake-up; the ledger decides. A module named
        on the command line that the board does not carry closes nothing."""
        live.file("BH-001", "tqdm/std.py:736")
        live.commit("harden tqdm: BH-001", touching=["tqdm/std.py"])
        record = live.record("tqdm")
        live.courier("elsewhere", record.stdout)
        assert live.resolutions() == []

    def test_a_second_firing_spends_no_second_row(self, live):
        """Idempotence: a resolved id has left the population, so re-running
        the courier cannot double-count `finding_resolved`."""
        live.file("BH-001", "tqdm/std.py:736")
        marker = live.batch("tqdm", ["tqdm/std.py"])
        live.courier("tqdm", marker)
        assert len(live.resolutions()) == 1

    def test_the_batch_clears_the_gate(self, live):
        """The escape, driven end to end against the real transitions. The
        SQL alone proves the block, never the way out."""
        live.file("BH-001", "tqdm/std.py:736")
        live.file("BH-002", "tqdm/utils.py:240")
        assert live.answer("no_open_fault_injected") == "false"
        live.batch("tqdm", ["tqdm/std.py"])
        assert live.answer("no_open_fault_injected") == "true"


# ── The gate ─────────────────────────────────────────────────────────────────


@pytest.mark.integration
class TestTheGate:
    """`converge` refuses while any fault_injected finding is open."""

    def test_an_open_fault_injected_finding_blocks(self, board):
        board.file("BH-001", "tqdm/std.py:736")
        assert board.answer("no_open_fault_injected") == "false"

    def test_a_clean_board_does_not(self, board):
        """Non-vacuity: the gate is not simply always shut."""
        board.file("BH-001", "tqdm/std.py:736", reachability="user_reachable")
        assert board.answer("no_open_fault_injected") == "true"

    def test_the_two_queries_agree(self, board):
        """`no_open_fault_injected` must be true exactly when
        `open_fault_injected_findings` is empty — editing one without the
        other is how a gate stops meaning what its escape produces."""
        board.file("BH-001", "tqdm/std.py:736")
        assert board.answer("no_open_fault_injected") == "false"
        assert board.show() != {}
        board.defer("BH-001")
        assert board.answer("no_open_fault_injected") == "true"
        assert board.show() == {}

    def test_converge_carries_the_gate(self):
        """It gates `converge`, not `finalize`. A `fault_injected` CRITICAL
        already blocks `converge` through `all_critical_resolved`, which
        carries no reachability filter and refuses a deferral — so a batch
        compelled at `finalize` would sit behind a door that run can never
        open."""
        try:
            import tomllib  # noqa: PLC0415
        except ModuleNotFoundError:  # pragma: no cover - 3.10 and below
            import tomli as tomllib  # type: ignore[no-redef]  # noqa: PLC0415
        with open(os.path.join(CONFIG_DIR, "transitions.toml"), "rb") as fh:
            transitions = tomllib.load(fh)["transitions"]
        converge = next(t for t in transitions if t["command"] == "converge")
        assert any(gate.get("query") == "no_open_fault_injected"
                   for gate in converge["gates"])


# ── The escape has to be reachable, and taught ───────────────────────────────


@pytest.mark.contract
class TestTheEscapeIsTaught:
    """A block naming a command no skill file teaches is a deadlock with a
    helpful message."""

    def _convergence(self):
        with open(_CONVERGENCE_DOC, encoding="utf-8") as fh:
            return fh.read()

    def test_the_batch_command_is_taught(self):
        assert "hardening_batch.py" in self._convergence()

    def test_it_is_taught_before_the_converge_transition(self):
        """Order is the contract: a batch taught after `transition converge`
        is a step the run reaches only once the gate has already refused."""
        text = self._convergence()
        assert text.index("hardening_batch.py") < text.index("transition converge")

    def test_the_stamp_names_the_step_that_teaches_the_batch(self):
        """The courier writes `phase`/`step` as constants because a writer of
        someone else's resolution reads nothing out of a tree the agent can
        edit. Pinned here so the constants cannot drift off the document."""
        assert hb.BATCH_PHASE == "convergence"
        assert f"Step {hb.BATCH_STEP}" in self._convergence()


# ── The predicate lives in the config, not in Python ─────────────────────────


class TestTheQueryIsNamed:
    """H7 exists because a hook holding its own copy of a gate's SQL is how
    #77 shipped."""

    def test_neither_end_carries_sql(self):
        for path in (_SCRIPT, _COURIER):
            with open(path, encoding="utf-8") as fh:
                assert "FROM events" not in fh.read(), path

    def test_the_named_query_exists(self):
        assert "reachability" in _named_query(hb.POPULATION_QUERY)


# ── Registration ─────────────────────────────────────────────────────────────


class TestRegistration:
    """A hook the harness never fires is a producer that never produces."""

    def test_the_courier_is_in_hooks_json(self):
        with open(os.path.join(REPO_ROOT, "hooks", "hooks.json"), encoding="utf-8") as fh:
            assert "hardening_batch_courier.py" in fh.read()

    def test_the_courier_is_in_the_trusted_caller_list(self):
        """`TRUSTED_SCRIPTS` is hand-kept — the generator will not discover a
        new courier, and the first regeneration after adding one looks
        entirely successful while its writes are silently refused."""
        with open(os.path.join(REPO_ROOT, "scripts", "hash-trusted-callers.sh"),
                  encoding="utf-8") as fh:
            assert "hardening_batch_courier.py" in fh.read()

    def test_the_courier_is_a_declared_producer(self):
        try:
            import tomllib  # noqa: PLC0415
        except ModuleNotFoundError:  # pragma: no cover - 3.10 and below
            import tomli as tomllib  # type: ignore[no-redef]  # noqa: PLC0415
        with open(os.path.join(CONFIG_DIR, "events.toml"), "rb") as fh:
            producers = tomllib.load(fh)["events"]["finding_resolved"]["producers"]
        assert any("hardening_batch_courier.py" in p["id"] for p in producers)
