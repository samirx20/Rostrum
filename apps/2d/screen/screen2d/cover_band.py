"""The warning band (2d-camera SPEC §4.12): with one of a scene's own sized, not pinned layers picked that covers the
whole frame at some moment (a backdrop), each edge the frame sees past at another moment is marked on the canvas with
when it starts ("shows past the right edge from 3.2 s"; Cover the frame's move fixes it). Worked out from the document
(rostrum2d/cover.report: the layer's own turned box at every frame), once per document state, markers and layer: the
playhead never changes it, so scrubbing costs nothing here (the band rides the selection box in QML: CoverBand.qml).
Worked out off the screen's thread (every frame of the piece: ~10-20 ms of each edit to the picked layer on an 18 s
piece), once the person pauses (WAIT_MS with no new change, the pointer quiet): a run of edits or picks walks the
piece once, after the last (Python's one lock made the walk slow the screen down while it ran beside an edit). A pick
of another layer clears the band at once, an edit keeps it until the new answer comes. A layer that can never cover
the frame (cover.never_covers) is answered at once, without the walk.
A QObject part, read in QML as `backend.coverBand`.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from PySide6.QtCore import Property, QObject, QTimer, Signal
from rostrum_gui import pointer_quiet
from rostrum2d import background as B, cover
from rostrum2d.frame import view
from rostrum2d.ops_align import SIZED


class CoverBand(QObject):
    changed = Signal()
    _came = Signal(object, object)          # (key, rows) from the worker thread
    _failed = Signal(str)                   # the worker's error, said in the top bar

    KEEP = 8            # the last layers' answers: picking back and forth between layers works nothing out again
    WAIT_MS = 400       # a pause in the person's changes before the piece is walked

    def __init__(self, bridge):
        super().__init__(bridge)
        self.b, self._key, self._rows, self._shots = bridge, None, [], (None, None, None, [])
        self._kept: list[tuple] = []                              # [(key, rows)], newest last
        self._work = ThreadPoolExecutor(1, thread_name_prefix="cover-band")
        self._asked = None                                         # (key, layer) waiting for the pause
        self._pause = QTimer(self, singleShot=True, interval=self.WAIT_MS)
        self._pause.timeout.connect(self._go)
        self._came.connect(self._take)
        self._failed.connect(bridge._fail)
        for s in (bridge.selectedItemsChanged, bridge.docChanged, bridge.markersChanged):
            s.connect(self._update)

    edges = Property("QVariantList", lambda self: self._rows, notify=changed)    # [{edge, words}] of the picked layer

    @staticmethod
    def _same(a, b) -> bool:
        """The same state: the same items by identity (the document replaces what it changes), the sizes by value."""
        return all(x is y or (i == 2 and x == y) for i, (x, y) in enumerate(zip(a, b)))

    def _update(self):
        """Worked out again only when what the band reads changed: the picked layer, the frame, the scene's size and
        times, the markers. A change to any other layer leaves the band as it is (the same items, by identity)."""
        b = self.b
        ids = b.selected_layers()
        comp = b.placed()
        layer = next((l for l in comp.get("layers", []) if l["id"] == ids[0]), None) if len(ids) == 1 else None
        key = (layer, view.of(b.comp()), tuple(comp.get(k) for k in ("fps", "duration", "width", "height")),
               b.marks.times if b.marks else None)
        if self._key is not None and self._same(self._key, key):
            return
        other = self._key is None or self._key[0] is None or layer is None or self._key[0]["id"] != layer["id"]
        self._key = key
        rows = next((r for k, r in self._kept if self._same(k, key)), None)
        if rows is None and (layer is None or layer["type"] not in SIZED or layer.get("screenLock")
                             or self._never(layer)):
            rows = []
        if rows is None:                                           # worked out on the worker; meanwhile another
            self._ask(key, layer)                                  # layer shows no band, the same layer its last one
            rows = [] if other else self._rows
        self._show(rows)

    def _never(self, layer) -> bool:
        """The layer can't cover the frame at any moment (cover.never_covers), told from the frame's shots worked out
        last when they still hold: a title or a small shape is answered without waiting for the walk."""
        comp, (frame, times, size, shots) = self.b.placed(), self._shots
        now = (view.of(self.b.comp()), self.b.marks.times if self.b.marks else None,
               tuple(comp.get(k) for k in ("fps", "duration", "width", "height")))
        return frame is now[0] and times is now[1] and size == now[2] and cover.never_covers(comp, layer, shots)

    def _show(self, rows):
        if rows != self._rows:
            self._rows = rows
            self.changed.emit()

    def _ask(self, key, layer):
        self._asked = (key, layer)
        self._pause.start()

    def _go(self):
        if pointer_quiet.busy():                                   # never beside a click or a drag
            return self._pause.start()
        if self._asked is None or not self._same(self._asked[0], self._key):
            return                                                 # the state asked about is gone
        (key, layer), self._asked = self._asked, None
        comp, frame = self.b.placed(), view.of(self.b.comp())     # times in scene seconds (keys on markers placed)
        times = self.b.marks.times if self.b.marks else None
        size = tuple(comp.get(k) for k in ("fps", "duration", "width", "height"))
        shots = self._shots

        def work():
            try:
                got = shots
                if not (got[0] is frame and got[1] is times and got[2] == size):
                    got = (frame, times, size, B.shots(comp))     # the frame at every frame of the piece
                found, once = (([], False) if cover.never_covers(comp, layer, got[3])
                               else cover.report(comp, layer, got[3], float(comp.get("fps", 30)) or 30.0))
                self._came.emit((key, got), [{"edge": e["edge"], "words": cover.words(e)} for e in found] if once else [])
            except Exception as e:  # noqa: BLE001  loud: the top bar says it (a wrong band never shows quietly)
                self._failed.emit(f"Error: the frame's cover warning could not be worked out: {e}")
        self._work.submit(work)

    def _take(self, asked, rows):
        key, shots = asked
        self._shots = shots                                        # kept while the frame, markers and size stay
        self._kept = self._kept[-(self.KEEP - 1):] + [(key, rows)]
        if self._key is not None and self._same(self._key, key):  # still the state asked about
            self._show(rows)
