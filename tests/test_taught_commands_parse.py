"""Every `sahjhan` command a skill file teaches must parse against the engine.

`contract_gate.py` and `test_contract_commands.py` prove the *hook* allows a
command string. Nothing proved the *engine* accepts it. The two facts are
independent, and the gap shipped: `protocol.toml` declares 17 two-word aliases,
sahjhan <= 0.21.0 matched only the first positional word against alias keys, and
`sahjhan defer low BH-001` died with `unrecognized subcommand 'defer'`. Every
deferral path an agent has was unrunnable while CI was green, because every test
drives the canonical `transition defer_low` instead of the taught spelling.

These tests run the exact string each doc contains, through a shell, against a
real ledger. The assertion is narrow on purpose: no CLI-level parse error. A
gate refusal, a wrong protocol state, or a missing schema field all mean the
command *reached* the protocol, which is the fact under test.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

# Deliberately not `slow`: the whole file runs in ~1.5s, and the pre-commit
# fast subset is where a broken taught command has to surface. Marking it slow
# would put it outside the local gate and reproduce the shape it exists to
# catch — a green gate over a step the agent cannot run.
pytestmark = [pytest.mark.contract]

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = REPO_ROOT / "enforcement"
BIN_DIR = REPO_ROOT / "bin"
sys.path.insert(0, str(CONFIG_DIR / "hooks"))

DOC_ROOTS = ("skills", "agents")

_FENCE = re.compile(r"^\s*```")
_INLINE = re.compile(r"`([^`\n]+)`")

# Bare subcommand names that appear inside prose — a warning about the noise a
# skipped `ledger create` produces, a prohibition on `sahjhan reset`, the
# bootstrap note's `sahjhan …`. These are references to a command, not
# instructions to run one. `test_prose_mentions_are_all_still_present` fails if
# one stops being extracted, so this set cannot quietly absorb a real command.
_PROSE_MENTIONS = frozenset({
    "sahjhan …",
    "sahjhan render",
    "sahjhan reset",
    "sahjhan transition",
    "sahjhan event ...",
    "sahjhan event finding",
})

# Placeholders the docs use for values the agent fills in. Order matters:
# the specific spellings resolve before the catch-all brace/angle forms.
_PLACEHOLDERS = (
    (re.compile(r"\s+#.*$"), ""),                       # trailing comment
    (re.compile(r"B[HJ]-NNN"), "BH-001"),
    (re.compile(r"\{item_id\}"), "BH-001"),
    (re.compile(r"\{project\}|<project>"), "holtz"),
    (re.compile(r"\{N\}|\bN\b"), "1"),
    (re.compile(r"\{lens\}|\{type\}|<name>"), "component"),
    (re.compile(r"\{[^}]*\}"), "x"),
    (re.compile(r"<[^>]*>"), "x"),
    (re.compile(r"\.\.\."), "x"),
)

# clap's own vocabulary for "I could not parse this". Anything else the engine
# says means the command was understood and the protocol answered it.
_PARSE_ERRORS = (
    "unrecognized subcommand",
    "unexpected argument",
    "required arguments were not provided",
    "invalid value",
    "Usage:",
)


def _docs() -> list[Path]:
    return sorted(p for d in DOC_ROOTS for p in (REPO_ROOT / d).rglob("*.md"))


def _commands(text: str) -> list[str]:
    """Every `sahjhan ...` invocation in fenced blocks and inline code spans."""
    found: list[str] = []
    in_fence = False
    pending = ""
    for line in text.splitlines():
        if _FENCE.match(line):
            in_fence = not in_fence
            pending = ""
            continue
        if in_fence:
            stripped = line.strip()
            if pending:
                pending = pending[:-1].strip() + " " + stripped
            elif stripped.startswith("sahjhan "):
                pending = stripped
            else:
                continue
            if pending.endswith("\\"):        # continuation
                continue
            found.append(pending)
            pending = ""
        else:
            found.extend(
                span.strip() for span in _INLINE.findall(line)
                if span.strip().startswith("sahjhan ")
            )
    return found


def _taught() -> dict[str, str]:
    """Every distinct taught command, mapped to the doc that teaches it."""
    seen: dict[str, str] = {}
    for doc in _docs():
        for cmd in _commands(doc.read_text()):
            seen.setdefault(cmd, doc.relative_to(REPO_ROOT).as_posix())
    return seen


def _runnable() -> dict[str, str]:
    return {c: d for c, d in _taught().items() if c not in _PROSE_MENTIONS}


def _leading_word(command: str) -> str | None:
    """The first positional word after `sahjhan`, past any global flag.

    `--config-dir "$CLAUDE_PLUGIN_ROOT/enforcement"` puts a path where a naive
    split sees a subcommand, so flags and the values they consume are dropped
    before the first positional is taken.
    """
    tokens = command.split()[1:]                     # drop "sahjhan"
    takes_a_value = {"--config-dir", "--field", "--from", "--snapshot", "--mode"}
    while tokens:
        token = tokens.pop(0)
        if token.startswith("-"):
            if token in takes_a_value and tokens:
                tokens.pop(0)
            continue
        return token
    return None


def _fill(command: str) -> str:
    for pattern, replacement in _PLACEHOLDERS:
        command = pattern.sub(replacement, command)
    return command.strip()


@pytest.fixture(scope="module")
def ledger(tmp_path_factory):
    """A real, initialized ledger with an active run, and the env the docs assume."""
    from _resolve import ensure_sahjhan
    if not ensure_sahjhan():
        pytest.skip("sahjhan binary not available")

    root = tmp_path_factory.mktemp("taught")
    env = {
        "PATH": f"{BIN_DIR}{os.pathsep}{os.environ.get('PATH', '')}",
        "CLAUDE_PLUGIN_ROOT": str(REPO_ROOT),
        "HOME": str(root),
    }
    for args in (["init"], ["ledger", "create", "--from", "run", "1", "--activate"]):
        subprocess.run(
            [str(BIN_DIR / "sahjhan"), "--config-dir", str(CONFIG_DIR), *args],
            cwd=root, env=env, capture_output=True, text=True, timeout=30, check=True,
        )
    return root, env


def _engine_subcommands(ledger) -> set[str]:
    """The subcommand names in the binary's own `--help`, not a restated list."""
    root, env = ledger
    help_text = subprocess.run(
        [str(BIN_DIR / "sahjhan"), "--help"],
        cwd=root, env=env, capture_output=True, text=True, timeout=30,
    ).stdout
    body = help_text.split("Commands:", 1)[-1].split("Options:", 1)[0]
    return {
        line.split()[0] for line in body.splitlines()
        if line.startswith("  ") and line.strip() and not line.strip().startswith("-")
    }


def _reaches_the_protocol(ledger, command: str) -> tuple[bool, str]:
    root, env = ledger
    result = subprocess.run(
        _fill(command), shell=True, cwd=root, env=env,
        capture_output=True, text=True, timeout=30,
    )
    output = result.stdout + result.stderr
    hit = next((e for e in _PARSE_ERRORS if e in output), None)
    return hit is None, output


@pytest.mark.parametrize("command", sorted(_runnable()), ids=lambda c: c[:60])
def test_a_taught_command_reaches_the_protocol(ledger, command):
    """The engine understands the command as spelled in the doc.

    A protocol error ("no transition X from state Y", "missing field") is a
    pass: the command was parsed and answered. Only clap's parse vocabulary
    fails, because that means the agent's copy-paste dies before the ledger
    ever sees it.
    """
    ok, output = _reaches_the_protocol(ledger, command)
    assert ok, (
        f"{_runnable()[command]} teaches a command the engine cannot parse:\n"
        f"  taught:   {command}\n"
        f"  ran:      {_fill(command)}\n"
        f"  engine:   {output.strip()}"
    )


def test_every_taught_alias_is_declared(ledger):
    """A taught spelling the engine has no subcommand for must be an alias.

    Parse-level acceptance is not enough on its own: `sahjhan defer low` fails
    open the day `[aliases]` loses the key *and* `defer` becomes a real
    subcommand. The subcommand list is read out of the binary's own `--help`
    rather than restated here, so a list that drifts cannot quietly excuse a
    taught word.
    """
    import tomllib
    with open(CONFIG_DIR / "protocol.toml", "rb") as fh:
        aliases = tomllib.load(fh).get("aliases", {})
    assert aliases, "protocol.toml declares no [aliases]"

    subcommands = _engine_subcommands(ledger)
    assert "defer" not in subcommands, (
        "`defer` is now a real sahjhan subcommand — this test's premise was "
        "that holtz's deferral spellings exist only as aliases"
    )

    for command, doc in _runnable().items():
        leading = _leading_word(command)
        if leading is None or leading in subcommands:
            continue
        assert any(key.split()[0] == leading for key in aliases), (
            f"{doc} teaches `{command}`, whose leading word {leading!r} is "
            f"neither an engine subcommand nor the first word of an alias in "
            f"{sorted(aliases)}"
        )


def test_prose_mentions_are_all_still_present():
    """Every excluded string is still a real mention somewhere in the docs.

    Guards the exclusion list against rot: a stale entry here would silently
    shrink coverage the day a doc turns that mention into a real command.
    """
    taught = _taught()
    missing = sorted(_PROSE_MENTIONS - set(taught))
    assert not missing, (
        f"_PROSE_MENTIONS lists strings no doc contains any more: {missing}. "
        f"Remove them, or the exclusion is hiding coverage it no longer buys."
    )


def test_the_extractor_finds_the_deferral_commands():
    """Non-vacuity: the four spellings that were dead until sahjhan 0.22.0.

    If the extractor regresses to finding nothing, every parametrized case
    above vanishes and the suite still passes. This pins the specific commands
    that motivated the file.
    """
    taught = set(_runnable())
    for spelling in ("defer cant-reproduce", "defer low", "defer medium"):
        assert any(spelling in c for c in taught), (
            f"no taught command contains {spelling!r} — the extractor stopped "
            f"seeing the deferral commands that were unrunnable until 0.22.0"
        )
