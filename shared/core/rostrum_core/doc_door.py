"""What a document's modules share: its clock, the door every change-making method goes through, its events (see document.py)."""
from __future__ import annotations

import functools
import time
from dataclasses import dataclass
from datetime import datetime, timezone

from .history import Change


_last_t = [0.0]


def ticking() -> float:
    """The clock every document stamps its changes with: wall time, but never the same or earlier twice in a process, so
    two changes made in one tick (a document and the project's markers) still have an order for one undo (desk.py)."""
    _last_t[0] = max(time.time(), _last_t[0] + 1e-6)
    return _last_t[0]


def _through_door(fn):
    """A change-making method runs inside the document's door: with live.keep, lock + catch up + save (live.py)."""
    @functools.wraps(fn)
    def through(self, *a, **kw):
        with self._door():
            return fn(self, *a, **kw)
    return through


@dataclass
class Event:
    kind: str          # "change" | "preview" | "reset"
    change: Change | None = None
    edits: list | None = None      # a preview's: what this step changed on top of the last one (a change's are its own);
                                   # a gesture's reset: what took the shown document back to its start (None: can't tell)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
