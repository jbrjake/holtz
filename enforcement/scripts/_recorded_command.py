#!/usr/bin/env python3
"""What the four recorded commands agree on, in one place.

`verify_suite.py`, `pattern_round.py`, `stale_sweep.py` and
`hardening_batch.py` each print an evidence line that a PostToolUse courier
turns into a ledger entry. Each carries a recognizer — `record_scope_of`,
`siblings_of`, `verdicts_of`, `module_of_command` — that decides whether a Bash
line *is* that command, and each returns `None` when it is not.

Items 34 and 28 are four instances of one thing that `None` cannot say. It
collapses two cases a run needs told apart:

* the line is `git status`, and there is nothing to report;
* the line names this very script and asks it to record, in a shape the
  recognizer refuses — so the agent believes it recorded something, the courier
  exits 0, and nothing was written. The gate that needed the evidence blocks
  later, with no connection back to this moment.

The second is the whole defect: **silence is the bug**, not the refusal. The
refusals are all deliberate — `--cwd` would attach another project's board to
this ledger, a chained segment would let arbitrary work ride the one Bash line
whose success becomes a ledger entry, and a wrapper in front of the interpreter
is a shape the recognizer cannot parse at all. Every one of them should say so.

Two halves live here so the four cannot drift apart on either:

* `looks_like_a_record` — the discriminator a courier uses to decide between
  silence and a warning;
* `refuse_cwd_with_record` — the CLI-side half, so a recorded command carrying
  `--cwd` fails at the parser instead of exiting 0 and recording nothing. A
  script's own argument parser refusing exactly what its courier refuses is
  what makes the second case above rare rather than routine.
"""
from __future__ import annotations

import argparse
import shlex

#: How a recorded command may be launched. Deliberately not widened to
#: `poetry run` / `uv run` / `conda run` / a venv shim: those put a wrapper in
#: `tokens[0]` and shift the script into `tokens[2]`, and the space of wrappers
#: is not enumerable. The scripts do not need the project's interpreter anyway
#: — `verify_suite.py` runs the suite under an in-tree venv or `$HOLTZ_PYTHON`,
#: which is exactly the seam for a project whose tests only run under one. So the taught
#: spelling is the supported one, and `looks_like_a_record` is what makes any
#: other spelling loud instead of silent.
INTERPRETERS = frozenset({"python", "python3", "py"})

CWD_HELP = "target project directory (diagnostic; not accepted with --record)"


def _tokens(command: str) -> list[str]:
    """The line's words, falling back to a naive split on an unbalanced quote.

    A courier must be able to decide "is this mine" on text it cannot parse —
    an unclosed quote is one of the shapes that reaches the recognizer's `None`
    path, so raising here would restore the silence this module exists to end.
    """
    try:
        return shlex.split(command)
    except ValueError:
        return command.split()


def looks_like_a_record(command: str, script_tail: str) -> bool:
    """Does this Bash line name ``script_tail`` and ask it to record?

    The question a courier asks *after* its recognizer has already said `None`,
    to choose between exiting quietly and warning. Deliberately looser than the
    recognizer — the shapes worth warning about are precisely the ones the
    recognizer cannot parse.

    ``--record`` is required as well as the path so that reading, editing or
    staging one of these scripts is not mistaken for running it: `git add
    enforcement/scripts/stale_sweep.py` names the script and asks it for
    nothing.
    """
    tokens = _tokens(command)
    return "--record" in tokens and any(t.endswith(script_tail) for t in tokens)


def not_the_taught_form(event_label: str, taught: str) -> str:
    """The warning for a line that asked to record in an unrecognised shape."""
    return (
        f"{event_label} NOT recorded: this line names the script and passes "
        "--record, but it is not the form the courier recognises, so nothing "
        f"was written. Run it exactly as:\n    {taught}\n"
        "— alone on its own Bash line, launched with python3, and without "
        "--cwd. The suite already runs under an in-tree venv; for an "
        "interpreter outside the tree, set $HOLTZ_PYTHON rather than wrapping "
        "this command."
    )


def refuse_cwd_with_record(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    """Fail a recorded command that carries ``--cwd``, instead of ignoring it.

    Every recognizer refuses `--cwd`: the courier derives against the *event's*
    directory, so a recorded command pointed elsewhere would attach another
    project's board to this ledger. Accepting it at the CLI is what made that
    refusal silent — the script checked the board, printed its marker and
    exited 0, and the courier wrote nothing.

    Presence is what is refused, not the value, because that is what the
    recognizers refuse: `--cwd .` is as unparseable to them as `--cwd /other`.
    So `--cwd` defaults to `None` in each parser and means "not given".
    """
    if getattr(args, "record", False) and args.cwd is not None:
        parser.error(
            "--cwd cannot be combined with --record: the courier derives "
            "against the directory the command ran in and refuses a recorded "
            "command carrying this flag, so it would exit 0 and record "
            "nothing. Run it from the project directory instead."
        )
