#!/usr/bin/env bash
# Dev setup for the holtz repo.
#
# By default, this script ONLY does repo-dev work: installs git hooks
# (pre-commit, post-commit, pre-push) and makes the sahjhan binary
# executable. It does NOT enable the plugin's Claude Code hooks against
# this repo itself.
#
# Running the plugin's enforcement hooks against the plugin's own repo
# creates circular blocks: the hooks protect enforcement/ and managed
# state, but dev work frequently needs to edit those paths, and the
# wrappers that pytest spawns look like interpreter writes. That loop
# wastes hours.
#
# If you explicitly want to simulate a downstream consumer — e.g. to
# manually verify that the enforcement hooks block the things they're
# supposed to block — run:
#
#     scripts/install-hooks.sh --simulate-downstream
#
# That writes hooks/hooks.json into .claude/settings.local.json so the
# Claude Code session enforces the plugin against itself. Reverse with
# --no-simulate-downstream (strips the hooks section while preserving
# permissions and other settings).
set -euo pipefail

MODE="dev"
for arg in "$@"; do
    case "$arg" in
        --simulate-downstream) MODE="simulate-downstream" ;;
        --no-simulate-downstream) MODE="strip-enforcement" ;;
        -h|--help)
            sed -n '2,22p' "$0" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        *)
            echo "Unknown flag: $arg" >&2
            exit 2
            ;;
    esac
done

REPO_ROOT="$(git rev-parse --show-toplevel)"
GIT_HOOKS_DIR="$REPO_ROOT/.git/hooks"
SRC_DIR="$REPO_ROOT/git-hooks"

if [[ ! -d "$SRC_DIR" ]]; then
    echo "Error: $SRC_DIR not found. Run from the repository root." >&2
    exit 1
fi

# Prune stale hook symlinks whose source under git-hooks/ was removed
# (e.g. the retired commit-msg hook). Without this, a deleted hook stays
# wired as a dangling symlink until manually cleaned. Only touch symlinks
# that point back into our SRC_DIR — never a dev's own hooks.
if [[ -d "$GIT_HOOKS_DIR" ]]; then
    for dest in "$GIT_HOOKS_DIR"/*; do
        [[ -L "$dest" ]] || continue
        target="$(readlink "$dest")"
        if [[ "$target" == "$SRC_DIR/"* ]] && [[ ! -e "$target" ]]; then
            rm -f "$dest"
            echo "$(basename "$dest"): removed stale hook (source deleted)"
        fi
    done
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

# ── Claude Code hook registration (opt-in via --simulate-downstream) ──
#
# In "dev" mode (the default) we do NOT install the plugin's enforcement
# hooks into this repo's .claude/settings.local.json. Dev work often
# needs to edit enforcement/ and managed paths; running the hooks
# against ourselves creates circular blocks (see header comment).
#
# In "simulate-downstream" mode, we write hooks/hooks.json into
# settings.local.json so the plugin enforces against itself — useful
# for verifying that the hooks block what they should.
#
# In "strip-enforcement" mode (--no-simulate-downstream), we remove the
# hooks section from settings.local.json while preserving permissions
# and other settings — useful after previously running with
# --simulate-downstream and wanting to get dev-mode behavior back.

HOOKS_JSON="$REPO_ROOT/hooks/hooks.json"
SETTINGS_FILE="$REPO_ROOT/.claude/settings.local.json"

case "$MODE" in
    dev)
        echo "install-hooks: dev mode — skipping .claude/settings.local.json hook registration"
        echo "  (run with --simulate-downstream to enforce the plugin against itself)"
        ;;
    simulate-downstream)
        if [[ ! -f "$HOOKS_JSON" ]]; then
            echo "ERROR: $HOOKS_JSON not found; cannot simulate downstream." >&2
            exit 1
        fi
        export REPO_ROOT
        python3 - <<'PYEOF'
import json, os, sys

repo_root = os.environ.get("REPO_ROOT") or os.popen("git rev-parse --show-toplevel").read().strip()
hooks_json_path = os.path.join(repo_root, "hooks", "hooks.json")
settings_path = os.path.join(repo_root, ".claude", "settings.local.json")

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

existing = {}
if os.path.isfile(settings_path):
    with open(settings_path) as f:
        try:
            existing = json.load(f)
        except json.JSONDecodeError:
            print(f"WARNING: Could not parse {settings_path}; existing content will be replaced.", file=sys.stderr)

existing["hooks"] = new_hooks

os.makedirs(os.path.dirname(settings_path), exist_ok=True)
with open(settings_path, "w") as f:
    json.dump(existing, f, indent=2)
    f.write("\n")

print("settings.local.json: hooks section installed from hooks/hooks.json (simulate-downstream)")
PYEOF

        if python3 "$REPO_ROOT/enforcement/hooks/verify_hooks.py" --settings "$SETTINGS_FILE"; then
            echo "install-hooks: verification passed"
        else
            echo "WARNING: Hook verification failed. Check settings.local.json." >&2
        fi
        ;;
    strip-enforcement)
        export SETTINGS_FILE
        python3 - <<'PYEOF'
import json, os, sys

settings_path = os.environ["SETTINGS_FILE"]
if not os.path.isfile(settings_path):
    print(f"install-hooks: {settings_path} does not exist; nothing to strip")
    sys.exit(0)

with open(settings_path) as f:
    try:
        data = json.load(f)
    except json.JSONDecodeError:
        print(f"ERROR: Could not parse {settings_path}", file=sys.stderr)
        sys.exit(1)

had_hooks = "hooks" in data
data.pop("hooks", None)

with open(settings_path, "w") as f:
    json.dump(data, f, indent=2)
    f.write("\n")

if had_hooks:
    print(f"settings.local.json: hooks section removed (permissions and other settings preserved)")
else:
    print(f"settings.local.json: no hooks section to remove")
PYEOF
        ;;
esac
