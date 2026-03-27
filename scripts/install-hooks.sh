#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
GIT_HOOKS_DIR="$REPO_ROOT/.git/hooks"
SRC_DIR="$REPO_ROOT/git-hooks"

if [[ ! -d "$SRC_DIR" ]]; then
    echo "Error: $SRC_DIR not found. Run from the repository root." >&2
    exit 1
fi

for hook in "$SRC_DIR"/*; do
    hook_name="$(basename "$hook")"
    dest="$GIT_HOOKS_DIR/$hook_name"

    # Check for existing hook that isn't our symlink
    if [[ -e "$dest" ]] && [[ ! -L "$dest" ]]; then
        echo "Error: $dest already exists and is not a symlink. Remove it manually or back it up first." >&2
        exit 1
    fi

    # If it's already our symlink, skip
    if [[ -L "$dest" ]] && [[ "$(readlink "$dest")" == "$hook" ]]; then
        echo "$hook_name: already installed"
        continue
    fi

    ln -sf "$hook" "$dest"
    echo "$hook_name: installed"
done

# ── Sahjhan binary setup ──

ARCH=$(uname -m)
OS=$(uname -s | tr '[:upper:]' '[:lower:]')
case "$ARCH" in arm64) ARCH="aarch64" ;; esac

case "$OS" in
    darwin) TRIPLE="${ARCH}-apple-darwin" ;;
    linux)  TRIPLE="${ARCH}-unknown-linux-gnu" ;;
    *)      TRIPLE="${ARCH}-${OS}" ;;
esac

SAHJHAN_BIN="$REPO_ROOT/bin/sahjhan-${TRIPLE}"
if [[ -f "$SAHJHAN_BIN" ]]; then
    chmod +x "$SAHJHAN_BIN"
    ln -sf "sahjhan-${TRIPLE}" "$REPO_ROOT/bin/sahjhan"
    echo "sahjhan: binary ready at bin/sahjhan-${TRIPLE} (symlinked to bin/sahjhan)"

    # Version pinning check
    PINNED_VERSION_FILE="$REPO_ROOT/bin/.sahjhan-version"
    if [[ -f "$PINNED_VERSION_FILE" ]]; then
        PINNED_VERSION=$(cat "$PINNED_VERSION_FILE")
        ACTUAL_VERSION=$("$SAHJHAN_BIN" --version 2>/dev/null || echo "unknown")
        if [[ "$ACTUAL_VERSION" != *"$PINNED_VERSION"* ]] && [[ "$ACTUAL_VERSION" != "unknown" ]]; then
            echo "WARNING: Sahjhan binary version ($ACTUAL_VERSION) does not match pinned version ($PINNED_VERSION)." >&2
            echo "         Run scripts/vendor-sahjhan.sh $PINNED_VERSION to fix." >&2
        fi
    fi
else
    echo "sahjhan: no binary for ${TRIPLE}. Run scripts/vendor-sahjhan.sh <version> first."
fi

# ── Dev-mode settings.local.json hook registration ──

HOOKS_JSON="$REPO_ROOT/hooks/hooks.json"
SETTINGS_FILE="$REPO_ROOT/.claude/settings.local.json"

if [[ ! -f "$HOOKS_JSON" ]]; then
    echo "WARNING: $HOOKS_JSON not found; skipping settings.local.json update." >&2
else
    export REPO_ROOT
    python3 - <<'PYEOF'
import json, os, sys

repo_root = os.environ.get("REPO_ROOT") or os.popen("git rev-parse --show-toplevel").read().strip()
hooks_json_path = os.path.join(repo_root, "hooks", "hooks.json")
settings_path = os.path.join(repo_root, ".claude", "settings.local.json")

# Load hooks.json and strip ${CLAUDE_PLUGIN_ROOT}/ from all commands
with open(hooks_json_path) as f:
    hooks_data = json.load(f)

def strip_plugin_root(obj):
    if isinstance(obj, dict):
        return {k: strip_plugin_root(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [strip_plugin_root(item) for item in obj]
    if isinstance(obj, str):
        return obj.replace('"${CLAUDE_PLUGIN_ROOT}/', '"').replace("${CLAUDE_PLUGIN_ROOT}/", "")
    return obj

new_hooks = strip_plugin_root(hooks_data.get("hooks", {}))

# Load existing settings.local.json if present (to preserve permissions)
existing = {}
if os.path.isfile(settings_path):
    with open(settings_path) as f:
        try:
            existing = json.load(f)
        except json.JSONDecodeError:
            print(f"WARNING: Could not parse {settings_path}; existing content will be replaced.", file=sys.stderr)

# Merge: replace hooks, preserve everything else (e.g. permissions)
existing["hooks"] = new_hooks

os.makedirs(os.path.dirname(settings_path), exist_ok=True)
with open(settings_path, "w") as f:
    json.dump(existing, f, indent=2)
    f.write("\n")

print(f"settings.local.json: hooks section updated from hooks/hooks.json")
PYEOF

    # Run hook verification
    if python3 "$REPO_ROOT/enforcement/hooks/verify_hooks.py" --settings "$SETTINGS_FILE"; then
        echo "install-hooks: verification passed"
    else
        echo "WARNING: Hook verification failed. Check settings.local.json." >&2
    fi
fi
