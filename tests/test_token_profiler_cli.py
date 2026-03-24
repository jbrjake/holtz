"""Tests for token_profiler CLI module."""

import json
import os
from pathlib import Path
from unittest import mock

from token_profiler.cli import (
    list_sessions,
    load_plugins,
    main,
    parse_args,
    resolve_session,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _assistant_chunk(
    request_id: str,
    content: list[dict],
    usage: dict | None = None,
    stop_reason: str | None = None,
    model: str = "claude-sonnet-4-20250514",
    timestamp: str | None = "2026-03-24T10:00:00Z",
) -> dict:
    """Build an assistant message line as it appears in session JSONL."""
    msg = {
        "content": content,
        "model": model,
    }
    if usage is not None:
        msg["usage"] = usage
    if stop_reason is not None:
        msg["stop_reason"] = stop_reason
    return {
        "type": "assistant",
        "requestId": request_id,
        "message": msg,
        "timestamp": timestamp,
    }


def _write_jsonl(path: Path, records: list[dict]) -> None:
    with open(path, "w") as f:
        for rec in records:
            f.write(json.dumps(rec) + "\n")


def _minimal_session(path: Path) -> None:
    """Write a minimal 2-turn session JSONL for integration tests."""
    _write_jsonl(path, [
        _assistant_chunk(
            "req_001",
            content=[{"type": "text", "text": "Hello"}],
            usage={
                "input_tokens": 1000,
                "cache_creation_input_tokens": 200,
                "cache_read_input_tokens": 300,
                "output_tokens": 50,
            },
            stop_reason="end_turn",
            timestamp="2026-03-24T10:00:00Z",
        ),
        _assistant_chunk(
            "req_002",
            content=[{"type": "text", "text": "Goodbye"}],
            usage={
                "input_tokens": 2000,
                "cache_creation_input_tokens": 100,
                "cache_read_input_tokens": 500,
                "output_tokens": 80,
            },
            stop_reason="end_turn",
            timestamp="2026-03-24T10:01:00Z",
        ),
    ])


# ---------------------------------------------------------------------------
# parse_args
# ---------------------------------------------------------------------------


class TestParseArgs:
    """parse_args should handle all spec flags."""

    def test_positional_session(self) -> None:
        args = parse_args(["/path/to/session.jsonl"])
        assert args.session == "/path/to/session.jsonl"

    def test_latest_flag(self) -> None:
        args = parse_args(["--latest"])
        assert args.latest is True

    def test_list_flag(self) -> None:
        args = parse_args(["--list"])
        assert args.list is True

    def test_project_flag(self) -> None:
        args = parse_args(["--project", "/my/project", "--latest"])
        assert args.project == "/my/project"

    def test_output_dir(self) -> None:
        args = parse_args(["-o", "/tmp/output", "--latest"])
        assert args.output == "/tmp/output"

    def test_output_dir_long(self) -> None:
        args = parse_args(["--output", "/tmp/output", "--latest"])
        assert args.output == "/tmp/output"

    def test_json_flag(self) -> None:
        args = parse_args(["--json", "--latest"])
        assert args.json is True

    def test_md_flag(self) -> None:
        args = parse_args(["--md", "--latest"])
        assert args.md is True

    def test_html_flag(self) -> None:
        args = parse_args(["--html", "--latest"])
        assert args.html is True

    def test_open_flag(self) -> None:
        args = parse_args(["--open", "--latest"])
        assert args.open is True

    def test_milestones_flag(self) -> None:
        args = parse_args(["--milestones", "milestones.json", "--latest"])
        assert args.milestones == "milestones.json"

    def test_plugin_flag_repeatable(self) -> None:
        args = parse_args(["--plugin", "a.py", "--plugin", "b.py", "--latest"])
        assert args.plugin == ["a.py", "b.py"]

    def test_no_subagents_flag(self) -> None:
        args = parse_args(["--no-subagents", "--latest"])
        assert args.no_subagents is True

    def test_pricing_flag(self) -> None:
        args = parse_args(["--pricing", "custom.json", "--latest"])
        assert args.pricing == "custom.json"

    def test_run_id_flag(self) -> None:
        args = parse_args(["--run-id", "my-run", "--latest"])
        assert args.run_id == "my-run"

    def test_defaults(self) -> None:
        args = parse_args(["--latest"])
        assert args.session is None
        assert args.list is False
        assert args.project is None
        assert args.output == "./token-profile"
        assert args.json is False
        assert args.md is False
        assert args.html is False
        assert args.open is False
        assert args.milestones is None
        assert args.plugin == []
        assert args.no_subagents is False
        assert args.pricing is None
        assert args.run_id is None


# ---------------------------------------------------------------------------
# load_plugins
# ---------------------------------------------------------------------------


class TestLoadPlugins:
    """load_plugins discovers ProfilerPlugin classes from Python files."""

    def test_empty_paths_returns_empty(self) -> None:
        result = load_plugins([])
        assert result == []

    def test_load_from_file(self, tmp_path: Path) -> None:
        plugin_file = tmp_path / "my_plugin.py"
        plugin_file.write_text(
            "class MyPlugin:\n"
            "    name = 'test'\n"
            "    def detect(self, turns): return True\n"
            "    def label_phases(self, turns): return {}\n"
            "    def name_subagent(self, turns): return None\n"
            "    def enrich_profile(self, profile): pass\n"
            "    def optimization_patterns(self): return []\n"
        )
        result = load_plugins([str(plugin_file)])
        assert len(result) == 1
        assert result[0].name == "test"

    def test_load_from_env(self, tmp_path: Path) -> None:
        plugin_file = tmp_path / "env_plugin.py"
        plugin_file.write_text(
            "class EnvPlugin:\n"
            "    name = 'env'\n"
            "    def detect(self, turns): return True\n"
            "    def label_phases(self, turns): return {}\n"
            "    def name_subagent(self, turns): return None\n"
            "    def enrich_profile(self, profile): pass\n"
            "    def optimization_patterns(self): return []\n"
        )
        with mock.patch.dict(os.environ, {"TOKEN_PROFILER_PLUGINS": str(plugin_file)}):
            result = load_plugins([], check_env=True)
        assert len(result) == 1
        assert result[0].name == "env"

    def test_env_not_checked_by_default(self, tmp_path: Path) -> None:
        plugin_file = tmp_path / "env_plugin.py"
        plugin_file.write_text(
            "class EnvPlugin:\n"
            "    name = 'env'\n"
            "    def detect(self, turns): return True\n"
            "    def label_phases(self, turns): return {}\n"
            "    def name_subagent(self, turns): return None\n"
            "    def enrich_profile(self, profile): pass\n"
            "    def optimization_patterns(self): return []\n"
        )
        with mock.patch.dict(os.environ, {"TOKEN_PROFILER_PLUGINS": str(plugin_file)}):
            result = load_plugins([], check_env=False)
        assert result == []

    def test_ignores_non_plugin_classes(self, tmp_path: Path) -> None:
        plugin_file = tmp_path / "mixed.py"
        plugin_file.write_text(
            "class NotAPlugin:\n"
            "    pass\n"
            "\n"
            "class RealPlugin:\n"
            "    name = 'real'\n"
            "    def detect(self, turns): return True\n"
            "    def label_phases(self, turns): return {}\n"
            "    def name_subagent(self, turns): return None\n"
            "    def enrich_profile(self, profile): pass\n"
            "    def optimization_patterns(self): return []\n"
        )
        result = load_plugins([str(plugin_file)])
        assert len(result) == 1
        assert result[0].name == "real"

    def test_colon_separated_env(self, tmp_path: Path) -> None:
        p1 = tmp_path / "p1.py"
        p2 = tmp_path / "p2.py"
        for i, p in enumerate([p1, p2], start=1):
            p.write_text(
                f"class Plugin{i}:\n"
                f"    name = 'p{i}'\n"
                f"    def detect(self, turns): return True\n"
                f"    def label_phases(self, turns): return {{}}\n"
                f"    def name_subagent(self, turns): return None\n"
                f"    def enrich_profile(self, profile): pass\n"
                f"    def optimization_patterns(self): return []\n"
            )
        env_val = f"{p1}:{p2}"
        with mock.patch.dict(os.environ, {"TOKEN_PROFILER_PLUGINS": env_val}):
            result = load_plugins([], check_env=True)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# list_sessions
# ---------------------------------------------------------------------------


class TestListSessions:
    """list_sessions returns metadata about available session files."""

    def test_lists_sessions(self, tmp_path: Path) -> None:
        _minimal_session(tmp_path / "session_a.jsonl")
        _minimal_session(tmp_path / "session_b.jsonl")
        result = list_sessions(tmp_path)
        assert len(result) == 2
        # Each has expected keys
        for entry in result:
            assert "path" in entry
            assert "name" in entry
            assert "size_kb" in entry
            assert "turns" in entry
            assert "started" in entry
            assert "ended" in entry

    def test_empty_dir(self, tmp_path: Path) -> None:
        result = list_sessions(tmp_path)
        assert result == []


# ---------------------------------------------------------------------------
# resolve_session
# ---------------------------------------------------------------------------


class TestResolveSession:
    """resolve_session finds the session JSONL from args."""

    def test_positional_path(self, tmp_path: Path) -> None:
        session_file = tmp_path / "mysession.jsonl"
        _minimal_session(session_file)
        args = parse_args([str(session_file)])
        result = resolve_session(args, tmp_path)
        assert result == session_file

    def test_latest_flag(self, tmp_path: Path) -> None:
        import time
        s1 = tmp_path / "old.jsonl"
        _minimal_session(s1)
        time.sleep(0.05)
        s2 = tmp_path / "new.jsonl"
        _minimal_session(s2)
        args = parse_args(["--latest"])
        result = resolve_session(args, tmp_path)
        assert result == s2

    def test_uuid_lookup(self, tmp_path: Path) -> None:
        session_file = tmp_path / "abc123-def456.jsonl"
        _minimal_session(session_file)
        args = parse_args(["abc123-def456"])
        result = resolve_session(args, tmp_path)
        assert result == session_file


# ---------------------------------------------------------------------------
# main — end-to-end integration
# ---------------------------------------------------------------------------


class TestMainEndToEnd:
    """main() orchestrates the full pipeline."""

    def test_produces_json_and_md(self, tmp_path: Path) -> None:
        session_file = tmp_path / "test-session.jsonl"
        _minimal_session(session_file)
        out_dir = tmp_path / "output"

        exit_code = main([str(session_file), "-o", str(out_dir)])

        assert exit_code == 0
        assert (out_dir / "profile.json").exists()
        assert (out_dir / "profile.md").exists()

        # Validate JSON is parseable
        with open(out_dir / "profile.json") as f:
            data = json.load(f)
        assert "run_id" in data
        assert "sessions" in data
        assert len(data["sessions"]) == 1

        # Validate markdown has expected heading
        md = (out_dir / "profile.md").read_text()
        assert "# Token Profile:" in md

    def test_json_only_flag(self, tmp_path: Path) -> None:
        session_file = tmp_path / "test-session.jsonl"
        _minimal_session(session_file)
        out_dir = tmp_path / "output"

        exit_code = main([str(session_file), "-o", str(out_dir), "--json"])

        assert exit_code == 0
        assert (out_dir / "profile.json").exists()
        assert not (out_dir / "profile.md").exists()

    def test_md_only_flag(self, tmp_path: Path) -> None:
        session_file = tmp_path / "test-session.jsonl"
        _minimal_session(session_file)
        out_dir = tmp_path / "output"

        exit_code = main([str(session_file), "-o", str(out_dir), "--md"])

        assert exit_code == 0
        assert not (out_dir / "profile.json").exists()
        assert (out_dir / "profile.md").exists()

    def test_list_flag(self, tmp_path: Path, capsys) -> None:
        _minimal_session(tmp_path / "sess1.jsonl")
        _minimal_session(tmp_path / "sess2.jsonl")

        # Mock find_project_dir to return our tmp_path
        with mock.patch("token_profiler.cli.find_project_dir", return_value=tmp_path):
            exit_code = main(["--list"])

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "sess1" in captured.out
        assert "sess2" in captured.out

    def test_no_subagents_flag(self, tmp_path: Path) -> None:
        session_dir = tmp_path / "sessions"
        session_dir.mkdir()
        session_file = session_dir / "test-session.jsonl"
        _minimal_session(session_file)

        # Create a subagent dir
        sub_dir = session_dir / "subagents"
        sub_dir.mkdir()
        _minimal_session(sub_dir / "sub1.jsonl")

        out_dir = tmp_path / "output"
        exit_code = main([str(session_file), "-o", str(out_dir), "--no-subagents"])

        assert exit_code == 0
        with open(out_dir / "profile.json") as f:
            data = json.load(f)
        # Only the main session, no subagents
        assert len(data["sessions"]) == 1

    def test_run_id_from_flag(self, tmp_path: Path) -> None:
        session_file = tmp_path / "test-session.jsonl"
        _minimal_session(session_file)
        out_dir = tmp_path / "output"

        main([str(session_file), "-o", str(out_dir), "--run-id", "my-custom-run"])

        with open(out_dir / "profile.json") as f:
            data = json.load(f)
        assert data["run_id"] == "my-custom-run"

    def test_run_id_inferred(self, tmp_path: Path) -> None:
        session_file = tmp_path / "my-session-abc.jsonl"
        _minimal_session(session_file)
        out_dir = tmp_path / "output"

        main([str(session_file), "-o", str(out_dir)])

        with open(out_dir / "profile.json") as f:
            data = json.load(f)
        assert data["run_id"] == "my-session-abc"

    def test_milestones_flag(self, tmp_path: Path) -> None:
        session_file = tmp_path / "test-session.jsonl"
        _minimal_session(session_file)
        milestones_file = tmp_path / "milestones.json"
        milestones_file.write_text(json.dumps([
            {"label": "recon", "start": 0, "end": 0},
            {"label": "execute", "start": 1, "end": 1},
        ]))
        out_dir = tmp_path / "output"

        main([str(session_file), "-o", str(out_dir), "--milestones", str(milestones_file)])

        with open(out_dir / "profile.json") as f:
            data = json.load(f)
        phases = data["sessions"][0]["phases"]
        phase_names = [p["phase"] for p in phases]
        assert "recon" in phase_names
        assert "execute" in phase_names
