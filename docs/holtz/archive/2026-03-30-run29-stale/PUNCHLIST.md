
# Punchlist

**Protocol:** holtz v1.0.0
**Run:** ?
**State:** Recon (Steps 0-4)
**Ledger:** 9 events

## HIGH

| ID | Category | Location | Perspective | Description | Status |
|----|----------|----------|-------------|-------------|--------|
| BH-020 | bug/logic | enforcement/states.toml,enforcement/hooks/stop_gate.py | temporal-protocol | No clean exit point between runs. Ending a run leaves state in awaiting_clear or fix_loop (non-terminal). Archiving and reinitializing moves to recon (also non-terminal). The stop gate blocks on all non-terminal states, so there is no state where the operator can safely pause between runs. The idle state allows run_start but not stopping. The recon state allows no iteration_boundary. An operator who finishes one run and wants to start fresh in a new conversation is trapped by the stop gate. | RESOLVED |

