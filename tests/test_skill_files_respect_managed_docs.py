"""No skill file may instruct a write the enforcement chain blocks.

`docs/holtz/STATUS.md` and `docs/holtz/PUNCHLIST.md` are rendered from the
ledger, and every write vector to them is denied — ``Edit``/``Write`` by
``pre_tool_hook.py``'s managed-path guard, and shell redirect / ``sed -i`` /
``tee`` / ``cp`` / interpreter ``-c`` by ``_check_bash_write`` in the bootstrap
hook. Yet eleven lines across five skill files said to update them, six of
them in ``step-10-fix-loop.md`` alone, and one two lines above a paragraph
explaining that the transition already records the fact.

A mandated step that cannot be performed is worse than a missing one. In the
run this came from it was followed zero times in 23 sampled fix cycles, and
what the agent saw for trying was ``BLOCKED: Bash command modifies protected
path 'docs/holtz/STATUS.md'`` — an alarm, on the protocol's own instruction.

The managed set is read from ``MANAGED_DOCS`` rather than restated here, so
adding a render target extends this check with it.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOKS = REPO_ROOT / "enforcement" / "hooks"
sys.path.insert(0, str(HOOKS))

from _sahjhan_bootstrap import MANAGED_DOCS  # noqa: E402

# Verbs that mean "you write this file". Matched only when one leads the
# managed filename inside a single clause, so "Re-read docs/holtz/PUNCHLIST.md"
# and "PUNCHLIST.md re-renders from those events" are not swept up with it.
_WRITE_VERB = r"(?:updat\w+|writ\w+|edit\w*|append\w*|modif\w+|overwrit\w+|record\w*)"

# `|` ends a clause as firmly as `.` does: SKILL.md's Rationalization Red Flags
# are two-column tables whose left cell quotes the very instinct the right cell
# refutes, and reading across the cell boundary turns a warning into a command.
_CLAUSE = r"[^.|\n]"

# `docs/holtz/justine/` is the auditor's own tree. Nothing renders those files
# and no guard blocks them — justine-skill.md declares the whole directory
# hers, so a bare `STATUS.md` in her documents means her copy. An explicit
# `docs/holtz/<managed>` still counts against her, which is the case that
# would actually be a problem.
_JUSTINE_DOCS = {"justine-skill.md", "justine.md"}

# `LIVING-PUNCHLIST.md` and `step3-recon-summary.md` end with a managed
# basename but are agent-owned files, and `docs/holtz/justine/SUMMARY.md` ends
# with one while living in the unmanaged tree. Require a boundary that a
# hyphen fails and that Justine's directory fails.
_LEFT_BOUNDARY = r"(?<![\w-])(?<!justine/)"


def _patterns(basename: str, qualified_only: bool) -> list[re.Pattern[str]]:
    """Write-instruction patterns for one managed doc.

    ``qualified_only`` restricts matching to the full ``docs/holtz/<name>``
    spelling, for files whose bare basenames refer to their own unmanaged copy.
    """
    names = [rf"docs/holtz/{re.escape(basename)}"]
    if not qualified_only:
        names.append(rf"{_LEFT_BOUNDARY}{re.escape(basename)}")
    return [
        re.compile(rf"\b{_WRITE_VERB}\b{_CLAUSE}{{0,70}}?{name}", re.IGNORECASE)
        for name in names
    ]


def _skill_markdown() -> list[Path]:
    files = sorted((REPO_ROOT / "skills").rglob("*.md"))
    files += sorted((REPO_ROOT / "agents").glob("*.md"))
    assert files, "no skill markdown found — the glob is wrong"
    return files


def test_no_skill_file_mandates_a_blocked_write():
    """Every managed doc, every skill file, every write verb."""
    basenames = [Path(p).name for p in MANAGED_DOCS]

    offenders = []
    for path in _skill_markdown():
        rel = path.relative_to(REPO_ROOT)
        qualified_only = path.name in _JUSTINE_DOCS
        patterns = [
            (b, p) for b in basenames for p in _patterns(b, qualified_only)
        ]
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for basename, pattern in patterns:
                match = pattern.search(line)
                if match:
                    offenders.append(f"{rel}:{lineno} [{basename}] {match.group(0).strip()}")

    assert not offenders, (
        "Skill files instruct writes to Sahjhan-managed documents, which every "
        "write vector denies:\n  " + "\n  ".join(offenders) + "\n\n"
        "These files are rendered from the ledger. Record the fact instead — "
        "`sahjhan event finding`, or the transition that auto-emits it — and "
        "the render follows. If a fact genuinely has nowhere to land, it needs "
        "an event, not a hand-written file."
    )


def test_the_fix_loop_still_teaches_what_replaced_those_steps():
    """Deleting the write steps must not leave the mechanism unexplained.

    The reason the fix loop needs no punchlist update is that `fix_commit`
    auto-emits `finding_resolved`, and that is what the render reads. If that
    sentence ever goes, the deletions above become an unexplained gap and the
    instruction grows back.
    """
    text = (REPO_ROOT / "skills" / "holtz" / "references"
            / "step-10-fix-loop.md").read_text(encoding="utf-8")
    assert "finding_resolved" in text and "fix_commit" in text, (
        "step-10-fix-loop.md no longer explains that `fix_commit` emits "
        "`finding_resolved` — the mechanism that makes hand-updating the "
        "punchlist unnecessary."
    )

    deferral = text.split("## Can't-Reproduce Path", 1)[1]
    assert "finding_deferred" in deferral, (
        "The can't-reproduce path no longer explains that the deferral "
        "transition emits `finding_deferred`."
    )
