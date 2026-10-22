"""Rostrum2D's document bridge: the kit's DocBridge plus time, the tool (move, pen, draw), the layer rows, the
canvas frame and the two drags (move a layer on the canvas, move a key on the timeline). Every change is an operation; each drag is
one doc.gesture = one undo step. How an edit becomes a call lives in route.py only.
"""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot
from rostrum_gui import DocBridge
from rostrum_gui.live_link import LiveLink
from rostrum_gui.markers import MarkerWatch
from rostrum_core import live, marker_times
from rostrum_core.tree import index
from rostrum2d import fields as F, retime

from . import bounds, outline, screen_seen
from .drags import DragSlots
from .command_words import CommandWords
from .file_commands import FileCommands
from .frames import FrameRenderer
from .handle_slots import HandleSlots
from .hooks import Hooks2D
from .action_slots import ActionSlots
from .agent_view import AgentView
from .layer_order import LayerOrder
from .painter import Painter
from .playback import Playback, size_offered
from .playstats import STATS
from .clipboard import ClipboardSlots
from .render3d_watch import Render3DWatch
from .shown import ShownState
from .tools2d import ToolSlots
from .undo_state import UndoState


TOOLS = ("move", "pen", "draw", "rect", "ellipse", "text")      # what the mouse does on the canvas (setTool)


class Bridge2D(AgentView, ShownState, ClipboardSlots, UndoState, ActionSlots, LayerOrder, FileCommands, CommandWords, DragSlots, HandleSlots, ToolSlots, Hooks2D, DocBridge):
    timeChanged = Signal()
    toolChanged = Signal()
    frameChanged = Signal()
    shownChanged = Signal()                                 # a new frame is on screen: the overlays follow it (shown.py)
    outlineChanged = Signal()
    playingChanged = Signal()
    markersChanged = Signal()
    renameRequested = Signal(str)                           # F2 / Ctrl+K "Rename layer": the layer row's name box
    sections = True                                         # settings panel: essentials, folded groups, search (kit)

    def __init__(self, doc, comp_id=None, autosave=False, parent=None):
        comps = doc.data.get("comps", [])
        if not comps:
            raise ValueError("the document has no composition yet (comp.add)")
        self.comp_id = comp_id or comps[0]["id"]
        self._t, self._tool, self._frame, self.autosave = 0.0, "move", 0, autosave
        self._flipped, self._drag, self._grab = set(), None, None      # rows folded / opened against their default
        self._anim_only = set()                             # layers opened by A: only their animated settings show
        self._placed = None                                 # placed(), kept per document and markers
        self.marks = None                                   # made below (it needs this QObject); the first rows have none
        self._shown_init()
        super().__init__(doc, parent=parent)
        self.frames = FrameRenderer(self)
        self._scene = None                                  # the engine's scene, described once per change (_render)
        self.frames.ready.connect(self._on_frame)
        self.frames.failed.connect(self._fail)
        self.frames.note.connect(self._set_status)         # no graphics driver: said once (frames.py)
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
        self.selectionChanged.connect(self.shownChanged)
        self.link = None
        if autosave and doc.folder:                         # live (--doc): one door for every save, shared with agents' servers
            live.keep(doc)
            self.link = LiveLink(self, "2d", screen_seen.state)
        self._make_actions()                                # the one action list's hub: bar, menus, Ctrl+K, keys
        self._render()
        self._problems.touch()

    isLive = Property(bool, lambda self: self.link is not None, constant=True)   # saved after every change: the top bar says "Saved"

    actions = Property(QObject, lambda self: self._hub, constant=True)   # the context bar, menus, keys (action_slots.py)

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

    @Property(str, notify=toolChanged)
    def tool(self):
        """What the mouse does on the canvas: "move" (select, move, handles), "pen" (pen.py), "draw" (painter.py), or "rect" / "ellipse" / "text" (create.py)."""
        return self._tool

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
        """The timeline's rows, which are the layers list too (outline.rows): bars, keys, frames, fields, effects."""
        return outline.rows(self.placed(), self._flipped, self._anim_only)

    @Property(str, notify=outlineChanged)
    def selectedLayer(self):
        """The layer the selection belongs to (itself, or the layer of a selected effect, mask or key)."""
        return bounds.layer_of(self.doc, self._sel) if self._sel else ""

    @Property("QVariantMap", notify=shownChanged)
    def selBox(self):
        """The selected layer's box as the picture on screen shows it (shown.py)."""
        layer = self.selectedLayer
        return next((b for b in bounds.boxes(self.shown_placed(), self.shown_t()) if b["id"] == layer), {})

    def _first(self):
        layers = self.comp().get("layers", [])
        return layers[-1]["id"] if layers else self.comp_id

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
    def setTool(self, tool):
        """The one tool switch (the strip, V / P / B / Esc, pen.setOn, Add path / drawing). Leaving the pen ends its path."""
        if tool not in TOOLS:
            return self._fail(f"Error: tool: {tool!r} is not a tool ({', '.join(TOOLS)}).")
        if tool != self._tool:
            if self._tool == "pen":
                self._pen.finish()
            self._tool = tool
            self.toolChanged.emit()

    @Slot()
    def togglePlay(self):
        self.play.toggle()

    @Slot(str)
    def toggleFold(self, item_id):
        """Fold an open row, open a closed one (a group starts open, any other layer closed)."""
        self._flipped ^= {item_id}
        self._anim_only.discard(item_id)
        self.outlineChanged.emit()

    @Slot()
    def showAnimated(self):
        """A: the selected layers open to only their animated settings; A again folds them (UX_SPEC 3.12)."""
        layers = self.selected_layers()
        if layers and all(i in self._anim_only for i in layers):
            self._anim_only -= set(layers)
        else:
            self._anim_only |= set(layers)
        self.outlineChanged.emit()

    @Slot(float, float, result=str)
    def pickAt(self, x, y):
        """A click on the canvas (composition px): select what is painted there by the click rule (picking.py: the
        outermost group, or the piece once inside it); on empty canvas, the composition (its frame size, rate,
        length, background)."""
        return self._multi.pick(x, y, "click")

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
            self.frames.request(self._scene, self._t, self.play.samples(), self.frame_scale(), self.frame_tag())
        elif self._shown is not None:                       # no picture for this state: the overlays go live
            self._shown = None
            self.shownChanged.emit()

    def _on_frame(self, serial, tag):
        self._frame = serial
        self.frameChanged.emit()                            # the picture and the overlays change together
        self._frame_shown(tag)
        STATS.frame_shown(self._t)

    def _on_doc(self, event):
        self._note_change()
        super()._on_doc(event)
        self.outlineChanged.emit()
        self._render()
        self._problems.touch()

    def close(self):
        if self.link:
            self.link.close()
        self.play.stop()
        self.marks.close()
        self.endDrag()
        self.frames.close()
        self._problems.close()
        self.r3d.close()
