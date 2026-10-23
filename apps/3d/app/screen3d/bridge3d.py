"""Rostrum3D's document bridge: the kit's DocBridge plus the shot, the playhead (a frame of the shot), play / pause, the
page (Build / Animate / Render: screen state), the scene list with its keys, the key drag, the viewport and the Render job.
The settings panel is the kit's sections layout (open if changed, the rest a row of names; each kind's own group always
open: OWN below). Every change is an operation; a drag is one
doc.gesture = one undo step. How an edit becomes a call lives in route.py only.

What the viewport (viewport.py) reads from it: scene(), frame, shot_info(), selected, select(id), and the signals
docChanged, frameChanged, selectionChanged.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot
from rostrum_core.keys import keys_of
from rostrum3d.compile import describe, shot_info
from rostrum_gui import DocBridge, sections
from rostrum_gui.edits import Drag
from rostrum_gui.selection_rules import click
from rostrum_gui.markers import MarkerWatch

from rostrum3d import fields as F

from . import outline, route, scene_state
from .action_preview3d import ActionPreview3D
from .adding import Adder
from .context_qt import Context
from .render_job import RenderJob


# The group each kind IS (SPEC §3.2, the lead's ruling): always open; every other group opens only when changed.
sections.OWN.update({"mesh": "Shape", "import": "File", "part": "Part", "light": "Light", "camera": "Lens", "rig": "Rig",
                     "material": "Surface", "shot": "Shot", "key": "Key"})
PAGES = ("build", "animate", "render")


def _viewport(bridge):
    from .viewport import Viewport      # written alongside; imported late so a bridge without a window needs no engine
    return Viewport(bridge)


class Bridge3D(ActionPreview3D, DocBridge):
    sections = True                     # the kit's open-if-changed settings panel (rostrum_gui/sections.py)
    frameChanged = Signal()
    outlineChanged = Signal()
    playingChanged = Signal()
    markersChanged = Signal()
    pageChanged = Signal()

    def __init__(self, doc, shot_id=None, autosave=False, viewport=_viewport, render_engine=None, parent=None):
        shots = doc.data.get("shots", [])
        if not shots:
            raise ValueError("the document has no shot yet (shot(...) in a script, or shot.add)")
        self.shot_id, self.autosave = shot_id or shots[0]["id"], autosave
        self._info = shot_info(doc.data, self.shot_id)          # fails loudly at start: a shot needs a camera
        self._frame, self._folded, self._drag, self._grab = self._info["start"], set(), None, None
        self._page = "build"
        super().__init__(doc, parent=parent)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self.marks = MarkerWatch(doc.folder, self, self.who, self._fail, "3d")   # shared markers: flags, edits, snapping
        self.marks.changed.connect(self.markersChanged)
        self.join_history(self.marks)                       # marker edits undo with the screen's one history
        self.render = RenderJob(self, render_engine)
        self.add = Adder(self)
        self.ctx = Context(self)
        self.selectedItemsChanged.connect(self.outlineChanged)     # the scene list lights every selected row
        self._make_actions()                                # the settings panel's actions (Combine) and their hover preview
        self.viewport = viewport(self) if viewport else None

    # ---- what the viewport and QML read -----------------------------------------------------------------------
    def scene(self) -> dict:
        """The shot's scene for the engine: the document's, or the hovered action's result (action_preview3d.py)."""
        return self._previewed if self._previewed is not None else describe(self.doc.data, self.shot_id)

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

    @Property("QVariantMap", notify=outlineChanged)
    def sceneState(self):
        """What the panel shows with nothing selected: {shot: {id, label, rows}, sky: {id, label} or {}} (scene_state)."""
        return scene_state.scene_state(self.doc.data, self.shotInfo)

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
    def sceneRows(self):
        """The scene list, its keys on the same rows (outline.scene_rows)."""
        return outline.scene_rows(self.doc.data, self._folded, self.selectedOwner)

    @Property("QVariantList", notify=outlineChanged)
    def materials(self):
        return outline.named(self.doc.data, "materials")

    @Property("QVariantList", notify=outlineChanged)
    def shots(self):
        return outline.named(self.doc.data, "shots")

    @Property(str, notify=pageChanged)
    def page(self):
        """Build | Animate | Render (screen state, never the document): the same document, camera and selection."""
        return self._page

    @Slot(str)
    def setPage(self, page):
        if page not in PAGES:
            return self.fail_line(f"Error: page: {page!r} is not one of {', '.join(PAGES)}.")
        if page != self._page:
            self._page = page
            self.pageChanged.emit()

    @Property(str, notify=outlineChanged)
    def selectedOwner(self):
        """The scene item the selection belongs to: itself, or the item of a selected key ("" for a material, shot)."""
        if not self._sel:
            return ""
        it = self.doc.item(self._sel)
        if it["type"] == "key":
            return self.doc.parent_of(self._sel)[0]
        return self._sel if it["type"] in route.F.ITEMS else ""

    actions = Property(QObject, lambda self: self._hub, constant=True)     # the panel's actions (action_preview3d.py)

    @Property("QVariantList", notify=outlineChanged)
    def selectedRows(self):
        """The scene items selected together (the primary first): the scene list lights them all."""
        return [i for i in self.selection if i in self._item_ids()]

    def _item_ids(self) -> set:
        return {it["id"] for it in outline.scene_items(self.doc.data)}

    @Slot(str)
    def toggleInSelection(self, item_id):
        """Ctrl+click in the scene list: add the item to the selection, or take it out."""
        self.selectMany(click(self.selection, None, item_id, {"ctrl"}, "list")[0] or [])

    @Slot(str)
    def selectRange(self, item_id):
        """Shift+click in the scene list: every item row from the primary to this one, as the list shows them."""
        order = [r["id"] for r in self.sceneRows if r["row"] == "layer"]
        here = self.selected if self.selected in order else item_id
        run = click(self.selection, here, item_id, {"shift"}, "list", order)[0]
        self.selectMany([here] + [i for i in run if i != here] if here in run else run)

    @Property(QObject, constant=True)
    def adder(self):
        """The Add menu, Delete and Duplicate (adding.py)."""
        return self.add

    @Slot(str, result="QVariantList")
    def contextEntries(self, item_id):
        return self.ctx.entries(item_id)

    @Slot(str, str)
    def contextRun(self, item_id, value):
        self._guard(lambda: self.ctx.run(item_id, value))

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

    def _rows(self):
        """The inspector's rows, with a field that names another item (its `kind`: a mesh's material, a shot's camera)
        shown as a choice of those items by name. Still the same field, written through the same operation."""
        rows = super()._rows()
        if not self._sel:
            return rows
        type_, doc_items = self.doc.item(self._sel)["type"], None
        for r in rows:
            p = F.param(type_, r["id"]) if r["row"] == "param" else None
            if p is not None and p.type == "text" and p.kind:
                doc_items = doc_items or list(self.doc.items())
                named = [{"value": i["id"], "label": outline.label_of(i)} for i in doc_items if i.get("type") == p.kind]
                r["type"], r["options"] = "choice", ([{"value": "", "label": "None"}] if p.kind == "material" else []) + named
        return rows

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
        self._previewed = None                 # a real change ends any hover preview (the viewport redraws on docChanged)
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

    # ---- the file pieces (files_3d.py, export3d.py) ----------------------------------------------------------
    @Property(QObject, constant=True)
    def exporter(self):
        """The kit's Export sheet for this shot (export3d.py); made on first ask, so a bridge without a window needs none."""
        if getattr(self, "_exporter", None) is None:
            from .export3d import Export3D
            self._exporter = Export3D(self)
        return self._exporter

    @Property(str, notify=outlineChanged)
    def docName(self):
        """The document's name on the top bar: its project's folder name ("" for a scene in memory: the crumb says the shot)."""
        return Path(self.doc.folder).name if self.doc.folder else ""
