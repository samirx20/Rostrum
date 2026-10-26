"""Rostrum2D's document bridge: the kit's DocBridge plus time, the tool (move, pen, draw), the layer rows, the
canvas frame and the two drags (move a layer on the canvas, move a key on the timeline). Every change is an operation; each drag is
one doc.gesture = one undo step. How an edit becomes a call lives in route.py only.
"""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot
from rostrum_gui import DocBridge, effects, news
from rostrum_gui.live_link import LiveLink
from rostrum_gui.markers import MarkerWatch
from rostrum_core import live, marker_times
from rostrum_core.tree import index
from rostrum2d import fields as F, ops_timing, placement, project_sound, retime
from rostrum2d.scene_keep import Keeper

from . import bounds, colour_feed, outline, picture_change, route, screen_seen
from .drags import DragSlots
from .command_words import CommandWords
from .file_commands import FileCommands
from .key_routes import KeyRoutes
from .view_commands import ViewCommands
from .frames import FrameRenderer
from .group_slots import GroupSlots
from .anchor_slots import AnchorSlots
from .handle_slots import HandleSlots
from .hooks import Hooks2D
from .action_slots import ActionSlots
from .action_preview import PREVIEW_TAG, ActionPreview
from .agent_view import AgentView
from .layer_order import LayerOrder
from .painter import Painter
from .painting_open import OpenedPainting
from .paint_edge import PaintEdge
from .paint_pictures import PaintPictures
from .frame_view import FrameView
from .world_view import WorldView
from .outline_news import OutlineNews
from .reveal_ahead import RevealAhead
from .playback import Playback, size_offered
from .playstats import STATS
from .clipboard import ClipboardSlots
from .scenes import SceneSlots
from .key_edits import KeyEdits
from .render3d_watch import Render3DWatch
from .shown import ShownState
from .sound_cue_pick import CuePick
from .soundtrack import Soundtrack
from .timeline_rows import TimelineRows
from .tools2d import ToolSlots
from .typed_edits import TypedEdits
from .undo_state import UndoState


TOOLS = ("move", "pen", "draw", *F.SHAPE_KINDS, "text", "bone", "hand", "zoom")   # what the mouse does on the canvas (setTool)




class Bridge2D(AgentView, ShownState, TimelineRows, KeyEdits, ClipboardSlots, SceneSlots, UndoState, ActionSlots, KeyRoutes, ActionPreview, LayerOrder, FileCommands, ViewCommands, CommandWords, DragSlots, HandleSlots, AnchorSlots, GroupSlots, ToolSlots, TypedEdits, Hooks2D, DocBridge):
    timeChanged = Signal()
    toolChanged = Signal()
    frameChanged = Signal()
    shownChanged = Signal()                                 # a new frame is on screen: the overlays follow it (shown.py)
    outlineChanged = Signal()
    rowFactsChanged = Signal()                              # what the timeline asks of its rows differs (row_facts.py)
    layersChanged = Signal()                                # the timeline's rows really changed (timeline_rows.py)
    layerChanged = Signal()                                 # selectedLayer is another layer (sent with outlineChanged, only then)
    frameInfoChanged = Signal()                             # the scene's size, rate, length or label changed (the same)
    playingChanged = Signal()
    _sel_layer = None                                       # (document state, selection, its layer): selectedLayer
    _comp_at = _placed_idx = None                           # comp() and placed_item()'s, kept per document state
    _asked_from = None                                      # (placed, index) the last picture was asked for
    markersChanged = Signal()
    viewRequested = Signal(str)                             # Ctrl+K's view commands: the view menu's step (view_commands.py)
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
        self._outline_paced = news.OnceAFrame(self.outlineChanged.emit, self)   # a drag's steps (_on_doc)
        self._outline_news = OutlineNews(self)              # a change's or a pick's: the frame after (outline_news.py)
        self.outlineChanged.connect(self._layers_check)     # first: every later listener reads the new rows
        self.outlineChanged.connect(self._outline_check)    # then selectedLayer / frameInfo, each sent only on news
        self._told = (None, None)
        self.frames = FrameRenderer(self)
        self._scene = None                                  # the engine's scene, described once per change (_render)
        self._keeper = Keeper()                             # ... again only where the change touched (scene_keep.py)
        self._waiting = None                                # the document state whose paint pictures are being made
        self._ahead = None                                  # ... whose pictures are made while stand-ins show (write_on.Ahead)
        self._ahead_jobs, self._ahead_at = [], None         # (those pictures, and the playhead they were ordered for)
        self._pictures = PaintPictures(self)                # ... off this thread (paint_pictures.py)
        self._pictures.done.connect(self._pictures_made)
        self._pictures.failed.connect(self._fail)
        self._time_due = False                              # playing: the playhead waits for its picture (setTime)
        self.held_view = None                               # a camera-key drag: the scene as at the press (motion_path.py)
        self.frames.ready.connect(self._on_frame)
        self.frames.failed.connect(self._fail)
        self.frames.note.connect(self._set_status)         # no graphics driver: said once (frames.py)
        self._opened = OpenedPainting(self)                 # a painting opened on its own (painting_open.py)
        self.painter = Painter(self)
        self._paint_edge, self._world = PaintEdge(self), WorldView(self)   # paint_edge.py, world_view.py
        self.painter.ahead = RevealAhead(self.painter, self)      # the eraser's reveal, drawn before the press (reveal_ahead.py)
        self.frames.pictured.connect(self._world.shown)
        self._frame_view = FrameView(self)                  # frame_view.py
        self._make_tools()                                  # pen, curves, export, import, add, problems (tools2d.py)
        self.play = Playback(self)                          # playing: follows the clock (playback.py)
        self.play.changed.connect(self.playingChanged)
        self.marks = MarkerWatch(doc.folder, self, self.who, self._fail, "2d")   # shared markers: flags, edits, snap
        ops_timing.use_project(doc.folder)                  # every operation's "#drop" reads this project's markers
        self.marks.changed.connect(self.markersChanged)
        self.marks.changed.connect(self._layers_check)      # keys timed on a marker move with it
        self.marks.changed.connect(lambda: self.model.update(self._rows()))   # the marker picks list them
        self._marker_saved()                                # (remembers the last change: only later ones are announced)
        self.marks.changed.connect(self._marker_saved)
        self.join_history(self.marks)                       # marker edits undo with the screen's one history
        self._host = placement.Host(self.frames.place, lambda: self.marks.times, lambda: doc.folder)
        placement.use(self._host)                           # comp-px strokes and spatial staggers ask the canvas's engine
        self._where = route.use(self.placed_item, self.offset, lambda: self.comp()["fps"])   # marker keys at the playhead (route.py)
        self.model.update(self._rows())
        self.marks.changed.connect(self._render_all)        # expressions may read marker("…")
        self.marks.changed.connect(self._problems.touch)
        self.r3d = Render3DWatch(self, self)                # a 3D render layer follows its item's newest render
        self.r3d.changed.connect(self._render_all)          # a render the document can't see: described afresh
        self.r3d.changed.connect(self._problems.touch)
        self._soundtrack = Soundtrack(self)                 # the project's sound, played by Sound's engine (soundtrack.py)
        self._cuepick = CuePick(self, self)                 # Add a sound here… (sound_cue_pick.py)
        self.selectedItemsChanged.connect(self._outline_news.soon)
        self.selectedItemsChanged.connect(self.shownChanged)
        self.rowsChanged.connect(self.anchorOpenChanged)       # the Anchor group opened or folded (anchor_slots.py)
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

    opened = Property(QObject, lambda self: self._opened, constant=True)         # a painting open on its own (painting_open.py)
    paintEdge = Property(QObject, lambda self: self._paint_edge, constant=True)   # the paint target's edge (paint_edge.py)
    world = Property(QObject, lambda self: self._world, constant=True)           # the world picture on the canvas (world_view.py)
    frameView = Property(QObject, lambda self: self._frame_view, constant=True)   # the frame's box on the canvas (frame_view.py)
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
        Worked out once per document, markers and scene shown (every change gives a new doc.data, every marker read a new
        marks.times, showing another scene a new comp_id), not on every read: rows, outline and drags read it many times a
        frame. Callers only read it."""
        data, times, got = self.doc.data, self.marks.times if self.marks else None, self._placed
        if got is None or got[0][0] is not data or got[0][1] is not times or got[2] != self.comp_id:
            self._placed = got = ((data, times), retime.timed(self.comp(), self.times(), self.comp()["fps"]), self.comp_id)
        return got[1]

    def placed_item(self, id_: str) -> dict:
        """One item of `placed()` (a layer, effect, mask or key owner), its times in composition seconds."""
        found = self.placed_index()[1].get(id_)
        return found.item if found else self.doc.item(id_)

    def placed_index(self) -> tuple:
        """(placed(), its index by id), worked out once per document and markers. A scene with nothing timed from a marker
        is placed as it is: the document's own index (kept by every edit) is its index, no walk of the scene."""
        placed = self.placed()
        if self._placed_idx is None or self._placed_idx[0] is not placed:
            own = placed is self.comp()
            self._placed_idx = (placed, self.doc.locs() if own else index(placed, self.doc.kind.lists))
        return self._placed_idx

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

    def _outline_check(self):
        """selectedLayer and frameInfo are their own signals: on outlineChanged, every binding reading them (the panels
        read selectedLayer hundreds of times) ran again on every edit."""
        layer, info = self.selectedLayer, self.frameInfo
        if layer != self._told[0]:
            self._told = (layer, self._told[1])
            self.layerChanged.emit()
        if info != self._told[1]:
            self._told = (self._told[0], info)
            self.frameInfoChanged.emit()

    @Property("QVariantMap", notify=frameInfoChanged)
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

    @Property("QVariantMap", notify=rowFactsChanged)
    def rowFacts(self):
        """What the timeline asks of its rows besides drawing them (rostrum_gui/row_facts.py): QML reads this, not `layers`."""
        return self.row_facts()

    @Property(QObject, constant=True)
    def rowsModel(self):
        """The timeline's rows as a list model, changed row by row (timeline_rows.py): what the Animate timeline shows."""
        return self.row_models()[0]

    @Property(QObject, constant=True)
    def rowsCompact(self):
        """The same, only the selected layer's row (the first layer's when none is selected): the small timeline."""
        return self.row_models()[1]

    @Property(str, notify=layerChanged)
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
        return next(iter(self.shown_boxes([layer])), {})

    def _first(self):
        """Nothing picked (a piece opening, the picked layers gone): the scene, its settings in the panel (camera SPEC
        mock-1). Never a layer, the frame least of all: picked, a drag anywhere on the picture moves the whole shot."""
        return self.comp_id

    # ---- screen state -----------------------------------------------------------------------------------------
    @Slot(float)
    def setTime(self, t):
        c = self.comp()
        self._t = min(max(round(t * c["fps"]) / c["fps"], 0.0), c["duration"])
        if self.play.playing:                    # only the playhead and the frame, moving together (playback.py):
            self._time_due = True                # the playhead moves when this time's picture arrives
            if not self._show():
                self._time_moves()
            return
        self.timeChanged.emit()
        if not self.play.moved_by_hand():        # a scrub's panels wait until it rests (time_rests)
            self._follow_time()
        self._show()

    def time_rests(self):
        """A scrub came to rest (playback.py): the full frame, and the panels at the playhead."""
        self._follow_time()
        self._show()

    def _follow_time(self):
        """The panel's values and what follows the outline at the playhead: the frame after (outline_news.py), the
        picture asked first."""
        self._rows_due().ask()
        self._outline_news.soon()

    def _time_moves(self):
        if self._time_due:
            self._time_due = False
            self.timeChanged.emit()

    @Slot(str)
    def setTool(self, tool):
        """The one tool switch (the rail, V / P / B / Esc, pen.setOn, Add path / drawing). Leaving the pen ends its path."""
        if tool not in TOOLS:
            return self._fail(f"Error: tool: {tool!r} is not a tool ({', '.join(TOOLS)}).")
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

    @Slot(str)
    def select(self, item_id):
        """One item ("" = none). The painting open on its own is where you are, not something picked (its timeline
        row and cells select it): nothing changes. A layer picked by its name, its bar or Ctrl+K: the pick is about
        layers, picked keys go (key_select.py, also when it was picked already)."""
        opened = getattr(self, "_opened", None)          # (the kit selects the first item before it is made)
        if not (item_id and opened is not None and item_id == opened.id):
            if getattr(self, "_keys", None) is not None:
                self._keys.clear()
            super().select(item_id)

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

    def drawn(self) -> bool:
        """The document's own picture is on screen: a frame landed, none is being drawn, and no paint picture of the
        state shown is still being made (until then the frame shows the last ones; a scripted picture waits for this), and
        no scrub is still moving (its pictures are the moving kind: playback.py)."""
        return self.frames.idle() and self._frame > 0 and self._waiting is None and self._ahead is None and not self.play.scrubbing

    def _render_all(self):
        """Something outside the document changed (the markers, a 3D render): every node is described again."""
        self._keeper.forget()
        self._render()

    def _show(self) -> bool:
        """The frame at the playhead. The scene doesn't depend on the playhead (the engine evaluates every time), so it
        is described once per change, never per frame: playing and scrubbing only send `t`. False: no picture asked."""
        self._previewing = False                            # the document's own picture is drawn again (action_preview.py)
        if self._scene is None:
            later = []
            try:        # a 3D render layer's render missing, a video file gone …: said on screen, no frame drawn
                with STATS.stage("describe"):
                    self._scene = self._keeper.describe(self.doc.data, self.comp_id, self.marks.times, self.doc.folder,
                                                        (0.0, self.comp()["duration"]), later)
            except Exception as e:  # noqa: BLE001
                self._scene = False                         # tried; the next change tries again
                self._fail(str(e))
            waits = [job for job in later if not getattr(job, "ahead", False)]
            self._waiting = self.doc.data if waits and self._scene else None
            self._ahead = self.doc.data if later and not waits and self._scene else None
            self._ahead_at = None
            if self._waiting is not None:                   # the frame shown (and wet ink over it) stays meanwhile; only
                self._pictures.make(waits, self._waiting)   # those: Drawn so far's come after, drawn as they're made (2D r12:
                #                                             made with them, a new stroke stayed off the canvas ~30 s)
            self._ahead_jobs = later if self._ahead is not None else []     # drawn now with stand-ins (Drawn so far's
        if self._ahead is not None and self._ahead_at != self._t:          # frames: the whole drawing), again as its
            self._ahead_at = self._t                                       # pictures are made, those nearest the
            self._ahead_jobs.sort(key=lambda job: abs(job.at - self._t))   # playhead first (made ones are only read)
            self._pictures.make(list(self._ahead_jobs), self._ahead)
        if self._scene and self._waiting is None and self._ghost is not None and self._ghost.moved:
            self._ghost.draw()                              # a drag of many layers: drawn where they are now (ghost_move.py)
            return True
        if self._scene and self._waiting is None:
            self._asked_from = self.placed_index()          # what the picture asked for shows (picture_change.py)
            self.frames.request(self._scene, self._t, self.play.samples(), self.frame_scale(), self.frame_tag(),
                                **self.frame_extras())
            return True
        if self._shown is not None:                         # no picture for this state: the overlays go live
            self._shown = None
            self.shownChanged.emit()
        return False

    def _pictures_made(self, token):
        """The paint pictures of the state described last are made: described again (now with them) and drawn. A scene with
        paintings has its rows read again too: the Fill row and its picker show a painting's picture (fill_rows.picture)."""
        if token is self.doc.data and token in (self._waiting, self._ahead):
            self._waiting, self._ahead, self._scene = None, None, None
            if self.held_view is None:
                self._show()
            if self.doc.data.get("paintings"):
                self._refresh()

    def _on_frame(self, serial, tag):
        with STATS.stage("picture.arrives"):
            self._picture_arrives(serial, tag)

    def _picture_arrives(self, serial, tag):
        self._frame = serial
        self.frameChanged.emit()                            # the picture and the overlays change together
        self._time_moves()                                  # playing: the playhead with its picture (setTime)
        if tag == PREVIEW_TAG:                              # an action's hover preview: not the document, the overlays stay
            return
        self._frame_shown(tag)
        STATS.frame_shown(self._t)

    def _on_doc(self, event):
        self._note_change()
        self.scene_still_there()                            # Undo of New scene while it is shown: the first scene shows
        with STATS.stage("doc.kit"):
            super()._on_doc(event)
        with STATS.stage("doc.outline"):
            reached = self.reached(self.selection or [self.comp_id])     # the selection's overlays, bars and panels
            if event.kind == "preview":                     # a drag's step: the timeline's rows (the bar or key
                self._layers_check()                        # dragged) at once, the parts that follow the outline
                if reached:                                 # (panels, overlays) once per screen refresh
                    self._outline_paced.ask()
            else:                                           # the frame after (outline_news.py); a change elsewhere
                self._outline_paced.cancel()                # (an agent's, an undo): only the timeline's rows; the
                self._outline_news.soon(bool(reached))      # canvas overlays follow the new picture (shownChanged)
        if event.kind != "preview":                         # (a step's picture was asked before: _before_followers)
            with STATS.stage("doc.render"):
                self._render()
        self._problems.touch()

    def _before_followers(self, event):
        """A drag's step: its picture is asked first, so the engine draws it while the panels and overlays follow."""
        if event.kind != "preview":
            return
        with STATS.stage("doc.render"):
            if self._picture_changes():
                self._render()
            else:
                self._scene = None                          # the picture stays: it shows the same (picture_change.py)

    def _picture_changes(self) -> bool:
        """A drag's step changes the picture at the playhead (else the engine is not asked again)."""
        c = self.comp()
        blur = c.get("shutter", 0) > 0 and c.get("shutterSamples", 1) > 1
        return self.held_view is not None or picture_change.changes(
            self._asked_from, self.placed_index(), self.touched(), self._t, self.doc.kind.lists, blur)

    def close(self):
        if self.link:
            self.link.close()
        self.play.stop()
        self.marks.close()
        self.endDrag()
        self._outline_paced.cancel()                       # a drag's step still waiting: nothing left to tell
        self._outline_news.cancel()
        self._kit.paced.cancel()
        placement.drop(self._host)
        route.drop(self._where)
        self.frames.close()
        self._pictures.close()
        self._opened.close_down()
        self._problems.close()
        self._cuepick.close()
        self.r3d.close()
        self._soundtrack.close()
