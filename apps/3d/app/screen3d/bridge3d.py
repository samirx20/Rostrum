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
from rostrum3d.compile import describe, shot_info
from rostrum_gui import DocBridge, sections
from rostrum_gui.selection_rules import click
from rostrum_gui.markers import MarkerWatch
from rostrum_gui.time_snap import TimeSnap

from rostrum3d import fields as F
from rostrum3d.light_fields import FINAL_ONLY as LIGHT_FINAL
from rostrum3d.material_fields import FINAL_ONLY as MATERIAL_FINAL

from . import outline, route, scene_state, shots as shot_list
from .action_preview3d import ActionPreview3D
from .actions3d import fit_note
from .adding import Adder
from .context_qt import Context
from .poses_qt import Poses
from .material_balls import BallRenderer, MaterialBalls
from .materials import USERS, Materials3D
from .key_pick3d import KeyBar3D, KeyPick3D, Multi3D
from .render_job import RenderJob
from .stretch3d import Stretch3D
from .timeline3d import Mover


# The group each kind IS (SPEC §3.2, the lead's ruling): always open; every other group opens only when changed.
sections.OWN.update({"mesh": "Shape", "import": "File", "part": "Part", "light": "Light", "camera": "Lens", "rig": "Rig",
                     "material": "Surface", "shot": "Shot", "key": "Key"})
FINAL_ONLY = {"light": LIGHT_FINAL, "material": MATERIAL_FINAL}      # fields the quick view can't show: their rows get a "Final" tag
FINAL_TIP = "Shows in Final, not in the Quick view"
PAGES = ("build", "animate", "render")
NONE_FIRST = {"material", "item"}       # fields naming another item that may name none ("" = no material, focus on a distance)


DATA_GROUPS = {"Mesh data"}             # groups that are data an operation writes (an editable mesh's points), never rows


def _is_data(type_, r) -> bool:
    p = F.param(type_, r["id"]) if r.get("row") == "param" else None
    return (p is not None and p.group in DATA_GROUPS) or any(r.get(k) in DATA_GROUPS for k in ("group", "in", "fold"))


def _without_data(r):
    names = r.get("names")
    return {**r, "names": [n for n in names if n.get("group") not in DATA_GROUPS]} if isinstance(names, list) else r


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
    shotChanged = Signal()              # the screen shows another shot (showShot): the viewport starts from its camera

    def __init__(self, doc, shot_id=None, autosave=False, viewport=_viewport, render_engine=None, parent=None):
        shots = doc.data.get("shots", [])
        if not shots:
            raise ValueError("the document has no shot yet (shot(...) in a script, or shot.add)")
        self.shot_id, self.autosave = shot_id or shots[0]["id"], autosave
        self._info = shot_info(doc.data, self.shot_id)          # fails loudly at start: a shot needs a camera
        self._frame, self._folded = self._info["start"], set()
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
        self._poses = Poses(self)
        self._mover, self._time_snap = Mover(self), TimeSnap(self)        # the timeline (timeline3d.py, key_pick3d.py)
        self._keys, self._key_bar, self._multi = KeyPick3D(self, self), KeyBar3D(self, self), Multi3D(self, self)
        self._stretch = Stretch3D(self, self)
        self.selectedItemsChanged.connect(self.outlineChanged)     # the scene list lights every selected row
        self._make_actions()                                # the settings panel's actions (Combine) and their hover preview
        self.viewport = viewport(self) if viewport else None
        self.balls = MaterialBalls(BallRenderer() if self.viewport is not None else None)   # rendered preview balls
        self._mats = Materials3D(self, self.balls)   # the picker, the chip, the inline rows

    # ---- what the viewport and QML read -----------------------------------------------------------------------
    def scene(self) -> dict:
        """The shot's scene for the engine: the document's, or the hovered action's result (action_preview3d.py)."""
        return self._previewed if self._previewed is not None else describe(self.doc.data, self.shot_id, self.doc.folder)

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
        return outline.scene_rows(self.doc.data, self._folded, self.selectedOwner, self._info["fps"])

    @Property("QVariantList", notify=outlineChanged)
    def materials(self):
        return outline.named(self.doc.data, "materials")

    @Property("QVariantList", notify=outlineChanged)
    def shots(self):
        return outline.named(self.doc.data, "shots")

    @Slot(str, result="QVariantList")
    def shotEntries(self, view_mode):
        """The crumb's list (shots.crumb_entries): the shots, the shown one checked, then New shot (from this view)."""
        return shot_list.crumb_entries(self.shots, self.shot_id, view_mode, self.add.canAddShot)

    @Slot(str)
    def showShot(self, shot_id):
        """Show another shot (screen state, not an edit): its time, its frame size, its camera in the viewport."""
        if not shot_id or shot_id == self.shot_id:      # "": a failed New shot already said why
            return
        try:
            info = shot_info(self.doc.data, shot_id)
        except ValueError as e:
            return self.fail_line(f"Error: shot: {e}")
        if self._timer.isActive():
            self.togglePlay()
        self.shot_id, self._info = shot_id, info
        self._frame = min(max(self._frame, info["start"]), info["end"])
        self.model.update(self._rows())
        self.shotChanged.emit()
        self.outlineChanged.emit()
        self.frameChanged.emit()

    @Slot()
    def newShotFromView(self):
        """A camera where the viewport looks from, a shot through it (shot.from_view: one undo step); then show it."""
        if self.viewport is None:
            return self.fail_line("Error: new shot from this view: there is no viewport to take the view from.")
        first = shot_info(self.doc.data, self.doc.data["shots"][0]["id"])     # the new shot is framed like the first
        call, new = shot_list.from_view_call(self.doc, self.viewport.cam, first)
        if self._guard(lambda: self._done(self.doc.apply([call], self.who, label="New shot from this view"), "")):
            self.showShot(new)

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

    @Slot(str)
    def rowAction(self, action_id):
        """A row's button (or a choice of its menu) was clicked: the action runs as it would from the bar."""
        self._hub.run(action_id)

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

    poses = Property(QObject, lambda self: self._poses, constant=True)  # QML: backend.poses (poses_qt.py)
    mats = Property(QObject, lambda self: self._mats, constant=True)    # QML: backend.mats (materials.py)

    def on_page(self, item):
        """An item's material shows in its own Material row (MaterialRow.qml, the picker), not as a plain choice."""
        return {"material"} if item.get("type") in USERS else set()
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
        rows = [_without_data(r) for r in rows if not _is_data(type_, r)]     # an editable mesh's points: data, not controls
        buttons = self._hub.row_buttons() if hasattr(self, "_hub") else {}               # actions that sit on a row (Action.row): Lens, Focus on an item, bevel
        for r in rows:
            if r["row"] == "param":
                r["button"] = buttons.get(r["id"])
            if r["row"] == "param" and r["id"] == "bevel" and type_ == "mesh":
                line = fit_note(getattr(self, "_fits", {}), self._sel)
                r["note"] = {"text": line, "kind": "warning"} if line else None
            if r["row"] == "param" and r["id"] in FINAL_ONLY.get(type_, ()):
                r["tag"], r["tagHelp"] = "Final", FINAL_TIP
            p = F.param(type_, r["id"]) if r["row"] == "param" else None
            if p is not None and p.type == "text" and p.kind:
                doc_items = doc_items or list(self.doc.items())
                named = [{"value": i["id"], "label": outline.label_of(i)} for i in doc_items if i["id"] != self._sel
                         and (i.get("type") == p.kind or (p.kind == "item" and i.get("type") in F.ITEMS))]
                r["type"], r["options"] = "choice", ([{"value": "", "label": "None"}] if p.kind in NONE_FIRST else []) + named
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

    # ---- the kit timeline (LayerTimeline.qml; TIMELINE.md › The key timeline): keys in time, one drag = one change
    @Property("QVariantMap", notify=outlineChanged)
    def frameInfo(self):
        """The ruler's length and rate: {fps, duration} (seconds, the shot's last frame included)."""
        return {"fps": self._info["fps"], "duration": (self._info["end"] + 1) / self._info["fps"]}

    @Property("QVariantList", notify=outlineChanged)
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
        if not self._mover.active or event.kind != "preview":     # mid-drag the timeline keeps its rows (and the mouse);
            self.outlineChanged.emit()                         # the dragged key follows the pointer until release
        if clamped != self._frame:
            self.setFrame(clamped)
        if self.autosave and event.kind == "change":
            self._guard(self.doc.save)

    def close(self):
        self._timer.stop()
        self.marks.close()
        self.endDrag()
        if self.balls._r is not None:
            self.balls._r.close()
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
