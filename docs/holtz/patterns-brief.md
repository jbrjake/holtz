# Holtz Pattern Brief

> Read this before starting any audit work. These patterns were discovered
> in prior audits of this project. Check for them in the code you're reviewing.

## PAT-001: dead-code-via-config (Run 28, 2026-03-29)
**What to look for:** Protection or enforcement logic that exists in source code but is not reachable because the configuration layer (hooks.json, routing tables, event matchers) doesn't route events to it.
**Detection heuristic:** For each function in a hook file, trace whether any configuration entry causes it to be invoked. Grep for the hook's filename in hooks.json and verify all code paths in main() are reachable given the configured matchers.
**Example:** _sahjhan_bootstrap.py had _check_bash_write (Bash write protection) and _bash_references_guarded (Bash read guard), but hooks.json only configured it for Write|Edit and Read — not Bash. The protection code was dead until the matcher was updated.

## PAT-002: copy-paste-algorithm (Run 30, 2026-03-30)
**What to look for:** Two files independently implementing the same algorithm without sharing code. When one is updated, the other silently diverges.
**Detection heuristic:** `grep -rn 'def.*match\|def.*resolve\|def.*detect\|def.*triple\|def.*prefix' --include='*.py' | sort` — look for function names with similar semantics in different files. For each match, compare logic.
**Example:** _sahjhan_bootstrap.py._platform_triple() and _resolve.py.sahjhan_binary() both independently mapped platform.machine()+platform.system() to Rust target triples. Also: pricing.py had get_pricing() and _custom_pricing() both doing longest-prefix model name matching.

## PAT-003: happy-path-matcher (Run 30, 2026-03-30)
**What to look for:** Regex or string matching that handles the common invocation format but misses valid edge-case input formats (env-prefix commands, unanchored patterns, bare binary names without paths).
**Detection heuristic:** For each `re.match()` call in hooks/enforcement code, ask: "What valid input format does this NOT match?" Check for: missing anchors, assumed token ordering, assumed path prefix.
**Example:** is_git_commit() used `re.match(r"git\s+commit\b", seg)` which missed `VAR=x git commit` (valid env-prefix bash). _ANSWERS_RE lacked ^ anchor, so quiz answers on a code-fence opener line survived masking.
