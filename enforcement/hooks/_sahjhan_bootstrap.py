#!/usr/bin/env python3
"""Sahjhan bootstrap hook — protects enforcement infrastructure.

DO NOT MODIFY. This hook protects itself.

PreToolUse hook that:
- Blocks Write/Edit to enforcement/, bin/sahjhan*, hooks/hooks.json, and this file
- Blocks Bash commands that write to protected or managed paths
- Blocks Bash commands that invoke non-allowlisted sahjhan subcommands
- Provides defense-in-depth guards for Grep/Glob tools on enforcement paths
"""
from __future__ import annotations

import json
import os
import sys

PROTECTED = [
    "enforcement/",
    "bin/sahjhan",
    "hooks/hooks.json",
    "_sahjhan_bootstrap.py",
]

# BH-001 (run 27): Sahjhan-managed files in docs/holtz/ that are rendered
# from ledger state. Direct writes (including via Bash) must be blocked.
MANAGED_DOCS = [
    "docs/holtz/STATUS.md",
    "docs/holtz/PUNCHLIST.md",
    "docs/holtz/SUMMARY.md",
    "docs/holtz/MERGE-REPORT.md",
    "docs/holtz/PUNCHLIST-MERGED.md",
]

# Issue #33: The .sahjhan data directory contains enforcement state (cache,
# ledger, active-ledger marker). Writes and deletes must be blocked.
MANAGED_DATA = [
    "docs/holtz/.sahjhan/",
]

# Combined set of all paths that must be protected from Bash writes.
ALL_PROTECTED = PROTECTED + MANAGED_DOCS + MANAGED_DATA

# Sahjhan subcommands the agent is permitted to invoke via Bash.
# Everything not listed is blocked by default (defense-in-depth).
ALLOWED_SAHJHAN_SUBCMDS = {
    "status",        # Read protocol state
    "event",         # Record standard events
    "authed-event",  # Record restricted events
    "transition",    # Advance protocol state
    "hook",          # Hook evaluation
    "manifest",      # Manifest verify
    "ledger",        # Ledger operations
    "render",        # Render STATUS.md/PUNCHLIST.md
    "daemon",        # Daemon management (start, status — NOT stop)
    "gate",          # Gate check
    "defer",         # Defer findings
    "init",          # Initialize sahjhan
    "set",           # Set perspective status, completion markers
}

# Second-level blocks: subcommand is allowed but specific sub-subcommands are not.
BLOCKED_SAHJHAN_SUBSUB: dict[str, set[str]] = {
    "daemon": {"stop"},
}

# Resolve plugin root: enforcement/hooks/ -> enforcement/ -> repo root
_PLUGIN_ROOT = os.environ.get(
    "CLAUDE_PLUGIN_ROOT",
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
)


_VALUE_FLAGS = {"--config-dir", "--data-dir", "-c"}


def _extract_sahjhan_subcmd(segment: str) -> tuple[str, str] | None:
    """Extract the sahjhan subcommand from a shell command segment.

    Skips leading wrappers (nohup, env) and flags (--config-dir X).
    Returns (subcommand, sub_subcommand) or None if not a sahjhan command.
    """
    # Strip shell redirections and trailing & for backgrounding.
    # Order matters: fd duplication first (2>&1), then fd redirections (2>/dev/null),
    # then combined redirects (&>file).  Issue #53: prior regexes left the leading
    # digit of "2>&1" behind, turning it into a ghost subcommand token.
    import re as _re
    clean = _re.sub(r'\d*>&\d+', '', segment)           # fd dup: 2>&1, 1>&2
    clean = _re.sub(r'\d*[<>]+\s*\S+', '', clean)       # fd redir: 2>/dev/null, >file, >>file, <in
    clean = _re.sub(r'&>+\s*\S+', '', clean)             # combined: &>file, &>>file
    clean = clean.rstrip('& \t')
    tokens = clean.lower().split()
    if not tokens:
        return None

    # Skip leading wrappers (nohup, env) and env var assignments (FOO=bar)
    idx = 0
    while idx < len(tokens):
        if tokens[idx] in ("nohup", "env"):
            idx += 1
        elif "=" in tokens[idx] and not tokens[idx].startswith("-"):
            # Shell env var assignment: FOO=bar, PATH=/usr/bin, etc.
            idx += 1
        else:
            break

    if idx >= len(tokens):
        return None

    # Normalize escaped/quoted command name (\\sahjhan, "sahjhan", 'sahjhan')
    # so the literal-invocation forms can't bypass the subcommand allowlist.
    cmd_token = tokens[idx]
    if cmd_token.startswith("\\"):
        cmd_token = cmd_token[1:]
    if len(cmd_token) >= 2 and cmd_token[0] == cmd_token[-1] and cmd_token[0] in ('"', "'"):
        cmd_token = cmd_token[1:-1]

    # The next token should be "sahjhan" (or end with /sahjhan)
    if cmd_token != "sahjhan" and not cmd_token.endswith("/sahjhan"):
        return None

    idx += 1

    # Skip flags before the subcommand (e.g. --config-dir /some/path).
    # Issue #53: --help / -h are not subcommands to enforce — allow through
    # by returning None (treated as "not a sahjhan command" → allowed).
    while idx < len(tokens) and tokens[idx].startswith("-"):
        flag = tokens[idx]
        if flag in ("--help", "-h", "--version"):
            return None  # help/version requests bypass enforcement
        idx += 1
        # Only value-taking flags consume the next token
        if flag in _VALUE_FLAGS and idx < len(tokens):
            idx += 1

    if idx >= len(tokens):
        # Bare "sahjhan" with no subcommand
        return ("", "")

    subcmd = tokens[idx]
    idx += 1

    # Skip flags between subcommand and sub-subcommand
    while idx < len(tokens) and tokens[idx].startswith("-"):
        flag = tokens[idx]
        idx += 1
        if flag in _VALUE_FLAGS and idx < len(tokens):
            idx += 1

    sub_subcmd = tokens[idx] if idx < len(tokens) else ""
    return (subcmd, sub_subcmd)


def _bash_references_blocked_sahjhan(command: str) -> str | None:
    """Check if a Bash command invokes a blocked sahjhan subcommand.

    Splits on shell operators (&&, ||, ;, |, newline), checks each segment.
    Returns block reason string if blocked, None if allowed.
    """
    import re

    segments = re.split(r'\s*(?:&&|\|\||[;|\n])\s*', command)

    for seg in segments:
        seg = seg.strip()
        if not seg:
            continue

        result = _extract_sahjhan_subcmd(seg)
        if result is None:
            # Not a sahjhan command — allow
            continue

        subcmd, sub_subcmd = result

        if not subcmd:
            return (
                "BLOCKED: Bare 'sahjhan' with no subcommand is not permitted. "
                f"Allowed subcommands: {', '.join(sorted(ALLOWED_SAHJHAN_SUBCMDS))}"
            )

        if subcmd not in ALLOWED_SAHJHAN_SUBCMDS:
            return (
                f"BLOCKED: 'sahjhan {subcmd}' is not permitted. "
                f"Allowed subcommands: {', '.join(sorted(ALLOWED_SAHJHAN_SUBCMDS))}"
            )

        # Check second-level blocks
        blocked_subs = BLOCKED_SAHJHAN_SUBSUB.get(subcmd)
        if blocked_subs and sub_subcmd in blocked_subs:
            return (
                f"BLOCKED: 'sahjhan {subcmd} {sub_subcmd}' is not permitted. "
                f"'{subcmd}' is allowed but '{sub_subcmd}' is blocked."
            )

    return None


def _unquote(s: str) -> str:
    """Strip surrounding single or double quotes from a shell token."""
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ('"', "'"):
        return s[1:-1]
    # Handle leading quote without closing (e.g., split mid-token)
    return s.lstrip("'\"").rstrip("'\"")


def _segment_references_protected(segment: str, protected: list[str]) -> str | None:
    """Check if any argument in a shell segment references a protected path."""
    args = segment.split()
    for arg in args:
        bare = _unquote(arg)
        for p in protected:
            if bare == p or bare.startswith(p) or ("/" + p) in bare:
                return p
    return None


def _strip_cmd_escapes(seg: str) -> str:
    """Normalize the command name at the start of a segment.

    Shell forms like ``\\cp``, ``"cp"``, and ``'cp'`` invoke the literal
    command (escaping skips alias/function lookup). This strips a single
    leading backslash and any matched quotes around the first whitespace
    token so downstream startswith / basename checks see the canonical
    name.
    """
    seg = seg.lstrip()
    if not seg:
        return seg
    if seg[0] == "\\":
        seg = seg[1:]
    if seg[:1] in ('"', "'"):
        quote = seg[0]
        end = seg.find(quote, 1)
        # Only strip if the quotes wrap the entire first token
        # (i.e., the closing quote is followed by whitespace or EOL).
        if end > 0 and (end == len(seg) - 1 or seg[end + 1].isspace()):
            seg = seg[1:end] + seg[end + 1:]
    return seg


def _cwd_is_inside_plugin(cwd: str) -> bool:
    """Return True if cwd is inside the plugin root.

    PROTECTED paths (enforcement/, hooks/hooks.json, bin/sahjhan, …) are
    plugin-relative. When an installed plugin runs against a target project,
    cwd is the target, so those names collide with unrelated directories in
    the user's own tree (many frameworks have an ``enforcement/`` or
    ``hooks/`` folder). Gate the PROTECTED substring checks on cwd actually
    being inside the plugin — the only place those paths matter.
    """
    try:
        cwd_real = os.path.realpath(cwd)
        plugin_real = os.path.realpath(_PLUGIN_ROOT)
    except (OSError, ValueError):
        return False
    return cwd_real == plugin_real or cwd_real.startswith(plugin_real + os.sep)


def _audit_terminated(cwd: str) -> bool:
    """Return True when the audit in ``cwd`` is terminated (daemon dead).

    The guard on MANAGED paths exists to stop Holtz from nuking the ledger
    mid-run. Once the daemon is dead the ledger is already unwritable — the
    primer and stop_hook both instruct the user to remove .sahjhan/ as the
    recovery step, and keeping the guard active traps them in a dead-end.
    """
    marker = os.path.join(cwd, "docs", "holtz", ".sahjhan", "terminated")
    return os.path.isfile(marker)


def _arg_contains_managed(arg: str, cwd: str, managed: list[str]) -> str | None:
    """Return a managed path name if ``arg`` resolves to an ancestor of it.

    ``rm -rf docs/holtz`` bypasses the exact-path guard on
    ``docs/holtz/.sahjhan/`` — the literal path doesn't match because the
    longer managed path doesn't start with the shorter argument. The rm
    still destroys the ledger. This helper catches that shape: an argument
    that resolves to a directory that contains a managed path on disk.

    The on-disk existence check is load-bearing — without it, a project
    with no audit at all would be blocked from ``rm -rf docs/`` because
    the literal ``docs/holtz/.sahjhan/`` path is always a logical ancestor.
    """
    arg_bare = _unquote(arg).rstrip("/")
    if not arg_bare or arg_bare in (".", ".."):
        return None
    arg_abs = arg_bare if os.path.isabs(arg_bare) else os.path.join(cwd, arg_bare)
    try:
        arg_real = os.path.realpath(arg_abs)
    except (OSError, ValueError):
        return None
    arg_boundary = arg_real.rstrip(os.sep) + os.sep
    for p in managed:
        p_rel = p.rstrip("/")
        p_abs = os.path.join(cwd, p_rel)
        if not os.path.exists(p_abs):
            continue
        try:
            p_real = os.path.realpath(p_abs)
        except (OSError, ValueError):
            continue
        if p_real == arg_real or p_real.startswith(arg_boundary):
            return p
    return None


def _check_bash_write(command: str, cwd: str | None = None) -> str | None:
    """Check if a bash command writes to any protected or managed path.

    Returns a block reason string if blocked, None if allowed.
    Splits on shell operators (&&, ||, ;, |, newline) and checks each segment.

    ``cwd`` determines whether plugin-relative PROTECTED paths are enforced:
    only when the agent is operating inside the plugin tree itself. Managed
    paths (MANAGED_DOCS, MANAGED_DATA) are always cwd-relative and always
    enforced — they live inside the target project's docs/holtz/.
    """
    import re

    # Default cwd=None preserves legacy test/dev behavior (check all paths).
    # Hook callers pass the real cwd so PROTECTED isn't enforced against
    # a target project that happens to have a same-named directory.
    if cwd is None or _cwd_is_inside_plugin(cwd):
        protected = list(ALL_PROTECTED)
        # Keep plugin integrity guards on enforcement/, hooks/hooks.json,
        # bin/sahjhan regardless of audit state — those protect the hook
        # code itself, not audit state.
        if cwd is not None and _audit_terminated(cwd):
            protected = list(PROTECTED)
    elif cwd is not None and _audit_terminated(cwd):
        # Terminated audit in a target project — the MANAGED guards exist
        # to preserve a live ledger; the ledger is already dead. Recovery
        # requires removing .sahjhan/ (per the primer's own instructions).
        protected = []
    else:
        protected = list(MANAGED_DOCS + MANAGED_DATA)

    # Issue #33: Pre-split interpreter check — python3 -c commands with
    # semicolons inside the string argument get split by the segment splitter,
    # causing the interpreter prefix and the path reference to appear in
    # different segments. Check the full command first.
    # Env var regex handles quoted values: FOO="bar baz", FOO='x y', FOO=simple
    _ENV_RE = r'''(?:(?:export\s+)?\w+=(?:"[^"]*"|'[^']*'|\S*)\s*)+'''
    cmd_stripped = _strip_cmd_escapes(re.sub(r'^' + _ENV_RE, '', command.lstrip()).strip())
    for interp in ("python ", "python3 ", "ruby ", "node ", "bash ", "sh "):
        if cmd_stripped.startswith(interp) and " -" in cmd_stripped:
            for p in protected:
                if p in command:
                    return (
                        f"BLOCKED: Bash command uses interpreter to write to protected path '{p}'. "
                        "This path cannot be modified during an audit session."
                    )

    # Split on shell operators to handle chained commands (BH-004 run 27)
    # BH-005 run 28: bare newline is a valid shell command separator — include \n
    segments = re.split(r'\s*(?:&&|\|\||[;|\n])\s*', command)

    for seg in segments:
        seg = seg.strip()
        if not seg:
            continue

        # Strip leading env var assignments (FOO=bar, FOO="x y", export X=1, etc.)
        # so that startswith-based command detection isn't bypassed.
        # Handles quoted values with spaces: FOO="bar baz", FOO='bar baz'.
        # Also normalize the command name (\\cp, "cp", 'cp' → cp) so escaped
        # or quoted invocations of cp/rm/python/etc. don't slip past detection.
        seg_cmd = _strip_cmd_escapes(re.sub(
            r'^' + _ENV_RE, '', seg,
        ).strip())

        for p in protected:
            # Redirect check: find ALL > and >> in the segment, not just first
            # BH-002 (run 27): quoted > before real redirect bypassed old check
            for op in (">>", ">"):  # check >> before > to avoid partial match
                start = 0
                while True:
                    idx = seg.find(op, start)
                    if idx < 0:
                        break
                    # Skip << (heredoc) — >> at idx means idx-1 might be >
                    if op == ">" and idx > 0 and seg[idx - 1] in "<>":
                        start = idx + 1
                        continue
                    after_op = seg[idx + len(op):].strip()
                    # Take first whitespace-delimited token as the target
                    target = _unquote(after_op.split()[0]) if after_op.split() else ""
                    if target == p or target.startswith(p):
                        return (
                            f"BLOCKED: Bash command redirects to protected path '{p}'. "
                            "This path cannot be modified during an audit session."
                        )
                    # Shell expansion ($VAR, $(cmd), `cmd`) in redirect targets
                    # defeats static path analysis. Block when the full command
                    # also references a protected path (e.g., TARGET=enforcement/...;
                    # echo > $TARGET). This catches variable-assignment-then-redirect
                    # bypasses without blocking unrelated $VAR redirects.
                    if target and ("$" in target or "`" in target) and p in command:
                        return (
                            f"BLOCKED: Bash redirect uses shell expansion near protected path '{p}'. "
                            "Redirect targets must be literal paths during an audit session."
                        )
                    start = idx + len(op)

            # tee check
            if "tee " in seg:
                tee_idx = seg.find("tee ")
                after_tee = seg[tee_idx + 4:].strip()
                if any(_unquote(arg) == p or _unquote(arg).startswith(p) for arg in after_tee.split()):
                    return (
                        f"BLOCKED: Bash command tees to protected path '{p}'. "
                        "This path cannot be modified during an audit session."
                    )

            # cp/mv/install check: protected path as target.
            # Handles both standard form (target is last arg) and -t/--target-directory
            # form where the target comes after the flag. Also handles full-path
            # commands like /bin/cp, /usr/bin/mv by extracting the basename.
            first_token = seg_cmd.split()[0] if seg_cmd.split() else ""
            cmd_basename = first_token.rsplit("/", 1)[-1] if "/" in first_token else first_token
            if any(cmd_basename == c.strip() for c in ("cp", "mv", "install")):
                args = seg_cmd.split()
                # Check -t / --target-directory flag (target is NOT last arg)
                for i, arg in enumerate(args):
                    if arg in ("-t", "--target-directory") and i + 1 < len(args):
                        target = _unquote(args[i + 1])
                        if target == p or target.startswith(p):
                            return (
                                f"BLOCKED: Bash command copies/moves to protected path '{p}'. "
                                "This path cannot be modified during an audit session."
                            )
                    if arg.startswith("--target-directory="):
                        target = _unquote(arg.split("=", 1)[1])
                        if target == p or target.startswith(p):
                            return (
                                f"BLOCKED: Bash command copies/moves to protected path '{p}'. "
                                "This path cannot be modified during an audit session."
                            )
                # Standard form: target is last argument
                if len(args) >= 3:
                    dest = _unquote(args[-1])
                    if dest == p or dest.startswith(p):
                        return (
                            f"BLOCKED: Bash command copies/moves to protected path '{p}'. "
                            "This path cannot be modified during an audit session."
                        )

            # Issue #33: rm/rmdir check — destructive operations on protected paths
            # Also match trailing-slash-stripped form so that
            # "rm -rf docs/holtz/.sahjhan" matches "docs/holtz/.sahjhan/".
            # Handle full-path commands (/bin/rm, /usr/bin/rmdir).
            if cmd_basename in ("rm", "rmdir"):
                p_stripped = p.rstrip("/")
                ref = _segment_references_protected(seg, [p, p_stripped])
                if ref:
                    return (
                        f"BLOCKED: Bash command removes protected path '{p}'. "
                        "This path cannot be deleted during an audit session."
                    )
                # Ancestor check: rm -rf docs/holtz nukes .sahjhan/ without
                # matching the literal managed path. Only check when the
                # managed path actually exists on disk (avoids false positives
                # on projects with no audit). The cwd-scoped check matches
                # MANAGED paths; PROTECTED (plugin-internal) is already
                # covered by the startswith check above.
                if cwd is not None:
                    for arg in seg.split():
                        ancestor_ref = _arg_contains_managed(
                            arg, cwd, [p] if p in MANAGED_DATA or p in MANAGED_DOCS else [],
                        )
                        if ancestor_ref:
                            return (
                                f"BLOCKED: Bash command removes a directory that contains "
                                f"'{ancestor_ref}'. Delete managed state directly after termination; "
                                "during an active audit the ledger must not be destroyed by proxy."
                            )

            # In-place modification tools: sed -i, perl -pi, patch
            for prefix in ("sed ", "perl "):
                if prefix in seg:
                    ref = _segment_references_protected(seg, [p])
                    if ref:
                        return (
                            f"BLOCKED: Bash command modifies protected path '{p}' in-place. "
                            "This path cannot be modified during an audit session."
                        )
            if "patch " in seg:
                ref = _segment_references_protected(seg, [p])
                if ref:
                    return (
                        f"BLOCKED: Bash command patches protected path '{p}'. "
                        "This path cannot be modified during an audit session."
                    )

            # BH-002 (run 27): Interpreter execution — python -c, dd, wget
            # These can write to arbitrary paths without using shell redirects.
            # Use substring match on full segment — paths may be inside quotes.
            for interp in ("python ", "python3 ", "ruby ", "node ", "bash ", "sh "):
                if seg_cmd.startswith(interp) and " -" in seg_cmd and p in seg:
                    return (
                            f"BLOCKED: Bash command uses interpreter to write to protected path '{p}'. "
                            "This path cannot be modified during an audit session."
                        )
            if seg_cmd.startswith("dd ") and ("of=" + p) in seg_cmd:
                return (
                    f"BLOCKED: Bash command uses dd to write to protected path '{p}'. "
                    "This path cannot be modified during an audit session."
                )
            if seg_cmd.startswith("wget "):
                args = seg_cmd.split()
                for i, arg in enumerate(args):
                    # BH-006 run 28: handle both -O <path> and --output-document=<path>
                    if arg == "-O" and i + 1 < len(args) and _unquote(args[i + 1]).startswith(p):
                        return (
                            f"BLOCKED: Bash command uses wget to write to protected path '{p}'. "
                            "This path cannot be modified during an audit session."
                        )
                    if arg.startswith("--output-document="):
                        target = _unquote(arg.split("=", 1)[1])
                        if target == p or target.startswith(p):
                            return (
                                f"BLOCKED: Bash command uses wget to write to protected path '{p}'. "
                                "This path cannot be modified during an audit session."
                            )
            # BH-007 run 28: curl -o / --output handler
            if seg_cmd.startswith("curl "):
                args = seg_cmd.split()
                for i, arg in enumerate(args):
                    if arg in ("-o", "--output") and i + 1 < len(args) and _unquote(args[i + 1]).startswith(p):
                        return (
                            f"BLOCKED: Bash command uses curl to write to protected path '{p}'. "
                            "This path cannot be modified during an audit session."
                        )
                    if arg.startswith("--output="):
                        target = _unquote(arg.split("=", 1)[1])
                        if target == p or target.startswith(p):
                            return (
                                f"BLOCKED: Bash command uses curl to write to protected path '{p}'. "
                                "This path cannot be modified during an audit session."
                            )

    return None


def _maybe_bootstrap_binary(command: str) -> None:
    """Trigger the binary bootstrap on a first invocation of `sahjhan …`.

    The rest of the hook chain defers `ensure_sahjhan()` until a Sahjhan
    audit is already active (primer.py, bash_guard.py, post_tool_hook.py),
    which avoids 100 MB downloads in projects that never use Holtz. That
    ordering is right for steady state but wrong for the first run: the
    skill instructs the model to invoke `sahjhan init` before any audit
    dir exists, and without the binary the command dies with
    "command not found".

    Do the bootstrap here — this hook is PreToolUse, so we run before
    Bash executes. Only fires when the user is actually typing a sahjhan
    command, so uninvolved projects still pay zero download cost.
    Failures are swallowed: if the download doesn't work (offline,
    checksum mismatch) the Bash command fails naturally with a clear
    error Claude can surface to the user.
    """
    import re as _re
    segments = _re.split(r'\s*(?:&&|\|\||[;|\n])\s*', command)
    for seg in segments:
        seg = seg.strip()
        if not seg:
            continue
        if _extract_sahjhan_subcmd(seg) is None:
            continue
        try:
            from _resolve import ensure_sahjhan  # local import keeps non-sahjhan Bash fast
            ensure_sahjhan()
        except Exception:
            pass
        return


def main() -> None:
    try:
        event = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, OSError):
        event = {}

    tool_input = event.get("tool_input", {})
    path = tool_input.get("file_path", "")
    command = tool_input.get("command", "")
    cwd = event.get("cwd", os.getcwd())
    tool_name = event.get("tool_name", "")

    # Bash tool: check for write operations and privileged daemon commands
    if command and not path:
        _maybe_bootstrap_binary(command)
        # Allowlist check for sahjhan subcommands (defense-in-depth)
        sahjhan_block = _bash_references_blocked_sahjhan(command)
        if sahjhan_block:
            _block(sahjhan_block)
            return
        result = _check_bash_write(command, cwd)
        if result:
            _block(result)
            return
        _allow()
        return

    # Grep/Glob tools: defense-in-depth write protection
    # (no read guards needed — secrets live in daemon memory, not on disk)
    if tool_name in ("Grep", "Glob") and not path:
        _allow()
        return

    if not path:
        _allow()
        return

    # Resolve both absolute and relative paths
    resolved = os.path.realpath(path) if os.path.isabs(path) else os.path.realpath(os.path.join(cwd, path))

    # Protected paths are relative to plugin root, not cwd
    for p in PROTECTED:
        full = os.path.realpath(os.path.join(_PLUGIN_ROOT, p))
        if resolved == full or resolved.startswith(full + os.sep):
            _block(
                f"BLOCKED: {path} is protected enforcement infrastructure. "
                "This file cannot be modified during an audit session."
            )
            return

    # Terminated audit → ledger dead → MANAGED guards guard nothing.
    # Skip them so the recovery path the primer advertises actually works.
    audit_is_terminated = _audit_terminated(cwd)

    # MANAGED_DOCS: sahjhan-rendered files that must not be directly written.
    # Paths are relative to cwd (same resolution as MANAGED_DATA).
    if not audit_is_terminated:
        for p in MANAGED_DOCS:
            full = os.path.realpath(os.path.join(cwd, p))
            if resolved == full:
                _block(
                    f"BLOCKED: {path} is a Sahjhan-managed document. "
                    "This file is rendered from ledger state and cannot be modified directly."
                )
                return

    # MANAGED_DATA paths are relative to cwd (not _PLUGIN_ROOT)
    if not audit_is_terminated:
        for p in MANAGED_DATA:
            full = os.path.realpath(os.path.join(cwd, p))
            if resolved == full or resolved.startswith(full + os.sep):
                _block(
                    f"BLOCKED: {path} is in the Sahjhan data directory. "
                    "This path cannot be modified during an audit session."
                )
                return

    _allow()


def _allow() -> None:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "permissionDecisionReason": "",
        },
        "suppressOutput": True,
    }))
    sys.exit(0)


def _block(reason: str) -> None:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        },
    }))
    sys.exit(0)


if __name__ == "__main__":
    main()
