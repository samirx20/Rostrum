"""The playhead and the kit timeline for Bridge3D (a slot mix-in; LayerTimeline.qml, TIMELINE.md > The key timeline):
the frame, play / pause, the ruler's length and markers, keys in time, one drag = one change (timeline3d.py)."""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, Slot

from .bridge_signals import Signals3D

S = Signals3D


class TimeMixin:
    @Property(int, notify=S.frameChanged)
    def frame(self):
        return self._frame

    @Property(float, notify=S.frameChanged)
    def time(self):
        """The playhead in document seconds (keys are at these times): frame / fps."""
        return self._frame / self._info["fps"]

    @Property(bool, notify=S.playingChanged)
    def playing(self):
        return self._timer.isActive()

    @Property("QVariantList", notify=S.markersChanged)
    def markers(self):
        """The shared markers for the ruler's flags ({id, name, at seconds, colour}; the Ruler places them in frames)."""
        return self.marks.rows()

    @Property(QObject, constant=True)
    def markerEdit(self):
        """The ruler's marker edits (add at the playhead, move, rename, delete): rostrum_gui.markers.MarkerWatch."""
        return self.marks

    @Slot(int)
    def setFrame(self, frame):
        frame = min(max(int(frame), self._info["start"]), self._info["end"])
        if frame == self._frame:
            return
        self._frame = frame
        self.model.update(self._rows())
        self.frameChanged.emit()

    @Slot()
    def togglePlay(self):
        if self._timer.isActive():
            self._timer.stop()
        else:
            self._timer.start(round(1000 / self._info["fps"]))
        self.playingChanged.emit()

    def _tick(self):
        nxt = self._frame + 1
        self.setFrame(self._info["start"] if nxt > self._info["end"] else nxt)

    @Property("QVariantMap", notify=S.outlineChanged)
    def frameInfo(self):
        """The ruler's length and rate: {fps, duration} (seconds, the shot's last frame included)."""
        return {"fps": self._info["fps"], "duration": (self._info["end"] + 1) / self._info["fps"]}

    @Property("QVariantList", notify=S.outlineChanged)
    def layers(self):
        """The timeline's rows (the kit reads `layers`): the scene list with its keys (outline.scene_rows)."""
        return self.sceneRows

    @Slot(float)
    def setTime(self, t):
        self.setFrame(round(t * self._info["fps"]))

    keys = Property(QObject, lambda self: self._keys, constant=True)            # key_pick3d.py
    keyBar = Property(QObject, lambda self: self._key_bar, constant=True)
    multi = Property(QObject, lambda self: self._multi, constant=True)
    stretch = Property(QObject, lambda self: self._stretch, constant=True)      # stretch3d.py (the kit's StretchSelect)
    timeSnap = Property(QObject, lambda self: self._time_snap, constant=True)   # rostrum_gui/time_snap.py

    def beginMove(self, ids, grab, label, t0=None) -> bool:
        return self._mover.begin(ids, grab, label, t0)

    @Slot(str, result=bool)
    def beginKeyDrag(self, key_id):
        """One key's drag (the picked keys' is keys.beginDrag): it becomes the selection, so the panel shows it."""
        self.select(key_id)
        return self.beginMove([key_id], key_id, "Move key")

    @Slot(str, str, float, result=bool)
    def beginBarDrag(self, item_id, how, t):
        """An item's bar dragged: every key of it moves together (`how` is the kit's: only "move" here)."""
        keys = self.doc.item(item_id).get("keys", []) if self.doc.has(item_id) else []
        if how != "move" or not keys:
            return False
        grab = min(keys, key=lambda k: abs(k["t"] - t))["id"]
        return self.beginMove([k["id"] for k in keys], grab, f"Move {self.label_of(self.doc.item(item_id))} in time", t)

    @Slot(float, float)
    def barDragTo(self, t, snap=0.0):
        self._mover.to(t, snap)

    @Slot(float, float)
    def keyDragTo(self, t, snap=0.0):
        """The grabbed key to `t` seconds (whole frames; within `snap` seconds it lands on a marker, the playhead or
        another key: timeline3d.py), the others it carries by as much."""
        self._mover.to(t, snap)

    @Slot()
    def endDrag(self):
        self._mover.end()
