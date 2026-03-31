#!/usr/bin/env bash
# holtz_split_session.sh — Run Holtz in two sessions for token efficiency.
#
# Session 1: Phase 0 (recon) + Justine dispatch
# Session 2: Phases 1-4 (audit, merge, fix loop, convergence)
#
# The split point is after Phase 0 completes and all recon artifacts are on disk.
# This resets the context window from ~103K back to ~32K, eliminating the
# accumulated recon context from being re-cached on every subsequent API call.
#
# Usage:
#   ./scripts/holtz_split_session.sh [project-path]
#
# Prerequisites:
#   - Claude Code CLI (claude) on PATH
#   - Holtz skill installed

set -euo pipefail

PROJECT="${1:-.}"
cd "$PROJECT"

echo "=== Holtz Split-Session Audit ==="
echo "Phase 1/2: Recon + Justine dispatch"
echo ""

# Session 1: Recon
claude --print "Run Holtz Phase 0 only on this codebase. Complete all recon steps (0a-0h), write all artifacts to docs/holtz/recon/, initialize/reconcile the impact graph, write STATUS.md and PUNCHLIST.md with any escalated items, and dispatch Justine as a background subagent. After dispatching Justine and verifying all Phase 0 artifacts exist on disk, STOP. Do not proceed to Phase 1. Report: 'Phase 0 complete. Justine dispatched. Ready for session split.'"

echo ""
echo "Phase 0 complete. Starting fresh session for Phases 1-4."
echo ""

# Verify Phase 0 artifacts exist
for f in docs/holtz/recon/step3-recon-summary.md docs/holtz/recon/step4-predictions.md docs/holtz/STATUS.md docs/holtz/impact-graph.json; do
    if [ ! -f "$f" ]; then
        echo "ERROR: Missing artifact: $f"
        echo "Phase 0 may not have completed. Check docs/holtz/STATUS.md."
        exit 1
    fi
done

echo "All Phase 0 artifacts verified."
echo ""

# Session 2: Audit phases
# Wait for Justine if needed (she runs ~15 min, recon takes ~20 min, so she may already be done)
claude --print "Resume Holtz from Phase 1. This is a FRESH SESSION after a deliberate context split for token efficiency.

READ THESE FILES FIRST to recover state:
1. docs/holtz/STATUS.md (your program counter)
2. docs/holtz/recon/step3-recon-summary.md (recon synthesis)
3. docs/holtz/recon/step4-predictions.md (predictions to test)
4. docs/holtz/PUNCHLIST.md (any escalated items from recon)

Phase 0 (recon) is COMPLETE. Justine has been dispatched and may still be running.

Proceed through: Phase 1 (doc audit) -> Phase 2 (test audit) -> Phase 3 (adversarial audit) -> check for Justine results at docs/holtz/justine/SUMMARY.md -> merge if available -> Phase 4 (fix loop) -> convergence.

If Justine's SUMMARY.md does not exist when you reach the merge point, note it in STATUS.md and proceed with Holtz-only findings. The merge can be done in a follow-up if Justine is still running."

echo ""
echo "=== Holtz Split-Session Audit Complete ==="
