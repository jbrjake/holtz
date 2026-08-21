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
_WRAPPER_RE = re.compile(
    r"""\b(?:eval|(?:ba|z|k|d?a)?sh\s+-c)\s+("(?:[^"]*)"|'(?:[^']*)')""",
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
    return {m.group(1): _unquote(m.group(2)) for m in _ASSIGN_RE.finditer(cmd)}


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
