"""What the canvas picture shows: the document, markers and playhead the newest frame ON SCREEN was rendered from.

Everything the canvas draws over the picture from the document's geometry (the selection's outlines and handles,
the selected path's points, the onion skin's box) reads this state, never the live document: the picture comes
from the engine a little later than a change, and an overlay drawn from the live document would run ahead of it
(the box moves first, the content catches up). With one source, box and picture always move as one.
Hit-testing a press still reads the live document (the person acts on the newest truth).

Paused, the canvas shows the world picture (world_view.py: the world rectangle the view shows, at the size shown,
half that while a drag is under way so the picture keeps up; the drag's last frame, after release, is full size
again). Playing, it looks through the frame: the export at the playing size, never bigger than the well shows it
(VIEW_SCALES: the engine takes 1, 1/2 or 1/4). The same engine and scene either way (preview = export); the view
itself is screen state. The engine's queue is newest-wins (rostrum_gui.frames.PictureWorker.post_latest): no backlog.
`drag→shown` (STATS, playstats.py): from a drag's change to the frame that shows it on screen.

A slot mix-in for Bridge2D (it declares `shownChanged`).
"""
from __future__ import annotations

import time

from PySide6.QtCore import Slot
from rostrum_core.tree import index
from rostrum2d import retime

from . import bounds
from .playstats import STATS

VIEW_SCALES = (0.25, 0.5, 1.0)   # the engine's sizes, smallest first: the first one at least as big as the view shows


def view_scale(shown: float) -> float:
    """The engine's `scale` for a frame shown at `shown` device px per composition px."""
    return next((s for s in VIEW_SCALES if s >= shown - 1e-3), 1.0)


class ShownState:
    def _shown_init(self):
        self._shown = None          # (doc.data, marker times, t) of the frame on screen; None: none yet (the live state)
        self._shown_placed = None   # (key, the comp placed): worked out once per shown state
        self._shown_boxes = None    # (placed, t, {id: box or None}, every layer's in order or None): the overlays' boxes
        self._asked = {}            # id(doc.data) → when a drag made it (for drag→shown)
        self._zoom, self._view = 1.0, 1.0   # the canvas's zoom (screen px per world px) and device px per screen px

    @Slot(float, float)
    def setView(self, zoom, device_ratio):
        """The canvas's zoom changed (Stage.qml): snapping's distance follows it; the world picture is asked again by
        world_view.py when the view needs it."""
        self._zoom = max(float(zoom), 1e-6)
        self._view = max(float(device_ratio), 1.0)

    def view_zoom(self) -> float:
        return self._zoom

    def frame_tag(self):
        """What a frame about to be requested is rendered from (it comes back with the frame: _frame_shown)."""
        return (self.doc.data, self.marks.times if self.marks else None, self._t)

    def dragging(self) -> bool:
        return self._drag is not None or self._pen._drag is not None

    def frame_scale(self) -> float:
        """The engine's scale for the export while playing (looking through the frame, fitted in the well): the
        Preview size, never more than the well shows. Paused frames are world pictures (their own scale)."""
        if not self.play.playing:
            return 1.0
        comp, v = self.comp(), self._world.visible()
        fit = 1.0 if v is None else min(v["w"] / comp["width"], v["h"] / comp["height"]) * self._zoom * self._view
        return min(view_scale(fit), self.play.scale())

    def frame_extras(self) -> dict:
        """What a frame job asks for beside the frame: the world rectangle (world_view.py; None while playing), the
        paint target's place (paint_edge.py) and, playing, the frame after (playback.py `ahead`)."""
        world, place = self._world.rect(), self._paint_edge.ids()
        self._world.asked(world)
        self._paint_edge.asked(place)
        return {"world": world, "place": place, "ahead": self.play.ahead(self._t)}

    def place_of(self, layer_id: str) -> dict:
        """The layer's place at the playhead now, from the canvas's engine and the scene as the document is
        (rostrum2d/placement.py: painting's one mapping)."""
        if not self._scene:
            raise RuntimeError("the canvas can't be drawn right now, so there is nowhere to paint (see the status line)")
        return self.frames.place(self._scene, self._t, [layer_id], world=not self.play.playing)[layer_id]

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

    def shown_boxes(self, ids: list[str] | None = None) -> list[dict]:
        """bounds.boxes of the picture on screen: of the layers `ids` (in that order; those with a box), else of every
        layer. Each worked out once per picture, and only when asked: the selection box, the group outlines and the agent
        view ask on each frame for their few layers (a scrub over 60 layers worked out all 60 per picture)."""
        placed, t = self.shown_placed(), self.shown_t()
        c = self._shown_boxes
        if c is None or c[0] is not placed or c[1] != t:
            c = self._shown_boxes = (placed, t, {}, None)
        known = c[2]
        if ids is None:
            if c[3] is None:
                c = self._shown_boxes = (placed, t, known, bounds.boxes(placed, t))
                known.update({b["id"]: b for b in c[3]})
            return c[3]
        missing = {i for i in ids if i not in known}
        if missing and c[3] is None:
            got = {b["id"]: b for b in bounds.boxes(placed, t, only=missing)}
            known.update(got)
            known.update({i: None for i in missing if i not in got})     # no box at this time: not asked again
        return [known[i] for i in ids if known.get(i)]

    def shown_item(self, id_: str) -> dict | None:
        """An item of the document as the picture on screen shows it (its own times, as doc.item): None when the
        picture is older than the item."""
        if self._shown is None:
            return self.doc.item(id_) if self.doc.has(id_) else None
        found = index(self._shown[0], self.doc.kind.lists).get(id_)
        return found.item if found else None
