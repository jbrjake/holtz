#!/usr/bin/env python3
"""Evert the enforcement layering into a document a person can read (#82).

``scripts/enforcement_lint.py`` makes CI red when a gate stops meaning what it
says. That is detection. The request behind #82 was *comprehension*: the chain
behind a gate spans five files linked by nothing but convention, so nobody can
see the weak link by scrolling past it.

This writes that chain down. One row per gate:

    gate → the fact it requires → the event carrying it → who writes it →
    what that writer's word is worth → whether the agent could have faked it

The #79 row would have read ``resume | context must be reset | context_reset |
primer.py | ambient``, and ``ambient`` in that row is the bug — legible with no
analyzer running at all. Which is the point: the linter catches the defect
classes we have already named, and the document is how a reader catches the one
we have not.

The output is generated, committed, and freshness-gated
(``tests/test_enforcement_contract.py``, and ``--check`` in
``scripts/lint-enforcement.sh``), so it cannot drift from the config the way
prose does. Nothing here re-derives facts: the model is
``enforcement_lint.build_model()``, the same one the checks are made of.

Usage::

    python3 scripts/enforcement_contract.py            # print
    python3 scripts/enforcement_contract.py --write    # regenerate the doc
    python3 scripts/enforcement_contract.py --check    # exit 1 if stale
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from enforcement_lint import (  # noqa: E402
    ENGINE_ATTESTATION as ENGINE,  # noqa: N811
)
from enforcement_lint import (
    ENGINE_BUILTIN_EVENTS,
    REPO_ROOT,
    Model,
    Tree,
    attestation_of,
    build_model,
    gate_consumed_events,
    gate_event_types,
)

CONTRACT_PATH = REPO_ROOT / "docs" / "ENFORCEMENT-CONTRACT.md"

GENERATED_BY = "python3 scripts/enforcement_contract.py --write"

# A gate that reads no event checks the world directly at gate time — the test
# suite runs, the file is stat'd, the snapshot is re-measured. No ledger
# evidence is involved, so no event attestation applies; `direct` is the class
# for "the engine looked, rather than believing a record".
DIRECT = "direct"
UNGATED = "ungated"

# Ranked weakest-first. The event classes come from `[attestation] levels` in
# protocol.toml — holtz declares the lattice, sahjhan's L7 enforces it — and
# `direct` is slotted just above `agent` because the agent can still arrange
# the world a direct check observes (gut a test, touch a file); what it cannot
# do is assert the fact without doing the work.
_EXTRA_RANKS = {UNGATED: -1, DIRECT: 0.5, ENGINE: 0.6}

_EDGE_COLOURS = {
    UNGATED: "#b0b0b0",
    "agent": "#d1495b",
    DIRECT: "#e08a2e",
    ENGINE: "#c9a227",
    "tool": "#2a9d8f",
    "ambient": "#8d6cab",
    "host": "#2f6fb0",
    "human": "#1f7a3d",
}

_CLASS_MEANING = {
    "agent": "a command the agent runs — it can produce this at will",
    "tool": "a Pre/PostToolUse hook watching a real tool call — the agent can "
    "cause it, but only by doing the thing",
    "ambient": "a signal that occurs without anyone intending it — the #79 trap",
    "host": "a session-lifecycle act no tool call can produce",
    "human": "a command only a person at the terminal can run",
    DIRECT: "no ledger evidence — the engine checks the world when the gate runs",
    ENGINE: "sahjhan's own record of a transition it allowed — producible only "
    "by passing that transition's gates",
}


# ── Rows ─────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class EvidenceRow:
    fact: str
    event: str  # "" for a direct check
    writers: str
    attests: str
    forgeable: str


@dataclass(frozen=True)
class GateRow:
    command: str
    src: str
    dst: str
    requires: str  # transitions.integrity.requires_attestation, or ""
    boundary: str
    evidence: tuple[EvidenceRow, ...]

    @property
    def weakest(self) -> str:
        classes = [row.attests for row in self.evidence]
        return min(classes, key=_rank) if classes else UNGATED


def _rank(attests: str) -> float:
    if attests in _EXTRA_RANKS:
        return _EXTRA_RANKS[attests]
    return float(_LEVELS.index(attests)) if attests in _LEVELS else len(_LEVELS)


_LEVELS: list[str] = []


def _forgeable(model: Model, event: str) -> str:
    """Could the party the gate constrains have manufactured this evidence?"""
    if event in ENGINE_BUILTIN_EVENTS:
        return "no — written by the engine, only by passing the gate"
    if event in model.agent_denied_events:
        return "no — bootstrap denies `sahjhan event`"
    if model.events.get(event, {}).get("restricted"):
        return "no — daemon refuses unauthenticated callers"
    return "**yes** — `sahjhan event`"


def _writers_of(model: Model, event: str) -> str:
    """The declared producers. H2/H3 are what make this the real answer."""
    if event in ENGINE_BUILTIN_EVENTS:
        return "`engine:sahjhan`"
    declared = [
        p.get("id", "")
        for p in model.events.get(event, {}).get("producers", []) or []
    ]
    if declared:
        return ", ".join(f"`{producer}`" for producer in declared)
    discovered = sorted({w.producer_id for w in model.writers.get(event, [])})
    if discovered:
        return ", ".join(f"`{producer}`" for producer in discovered) + " *(undeclared)*"
    return "**nothing**"


def _gate_fact(model: Model, gate: dict) -> str:
    """What the gate is trying to be true, in one line.

    ``intent`` when the author wrote one — and a named query carries its
    intent for every gate that references it, which is a quiet argument for
    naming predicates: the prose stops being copied along with the SQL.
    """
    intent = gate.get("intent")
    if not intent:
        named = gate.get("query")
        if isinstance(named, str):
            intent = model.queries.get(named, {}).get("intent")
    if intent:
        return str(intent)

    kind = gate.get("type", "?")
    if kind == "file_exists":
        return f"`{gate.get('path')}` exists"
    if kind == "command_succeeds":
        return f"`{gate.get('cmd')}` exits 0"
    if kind == "no_violations":
        return "no unresolved protocol violations"
    if kind in ("ledger_has_event", "ledger_has_event_since", "ledger_lacks_event"):
        return f"{kind} `{gate.get('event')}`"
    if kind == "set_covered":
        return f"every `{gate.get('set')}` member recorded via `{gate.get('event')}`"
    if kind == "min_elapsed":
        return f"≥{gate.get('seconds')}s since `{gate.get('event')}`"
    if kind == "query":
        return f"`{gate.get('query') or gate.get('sql')}`"
    return kind


def gate_rows(model: Model) -> list[GateRow]:
    """One row per transition, with one evidence line per gate × event.

    File order, not sorted: transitions.toml is grouped by phase, and reading
    the contract top to bottom should walk the run the way the agent does.
    """
    global _LEVELS
    _LEVELS = list(model.attestation_levels)

    rows = []
    for transition in model.transitions:
        evidence: list[EvidenceRow] = []
        for gate in transition.get("gates", []) or []:
            fact = _gate_fact(model, gate)
            events = sorted(gate_event_types(model, gate))
            if not events:
                evidence.append(EvidenceRow(fact, "", "—", DIRECT, "n/a"))
                continue
            for index, event in enumerate(events):
                evidence.append(
                    EvidenceRow(
                        fact if index == 0 else "↳",
                        event,
                        _writers_of(model, event),
                        attestation_of(model, event),
                        _forgeable(model, event),
                    )
                )
        integrity = transition.get("integrity", {})
        rows.append(
            GateRow(
                command=transition.get("command", "?"),
                src=transition.get("from", "?"),
                dst=transition.get("to", "?"),
                requires=str(integrity.get("requires_attestation", "")),
                boundary=str(transition.get("boundary", "")),
                evidence=tuple(evidence),
            )
        )
    return rows


# ── Rendering ────────────────────────────────────────────────────────────────


def _cell(text: str) -> str:
    """Markdown tables end a cell at a pipe, and gate SQL is full of them."""
    return text.replace("|", "\\|").replace("\n", " ").strip()


def _render_gates(model: Model, rows: list[GateRow]) -> list[str]:
    out = ["## Gates", ""]
    out.append(
        "Every transition in the protocol, in the order `transitions.toml` "
        "declares them. **Forgeable** answers the only question that matters "
        "for a gate meant to constrain the agent: could the agent have "
        "produced this evidence without doing the work?"
    )
    out.append("")
    for row in rows:
        out.append(f"### `{row.command}` — {row.src} → {row.dst}")
        out.append("")
        notes = []
        if row.requires:
            notes.append(
                f"requires attestation **{row.requires}** or stronger "
                "(`sahjhan lint` L7 fails the build if the evidence weakens)"
            )
        if row.boundary:
            notes.append(
                f"tagged with boundary **{row.boundary}** — no path from the "
                "boundary's origin may reach its target without traversing "
                "this edge (L3)"
            )
        if notes:
            out.extend([f"> {note}" for note in notes] + [""])
        if not row.evidence:
            out.extend(["*Ungated — this transition asserts nothing.*", ""])
            continue
        out.append("| Fact required | Evidence | Writer | Attests | Forgeable |")
        out.append("|---|---|---|---|---|")
        for line in row.evidence:
            event = f"`{line.event}`" if line.event else "*direct check*"
            out.append(
                f"| {_cell(line.fact)} | {event} | {_cell(line.writers)} "
                f"| `{line.attests}` | {_cell(line.forgeable)} |"
            )
        out.append("")
    return out


def _render_graph(model: Model, rows: list[GateRow]) -> list[str]:
    out = [
        "## Trust graph",
        "",
        "The protocol, with each edge coloured by the **weakest** evidence any "
        "of its gates rests on. A critical path that is all one colour is a "
        "path defended by one kind of claim — and if that colour is "
        "`agent`, it is defended by the agent's own word.",
        "",
        "```mermaid",
        "flowchart LR",
    ]
    for state, spec in model.states.items():
        # Quoted because every label in states.toml has parentheses in it
        # ("Recon (Steps 0-4)"), which mermaid otherwise reads as syntax.
        label = str(spec.get("label", state)).replace('"', "'")
        shape = '(["%s"])' if spec.get("initial") or spec.get("terminal") else '["%s"]'
        out.append(f"    {state}{shape % label}")
    for row in rows:
        out.append(f"    {row.src} -->|{row.command}| {row.dst}")
    for index, row in enumerate(rows):
        out.append(
            f"    linkStyle {index} stroke:{_EDGE_COLOURS[row.weakest]},stroke-width:2px"
        )
    out.append("```")
    out.append("")
    out.append("| Colour | Class | Edges |")
    out.append("|---|---|---|")
    for name, colour in _EDGE_COLOURS.items():
        # Keyed by the whole edge, not the command: two transitions can share a
        # command name and differ in strength. `resume` does — the one out of
        # `awaiting_clear` demands host evidence, the one out of
        # `awaiting_human` is deliberately ungated — and a legend that collapsed
        # them would hide the route-around L3's boundary check exists to stop.
        edges = sorted(
            f"`{row.command}` ({row.src}→{row.dst})"
            for row in rows
            if row.weakest == name
        )
        if not edges:
            continue
        out.append(f"| `{colour}` | `{name}` | {', '.join(edges)} |")
    out.append("")
    return out


def _render_posture(model: Model, rows: list[GateRow]) -> list[str]:
    """The census, as a document rather than a number someone once quoted."""
    by_event = gate_consumed_events(model)
    counts: dict[str, int] = {}
    for attests in by_event.values():
        counts[attests] = counts.get(attests, 0) + 1
    agent_backed = counts.get("agent", 0)

    out = [
        "## Posture",
        "",
        f"**{agent_backed} of {len(by_event)} gate-consumed events are the "
        "agent's own word.**",
        "",
        "This is not a bug — self-attestation is fine for bookkeeping, and a "
        "protocol whose every step needed host evidence would not be usable. "
        "It is here because it should be a *deliberate, visible* posture "
        "rather than an accident nobody had counted. The defect is a "
        "**mismatch**: a gate whose purpose is to constrain the agent, fed by "
        "evidence the agent controls.",
        "",
        "| Class | Gate-consumed events |",
        "|---|---|",
    ]
    for name in list(_EDGE_COLOURS) + sorted(set(counts) - set(_EDGE_COLOURS)):
        if name not in counts:
            continue
        events = sorted(e for e, a in by_event.items() if a == name)
        out.append(
            f"| `{name}` ({counts[name]}) | {', '.join(f'`{e}`' for e in events)} |"
        )
    out.append("")
    return out


def _hook_fact(model: Model, hook: dict) -> tuple[str, list[str]]:
    """What a runtime hook demands, and the events carrying it."""
    gate = hook.get("gate", {})
    if gate:
        return _gate_fact(model, gate), sorted(gate_event_types(model, gate))
    # A monitor spells its condition `[monitors.trigger]`; a hook spells the
    # same thing `[hooks.check]`.
    check = hook.get("check") or hook.get("trigger") or {}
    kind = check.get("type", "")
    events = sorted(check.get("event_types", []) or [])
    if kind == "event_count_since_last_transition":
        return (
            f"fewer than {check.get('threshold')} "
            f"{', '.join(events) or 'events'} since the last transition",
            events,
        )
    if kind == "output_contains_any":
        return (
            f"the agent's output claims none of {len(check.get('patterns', []))} "
            "completion phrases",
            [],
        )
    return kind or "—", events


def _render_hooks(model: Model) -> list[str]:
    """The gates that fire on a tool call rather than on a transition."""
    out = [
        "## Runtime hooks",
        "",
        "`hooks.toml` gates fire on the harness's own tool-call events, so "
        "they constrain the agent between transitions. The message a blocking "
        "hook prints is part of the contract too: it is the escape the agent "
        "reads at the moment it is stuck, which makes it a *taught command* "
        "and not documentation.",
        "",
        "| Fires on | States | Action | Fact required | Evidence | Attests | Forgeable |",
        "|---|---|---|---|---|---|---|",
    ]
    for hook in model.hooks:
        if hook.get("auto_record"):
            continue
        fact, events = _hook_fact(model, hook)
        excluded = ", ".join(hook.get("states_not", []) or [])
        states = (
            ", ".join(hook.get("states", []) or [])
            or (f"any except {excluded}" if excluded else "any")
        )
        tools = ", ".join(hook.get("tools", []) or [])
        fires = f"`{hook.get('event', '?')}`" + (f" ({tools})" if tools else "")
        evidence = ", ".join(f"`{event}`" for event in events) or "*direct check*"
        attests = sorted({attestation_of(model, event) for event in events})
        forgeable = sorted({_forgeable(model, event) for event in events})
        out.append(
            f"| {fires} | {_cell(states)} | `{hook.get('action', 'record')}` "
            f"| {_cell(fact)} | {_cell(evidence)} "
            f"| {', '.join(f'`{a}`' for a in attests) or '`direct`'} "
            f"| {_cell(', '.join(forgeable)) or 'n/a'} |"
        )
    for monitor in model.monitors:
        fact, events = _hook_fact(model, monitor)
        evidence = ", ".join(f"`{event}`" for event in events) or "*any event*"
        out.append(
            f"| monitor `{monitor.get('name', '?')}` "
            f"| {_cell(', '.join(monitor.get('states', []) or []))} "
            f"| `{monitor.get('action', 'warn')}` | {_cell(fact)} "
            f"| {_cell(evidence)} | — | — |"
        )
    out.append("")
    out.append(
        "Events the engine records off the agent's tool calls, with no command "
        "run and nothing for the agent to remember. Note that the *signal* "
        "being tool-observed does not by itself make the *event* tool-class: "
        "attestation is the strength of the weakest available write path, and "
        "an auto-recorded event that is not `restricted` can still be written "
        "by `sahjhan event`. That is why these declare `agent`."
    )
    out.append("")
    out.append("| Fires on | Records |")
    out.append("|---|---|")
    for hook in model.hooks:
        auto = hook.get("auto_record", {})
        if not auto:
            continue
        tools = ", ".join(hook.get("tools", []) or []) or "*"
        out.append(
            f"| `{hook.get('event', '?')}` ({tools}) | `{auto.get('event_type')}` |"
        )
    out.append("")
    return out


def _render_writers(model: Model) -> list[str]:
    """The bottom row of the layering table: is the writer actually wired up?

    A hook that writes a restricted event is enforcement only while it is
    registered with the harness *and* hash-pinned in ``trusted-callers.toml``.
    Editing one changes its SHA-256 and silently invalidates the pin — the
    daemon then refuses it, the hook's write is swallowed, and every gate
    downstream fails open while everything still exits 0. H4 checks this; this
    table is what it checks, in a form a person can scan.
    """
    out = [
        "## Writers",
        "",
        "Every Python writer in the tree, with the registration and pin that "
        "decide whether it can actually record anything. A writer that is not "
        "registered never runs; one whose pin is stale is refused by the "
        "daemon, and because the refusal is swallowed the gates downstream "
        "fail *open* while every hook still exits 0. **Hash-pinned** names the "
        "entrypoint whose process carries the identity — the daemon "
        "authenticates the process, so a module that only ever runs inside "
        "another hook is pinned through it.",
        "",
        "| Writer | Registered for | Hash-pinned | Writes |",
        "|---|---|---|---|",
    ]
    writes: dict[str, set[str]] = {}
    for event, writers in model.writers.items():
        for writer in writers:
            if writer.producer_id.startswith("hook:"):
                script = writer.producer_id.split(":", 1)[1]
                writes.setdefault(script, set()).add(event)
    for script in sorted(writes):
        name = script.split("/")[-1]
        registered = sorted(set(model.hook_entrypoints.get(name, [])))
        reaching = model.reaching_entrypoints.get(name, {name})
        pinned = sorted(reaching & model.trusted_callers)
        restricted = any(
            model.events.get(event, {}).get("restricted") for event in writes[script]
        )
        pinned_cell = ", ".join(f"`{entry}`" for entry in pinned)
        pin = pinned_cell or ("**no**" if restricted else "—")
        out.append(
            f"| `{script}` | {', '.join(f'`{e}`' for e in registered) or '**not registered**'} "
            f"| {pin} | {', '.join(f'`{e}`' for e in sorted(writes[script]))} |"
        )
    out.append("")
    return out


def render(model: Model) -> str:
    rows = gate_rows(model)
    out = [
        "# Enforcement contract",
        "",
        f"<!-- GENERATED by `{GENERATED_BY}`. Do not edit by hand: "
        "`scripts/lint-enforcement.sh` fails when this file and "
        "`enforcement/*.toml` disagree. -->",
        "",
        "A holtz gate is only as strong as the chain of facts behind it, and "
        "that chain lives in five places connected by nothing but convention: "
        "what the gate requires (`transitions.toml`), what the event's fields "
        "must look like (`events.toml`), what the event *means* (prose), who "
        "may write it and from what signal (Python hooks and skill markdown), "
        "and whether that writer is registered and hash-pinned (`hooks.json`, "
        "`trusted-callers.toml`).",
        "",
        "The gate can be read. The evidence behind it could not — which is "
        "where [#73](https://github.com/jbrjake/holtz/issues/73) "
        "(gate unsatisfiable), "
        "[#77](https://github.com/jbrjake/holtz/issues/77) (gate deadlocked) "
        "and [#79](https://github.com/jbrjake/holtz/issues/79) (gate satisfied "
        "without cause) all lived. This document is that middle row, written "
        "down. See [#82](https://github.com/jbrjake/holtz/issues/82).",
        "",
        "## Attestation classes",
        "",
        "Every event gets exactly one, declared in `events.toml` and ordered "
        "by `[attestation] levels` in `protocol.toml`.",
        "",
        "| Class | Written from |",
        "|---|---|",
    ]
    for name in model.attestation_levels:
        out.append(f"| `{name}` | {_CLASS_MEANING.get(name, '—')} |")
    out.append(f"| `{DIRECT}` | {_CLASS_MEANING[DIRECT]} |")
    out.extend(
        [
            "",
            "`restricted = true` means the daemon accepts the event only from "
            "a hash-pinned caller. It cannot express *human*: a person at the "
            "terminal runs the bare CLI, so `restricted` would lock them out "
            "and the hooks in. The human channel is the agent's path being "
            "denied in `_sahjhan_bootstrap.py` while the user runs a "
            "`!`-prefixed command, which Claude Code executes without a tool "
            "call.",
            "",
        ]
    )
    out.extend(_render_posture(model, rows))
    out.extend(_render_graph(model, rows))
    out.extend(_render_gates(model, rows))
    out.extend(_render_hooks(model))
    out.extend(_render_writers(model))
    return "\n".join(out).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="regenerate the doc")
    parser.add_argument("--check", action="store_true", help="exit 1 if stale")
    parser.add_argument("--config-dir", default=None)
    args = parser.parse_args()

    tree = Tree(config_dir=Path(args.config_dir).resolve()) if args.config_dir else Tree()
    body = render(build_model(tree))

    if args.write:
        CONTRACT_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONTRACT_PATH.write_text(body, encoding="utf-8")
        print(f"wrote {CONTRACT_PATH.relative_to(REPO_ROOT)}")
        return 0

    if args.check:
        current = (
            CONTRACT_PATH.read_text(encoding="utf-8")
            if CONTRACT_PATH.exists()
            else ""
        )
        if current == body:
            print("docs/ENFORCEMENT-CONTRACT.md is current")
            return 0
        print(
            "docs/ENFORCEMENT-CONTRACT.md is stale — the enforcement config "
            "changed and the contract did not.\n"
            f"run: {GENERATED_BY}",
            file=sys.stderr,
        )
        return 1

    print(body, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
