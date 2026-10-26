"""Tell QML only news: a part's `changed` sent only when a property it notifies reads differently than last time.

A part (a QObject whose properties QML reads, all notified by one `changed`) that relays a broad signal (the document
changed, the outline changed) made every binding on every one of its properties run again on every edit, even when
nothing it shows moved: the canvas overlays redid their handles, the rail rebuilt its tools. `relay(part)` returns the
slot to connect instead of `changed`: it reads the part's own properties (those `changed` notifies) and sends `changed`
only when one differs. A part that changes for its own reasons still sends `changed` itself; the next relay then sends
it again (what QML read in between is not known).

    bridge.outlineChanged.connect(news.relay(self))      # instead of bridge.outlineChanged.connect(self.changed)

`OnceAFrame`: what a drag's step sets off beside the dragged thing itself (the settings panel, the parts that follow
the outline) runs at most once per screen refresh, however fast the pointer moves, in the frame after the step's.
"""
from __future__ import annotations

import time

from PySide6.QtCore import QTimer

from .after_frame import AfterFrame


def _names(part, signal: str) -> list[str]:
    mo = part.metaObject()
    out = []
    for i in range(mo.propertyOffset(), mo.propertyCount()):
        p = mo.property(i)
        if p.hasNotifySignal() and bytes(p.notifySignal().name()).decode() == signal:
            out.append(p.name())
    return out


def relay(part, signal: str = "changed"):
    """The slot that sends `part.<signal>` only when a property it notifies reads differently. When the part sends it
    itself, what QML read is unknown: the next relay sends it again."""
    names, state = _names(part, signal), {"told": None, "mine": False}
    sig = getattr(part, signal)

    def own():
        if not state["mine"]:
            state["told"] = None

    def check():
        now = tuple(getattr(part, n) for n in names)
        if now != state["told"]:
            state["told"], state["mine"] = now, True
            try:
                sig.emit()
            finally:
                state["mine"] = False
    sig.connect(own)
    return check


FRAME_MS = 16          # one screen refresh


class OnceAFrame:
    """Work a drag sets off on every pointer move, run at most once per screen refresh and never in the move's own
    turn: `ask()` runs `fn` right after the next frame is on screen (after_frame.py) when it last ran a refresh ago or
    more, else once that refresh is over (the asks in between are that one run, so the last state always shows). So a
    step's frame holds only the step (the dragged thing, its picture asked), and the panel and the parts that follow
    the outline land in the frame after: run at once, they met the move's picture in one long frame (key square,
    resize: 15-25 ms). `cancel()` drops a run still waiting (the work was just done in full)."""

    def __init__(self, fn, parent):
        self._fn, self._last = fn, -1e9
        self._job = AfterFrame(self._run, parent)
        self._timer = QTimer(parent)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._job.ask)

    def ask(self):
        if self._timer.isActive() or self._job.due:
            return
        wait = FRAME_MS - (time.perf_counter() - self._last) * 1000
        if wait <= 0:
            self._job.ask()
        else:
            self._timer.start(int(wait) + 1)

    def cancel(self):
        self._timer.stop()
        self._job.cancel()

    def _run(self):
        self._last = time.perf_counter()
        self._fn()
