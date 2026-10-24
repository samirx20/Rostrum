"""The warning band (2d-camera SPEC §4.12): with one of a scene's own sized, not pinned layers picked that covers the
whole frame at some moment (a backdrop), each edge the frame sees past at another moment is marked on the canvas with
when it starts ("shows past the right edge from 3.2 s"; Cover the frame's move fixes it). Worked out from the document
(rostrum2d/cover.report: the layer's own turned box at every frame), once per document state, markers and layer: the
playhead never changes it, so scrubbing costs nothing here (the band rides the selection box in QML: CoverBand.qml).
A QObject part, read in QML as `backend.coverBand`.
"""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal
from rostrum2d import background as B, cover
from rostrum2d.frame import view
from rostrum2d.ops_align import SIZED


class CoverBand(QObject):
    changed = Signal()

    KEEP = 8            # the last layers' answers: picking back and forth between layers works nothing out again

    def __init__(self, bridge):
        super().__init__(bridge)
        self.b, self._key, self._rows, self._shots = bridge, None, [], (None, None, None, [])
        self._kept: list[tuple] = []                              # [(key, rows)], newest last
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
        self._key = key
        rows = next((r for k, r in self._kept if self._same(k, key)), None)
        if rows is None:
            rows = self._rows_for(layer) if layer is not None else []
            self._kept = self._kept[-(self.KEEP - 1):] + [(key, rows)]
        if rows != self._rows:
            self._rows = rows
            self.changed.emit()

    def _rows_for(self, layer: dict) -> list[dict]:
        if layer["type"] not in SIZED or layer.get("screenLock"):
            return []
        comp = self.b.placed()                                    # times in scene seconds (keys on markers placed)
        found, once = cover.report(comp, layer, self._shots_of(comp), float(comp.get("fps", 30)) or 30.0)
        return [{"edge": e["edge"], "words": cover.words(e)} for e in found] if once else []

    def _shots_of(self, comp: dict) -> list:
        """The frame at every frame of the piece, kept while the frame, the markers and the scene's size and times stay
        (most changes and every pick leave them: ~10 ms a 4 s piece, so not on each)."""
        frame = view.of(self.b.comp())
        size = tuple(comp.get(k) for k in ("fps", "duration", "width", "height"))
        times = self.b.marks.times if self.b.marks else None
        got = self._shots
        if not (got[0] is frame and got[1] is times and got[2] == size):
            self._shots = got = (frame, times, size, B.shots(comp))
        return got[3]
