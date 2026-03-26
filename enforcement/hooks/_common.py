"""Bridge to hooks/_common.py shared utilities.

Enforcement hooks live in enforcement/hooks/ but need access to the
shared exit helpers in hooks/_common.py. Uses importlib to avoid
self-import (both files are named _common.py).
"""
from __future__ import annotations

import importlib.util
import os

_HOOKS_COMMON = os.path.join(
    os.path.dirname(__file__), '..', '..', 'hooks', '_common.py'
)
_spec = importlib.util.spec_from_file_location("hooks._common", _HOOKS_COMMON)
assert _spec is not None and _spec.loader is not None
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

# Re-export all public names
read_event = _mod.read_event
exit_ok = _mod.exit_ok
exit_warn = _mod.exit_warn
exit_block = _mod.exit_block
exit_stop_allow = _mod.exit_stop_allow
exit_stop_block = _mod.exit_stop_block
mask_fenced_blocks = _mod.mask_fenced_blocks


def _active_ledger(cwd: str) -> str | None:
    """Detect the active run ledger name from .sahjhan/active-run marker."""
    active_file = os.path.join(cwd, "docs", "holtz", ".sahjhan", "active-run")
    if os.path.isfile(active_file):
        with open(active_file) as f:
            return f.read().strip()
    return None
