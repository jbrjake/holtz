"""Tests for the commit-msg git hook version bumping logic."""

import json
import subprocess
from pathlib import Path

HOOK_PATH = Path(__file__).parent.parent / "git-hooks" / "commit-msg"


def _setup_git_repo(tmp_path: Path, version: str = "0.4.0") -> Path:
    """Create a minimal git repo with plugin.json and the commit-msg hook installed."""
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "test@test.com"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "Test"], check=True, capture_output=True)

    # Create plugin.json
    plugin_dir = tmp_path / ".claude-plugin"
    plugin_dir.mkdir()
    plugin_json = plugin_dir / "plugin.json"
    plugin_json.write_text(json.dumps({"name": "test", "version": version}, indent=2) + "\n")

    # Install our hook
    hooks_dir = tmp_path / ".git" / "hooks"
    hooks_dir.mkdir(exist_ok=True)
    hook_dest = hooks_dir / "commit-msg"
    hook_dest.symlink_to(HOOK_PATH.resolve())

    # Initial commit (without hook — use a no-bump prefix)
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "commit", "-m", "chore: initial commit"],
        check=True,
        capture_output=True,
    )

    return tmp_path


def _make_commit(repo: Path, msg: str, touch_file: str = "dummy.txt", body: str = "") -> subprocess.CompletedProcess:
    """Create a file and commit with the given message. Returns the completed process."""
    dummy = repo / touch_file
    dummy.write_text(msg)
    subprocess.run(["git", "-C", str(repo), "add", touch_file], check=True, capture_output=True)
    cmd = ["git", "-C", str(repo), "commit", "-m", msg]
    if body:
        cmd.extend(["-m", body])
    return subprocess.run(cmd, capture_output=True, text=True)


def _get_version(repo: Path) -> str:
    """Read the current version from plugin.json."""
    plugin_json = repo / ".claude-plugin" / "plugin.json"
    return json.loads(plugin_json.read_text())["version"]


class TestMinorBump:
    def test_feat_bumps_minor(self, tmp_path: Path) -> None:
        repo = _setup_git_repo(tmp_path, "0.4.0")
        result = _make_commit(repo, "feat: add new feature", "a.txt")
        assert result.returncode == 0
        assert _get_version(repo) == "0.5.0"

    def test_feat_with_scope_bumps_minor(self, tmp_path: Path) -> None:
        repo = _setup_git_repo(tmp_path, "0.4.0")
        result = _make_commit(repo, "feat(auth): add login", "a.txt")
        assert result.returncode == 0
        assert _get_version(repo) == "0.5.0"


class TestPatchBump:
    def test_fix_bumps_patch(self, tmp_path: Path) -> None:
        repo = _setup_git_repo(tmp_path, "0.5.0")
        result = _make_commit(repo, "fix: resolve crash", "a.txt")
        assert result.returncode == 0
        assert _get_version(repo) == "0.5.1"

    def test_perf_bumps_patch(self, tmp_path: Path) -> None:
        repo = _setup_git_repo(tmp_path, "0.5.0")
        result = _make_commit(repo, "perf: optimize query", "a.txt")
        assert result.returncode == 0
        assert _get_version(repo) == "0.5.1"

    def test_fix_with_scope_bumps_patch(self, tmp_path: Path) -> None:
        repo = _setup_git_repo(tmp_path, "1.2.3")
        result = _make_commit(repo, "fix(parser): handle edge case", "a.txt")
        assert result.returncode == 0
        assert _get_version(repo) == "1.2.4"


class TestMajorBump:
    def test_feat_bang_bumps_major(self, tmp_path: Path) -> None:
        repo = _setup_git_repo(tmp_path, "1.2.3")
        result = _make_commit(repo, "feat!: redesign API", "a.txt")
        assert result.returncode == 0
        assert _get_version(repo) == "2.0.0"

    def test_fix_bang_bumps_major(self, tmp_path: Path) -> None:
        repo = _setup_git_repo(tmp_path, "1.2.3")
        result = _make_commit(repo, "fix!: breaking change in error format", "a.txt")
        assert result.returncode == 0
        assert _get_version(repo) == "2.0.0"

    def test_breaking_change_in_body_bumps_major(self, tmp_path: Path) -> None:
        repo = _setup_git_repo(tmp_path, "1.2.3")
        result = _make_commit(repo, "feat: add new API", "a.txt", body="BREAKING CHANGE: removes old endpoint")
        assert result.returncode == 0
        assert _get_version(repo) == "2.0.0"


class TestNoBump:
    def test_docs_no_bump(self, tmp_path: Path) -> None:
        repo = _setup_git_repo(tmp_path, "0.4.0")
        result = _make_commit(repo, "docs: update README", "a.txt")
        assert result.returncode == 0
        assert _get_version(repo) == "0.4.0"

    def test_chore_no_bump(self, tmp_path: Path) -> None:
        repo = _setup_git_repo(tmp_path, "0.4.0")
        result = _make_commit(repo, "chore: clean up deps", "a.txt")
        assert result.returncode == 0
        assert _get_version(repo) == "0.4.0"

    def test_refactor_no_bump(self, tmp_path: Path) -> None:
        repo = _setup_git_repo(tmp_path, "0.4.0")
        result = _make_commit(repo, "refactor: simplify logic", "a.txt")
        assert result.returncode == 0
        assert _get_version(repo) == "0.4.0"

    def test_test_no_bump(self, tmp_path: Path) -> None:
        repo = _setup_git_repo(tmp_path, "0.4.0")
        result = _make_commit(repo, "test: add coverage", "a.txt")
        assert result.returncode == 0
        assert _get_version(repo) == "0.4.0"

    def test_ci_no_bump(self, tmp_path: Path) -> None:
        repo = _setup_git_repo(tmp_path, "0.4.0")
        result = _make_commit(repo, "ci: update workflow", "a.txt")
        assert result.returncode == 0
        assert _get_version(repo) == "0.4.0"

    def test_style_no_bump(self, tmp_path: Path) -> None:
        repo = _setup_git_repo(tmp_path, "0.4.0")
        result = _make_commit(repo, "style: format code", "a.txt")
        assert result.returncode == 0
        assert _get_version(repo) == "0.4.0"

    def test_merge_commit_no_bump(self, tmp_path: Path) -> None:
        repo = _setup_git_repo(tmp_path, "0.4.0")
        result = _make_commit(repo, "Merge branch 'feature/foo' into dev", "a.txt")
        assert result.returncode == 0
        assert _get_version(repo) == "0.4.0"

    def test_non_conventional_no_bump(self, tmp_path: Path) -> None:
        repo = _setup_git_repo(tmp_path, "0.4.0")
        result = _make_commit(repo, "random commit message", "a.txt")
        assert result.returncode == 0
        assert _get_version(repo) == "0.4.0"


class TestCumulativeBumping:
    def test_feat_then_fix_then_feat(self, tmp_path: Path) -> None:
        repo = _setup_git_repo(tmp_path, "0.4.0")
        _make_commit(repo, "feat: first feature", "a.txt")
        assert _get_version(repo) == "0.5.0"
        _make_commit(repo, "fix: a fix", "b.txt")
        assert _get_version(repo) == "0.5.1"
        _make_commit(repo, "feat: second feature", "c.txt")
        assert _get_version(repo) == "0.6.0"


class TestGuards:
    def test_skips_if_plugin_json_already_modified(self, tmp_path: Path) -> None:
        repo = _setup_git_repo(tmp_path, "0.4.0")
        # Modify plugin.json without staging it
        plugin_json = repo / ".claude-plugin" / "plugin.json"
        data = json.loads(plugin_json.read_text())
        data["version"] = "1.0.0"
        plugin_json.write_text(json.dumps(data, indent=2) + "\n")
        # Now make a feat commit — hook should skip, version stays at manual edit
        result = _make_commit(repo, "feat: should not auto-bump", "a.txt")
        assert result.returncode == 0
        assert _get_version(repo) == "1.0.0"
