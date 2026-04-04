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
# Paths are relative to the plugin root (config directory's parent).
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
    echo "\"$script\" = \"sha256:$hash\"" >> "$MANIFEST"
done

echo "Updated $MANIFEST"
