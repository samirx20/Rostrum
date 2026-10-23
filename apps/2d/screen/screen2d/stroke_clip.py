"""Copy and paste of picked strokes while Draw is on (UX_SPEC.md §3.8, "Select and move paint"): the screen's one
clipboard (clipboard.py), strokes under their own type, the latest copy wins. A paste is one change through the very
operations an agent calls (`paint.stroke`, `fill.add`), a little down and right of the copy. A slot mix-in for
StrokeSelect (stroke_select.py: the selection, the mapping, `_change`).
"""
from __future__ import annotations

import json
from copy import deepcopy

from PySide6.QtCore import Slot
from PySide6.QtGui import QGuiApplication
from rostrum_core.conditions import holds
from rostrum_core.errors import RostrumError, codes
from rostrum_gui import clip
from rostrum_gui.parts import SlotMixin
from rostrum_paint.fields import BRUSH

from . import stroke_geom as G

MIME = "application/x-rostrum2d-strokes"        # beside clipboard.py's layers type: one clipboard, the latest copy wins
PASTE_STEP = 24.0           # composition px: a paste lands this far down and right of the copy


def _brush_of(stroke: dict) -> dict:
    """A stroke's brush settings as `paint.stroke` takes them: only those that apply (a tip angle only when the tip does
    not follow the stroke), the kit's own rule (`valid_when`)."""
    return {p.name: stroke[p.name] for p in BRUSH if p.name in stroke and p.type not in ("id", "points")
            and holds(p.valid_when, stroke)}


class StrokeClip(SlotMixin):
    @property
    def _clip(self) -> list[dict]:
        mime = QGuiApplication.clipboard().mimeData()
        return json.loads(bytes(mime.data(MIME)).decode("utf-8")) if mime is not None and mime.hasFormat(MIME) else []

    def has_clip(self) -> bool:
        return bool(self._clip)

    @Slot()
    def copy(self):
        items = [deepcopy(self.b.doc.item(i)) | {"comp": self._comp[i]} for i in self._ids]
        clip.put({MIME: json.dumps(items).encode("utf-8")})
        self.b._key_clip = []                           # the latest copy wins over copied keys (key_edits.py)
        self.b._set_status(f"Copied {len(items)} stroke{'s' if len(items) != 1 else ''}")
        self.changed.emit()

    @Slot(result=bool)
    def paste(self):
        """The copied strokes and fills, a little down and right, on the highlighted paint layer of what the pen paints on."""
        d, clip = self._target(), self._clip
        if d is None or not clip:
            self.b._set_status("Nothing to paste here: select what the strokes go on")
            return False
        self._layer, self._place = d["id"], self.b.place_of(d["id"])
        layer, frame = self.b._paint_layers.current(), max(0, self.b.painter._n())
        calls = []
        for s in clip:
            pts = self._to_canvas(G.moved(s["comp"], PASTE_STEP, PASTE_STEP))
            if s["type"] == "fill":
                calls.append({"op": "fill.add", "target": [self._paint_for_fill(d, layer)],
                              "args": {"points": pts, "color": s["color"], "opacity": s["opacity"]}})
            else:
                calls.append({"op": "paint.stroke", "target": [d["id"]], "args": {
                    **_brush_of(s), "space": "canvas", "layer": layer, "points": pts, "frame": frame}})
        return self._change("Paste strokes", lambda: calls)

    def _paint_for_fill(self, d: dict, layer: str) -> str:
        """The paint layer a pasted fill goes on: the highlighted one, else the top unlocked one of the drawing shown."""
        f = self._frame(d)
        paints = [p for p in (f["paints"] if f else []) if not p.get("locked")]
        if layer and any(p["id"] == layer for p in paints):
            return layer
        if not paints:
            raise RostrumError(codes.NOT_FOUND, "paste", f'drawing {d["id"]}', "has no unlocked paint layer for a fill", hint="Paint a stroke first.")
        return paints[-1]["id"]

