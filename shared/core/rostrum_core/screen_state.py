"""What the person sees right now, for agents (`inspect_screen`, INTERACTION.md 1.18 point 7).

A window writes it whenever its selection, playhead, time range, open scene or song, focused area or view changes
(throttled by the window); an agent's server reads it. It is screen state, not a change: no history, no undo.

    <project>/.rostrum/screen-<app>.json   {"app", "item", "at" (clock time), "selection": [{id, kind, name, time?}],
                                            "playhead", "range", "scene", "focus", "view", "dragging": [ids]}

A window that closes removes its file (`clear`); a file older than STALE_S with no newer write reads as "no window".
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from .storage import write_atomic

STALE_S = 6 * 3600          # a window left open overnight still counts; a crashed one stops counting after this
KEYS = ("selection", "playhead", "range", "scene", "focus", "view", "dragging")


def path(folder, app: str) -> Path:
    return Path(folder) / ".rostrum" / f"screen-{app}.json"


def write(folder, item, app: str, state: dict) -> None:
    unknown = set(state) - set(KEYS)
    if unknown:                                  # a typo here would make agents read nothing: loud
        raise ValueError(f"screen_state.write: unknown keys {sorted(unknown)}; allowed: {KEYS}")
    write_atomic(path(folder, app), json.dumps({"app": app, "item": item, "at": time.time(), **state}, ensure_ascii=False))


def clear(folder, app: str) -> None:
    path(folder, app).unlink(missing_ok=True)


def read(folder) -> list[dict]:
    """Every window open on this project now, newest first ([] when none)."""
    out = []
    for p in (Path(folder) / ".rostrum").glob("screen-*.json"):
        try:
            s = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue                             # being written this instant: the next read sees it
        if time.time() - s.get("at", 0) <= STALE_S:
            out.append(s)
    return sorted(out, key=lambda s: -s.get("at", 0))
