"""Rostrum3D's document bridge: the kit's DocBridge plus the shot, the playhead, the page, the scene list with its keys,
the viewport and the Render job. The settings panel is the kit's sections layout (open if changed, the rest a row of
names; each kind's own group always open: OWN below). Every change is an operation; a drag is one doc.gesture = one
undo step. How an edit becomes a call lives in route.py only.

Bridge3D is this class (the wiring, the document hooks, the file pieces) and its mix-ins, one job each:
bridge_signals (the signals), bridge_shots (shot + page), bridge_scene (scene list, selection), bridge_time (playhead,
timeline, key drags), bridge_rows (the settings panel's rows, the screen's facts), action_preview3d (actions).

What the viewport (viewport.py) reads from it: scene(), frame, shot_info(), selected, select(id), and the signals
docChanged, frameChanged, selectionChanged.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Property, QObject, QTimer, Slot
from rostrum3d.compile import describe, shot_info
from rostrum_gui import DocBridge, sections
from rostrum_gui.markers import MarkerWatch
from rostrum_gui.time_snap import TimeSnap

from rostrum3d.light_fields import FINAL_ONLY as LIGHT_FINAL
from rostrum3d.material_fields import FINAL_ONLY as MATERIAL_FINAL

from . import lipsync3d, outline, route
from .action_preview3d import ActionPreview3D
from .adding import Adder
from .bridge_rows import RowsMixin
from .bridge_scene import SceneMixin
from .bridge_shots import ShotMixin
from .bridge_signals import Signals3D
from .bridge_time import TimeMixin
from .context_qt import Context
from .poses_qt import Poses
from .material_balls import BallRenderer, MaterialBalls
from .materials import Materials3D
from .key_pick3d import KeyBar3D, KeyPick3D, Multi3D
from .queue import RenderQueue
from .render_job import RenderJob
from .send_qt import Sender
from .stretch3d import Stretch3D
from .timeline3d import Mover


# The group each kind IS (SPEC 3.2, the lead's ruling): always open; every other group opens only when changed.
sections.OWN.update({"mesh": "Shape", "import": "File", "part": "Part", "light": "Light", "camera": "Lens", "rig": "Rig",
                     "material": "Surface", "shot": "Shot", "key": "Key"})


def _viewport(bridge):
    from .viewport import Viewport      # imported late so a bridge without a window needs no engine
    return Viewport(bridge)


class Bridge3D(Signals3D, ShotMixin, SceneMixin, TimeMixin, RowsMixin, ActionPreview3D, DocBridge):
    sections = True                     # the kit's open-if-changed settings panel (rostrum_gui/sections.py)
    FINAL_ONLY = {"light": LIGHT_FINAL, "material": MATERIAL_FINAL}      # fields the quick view can't show: a "Final" tag

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
        self.queue = RenderQueue(self, render_engine)     # the Render page's queue (queue.py)
        self.send_to = Sender(self)                       # Send to 2D (send_qt.py); QML's `sender` (not a QObject attribute: sender() is Qt's)
        self.add = Adder(self)
        self.ctx = Context(self)
        self._poses = Poses(self)
        self._lipsync, self.open_lipsync = lipsync3d.make(self)     # Lip sync… on a mouth group (lipsync3d.py)
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

    @Property("QVariantMap", notify=Signals3D.outlineChanged)
    def shotInfo(self):
        s = next((s for s in self.doc.data.get("shots", []) if s["id"] == self.shot_id), {"id": self.shot_id})
        return {**self._info, "label": outline.label_of(s)}

    @Slot(str)
    def rowAction(self, action_id):
        """A row's button (or a choice of its menu) was clicked: the action runs as it would from the bar."""
        self._hub.run(action_id)

    actions = Property(QObject, lambda self: self._hub, constant=True)     # the panel's actions (action_preview3d.py)
    poses = Property(QObject, lambda self: self._poses, constant=True)  # QML: backend.poses (poses_qt.py)
    mats = Property(QObject, lambda self: self._mats, constant=True)    # QML: backend.mats (materials.py)
    lipsync = Property(QObject, lambda self: self._lipsync, constant=True)   # QML: backend.lipsync (the kit's LipSyncSheet)

    @Property(QObject, constant=True)
    def adder(self):
        """The Add menu, Delete and Duplicate (adding.py)."""
        return self.add

    @Property(QObject, constant=True)
    def renderJob(self):
        return self.render

    renderQueue = Property(QObject, lambda self: self.queue, constant=True)   # QML: backend.renderQueue (queue.py)

    def extra_commands(self):
        """Ctrl K: the render queue's operations (queue.commands)."""
        return self.queue.commands()

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

    def animate_calls(self, item_id, param, stop=False):
        return route.animate_calls(self.doc.item(item_id), param, self.time, self._info["fps"], stop)

    def _first(self):
        return next((i["id"] for i in self.doc.data.get("items", [])), "")

    @Slot(str)
    def select(self, item_id):
        super().select(item_id)
        self.outlineChanged.emit()

    @Slot()
    def renderStill(self):
        self.render.start()

    # ---- for the render job -----------------------------------------------------------------------------------
    def say(self, text):
        self._set_status(text)

    def fail_line(self, line):
        self._fail(line)

    # ---- inside -----------------------------------------------------------------------------------------------
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
        self.queue.close()
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

    @Property(str, notify=Signals3D.outlineChanged)
    def docName(self):
        """The document's name on the top bar: its project's folder name ("" for a scene in memory: the crumb says the shot)."""
        return Path(self.doc.folder).name if self.doc.folder else ""
