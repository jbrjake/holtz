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
    cfg = tomllib.loads((ENFORCEMENT / "transitions.toml").read_text())
    paths: list[str] = []
    for t in cfg.get("transitions", []):
        for gate in t.get("gates", []):
            if gate.get("type") == "file_exists" and "path" in gate:
                paths.append(gate["path"])
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
