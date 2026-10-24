"""Rostrum2D's document bridge: the kit's DocBridge plus time, the tool (move, pen, draw), the layer rows, the
canvas frame and the two drags (move a layer on the canvas, move a key on the timeline). Every change is an operation; each drag is
one doc.gesture = one undo step. How an edit becomes a call lives in route.py only.
"""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot
from rostrum_gui import DocBridge, effects
from rostrum_gui.live_link import LiveLink
from rostrum_gui.markers import MarkerWatch
from rostrum_core import live, marker_times
from rostrum_core.tree import index
from rostrum2d import fields as F, placement, project_sound, retime

from . import bounds, colour_feed, outline, screen_seen
from .drags import DragSlots
from .command_words import CommandWords
from .file_commands import FileCommands
from .frames import FrameRenderer
from .group_slots import GroupSlots
from .handle_slots import HandleSlots
from .hooks import Hooks2D
from .action_slots import ActionSlots
from .action_preview import PREVIEW_TAG, ActionPreview
from .agent_view import AgentView
from .layer_order import LayerOrder
from .painter import Painter
from .paint_edge import PaintEdge
from .paint_pictures import PaintPictures
from .sharp import Sharp
from .playback import Playback, size_offered
from .playstats import STATS
from .clipboard import ClipboardSlots
from .key_edits import KeyEdits
from .render3d_watch import Render3DWatch
from .shown import ShownState
from .sound_cue_pick import CuePick
from .soundtrack import Soundtrack
from .timeline_rows import TimelineRows
from .tools2d import ToolSlots
from .undo_state import UndoState


TOOLS = ("move", "pen", "draw", *F.SHAPE_KINDS, "text", "camera", "bone", "hand", "zoom")   # what the mouse does on the canvas (setTool)




class Bridge2D(AgentView, ShownState, TimelineRows, KeyEdits, ClipboardSlots, UndoState, ActionSlots, ActionPreview, LayerOrder, FileCommands, CommandWords, DragSlots, HandleSlots, GroupSlots, ToolSlots, Hooks2D, DocBridge):
    timeChanged = Signal()
    toolChanged = Signal()
    frameChanged = Signal()
    viewGlide = Signal("QVariantList")                     # a camera key was dropped: the box the new view starts from (camera_glide.py)
    shownChanged = Signal()                                 # a new frame is on screen: the overlays follow it (shown.py)
    outlineChanged = Signal()
    layersChanged = Signal()                                # the timeline's rows really changed (timeline_rows.py)
    playingChanged = Signal()
    _sel_layer = None                                       # (document state, selection, its layer): selectedLayer
    _comp_at = _placed_idx = None                           # comp() and placed_item()'s, kept per document state
    markersChanged = Signal()
    renameRequested = Signal(str)                           # F2 / Ctrl+K "Rename layer": the layer row's name box
    sections = True                                         # settings panel: essentials, folded groups, search (kit)

    def __init__(self, doc, comp_id=None, parent=None):
        comps = doc.data.get("comps", [])
        if not comps:
            raise ValueError("the document has no composition yet (comp.add)")
        self.comp_id = comp_id or comps[0]["id"]
        self._t, self._tool, self._frame = 0.0, "move", 0
        self._flipped, self._drag, self._grab = set(), None, None      # rows folded / opened against their default
        self._anim_only = set()                             # layers opened by A: only their animated settings show
        self._placed = None                                 # placed(), kept per document and markers
        self.marks = None                                   # made below (it needs this QObject); the first rows have none
        self._shown_init()
        super().__init__(doc, parent=parent)
        self.outlineChanged.connect(self._layers_check)     # first: every later listener reads the new rows
        self.frames = FrameRenderer(self)
        self._scene = None                                  # the engine's scene, described once per change (_render)
        self._waiting = None                                # the document state whose paint pictures are being made
        self._pictures = PaintPictures(self)                # ... off this thread (paint_pictures.py)
        self._pictures.done.connect(self._pictures_made)
        self._pictures.failed.connect(self._fail)
        self.held_view = None                               # a camera-key drag: the scene as at the press (motion_path.py)
        self.frames.ready.connect(self._on_frame)
        self.frames.failed.connect(self._fail)
        self.frames.note.connect(self._set_status)         # no graphics driver: said once (frames.py)
        self.painter = Painter(self)
        self._paint_edge, self._sharp = PaintEdge(self), Sharp(self, self.frames)   # paint_edge.py, sharp.py
        self._make_tools()                                  # pen, curves, export, import, add, problems (tools2d.py)
        self.play = Playback(self)                          # playing: follows the clock (playback.py)
        self.play.changed.connect(self.playingChanged)
        self.marks = MarkerWatch(doc.folder, self, self.who, self._fail, "2d")   # shared markers: flags, edits, snap
        self.marks.changed.connect(self.markersChanged)
        self.marks.changed.connect(self._layers_check)      # keys timed on a marker move with it
        self.marks.changed.connect(lambda: self.model.update(self._rows()))   # the marker picks list them
        self._marker_saved()                                # (remembers the last change: only later ones are announced)
        self.marks.changed.connect(self._marker_saved)
        self.join_history(self.marks)                       # marker edits undo with the screen's one history
        self._host = placement.Host(self.frames.place, lambda: self.marks.times, lambda: doc.folder)
        placement.use(self._host)                           # comp-px strokes and spatial staggers ask the canvas's engine
        self.model.update(self._rows())
        self.marks.changed.connect(self._render)            # expressions may read marker("…")
        self.marks.changed.connect(self._problems.touch)
        self.r3d = Render3DWatch(self, self)                # a 3D render layer follows its item's newest render
        self.r3d.changed.connect(self._render)
        self.r3d.changed.connect(self._problems.touch)
        self._soundtrack = Soundtrack(self)                 # the project's sound, played by Sound's engine (soundtrack.py)
        self._cuepick = CuePick(self, self)                 # Add a sound here… (sound_cue_pick.py)
        self.selectedItemsChanged.connect(self.outlineChanged)
        self.selectedItemsChanged.connect(self.shownChanged)
        self.link = None
        if doc.folder and doc.item_id:                     # live: one door for every save, shared with agents' servers
            live.keep(doc)
            self.link = LiveLink(self, "2d", screen_seen.state)
        self._make_actions()                                # the one action list's hub: bar, menus, Ctrl+K, keys
        effects.attach(self, effects.EffectsSpec(           # the panel's "Effects (n) +" (the kit's row; PANEL.md)
            types=[effects.EffectType(e, F.LABELS[e]) for e in F.EFFECTS if e != "gradient"],   # a gradient is a fill now
            kinds=tuple(t for t in F.LAYERS if t != "camera"), label=lambda eff: F.LABELS[eff["type"]]))
        colour_feed.attach(self)                            # the colour pickers' project and brand swatches
        self._render()
        self._problems.touch()

    isLive = Property(bool, lambda self: self.link is not None, constant=True)   # saved after every change: the top bar says "Saved"

    paintEdge = Property(QObject, lambda self: self._paint_edge, constant=True)   # the paint target's edge (paint_edge.py)
    sharp = Property(QObject, lambda self: self._sharp, constant=True)           # past Full, drawn sharp (sharp.py)
    actions = Property(QObject, lambda self: self._hub, constant=True)   # the context bar, menus, keys (action_slots.py)
    soundtrack = Property(QObject, lambda self: self._soundtrack, constant=True)   # the Sound row, beats (soundtrack.py)
    cuePick = Property(QObject, lambda self: self._cuepick, constant=True)       # Add a sound here… (sound_cue_pick.py)

    def open_item(self, item_id):
        """Undo / Redo of a step that reached Sound's song (Add a sound here): the song opened live (project_sound)."""
        return project_sound.open_item(self.doc.folder, item_id)

    # ---- reads for QML ----------------------------------------------------------------------------------------
    def comp(self) -> dict:
        got, data = self._comp_at, self.doc.data              # asked thousands of times per pen stroke: once per state
        if got is None or got[0] is not data or got[1] != self.comp_id:
            got = self._comp_at = (data, self.comp_id, self.doc.item(self.comp_id))
        return got[2]

    def times(self) -> dict:
        """The project's shared markers {name: seconds} (keys timed on a marker are placed through them)."""
        if self.marks is not None:                          # the watch's own copy: no file look per call (it polls)
            return self.marks.times
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
        placed = self.placed()
        if self._placed_idx is None or self._placed_idx[0] is not placed:
            self._placed_idx = (placed, index(placed, self.doc.kind.lists))
        found = self._placed_idx[1].get(id_)
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
        """Playing's settings (Motion blur while playing, in the canvas view menu): screen2d/playback.py."""
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

    @Property("QVariantList", notify=layersChanged)
    def layers(self):
        """The timeline's rows, which are the layers list too (outline.rows): bars, keys, frames, fields, effects.
        Announced only when they change (timeline_rows.py)."""
        return self.layer_rows()

    @Property(QObject, constant=True)
    def rowsModel(self):
        """The timeline's rows as a list model, changed row by row (timeline_rows.py): what the Animate timeline shows."""
        return self.row_models()[0]

    @Property(QObject, constant=True)
    def rowsCompact(self):
        """The same, only the selected layer's row (the first layer's when none is selected): the small timeline."""
        return self.row_models()[1]

    @Property(str, notify=outlineChanged)
    def selectedLayer(self):
        """The layer the selection belongs to (itself, or the layer of a selected effect, mask or key). The panels ask
        hundreds of times per change, so it is worked out once per document state and selection (a document is never
        changed in place: each change is a new tree)."""
        got, data, sel = self._sel_layer, self.doc.data, self._sel
        if got is None or got[0] is not data or got[1] != sel:
            got = self._sel_layer = (data, sel, bounds.layer_of(self.doc, sel) if sel else "")
        return got[2]

    @Property("QVariantMap", notify=shownChanged)
    def selBox(self):
        """The selected layer's box as the picture on screen shows it (shown.py)."""
        layer = self.selectedLayer
        return next((b for b in self.shown_boxes() if b["id"] == layer), {})

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
        """The one tool switch (the rail, V / P / B / Esc, pen.setOn, Add path / drawing). Leaving the pen ends its path."""
        if tool not in TOOLS:
            return self._fail(f"Error: tool: {tool!r} is not a tool ({', '.join(TOOLS)}).")
        if tool == "camera" and not self._camera.available:
            return self._fail("Error: camera: this scene has no camera; the rail's Camera adds one.")
        if tool == "bone" and not self._bone_tool.available:
            return self._fail("Error: bone: select a rig first (Make rig on a character's parts).")
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
        """The document, the markers or a 3D render changed: describe the scene again, then show the playhead. While a
        camera-key drag holds the view (`held_view`), the picture stays as at the press and is drawn once at the drop."""
        self._scene = None
        if self.held_view is None:
            self._show()

    def _show(self):
        """The frame at the playhead. The scene doesn't depend on the playhead (the engine evaluates every time), so it
        is described once per change, never per frame: playing and scrubbing only send `t`."""
        from rostrum2d.scene import describe
        self._previewing = False                            # the document's own picture is drawn again (action_preview.py)
        if self._scene is None:
            later = []
            try:        # a 3D render layer's render missing, a video file gone …: said on screen, no frame drawn
                with STATS.stage("describe"):
                    self._scene = describe(self.doc.data, self.comp_id, self.marks.times, self.doc.folder,
                                           (0.0, self.comp()["duration"]), later)
            except Exception as e:  # noqa: BLE001
                self._scene = False                         # tried; the next change tries again
                self._fail(str(e))
            self._waiting = self.doc.data if later and self._scene else None
            if self._waiting is not None:                   # the frame shown (and wet ink over it) stays meanwhile
                self._pictures.make(later, self._waiting)
        if self._scene and self._waiting is None:
            self.frames.request(self._scene, self._t, self.play.samples(), self.frame_scale(), self.frame_tag(),
                                **self.frame_extras())
        elif self._shown is not None:                       # no picture for this state: the overlays go live
            self._shown = None
            self.shownChanged.emit()

    def _pictures_made(self, token):
        """The paint pictures of the state described last are made: described again (now with them) and drawn."""
        if token is self._waiting and token is self.doc.data:
            self._waiting, self._scene = None, None
            if self.held_view is None:
                self._show()

    def _on_frame(self, serial, tag):
        self._frame = serial
        self.frameChanged.emit()                            # the picture and the overlays change together
        if tag == PREVIEW_TAG:                              # an action's hover preview: not the document, the overlays stay
            return
        self._frame_shown(tag)
        STATS.frame_shown(self._t)

    def _on_doc(self, event):
        self._note_change()
        super()._on_doc(event)
        if self.reached(self.selection or [self.comp_id]):     # the selection's overlays, bars and panels
            self.outlineChanged.emit()
        else:                                               # a change elsewhere (an agent's, an undo): only the
            self._layers_check()                            # timeline's rows (outline's first listener); the canvas
                                                            # overlays follow the new picture (shownChanged)
        self._render()
        self._problems.touch()

    def close(self):
        if self.link:
            self.link.close()
        self.play.stop()
        self.marks.close()
        self.endDrag()
        placement.drop(self._host)
        self.frames.close()
        self._pictures.close()
        self._problems.close()
        self._cuepick.close()
        self.r3d.close()
        self._soundtrack.close()
