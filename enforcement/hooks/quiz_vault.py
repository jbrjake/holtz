#!/usr/bin/env python3
"""Vault channel for the lens quiz bank (#73).

The quiz bank lives ONLY in the sahjhan daemon's in-memory vault — never on
disk. The ledger under ``docs/holtz/.sahjhan/`` is hash-chained but NOT
encrypted, so on-disk questions would be ``cat``-readable and their answers
would leak, defeating the whole point of the quiz (forcing a *later* pass to
actually re-read the code rather than claim "I looked again").

Lifecycle, all enforced declaratively by sahjhan's vault policy
(``enforcement/vault.toml``), never by imperative checks here:

* During **recon**, a generation subagent derives questions from the impact
  graph and stages them one at a time. A trusted courier hook
  (``quiz_capture.py``) appends each to the ``quiz-bank`` vault key. The key is
  ``writable_in_states = ["recon"]`` — so the daemon slams the channel shut the
  instant ``recon_complete`` advances the state. Questions "delivered after the
  phase has passed" are rejected at the engine.
* During lens sweeps, ``lens_quiz.py`` reads the bank to pose/score. The key is
  ``readable_in_states`` = the sweep states only.

Trusted callers only: the daemon authenticates the peer (SO_PEERCRED against
``trusted-callers.toml``) before any vault op, so these run from registered
hooks — the bare ``sahjhan`` CLI the agent can invoke is rejected.
"""
from __future__ import annotations

import base64
import binascii
import contextlib
import json
import os

from _common import (
    _daemon_request,
    _get_daemon_socket_path,
    record_authed_event,
)

VAULT_NAME = "quiz-bank"


def get_run_number(cwd: str) -> str:
    """Current run number from the sahjhan active-ledger marker ('0' if none)."""
    active_file = os.path.join(cwd, "docs", "holtz", ".sahjhan", "active-ledger")
    try:
        with open(active_file, encoding="utf-8") as f:
            return f.read().strip().replace("run-", "") or "0"
    except OSError:
        return "0"


def store_quiz_bank(bank: list[dict], cwd: str | None = None) -> None:
    """Overwrite the ``quiz-bank`` vault entry with ``bank``.

    Raises OSError (socket) / RuntimeError (daemon error, e.g. the vault
    policy forbids a write outside recon). Caller must be a trusted hook.
    """
    sock_path = _get_daemon_socket_path(cwd)
    data = base64.b64encode(json.dumps(bank).encode()).decode()
    _daemon_request(sock_path, {"op": "vault_store", "name": VAULT_NAME, "data": data})


def read_quiz_bank(cwd: str | None = None) -> list[dict]:
    """Read and decode the ``quiz-bank`` vault entry.

    Raises: OSError (socket), RuntimeError (daemon error — not_found when the
    bank is empty, or the vault policy forbids a read in the current state),
    KeyError / binascii.Error / ValueError (corrupt payload).
    """
    sock_path = _get_daemon_socket_path(cwd)
    resp = _daemon_request(sock_path, {"op": "vault_read", "name": VAULT_NAME})
    return json.loads(base64.b64decode(resp["data"]))


def read_quiz_bank_safe(cwd: str | None = None) -> list[dict]:
    """The vault bank, or ``[]`` on any failure (graceful degradation).

    Used by ``lens_quiz.py``: a daemon that is down (or a bank that was never
    generated) degrades to "no quiz" rather than crashing the SubagentStop
    hook. A populated, readable bank always round-trips.
    """
    with contextlib.suppress(
        OSError, RuntimeError, KeyError, ValueError, binascii.Error, json.JSONDecodeError
    ):
        return read_quiz_bank(cwd)
    return []


def _read_or_empty(cwd: str | None) -> list[dict]:
    """Current bank for read-modify-write, treating not_found as empty.

    A ``not_found`` daemon error (the first question of a run) yields ``[]``.
    Any *other* RuntimeError — notably a vault-policy ``state_forbidden`` — is
    re-raised so the courier surfaces "not in recon" instead of silently
    resetting the bank.
    """
    try:
        bank = read_quiz_bank(cwd)
    except RuntimeError as exc:
        if "no entry" in str(exc) or "not_found" in str(exc):
            return []
        raise
    return bank if isinstance(bank, list) else []


def append_question(question: dict, cwd: str | None = None) -> int:
    """Append one question to the vault bank (read-modify-write). Returns count.

    The append (a ``vault_store``) is what the daemon gates to the recon state.
    Outside recon the store raises RuntimeError — the caller reports it rather
    than writing.
    """
    bank = _read_or_empty(cwd)
    bank.append(question)
    store_quiz_bank(bank, cwd)
    return len(bank)


def record_bank_generated(
    cwd: str,
    run: str = "0",
    auditor: str = "holtz",
) -> None:
    """Record the ``quiz_bank_generated`` marker for this run.

    Gates ``recon_complete`` (you cannot leave recon without a bank), and
    carries the question/lens counts for the audit trail. Best-effort:
    swallows daemon-unavailable errors. Counts come from the vault, so this
    must run while the bank is still readable (i.e. during recon).
    """
    bank = read_quiz_bank_safe(cwd)
    lenses = {q.get("lens") for q in bank if q.get("lens")}
    project = os.path.basename(os.path.normpath(cwd)) or "project"
    with contextlib.suppress(OSError, RuntimeError):
        record_authed_event(
            "quiz_bank_generated",
            {
                "project": project,
                "run": str(run),
                "auditor": auditor,
                "question_count": str(len(bank)),
                "lens_count": str(len(lenses)),
            },
            cwd,
        )
