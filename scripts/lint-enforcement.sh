#!/usr/bin/env bash
# Static analysis of the enforcement layering (#82).
#
# Two halves, and they need each other:
#
#   sahjhan lint            the protocol GRAPH — a gate that requires an event
#                           nothing can produce, a state with no satisfiable
#                           exit, a boundary a path routes around, two
#                           predicates deciding one fact two ways. Config in,
#                           findings out; it never opens a ledger.
#
#   scripts/enforcement_lint.py
#                           the parts of the chain that live in holtz code —
#                           who really writes each event, whether the declared
#                           producer is that writer, whether it is registered
#                           and hash-pinned, whether a skill file teaches the
#                           command. The engine must never learn about those.
#
# The engine can only see producers declared in TOML. Holtz's producers are
# Python hooks and skill-file commands, so `[[events.*.producers]]` is a claim
# and the second half is what falsifies it. Running one without the other
# leaves exactly the gap #79 shipped through.
#
# Exit 0 = no errors. Exit 1 = a gate does not mean what it says.
# Warnings do not fail unless --strict.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

STRICT=""
if [[ "${1:-}" == "--strict" ]]; then
    STRICT="--strict"
fi

FAILURES=0

SAHJHAN="$(python3 -c "
import sys
sys.path.insert(0, 'enforcement/hooks')
import _resolve
print(_resolve.sahjhan_binary())
")"

echo "--- sahjhan lint (protocol graph) ---"
if [[ -x "$SAHJHAN" ]]; then
    # Exit 3 is "errors found"; anything else non-zero is the tool failing,
    # which must not be mistaken for a clean protocol.
    set +e
    "$SAHJHAN" --config-dir enforcement lint ${STRICT}
    status=$?
    set -e
    if [[ $status -ne 0 ]]; then
        FAILURES=$((FAILURES + 1))
    fi
else
    # Not silently skipped: an absent binary means the graph half did not run,
    # and reporting that as a pass is the failure mode this file exists to stop.
    echo "sahjhan binary not found at $SAHJHAN — graph checks did NOT run" >&2
    echo "run: python3 -c \"import sys; sys.path.insert(0,'enforcement/hooks'); import _resolve; _resolve.ensure_sahjhan()\"" >&2
    FAILURES=$((FAILURES + 1))
fi

echo ""
echo "--- enforcement_lint (declarations vs. the tree) ---"
if ! python3 scripts/enforcement_lint.py ${STRICT}; then
    FAILURES=$((FAILURES + 1))
fi

# The third artifact: the layering written out where a person reads it.
# Detection makes CI red; comprehension is what catches the defect class we
# have not named yet. A stale contract is a document that describes a protocol
# we no longer run, which is worse than no document.
echo ""
echo "--- enforcement contract (generated doc vs. config) ---"
if ! python3 scripts/enforcement_contract.py --check; then
    FAILURES=$((FAILURES + 1))
fi

if [[ $FAILURES -gt 0 ]]; then
    exit 1
fi
