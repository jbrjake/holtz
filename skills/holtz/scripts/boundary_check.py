#!/usr/bin/env python3
"""Report whether this shell is on the outside of the audit boundary.

Run from the agent's Bash at the top of recon. Prints one line and exits 0
only when the boundary is real:

    BOUNDARY: confined    — the socket is there and this shell cannot reach it
    BOUNDARY: exposed     — this shell CAN reach the daemon; nothing is confined
    BOUNDARY: no-daemon   — nothing is listening; holtz-start has not run

This probes the fact itself — can this process open the daemon socket — rather
than a proxy for it. The obvious proxy, `CLAUDE_CODE_SANDBOXED`, does not work:
in Claude Code 2.1.237 that variable is an *input* the launcher reads (to skip
the trust dialog when Claude Code itself runs containerized), and nothing sets
it in a sandboxed command's environment. A probe that trusted it would report
`exposed` inside a perfectly good sandbox.

Connecting is also the honest test in the other direction. The security does
not rest on this script: sahjhan's fuse refuses to serve without the boundary,
and holtz's hooks fail closed on that refusal, so an audit cannot proceed
un-confined even if this output is ignored. What this buys is a clear message
at step 0 instead of a puzzling block twenty commands later.
"""
from __future__ import annotations

import os
import socket
import sys

_HOOKS = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
    "enforcement", "hooks",
)
sys.path.insert(0, _HOOKS)

from _common import _get_daemon_socket_path  # noqa: E402

CONFINED = "BOUNDARY: confined"
EXPOSED = "BOUNDARY: exposed"
NO_DAEMON = "BOUNDARY: no-daemon"


def probe(sock_path: str) -> str:
    """Classify what a connect() to the daemon socket does from here."""
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(5)
    try:
        sock.connect(sock_path)
    except PermissionError:
        # The sandbox denied the syscall: macOS Seatbelt answers EPERM, and
        # Linux's seccomp filter blocks socket(AF_UNIX) outright. Either way
        # the process was stopped from reaching a socket that exists.
        return CONFINED
    except (FileNotFoundError, ConnectionRefusedError):
        return NO_DAEMON
    except OSError:
        # Anything else the kernel says about this path is not evidence of
        # confinement, and claiming confinement on an unknown error is the one
        # mistake that matters here.
        return NO_DAEMON
    else:
        return EXPOSED
    finally:
        sock.close()


def main() -> int:
    sock_path = _get_daemon_socket_path(os.getcwd())
    verdict = probe(sock_path)
    print(f"{verdict}  (socket: {sock_path})")
    if verdict == CONFINED:
        return 0
    if verdict == EXPOSED:
        print(
            "This shell can reach the daemon, so the quiz and the enforcement "
            "state are not protected from it. Tell the user to type "
            "holtz-start (the bare word, on its own line) and stop.",
            file=sys.stderr,
        )
    else:
        print(
            "No daemon is listening. Tell the user to type holtz-start (the "
            "bare word, on its own line) and stop.",
            file=sys.stderr,
        )
    return 1


if __name__ == "__main__":
    sys.exit(main())
