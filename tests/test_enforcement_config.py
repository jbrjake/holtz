"""Tests for enforcement TOML configuration files."""

import json
import os
import re
import sys
from pathlib import Path

import pytest

if sys.version_info >= (3, 11):  # noqa: UP036
    import tomllib
else:
    import tomli as tomllib

ENFORCEMENT_DIR = Path(__file__).parent.parent / "enforcement"
EVENTS_TOML = ENFORCEMENT_DIR / "events.toml"
TRANSITIONS_TOML = ENFORCEMENT_DIR / "transitions.toml"
RENDERS_TOML = ENFORCEMENT_DIR / "renders.toml"
PROTOCOL_TOML = ENFORCEMENT_DIR / "protocol.toml"
VERIFY_SUITE = ENFORCEMENT_DIR / "scripts" / "verify_suite.py"

BREADCRUMBS = ["project", "run", "auditor"]

# Auto-recorded events don't need breadcrumb fields — they're telemetry, not audit events
_AUTO_RECORDED_EVENTS = {"file_read", "source_edit", "file_search", "bash_command"}

# The JSONL-migration vocabulary that is actually reachable. Six others
# (merge_result, convergence_iteration, run_summary, pattern_discovered,
# baseline_delta, run_postmortem) were declared and never wired to anything —
# no gate, template, hook, skill file, or alias — and this list was what kept
# them alive: a test asserting the noun exists, while nothing meant it. Removed
# in #82 along with the declarations. See `sahjhan lint` L5.
NEW_EVENT_TYPES = [
    "recon_finding", "audit_claim", "test_audit_finding",
    "code_audit_finding", "graph_delta",
]


# ── Task 1.1: events.toml ──


def test_all_events_have_breadcrumbs():
    """Every event type must have project, run, auditor fields.

    Auto-recorded events (file_read, source_edit, file_search, bash_command)
    are excluded — they are ground-truth telemetry emitted by hooks, not audit
    events authored by the auditor, so they don't carry breadcrumb fields.
    """
    cfg = tomllib.loads(EVENTS_TOML.read_text())
    events = cfg["events"]
    for name, defn in events.items():
        if name in _AUTO_RECORDED_EVENTS:
            continue
        field_names = [f["name"] for f in defn["fields"]]
        for bc in BREADCRUMBS:
            assert bc in field_names, (
                f"Event '{name}' missing breadcrumb field '{bc}'"
            )


def test_finding_has_phase_and_step():
    """The 'finding' event must have phase and step fields."""
    cfg = tomllib.loads(EVENTS_TOML.read_text())
    finding = cfg["events"]["finding"]
    field_names = [f["name"] for f in finding["fields"]]
    assert "phase" in field_names, "finding missing 'phase' field"
    assert "step" in field_names, "finding missing 'step' field"


def test_new_event_types_exist():
    """All new event types must be defined."""
    cfg = tomllib.loads(EVENTS_TOML.read_text())
    events = cfg["events"]
    for evt in NEW_EVENT_TYPES:
        assert evt in events, f"Missing new event type: {evt}"


def test_quiz_event_types_exist():
    """All quiz-related event types are defined in events.toml."""
    cfg = tomllib.loads(EVENTS_TOML.read_text())
    events = cfg["events"]
    required = ["quiz_bank_generated", "quiz_posed", "quiz_answered", "quiz_failed", "quiz_exhausted", "quiz_exhausted_resolved"]
    for name in required:
        assert name in events, f"Missing event type: {name}"


def test_field_patterns_are_valid_regexes():
    """Every field with a 'pattern' key must compile as a valid regex."""
    cfg = tomllib.loads(EVENTS_TOML.read_text())
    events = cfg["events"]
    for name, defn in events.items():
        for field in defn["fields"]:
            if "pattern" in field:
                try:
                    re.compile(field["pattern"])
                except re.error as exc:
                    raise AssertionError(
                        f"Event '{name}', field '{field['name']}': "
                        f"invalid regex pattern '{field['pattern']}': {exc}"
                    ) from exc


# ── Task 1.2: transitions.toml ──


def test_recon_complete_uses_event_gates():
    """recon_complete must not use files_exist; should use query or ledger_has_event."""
    cfg = tomllib.loads(TRANSITIONS_TOML.read_text())
    recon_complete = None
    for t in cfg["transitions"]:
        if t.get("command") == "recon_complete":
            recon_complete = t
            break
    assert recon_complete is not None, "No recon_complete transition found"
    gate_types = [g["type"] for g in recon_complete["gates"]]
    assert "files_exist" not in gate_types, (
        "recon_complete should not use files_exist gate"
    )
    assert "query" in gate_types or "ledger_has_event" in gate_types, (
        "recon_complete should have a query or ledger_has_event gate"
    )


def test_audit_complete_uses_event_gates():
    """audit_complete must not use file_exists for audit markdown."""
    cfg = tomllib.loads(TRANSITIONS_TOML.read_text())
    audit_complete = None
    for t in cfg["transitions"]:
        if t.get("command") == "audit_complete":
            audit_complete = t
            break
    assert audit_complete is not None, "No audit_complete transition found"
    for gate in audit_complete["gates"]:
        if gate["type"] == "file_exists":
            # file_exists for impact-graph.json is OK
            assert "impact-graph" in gate.get("path", ""), (
                f"audit_complete has file_exists gate for non-graph file: {gate}"
            )


def test_fix_commit_has_circuit_breaker():
    """fix_commit must have a query gate (circuit breaker)."""
    cfg = tomllib.loads(TRANSITIONS_TOML.read_text())
    fix_commit = None
    for t in cfg["transitions"]:
        if t.get("command") == "fix_commit":
            fix_commit = t
            break
    assert fix_commit is not None, "No fix_commit transition found"
    gate_types = [g["type"] for g in fix_commit["gates"]]
    assert "query" in gate_types, (
        "fix_commit should have a query gate (circuit breaker)"
    )


def test_fix_commit_auto_emits_finding_resolved():
    """fix_commit must AUTO-EMIT finding_resolved for its item (sahjhan emits).

    Recording fix_commit writes only a state_transition, not a finding_resolved
    — so without coupling the two, an audit could commit every fix, register
    every fix_commit, and still show "Resolved: 0" with all findings OPEN,
    unable to converge (the perspective/pattern/convergence gates read
    finding_resolved). Emitting the resolution from the transition keeps
    "committed a fix for BH-NNN" and "BH-NNN is resolved" atomic in one command,
    without the agent restating the fact.
    """
    cfg = tomllib.loads(TRANSITIONS_TOML.read_text())
    fix_commit = next(
        (t for t in cfg["transitions"] if t.get("command") == "fix_commit"), None
    )
    assert fix_commit is not None, "No fix_commit transition found"

    emit = next(
        (e for e in fix_commit.get("emits", []) if e.get("event") == "finding_resolved"),
        None,
    )
    assert emit is not None, (
        "fix_commit must declare an `emits` entry for finding_resolved — "
        "otherwise the transition and the finding's resolution decouple and the "
        "run can never converge."
    )
    fields = emit.get("fields", {})
    assert fields.get("id") == "{{item_id}}", (
        "the emitted finding_resolved must carry the item id from the transition arg"
    )
    assert "commit_hash" in emit.get("commands", {}), (
        "the emit must derive commit_hash from the commit (git rev-parse HEAD)"
    )

    # The old manual-recording gate must be gone (it would deadlock: you cannot
    # gate a transition on an event the transition itself emits).
    for g in fix_commit.get("gates", []):
        assert "finding_resolved" not in g.get("sql", ""), (
            "fix_commit must not gate on finding_resolved — it emits it"
        )


def test_fix_loop_event_count_triggers_filter_source_edit():
    """#70 item 7: the fix_loop "N events" nudges count only source_edit events.

    Counting every ledger event (dominated by auto-recorded reads/searches) made
    the warning climb to 30-40 during a single fix's investigation. The triggers
    now set event_types = ["source_edit"] (honored by sahjhan >= 0.17.0) so the
    count reflects uncommitted work, not read noise.
    """
    hooks = tomllib.loads((ENFORCEMENT_DIR / "hooks.toml").read_text())

    # PostToolUse Edit accumulation warning
    edit_warn = next(
        (h for h in hooks.get("hooks", [])
         if h.get("check", {}).get("type") == "event_count_since_last_transition"),
        None,
    )
    assert edit_warn is not None, "no event_count_since_last_transition hook found"
    assert edit_warn["check"].get("event_types") == ["source_edit"], (
        "Edit-accumulation warn must count only source_edit events (#70 item 7)"
    )

    # fix_loop_stall monitor
    stall = next(
        (m for m in hooks.get("monitors", []) if m.get("name") == "fix_loop_stall"),
        None,
    )
    assert stall is not None, "fix_loop_stall monitor not found"
    assert stall["trigger"].get("event_types") == ["source_edit"], (
        "fix_loop_stall monitor must count only source_edit events (#70 item 7)"
    )


def test_pause_resume_transitions_exist():
    """#69: a reversible awaiting_human pause with an ungated pause/resume pair.

    fix_loop --pause--> awaiting_human --resume--> fix_loop. Pausing to answer a
    user question must never be gated (that's the whole point), and awaiting_human
    must be a declared state.
    """
    cfg = tomllib.loads(TRANSITIONS_TOML.read_text())
    pause = next(
        (t for t in cfg["transitions"]
         if t.get("command") == "pause" and t.get("from") == "fix_loop"), None
    )
    assert pause is not None, "No fix_loop --pause--> transition found (#69)"
    assert pause["to"] == "awaiting_human"
    assert not pause.get("gates"), "pause must be ungated — pausing for a human is always allowed"

    resume = next(
        (t for t in cfg["transitions"]
         if t.get("command") == "resume" and t.get("from") == "awaiting_human"), None
    )
    assert resume is not None, "No awaiting_human --resume--> transition found (#69)"
    assert resume["to"] == "fix_loop"
    assert not resume.get("gates"), "resume from a pause must be ungated"

    states = tomllib.loads((ENFORCEMENT_DIR / "states.toml").read_text())
    assert "awaiting_human" in states["states"], "awaiting_human state not declared"
    assert not states["states"]["awaiting_human"].get("terminal"), (
        "awaiting_human is a pause, not terminal"
    )


def test_iteration_boundary_enforces_pattern_check():
    """BH-020: iteration_boundary must block when 3+ fixes lack pattern analysis."""
    cfg = tomllib.loads(TRANSITIONS_TOML.read_text())
    boundary = None
    for t in cfg["transitions"]:
        if t.get("command") == "iteration_boundary":
            boundary = t
            break
    assert boundary is not None, "No iteration_boundary transition found"
    gate_strs = [json.dumps(g) for g in boundary.get("gates", [])]
    assert any("pattern_analysis" in g for g in gate_strs), (
        "iteration_boundary must have a gate enforcing pattern analysis "
        "after 3+ fix_commits — otherwise the auditor can skip Step 11 "
        "and miss recurring patterns (BH-020)"
    )


def test_fix_commit_breaker_scoped_to_iteration_not_lifetime():
    """#67: the fix_commit circuit breaker must reset each iteration_boundary.

    A lifetime ``count(*) < 15`` cap makes ``converge`` mathematically
    unsatisfiable for any audit whose must-fix set exceeds 15 — ``converge``
    requires every finding resolved-or-deferred, and the one-fix-one-commit rule
    forbids clearing several findings per commit. Scoping the breaker to fixes
    ``seq >`` the last ``iteration_boundary`` caps runaway *within* an uncleared
    window while still letting a long audit converge across ``/clear`` cycles.
    """
    cfg = tomllib.loads(TRANSITIONS_TOML.read_text())
    fix_commit = next(
        (t for t in cfg["transitions"] if t.get("command") == "fix_commit"), None
    )
    assert fix_commit is not None, "No fix_commit transition found"
    breaker = next(
        (
            g
            for g in fix_commit["gates"]
            if g["type"] == "query" and "command='fix_commit'" in g.get("sql", "")
        ),
        None,
    )
    assert breaker is not None, "fix_commit must have a query circuit-breaker gate"
    sql = breaker["sql"]
    assert "iteration_boundary" in sql and "COALESCE" in sql and "seq >" in sql, (
        "fix_commit circuit breaker must be scoped since the last "
        "iteration_boundary (seq > COALESCE(... iteration_boundary ..., 0)) so the "
        "cap resets each /clear; a lifetime cap blocks convergence for audits with "
        f">15 must-fix findings (#67). Got: {sql}"
    )


def test_pattern_check_bootstraps_from_zero():
    """#65: the first pattern_check must be satisfiable with no prior analysis.

    The old gate used ``ledger_has_event_since`` with
    ``since = "last_event_of_type:pattern_analysis_complete"`` — a reference
    syntax that gate type does not parse. It matched no event, silently fell back
    to "since last state_transition", and ignored ``min_count`` entirely, so the
    very first ``pattern_check`` could never fire (you need a
    ``pattern_analysis_complete`` to satisfy the gate that produces the first
    one). A COALESCE-scoped query treats "no prior analysis" as the run start.
    """
    cfg = tomllib.loads(TRANSITIONS_TOML.read_text())
    pattern_check = next(
        (t for t in cfg["transitions"] if t.get("command") == "pattern_check"), None
    )
    assert pattern_check is not None, "No pattern_check transition found"
    gate_types = [g["type"] for g in pattern_check["gates"]]
    assert "ledger_has_event_since" not in gate_types, (
        "pattern_check must not use ledger_has_event_since with a "
        "last_event_of_type baseline — that gate ignores the baseline and "
        "min_count, so the first pattern analysis can never fire (#65)"
    )
    q = next((g for g in pattern_check["gates"] if g["type"] == "query"), None)
    assert q is not None, "pattern_check must use a query gate (#65)"
    # #82: the predicate moved into protocol.toml [queries] so the block that
    # names pattern_check as its escape decides by the same object. Resolve the
    # name the way the engine does rather than reading an inline copy — a test
    # that insisted on the copy would have made the fix look like a regression.
    sql = q.get("sql") or _named_query_sql(q.get("query", ""))
    assert "COALESCE" in sql and "pattern_analysis_complete" in sql, (
        "pattern_check must use a COALESCE-scoped query so the first pattern "
        f"analysis fires once 3+ findings resolve (#65). Got: {pattern_check['gates']}"
    )
    assert ">= 3" in sql or ">=3" in sql, (
        "pattern_check must enforce the 3-resolved-findings minimum in SQL "
        "(the old ledger_has_event_since silently ignored min_count) (#65)"
    )


def test_pattern_analysis_overdue_is_one_predicate_with_opposite_gates():
    """#77/#82: the block and its printed escape must be the same object.

    ``iteration_boundary`` blocks while pattern analysis is overdue and tells
    the agent to run ``pattern_check``, whose gate decides whether it *is*
    overdue. When those were two predicates they could both be shut at once —
    the block's own escape unsatisfiable, which is what #77 was. Referencing
    one named query with opposite expectations makes exactly one of them open
    at any moment, by construction rather than by care.
    """
    cfg = tomllib.loads(TRANSITIONS_TOML.read_text())

    def _overdue_gate(command: str) -> dict:
        transition = next(
            t for t in cfg["transitions"] if t.get("command") == command
        )
        gate = next(
            (
                g
                for g in transition.get("gates", [])
                if g.get("query") == "pattern_analysis_overdue"
            ),
            None,
        )
        assert gate is not None, (
            f"{command} must decide 'pattern analysis overdue' by the named "
            "query, not a copy of its SQL (#82)"
        )
        return gate

    assert _overdue_gate("pattern_check")["expect"] == "true"
    assert _overdue_gate("iteration_boundary")["expect"] == "false"


def _named_query_sql(name: str) -> str:
    queries = tomllib.loads(PROTOCOL_TOML.read_text()).get("queries", {})
    assert name in queries, f"gate references undeclared query '{name}'"
    return str(queries[name]["sql"])


def test_test_and_lint_gates_are_env_overridable():
    """#63/#70.5: pytest/ruff gate commands must be overridable per target.

    Gate commands run in the environment that invoked ``sahjhan transition``, so
    a target project whose tests/lint only run under a venv/pyenv/conda/poetry/
    tox can't rely on the login ``python3``/``ruff``. Wrapping each command in
    ``${HOLTZ_PYTEST:-...}`` / ``${HOLTZ_LINT:-...}`` lets an operator set the
    exact command once (``sh`` expands the default when the var is unset, so
    prior behavior is preserved) — without hardcoding any interpreter path into
    the engine.
    """
    cfg = tomllib.loads(TRANSITIONS_TOML.read_text())
    lint_cmds = [
        g.get("cmd", "")
        for t in cfg["transitions"]
        for g in t.get("gates", [])
        if "ruff" in g.get("cmd", "")
    ]
    assert lint_cmds, "expected at least one ruff gate command"
    for cmd in lint_cmds:
        assert cmd.startswith("${HOLTZ_LINT:-") and cmd.endswith("}"), (
            f"lint gate must be overridable via $HOLTZ_LINT (#63/#70.5): {cmd}"
        )
    # The suite half of the same contract moved into verify_suite.py when the
    # gates stopped running pytest and started reading the ledger. The override
    # still exists and still flows to every gate — it is read where the suite
    # is actually run, so it reaches the agent's `--record` too, which the
    # shell-expansion form never did.
    assert "HOLTZ_PYTEST" in VERIFY_SUITE.read_text(), (
        "the suite command must stay overridable via $HOLTZ_PYTEST (#63/#70.5)"
    )


@pytest.mark.contract
def test_gate_commands_never_truncate_the_suite():
    """A gate asserting "the suite passes" must actually run the suite.

    ``--lf``/``--last-failed`` runs *only* the tests that failed on the previous
    run. Dropped into a gate command it reads as a harmless speedup and behaves
    as a false green: seed a 4-test suite with one failure, fix it, re-run under
    ``--lf`` and pytest reports ``1 passed`` / exit 0 — the gate certifies
    "test suite must pass" having executed one test. Same defect class as #83,
    where ``ruff check .`` returns exit 0 on a repo with no Python files.

    ``--ff``/``--failed-first`` is the safe form of the same idea: it reorders so
    the known-failing test is hit first (which is what makes ``-x`` pay off in
    the fix/re-run loop) but still runs everything.

    This constrains the *defaults* in transitions.toml. An operator who exports
    ``HOLTZ_PYTEST='pytest --lf'`` can still defeat their own gate — that is
    outside what a config test can reach, and is called out in
    references/phase-fix-loop.md.
    """
    cfg = tomllib.loads(TRANSITIONS_TOML.read_text())
    banned = ("--lf", "--last-failed")
    for t in cfg["transitions"]:
        for g in t.get("gates", []):
            cmd = g.get("cmd", "")
            for flag in banned:
                assert flag not in cmd.split(), (
                    f"gate command truncates the suite with {flag!r} — use --ff. "
                    f"transition={t.get('command')!r} cmd={cmd!r}"
                )


@pytest.mark.contract
def test_suite_gates_delegate_to_verify_suite():
    """No gate runs pytest; every suite gate reads the ledger instead.

    Three gates used to carry a copy of the pytest command and execute it, so
    the fix loop ran the target's full suite three times per finding for one
    enforced answer. They now run ``verify_suite.py --check``, which recomputes
    the working-tree hash and asks whether a ``suite_green`` already names it.

    Two invariants, and the second is what keeps the first honest: a gate that
    reintroduced ``pytest`` would be both a second copy of a default that now
    lives in exactly one place, and a suite execution inside a transition —
    silently restoring the cost this design removed. Its evidence must also be
    *named* (``evidence = "suite_green"``), which is what lets H1 and the
    generated contract see a gate whose predicate lives inside a script.
    """
    cfg = tomllib.loads(TRANSITIONS_TOML.read_text())
    suite_gates = []
    for t in cfg["transitions"]:
        for g in t.get("gates", []):
            cmd = g.get("cmd", "")
            assert "pytest" not in cmd, (
                f"gate runs the suite instead of reading the ledger — use "
                f"verify_suite.py --check. transition={t.get('command')!r} "
                f"cmd={cmd!r}"
            )
            if "verify_suite.py" in cmd:
                suite_gates.append((t.get("command"), g))
    commands = {command for command, _ in suite_gates}
    assert commands == {
        "fix_commit",
        "iteration_boundary",
        "set complete perspective",
        "converge",
    }, f"unexpected set of suite gates: {commands}"
    for command, gate in suite_gates:
        assert "--check" in gate["cmd"].split(), (
            f"{command}'s suite gate must be the read-only --check mode, never "
            f"--record: a gate that records its own evidence proves nothing"
        )
        assert gate.get("evidence") == "suite_green", (
            f"{command}'s suite gate must name the event it depends on so H10 "
            f"and ENFORCEMENT-CONTRACT.md can see it"
        )
    # `affected` is the per-fix optimisation; every other suite gate is the
    # thing that bounds it. Widen one of those to `affected` and an audit could
    # converge having never run the whole suite on the converged tree.
    scopes = {command: gate["cmd"].split()[-1] for command, gate in suite_gates}
    assert scopes["fix_commit"] == "affected", scopes
    assert set(scopes.values()) - {"affected"} == {"full"}, scopes


@pytest.mark.contract
def test_the_suite_command_fails_fast_in_its_one_home():
    """The suite default carries ``-x --ff`` (fail-fast, no truncation).

    The gate consumes a boolean, so it has no use for the remaining passing
    tests once one fails. ``-x`` costs nothing on the green path and collapses
    the red path; ``--ff`` reaches the previously-failing test immediately.
    Paired with test_gate_commands_never_truncate_the_suite, which bans the
    unsafe way to get the same effect (``--lf``, which runs *only* the
    previously-failing tests).
    """
    default = re.search(
        r'^DEFAULT_PYTEST\s*=\s*"([^"]+)"', VERIFY_SUITE.read_text(), re.M
    )
    assert default, "verify_suite.py must define DEFAULT_PYTEST as a literal"
    tokens = default.group(1).split()
    assert "-x" in tokens, f"suite command should fail fast with -x: {tokens}"
    assert "--ff" in tokens, f"suite command should order failed-first: {tokens}"
    assert "--lf" not in tokens and "--last-failed" not in tokens, (
        f"suite command must never truncate to the last failures: {tokens}"
    )


# ── Task 1.3: renders.toml ──


def test_renders_have_ledger_field():
    """Every render entry must have a 'ledger' or 'ledger_template' field."""
    cfg = tomllib.loads(RENDERS_TOML.read_text())
    for i, render in enumerate(cfg["renders"]):
        assert "ledger" in render or "ledger_template" in render, (
            f"Render entry {i} (target={render.get('target', '?')}) missing 'ledger' or 'ledger_template' field"
        )


def test_agent_owned_living_docs_are_not_render_targets():
    """The living documents are agent-written per the skill instructions.

    A render entry manifest-tracks its target, so the skill-prescribed
    agent writes would trigger permanent protocol_violation events (#57).
    Any file the skill tells the agent to write must never appear here.
    """
    agent_owned = {
        "patterns-brief.md",
        "patterns-brief-archive.md",
        "LIVING-PUNCHLIST.md",
        "architecture-baseline.md",
        "impact-graph.json",
    }
    cfg = tomllib.loads(RENDERS_TOML.read_text())
    render_targets = {r["target"] for r in cfg["renders"]}
    overlap = agent_owned & render_targets
    assert not overlap, (
        f"Agent-owned living docs must not be render targets "
        f"(render → manifest-tracked → agent write = permanent violation, #57): {sorted(overlap)}"
    )


def test_render_templates_exist():
    """Every render entry's template file must exist in enforcement/."""
    cfg = tomllib.loads(RENDERS_TOML.read_text())
    for render in cfg["renders"]:
        template = ENFORCEMENT_DIR / render["template"]
        assert template.exists(), (
            f"Render target '{render['target']}' references missing template {render['template']}"
        )


def test_render_ledger_templates_match_protocol():
    """Every ledger_template in renders.toml must have a matching template in protocol.toml."""
    renders_cfg = tomllib.loads(RENDERS_TOML.read_text())
    protocol_cfg = tomllib.loads(PROTOCOL_TOML.read_text())
    declared_templates = set(protocol_cfg.get("ledgers", {}).keys())
    for render in renders_cfg["renders"]:
        tmpl = render.get("ledger_template")
        if tmpl is not None:
            assert tmpl in declared_templates, (
                f"Render target '{render['target']}' uses ledger_template '{tmpl}' "
                f"but protocol.toml only declares: {sorted(declared_templates)}. "
                f"Ledger must be created with 'sahjhan ledger create --from {tmpl} <N>' "
                f"so the template link is preserved."
            )


# ── Task 1.4: protocol.toml ──


def test_protocol_has_ledger_config():
    """protocol.toml must have ledgers.run and ledgers.project."""
    cfg = tomllib.loads(PROTOCOL_TOML.read_text())
    assert "ledgers" in cfg, "protocol.toml missing 'ledgers' key"
    assert "run" in cfg["ledgers"], "protocol.toml missing ledgers.run"
    assert "project" in cfg["ledgers"], "protocol.toml missing ledgers.project"


def test_protocol_has_content_event_aliases():
    """protocol.toml aliases must include content event shortcuts."""
    cfg = tomllib.loads(PROTOCOL_TOML.read_text())
    aliases = cfg["aliases"]
    expected = [
        "recon finding",
        "audit claim",
        "test finding",
        "code finding",
        "graph delta",
    ]
    for alias in expected:
        assert alias in aliases, f"Missing alias: '{alias}'"


def test_transitions_no_plugin_root_references():
    """BH-002: Gate commands must not reference ${CLAUDE_PLUGIN_ROOT}."""
    content = TRANSITIONS_TOML.read_text()
    assert "${CLAUDE_PLUGIN_ROOT}" not in content, (
        "transitions.toml still references ${CLAUDE_PLUGIN_ROOT} — "
        "use relative paths (e.g. skills/holtz/scripts/) instead"
    )


def test_perspective_clean_has_quiz_gate():
    """set complete perspective transition requires quiz_answered."""
    cfg = tomllib.loads(TRANSITIONS_TOML.read_text())
    for t in cfg["transitions"]:
        if t.get("command") == "set complete perspective":
            gate_strs = [json.dumps(g) for g in t.get("gates", [])]
            assert any("quiz_answered" in g for g in gate_strs), \
                "set complete perspective missing quiz_answered gate"
            return
    raise AssertionError("set complete perspective transition not found")


def _resolved_gate_predicates(transition: dict) -> list[str]:
    """Gate JSON with `query = "<name>"` replaced by the SQL it names.

    A gate's predicate can now live in `protocol.toml [queries]` rather than
    inline (#82), so asserting on the gate's own text stops seeing it — this
    test passed on the inline SQL and failed the moment the predicate became a
    shared object, without the gate's meaning changing at all. Resolve the
    name, then assert on what actually runs.
    """
    queries = tomllib.loads(PROTOCOL_TOML.read_text()).get("queries", {})
    resolved = []
    for gate in transition.get("gates", []) or []:
        named = gate.get("query")
        if named:
            assert named in queries, f"gate references undeclared query '{named}'"
            resolved.append(json.dumps({**gate, "sql": queries[named]["sql"]}))
        else:
            resolved.append(json.dumps(gate))
    return resolved


def test_converge_has_quiz_exhaustion_gate():
    """converge transition checks for unresolved quiz_exhausted."""
    cfg = tomllib.loads(TRANSITIONS_TOML.read_text())
    for t in cfg["transitions"]:
        if t.get("command") == "converge":
            gate_strs = _resolved_gate_predicates(t)
            assert any("quiz_exhausted" in g for g in gate_strs), \
                "converge missing quiz_exhausted gate"
            return
    raise AssertionError("converge transition not found")


def test_gate_sql_uses_seq_not_rowid():
    """BH-021: Gate SQL must use 'seq' not 'rowid' — Sahjhan uses DataFusion, not SQLite."""
    cfg = tomllib.loads(TRANSITIONS_TOML.read_text())
    for t in cfg["transitions"]:
        for gate in t.get("gates", []):
            sql = gate.get("sql", "")
            assert "rowid" not in sql.lower(), (
                f"Gate SQL in '{t['command']}' references 'rowid' which is a SQLite concept. "
                f"Sahjhan's DataFusion backend uses 'seq' for event ordering. "
                f"SQL: {sql}"
            )


def test_mypy_uses_explicit_package_bases():
    """BH-002: mypy commands must use --explicit-package-bases to avoid _common collision."""
    cfg = tomllib.loads(TRANSITIONS_TOML.read_text())
    for t in cfg["transitions"]:
        for gate in t.get("gates", []):
            cmd = gate.get("cmd", "")
            if "mypy" in cmd:
                assert "--explicit-package-bases" in cmd, (
                    f"mypy gate in '{t['command']}' missing --explicit-package-bases: {cmd}"
                )


# ── Tasks 5 & 6: Hook registration ──


def test_settings_local_has_no_enforcement_hooks():
    """settings.local.json must NOT register enforcement hooks.

    Enforcement hooks run via the plugin (hooks/hooks.json), not via
    project settings. Having them in settings.local.json causes them
    to fire during plugin development, blocking edits to the hooks
    themselves. See: two broken releases from this exact mistake.
    """
    settings_path = Path(__file__).parent.parent / ".claude" / "settings.local.json"
    if not settings_path.exists():
        pytest.skip(".claude/settings.local.json not present (not tracked in git)")
    cfg = json.loads(settings_path.read_text())
    hooks = cfg.get("hooks", {})

    all_commands = []
    for event_hooks in hooks.values():
        for entry in event_hooks if isinstance(event_hooks, list) else []:
            for h in entry.get("hooks", []):
                all_commands.append(h.get("command", ""))

    enforcement_hooks = [c for c in all_commands if "enforcement/" in c]
    assert not enforcement_hooks, (
        f"Enforcement hooks must not be in settings.local.json (found: {enforcement_hooks}). "
        "They belong in hooks/hooks.json (plugin mode only)."
    )


def test_pre_release_hook_validation_gate():
    """Pre-release gate: smoke test script exists and is executable."""
    smoke_test = Path(__file__).parent.parent / "scripts" / "smoke-test-hooks.sh"
    assert smoke_test.exists(), "scripts/smoke-test-hooks.sh missing"
    assert os.access(smoke_test, os.X_OK), "scripts/smoke-test-hooks.sh not executable"


def test_hook_schema_exists():
    """Pre-release gate: hook_schema.py must exist as source of truth."""
    schema = Path(__file__).parent / "hook_schema.py"
    assert schema.exists(), "tests/hook_schema.py missing — hooks have no schema to validate against"


def test_hooks_json_registers_enforcement_hooks():
    """Plugin-mode hooks.json must register commit_gate and protocol_tracker."""
    hooks_path = Path(__file__).parent.parent / "hooks" / "hooks.json"
    cfg = json.loads(hooks_path.read_text())
    hooks = cfg.get("hooks", {})

    pre_tool = hooks.get("PreToolUse", [])
    post_tool = hooks.get("PostToolUse", [])

    all_pre_commands = []
    for entry in pre_tool:
        for h in entry.get("hooks", []):
            all_pre_commands.append(h.get("command", ""))

    all_post_commands = []
    for entry in post_tool:
        for h in entry.get("hooks", []):
            all_post_commands.append(h.get("command", ""))

    assert any("commit_gate" in c for c in all_pre_commands), (
        "commit_gate.py not registered in hooks.json PreToolUse"
    )
    assert any("protocol_tracker" in c for c in all_post_commands), (
        "protocol_tracker.py not registered in hooks.json PostToolUse"
    )


def test_trusted_callers_keys_match_daemon_path_strip():
    """Manifest keys must match how the daemon identifies caller scripts.

    The sahjhan daemon identifies a caller by taking the caller's absolute
    script path and stripping its ``--config-dir`` prefix (which is
    ``<plugin_root>/enforcement``). So a script at
    ``<plugin_root>/enforcement/hooks/primer.py`` is identified as
    ``hooks/primer.py`` — NOT ``enforcement/hooks/primer.py``.

    A previous version of the manifest used plugin-root-relative keys with
    an ``enforcement/`` prefix. Every daemon auth request silently failed
    with "caller not in manifest", and the whole enforcement layer
    collapsed to fail-open in the installed-plugin case — read_cache
    returned None everywhere, is_enforcement_fresh returned False, every
    protocol gate fell through to exit_ok. No tests caught this because
    no tests hit the real authed-event path.

    Pin the format so the regression can't repeat silently.
    """
    repo_root = Path(__file__).parent.parent
    manifest_path = repo_root / "enforcement" / "trusted-callers.toml"
    manifest = tomllib.loads(manifest_path.read_text())

    bad_keys = [
        k for k in manifest.get("callers", {})
        if k.startswith("enforcement/")
    ]
    assert not bad_keys, (
        "trusted-callers.toml keys must be relative to --config-dir "
        "(which is enforcement/), not relative to plugin root. "
        f"These keys will be rejected by the daemon: {bad_keys}. "
        "Regenerate with scripts/hash-trusted-callers.sh."
    )


def test_trusted_callers_hashes_match_files():
    """Every hash in trusted-callers.toml must match the current file content.

    The daemon authenticates hook scripts by SHA-256 against this manifest.
    If a hook is edited but the hash isn't regenerated via
    scripts/hash-trusted-callers.sh, daemon auth silently fails and the
    hook can't record authed events.

    The file's own comment claims "the pre-commit hook verifies this
    manifest is up to date" — no such hook exists. This test is that
    check, running in pytest instead.
    """
    import hashlib

    repo_root = Path(__file__).parent.parent
    manifest_path = repo_root / "enforcement" / "trusted-callers.toml"
    manifest = tomllib.loads(manifest_path.read_text())

    mismatches: list[str] = []
    for rel_path, expected in manifest.get("callers", {}).items():
        if not expected.startswith("sha256:"):
            mismatches.append(f"{rel_path}: manifest entry missing sha256: prefix")
            continue
        expected_hash = expected.removeprefix("sha256:")
        # Manifest keys match the daemon's caller-identification path, which
        # strips the --config-dir prefix: `hooks/primer.py` really lives at
        # `enforcement/hooks/primer.py`, while `hooks/subagent_findings_check.py`
        # lives at the plugin-root path of the same name. Try both.
        candidates = [
            repo_root / "enforcement" / rel_path,
            repo_root / rel_path,
        ]
        full_path = next((p for p in candidates if p.is_file()), None)
        if full_path is None:
            mismatches.append(
                f"{rel_path}: file not found at any of "
                + ", ".join(str(p) for p in candidates)
            )
            continue
        actual_hash = hashlib.sha256(full_path.read_bytes()).hexdigest()
        if actual_hash != expected_hash:
            mismatches.append(
                f"{rel_path}: manifest has {expected_hash[:12]}..., "
                f"file is {actual_hash[:12]}.... "
                f"Regenerate with scripts/hash-trusted-callers.sh."
            )

    assert not mismatches, (
        "trusted-callers.toml is stale. The daemon will reject these callers:\n  "
        + "\n  ".join(mismatches)
    )


# ── Issue #79: context_reset provenance is declarative ──


def _context_reset_fields() -> dict[str, dict]:
    cfg = tomllib.loads(EVENTS_TOML.read_text())
    return {f["name"]: f for f in cfg["events"]["context_reset"]["fields"]}


def _resume_gate() -> dict:
    cfg = tomllib.loads(TRANSITIONS_TOML.read_text())
    resume = [
        t for t in cfg["transitions"]
        if t.get("command") == "resume" and t.get("from") == "awaiting_clear"
    ]
    assert len(resume) == 1, "expected exactly one awaiting_clear `resume` transition"
    gates = resume[0]["gates"]
    reset_gates = [g for g in gates if g.get("event") == "context_reset"]
    assert len(reset_gates) == 1, "expected exactly one context_reset gate on resume"
    return reset_gates[0]


def test_context_reset_trigger_cannot_be_a_prompt():
    """The old provenance must be unwritable, not merely unused (#79).

    The daemon validates event fields against this pattern on every
    `record_event`, so narrowing it is what stops any future hook — or a
    revert of primer.py — from recording a prompt as if it were a reset.
    """
    pattern = _context_reset_fields()["trigger"]["pattern"]
    assert not re.match(pattern, "user_prompt_submit"), (
        f"trigger pattern {pattern!r} still admits 'user_prompt_submit'. "
        "A submitted prompt is not a context reset."
    )
    assert re.match(pattern, "session_start")


def test_context_reset_source_admits_only_real_resets():
    """resume/fork carry the prior transcript forward — they are not resets."""
    pattern = _context_reset_fields()["source"]["pattern"]
    for source in ("clear", "compact", "startup"):
        assert re.match(pattern, source), (
            f"source pattern {pattern!r} rejects {source!r}, which does wipe "
            f"or replace the context — this would make the gate unsatisfiable"
        )
    for source in ("resume", "fork"):
        assert not re.match(pattern, source), (
            f"source pattern {pattern!r} admits {source!r}, which restores or "
            f"copies the prior context"
        )


def test_context_reset_is_restricted():
    """Only a hash-verified trusted caller may write the event."""
    cfg = tomllib.loads(EVENTS_TOML.read_text())
    assert cfg["events"]["context_reset"].get("restricted") is True


def test_resume_gate_requires_session_start_provenance():
    """The gate must filter on provenance, not just on the event type.

    Without the filter, `context_reset` events already in live ledgers — the
    ones the primer wrote on ordinary prompts — would still satisfy it.
    """
    gate = _resume_gate()
    assert gate.get("filter", {}).get("trigger") == "session_start", (
        f"resume gate does not require trigger=session_start: {gate!r}"
    )
    assert gate["since"] == "last_transition"


def test_session_start_hook_is_registered_and_trusted():
    """The only writer of context_reset must actually run, and authenticate."""
    hooks_json = json.loads(
        (Path(__file__).parent.parent / "hooks" / "hooks.json").read_text()
    )
    commands = [
        h["command"]
        for group in hooks_json["hooks"].get("SessionStart", [])
        for h in group["hooks"]
    ]
    assert any("session_start.py" in c for c in commands), (
        "session_start.py is not registered for SessionStart — context_reset "
        "would never be recorded and every awaiting_clear would deadlock"
    )

    manifest = tomllib.loads((ENFORCEMENT_DIR / "trusted-callers.toml").read_text())
    assert "hooks/session_start.py" in manifest["callers"], (
        "session_start.py is missing from trusted-callers.toml — the daemon "
        "would reject its record_event and the gate could never open"
    )


def test_ungated_resume_cannot_bypass_the_clear_boundary():
    """The `awaiting_human` resume is ungated on purpose — keep it unreachable
    from `awaiting_clear`.

    Pausing to answer a user mid-fix (#69) is always legitimate, so that
    transition carries no context_reset gate. It shares the `resume` command
    name with the gated one, which makes it a standing bypass risk: if anything
    ever routes `awaiting_clear -> awaiting_human`, the clear boundary becomes
    optional again.
    """
    cfg = tomllib.loads(TRANSITIONS_TOML.read_text())
    sources_into_awaiting_human = {
        t["from"] for t in cfg["transitions"] if t.get("to") == "awaiting_human"
    }
    assert "awaiting_clear" not in sources_into_awaiting_human, (
        "awaiting_clear can reach awaiting_human, whose `resume` is ungated — "
        "that is a route around the mandatory context reset (#79). Entries: "
        f"{sorted(sources_into_awaiting_human)}"
    )
