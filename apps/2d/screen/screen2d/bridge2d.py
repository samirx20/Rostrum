"""Rostrum2D's document bridge: the kit's DocBridge plus time, pages (design, draw, animate), the layer tree, the
canvas frame and the two drags (move a layer on the canvas, move a key on the timeline). Every change is an operation; each drag is
one doc.gesture = one undo step. How an edit becomes a call lives in route.py only.
"""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot
from rostrum_gui import DocBridge
from rostrum_gui.markers import MarkerWatch
from rostrum_core import marker_times
from rostrum_core.tree import index
from rostrum2d import fields as F, retime

from .command_words import CommandWords
from . import bounds, outline
from .drags import DragSlots
from .file_commands import FileCommands
from .frames import FrameRenderer
from .handle_slots import HandleSlots
from .hooks import Hooks2D
from .layer_order import LayerOrder
from .painter import Painter
from .playback import Playback, size_offered
from .playstats import STATS
from .render3d_watch import Render3DWatch
from .tools2d import ToolSlots
from .undo_state import UndoState


class Bridge2D(UndoState, LayerOrder, FileCommands, CommandWords, DragSlots, HandleSlots, ToolSlots, Hooks2D, DocBridge):
    timeChanged = Signal()
    pageChanged = Signal()
    frameChanged = Signal()
    outlineChanged = Signal()
    playingChanged = Signal()
    markersChanged = Signal()
    historyChanged = Signal()                               # the kit's docChanged, for the history properties below
    renameRequested = Signal(str)                           # F2 / Ctrl+K "Rename layer": the Layers panel's name box

    def __init__(self, doc, comp_id=None, autosave=False, parent=None):
        comps = doc.data.get("comps", [])
        if not comps:
            raise ValueError("the document has no composition yet (comp.add)")
        self.comp_id = comp_id or comps[0]["id"]
        self._t, self._page, self._frame, self.autosave = 0.0, "design", 0, autosave
        self._folded, self._opened, self._drag, self._grab = set(), set(), None, None
        self._placed = None                                 # placed(), kept per document and markers
        self.marks = None                                   # made below (it needs this QObject); the first rows have none
        super().__init__(doc, parent=parent)
        self.docChanged.connect(self.historyChanged)
        self.frames = FrameRenderer(self)
        self._scene = None                                  # the engine's scene, described once per change (_render)
        self.frames.ready.connect(self._on_frame)
        self.frames.failed.connect(self._fail)
        self.painter = Painter(self)
        self._make_tools()                                  # pen, curves, export, import, add, problems (tools2d.py)
        self.play = Playback(self)                          # playing: follows the clock (playback.py)
        self.play.changed.connect(self.playingChanged)
        self.marks = MarkerWatch(doc.folder, self, self.who, self._fail, "2d")   # shared markers: flags, edits, snap
        self.marks.changed.connect(self.markersChanged)
        self.marks.changed.connect(lambda: self.model.update(self._rows()))   # the marker picks list them
        self._marker_saved()                                # (remembers the last change: only later ones are announced)
        self.marks.changed.connect(self._marker_saved)
        self.join_history(self.marks)                       # marker edits undo with the screen's one history
        self.model.update(self._rows())
        self.marks.changed.connect(self._render)            # expressions may read marker("…")
        self.marks.changed.connect(self._problems.touch)
        self.r3d = Render3DWatch(self, self)                # a 3D render layer follows its item's newest render
        self.r3d.changed.connect(self._render)
        self.r3d.changed.connect(self._problems.touch)
        self.selectionChanged.connect(self.outlineChanged)
        self._render()
        self._problems.touch()

    # ---- the history, as the top bar and the Undo / Redo buttons read it (undo_state.py) ----------------------------
    historyCount = Property(int, lambda self: self.changes_since_open(), notify=historyChanged)   # since it opened
    undoLabel = Property(str, UndoState.undo_label, notify=historyChanged)         # "" = nothing to undo
    redoLabel = Property(str, UndoState.redo_label, notify=historyChanged)

    # ---- reads for QML ----------------------------------------------------------------------------------------
    def comp(self) -> dict:
        return self.doc.item(self.comp_id)

    def times(self) -> dict:
        """The project's shared markers {name: seconds} (keys timed on a marker are placed through them)."""
        return marker_times.times(self.doc.folder) if self.doc.folder else {}

    def placed(self) -> dict:
        """The composition as the screen shows it: every time in composition seconds, where it plays (retime.timed:
        a layer timed from a marker, keys on a marker). The playhead is in these seconds; keys on a marker keep `ref`.
        Worked out once per document and markers (every change gives a new doc.data, every marker read a new
        marks.times), not on every read: rows, outline and drags read it many times a frame. Callers only read it."""
        key = (self.doc.data, self.marks.times if self.marks else None)
        if self._placed is None or any(a is not b for a, b in zip(self._placed[0], key)):
            self._placed = (key, retime.timed(self.comp(), self.times(), self.comp()["fps"]))
        return self._placed[1]

    def placed_item(self, id_: str) -> dict:
        """One item of `placed()` (a layer, effect, mask or key owner), its times in composition seconds."""
        found = index(self.placed(), self.doc.kind.lists).get(id_)
        return found.item if found else self.doc.item(id_)

    def offset(self, id_: str) -> float:
        """Where the item's own time 0 sits in composition seconds (0 unless it or a parent is timed from a marker)."""
        return retime.offset_of(self.doc.data, id_, self.times())

    def own_t(self, id_: str, t: float | None = None) -> float:
        """A screen time (the playhead by default) as the item's document writes it: its own seconds. The one way back
        from composition seconds; every write at a time (key.add, value.set, key drag, frame add, stroke) uses it."""
        return (self._t if t is None else t) - self.offset(id_)

    @Property(float, notify=timeChanged)
    def time(self):
        return self._t

    @Property("QVariantMap", notify=outlineChanged)
    def frameInfo(self):
        c = {**F.defaults("comp"), **self.comp()}
        return {"width": c["width"], "height": c["height"], "fps": c["fps"], "duration": c["duration"],
                "label": outline.label_of(c), "blur": c["shutter"] > 0 and c["shutterSamples"] > 1,
                "previewSize": size_offered(c)}

    @Property(str, notify=pageChanged)
    def page(self):
        return self._page

    @Property(bool, notify=playingChanged)
    def playing(self):
        return self.play.playing

    @Property(QObject, constant=True)
    def playback(self):
        """Playing's settings (Blur while playing): screen2d/playback.py."""
        return self.play

    @Property(int, notify=frameChanged)
    def frame(self):
        return self._frame

    @Property("QVariantList", notify=markersChanged)
    def markers(self):
        return self.marks.rows()

    @Property(QObject, constant=True)
    def markerEdit(self):
        """The ruler's marker edits (add at the playhead, move, rename, delete): rostrum_gui.markers.MarkerWatch."""
        return self.marks

    @Property("QVariantList", notify=outlineChanged)
    def layers(self):
        return outline.layer_rows(self.comp(), self._folded)

    @Property("QVariantList", notify=outlineChanged)
    def tracks(self):
        return outline.tracks(self.placed(), self._opened)

    @Property(str, notify=outlineChanged)
    def selectedLayer(self):
        """The layer the selection belongs to (itself, or the layer of a selected effect, mask or key)."""
        return bounds.layer_of(self.doc, self._sel) if self._sel else ""

    @Property("QVariantMap", notify=outlineChanged)
    def selBox(self):
        layer = self.selectedLayer
        return next((b for b in bounds.boxes(self.placed(), self._t) if b["id"] == layer), {})

    def _first(self):
        rows = outline.layer_rows(self.comp(), set())
        return rows[0]["id"] if rows else self.comp_id

    # ---- screen state -----------------------------------------------------------------------------------------
    @Slot(float)
    def setTime(self, t):
        c = self.comp()
        self._t = min(max(round(t * c["fps"]) / c["fps"], 0.0), c["duration"])
        still = not self.play.playing            # while playing, only the playhead and the frame (playback.py)
        if still:
            with STATS.stage("rows"):
                self.model.update(self._rows())
        self.timeChanged.emit()
        if still:
            with STATS.stage("outline"):
                self.outlineChanged.emit()
        self._show()

    @Slot(str)
    def setPage(self, page):
        self._page = page
        self.pageChanged.emit()

    @Slot()
    def togglePlay(self):
        self.play.toggle()

    @Slot(str)
    def toggleFold(self, item_id):
        self._folded ^= {item_id}
        self.outlineChanged.emit()

    @Slot(str)
    def toggleTrack(self, item_id):
        self._opened ^= {item_id}
        self.outlineChanged.emit()

    @Slot(float, float, result=str)
    def pickAt(self, x, y):
        """A click on the canvas (composition px): select the topmost layer there; on empty canvas, the
        composition (its frame size, rate, length, background)."""
        hit = bounds.pick(self.placed(), self._t, x, y)
        if hit != self.selectedLayer:
            self.select(hit or self.comp_id)
        return hit

    # ---- for the Painter (screen2d/painter.py) ----------------------------------------------------------------
    def guard(self, fn) -> bool:
        return self._guard(fn)

    def done(self, change, nothing):
        self._done(change, nothing)

    # ---- inside -----------------------------------------------------------------------------------------------
    def _render(self):
        """The document, the markers or a 3D render changed: describe the scene again, then show the playhead."""
        self._scene = None
        self._show()

    def _show(self):
        """The frame at the playhead. The scene doesn't depend on the playhead (the engine evaluates every time), so it
        is described once per change, never per frame: playing and scrubbing only send `t`."""
        from rostrum2d.scene import describe
        if self._scene is None:
            try:        # a 3D render layer's render missing, a video file gone …: said on screen, no frame drawn
                with STATS.stage("describe"):
                    self._scene = describe(self.doc.data, self.comp_id, self.marks.times, self.doc.folder,
                                           (0.0, self.comp()["duration"]))
            except Exception as e:  # noqa: BLE001
                self._scene = False                         # tried; the next change tries again
                self._fail(str(e))
        if self._scene:
            self.frames.request(self._scene, self._t, self.play.samples(), self.play.scale())

    def _on_frame(self, serial):
        self._frame = serial
        self.frameChanged.emit()
        STATS.frame_shown(self._t)

    def _on_doc(self, event):
        super()._on_doc(event)
        self.outlineChanged.emit()
        self._render()
        self._problems.touch()
        if self.autosave and event.kind == "change":
            self._guard(self.doc.save)

    def close(self):
        self.play.stop()
        self.marks.close()
        self.endDrag()
        self.frames.close()
        self._problems.close()
        self.r3d.close()
