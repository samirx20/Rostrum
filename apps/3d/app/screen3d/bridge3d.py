"""Rostrum3D's document bridge: the kit's DocBridge plus the shot, the playhead (a frame of the shot), play / pause, the
outliner and timeline rows, the key drag, the viewport and the Render job. Every change is an operation; a drag is one
doc.gesture = one undo step. How an edit becomes a call lives in route.py only.

What the viewport (viewport.py) reads from it: scene(), frame, shot_info(), selected, select(id), and the signals
docChanged, frameChanged, selectionChanged.
"""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot
from rostrum_core.keys import keys_of
from rostrum3d.compile import describe, shot_info
from rostrum_gui import DocBridge
from rostrum_gui.edits import Drag
from rostrum_gui.markers import MarkerWatch

from . import outline, route
from .render_job import RenderJob


def _viewport(bridge):
    from .viewport import Viewport      # written alongside; imported late so a bridge without a window needs no engine
    return Viewport(bridge)


class Bridge3D(DocBridge):
    frameChanged = Signal()
    outlineChanged = Signal()
    playingChanged = Signal()
    markersChanged = Signal()

    def __init__(self, doc, shot_id=None, autosave=False, viewport=_viewport, render_engine=None, parent=None):
        shots = doc.data.get("shots", [])
        if not shots:
            raise ValueError("the document has no shot yet (shot(...) in a script, or shot.add)")
        self.shot_id, self.autosave = shot_id or shots[0]["id"], autosave
        self._info = shot_info(doc.data, self.shot_id)          # fails loudly at start: a shot needs a camera
        self._frame, self._folded, self._drag, self._grab = self._info["start"], set(), None, None
        super().__init__(doc, parent=parent)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self.marks = MarkerWatch(doc.folder, self, self.who, self._fail, "3d")   # shared markers: flags, edits, snapping
        self.marks.changed.connect(self.markersChanged)
        self.render = RenderJob(self, render_engine)
        self.viewport = viewport(self) if viewport else None

    # ---- what the viewport and QML read -----------------------------------------------------------------------
    def scene(self) -> dict:
        return describe(self.doc.data, self.shot_id)

    def shot_info(self) -> dict:
        return dict(self._info)

    @Property(int, notify=frameChanged)
    def frame(self):
        return self._frame

    @Property(float, notify=frameChanged)
    def time(self):
        """The playhead in document seconds (keys are at these times): frame / fps."""
        return self._frame / self._info["fps"]

    @Property("QVariantMap", notify=outlineChanged)
    def shotInfo(self):
        s = next((s for s in self.doc.data.get("shots", []) if s["id"] == self.shot_id), {"id": self.shot_id})
        return {**self._info, "label": outline.label_of(s)}

    @Property("QVariantList", notify=markersChanged)
    def markers(self):
        """The shared markers for the ruler's flags ({id, name, at seconds, colour}; the Ruler places them in frames)."""
        return self.marks.rows()

    @Property(QObject, constant=True)
    def markerEdit(self):
        """The ruler's marker edits (add at the playhead, move, rename, delete): rostrum_gui.markers.MarkerWatch."""
        return self.marks

    @Property(bool, notify=playingChanged)
    def playing(self):
        return self._timer.isActive()

    @Property("QVariantList", notify=outlineChanged)
    def outline(self):
        return outline.outliner_rows(self.doc.data, self._folded)

    @Property("QVariantList", notify=outlineChanged)
    def tracks(self):
        return outline.tracks(self.doc.data, self.selectedOwner)

    @Property(str, notify=outlineChanged)
    def selectedOwner(self):
        """The scene item the selection belongs to: itself, or the item of a selected key ("" for a material, shot)."""
        if not self._sel:
            return ""
        it = self.doc.item(self._sel)
        if it["type"] == "key":
            return self.doc.parent_of(self._sel)[0]
        return self._sel if it["type"] in route.F.ITEMS else ""

    @Property(QObject, constant=True)
    def renderJob(self):
        return self.render

    # ---- the kit's hooks: the 3D animation model (route.py) ----------------------------------------------------
    def label_of(self, item):
        owner = self.doc.item(self.doc.parent_of(item["id"])[0]) if item.get("type") == "key" else None
        return outline.label_of(item, owner)

    def edit_call(self, item_id, param, value):
        return route.edit_call(self.doc, item_id, param, value, self.time)

    def shown_values(self, item):
        return route.shown_values(item, self.time)

    def anim_state(self, item, param):
        return route.anim_state(item, param, self.time, self._info["fps"])

    def animate_calls(self, item_id, param):
        return route.animate_calls(self.doc.item(item_id), param, self.time)

    def _first(self):
        return next((i["id"] for i in self.doc.data.get("items", [])), "")

    # ---- screen state -----------------------------------------------------------------------------------------
    @Slot(str)
    def select(self, item_id):
        super().select(item_id)
        self.outlineChanged.emit()

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

    @Slot(str)
    def toggleFold(self, item_id):
        self._folded ^= {item_id}
        self.outlineChanged.emit()

    @Slot()
    def renderStill(self):
        self.render.start()

    # ---- the key drag: one doc.gesture = one change ------------------------------------------------------------
    @Slot(str, result=bool)
    def beginKeyDrag(self, key_id):
        self.endDrag()
        self.select(key_id)

        def go():
            self._drag, self._grab = Drag(self.doc, self.who, "Move key"), key_id
        return self._guard(go)

    @Slot(float, float)
    def keyDragTo(self, frame, snap=0.0):
        """Move the dragged key to a frame of the shot, or to its end (whole frames; a frame another key of its field
        holds is skipped). `snap`: frames within which the key lands on a shared marker's frame instead."""
        if self._drag is None:
            return
        fps, key = self._info["fps"], self.doc.item(self._grab)
        on = self.marks.snap(frame / fps, snap / fps)
        frame = round(on * fps) if on != frame / fps else round(frame)
        t = min(max(frame, self._info["start"]), self._info["end"] + 1) / fps   # up to where the shot ends
        owner = self.doc.item(self.doc.parent_of(key["id"])[0])
        if any(k["id"] != key["id"] and abs(k["t"] - t) < 1e-6 for k in keys_of(owner, key["prop"])):
            return
        self._guard(lambda: self._drag.preview([{"op": "key.set", "target": [key["id"]], "args": {"t": t}}]))

    @Slot()
    def endDrag(self):
        d, self._drag, self._grab = self._drag, None, None
        if d is not None:
            self._guard(lambda: self._done(d.end(), ""))

    # ---- for the render job -----------------------------------------------------------------------------------
    def say(self, text):
        self._set_status(text)

    def fail_line(self, line):
        self._fail(line)

    # ---- inside -----------------------------------------------------------------------------------------------
    def _tick(self):
        nxt = self._frame + 1
        self.setFrame(self._info["start"] if nxt > self._info["end"] else nxt)

    def _on_doc(self, event):
        try:                                   # a shot edit may change its length, rate or camera
            self._info = shot_info(self.doc.data, self.shot_id)
        except ValueError as e:
            self._fail(f"Error: shot: {e}")
        clamped = min(max(self._frame, self._info["start"]), self._info["end"])
        super()._on_doc(event)
        if self._drag is None or event.kind != "preview":     # mid-drag the timeline keeps its rows (and the mouse);
            self.outlineChanged.emit()                         # the dragged key follows the pointer until release
        if clamped != self._frame:
            self.setFrame(clamped)
        if self.autosave and event.kind == "change":
            self._guard(self.doc.save)

    def close(self):
        self._timer.stop()
        self.marks.close()
        self.endDrag()
        if self.viewport is not None and hasattr(self.viewport, "close"):
            self.viewport.close()
