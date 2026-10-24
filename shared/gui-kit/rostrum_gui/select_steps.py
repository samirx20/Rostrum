"""`selecttime <id> <id> … [n]` (any app, through layout_run.kit_step): what switching the selection costs the screen thread.

Selects each id in turn (n rounds, default 6; a number is n); per switch, the screen thread's busy ms from the select
until it is idle again (the select slot, the events it queues, the picture or sound arriving). The first round is a
warm-up and is not counted. Prints median and worst, then clears the selection.
"""
from __future__ import annotations

import statistics
import time

from PySide6.QtCore import QAbstractEventDispatcher, QCoreApplication, QEventLoop, QTimer

IDLE_MS = 150


def _wait(ms):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


class _Busy:
    """Busy ms of the screen thread: from each wake-up of its event loop to its next wait."""

    def __init__(self):
        self._d = QAbstractEventDispatcher.instance()
        self.total, self._up = 0.0, time.perf_counter()
        self._d.awake.connect(self._awake)
        self._d.aboutToBlock.connect(self._block)

    def _awake(self):
        if self._up is None:
            self._up = time.perf_counter()

    def _block(self):
        if self._up is not None:
            self.total += time.perf_counter() - self._up
            self._up = None

    def now(self) -> float:
        return (self.total + (time.perf_counter() - self._up if self._up is not None else 0.0)) * 1000

    def close(self):
        self._d.awake.disconnect(self._awake)
        self._d.aboutToBlock.disconnect(self._block)


def do(bridge, args: list[str]) -> None:
    ids = [a for a in args if not a.isdigit()]
    if not ids:
        raise ValueError("selecttime <id> <id> … [n]")
    n = int(next((a for a in args if a.isdigit()), 6))
    _wait(300)
    busy, ms = _Busy(), []
    try:
        for r in range(n + 1):
            for i in ids:
                _wait(IDLE_MS)
                b0 = busy.now()
                bridge.select(i)
                QCoreApplication.processEvents()
                _wait(IDLE_MS)
                if r:
                    ms.append(busy.now() - b0)
    finally:
        busy.close()
    bridge.select("")
    print(f"selecttime {' '.join(ids)}: {len(ms)} switches; screen thread median {statistics.median(ms):.1f}, worst {max(ms):.1f} ms")
