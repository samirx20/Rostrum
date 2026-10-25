"""A bug in Rostrum (an exception that isn't a RostrumError), said in plain words: the ONE place it is formatted.

`said(e)` names what failed: the last step in Rostrum's own code (file, line, function), the file an OS error was
about, and the error itself, e.g. "OSError: [Errno 22] Invalid argument, on file C:\\...\\canvas.png, in
rostrum_paint/canvas.py line 332 (png)". `log(text)` keeps the whole traceback in the day's log and returns its path.
`internal(where, subject, e)` is the INTERNAL RostrumError an operation, a tool or a job answers with (never a quiet
success, never a bare "OSError" with no step or file); a screen shows its `person()` sentence, never the raw
"StopIteration: ." (the step and the traceback stay in line() and the log). `note(text)` is a developer's line on stderr that can never
fail the work it reports on.
"""
from __future__ import annotations

import sys
import time
import traceback
from pathlib import Path

from .errors import RostrumError, codes

LOG_DIR = Path.home() / ".rostrum" / "logs"
OURS = ("rostrum_core", "rostrum_paint", "rostrum_gui", "rostrum2d", "rostrum_sound", "rostrum3d", "rostrum_mcp", "screen2d")


def log(text: str) -> str:
    """Write a bug's traceback to the day's log file and return its path."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    path = LOG_DIR / f"mcp-{time.strftime('%Y%m%d')}.log"
    with path.open("a", encoding="utf-8") as f:
        f.write(f"--- {time.strftime('%H:%M:%S')}\n{text}\n")
    return str(path)


def note(text: str):
    """A developer's log line on stderr (the console; an MCP client's log). Never fails the caller: on Windows a write
    to a stderr pipe whose reader went away answers OSError [Errno 22] Invalid argument, and a line printed during a
    scene load once failed a paint.stroke batch at a random op (agents-first-time b1)."""
    try:
        print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {text}", file=sys.stderr, flush=True)
    except (OSError, ValueError):       # a closed or broken stderr: the line is lost, the work goes on
        pass


def _step(e: BaseException) -> str:
    """The last frame of the traceback in Rostrum's own code: "rostrum_paint/canvas.py line 332 (png)"."""
    frames = traceback.extract_tb(e.__traceback__)
    ours = [f for f in frames if any(f"{p}/" in f.filename.replace("\\", "/") for p in OURS)] or frames
    if not ours:
        return ""
    f = ours[-1]
    parts = Path(f.filename).parts
    short = "/".join(parts[-2:]) if len(parts) > 1 else f.filename
    return f"{short} line {f.lineno} ({f.name})"


def said(e: BaseException) -> str:
    text = f"{type(e).__name__}: {e}"
    files = [str(n) for n in (getattr(e, "filename", None), getattr(e, "filename2", None)) if n]
    if files and not all(n in str(e) for n in files):
        text += ", on file " + " and ".join(files)
    step = _step(e)
    return text + (f", in {step}" if step else "")


def internal(where: str, subject: str, e: BaseException) -> RostrumError:
    """The INTERNAL error for a bug: what failed (step, file), the traceback logged, the log named."""
    path = log("".join(traceback.format_exception(e)))
    return RostrumError(codes.INTERNAL, where, subject, f"failed: {said(e)}",
                        hint=f"A fault in Rostrum, not in the request. Full details: {path}",
                        plain=f"Something went wrong inside Rostrum, so that didn't happen (not your mistake). "
                              f"The details are in {path}")
