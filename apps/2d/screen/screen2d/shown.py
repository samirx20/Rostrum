"""What the canvas picture shows: the document, markers and playhead the newest frame ON SCREEN was rendered from.

Everything the canvas draws over the picture from the document's geometry (the selection's outlines and handles,
the selected path's points, the onion skin's box) reads this state, never the live document: the picture comes
from the engine a little later than a change, and an overlay drawn from the live document would run ahead of it
(the box moves first, the content catches up). With one source, box and picture always move as one.
Hit-testing a press still reads the live document (the person acts on the newest truth).

While a drag is under way (a layer, a handle, a point, a key or a bar), frames are drawn at half size so the picture
keeps up; the drag's last frame, after release, is full size again. The engine's queue is newest-wins
(rostrum_gui.frames.PictureWorker.post_latest): no backlog.
`drag→shown` (STATS, playstats.py): from a drag's change to the frame that shows it on screen.

A slot mix-in for Bridge2D (it declares `shownChanged`).
"""
from __future__ import annotations

import time

from rostrum_core.tree import index
from rostrum2d import retime

from .playstats import STATS

DRAG_SCALE = 0.5           # the engine's `scale` while dragging


class ShownState:
    def _shown_init(self):
        self._shown = None          # (doc.data, marker times, t) of the frame on screen; None: none yet (the live state)
        self._shown_placed = None   # (key, the comp placed): worked out once per shown state
        self._asked = {}            # id(doc.data) → when a drag made it (for drag→shown)

    def frame_tag(self):
        """What a frame about to be requested is rendered from (it comes back with the frame: _frame_shown)."""
        return (self.doc.data, self.marks.times if self.marks else None, self._t)

    def dragging(self) -> bool:
        return self._drag is not None or self._pen._drag is not None

    def frame_scale(self) -> float:
        """The engine's scale for the next frame: Preview size while playing, half while dragging, else full."""
        return DRAG_SCALE if self.dragging() and not self.play.playing else self.play.scale()

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
