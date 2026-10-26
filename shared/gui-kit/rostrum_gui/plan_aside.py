"""A big fresh preview planned on a worker thread, so the window goes on meanwhile (the amounts popover's Repeat x4 on a
whole song: ~1.7 s of planning 14,000 new notes held the window, the box's own rows included).

Planning is pure (Gesture.plan: the drag's start state is never changed), so it runs beside the window; working out the
calls and showing the result stay on the document's thread (Gesture.fresh_calls / show_planned). One plan at a time on
one worker; a newer request makes an older result void (it is never shown). `finish()` lands the plan now, waiting for
it if needed (Enter: the change kept is the one asked for last); `drop()` lets it go (Esc, the popover closed).
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from PySide6.QtCore import QObject, Signal
from rostrum_core import RostrumError

BIG = 1000          # items a step's calls target from which it is planned aside (smaller ones: at once, ~ms)
_POOL: ThreadPoolExecutor | None = None


def _pool() -> ThreadPoolExecutor:
    global _POOL
    if _POOL is None:
        _POOL = ThreadPoolExecutor(max_workers=1, thread_name_prefix="plan-aside")
    return _POOL


def big(calls) -> bool:
    return sum(len(c.get("target") or ()) for c in calls) >= BIG


class PlanAside(QObject):
    _landed = Signal(int)           # from the worker: queued to the window's thread

    def __init__(self, parent=None):
        super().__init__(parent)
        self._gen, self._busy = 0, None
        self._landed.connect(self._on_landed)

    @property
    def busy(self) -> bool:
        return self._busy is not None

    def start(self, drag, calls, done):
        """Plan `calls` (worked out already: Drag.fresh_calls) for `drag` aside; then show them and call `done(error)`
        (None, or the RostrumError the plan raised: the last good state stays shown)."""
        self._gen += 1
        gen = self._gen
        fut = _pool().submit(drag.plan, calls)
        self._busy = (gen, fut, drag, calls, done)
        fut.add_done_callback(lambda _f: self._landed.emit(gen))

    def _on_landed(self, gen):
        if self._busy is not None and self._busy[0] == gen:
            self.finish()

    def finish(self):
        """The plan asked for last, shown now (waited for if still running). A bug in it is raised here, loudly."""
        if self._busy is None:
            return
        _gen, fut, drag, calls, done = self._busy
        self._busy = None
        try:
            planned = fut.result()
        except RostrumError as e:
            return done(e)
        if drag.closed:
            return None
        drag.show_planned(planned, calls)
        return done(None)

    def drop(self):
        self._gen += 1
        self._busy = None
