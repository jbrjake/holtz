"""Tests for token_profiler JSONL extraction module."""

import json
from pathlib import Path

from token_profiler.extract import (
    classify_tool_result_content,
    discover_subagents,
    extract_session,
    tool_description,
)

# ---------------------------------------------------------------------------
# Helpers to build synthetic JSONL data
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


def _user_message(content) -> dict:
    """Build a user message line."""
    return {
        "type": "user",
        "message": {"content": content},
    }


def _write_jsonl(path: Path, records: list[dict]) -> None:
    with open(path, "w") as f:
        for rec in records:
            f.write(json.dumps(rec) + "\n")


# ---------------------------------------------------------------------------
# extract_session — grouping and merging
# ---------------------------------------------------------------------------


class TestExtractSessionGrouping:
    """Groups multiple assistant chunks by requestId into a single RawTurn."""

    def test_single_request_single_chunk(self, tmp_path: Path) -> None:
        session = tmp_path / "session.jsonl"
        _write_jsonl(session, [
            _assistant_chunk(
                "req_001",
                content=[{"type": "text", "text": "Hello world"}],
                usage={
                    "input_tokens": 1000,
                    "cache_creation_input_tokens": 200,
                    "cache_read_input_tokens": 300,
                    "output_tokens": 50,
                },
                stop_reason="end_turn",
            ),
        ])
        turns = extract_session(session)
        assert len(turns) == 1
        assert turns[0].request_id == "req_001"
        assert turns[0].index == 0
        assert turns[0].assistant_text == "Hello world"
        assert turns[0].stop_reason == "end_turn"

    def test_multiple_chunks_same_request_id(self, tmp_path: Path) -> None:
        """Multiple assistant chunks with the same requestId become one RawTurn."""
        session = tmp_path / "session.jsonl"
        _write_jsonl(session, [
            _assistant_chunk(
                "req_001",
                content=[{"type": "thinking", "thinking": "Let me think..."}],
                usage={
                    "input_tokens": 1000,
                    "cache_creation_input_tokens": 200,
                    "cache_read_input_tokens": 300,
                    "output_tokens": 20,
                },
                stop_reason=None,
            ),
            _assistant_chunk(
                "req_001",
                content=[{"type": "text", "text": "The answer is 42."}],
                usage={
                    "input_tokens": 1000,
                    "cache_creation_input_tokens": 200,
                    "cache_read_input_tokens": 300,
                    "output_tokens": 50,
                },
                stop_reason="end_turn",
            ),
        ])
        turns = extract_session(session)
        assert len(turns) == 1
        assert turns[0].request_id == "req_001"
        # Content blocks merged from both chunks
        assert len(turns[0].content_blocks) == 2
        assert turns[0].content_blocks[0].type == "thinking"
        assert turns[0].content_blocks[1].type == "text"
        assert turns[0].assistant_text == "The answer is 42."

    def test_multiple_turns_sequential_indexing(self, tmp_path: Path) -> None:
        """Multiple requestIds become separate turns with correct indexing."""
        session = tmp_path / "session.jsonl"
        _write_jsonl(session, [
            _assistant_chunk(
                "req_001",
                content=[{"type": "text", "text": "First turn"}],
                usage={"input_tokens": 500, "output_tokens": 30},
                stop_reason="end_turn",
            ),
            _assistant_chunk(
                "req_002",
                content=[{"type": "text", "text": "Second turn"}],
                usage={"input_tokens": 1000, "output_tokens": 40},
                stop_reason="end_turn",
            ),
            _assistant_chunk(
                "req_003",
                content=[{"type": "text", "text": "Third turn"}],
                usage={"input_tokens": 1500, "output_tokens": 60},
                stop_reason="end_turn",
            ),
        ])
        turns = extract_session(session)
        assert len(turns) == 3
        assert [t.index for t in turns] == [0, 1, 2]
        assert [t.request_id for t in turns] == ["req_001", "req_002", "req_003"]


# ---------------------------------------------------------------------------
# extract_session — output_tokens handling (CRITICAL)
# ---------------------------------------------------------------------------


class TestOutputTokensFromFinalChunk:
    """output_tokens is CUMULATIVE — must take from the final chunk only."""

    def test_output_tokens_from_final_chunk_only(self, tmp_path: Path) -> None:
        session = tmp_path / "session.jsonl"
        _write_jsonl(session, [
            # Intermediate chunk: output_tokens=20 (partial, growing)
            _assistant_chunk(
                "req_001",
                content=[{"type": "thinking", "thinking": "thinking..."}],
                usage={
                    "input_tokens": 1000,
                    "cache_creation_input_tokens": 200,
                    "cache_read_input_tokens": 300,
                    "output_tokens": 20,
                },
                stop_reason=None,
            ),
            # Another intermediate chunk: output_tokens=35 (still partial)
            _assistant_chunk(
                "req_001",
                content=[{"type": "text", "text": "partial"}],
                usage={
                    "input_tokens": 1000,
                    "cache_creation_input_tokens": 200,
                    "cache_read_input_tokens": 300,
                    "output_tokens": 35,
                },
                stop_reason=None,
            ),
            # Final chunk: output_tokens=50 (this is the correct total)
            _assistant_chunk(
                "req_001",
                content=[{"type": "text", "text": " response"}],
                usage={
                    "input_tokens": 1000,
                    "cache_creation_input_tokens": 200,
                    "cache_read_input_tokens": 300,
                    "output_tokens": 50,
                },
                stop_reason="end_turn",
            ),
        ])
        turns = extract_session(session)
        assert len(turns) == 1
        # Must be 50 (final chunk), NOT 20+35+50=105 or any other combination
        assert turns[0].usage.output_tokens == 50

    def test_input_tokens_stable_across_chunks(self, tmp_path: Path) -> None:
        """input/cache tokens are stable across chunks — take from any (final is fine)."""
        session = tmp_path / "session.jsonl"
        _write_jsonl(session, [
            _assistant_chunk(
                "req_001",
                content=[{"type": "thinking", "thinking": "..."}],
                usage={
                    "input_tokens": 1000,
                    "cache_creation_input_tokens": 200,
                    "cache_read_input_tokens": 300,
                    "output_tokens": 10,
                },
                stop_reason=None,
            ),
            _assistant_chunk(
                "req_001",
                content=[{"type": "text", "text": "done"}],
                usage={
                    "input_tokens": 1000,
                    "cache_creation_input_tokens": 200,
                    "cache_read_input_tokens": 300,
                    "output_tokens": 40,
                },
                stop_reason="end_turn",
            ),
        ])
        turns = extract_session(session)
        assert turns[0].usage.input_tokens == 1000
        assert turns[0].usage.cache_creation_input_tokens == 200
        assert turns[0].usage.cache_read_input_tokens == 300


# ---------------------------------------------------------------------------
# extract_session — model extraction (Errata E1)
# ---------------------------------------------------------------------------


class TestModelExtraction:
    """Errata E1: Extract model from JSONL assistant message."""

    def test_model_extracted(self, tmp_path: Path) -> None:
        session = tmp_path / "session.jsonl"
        _write_jsonl(session, [
            _assistant_chunk(
                "req_001",
                content=[{"type": "text", "text": "Hello"}],
                usage={"input_tokens": 100, "output_tokens": 10},
                stop_reason="end_turn",
                model="claude-opus-4-20250514",
            ),
        ])
        turns = extract_session(session)
        assert turns[0].model == "claude-opus-4-20250514"

    def test_model_defaults_to_unknown(self, tmp_path: Path) -> None:
        session = tmp_path / "session.jsonl"
        # Simulate a message without model field
        rec = _assistant_chunk(
            "req_001",
            content=[{"type": "text", "text": "Hello"}],
            usage={"input_tokens": 100, "output_tokens": 10},
            stop_reason="end_turn",
        )
        del rec["message"]["model"]  # Remove model field
        _write_jsonl(session, [rec])
        turns = extract_session(session)
        assert turns[0].model == "unknown"


# ---------------------------------------------------------------------------
# extract_session — content blocks
# ---------------------------------------------------------------------------


class TestContentBlocks:
    """Content blocks are captured from assistant chunks."""

    def test_text_block(self, tmp_path: Path) -> None:
        session = tmp_path / "session.jsonl"
        _write_jsonl(session, [
            _assistant_chunk(
                "req_001",
                content=[{"type": "text", "text": "Some text content here"}],
                usage={"input_tokens": 100, "output_tokens": 20},
                stop_reason="end_turn",
            ),
        ])
        turns = extract_session(session)
        blocks = turns[0].content_blocks
        assert len(blocks) == 1
        assert blocks[0].type == "text"
        assert blocks[0].text_content == "Some text content here"
        assert blocks[0].size == len("Some text content here")

    def test_thinking_block(self, tmp_path: Path) -> None:
        session = tmp_path / "session.jsonl"
        _write_jsonl(session, [
            _assistant_chunk(
                "req_001",
                content=[{"type": "thinking", "thinking": "Let me reason about this..."}],
                usage={"input_tokens": 100, "output_tokens": 20},
                stop_reason="end_turn",
            ),
        ])
        turns = extract_session(session)
        blocks = turns[0].content_blocks
        assert len(blocks) == 1
        assert blocks[0].type == "thinking"
        assert blocks[0].thinking_content == "Let me reason about this..."
        assert blocks[0].size == len("Let me reason about this...")

    def test_tool_use_block_with_id(self, tmp_path: Path) -> None:
        """tool_use blocks include tool_use_id (errata E13)."""
        session = tmp_path / "session.jsonl"
        _write_jsonl(session, [
            _assistant_chunk(
                "req_001",
                content=[{
                    "type": "tool_use",
                    "id": "toolu_abc123",
                    "name": "Read",
                    "input": {"file_path": "/home/user/project/src/main.py"},
                }],
                usage={"input_tokens": 100, "output_tokens": 20},
                stop_reason="tool_use",
            ),
        ])
        turns = extract_session(session)
        blocks = turns[0].content_blocks
        assert len(blocks) == 1
        assert blocks[0].type == "tool_use"
        assert blocks[0].tool_name == "Read"
        assert blocks[0].tool_use_id == "toolu_abc123"
        assert blocks[0].tool_input_summary is not None

    def test_assistant_text_concatenation(self, tmp_path: Path) -> None:
        """assistant_text concatenates all text blocks across chunks."""
        session = tmp_path / "session.jsonl"
        _write_jsonl(session, [
            _assistant_chunk(
                "req_001",
                content=[
                    {"type": "thinking", "thinking": "reasoning"},
                    {"type": "text", "text": "First paragraph."},
                ],
                usage={"input_tokens": 100, "output_tokens": 20},
                stop_reason=None,
            ),
            _assistant_chunk(
                "req_001",
                content=[
                    {"type": "text", "text": " Second paragraph."},
                ],
                usage={"input_tokens": 100, "output_tokens": 40},
                stop_reason="end_turn",
            ),
        ])
        turns = extract_session(session)
        assert turns[0].assistant_text == "First paragraph. Second paragraph."

    def test_mixed_blocks_in_single_chunk(self, tmp_path: Path) -> None:
        """A single chunk can contain thinking + text + tool_use blocks."""
        session = tmp_path / "session.jsonl"
        _write_jsonl(session, [
            _assistant_chunk(
                "req_001",
                content=[
                    {"type": "thinking", "thinking": "Let me check"},
                    {"type": "text", "text": "I'll read the file."},
                    {"type": "tool_use", "id": "toolu_001", "name": "Read", "input": {"file_path": "/tmp/foo.py"}},
                ],
                usage={"input_tokens": 100, "output_tokens": 30},
                stop_reason="tool_use",
            ),
        ])
        turns = extract_session(session)
        blocks = turns[0].content_blocks
        assert len(blocks) == 3
        assert [b.type for b in blocks] == ["thinking", "text", "tool_use"]


# ---------------------------------------------------------------------------
# extract_session — tool results pairing
# ---------------------------------------------------------------------------


class TestToolResultsPairing:
    """Tool results from user messages are paired by tool_use_id."""

    def test_tool_result_paired(self, tmp_path: Path) -> None:
        session = tmp_path / "session.jsonl"
        _write_jsonl(session, [
            # Assistant makes a tool call
            _assistant_chunk(
                "req_001",
                content=[{
                    "type": "tool_use",
                    "id": "toolu_abc",
                    "name": "Read",
                    "input": {"file_path": "/tmp/test.py"},
                }],
                usage={"input_tokens": 100, "output_tokens": 20},
                stop_reason="tool_use",
            ),
            # User message with tool result
            _user_message([{
                "type": "tool_result",
                "tool_use_id": "toolu_abc",
                "content": "file contents here with some data",
                "is_error": False,
            }]),
            # Assistant responds after tool result
            _assistant_chunk(
                "req_002",
                content=[{"type": "text", "text": "I see the file"}],
                usage={"input_tokens": 200, "output_tokens": 30},
                stop_reason="end_turn",
            ),
        ])
        turns = extract_session(session)
        assert len(turns) == 2
        # First turn made the tool call — result should be paired there
        assert len(turns[0].tool_results) == 1
        assert turns[0].tool_results[0].tool_use_id == "toolu_abc"
        assert turns[0].tool_results[0].content_type == "text"
        assert turns[0].tool_results[0].content_size_chars == len("file contents here with some data")

    def test_multiple_tool_results_paired(self, tmp_path: Path) -> None:
        """Multiple tool calls in one turn get their results paired."""
        session = tmp_path / "session.jsonl"
        _write_jsonl(session, [
            _assistant_chunk(
                "req_001",
                content=[
                    {"type": "tool_use", "id": "toolu_001", "name": "Read", "input": {"file_path": "/tmp/a.py"}},
                    {"type": "tool_use", "id": "toolu_002", "name": "Read", "input": {"file_path": "/tmp/b.py"}},
                ],
                usage={"input_tokens": 100, "output_tokens": 20},
                stop_reason="tool_use",
            ),
            _user_message([
                {"type": "tool_result", "tool_use_id": "toolu_001", "content": "aaa", "is_error": False},
                {"type": "tool_result", "tool_use_id": "toolu_002", "content": "bbbbb", "is_error": False},
            ]),
        ])
        turns = extract_session(session)
        assert len(turns[0].tool_results) == 2
        assert turns[0].tool_results[0].tool_use_id == "toolu_001"
        assert turns[0].tool_results[0].content_size_chars == 3
        assert turns[0].tool_results[1].tool_use_id == "toolu_002"
        assert turns[0].tool_results[1].content_size_chars == 5

    def test_error_tool_result(self, tmp_path: Path) -> None:
        session = tmp_path / "session.jsonl"
        _write_jsonl(session, [
            _assistant_chunk(
                "req_001",
                content=[{
                    "type": "tool_use",
                    "id": "toolu_err",
                    "name": "Bash",
                    "input": {"command": "false"},
                }],
                usage={"input_tokens": 100, "output_tokens": 20},
                stop_reason="tool_use",
            ),
            _user_message([{
                "type": "tool_result",
                "tool_use_id": "toolu_err",
                "content": "Command failed with exit code 1",
                "is_error": True,
            }]),
        ])
        turns = extract_session(session)
        assert turns[0].tool_results[0].content_type == "error"
        assert turns[0].tool_results[0].content_size_chars == len("Command failed with exit code 1")


# ---------------------------------------------------------------------------
# extract_session — non-assistant messages skipped
# ---------------------------------------------------------------------------


class TestNonAssistantMessagesSkipped:
    """Non-assistant message types are ignored during extraction."""

    def test_progress_and_system_skipped(self, tmp_path: Path) -> None:
        session = tmp_path / "session.jsonl"
        _write_jsonl(session, [
            {"type": "system", "message": {"content": "system prompt"}},
            {"type": "progress", "data": {}},
            {"type": "file-history-snapshot", "data": {}},
            {"type": "queue-operation", "data": {}},
            _assistant_chunk(
                "req_001",
                content=[{"type": "text", "text": "Only assistant turn"}],
                usage={"input_tokens": 100, "output_tokens": 10},
                stop_reason="end_turn",
            ),
        ])
        turns = extract_session(session)
        assert len(turns) == 1
        assert turns[0].assistant_text == "Only assistant turn"


# ---------------------------------------------------------------------------
# extract_session — timestamp
# ---------------------------------------------------------------------------


class TestTimestampExtraction:
    def test_timestamp_from_first_chunk(self, tmp_path: Path) -> None:
        session = tmp_path / "session.jsonl"
        _write_jsonl(session, [
            _assistant_chunk(
                "req_001",
                content=[{"type": "text", "text": "hi"}],
                usage={"input_tokens": 100, "output_tokens": 10},
                stop_reason="end_turn",
                timestamp="2026-03-24T10:30:00Z",
            ),
        ])
        turns = extract_session(session)
        assert turns[0].timestamp == "2026-03-24T10:30:00Z"


# ---------------------------------------------------------------------------
# classify_tool_result_content
# ---------------------------------------------------------------------------


class TestClassifyToolResultContent:
    def test_text_string(self) -> None:
        ctype, csize = classify_tool_result_content("some text output")
        assert ctype == "text"
        assert csize == len("some text output")

    def test_empty_string(self) -> None:
        ctype, csize = classify_tool_result_content("")
        assert ctype == "empty"
        assert csize == 0

    def test_none(self) -> None:
        ctype, csize = classify_tool_result_content(None)
        assert ctype == "empty"
        assert csize == 0

    def test_tool_references_list(self) -> None:
        """A list containing tool_reference objects."""
        content = [
            {"type": "tool_reference", "tool_use_id": "toolu_001"},
            {"type": "tool_reference", "tool_use_id": "toolu_002"},
        ]
        ctype, csize = classify_tool_result_content(content)
        assert ctype == "tool_references"
        assert csize == 0  # tool_references have no text content to count

    def test_list_with_text_items(self) -> None:
        """A list containing text items (not tool_references)."""
        content = [
            {"type": "text", "text": "some result text here"},
        ]
        ctype, csize = classify_tool_result_content(content)
        assert ctype == "text"
        assert csize > 0

    def test_empty_list(self) -> None:
        ctype, csize = classify_tool_result_content([])
        assert ctype == "empty"
        assert csize == 0


# ---------------------------------------------------------------------------
# tool_description
# ---------------------------------------------------------------------------


class TestToolDescription:
    def test_bash_with_description(self) -> None:
        desc = tool_description("Bash", {"description": "Run unit tests", "command": "pytest tests/"})
        assert desc == "Run unit tests"

    def test_bash_no_description(self) -> None:
        desc = tool_description("Bash", {"command": "ls -la /some/path/to/file"})
        assert "ls -la" in desc
        assert len(desc) <= 80

    def test_read_file(self) -> None:
        desc = tool_description("Read", {"file_path": "/home/user/project/src/main.py"})
        assert desc == "src/main.py"

    def test_write_file(self) -> None:
        desc = tool_description("Write", {"file_path": "/home/user/project/src/utils.py"})
        assert desc == "src/utils.py"

    def test_edit_file(self) -> None:
        desc = tool_description("Edit", {"file_path": "/home/user/project/config/settings.json"})
        assert desc == "config/settings.json"

    def test_grep_pattern(self) -> None:
        desc = tool_description("Grep", {"pattern": "def main"})
        assert desc == "/def main/"

    def test_glob_pattern(self) -> None:
        desc = tool_description("Glob", {"pattern": "**/*.py"})
        assert desc == "**/*.py"

    def test_agent_with_subagent_type(self) -> None:
        desc = tool_description("Agent", {
            "description": "Review the code",
            "subagent_type": "code_review",
            "run_in_background": True,
        })
        assert "[code_review]" in desc
        assert "Review the code" in desc
        assert "(background)" in desc

    def test_agent_without_subagent_type(self) -> None:
        desc = tool_description("Agent", {"description": "Do something"})
        assert desc == "Do something"

    def test_unknown_tool(self) -> None:
        desc = tool_description("SomeNewTool", {"foo": "bar"})
        assert desc == ""

    def test_skill(self) -> None:
        desc = tool_description("Skill", {"skill": "commit"})
        assert desc == "commit"


# ---------------------------------------------------------------------------
# discover_subagents
# ---------------------------------------------------------------------------


class TestDiscoverSubagents:
    def test_finds_subagent_files(self, tmp_path: Path) -> None:
        # Create session file structure: <session-id>/subagents/*.jsonl
        session_dir = tmp_path / "abc123"
        sub_dir = session_dir / "subagents"
        sub_dir.mkdir(parents=True)

        session_file = session_dir / "abc123.jsonl"
        session_file.write_text("")

        sub1 = sub_dir / "sub1.jsonl"
        sub2 = sub_dir / "sub2.jsonl"
        sub1.write_text("")
        sub2.write_text("")

        # discover_subagents expects the session JSONL path
        # It should look for <session_dir>/subagents/*.jsonl
        result = discover_subagents(session_file)
        assert len(result) == 2
        assert all(p.suffix == ".jsonl" for p in result)
        # Should be sorted
        assert result == sorted(result)

    def test_no_subagents_dir(self, tmp_path: Path) -> None:
        session_file = tmp_path / "session.jsonl"
        session_file.write_text("")
        result = discover_subagents(session_file)
        assert result == []

    def test_empty_subagents_dir(self, tmp_path: Path) -> None:
        session_dir = tmp_path / "sess123"
        sub_dir = session_dir / "subagents"
        sub_dir.mkdir(parents=True)
        session_file = session_dir / "sess123.jsonl"
        session_file.write_text("")
        result = discover_subagents(session_file)
        assert result == []


# ---------------------------------------------------------------------------
# Integration: realistic multi-turn session
# ---------------------------------------------------------------------------


class TestRealisticSession:
    """End-to-end extraction of a realistic multi-turn session."""

    def test_full_session_extraction(self, tmp_path: Path) -> None:
        session = tmp_path / "session.jsonl"
        _write_jsonl(session, [
            # System message (skipped)
            {"type": "system", "message": {"content": "You are an assistant"}},
            # Turn 0: assistant thinks + responds
            _assistant_chunk(
                "req_001",
                content=[
                    {"type": "thinking", "thinking": "The user wants X"},
                    {"type": "text", "text": "I'll help with that."},
                    {"type": "tool_use", "id": "toolu_r1", "name": "Read", "input": {"file_path": "/project/src/app.py"}},
                ],
                usage={
                    "input_tokens": 2000,
                    "cache_creation_input_tokens": 500,
                    "cache_read_input_tokens": 1000,
                    "output_tokens": 80,
                },
                stop_reason="tool_use",
                model="claude-sonnet-4-20250514",
            ),
            # Tool result
            _user_message([{
                "type": "tool_result",
                "tool_use_id": "toolu_r1",
                "content": "def main():\n    pass\n",
                "is_error": False,
            }]),
            # Turn 1: assistant responds with multi-chunk streaming
            _assistant_chunk(
                "req_002",
                content=[{"type": "text", "text": "The file looks"}],
                usage={
                    "input_tokens": 3000,
                    "cache_creation_input_tokens": 0,
                    "cache_read_input_tokens": 2000,
                    "output_tokens": 15,
                },
                stop_reason=None,
                model="claude-sonnet-4-20250514",
            ),
            _assistant_chunk(
                "req_002",
                content=[{"type": "text", "text": " good to me."}],
                usage={
                    "input_tokens": 3000,
                    "cache_creation_input_tokens": 0,
                    "cache_read_input_tokens": 2000,
                    "output_tokens": 40,
                },
                stop_reason="end_turn",
                model="claude-sonnet-4-20250514",
            ),
        ])
        turns = extract_session(session)
        assert len(turns) == 2

        # Turn 0
        t0 = turns[0]
        assert t0.request_id == "req_001"
        assert t0.index == 0
        assert t0.model == "claude-sonnet-4-20250514"
        assert t0.usage.input_tokens == 2000
        assert t0.usage.cache_creation_input_tokens == 500
        assert t0.usage.cache_read_input_tokens == 1000
        assert t0.usage.output_tokens == 80
        assert t0.stop_reason == "tool_use"
        assert len(t0.content_blocks) == 3
        assert t0.assistant_text == "I'll help with that."
        assert len(t0.tool_results) == 1
        assert t0.tool_results[0].content_type == "text"

        # Turn 1
        t1 = turns[1]
        assert t1.request_id == "req_002"
        assert t1.index == 1
        assert t1.usage.output_tokens == 40  # from final chunk, not 15
        assert t1.assistant_text == "The file looks good to me."
        assert t1.stop_reason == "end_turn"
        assert len(t1.tool_results) == 0

    def test_user_text_messages_skipped(self, tmp_path: Path) -> None:
        """Plain user text messages (not tool results) don't affect extraction."""
        session = tmp_path / "session.jsonl"
        _write_jsonl(session, [
            _user_message("Hello, can you help me?"),
            _assistant_chunk(
                "req_001",
                content=[{"type": "text", "text": "Sure!"}],
                usage={"input_tokens": 100, "output_tokens": 10},
                stop_reason="end_turn",
            ),
            _user_message("Thanks!"),
        ])
        turns = extract_session(session)
        assert len(turns) == 1
        assert turns[0].assistant_text == "Sure!"
        assert len(turns[0].tool_results) == 0
