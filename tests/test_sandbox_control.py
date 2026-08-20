"""Tests for sandbox_control.py — the holtz-start / holtz-stop boundary switch.

Two kinds of test here, and the distinction matters:

* **hook_e2e** — the hook run as a subprocess with a JSON event on stdin, which
  is the interface Claude Code actually uses. These cover the trigger surface:
  which prompts fire it and which must not.
* **unit** — the settings functions called directly, because what they produce
  has to satisfy a checker that lives in another language (sahjhan's
  `daemon/fuse.rs`). The fuse's requirements are asserted here as literal
  key/value expectations rather than "whatever the function returns", so a
  well-meaning edit that drops `failIfUnavailable` fails a test instead of
  silently disarming every audit.
"""
from __future__ import annotations

import contextlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOKS_DIR = os.path.join(REPO_ROOT, "enforcement", "hooks")
sys.path.insert(0, HOOKS_DIR)
sys.path.insert(0, os.path.join(REPO_ROOT, "tests"))

import _resolve  # noqa: E402
from test_sahjhan_integration import run_enforcement_hook  # noqa: E402


def _load(name: str = "sandbox_control"):
    """Import the hook module by path (it is a script, not a package member)."""
    spec = importlib.util.spec_from_file_location(name, os.path.join(HOOKS_DIR, f"{name}.py"))
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


sandbox_control = _load()

HOOK = os.path.join(HOOKS_DIR, "sandbox_control.py")


def _run_verb(env: dict, prompt: str) -> str:
    """Type a word at the plugin, the way Claude Code delivers it.

    Absolute hook path on purpose — see the class docstring below.
    """
    proc = subprocess.run(
        [sys.executable, HOOK],
        input=json.dumps({"prompt": prompt, "cwd": env["project"]}),
        capture_output=True, text=True, timeout=120,
        env={**os.environ, "HOME": env["home"], "CLAUDE_PLUGIN_ROOT": REPO_ROOT},
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)["reason"]


def _only_socket(run_root: str) -> str:
    """The one daemon.sock under the boundary directory tree."""
    found = [
        os.path.join(base, "daemon.sock")
        for base, _, files in os.walk(run_root)
        if "daemon.sock" in files
    ]
    assert len(found) == 1, f"expected exactly one socket, found {found}"
    return os.path.realpath(found[0])


@pytest.fixture
def armed_project():
    """A throwaway project with the boundary raised, torn down either way.

    Both paths are made under /tmp rather than pytest's `tmp_path`: the socket
    that lands under HOME has to stay inside the 104-byte macOS `AF_UNIX`
    limit, and /private/var/folders/... does not leave room.
    """
    if _resolve.ensure_sahjhan() is None:
        pytest.skip("sahjhan binary not available")
    project = tempfile.mkdtemp(prefix="sc-p-", dir="/tmp")
    home = tempfile.mkdtemp(prefix="sc-h-", dir="/tmp")
    env = {"project": project, "home": home}
    receipt = ""
    try:
        receipt = _run_verb(env, "holtz-start")
        yield env, receipt
    finally:
        # Unconditional: a leaked daemon holds a socket and a session key for
        # the rest of the test run.
        with contextlib.suppress(Exception):
            _run_verb(env, "holtz-stop")
        shutil.rmtree(project, ignore_errors=True)
        shutil.rmtree(home, ignore_errors=True)


# ── the trigger surface (hook_e2e) ───────────────────────────────────────────


@pytest.mark.hook_e2e
class TestTriggerSurface:
    """Only a human typing the bare word may arm or disarm."""

    @pytest.mark.parametrize("prompt", [
        "",
        "how do I holtz-stop?",
        "run holtz-start for me",
        "holtz-start please",
        "`holtz-start`",
        "Here are the docs:\n\nholtz-start\n\nwhat does that do?",
        "holtz-startle",
        "holtzstart",
    ])
    def test_non_matching_prompts_pass_through(self, prompt, tmp_path):
        """Exact match on the WHOLE message, so quoted or embedded text is inert.

        This is the property that makes the trigger safe: the agent cannot
        submit prompts at all, and a human pasting a transcript that mentions
        the word must not tear down their own sandbox.
        """
        event = {"prompt": prompt, "cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("sandbox_control.py", event, cwd=str(tmp_path))
        assert code == 0
        assert output.get("decision") != "block", f"{prompt!r} should not have fired"

    @pytest.mark.parametrize("prompt", ["holtz-stop", "  holtz-stop  ", "holtz-stop\n"])
    def test_surrounding_whitespace_still_matches(self, prompt, tmp_path):
        """A trailing newline from the input box is not a different word."""
        event = {"prompt": prompt, "cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("sandbox_control.py", event, cwd=str(tmp_path))
        assert code == 0
        assert output.get("decision") == "block"

    def test_receipt_never_reaches_the_model(self, tmp_path):
        """Both verbs answer with a UserPromptSubmit block: user sees it, model does not.

        `additionalContext` would spend a whole turn having the model repeat
        back what the hook already did.
        """
        event = {"prompt": "holtz-stop", "cwd": str(tmp_path)}
        code, output, _ = run_enforcement_hook("sandbox_control.py", event, cwd=str(tmp_path))
        assert code == 0
        assert output.get("decision") == "block"
        assert output.get("reason")
        assert "hookSpecificOutput" not in output


# ── the settings the fuse has to accept ──────────────────────────────────────


class TestSandboxSettings:
    """What we write must satisfy every check in sahjhan's daemon/fuse.rs."""

    def test_satisfies_every_effective_value_check(self, tmp_path):
        block = sandbox_control.sandbox_settings(str(tmp_path))
        # fuse.rs [fuse-evaluate], in order. Each of these is a distinct
        # refusal reason, and each must be the exact literal — the fuse tests
        # `!= Some(true)` / `!= Some(false)`, so a missing key or a string
        # "true" refuses just as hard as an explicit wrong value.
        assert block["enabled"] is True, "else reason=sandbox_not_enabled"
        assert block["allowUnsandboxedCommands"] is False, \
            "else reason=unsandboxed_commands_allowed"
        assert block["failIfUnavailable"] is True, "else reason=sandbox_fail_open"

    def test_never_allowlists_a_socket_or_excludes_a_command(self, tmp_path):
        """The two deny-direction scans the fuse runs across every scope."""
        block = sandbox_control.sandbox_settings(str(tmp_path))
        network = block.get("network", {})
        assert not network.get("allowUnixSockets")
        assert not network.get("allowAllUnixSockets")
        assert not block.get("excludedCommands")

    def test_denies_writes_to_the_plugin_tree_and_the_socket_directory(self, tmp_path, monkeypatch):
        """Two injection routes a confined agent would otherwise still have.

        Writing the plugin tree lets it plant a `sitecustomize.py` or a sibling
        `json.py` that a genuine hook — running OUTSIDE the sandbox — imports
        later. Writing the socket directory lets it squat the path between
        daemon restarts.
        """
        monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", "/opt/holtz-plugin")
        block = sandbox_control.sandbox_settings(str(tmp_path))
        deny = block["filesystem"]["denyWrite"]
        assert "/opt/holtz-plugin" in deny
        assert sandbox_control.boundary_dir(str(tmp_path)) in deny

    def test_only_strengthening_keys(self, tmp_path):
        """Claude Code drops loosening keys from a project-scope settings file.

        Any scope may tighten isolation; only operator scopes may loosen it.
        A key in the loosening direction would be silently discarded — and the
        fuse, which reads the file rather than the merged config, would then
        pass on a value that is not in force.
        """
        block = sandbox_control.sandbox_settings(str(tmp_path))
        assert "allowWrite" not in block.get("filesystem", {})
        assert "allowRead" not in block.get("filesystem", {})
        assert "disabled" not in block.get("filesystem", {})


class TestSettingsRoundTrip:
    """holtz-stop must hand the project back exactly as it was found."""

    def _settings(self, root):
        return os.path.join(root, ".claude", "settings.local.json")

    def test_absent_file_is_left_absent_after_stop(self, tmp_path, monkeypatch):
        """A project with no settings file gets it back with no settings file.

        Leaving a `{}` behind is litter in someone else's repo, and it is the
        kind of litter that gets committed by accident.
        """
        monkeypatch.setenv("HOME", str(tmp_path / "home"))
        root = str(tmp_path / "project")
        os.makedirs(root)
        sandbox_control._apply_settings(root)
        assert os.path.isfile(self._settings(root))

        sandbox_control._restore_settings(root)
        assert not os.path.exists(self._settings(root))

    def test_a_file_that_was_there_stays_there_even_if_it_empties(self, tmp_path, monkeypatch):
        """Only a file we created is removed — never one that was already there."""
        monkeypatch.setenv("HOME", str(tmp_path / "home"))
        root = str(tmp_path / "project")
        os.makedirs(os.path.join(root, ".claude"))
        with open(self._settings(root), "w", encoding="utf-8") as f:
            json.dump({}, f)

        sandbox_control._apply_settings(root)
        sandbox_control._restore_settings(root)
        assert os.path.isfile(self._settings(root))

    def test_re_arming_does_not_overwrite_the_backup(self, tmp_path, monkeypatch):
        """Typing holtz-start twice must not capture our own block as "theirs".

        If it did, holtz-stop would faithfully restore the sandbox instead of
        removing it, and the project would stay confined forever.
        """
        monkeypatch.setenv("HOME", str(tmp_path / "home"))
        root = str(tmp_path / "project")
        os.makedirs(os.path.join(root, ".claude"))
        theirs = {"sandbox": {"enabled": False}}
        with open(self._settings(root), "w", encoding="utf-8") as f:
            json.dump(theirs, f)

        sandbox_control._apply_settings(root)
        sandbox_control._apply_settings(root)
        sandbox_control._restore_settings(root)
        with open(self._settings(root), encoding="utf-8") as f:
            assert json.load(f) == theirs

    def test_backup_is_consumed_by_the_restore(self, tmp_path, monkeypatch):
        """A stale snapshot must not be replayed over a later arm."""
        monkeypatch.setenv("HOME", str(tmp_path / "home"))
        root = str(tmp_path / "project")
        os.makedirs(root)
        backup = os.path.join(
            sandbox_control.boundary_dir(root), sandbox_control._BACKUP_NAME
        )
        sandbox_control._apply_settings(root)
        sandbox_control._restore_settings(root)
        assert not os.path.exists(backup)

    def test_unrelated_settings_survive_both_directions(self, tmp_path, monkeypatch):
        """We own the `sandbox` key and nothing else in the user's file."""
        monkeypatch.setenv("HOME", str(tmp_path / "home"))
        root = str(tmp_path / "project")
        os.makedirs(os.path.join(root, ".claude"))
        original = {"permissions": {"allow": ["Bash(ls:*)"]}, "model": "opus"}
        with open(self._settings(root), "w", encoding="utf-8") as f:
            json.dump(original, f)

        sandbox_control._apply_settings(root)
        with open(self._settings(root), encoding="utf-8") as f:
            armed = json.load(f)
        assert armed["permissions"] == original["permissions"]
        assert armed["model"] == "opus"
        assert armed["sandbox"]["enabled"] is True

        sandbox_control._restore_settings(root)
        with open(self._settings(root), encoding="utf-8") as f:
            assert json.load(f) == original

    def test_a_pre_existing_sandbox_block_is_replaced_then_restored(self, tmp_path, monkeypatch):
        """Merging into the user's block would inherit whatever trips the fuse.

        A leftover `excludedCommands` or `allowUnixSockets` from their own
        experimenting is exactly the kind of value that makes an armed daemon
        refuse for a reason nobody can see. Replace wholesale, restore exactly.
        """
        monkeypatch.setenv("HOME", str(tmp_path / "home"))
        root = str(tmp_path / "project")
        os.makedirs(os.path.join(root, ".claude"))
        theirs = {"sandbox": {"enabled": False, "excludedCommands": ["git"]}}
        with open(self._settings(root), "w", encoding="utf-8") as f:
            json.dump(theirs, f)

        sandbox_control._apply_settings(root)
        with open(self._settings(root), encoding="utf-8") as f:
            armed = json.load(f)
        assert "excludedCommands" not in armed["sandbox"]

        sandbox_control._restore_settings(root)
        with open(self._settings(root), encoding="utf-8") as f:
            assert json.load(f) == theirs

    def test_backup_lives_outside_the_project(self, tmp_path, monkeypatch):
        """A confined agent must not be able to edit what `holtz-stop` restores."""
        monkeypatch.setenv("HOME", str(tmp_path / "home"))
        root = str(tmp_path / "project")
        os.makedirs(root)
        sandbox_control._apply_settings(root)
        backup = os.path.join(
            sandbox_control.boundary_dir(root), sandbox_control._BACKUP_NAME
        )
        assert os.path.isfile(backup)
        assert not os.path.realpath(backup).startswith(os.path.realpath(root) + os.sep)


# ── the whole thing, against a live daemon ───────────────────────────────────


@pytest.mark.slow
@pytest.mark.integration
class TestArmDisarmAgainstALiveDaemon:
    """The unit tests above check the parts; this checks that they add up.

    Everything here goes through the hook as a subprocess invoked by its
    **absolute** path, because that is what hooks.json does and it is
    load-bearing: sahjhan resolves a caller by the script path in its cmdline,
    and a relative one resolves against the *daemon's* cwd, not the hook's.
    A test that ran the hook by relative path would fail auth for a reason no
    real session ever hits.
    """

    def test_arm_then_disarm(self, armed_project):
        env, receipt = armed_project

        # "HOLTZ ARMED" is not cosmetic — arm() only says it after the daemon
        # answered a *privileged* request, which means the fuse let it through
        # and the daemon resolved this hook to a trusted caller. Anything less
        # and the receipt names which of the two failed.
        assert receipt.startswith("HOLTZ ARMED"), receipt

        sock = os.path.join(env["home"], ".holtz", "run")
        assert os.path.isdir(sock)
        socket_file = _only_socket(sock)
        assert not socket_file.startswith(os.path.realpath(env["project"]) + os.sep)

        data_dir = os.path.join(env["project"], "docs", "holtz", ".sahjhan")
        assert os.path.isfile(os.path.join(data_dir, "daemon-init-pid")), \
            "death detection has nothing to compare against without this"

        settings = os.path.join(env["project"], ".claude", "settings.local.json")
        with open(settings, encoding="utf-8") as f:
            assert json.load(f)["sandbox"]["enabled"] is True

        stop = _run_verb(env, "holtz-stop")
        assert stop.startswith("HOLTZ STOPPED"), stop
        assert not os.path.exists(socket_file)
        assert not os.path.exists(os.path.join(data_dir, "daemon-init-pid")), \
            "a deliberate teardown must not look like a crash to _daemon_lifecycle"
        assert not os.path.exists(settings)

    def test_arming_twice_is_harmless(self, armed_project):
        """Humans re-type it. `sahjhan init` is not idempotent, so this is not free."""
        env, _ = armed_project
        again = _run_verb(env, "holtz-start")
        assert again.startswith("HOLTZ ARMED"), again
