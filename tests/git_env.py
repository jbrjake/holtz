"""The one expression of "an environment safe to run git in, elsewhere".

`git-hooks/pre-commit` runs this suite, and git runs a hook with `GIT_DIR`,
`GIT_INDEX_FILE`, `GIT_PREFIX` and friends **exported**, pointing at the
repository being committed to. Left in place they follow every subprocess into
a throwaway repository, where `git worktree add` exits 128 — so a test passes
every way you check it by hand and fails only inside the commit that ships it.

`sahjhan` and `verify_suite.compute_tree_hash` shell out to git too, so the
scrubbed environment belongs on *every* subprocess in such a test, not only on
the ones whose argv starts with `git`.
"""
from __future__ import annotations

import os


def scrubbed_env(**overrides: str) -> dict[str, str]:
    """The ambient environment with git's per-invocation variables removed."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(overrides)
    return env
