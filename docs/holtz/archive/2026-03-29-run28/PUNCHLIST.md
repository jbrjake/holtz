
# Punchlist

**Protocol:** holtz v1.0.0
**Run:** ?
**State:** Fix Loop (Step 10)
**Ledger:** 163 events

## HIGH

| ID | Category | Location | Perspective | Description | Status |
|----|----------|----------|-------------|-------------|--------|
| BH-005 | bug/security | enforcement/hooks/_sahjhan_bootstrap.py:137 | component | Newline bypass in _check_bash_write: re.split pattern does not split on bare newlines. Multi-line bash commands bypass all startswith-based write detectors (cp, mv, install, dd, python3, wget). Real security bypass. | RESOLVED |
| BH-019 | bug/logic | enforcement/hooks/bash_guard.py,enforcement/events.toml | temporal-protocol | Self-referential deadlock: sahjhan render operations modify managed files (STATUS.md, PUNCHLIST.md), triggering bash_guard manifest violations. Violations are permanent (no resolution pathway per events.toml). 46 violations accumulated in this run, permanently blocking convergence. The enforcement engine cannot converge on itself. | RESOLVED |
## MEDIUM

| ID | Category | Location | Perspective | Description | Status |
|----|----------|----------|-------------|-------------|--------|
| BH-003 | doc/drift | skills/holtz/SKILL.md:87,119,128 | contract | SKILL.md CLI examples omit required event fields. finding_resolved example (L87) missing project/run/auditor/phase/step. recon_step example (L119) missing project/run/auditor/phase. justine_dispatched example (L128) missing project/run/auditor. Commands will fail with missing field errors. | RESOLVED |
| BH-004 | bug/security | hooks/hooks.json, enforcement/hooks/_sahjhan_bootstrap.py:102,129,256,268 | integration | _sahjhan_bootstrap.py contains _check_bash_write and _bash_references_guarded for Bash commands but hooks.json only configures it for Write|Edit and Read. Bash writes to enforcement/ and read-guarded paths (session.key, quiz-bank.json) are not preventively blocked. Caught reactively by bash_guard PostToolUse manifest verify, but the write already occurred. | RESOLVED |
| BH-006 | bug/security | enforcement/hooks/_sahjhan_bootstrap.py:220-227 | component | wget --output-document=PATH (equals form) bypasses write detection. Only short form -O is handled. | RESOLVED |
| BH-007 | bug/security | enforcement/hooks/_sahjhan_bootstrap.py:128-229 | component | No curl handler in _check_bash_write. curl -o and curl --output to protected paths are undetected. Redirect form (curl > file) is caught. | RESOLVED |
| BH-008 | bug/logic | enforcement/hooks/lens_quiz.py:350,444 | component | PAT-001: parse_lens_name and parse_answers operate on raw message without mask_fenced_blocks. Code block containing LENS: prefix triggers quiz gate for non-lens subagents. mask_fenced_blocks available in _common but never called. | RESOLVED |
| BH-010 | doc/drift | skills/holtz/SKILL.md:62-69 | contract | Phase Index table uses 5 nonexistent state names: initialized (actual: idle), auditing (actual: audit), merging (actual: merge_ready/merge_done), converging (actual: all_perspectives_clean), finalizing (actual: finalized). Operators matching sahjhan status output to Phase Index will find no matches. | RESOLVED |
| BH-011 | doc/drift | skills/holtz/SKILL.md:118 | contract | sahjhan ledger checkpoint example missing required --name flag. Command will error at runtime with missing required argument. | RESOLVED |
| BH-012 | doc/drift | skills/holtz/SKILL.md:106 | contract | sahjhan set complete perspective example missing required MEMBER positional argument. Should be sahjhan set complete perspective <lens-name>. | RESOLVED |
| BH-015 | doc/drift | README.md:146 | public-contract | Circuit breaker claims inaccurate: max 3 attempts per item is advisory only (no enforcement gate in transitions.toml). Stall threshold is 15 non-productive commands, not 3 iterations as stated. README implies enforcement that does not exist. | RESOLVED |
| BH-016 | bug/logic | enforcement/hooks/_protocol_cache.py:181-190 | security | is_sahjhan_cmd returns True if ANY segment of chained command is sahjhan. commit_gate exits OK for entire command, so git commit; sahjhan status bypasses unregistered-commit block. | RESOLVED |
| BH-017 | bug/logic | enforcement/hooks/protocol_tracker.py:112-116 | data-flow | Substring check 'fix_commit in cmd' matches anywhere in full command string. A sahjhan command with fix_commit in a ledger name or option value would incorrectly clear unregistered_commits. | RESOLVED |
| BH-018 | bug/integration | enforcement/hooks/write_guard.py:20-26,enforcement/hooks/_sahjhan_bootstrap.py:25-31 | integration | MANAGED_FILES and MANAGED_DOCS are identical lists maintained independently in two files. No test or import ensures they stay in sync. Adding a managed file to one but not the other creates a bypass. | RESOLVED |
## LOW

| ID | Category | Location | Perspective | Description | Status |
|----|----------|----------|-------------|-------------|--------|
| BH-001 | doc/drift | README.md:7 | public-contract | Badge claims 857 tests passed but actual is 856 passed + 1 skipped. Badge also claims 76% coverage but actual is 80%. | RESOLVED |
| BH-002 | doc/drift | README.md:190,214 | public-contract | Two instances of stale line count: claims 19,446 lines but actual is 19,735 (delta +289). | RESOLVED |
| BH-009 | bug/logic | enforcement/hooks/lens_quiz.py:444-450 | component | Dual-parser divergence: parse_answers returns lens name but it is discarded at L450. If message has two LENS: lines with different names, questions are selected for one lens but answers scored against another. | RESOLVED |
| BH-013 | doc/drift | README.md:160,190 | public-contract | Run count contradiction: L160 says Twenty-seven runs but L190 says After 28 runs. Internal inconsistency in same section. | RESOLVED |
| BH-014 | doc/drift | README.md:190,214 | public-contract | Line count stale: README claims 19649 but actual Python line count is 24071. Same class as BH-001/BH-002. | RESOLVED |

