#!/usr/bin/env python3
"""Rewrite indirect command spellings into the direct ones they run.

The enforcement hooks decide what a Bash line does by looking at its tokens.
That works until the line puts the executable behind a variable or a shell
wrapper, at which point the token the hooks look for is not on the line:

    SAH="$CLAUDE_PLUGIN_ROOT/bin/sahjhan"; "$SAH" event quiz_exhausted_resolved
    eval "$CLAUDE_PLUGIN_ROOT/bin/sahjhan daemon stop"
    bash -c "sahjhan status"

Every one of those runs sahjhan. Left unresolved, the stall counter reads a
re-sync as another silent command, and — the reason this module exists — the
blocked-subcommand guard reads a denied invocation as an unrelated one, so
the human-only attestation channel has a second door.

Deliberately narrow. Only variables **assigned on the same line** are
substituted: this resolves the shape an agent actually writes when it is
unsure the binary is on PATH, without pretending to know the surrounding
shell's environment. A variable from elsewhere stays unexpanded, and a
command the hooks already parse is returned byte-identical.

Owned in one place on purpose. Two hooks answering "is this sahjhan?" from
two parsers is PAT-001 (dual-parser-divergence), and this is precisely the
question where a disagreement between them is a hole rather than a nuisance.

The same ownership covers *segmentation* — deciding where one command ends
and the next begins. Eight sites used to answer that themselves, in two
different spellings of one regex, and every one of them omitted a single
``&``. ``A & B`` is two commands, so a guard reading the first token of the
whole line inspected ``A`` and let ``B`` through unread.
"""
from __future__ import annotations

import re

# ``VAR=value`` / ``export VAR=value`` at the start of a line or a segment.
_ASSIGN_RE = re.compile(
    r"""(?:^|(?<=[;&|\n])|(?<=\s))(?:export\s+)?([A-Za-z_]\w*)="""
    r"""("(?:[^"]*)"|'(?:[^']*)'|[^\s;&|]*)""",
)

# ``eval "…"`` / ``eval '…'`` / ``bash -c "…"``. The payload is the command
# that actually runs, so the wrapper is replaced by its own argument.
#
# The lookbehind rejects a preceding ``-``, so an interpreter *flag* that
# ends in the same letters is not read as the shell builtin. ``\b`` matched
# inside ``node --eval "…"``, which rewrote it to ``node --require(…)`` —
# the flag eaten, the payload unquoted. That is not academic: the
# protected-path guard identifies an inline interpreter write by finding
# ``--eval`` on the line, so the rewrite turned a block into an allow.
# A word character is rejected for the same reason ``\b`` did.
_WRAPPER_RE = re.compile(
    r"""(?<![-\w])(?:eval|(?:ba|z|k|d?a)?sh\s+-c)\s+("(?:[^"]*)"|'(?:[^']*)')""",
)

_VAR_RE = re.compile(r"\$\{(\w+)\}|\$(\w+)")

# Two passes resolve a variable defined in terms of another variable
# (``ROOT=…; SAH=$ROOT/bin/sahjhan``). More passes buy nothing and a cycle
# must not spin, so the count is fixed rather than run to a fixpoint.
_MAX_PASSES = 3


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
        return value[1:-1]
    return value


def _collect_assignments(cmd: str) -> dict[str, str]:
    """``VAR=value`` pairs assigned on this line.

    A ``k=v`` whose preceding token is an option — ``--field k=v`` — is that
    option's operand, handed to the program as data, and assigns nothing.
    Collecting it made ``$k`` elsewhere on the line resolve to ``v``, so the
    guards reasoned about a command string nobody typed.
    """
    found = {}
    for m in _ASSIGN_RE.finditer(cmd):
        before = cmd[: m.start()].split()
        if before and before[-1].startswith("-"):
            continue
        found[m.group(1)] = _unquote(m.group(2))
    return found


def _substitute(cmd: str, values: dict[str, str]) -> str:
    """Replace ``$VAR`` / ``${VAR}`` where VAR was assigned on this line."""
    def repl(match: re.Match[str]) -> str:
        name = match.group(1) or match.group(2)
        return values.get(name, match.group(0))
    return _VAR_RE.sub(repl, cmd)


def _unwrap(cmd: str) -> str:
    """Replace ``eval "X"`` / ``sh -c "X"`` with ``X``."""
    return _WRAPPER_RE.sub(lambda m: _unquote(m.group(1)), cmd)


def resolve_indirection(cmd: str) -> str:
    """Return ``cmd`` with same-line variables and shell wrappers resolved.

    Returns the input unchanged when there is nothing to resolve, so callers
    can apply it unconditionally.
    """
    if "$" not in cmd and "eval" not in cmd and "-c" not in cmd:
        return cmd
    resolved = cmd
    for _ in range(_MAX_PASSES):
        assignments = _collect_assignments(resolved)
        nxt = _unwrap(_substitute(resolved, assignments) if assignments else resolved)
        if nxt == resolved:
            break
        resolved = nxt
    return resolved


# Operators that end one command and begin the next. ``&&`` and ``||`` are
# listed before the single-character class so the two-character operators
# still win the alternation. ``\n`` is here because Claude Code sends
# newline-separated commands in a single Bash call.
_SEGMENT_RE = re.compile(r"\s*(?:&&|\|\||[;&|\n])\s*")

# The ``&`` characters that belong to a *redirection* rather than separating
# two commands: fd duplication and closing (``2>&1``, ``>&2``, ``2>&-``) on
# one side, bash's combined-stream redirect (``&>file``, ``&>>file``) on the
# other. Both are one token to the shell, and both appear in commands the
# skill files teach, so splitting inside them would turn ``sahjhan status
# 2>&1`` into ``sahjhan status 2>`` and ``1``.
#
# They are *masked* rather than stripped: a caller that scans a segment for
# redirect targets (``_check_bash_write``) must still see the bytes that were
# written. The mask is NUL, which cannot occur in a JSON tool-input string.
_REDIRECT_AMP_RE = re.compile(r"\d*>>?&|&>>?")
_AMP_MASK = "\x00"


def _mask_redirect_amps(cmd: str) -> str:
    return _REDIRECT_AMP_RE.sub(lambda m: m.group(0).replace("&", _AMP_MASK), cmd)


def shell_segments(cmd: str, *, resolve: bool = True) -> list[str]:
    """Split ``cmd`` into the commands the shell would run, in order.

    The one place segmentation is decided. Resolves indirection first, so
    every caller keys on the command that runs rather than the spelling it
    was written in, then splits on ``&&``, ``||``, ``;``, ``|``, ``&`` and
    newline. Empty segments are dropped, which is what makes a *trailing*
    ``&`` — backgrounding, one command, not two — segment as one command.

    Operators inside quotes are split on, as they always have been here:
    ``git commit -m "a; b"`` yields two segments. That is the fail-closed
    direction for the guards (more segments get read, not fewer) and adding
    ``&`` does not change the class of the imprecision.
    """
    if resolve:
        cmd = resolve_indirection(cmd)
    parts = _SEGMENT_RE.split(_mask_redirect_amps(cmd))
    return [s for s in (p.replace(_AMP_MASK, "&").strip() for p in parts) if s]
