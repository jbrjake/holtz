"""F3 — do the `sahjhan event` commands we *teach* carry the fields the engine
requires?

`contract_gate.py` asks one question about a taught command: does the hook allow
this string. It has never asked whether the engine accepts its fields, and
`sahjhan event` does not inherit run context — only `emits` do. So a command
that reads perfectly, passes the hook, and is printed as the escape from a block
can still exit 4 on the first use of every run (item 31 / W03).

Two sources are in scope, and the second is the one nothing covers today:

* **skill files** — `skills/**/*.md`, in fenced blocks *and* in inline
  backticks. `contract_gate.extract_sahjhan_commands` reads fenced blocks only,
  which is how six inline commands kept the omission.
* **`enforcement/hooks.toml` block messages** — not a skill file, so out of the
  gate's scope entirely, yet it is the string a blocked agent actually copies.

This module is the shared expression of the check. It is imported by the tests
that report per-command, and (from W03) by the contract gate that fails the
build. One named fact, two consumers.
"""
from __future__ import annotations

import os
import re
import tomllib
from dataclasses import dataclass

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENFORCEMENT_DIR = os.path.join(REPO_ROOT, "enforcement")
SKILLS_DIR = os.path.join(REPO_ROOT, "skills")
EVENTS_TOML = os.path.join(ENFORCEMENT_DIR, "events.toml")
HOOKS_TOML = os.path.join(ENFORCEMENT_DIR, "hooks.toml")

#: `sahjhan … event <type>` — the verb and its subcommand, wherever they sit in
#: the line. Tolerates `--config-dir "$X"` and a `nohup`/`&&` prefix, because
#: the taught forms carry both.
_EVENT_RE = re.compile(r"\bsahjhan\b[^\n]*?\bevent\s+([a-z_][a-z0-9_]*)")
_FIELD_RE = re.compile(r"--field\s+([A-Za-z_][A-Za-z0-9_]*)=")

#: A placeholder the docs use where a real value goes. Field *names* are what
#: this module checks, so a placeholder value is not a defect.
_PLACEHOLDER = re.compile(r"^(\.\.\.|<.*>|\{\{.*\}\}|N|BH-NNN)$")


@dataclass(frozen=True)
class TaughtCommand:
    """One `sahjhan event` invocation we tell an agent (or print at it) to run."""

    source: str          # repo-relative path
    line: int            # 1-indexed
    origin: str          # "fenced" | "inline" | "hooks.toml message"
    event_type: str
    fields: frozenset[str]
    text: str

    @property
    def where(self) -> str:
        return f"{self.source}:{self.line}"


def load_required_fields(events_toml: str = EVENTS_TOML) -> dict[str, set[str]]:
    """Every event type's required field names, read from `events.toml`.

    A field is required unless it says `optional = true`. Read from the config
    rather than restated here: a test that carries its own copy of the schema
    stops being a check on the schema.
    """
    with open(events_toml, "rb") as fh:
        model = tomllib.load(fh)
    required: dict[str, set[str]] = {}
    for name, stanza in (model.get("events") or {}).items():
        required[name] = {
            field["name"]
            for field in (stanza.get("fields") or [])
            if not field.get("optional", False)
        }
    return required


def _fields_of(text: str) -> frozenset[str]:
    return frozenset(_FIELD_RE.findall(text))


def _commands_in(text: str, *, source: str, line: int, origin: str) -> list[TaughtCommand]:
    """Every `sahjhan event <type> --field …` invocation in one span of text.

    A form carrying **no** `--field` at all is a reference to the command, not
    a runnable form — `"record findings via \\`sahjhan event finding\\`"` names
    the tool the way prose names a tool. Scoring those against the schema would
    report thirteen missing fields on a sentence, which is noise a gate cannot
    carry. The scope is the plan's: commands of the shape
    `sahjhan event <type> --field …`.
    """
    match = _EVENT_RE.search(text)
    if not match:
        return []
    fields = _fields_of(text)
    if not fields:
        return []
    return [TaughtCommand(
        source=source, line=line, origin=origin,
        event_type=match.group(1), fields=fields, text=text.strip(),
    )]


def _inline_spans(line: str) -> list[str]:
    """The contents of every single-backtick span on a line.

    Triple-backtick fences are handled by the caller's fence tracking, so a
    fence marker never reaches here as a span.
    """
    return re.findall(r"`([^`\n]+)`", line)


def commands_in_markdown(md_path: str) -> list[TaughtCommand]:
    """Taught commands in one markdown file — fenced blocks and inline spans.

    A fenced command may be split across continuation lines (`\\`), so fenced
    lines are joined before matching; inline spans never are.
    """
    with open(md_path, encoding="utf-8") as fh:
        lines = fh.readlines()

    source = os.path.relpath(md_path, REPO_ROOT)
    found: list[TaughtCommand] = []
    in_fence = False
    buffer: list[str] = []
    buffer_line = 0

    def flush() -> None:
        nonlocal buffer, buffer_line
        if buffer:
            found.extend(_commands_in(
                " ".join(buffer), source=source, line=buffer_line, origin="fenced",
            ))
        buffer = []

    for i, raw in enumerate(lines, 1):
        stripped = raw.strip()
        if stripped.startswith("```"):
            flush()
            in_fence = not in_fence
            continue
        if in_fence:
            if stripped.startswith("#") or not stripped:
                flush()
                continue
            if not buffer:
                buffer_line = i
            buffer.append(stripped.rstrip("\\").strip())
            if not raw.rstrip("\n").endswith("\\"):
                flush()
            continue
        for span in _inline_spans(raw):
            found.extend(_commands_in(span, source=source, line=i, origin="inline"))
    flush()
    return found


def commands_in_hook_messages(hooks_toml: str = HOOKS_TOML) -> list[TaughtCommand]:
    """Taught commands inside `hooks.toml` block messages.

    The line number is resolved by searching the raw file for the message text,
    so a failure points at the stanza a human has to edit rather than at an
    index into a parsed structure.
    """
    with open(hooks_toml, "rb") as fh:
        model = tomllib.load(fh)
    with open(hooks_toml, encoding="utf-8") as fh:
        raw_lines = fh.readlines()

    source = os.path.relpath(hooks_toml, REPO_ROOT)
    found: list[TaughtCommand] = []
    for stanza in model.get("hooks") or []:
        message = stanza.get("message")
        if not isinstance(message, str):
            continue
        needle = message[:40]
        line = next(
            (i for i, raw in enumerate(raw_lines, 1) if needle in raw), 0
        )
        found.extend(_commands_in(
            message, source=source, line=line, origin="hooks.toml message",
        ))
    return found


def all_taught_commands() -> list[TaughtCommand]:
    """Every taught `sahjhan event` command in the tree, both sources."""
    found: list[TaughtCommand] = []
    for root, _dirs, files in os.walk(SKILLS_DIR):
        for name in sorted(files):
            if name.endswith(".md"):
                found.extend(commands_in_markdown(os.path.join(root, name)))
    found.extend(commands_in_hook_messages())
    return found


def missing_fields(
    command: TaughtCommand,
    required: dict[str, set[str]] | None = None,
) -> set[str]:
    """Required fields `events.toml` demands that the taught form omits.

    An unknown event type returns the empty set rather than raising: this check
    exists to catch omissions, and a typo'd event type is `contract_gate`'s
    business, reported separately by :func:`unknown_event_types`.
    """
    required = load_required_fields() if required is None else required
    return required.get(command.event_type, set()) - set(command.fields)


def unknown_event_types(
    commands: list[TaughtCommand],
    required: dict[str, set[str]] | None = None,
) -> list[TaughtCommand]:
    required = load_required_fields() if required is None else required
    return [c for c in commands if c.event_type not in required]


def report(commands: list[TaughtCommand] | None = None) -> tuple[int, list[str]]:
    """Per-command result. Returns (failure_count, lines) — lines are printable."""
    commands = all_taught_commands() if commands is None else commands
    required = load_required_fields()
    lines: list[str] = []
    failures = 0
    for command in sorted(commands, key=lambda c: (c.source, c.line)):
        gap = missing_fields(command, required)
        if command.event_type not in required:
            failures += 1
            lines.append(f"  UNKNOWN EVENT {command.where} [{command.origin}]: "
                         f"{command.event_type}")
        elif gap:
            failures += 1
            lines.append(f"  MISSING FIELDS {command.where} [{command.origin}]: "
                         f"event {command.event_type} needs "
                         f"{', '.join(sorted(gap))}")
        else:
            lines.append(f"  ok {command.where} [{command.origin}]: "
                         f"event {command.event_type}")
    return failures, lines


def main() -> int:
    failures, lines = report()
    for line in lines:
        print(line)
    total = len(lines)
    print(f"\nTaught-command field check: {total} commands, {failures} failing")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
