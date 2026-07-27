#!/usr/bin/env python3
"""Holtz-domain static analysis of the enforcement layering (#82).

``sahjhan lint`` proves things about the protocol *graph*: a gate that requires
an event nothing can produce, a state with no satisfiable exit, two predicates
that decide one fact two ways. But every producer the engine can see must be
visible **in TOML** — a transition ``emits`` block, a hook ``auto_record``, its
own built-ins. Holtz's real producers are Python hooks calling
``record_authed_event`` and skill files teaching the agent a command. The
engine must never learn about those; that is the purity seam.

So this script is the other half. It does two things the engine cannot:

1. **Discovers** the real write paths in the tree, by enumerating the *verbs*
   that write (``record_authed_event``, a subprocess ``event`` argv, a dict
   literal ``event_type``, a fenced ``sahjhan … event X`` in a skill file, a
   ``[aliases]`` entry that expands to one). Grepping for the event *name*
   cannot work: ``set_member_complete`` is written by ``sahjhan set complete``
   and never appears at a write site, while a bare ``event <name>`` regex
   matches English prose.
2. **Falsifies** the ``[[events.*.producers]]`` declarations against that
   discovery. A declaration is a claim. Believing it because it is written in
   TOML would repeat #79's original sin one level up — where ``events.toml``
   said ``context_reset`` means "after /clear" and the only writer fired on
   every ``UserPromptSubmit``.

Checks (H-series, to keep them distinct from sahjhan's L1–L7):

===  =========================================================================
H1   A gate consumes an event nothing in the tree can write (unsatisfiable).
H2   A declared producer does not resolve to a real writer (a false claim).
H3   A real writer is not declared (the declaration is not the *only* writer).
H4   A hook producer is not registered in hooks.json / not hash-pinned.
H5   An event claims non-agent attestation but is not ``restricted``, so
     ``sahjhan event`` can write it anyway.
H6   A transition command no skill file teaches, or a skill file teaches a
     transition that does not exist.
H7   A gate predicate that also lives as a string literal in a Python hook —
     two expressions of one fact, which is how #77 deadlocked.
H8   A block whose printed escape is decided by a different predicate than the
     block itself, so the escape can be unsatisfiable when it is printed.
H9   An item-scoped transition that does not record the item state it implies,
     forcing the agent to state the same fact twice.
===  =========================================================================

Usage::

    python3 scripts/enforcement_lint.py            # exit 0 clean, 1 on error
    python3 scripts/enforcement_lint.py --strict   # warnings fail too
    python3 scripts/enforcement_lint.py --census   # attestation posture table
    python3 scripts/enforcement_lint.py --json
"""
from __future__ import annotations

import argparse
import ast
import difflib
import json
import re
import sys
import tomllib
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ENFORCEMENT = REPO_ROOT / "enforcement"
SKILLS_DIR = REPO_ROOT / "skills"
PLUGIN_HOOKS_JSON = REPO_ROOT / "hooks" / "hooks.json"
TRUSTED_CALLERS = ENFORCEMENT / "trusted-callers.toml"

# Directories scanned for Python write paths. skills/holtz/scripts is included
# because a skill-vended script is as much a writer as a hook is.
PY_WRITER_DIRS = (
    ENFORCEMENT / "hooks",
    REPO_ROOT / "hooks",
    SKILLS_DIR / "holtz" / "scripts",
)

# Events the engine itself writes. Nothing in the tree records these, and
# nothing should: they exist because sahjhan appends them.
ENGINE_BUILTIN_EVENTS = frozenset({"state_transition"})
# Their attestation class. Not in `[attestation] levels` because no event
# *declares* it — it is a property of who appends the record. The agent can
# produce one only by satisfying the gates of the transition it describes.
ENGINE_ATTESTATION = "engine"


# ── Write-path verbs ─────────────────────────────────────────────────────────
#
# Each pattern matches a *verb that writes*, not an event name. This is the
# correction the prototype forced: name-matching produced one false positive
# (`set_member_complete`, written by `sahjhan set complete`) and junk prose
# matches (`event and`, `event the`).

_PY_AUTHED_EVENT = re.compile(
    r"record_authed_event\(\s*(?:#[^\n]*\n\s*)?[\"']([a-z_][a-z0-9_]*)[\"']"
)
# A subprocess argv fragment: `[binary, "--config-dir", cfg, "event", "<type>"]`.
# The `--field` requirement is load-bearing, not decoration: without it this
# also matches the tuple comparison `("event", "quiz_exhausted_resolved")` in
# the bootstrap hook's *denylist*, reporting the hook that forbids an event as
# one of its writers.
_PY_ARGV_EVENT = re.compile(
    r"[\"']event[\"']\s*,\s*[\"']([a-z_][a-z0-9_]*)[\"'][^\[\]]*?[\"']--field[\"']",
    re.S,
)
_PY_EVENT_TYPE_LITERAL = re.compile(
    r"[\"']event_type[\"']\s*:\s*[\"']([a-z_][a-z0-9_]*)[\"']"
)
_PY_SQL_CONSUMER = re.compile(r"type\s*=\s*\\?'([a-z_][a-z0-9_]*)\\?'")

# A sahjhan invocation inside a fenced code block in a skill file.
_SKILL_SAHJHAN_LINE = re.compile(r"(?:^|\s|nohup\s+|!\s*)sahjhan\s")
_SKILL_EVENT = re.compile(r"\bsahjhan\b[^|;&\n]*?\bevent\s+([a-z_][a-z0-9_]*)")
_SKILL_AUTHED_EVENT = re.compile(
    r"\bsahjhan\b[^|;&\n]*?\bauthed-event\s+([a-z_][a-z0-9_]*)"
)
_SKILL_TRANSITION = re.compile(
    r"\bsahjhan\b[^|;&\n]*?\btransition\s+([a-z_][a-z0-9_]*)"
)
_SKILL_SET_COMPLETE = re.compile(r"\bsahjhan\b[^|;&\n]*?\bset\s+complete\s+([a-z_-]+)")

# Event-type literals inside gate SQL. The NOT IN (SELECT … type='Y') form is
# the one that is easy to miss by eye, and is exactly where #81 hides.
# Tera renders read the ledger too: `where_eq(attribute="event_type", value="X")`.
_TERA_EVENT_TYPE = re.compile(
    r"attribute\s*=\s*[\"']event_type[\"']\s*,\s*value\s*=\s*[\"']([a-z_][a-z0-9_]*)[\"']"
)

_SQL_TYPE_EQ = re.compile(r"type\s*=\s*'([a-z_][a-z0-9_]*)'")
_SQL_TYPE_IN = re.compile(r"type\s+IN\s*\(([^)]*)\)", re.IGNORECASE)
_SQL_QUOTED = re.compile(r"'([a-z_][a-z0-9_]*)'")


@dataclass(frozen=True)
class Predicate:
    """One gate predicate, wherever it was written down."""

    origin: str  # "transitions.toml: pattern_check" or "protocol_tracker.py:102"
    sql: str


@dataclass(frozen=True)
class BlockSite:
    """A place that refuses the agent and prints a way out."""

    origin: str
    message: str
    source: str  # the whole file, so the check can ask what else it names


@dataclass(frozen=True)
class Writer:
    """A discovered write path for one event type."""

    event: str
    producer_id: str  # the `id` an [[events.X.producers]] block must declare
    origin: str  # human-readable file:line for the report

    def __str__(self) -> str:
        return f"{self.producer_id} ({self.origin})"


@dataclass
class Finding:
    check: str
    level: str  # "error" | "warning"
    subject: str
    message: str
    hint: str = ""

    def render(self) -> str:
        head = f"{self.check} {self.level}: {self.subject}"
        body = f"    {self.message}"
        if self.hint:
            body += f"\n    hint: {self.hint}"
        return f"{head}\n{body}"


@dataclass(frozen=True)
class Tree:
    """Where to look. Defaults are this repo; tests point it at a fixture.

    The checks assert things about files — that a declared writer exists, is
    registered, is hash-pinned — so proving a check fires on a historical
    defect means reconstructing that defect's *tree*, not just its config.
    """

    root: Path = REPO_ROOT
    config_dir: Path = ENFORCEMENT
    skills_dir: Path = SKILLS_DIR
    hooks_json: Path = PLUGIN_HOOKS_JSON

    @property
    def py_dirs(self) -> tuple[Path, ...]:
        return (
            self.config_dir / "hooks",
            self.config_dir / "scripts",
            self.root / "hooks",
            self.skills_dir / "holtz" / "scripts",
        )

    @property
    def tool_dirs(self) -> tuple[Path, ...]:
        """Dirs whose scripts run because something invokes them by path.

        A hook is fired by the harness, so "is it in hooks.json?" decides
        whether it ever runs. A gate helper under ``enforcement/scripts`` is
        run by a gate command or a documented agent command instead, and will
        never appear there — asking the hook question about it produces a
        permanent false error. The producer grammar therefore separates the
        two: ``hook:<path>`` and ``tool:<path>``. Both are hash-pinned when
        they write a restricted event; only one is registered.
        """
        return (self.config_dir / "scripts",)

    @property
    def trusted_callers(self) -> Path:
        return self.config_dir / "trusted-callers.toml"

    def rel(self, path: Path) -> str:
        try:
            return str(path.relative_to(self.root))
        except ValueError:
            return str(path)


@dataclass
class Model:
    """Everything parsed out of the tree, in one place."""

    tree: Tree = field(default_factory=Tree)
    events: dict[str, dict] = field(default_factory=dict)
    states: dict[str, dict] = field(default_factory=dict)
    transitions: list[dict] = field(default_factory=list)
    # protocol.toml [queries]: the named predicates a gate can reference instead
    # of carrying its own copy of the SQL. Kept on the model because identity is
    # the point — a checker that cannot resolve the name cannot tell two gates
    # apart from two copies of one gate.
    queries: dict[str, dict] = field(default_factory=dict)
    # hooks.toml's runtime gates and monitors, kept whole: they are gates in
    # every sense that matters (the TDD block is one), and the message a
    # blocking hook prints is itself a taught command.
    hooks: list[dict] = field(default_factory=list)
    monitors: list[dict] = field(default_factory=list)
    # Every predicate that decides a gate, from both sides of the seam: the
    # ones declared in TOML, and the ones a Python hook carries as a string.
    toml_predicates: list[Predicate] = field(default_factory=list)
    python_predicates: list[Predicate] = field(default_factory=list)
    block_sites: list[BlockSite] = field(default_factory=list)
    aliases: dict[str, str] = field(default_factory=dict)
    attestation_levels: list[str] = field(default_factory=list)
    consumed: dict[str, list[str]] = field(default_factory=dict)
    # Consumers split by what a missing writer costs: "gate" blocks a run,
    # "render" only leaves a document section permanently empty.
    consumer_kinds: dict[str, set[str]] = field(default_factory=dict)
    writers: dict[str, list[Writer]] = field(default_factory=dict)
    skill_transitions: dict[str, list[str]] = field(default_factory=dict)
    hook_entrypoints: dict[str, list[str]] = field(default_factory=dict)
    # script name -> entrypoint scripts whose process can run it (itself
    # included when it is an entrypoint). The daemon authenticates the process.
    reaching_entrypoints: dict[str, set[str]] = field(default_factory=dict)
    trusted_callers: set[str] = field(default_factory=set)
    unresolved_queries: list[tuple[str, str]] = field(default_factory=list)
    # Event types the bootstrap hook refuses to let the agent record. The
    # second way (besides `restricted`) an event becomes agent-unwritable.
    agent_denied_events: set[str] = field(default_factory=set)


# ── Parsing ──────────────────────────────────────────────────────────────────


def _load_toml(path: Path) -> dict:
    with path.open("rb") as fh:
        return tomllib.load(fh)


def _sql_event_types(sql: str) -> set[str]:
    """Every event type literal referenced by a gate predicate."""
    found = set(_SQL_TYPE_EQ.findall(sql))
    for group in _SQL_TYPE_IN.findall(sql):
        found.update(_SQL_QUOTED.findall(group))
    return found


def _gate_branches(gate: dict) -> Iterator[dict]:
    """Sub-gates of a boolean gate, whatever shape the branch was written in."""
    for branch_key in ("any_of", "all_of", "not"):
        branch = gate.get(branch_key)
        if isinstance(branch, list):
            for sub in branch:
                if isinstance(sub, dict):
                    yield sub
        elif isinstance(branch, dict):
            yield branch


def _gate_query_names(gate: dict) -> set[str]:
    """Named queries a gate references, including inside boolean branches."""
    names = {gate["query"]} if isinstance(gate.get("query"), str) else set()
    for sub in _gate_branches(gate):
        names |= _gate_query_names(sub)
    return names


def _gate_consumed(gate: dict, queries: dict[str, dict] | None = None) -> set[str]:
    """Event types one gate depends on, across every gate shape.

    Pass ``queries`` to resolve ``query = "<name>"`` references through
    ``protocol.toml [queries]``. Without it a named-query gate reads as
    consuming nothing — which is how a live H1 error silently retired the
    moment its predicate was migrated to a name.
    """
    consumed: set[str] = set()
    if isinstance(gate.get("event"), str):
        consumed.add(gate["event"])
    if isinstance(gate.get("sql"), str):
        consumed |= _sql_event_types(gate["sql"])
    if queries is not None:
        for name in _gate_query_names(gate):
            consumed |= _sql_event_types(queries.get(name, {}).get("sql", ""))
    for sub in _gate_branches(gate):
        consumed |= _gate_consumed(sub, queries)
    return consumed


def gate_event_types(model: Model, gate: dict) -> set[str]:
    """Public form of the above, with the model's named queries resolved."""
    return _gate_consumed(gate, model.queries)


def parse_config(model: Model) -> None:
    """Read the five enforcement TOML files into the model."""
    config_dir = model.tree.config_dir
    events_doc = _load_toml(config_dir / "events.toml")
    model.events = dict(events_doc.get("events", {}))

    protocol_doc = _load_toml(config_dir / "protocol.toml")
    model.aliases = dict(protocol_doc.get("aliases", {}))
    model.attestation_levels = list(
        protocol_doc.get("attestation", {}).get("levels", [])
    )
    # `[queries]` lives in protocol.toml, not next to the gates that reference
    # it. Reading it from the wrong file makes every named-query gate look like
    # it consumes nothing — which silently retired a live H1 error the moment
    # its predicate was migrated. Resolve the name, or report the gap.
    named_queries = dict(protocol_doc.get("queries", {}))
    model.queries = named_queries

    transitions_doc = _load_toml(config_dir / "transitions.toml")
    model.transitions = list(transitions_doc.get("transitions", []))

    states_path = config_dir / "states.toml"
    if states_path.exists():
        model.states = dict(_load_toml(states_path).get("states", {}))

    def _record_consumer(event: str, where: str, kind: str = "gate") -> None:
        model.consumed.setdefault(event, []).append(where)
        model.consumer_kinds.setdefault(event, set()).add(kind)

    for transition in model.transitions:
        command = transition.get("command", "?")
        where = f"transitions.toml: {command}"
        for gate in transition.get("gates", []) or []:
            for named in sorted(_gate_query_names(gate)):
                if named not in named_queries:
                    model.unresolved_queries.append((command, named))
                    continue
                sql = named_queries[named].get("sql", "")
                for event in _sql_event_types(sql):
                    _record_consumer(event, f"{where} (query {named})")
            if isinstance(gate.get("sql"), str):
                model.toml_predicates.append(Predicate(where, gate["sql"]))
            for event in _gate_consumed(gate):
                _record_consumer(event, where)
        # `emits` is a write path, not a read.
        for emit in transition.get("emits", []) or []:
            event = emit.get("event")
            if event:
                model.writers.setdefault(event, []).append(
                    Writer(event, f"engine:emits:{command}", f"{where} emits")
                )

    for name, spec in named_queries.items():
        model.toml_predicates.append(
            Predicate(f"protocol.toml: [queries.{name}]", spec.get("sql", ""))
        )
        for event in _sql_event_types(spec.get("sql", "")):
            _record_consumer(event, f"protocol.toml: [queries.{name}]")

    hooks_doc = _load_toml(config_dir / "hooks.toml")
    model.hooks = list(hooks_doc.get("hooks", []))
    model.monitors = list(hooks_doc.get("monitors", []))
    for hook in hooks_doc.get("hooks", []):
        label = f"hooks.toml: {hook.get('event', '?')}"
        gate = hook.get("gate", {})
        if isinstance(gate.get("event"), str):
            _record_consumer(gate["event"], label)
        if isinstance(gate.get("sql"), str):
            model.toml_predicates.append(Predicate(label, gate["sql"]))
            for event in _sql_event_types(gate["sql"]):
                _record_consumer(event, label)
        for event in hook.get("check", {}).get("event_types", []) or []:
            _record_consumer(event, label)
        auto = hook.get("auto_record", {})
        if auto.get("event_type"):
            tools = ",".join(hook.get("tools", []) or []) or "*"
            model.writers.setdefault(auto["event_type"], []).append(
                Writer(
                    auto["event_type"],
                    f"engine:auto_record:{tools}",
                    f"{label} auto_record",
                )
            )
    for monitor in hooks_doc.get("monitors", []):
        for event in monitor.get("trigger", {}).get("event_types", []) or []:
            _record_consumer(event, f"hooks.toml: monitor {monitor.get('name', '?')}")

    renders_path = config_dir / "renders.toml"
    if renders_path.exists():
        for render in _load_toml(renders_path).get("renders", []):
            target = render.get("target", "?")
            for event in render.get("event_types", []) or []:
                _record_consumer(event, f"renders.toml: {target}", kind="render")
            # A template is a consumer too, and neither linter saw it: both
            # reported `prediction`/`prediction_outcome` as dead vocabulary
            # while summary.md.tera has a whole section keyed on them.
            template = render.get("template")
            if not template:
                continue
            template_path = config_dir / template
            if not template_path.exists():
                continue
            body = template_path.read_text(encoding="utf-8")
            for event in _TERA_EVENT_TYPE.findall(body):
                _record_consumer(event, f"{template} → {target}", kind="render")


_SQL_IN_PYTHON = re.compile(r"\bFROM\s+events\b", re.I)


def parse_python_predicates(model: Model) -> None:
    """Find gate predicates a Python hook carries as a string literal.

    Parsed rather than grepped, for one reason that matters: Python folds
    adjacent string literals at compile time, and the predicate this check
    exists to find is written as four concatenated fragments across four
    lines. A regex would have to reassemble them; ``ast`` already has.
    """
    for directory in model.tree.py_dirs:
        if not directory.is_dir():
            continue
        for py in sorted(directory.rglob("*.py")):
            if "__pycache__" in py.parts:
                continue
            try:
                parsed = ast.parse(py.read_text(encoding="utf-8"))
            except SyntaxError:  # pragma: no cover - not our file to fix
                continue
            rel = model.tree.rel(py)
            for node in ast.walk(parsed):
                if not isinstance(node, ast.Constant) or not isinstance(
                    node.value, str
                ):
                    continue
                value = node.value
                if "SELECT" in value.upper() and _SQL_IN_PYTHON.search(value):
                    model.python_predicates.append(
                        Predicate(f"{rel}:{node.lineno}", value)
                    )


def parse_python_writers(model: Model) -> None:
    """Discover write paths and SQL consumers in Python."""
    tool_dirs = set(model.tree.tool_dirs)
    for directory in model.tree.py_dirs:
        if not directory.is_dir():
            continue
        kind = "tool" if directory in tool_dirs else "hook"
        for py in sorted(directory.rglob("*.py")):
            if "__pycache__" in py.parts:
                continue
            text = py.read_text(encoding="utf-8")
            rel = model.tree.rel(py)
            for pattern in (
                _PY_AUTHED_EVENT,
                _PY_ARGV_EVENT,
                _PY_EVENT_TYPE_LITERAL,
            ):
                for match in pattern.finditer(text):
                    event = match.group(1)
                    line = text.count("\n", 0, match.start()) + 1
                    model.writers.setdefault(event, []).append(
                        Writer(event, f"{kind}:{rel}", f"{rel}:{line}")
                    )
            for match in _PY_SQL_CONSUMER.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                model.consumed.setdefault(match.group(1), []).append(f"{rel}:{line}")


_INLINE_CODE_SPAN = re.compile(r"`([^`\n]+)`")


def _skill_command_lines(md: Path) -> list[tuple[int, str, bool]]:
    """Every sahjhan invocation a skill file actually teaches.

    Two surfaces, both required. Holtz's phase references overwhelmingly give
    commands as **inline code spans** mid-sentence ("Run `sahjhan … transition
    resume` → now you are in fix_loop"), not as fenced blocks; scanning only
    fences reported eleven transitions as undocumented that are documented on
    the very page an agent reads before running them.

    Restricting to code — fence or span — is what keeps English prose out.
    ``lens_quiz.py`` naming an event in a sentence is not a command anyone can
    run, and counting it as one is how the prototype invented producers.

    A leading ``!`` marks the third surface: a command the *user* runs. Claude
    Code executes it directly rather than as a tool call, so no PreToolUse hook
    sees it and the agent cannot issue it. That makes it the only write path in
    the tree attributable to a person, which is what `human` attestation means
    (#81, and the pre-existing `! sahjhan daemon stop`).
    """
    lines: list[tuple[int, str, bool]] = []
    in_fence = False
    for number, raw in enumerate(md.read_text(encoding="utf-8").splitlines(), 1):
        stripped = raw.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            if _SKILL_SAHJHAN_LINE.search(stripped):
                lines.append((number, stripped, stripped.startswith("!")))
            continue
        for span in _INLINE_CODE_SPAN.findall(raw):
            if _SKILL_SAHJHAN_LINE.search(span):
                text = span.strip()
                lines.append((number, text, text.startswith("!")))
    return lines


def _hook_message_lines(config_dir: Path) -> list[tuple[str, str]]:
    """sahjhan commands printed by a blocking hook's message.

    A block message that says "Record with: sahjhan … event X" *is* a taught
    write path — arguably the most load-bearing one, because it is what the
    agent reads at the moment it is stuck. Treating it as documentation rather
    than a producer is how an event ends up looking writerless.
    """
    lines: list[tuple[str, str]] = []
    hooks_doc = _load_toml(config_dir / "hooks.toml")
    for section in ("hooks", "monitors"):
        for entry in hooks_doc.get(section, []) or []:
            message = entry.get("message", "")
            if message and _SKILL_SAHJHAN_LINE.search(message):
                label = entry.get("name") or entry.get("event", "?")
                lines.append((f"enforcement/hooks.toml ({label})", message))
    return lines


def _scan_taught_command(
    model: Model, line: str, producer_id: str, origin: str
) -> None:
    """Record every write path one taught command line opens up."""
    alias_targets = {
        alias: target
        for alias, target in model.aliases.items()
        if target.startswith(("event ", "transition ", "set complete"))
    }
    for pattern in (_SKILL_EVENT, _SKILL_AUTHED_EVENT):
        for match in pattern.finditer(line):
            model.writers.setdefault(match.group(1), []).append(
                Writer(match.group(1), producer_id, origin)
            )
    for match in _SKILL_TRANSITION.finditer(line):
        model.skill_transitions.setdefault(match.group(1), []).append(origin)
    if _SKILL_SET_COMPLETE.search(line):
        model.writers.setdefault("set_member_complete", []).append(
            Writer("set_member_complete", producer_id, origin)
        )
    # An alias is a real command surface: `sahjhan finding …` writes a
    # `finding` event just as `sahjhan event finding` does.
    for alias, target in alias_targets.items():
        if not re.search(rf"\bsahjhan\b[^|;&\n]*?\b{re.escape(alias)}\b", line):
            continue
        verb, _, name = target.partition(" ")
        if verb == "event":
            model.writers.setdefault(name, []).append(
                Writer(name, producer_id, f"{origin} (alias {alias})")
            )
        elif verb == "transition":
            model.skill_transitions.setdefault(name, []).append(origin)
        elif verb == "set":
            model.writers.setdefault("set_member_complete", []).append(
                Writer("set_member_complete", producer_id, f"{origin} (alias {alias})")
            )


def parse_skill_writers(model: Model) -> None:
    """Discover what commands the agent is actually taught to run."""
    for md in sorted(model.tree.skills_dir.rglob("*.md")):
        if ".pytest_cache" in md.parts:
            continue
        rel = model.tree.rel(md)
        for number, line, by_human in _skill_command_lines(md):
            actor = "human" if by_human else "agent"
            _scan_taught_command(model, line, f"{actor}:{rel}", f"{rel}:{number}")
    for origin, message in _hook_message_lines(model.tree.config_dir):
        _scan_taught_command(model, message, "agent:enforcement/hooks.toml", origin)


def parse_hook_registration(model: Model) -> None:
    """Map each hook script to the harness events it is registered for.

    A module that writes an event but is only *imported* by an entrypoint
    inherits that entrypoint's registration — the daemon authenticates the
    process, and the process is the entrypoint.
    """
    if model.tree.hooks_json.exists():
        doc = json.loads(model.tree.hooks_json.read_text(encoding="utf-8"))
        for host_event, groups in doc.get("hooks", {}).items():
            for group in groups:
                for entry in group.get("hooks", []):
                    command = entry.get("command", "")
                    for match in re.finditer(r"([\w./-]+\.py)", command):
                        script = match.group(1).split("/")[-1]
                        model.hook_entrypoints.setdefault(script, []).append(host_event)

    # Follow imports: a helper module runs inside its importer's process, so it
    # inherits both that entrypoint's harness events and its daemon identity.
    modules: dict[str, Path] = {}
    for directory in model.tree.py_dirs:
        if directory.is_dir():
            for py in directory.rglob("*.py"):
                if "__pycache__" not in py.parts:
                    modules.setdefault(py.name, py)
    imports: dict[str, set[str]] = {}
    for name, path in modules.items():
        text = path.read_text(encoding="utf-8")
        imports[name] = {
            f"{imported}.py"
            for imported in re.findall(r"^\s*(?:from|import)\s+(\w+)", text, re.M)
            if f"{imported}.py" in modules
        }
    for entrypoint in list(model.hook_entrypoints):
        seen = {entrypoint}
        stack = [entrypoint]
        while stack:
            current = stack.pop()
            model.reaching_entrypoints.setdefault(current, set()).add(entrypoint)
            for imported in imports.get(current, set()):
                if imported not in seen:
                    seen.add(imported)
                    stack.append(imported)
        for reached in seen:
            known = model.hook_entrypoints.setdefault(reached, [])
            for host_event in model.hook_entrypoints[entrypoint]:
                if host_event not in known:
                    known.append(host_event)

    if model.tree.trusted_callers.exists():
        callers = _load_toml(model.tree.trusted_callers).get("callers", {})
        model.trusted_callers = {key.split("/")[-1] for key in callers}


_BOOTSTRAP_DENIED_EVENTS = re.compile(
    r"BLOCKED_SAHJHAN_SUBSUB.*?[\"']event[\"']\s*:\s*\{([^}]*)\}", re.S
)


def parse_agent_denylist(model: Model) -> None:
    """Event types the bootstrap hook refuses on the agent's Bash path.

    `restricted = true` is the wrong tool when the intended writer is a
    *person*: it admits daemon-authenticated hooks, and a human at the terminal
    runs the bare CLI. Denying the agent's tool-call path is the other way to
    make an event agent-unwritable, so H5 has to know about it or it would
    report the human channel as forgeable evidence (#81).
    """
    bootstrap = model.tree.config_dir / "hooks" / "_sahjhan_bootstrap.py"
    if not bootstrap.exists():
        return
    match = _BOOTSTRAP_DENIED_EVENTS.search(bootstrap.read_text(encoding="utf-8"))
    if match:
        model.agent_denied_events = set(
            re.findall(r"[\"']([a-z_][a-z0-9_]*)[\"']", match.group(1))
        )


def build_model(tree: Tree | None = None) -> Model:
    model = Model(tree=tree or Tree())
    parse_config(model)
    parse_agent_denylist(model)
    parse_python_predicates(model)
    parse_block_sites(model)
    parse_python_writers(model)
    parse_skill_writers(model)
    parse_hook_registration(model)
    return model


# ── Checks ───────────────────────────────────────────────────────────────────


def _declared_producers(model: Model, event: str) -> list[str]:
    return [
        producer.get("id", "")
        for producer in model.events.get(event, {}).get("producers", []) or []
    ]


def check_h1_unsatisfiable(model: Model) -> list[Finding]:
    """Something consumes an event nothing in the tree can write.

    Severity follows what a missing writer costs. A *gate* with no writer is a
    wall: the agent reads the intent, does the work, and stays blocked with no
    discoverable escape — #73's shape. A *render* with no writer only leaves a
    document section permanently empty, which is rot rather than a deadlock.
    """
    findings = []
    for event, consumers in sorted(model.consumed.items()):
        if event in ENGINE_BUILTIN_EVENTS or event not in model.events:
            continue
        if model.writers.get(event) or _declared_producers(model, event):
            continue
        kinds = model.consumer_kinds.get(event, {"gate"})
        blocking = "gate" in kinds
        findings.append(
            Finding(
                "H1",
                "error" if blocking else "warning",
                f"events.toml: event '{event}'",
                "consumed by "
                + ", ".join(sorted(set(consumers))[:3])
                + " but no write path exists anywhere in the tree "
                "(no hook, no skill command, no alias, no emit)",
                "add the writer, or drop the gate — an agent that hits this "
                "is blocked by a gate whose escape is undiscoverable"
                if blocking
                else "nothing records this, so the section it feeds is always "
                "empty — teach the command, or drop the section",
            )
        )
    return findings


def check_h2_false_declarations(model: Model) -> list[Finding]:
    """A declared producer that does not resolve to a real writer.

    The producer ``id`` is opaque to sahjhan by design, which leaves holtz free
    to give it meaning — and an obligation to check it:

    ``agent:cli``
        the agent's own ``sahjhan event <type>``. Real for any event that is
        not ``restricted``, because ``event`` is on the bootstrap allowlist.
    ``hook:<path>``
        one named Python writer. The file must exist and must actually write
        this event type.
    ``engine:emits:<command>`` / ``engine:auto_record:<tools>``
        declared in TOML, so discovery must have found it.
    """
    findings = [
        Finding(
            "H2",
            "error",
            f"transitions.toml: transition '{command}'",
            f"references named query '{name}', which is not declared in "
            "protocol.toml [queries] — this analyzer cannot see what the gate "
            "consumes, so every other check is blind to it",
            "declare the query, or fix the name",
        )
        for command, name in model.unresolved_queries
    ]
    for event, spec in sorted(model.events.items()):
        discovered = {writer.producer_id for writer in model.writers.get(event, [])}
        for producer in spec.get("producers", []) or []:
            producer_id = producer.get("id", "")
            if producer_id == "agent:cli":
                if spec.get("restricted"):
                    findings.append(
                        Finding(
                            "H2",
                            "error",
                            f"events.toml: event '{event}' producer 'agent:cli'",
                            "claims the agent records this with `sahjhan event`, "
                            "but the event is restricted — the daemon refuses it",
                            "name the hook that really writes it, or drop "
                            "restricted = true",
                        )
                    )
                continue
            if producer_id.startswith("human:") and producer_id in discovered:
                # A human channel is only real if the agent's path is shut.
                # Otherwise the `!` in the docs is a convention, not a control.
                if event not in model.agent_denied_events:
                    findings.append(
                        Finding(
                            "H2",
                            "error",
                            f"events.toml: event '{event}' producer '{producer_id}'",
                            "claims a human-only write path, but the bootstrap "
                            "hook does not deny the agent's "
                            f"`sahjhan event {event}` — the agent can record it "
                            "too, so the channel is a convention, not a control",
                            "add it to BLOCKED_SAHJHAN_SUBSUB['event'] in "
                            "enforcement/hooks/_sahjhan_bootstrap.py",
                        )
                    )
                continue
            if producer_id in discovered:
                continue
            if producer_id.startswith(("hook:", "tool:")):
                path = producer_id.split(":", 1)[1]
                detail = (
                    "names a file that does not exist"
                    if not (model.tree.root / path).exists()
                    else "names a file that does not write this event"
                )
            else:
                detail = "matches no write path in the tree"
            findings.append(
                Finding(
                    "H2",
                    "error",
                    f"events.toml: event '{event}' producer '{producer_id}'",
                    f"{detail}; real writers: "
                    + (", ".join(sorted(discovered)) or "none"),
                    "the declaration is a claim — correct the id, or add the "
                    "writer it names",
                )
            )
    return findings


def check_h3_undeclared_writers(model: Model) -> list[Finding]:
    """A real writer that no declaration names.

    This is the "declared writer is the *only* writer" property, and it is
    deliberately scoped. For an `agent`-attested event the question is
    uninteresting — the answer is "the agent, from anywhere" — and demanding a
    declaration per skill file would fail the build every time someone added a
    doc mention. What matters is the precise writers: a hook, an emit, an
    auto_record. Those are stable, and an undeclared one on an event a gate
    trusts is #79's shape.
    """
    findings = []
    for event, writers in sorted(model.writers.items()):
        if event not in model.events:
            continue
        declared = set(_declared_producers(model, event))
        if not declared:
            continue  # nothing claimed yet — H1/H5 cover that case
        discovered = {writer.producer_id for writer in writers}
        undeclared = {
            producer_id
            for producer_id in discovered
            if producer_id not in declared and not producer_id.startswith("agent:")
        }
        if any(p.startswith("agent:") for p in discovered) and "agent:cli" not in declared:
            undeclared.add("agent:cli")
        for producer_id in sorted(undeclared):
            origins = sorted(
                {w.origin for w in writers if w.producer_id == producer_id}
                or {w.origin for w in writers if w.producer_id.startswith("agent:")}
            )
            findings.append(
                Finding(
                    "H3",
                    "error",
                    f"events.toml: event '{event}'",
                    f"written by undeclared producer '{producer_id}' "
                    f"({', '.join(origins[:3])})",
                    "declare it, or remove the write path — a gate can only "
                    "trust an event whose writers are all accounted for",
                )
            )
    return findings


def check_h4_hook_registration(model: Model) -> list[Finding]:
    """A named Python writer must actually be able to run, and be pinned.

    Two producer kinds reach this check, and they differ in exactly one way.
    A ``hook:`` runs because the *harness* fires it, so being absent from
    ``hooks/hooks.json`` means it never runs at all. A ``tool:`` runs because
    something invokes it by path — a gate command, or a command a skill file
    teaches — and will never be in ``hooks.json``; demanding registration of
    one would be a permanent false error rather than a check.

    What both owe is the pin: whichever process the daemon sees, it
    authenticates by content hash, so an unpinned writer of a ``restricted``
    event is refused at runtime no matter how it was started.
    """
    findings = []
    for event, spec in sorted(model.events.items()):
        for producer in spec.get("producers", []) or []:
            producer_id = producer.get("id", "")
            if not producer_id.startswith(("hook:", "tool:")):
                continue
            kind, path = producer_id.split(":", 1)
            script = path.split("/")[-1]
            if not (model.tree.root / path).exists():
                findings.append(
                    Finding(
                        "H4",
                        "error",
                        f"events.toml: event '{event}' producer '{producer_id}'",
                        "names a file that does not exist",
                        "fix the path, or drop the declaration",
                    )
                )
                continue
            if kind == "hook" and script not in model.hook_entrypoints:
                findings.append(
                    Finding(
                        "H4",
                        "error",
                        f"events.toml: event '{event}' producer '{producer_id}'",
                        "is not registered in hooks/hooks.json, and nothing "
                        "registered imports it — the harness never runs it",
                        "register the hook, or record the event from one that is",
                    )
                )
            # The daemon authenticates the *process* (SO_PEERCRED → pid →
            # script), so an imported module is trusted through whichever
            # entrypoint runs it. Demanding a pin on the module itself would
            # flag `quiz_vault.py`, which only ever executes inside the
            # already-pinned `quiz_capture.py`.
            if spec.get("restricted") and not (
                model.reaching_entrypoints.get(script, {script}) & model.trusted_callers
            ):
                findings.append(
                    Finding(
                        "H4",
                        "error",
                        f"events.toml: event '{event}' producer '{producer_id}'",
                        "writes a restricted event, but neither it nor any "
                        "entrypoint that runs it is hash-pinned in "
                        "enforcement/trusted-callers.toml — the daemon will "
                        "refuse it at runtime",
                        "run scripts/hash-trusted-callers.sh",
                    )
                )
    return findings


def check_h5_attestation(model: Model) -> list[Finding]:
    """An event claiming non-agent evidence that an agent can nonetheless write.

    ``sahjhan event <type>`` is on the agent's allowlist and can record any
    declared non-restricted type. So "only a hook writes this" is only true if
    the event is ``restricted``; otherwise the claim is decoration.
    """
    findings: list[Finding] = []
    if not model.attestation_levels:
        return findings
    weakest = model.attestation_levels[0]
    for event, spec in sorted(model.events.items()):
        attests = spec.get("attestation")
        if not attests or attests == weakest:
            continue
        denied = event in model.agent_denied_events
        if not spec.get("restricted") and not denied:
            findings.append(
                Finding(
                    "H5",
                    "error",
                    f"events.toml: event '{event}'",
                    f"declares attestation '{attests}' but the agent can write "
                    "it: the event is not restricted, and the bootstrap hook "
                    "does not deny it — `sahjhan event` is on the allowlist",
                    "set restricted = true (for a hook writer), add it to "
                    "BLOCKED_SAHJHAN_SUBSUB['event'] (for a human writer), or "
                    f"downgrade the attestation to '{weakest}'",
                )
            )
        agent_writers = sorted(
            {
                writer.producer_id
                for writer in model.writers.get(event, [])
                if writer.producer_id.startswith("agent:")
            }
        )
        if agent_writers and not denied:
            findings.append(
                Finding(
                    "H5",
                    "error",
                    f"events.toml: event '{event}'",
                    f"declares attestation '{attests}' but a skill file teaches "
                    f"the agent to write it ({', '.join(agent_writers)})",
                    "remove the command from the skill file, or downgrade the "
                    "attestation to match who really writes it",
                )
            )
    return findings


def check_h6_skill_agreement(model: Model) -> list[Finding]:
    """Transition commands and skill files must agree in both directions."""
    findings = []
    declared = {t.get("command", "") for t in model.transitions}
    # sahjhan resolves `set complete <set>` as a transition command; the skill
    # teaches it through the `set` verb, which parse_skill_writers records as a
    # set_member_complete write rather than a transition.
    declared = {command for command in declared if not command.startswith("set ")}

    for command in sorted(declared):
        if command not in model.skill_transitions:
            findings.append(
                Finding(
                    "H6",
                    "warning",
                    f"transitions.toml: transition '{command}'",
                    "no skill file teaches this command — the agent has no "
                    "documented way to reach it",
                    "document it in the phase reference, or remove the transition",
                )
            )
    for command, origins in sorted(model.skill_transitions.items()):
        if command not in declared:
            findings.append(
                Finding(
                    "H6",
                    "error",
                    f"skill files: transition '{command}'",
                    f"taught at {', '.join(sorted(origins)[:3])} but no such "
                    "transition exists — the command fails at runtime",
                    "fix the skill file, or add the transition",
                )
            )
    return findings


# Matches sahjhan's `lint::similarity::DEFAULT_THRESHOLD`. Deliberately the
# same number: L6 compares TOML predicates to each other and H7 compares
# Python's copies to those, so two different thresholds would mean two
# different answers to "is this the same predicate" — the defect being hunted,
# committed by the tools hunting it.
SIMILARITY_THRESHOLD = 0.85


def normalize_sql(sql: str) -> list[str]:
    """Token form of a predicate: lowercase, punctuation split out.

    A reformatted copy must not read as a different predicate, so spacing and
    case are discarded and punctuation becomes its own token. Ported from
    sahjhan's `normalize_sql` rather than reinvented, for the same reason the
    threshold is shared.
    """
    tokens: list[str] = []
    current = ""
    for char in sql.strip().rstrip(";"):
        if char.isspace():
            if current:
                tokens.append(current)
                current = ""
        elif char.isalnum() or char in "_'\"":
            current += char.lower()
        else:
            if current:
                tokens.append(current)
                current = ""
            tokens.append(char)
    if current:
        tokens.append(current)
    return tokens


def sql_similarity(left: str, right: str) -> float:
    """0.0–1.0 token-level similarity of two predicates."""
    return difflib.SequenceMatcher(
        None, normalize_sql(left), normalize_sql(right)
    ).ratio()


def check_h7_predicate_copies(model: Model) -> list[Finding]:
    """A gate predicate that also exists as a string literal in Python.

    #77 was two copies of one fact drifting apart: the commit gate blocked on a
    hand-maintained mirror while the escape it printed was decided by the
    ledger, so the block's own instruction was unsatisfiable — a deadlock. The
    fix made the hook run the gate's query. But *run the same SQL* and *hold a
    copy of the same SQL* are different things, and the tree still holds a
    copy: nothing compares a Python string to a TOML gate, so the next edit to
    one of them re-opens #77 silently.

    The escape is not "keep them in sync". It is to name the predicate in
    ``protocol.toml [queries]`` and have both sides resolve the name, so they
    are one object and cannot disagree. A hook that does that has no SQL in it
    for this check to find.
    """
    findings = []
    for predicate in model.python_predicates:
        matches = [
            (sql_similarity(predicate.sql, other.sql), other)
            for other in model.toml_predicates
        ]
        if not matches:
            continue
        score, nearest = max(matches, key=lambda pair: pair[0])
        if score < SIMILARITY_THRESHOLD:
            continue
        named = [
            origin.split("[queries.")[1].rstrip("]")
            for origin, _ in [(p.origin, p.sql) for p in model.toml_predicates]
            if "[queries." in origin
        ]
        findings.append(
            Finding(
                "H7",
                "error",
                f"{predicate.origin}",
                f"holds a copy of the predicate at {nearest.origin} "
                f"({score:.0%} identical) — two expressions of one fact, which "
                "is how #77 deadlocked a commit gate against its own printed "
                "escape",
                "declare it once in protocol.toml [queries.<name>], reference "
                "it from the gate with query = \"<name>\", and have the hook "
                "resolve the same name at runtime instead of carrying the SQL"
                + (f" (existing names: {', '.join(sorted(named))})" if named else ""),
            )
        )
    return findings


# The helpers that end a hook by refusing the tool call. A string reaching one
# of these is not documentation — it is what the agent reads at the moment it
# is stuck, so the command in it is a promise that the escape is reachable.
BLOCK_HELPERS = frozenset({"exit_block", "exit_stop_block"})

# "run pattern_check", "Run: sahjhan … transition pattern_check". Both forms
# appear in the tree; the second is the one an agent can paste. Matches are
# filtered against the real transition list, so prose like "run the suite"
# cannot become an escape.
_ESCAPE_FORMS = (
    re.compile(r"\btransition\s+`?([a-z_][a-z0-9_]*)`?"),
    re.compile(r"\brun\s+`?([a-z_][a-z0-9_]*)`?", re.I),
)


def _named_escapes(text: str, commands: set[str], own: str = "") -> list[str]:
    found = []
    for pattern in _ESCAPE_FORMS:
        for match in pattern.findall(text):
            if match in commands and match != own and match not in found:
                found.append(match)
    return found


def parse_block_sites(model: Model) -> None:
    """Collect every place that blocks the agent and prints a way out.

    Python blocks are found at the *call site* rather than by scanning strings:
    ``exit_block("… transition pattern_check")`` is an escape, while the same
    sentence in an obligation nudge or a status line is not, and a check that
    cannot tell them apart would report five sites to catch one.
    """
    for directory in model.tree.py_dirs:
        if not directory.is_dir():
            continue
        for py in sorted(directory.rglob("*.py")):
            if "__pycache__" in py.parts:
                continue
            source = py.read_text(encoding="utf-8")
            try:
                parsed = ast.parse(source)
            except SyntaxError:  # pragma: no cover - not our file to fix
                continue
            rel = model.tree.rel(py)
            for node in ast.walk(parsed):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                name = getattr(func, "id", None) or getattr(func, "attr", None)
                if name not in BLOCK_HELPERS:
                    continue
                text = " ".join(
                    part.value
                    for part in ast.walk(node)
                    if isinstance(part, ast.Constant) and isinstance(part.value, str)
                )
                model.block_sites.append(
                    BlockSite(f"{rel}:{node.lineno}", text, source)
                )


def check_h8_escape_identity(model: Model) -> list[Finding]:
    """A block whose printed escape is decided by a different predicate.

    This is #77 stated as a property. The commit gate blocked on "3+ fixes
    since the last pattern analysis" and told the agent to run
    ``transition pattern_check`` — whose own gate decided the *same* fact with
    a different expression. When the two drifted, the gate blocked a real fix
    commit and the escape it printed was itself blocked. The agent was told to
    do the one thing it could not do.

    Two predicates that mean to be the same fact cannot be kept in agreement by
    care. They agree when they are one object: a named query both sides
    reference. So the rule is nominal, not textual — the block must name the
    query its escape is gated on.
    """
    findings: list[Finding] = []
    commands = {
        transition.get("command", "")
        for transition in model.transitions
        if transition.get("command")
    }
    # Which named queries decide each transition's readiness.
    escape_queries: dict[str, set[str]] = {}
    for transition in model.transitions:
        command = transition.get("command", "")
        for gate in transition.get("gates", []) or []:
            escape_queries.setdefault(command, set()).update(_gate_query_names(gate))

    def _judge(
        where: str,
        text: str,
        referenced: set[str],
        own: str = "",
        unnamed_is_finding: bool = True,
    ) -> None:
        for escape in _named_escapes(text, commands, own):
            available = escape_queries.get(escape) or set()
            if not available and not unnamed_is_finding:
                # A block whose escape is gated on inline predicates may be a
                # perfectly good block: `fix_commit`'s gates are *more work*
                # (record the blast radius, pass the suite), not a restatement
                # of the fact that blocked. Only the nominal case is decidable
                # here, so the undecidable one stays quiet rather than crying
                # wolf at every honest escape in the tree.
                continue
            if not available:
                findings.append(
                    Finding(
                        "H8",
                        "warning",
                        where,
                        f"prints `{escape}` as the way out, but {escape}'s own "
                        "readiness is decided by an inline predicate — nothing "
                        "can check that the fact blocking here is the fact "
                        "that unblocks there",
                        f"name {escape}'s predicate in protocol.toml "
                        "[queries.<name>] and decide both sides by it",
                    )
                )
            elif not (available & referenced):
                findings.append(
                    Finding(
                        "H8",
                        "error",
                        where,
                        f"blocks on a fact that is not the one `{escape}` is "
                        f"gated on ({', '.join(sorted(available))}) — the "
                        "escape it prints can be unsatisfiable at the moment "
                        "it is printed, which is exactly how #77 deadlocked",
                        f"decide this block with query = "
                        f"\"{sorted(available)[0]}\" so the block condition and "
                        "the escape's readiness are one object",
                    )
                )

    for transition in model.transitions:
        command = transition.get("command", "")
        for gate in transition.get("gates", []) or []:
            _judge(
                f"transitions.toml: transition '{command}'",
                str(gate.get("intent", "")),
                _gate_query_names(gate),
                own=command,
            )
    for hook in model.hooks:
        if hook.get("action") != "block":
            continue
        _judge(
            f"hooks.toml: {hook.get('event', '?')} block",
            str(hook.get("message", "")),
            _gate_query_names(hook.get("gate", {})),
        )
    for site in model.block_sites:
        # A Python hook cannot reference a gate; it can only *use the name*.
        # Requiring the name to appear in the file makes the chain checkable:
        # block → the value it reads → the query that derived it → the gate.
        # A file that names no query is not making a claim this check can
        # falsify, so it is left alone.
        referenced = {name for name in model.queries if name in site.source}
        if referenced:
            _judge(site.origin, site.message, referenced, unnamed_is_finding=False)
    return findings


_ABSENCE_PREDICATE = re.compile(r"count\s*\(\s*\*\s*\)\s*=\s*0", re.I)


def check_h9_transition_state_decoupling(model: Model) -> list[Finding]:
    """A transition that acts on an item without recording the item's new state.

    A gate reading "this item must not already be resolved or deferred" is the
    transition saying, in config, that it is *about to* resolve or defer it.
    If it then emits nothing, the ledger holds a state_transition and the item
    stays open — the transition and the state it implies are two facts, and the
    agent is left to state the second one by hand.

    That costs twice. It burns a command per item on a fact the engine already
    has (holtz's core principle is that the agent should never restate what the
    system knows), and it is a correctness hazard: run the pair in the wrong
    order and the ``item_open`` gate refuses the transition that was supposed
    to record it. ``fix_commit`` already solved this with ``emits``; this check
    is that fix stated as a property, so the next item-scoped transition cannot
    ship without it.
    """
    findings = []
    for transition in model.transitions:
        args = transition.get("args") or []
        if not args:
            continue
        command = transition.get("command", "?")
        emitted = {
            emit.get("event") for emit in transition.get("emits", []) or [] if emit
        }
        for gate in transition.get("gates", []) or []:
            sql = gate.get("sql")
            for name in _gate_query_names(gate):
                sql = sql or model.queries.get(name, {}).get("sql")
            if not isinstance(sql, str):
                continue
            # Per-item, and phrased as "none of these has happened yet".
            if not any(f"{{{{{arg}}}}}" in sql for arg in args):
                continue
            if not _ABSENCE_PREDICATE.search(sql):
                continue
            closing = _sql_event_types(sql)
            if not closing or closing & emitted:
                continue
            findings.append(
                Finding(
                    "H9",
                    "error",
                    f"transitions.toml: transition '{command}'",
                    f"is gated on {args[0]} not yet being closed by "
                    + ", ".join(f"'{event}'" for event in sorted(closing))
                    + ", but emits none of them — recording the transition "
                    "leaves the item open, so the fact has to be stated a "
                    "second time by hand",
                    "add an emits block "
                    f"(event = \"{sorted(closing)[0]}\", "
                    f"fields = {{ id = \"{{{{{args[0]}}}}}\" }}) so one command "
                    "records both, the way fix_commit does",
                )
            )
    return findings


CHECKS = {
    "H1": check_h1_unsatisfiable,
    "H2": check_h2_false_declarations,
    "H3": check_h3_undeclared_writers,
    "H4": check_h4_hook_registration,
    "H5": check_h5_attestation,
    "H6": check_h6_skill_agreement,
    "H7": check_h7_predicate_copies,
    "H8": check_h8_escape_identity,
    "H9": check_h9_transition_state_decoupling,
}


def run_checks(model: Model, only: list[str] | None = None) -> list[Finding]:
    selected = only or list(CHECKS)
    findings: list[Finding] = []
    for name in selected:
        findings.extend(CHECKS[name](model))
    return findings


# ── Census ───────────────────────────────────────────────────────────────────


def attestation_of(model: Model, event: str) -> str:
    """What one event's word is worth.

    Defined here, once, because two things ask: the ``--census`` view and the
    generated contract document. Two copies of this rule would drift into two
    different answers to "how much of the evidence is the agent's own word" —
    the same defect the checks below exist to find.
    """
    if event in ENGINE_BUILTIN_EVENTS:
        return ENGINE_ATTESTATION
    spec = model.events.get(event, {})
    declared = spec.get("attestation")
    if declared:
        return str(declared)
    # No declared class: agent-attested unless something stops the agent
    # writing it. "unstated" is said out loud because a blank cell reads as
    # "fine", and this one is not.
    return "agent" if not spec.get("restricted") else "unstated"


def gate_consumed_events(model: Model) -> dict[str, str]:
    """Every event some *gate* depends on → its attestation class.

    Wider than the transition table: a hooks.toml gate (the TDD block) and a
    predicate embedded in a Python hook (the commit gate) decide as much as a
    transition gate does. Render-only consumers are excluded — an unwritten
    event there leaves a document section empty, not a run blocked.
    """
    consumed = {}
    for event in sorted(model.consumed):
        # A Python-embedded predicate records no kind; default to "gate",
        # matching H1. Calling that one a render would hide the commit gate.
        if "gate" in model.consumer_kinds.get(event, {"gate"}):
            consumed[event] = attestation_of(model, event)
    return consumed


def census(model: Model) -> list[tuple[str, str, str]]:
    """One row per gate-consumed event: who writes it, and how strong that is.

    This is the posture number the plan wanted visible rather than accidental:
    what share of the evidence a gate relies on is the agent's own word. The
    committed form is ``docs/ENFORCEMENT-CONTRACT.md``; this is the same data
    on the terminal.
    """
    rows = []
    for event, attests in gate_consumed_events(model).items():
        writers = sorted({writer.producer_id for writer in model.writers.get(event, [])})
        rows.append((event, attests, ", ".join(writers) or "NONE"))
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true", help="warnings fail too")
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--census", action="store_true", help="attestation posture")
    parser.add_argument("--only", action="append", metavar="CHECK", choices=list(CHECKS))
    parser.add_argument("--config-dir", default=str(ENFORCEMENT))
    args = parser.parse_args()

    config_dir = Path(args.config_dir).resolve()
    model = build_model(Tree(config_dir=config_dir))
    findings = run_checks(model, args.only)
    errors = [f for f in findings if f.level == "error"]
    warnings = [f for f in findings if f.level == "warning"]

    if args.as_json:
        print(
            json.dumps(
                {
                    "findings": [vars(f) for f in findings],
                    "errors": len(errors),
                    "warnings": len(warnings),
                    "census": census(model) if args.census else [],
                },
                indent=2,
            )
        )
    else:
        for finding in findings:
            print(finding.render())
        if args.census:
            print("\nGate-consumed events — who vouches for what:\n")
            width = max((len(row[0]) for row in census(model)), default=10)
            for event, attests, writers in census(model):
                print(f"  {event:<{width}}  {attests:<8}  {writers}")
            agent_backed = sum(
                1 for _, attests, _ in census(model) if attests == "agent"
            )
            total = len(census(model))
            print(
                f"\n  {agent_backed} of {total} gate-consumed events are the "
                "agent's own word."
            )
        checks = ", ".join(args.only or CHECKS)
        print(
            f"\n{len(errors)} error(s), {len(warnings)} warning(s) "
            f"from {len(args.only or CHECKS)} check(s): {checks}"
        )

    if errors:
        return 1
    if warnings and args.strict:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
