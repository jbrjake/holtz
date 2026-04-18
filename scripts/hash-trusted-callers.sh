#!/bin/bash
set -euo pipefail

# Regenerate enforcement/trusted-callers.toml with current SHA-256 hashes.
# Run this after modifying any hook script that calls sahjhan sign or vault.

REPO_ROOT="$(git rev-parse --show-toplevel)"
MANIFEST="$REPO_ROOT/enforcement/trusted-callers.toml"

# Hook scripts that connect to the sahjhan daemon (sign or vault operations)
TRUSTED_SCRIPTS=(
    "enforcement/hooks/_common.py"
    "enforcement/hooks/lens_quiz.py"
    "enforcement/hooks/stop_hook.py"
    "enforcement/hooks/primer.py"
    "hooks/subagent_findings_check.py"
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
