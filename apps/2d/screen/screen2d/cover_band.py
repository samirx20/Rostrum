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

    def __init__(self, bridge):
        super().__init__(bridge)
        self.b, self._key, self._rows, self._shots = bridge, None, [], (None, None, None, [])
        for s in (bridge.selectedItemsChanged, bridge.docChanged, bridge.markersChanged):
            s.connect(self._update)

    edges = Property("QVariantList", lambda self: self._rows, notify=changed)    # [{edge, words}] of the picked layer

    def _update(self):
        b = self.b
        ids = b.selected_layers()
        key = (b.doc.data, b.marks.times if b.marks else None, tuple(ids))
        if self._key is not None and self._key[0] is key[0] and self._key[1] is key[1] and self._key[2] == key[2]:
            return
        self._key = key
        rows = self._rows_for(ids[0]) if len(ids) == 1 else []
        if rows != self._rows:
            self._rows = rows
            self.changed.emit()

    def _rows_for(self, id_: str) -> list[dict]:
        doc = self.b.doc
        if not doc.has(id_) or doc.item(doc.parent_of(id_)[0])["type"] != "comp":
            return []
        comp = self.b.placed()                                    # times in scene seconds (keys on markers placed)
        layer = next((l for l in comp.get("layers", []) if l["id"] == id_), None)
        if layer is None or layer["type"] not in SIZED or layer.get("screenLock"):
            return []
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
