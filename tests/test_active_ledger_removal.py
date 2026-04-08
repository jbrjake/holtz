"""Verify _active_ledger and write_active_run_marker are removed from _common.py."""
import importlib.util
import inspect
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "enforcement", "hooks"))


def _load_enforcement_common():
    spec = importlib.util.spec_from_file_location(
        "_common_enforcement",
        os.path.join(REPO_ROOT, "enforcement", "hooks", "_common.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_active_ledger_removed():
    """_active_ledger must not exist — sahjhan handles ledger resolution."""
    mod = _load_enforcement_common()
    assert not hasattr(mod, "_active_ledger"), (
        "_active_ledger still exists in enforcement/hooks/_common.py. "
        "Remove it — sahjhan v0.11.0 handles active-ledger resolution."
    )


def test_write_active_run_marker_removed():
    """write_active_run_marker must not exist — sahjhan manages the marker."""
    mod = _load_enforcement_common()
    assert not hasattr(mod, "write_active_run_marker"), (
        "write_active_run_marker still exists in enforcement/hooks/_common.py. "
        "Remove it — sahjhan ledger create --activate manages the marker."
    )


def test_record_authed_event_no_ledger_param():
    """record_authed_event should not accept a ledger parameter."""
    mod = _load_enforcement_common()
    sig = inspect.signature(mod.record_authed_event)
    assert "ledger" not in sig.parameters, (
        "record_authed_event still has a 'ledger' parameter. "
        "Remove it — sahjhan resolves the active ledger automatically."
    )
