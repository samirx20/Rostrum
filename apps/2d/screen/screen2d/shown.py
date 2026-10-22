"""What the canvas picture shows: the document, markers and playhead the newest frame ON SCREEN was rendered from.

Everything the canvas draws over the picture from the document's geometry (the selection's outlines and handles,
the selected path's points, the onion skin's box) reads this state, never the live document: the picture comes
from the engine a little later than a change, and an overlay drawn from the live document would run ahead of it
(the box moves first, the content catches up). With one source, box and picture always move as one.
Hit-testing a press still reads the live document (the person acts on the newest truth).

While a drag is under way (a layer, a handle, a point, a key or a bar), frames are drawn at half size so the picture
keeps up; the drag's last frame, after release, is full size again. The canvas's zoom (Stage.qml's one mapping, sent with
setView) caps the size too: the engine draws the frame at the size it is shown, up to Full (VIEW_SCALES: the engine
takes 1, 1/2 or 1/4), so the fit view doesn't draw more than it shows; past Full the visible part is drawn again at the
size shown (sharp.py), so 400 % is sharp, never Full enlarged. The same engine and scene either way (preview = export); the view itself is screen state. The engine's queue is newest-wins
(rostrum_gui.frames.PictureWorker.post_latest): no backlog.
`drag→shown` (STATS, playstats.py): from a drag's change to the frame that shows it on screen.

A slot mix-in for Bridge2D (it declares `shownChanged`).
"""
from __future__ import annotations

import time

from PySide6.QtCore import Slot
from rostrum_core.tree import index
from rostrum2d import retime

from .playstats import STATS

DRAG_SCALE = 0.5           # the engine's `scale` while dragging
VIEW_SCALES = (0.25, 0.5, 1.0)   # the engine's sizes, smallest first: the first one at least as big as the view shows


def view_scale(shown: float) -> float:
    """The engine's `scale` for a frame shown at `shown` device px per composition px."""
    return next((s for s in VIEW_SCALES if s >= shown - 1e-3), 1.0)


class ShownState:
    def _shown_init(self):
        self._shown = None          # (doc.data, marker times, t) of the frame on screen; None: none yet (the live state)
        self._shown_placed = None   # (key, the comp placed): worked out once per shown state
        self._asked = {}            # id(doc.data) → when a drag made it (for drag→shown)
        self._zoom, self._view = 1.0, 1.0   # the canvas's zoom (screen px per composition px) and its engine scale

    @Slot(float, float)
    def setView(self, zoom, device_ratio):
        """The canvas's zoom changed (Stage.qml): snapping's distance follows it; the next frame is drawn at the size
        shown (redrawn now only when that size changes)."""
        self._zoom = max(float(zoom), 1e-6)
        scale = view_scale(self._zoom * max(float(device_ratio), 1.0))
        if scale != self._view:
            self._view = scale
            self._show()

    def view_zoom(self) -> float:
        return self._zoom

    def frame_tag(self):
        """What a frame about to be requested is rendered from (it comes back with the frame: _frame_shown)."""
        return (self.doc.data, self.marks.times if self.marks else None, self._t)

    def dragging(self) -> bool:
        return self._drag is not None or self._pen._drag is not None

    def frame_scale(self) -> float:
        """The engine's scale for the next frame: Preview size while playing, half while dragging, else full; never
        more than the canvas shows."""
        return min(self._view, DRAG_SCALE if self.dragging() and not self.play.playing else self.play.scale())

    def frame_extras(self) -> dict:
        """What a frame job asks for beside the frame: the sharp crop (sharp.py) and the paint target's place
        (paint_edge.py)."""
        crop, place = self._sharp.crop(), self._paint_edge.ids()
        self._sharp.asked(crop)
        self._paint_edge.asked(place)
        return {"crop": crop, "place": place}

    def place_of(self, layer_id: str) -> dict:
        """The layer's place at the playhead now, from the canvas's engine and the scene as the document is
        (rostrum2d/placement.py: painting's one mapping)."""
        if not self._scene:
            raise RuntimeError("the canvas can't be drawn right now, so there is nowhere to paint (see the status line)")
        return self.frames.place(self._scene, self._t, [layer_id])[layer_id]

    def _note_change(self):
        """A document change: remember when, while dragging (for drag→shown)."""
        if STATS.on and self.dragging():
            self._asked[id(self.doc.data)] = time.perf_counter()

    def _frame_shown(self, tag):
        """The frame rendered from `tag` is the one on screen now: the overlays follow it."""
        self._shown = tag
        at = self._asked.pop(id(tag[0]), None)
        if at is not None:
            STATS.ms["drag→shown"].append((time.perf_counter() - at) * 1000)
            if not self.dragging():
                self._asked.clear()
        if not self.play.playing:              # the overlays are hidden while playing; they catch up when it stops
            self.shownChanged.emit()

    def shown_t(self) -> float:
        return self._t if self._shown is None else self._shown[2]

    def shown_placed(self) -> dict:
        """The composition as the picture on screen shows it (as placed(): every time in composition seconds)."""
        if self._shown is None:
            return self.placed()
        data, times, _ = self._shown
        if self._shown_placed is None or self._shown_placed[0] is not self._shown:
            comp = index(data, self.doc.kind.lists).get(self.comp_id)
            if comp is None:
                return self.placed()
            self._shown_placed = (self._shown, retime.timed(comp.item, self.times(), comp.item["fps"]))
        return self._shown_placed[1]

    def shown_item(self, id_: str) -> dict | None:
        """An item of the document as the picture on screen shows it (its own times, as doc.item): None when the
        picture is older than the item."""
        if self._shown is None:
            return self.doc.item(id_) if self.doc.has(id_) else None
        found = index(self._shown[0], self.doc.kind.lists).get(id_)
        return found.item if found else None
