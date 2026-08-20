#!/bin/bash
set -euo pipefail

# Regenerate enforcement/trusted-callers.toml with current SHA-256 hashes.
# Run this after modifying any hook script that calls sahjhan sign or vault.

REPO_ROOT="$(git rev-parse --show-toplevel)"
MANIFEST="$REPO_ROOT/enforcement/trusted-callers.toml"

# Hook scripts that connect to the sahjhan daemon (sign, vault, or
# enforcement_read/write/update operations). Every hook that talks to
# the daemon socket needs to be listed here — the daemon rejects
# unlisted callers with "caller not authenticated" and the hook falls
# back to cache=None / is_enforcement_fresh=False, which silently
# disables enforcement.
#
# Since sahjhan 0.21.0 the daemon authenticates only the process *directly*
# holding the socket, and its script must canonicalize under --config-dir
# (i.e. live under enforcement/). A script outside that tree can never
# authenticate however it is invoked, so listing one is decoration — which is
# why hooks/subagent_findings_check.py is no longer here. It never opened the
# socket in the first place; it only warns about missing files.
TRUSTED_SCRIPTS=(
    "enforcement/hooks/_common.py"
    "enforcement/hooks/lens_quiz.py"
    "enforcement/hooks/stop_hook.py"
    "enforcement/hooks/primer.py"
    "enforcement/hooks/sandbox_control.py"
    "enforcement/hooks/session_start.py"
    "enforcement/hooks/pre_tool_hook.py"
    "enforcement/hooks/post_tool_hook.py"
    "enforcement/hooks/commit_gate.py"
    "enforcement/hooks/bash_guard.py"
    "enforcement/hooks/protocol_tracker.py"
    "enforcement/hooks/quiz_capture.py"
    # Not a hook — a gate helper the agent and the fix_commit gate invoke by
    # path. It records the restricted `suite_green` event, so the daemon
    # resolves *this* script from the caller's cmdline and checks its hash.
    "enforcement/scripts/verify_suite.py"
)

cat > "$MANIFEST" << 'HEADER'
# Trusted callers manifest for sahjhan daemon authentication.
# Keys match how the daemon identifies caller scripts at runtime:
# it strips the config directory prefix from the caller's absolute
# path, so `enforcement/hooks/primer.py` is keyed as `hooks/primer.py`.
# Paths outside the config tree (e.g., the plugin-root `hooks/` dir)
# keep their plugin-root-relative form — the daemon falls back to a
# suffix match for those.
# Hashes are SHA-256 of file contents at build/release time.
#
# Regenerate with: scripts/hash-trusted-callers.sh
# CI gate: the pre-commit hook verifies this manifest is up to date.

[callers]
HEADER

for script in "${TRUSTED_SCRIPTS[@]}"; do
    full_path="$REPO_ROOT/$script"
    if [ ! -f "$full_path" ]; then
        echo "WARNING: $script not found, skipping" >&2
        continue
    fi
    hash=$(shasum -a 256 "$full_path" | cut -d' ' -f1)
    # Key scripts under enforcement/ relative to enforcement/ — that's what
    # the daemon matches against (strips --config-dir prefix from the
    # caller's absolute path). Scripts outside enforcement/ keep their
    # plugin-root-relative form.
    key="${script#enforcement/}"
    echo "\"$key\" = \"sha256:$hash\"" >> "$MANIFEST"
done

echo "Updated $MANIFEST"
