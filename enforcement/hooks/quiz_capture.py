#!/usr/bin/env python3
"""PostToolUse courier: append staged lens-quiz questions to the vault (#73).

The generation subagent stages questions during recon by running
``skills/holtz/scripts/quiz_stage.py`` (one Bash call per question). That script
prints a canonical ``QUIZ-QUESTION:`` marker; this hook — a trusted caller that
CAN authenticate to the daemon — captures the marker from the Bash tool output
and appends the question to the ``quiz-bank`` vault key.

The hook is a *courier*, not a gatekeeper: it performs ZERO state logic. Whether
an append is allowed "only during recon" is declared in ``enforcement/vault.toml``
and enforced by the daemon (``writable_in_states = ["recon"]``). A store outside
recon simply raises, and the hook reports it. The one integrity check it does is
data hygiene, not policy: a staged question must be *answerable against the
current target source* (``verify_answer_freshness``), which forces questions to
be about real code rather than trivia — a subagent can't stage "what is 2+2".

``--finalize`` records ``quiz_bank_generated`` (the marker that gates
``recon_complete``: you cannot leave recon without a bank).
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from _common import bash_output, exit_ok, exit_warn, read_event  # noqa: E402
from lens_quiz import verify_answer_freshness  # noqa: E402
from quiz_vault import (  # noqa: E402
    append_question,
    get_run_number,
    record_bank_generated,
)

QUESTION_MARKER = "QUIZ-QUESTION:"
FINALIZE_MARKER = "QUIZ-BANK-FINALIZE:"


def main() -> None:
    event = read_event()

    # Only Bash output can carry the marker. Fast-exit everything else so the
    # hot path stays cheap.
    if event.get("tool_name") != "Bash":
        exit_ok()

    # Read stdout via the shape-tolerant helper: CC 2.x puts Bash stdout under
    # tool_response.stdout, not .output — reading .output silently dropped every
    # staged question and wedged recon_complete (#75).
    output = bash_output(event)
    if QUESTION_MARKER not in output and FINALIZE_MARKER not in output:
        exit_ok()

    cwd = event.get("cwd", os.getcwd())
    staged = 0
    problems: list[str] = []

    for raw in output.splitlines():
        line = raw.strip()
        if line.startswith(QUESTION_MARKER):
            payload = line[len(QUESTION_MARKER):].strip()
            try:
                question = json.loads(payload)
            except json.JSONDecodeError:
                problems.append("unparseable QUIZ-QUESTION marker")
                continue
            if not isinstance(question, dict):
                problems.append("QUIZ-QUESTION payload is not an object")
                continue
            # Data hygiene: only stage questions answerable against real source.
            if not verify_answer_freshness(question, cwd):
                problems.append(
                    f"dropped unverifiable question for lens "
                    f"'{question.get('lens', '?')}' (source {question.get('source', '?')})"
                )
                continue
            try:
                append_question(question, cwd)
                staged += 1
            except (OSError, RuntimeError) as exc:
                # RuntimeError here is typically the vault policy rejecting a
                # write outside recon — surface it verbatim.
                problems.append(str(exc))
        elif line.startswith(FINALIZE_MARKER):
            record_bank_generated(cwd, run=get_run_number(cwd), auditor="holtz")

    if problems:
        exit_warn(
            "Quiz staging: " + "; ".join(problems[:3]),
            "PostToolUse",
        )
    exit_ok()


if __name__ == "__main__":
    main()
