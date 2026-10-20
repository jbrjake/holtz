"""Config self-consistency: MANAGED_DOCS must match what sahjhan renders.

Issue #60 was a wedge: `docs/holtz/PUNCHLIST-MERGED.md` was in the PreToolUse
hook's MANAGED_DOCS (so every write to it was blocked) but had no render rule
in renders.toml (so `sahjhan render` never produced it either). The
`merge_complete` transition gates on that file existing, so a full adversarial
run could never advance past Step 9 — nothing was allowed to create the file.

These tests lock the invariant that would have caught it at commit time:

    a path is in MANAGED_DOCS  <=>  it has a render rule in renders.toml

and the direct corollary that no `file_exists` gate may require a path that is
simultaneously write-guarded and unrendered (i.e. unsatisfiable by anyone).

If a future change re-adds an agent-authored artifact to MANAGED_DOCS, or
adds a file_exists gate on a managed-but-unrendered path, this fails loudly
here instead of wedging a live audit run.
"""
from __future__ import annotations

import importlib.util
import sys
import tomllib
from pathlib import Path
from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parent.parent
ENFORCEMENT = REPO_ROOT / "enforcement"
HOOKS = ENFORCEMENT / "hooks"

sys.path.insert(0, str(HOOKS))


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, str(path))
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_BOOTSTRAP = _load("_sahjhan_bootstrap", HOOKS / "_sahjhan_bootstrap.py")


def _managed_basenames() -> set[str]:
    return {Path(p).name for p in _BOOTSTRAP.MANAGED_DOCS}


def _rendered_basenames() -> set[str]:
    cfg = tomllib.loads((ENFORCEMENT / "renders.toml").read_text())
    return {Path(r["target"]).name for r in cfg.get("renders", [])}


def _file_exists_gate_paths() -> list[str]:
    """Every path a `file_exists` gate requires, at any nesting depth.

    `not`, `all_of`, `any_of` and `k_of_n` carry child gates, and a positive
    `file_exists` buried in one wedges a run exactly as hard as a top-level
    one. Walking only the top level would have declared the config clean while
    the unsatisfiable requirement sat one level down.
    """
    cfg = tomllib.loads((ENFORCEMENT / "transitions.toml").read_text())
    paths: list[str] = []

    def walk(gates: list[dict], negated: bool) -> None:
        for gate in gates:
            children = gate.get("gates", [])
            if gate.get("type") == "not":
                walk(children, not negated)
                continue
            if children:
                walk(children, negated)
            # Only a *positive* requirement can be unsatisfiable. Under `not`
            # the gate asks for the file to be absent, which deleting it
            # satisfies — and delete is what MANAGED_DOCS does not block.
            if not negated and gate.get("type") == "file_exists" and "path" in gate:
                paths.append(gate["path"])

    for t in cfg.get("transitions", []):
        walk(t.get("gates", []), negated=False)
    return paths


def test_managed_docs_are_exactly_the_rendered_files():
    """MANAGED_DOCS must equal the set of rendered targets — no more, no less.

    A managed file with no render rule can be produced by no one (the guard
    blocks the agent; sahjhan never renders it). A rendered file that is NOT
    managed can be forged by the agent, defeating the ledger-as-source-of-truth
    guarantee. Both directions matter.
    """
    managed = _managed_basenames()
    rendered = _rendered_basenames()

    unrendered_but_managed = managed - rendered
    assert not unrendered_but_managed, (
        f"MANAGED_DOCS contains files with no render rule: "
        f"{sorted(unrendered_but_managed)}. These are write-blocked but never "
        f"rendered — nothing can create them. If they are agent-authored "
        f"artifacts, remove them from MANAGED_DOCS (see issue #60). If they "
        f"should be ledger-rendered, add a render rule in renders.toml."
    )

    rendered_but_unmanaged = rendered - managed
    assert not rendered_but_unmanaged, (
        f"renders.toml renders files that are NOT in MANAGED_DOCS: "
        f"{sorted(rendered_but_unmanaged)}. A rendered view the agent can "
        f"overwrite lets it forge protocol state — add these to MANAGED_DOCS."
    )


def test_no_file_exists_gate_requires_an_unsatisfiable_path():
    """The #60 wedge, checked directly: a file_exists gate must not require a
    path that is write-guarded (MANAGED_DOCS) yet unrendered.

    Such a path is satisfiable by no actor, so the transition can never fire.
    """
    managed = _managed_basenames()
    rendered = _rendered_basenames()

    for path in _file_exists_gate_paths():
        base = Path(path).name
        if base in managed and base not in rendered:
            raise AssertionError(
                f"file_exists gate requires '{path}', which is in MANAGED_DOCS "
                f"(write-blocked) but has no render rule — nothing can create "
                f"it, so the transition is unsatisfiable (issue #60). Either "
                f"un-manage the path (if agent-authored) or render it."
            )


# ── The docs' own picture of the runtime tree (item 13) ──────────────────────
#
# `ARCHITECTURE.md`'s runtime-artifacts block is the only place a reader is
# shown what a run leaves behind. It listed `PUNCHLIST-MERGED.md`, which P0.4
# deleted as a concept and which `merge_done -> awaiting_clear` now gates on
# being *absent*, and it omitted two files the hook guards. Both directions are
# derived from config here rather than from a hand-kept list, so the block
# cannot drift again without this going red.

ARCHITECTURE = REPO_ROOT / "docs" / "ARCHITECTURE.md"
_RUNTIME_BLOCK_HEADING = "## Runtime artifacts"


def _runtime_artifacts_block() -> str:
    """The fenced tree under `## Runtime artifacts`, and nothing else."""
    text = ARCHITECTURE.read_text(encoding="utf-8")
    start = text.index(_RUNTIME_BLOCK_HEADING)
    fence = text.index("```", start)
    end = text.index("```", fence + 3)
    return text[fence:end]


def _absent_required_paths() -> list[str]:
    """Every path a gate requires to NOT exist, at any nesting depth.

    The mirror image of `_file_exists_gate_paths`: a path under a `not` is one
    the protocol requires deleted, so a document still presenting it as a
    runtime artifact is telling the reader to recreate a wedge.
    """
    cfg = tomllib.loads((ENFORCEMENT / "transitions.toml").read_text())
    paths: list[str] = []

    def walk(gates: list[dict], negated: bool) -> None:
        for gate in gates:
            children = gate.get("gates", [])
            if gate.get("type") == "not":
                walk(children, not negated)
                continue
            if children:
                walk(children, negated)
            if negated and gate.get("type") == "file_exists" and "path" in gate:
                paths.append(gate["path"])

    for t in cfg.get("transitions", []):
        walk(t.get("gates", []), False)
    return paths


def test_the_layout_block_shows_every_managed_doc() -> None:
    block = _runtime_artifacts_block()
    missing = sorted(name for name in _managed_basenames() if name not in block)
    assert not missing, (
        f"ARCHITECTURE.md's runtime-artifacts block omits {missing}. Every file "
        f"the PreToolUse hook guards is a file a run produces, so a reader "
        f"looking for it in this block will not find it — and will write it by "
        f"hand and be blocked."
    )


def test_the_layout_block_shows_nothing_the_protocol_requires_deleted() -> None:
    block = _runtime_artifacts_block()
    stale = sorted({
        Path(p).name for p in _absent_required_paths() if Path(p).name in block
    })
    assert not stale, (
        f"ARCHITECTURE.md's runtime-artifacts block still lists {stale}, which "
        f"a `not(file_exists)` gate requires absent — `merge_done -> "
        f"awaiting_clear` refuses to fire while it exists."
    )
