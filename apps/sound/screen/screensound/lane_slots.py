"""Automation lanes under a track's row: open one, press / drag a point (one gesture = one undo step), nudge the
selected one with the arrows (key_slots: ← → a grid step, ↑ ↓ a twentieth of the lane's range), right-click it for its
menu (Delete point), delete it (lanes.py does the work)."""
from __future__ import annotations

from PySide6.QtCore import Property, Signal, Slot
from rostrum_gui.edits import Drag

from . import lanes, timing
from .signals import SoundSignals as S


class LaneSlots:
    rollPlayedChanged = Signal()

    @Property("QVariant", notify=rollPlayedChanged)
    def rollPlayed(self):
        """The Editor's playing lane (sustain, expression, bend) of the roll's track: its points, range and the lanes on
        offer (lanes.played); None when the roll is not a notes track. Apart from `roll`, so a point relays no key row."""
        return ((self._view or {}).get("roll") or {}).get("played")

    @Property("QVariantMap", notify=S.pointChanged)
    def point(self):
        """The selected automation point: track, item, lane, index ({} when none)."""
        a = self._apt
        return {"track": a[0], "item": a[1], "lane": a[2], "index": a[3]} if a else {}

    @Slot(str)
    def toggleLanes(self, track_id):
        """Open (or close) the automation lane under a track's row; it opens on the track's volume."""
        self.openLane(track_id, "" if track_id in self._open else track_id, "volume")

    @Slot(str, str, str)
    def openLane(self, track_id, target, lane):
        """Show `lane` of `target` (the track or one of its sends) under the track's row; "" closes."""
        if not target:
            self._open.pop(track_id, None)
        elif (target, lane) in lanes.applicable(self.doc.item(track_id), self.doc.data):
            self._open[track_id] = (target, lane)
        else:
            return self._fail(f'Error: lane: "{lane}" of "{target}" is not a lane on {track_id}.')
        self._kept_view().keep_lanes(self._open)       # open lanes survive a reopen (view_kept.py)
        self._rebuild()

    @Slot(str)
    def openPlayLane(self, lane):
        """Show `lane` (sustain, dynamics = expression, bend) in the Editor's playing lane."""
        if lane not in lanes.PLAYED:
            return self._fail(f'Error: lane: "{lane}" is not a playing lane (one of {", ".join(lanes.PLAYED)}).')
        self._play_lane = lane
        self._rebuild()

    @Slot(str, str, str, float, float, float, float, bool)
    @Slot(str, str, str, float, float, float, float, bool, float)
    def laneBegin(self, track_id, target, lane, t, yfrac, tol_t, tol_y, free, px=0.0):
        """Press in a lane (`yfrac` 0 top .. 1 bottom, tolerances: seconds and a fraction of the height): grab
        the point there or add one (in the grid cell under the pointer; `px`: one screen pixel in seconds), and start
        one gesture."""
        self.endDrag()
        self.select(track_id)

        def go():
            track = self.doc.item(track_id)
            e = lanes.PointEdit(target, lanes.owner_of(track, target), self.doc.data, lane, self._grid_now)
            span = e.hi - e.lo
            call = e.press(t, e.lo + (1 - yfrac) * span, tol_t, tol_y * span, free, px)
            self._edit, self._drag = e, Drag(self.doc, self.who, "Automate")
            if call:
                self._drag.preview([call])
            self._apt = (track_id, target, lane, e.index)
            self.pointChanged.emit()
        self._guard(go)

    @Slot(float, float, bool)
    def laneDrag(self, t, yfrac, free):
        e = self._edit
        if e is not None and self._drag is not None:
            self._guard(lambda: self._drag.preview([e.move(t, e.lo + (1 - yfrac) * (e.hi - e.lo), free)]))

    @Slot()
    def clearPoint(self):
        if self._apt:
            self._apt = None
            self.pointChanged.emit()

    def _drop_point(self):
        if self._apt and self._sel != self._apt[0]:
            self.clearPoint()

    def _remove_point(self):
        e = self._point_edit()
        self._apt = None
        self.pointChanged.emit()
        self._guard(lambda: self._apply([e.remove()], "Delete point"))

    def _point_edit(self):
        track_id, target, lane, i = self._apt
        e = lanes.PointEdit(target, lanes.owner_of(self.doc.item(track_id), target), self.doc.data, lane, self._grid_now)
        e.index = i
        return e

    def _nudge_point(self, beats: float = 0.0, steps: int = 0) -> bool:
        """The arrows on a selected point: `beats` later (earlier when < 0), never past its neighbours; `steps`
        twentieths of the lane's range up (down when < 0), inside the range. One change (quick repeats merge)."""
        e = self._point_edit()
        if not 0 <= e.index < len(e.pts):
            self.clearPoint()
            return False
        at = e.pts[e.index][2]
        t = timing.tempo.seconds_at(self.doc.data, max(0.0, timing.beat(at, self.doc.data) + beats)) if beats else at
        call = e.move(t, e.value() + steps * (e.hi - e.lo) / 20, True)
        return self._act([call], "Nudge point")

    @Slot(str, str, str, float, float, float, float, result="QVariantList")
    def pointMenu(self, track_id, target, lane, t, yfrac, tol_t, tol_y):
        """Right-click in a lane: on a point, it is selected and its menu comes back (Delete point); [] off every point
        (the place's own menu then)."""
        e = lanes.PointEdit(target, lanes.owner_of(self.doc.item(track_id), target), self.doc.data, lane, self._grid_now)
        v = e.lo + (1 - yfrac) * (e.hi - e.lo)
        near = [(((p[2] - t) / tol_t) ** 2 + ((p[1] - v) / (tol_y * (e.hi - e.lo) or 1)) ** 2, i) for i, p in enumerate(e.pts)]
        d, i = min(near, default=(2.0, -1))
        if d > 1.0:
            return []
        self._apt = (track_id, target, lane, i)
        self.pointChanged.emit()
        return [{"value": "at:point:delete", "label": "Delete point", "keys": "Delete", "group": "point", "sub": []}]
