"""RostrumSound's document bridge: the kit's DocBridge plus pages, the playhead, the arrangement and piano roll
(timeline.py), what is under the pointer (pick.py), the drags (one doc.gesture = one undo step) and the sound
(transport.py: rendered by the engine after each change, played from the playhead).

The slots live in small mix-ins (gui-kit README › parts.py): view_slots (playhead, zoom), picture_slots, song_slots
(music map), lane_slots (automation), edit_slots (edits and drags); the signals in signals.py. Every change is an
operation (moves.py builds the calls). The Mix page reads `lastRender` (the engine's render answer, with stems for
every track) and listens to `renderChanged`. The project's shared markers are watched (MarkerWatch): one moved or
renamed in another app re-renders the sound, and a rename is followed as one recorded step (marker.follow).
"""
from __future__ import annotations

from PySide6.QtCore import Property, Slot
from rostrum_gui import DocBridge
from rostrum_gui.markers import MarkerWatch
from rostrum_sound import compile as compile_doc
from rostrum_sound.doc import markers as MK
from rostrum_sound.doc import ops_mix

from . import inspect, lanes, onpage, picture, pick, timeline
from .edit_slots import EditSlots
from .lane_slots import LaneSlots
from .picture_slots import PictureSlots
from .signals import SoundSignals as S
from .song_slots import SongSlots
from .transport import Transport
from .view import View
from .view_slots import ViewSlots

PAGES = ("instruments", "timeline", "mix")
SOUNDING = ("notes", "hits", "clips", "sounds")       # what makes a compiled track last (engine contract/track.rs)


class SoundBridge(ViewSlots, PictureSlots, SongSlots, LaneSlots, EditSlots, S, DocBridge):
    def __init__(self, doc, name="Untitled song", autosave=False, parent=None):
        self.name, self.autosave = name, autosave
        self._page, self._t, self._track = "timeline", 0.0, ""
        self._drag = self._grab = None
        self._view: dict = {}
        self._fitted: set[str] = set()      # tracks the piano roll has already framed once
        self._zoom = View()                 # which stretch of the song is on screen (screen state, not an edit)
        self._open: dict = {}               # track id -> (item id, lane) of the automation lane shown under its row
        self._edit = None                   # the automation point being dragged (lanes.PointEdit)
        self._apt: tuple | None = None      # the selected automation point: (track id, item id, lane, index)
        self._picture_open = False
        MK.use_project(doc.folder)          # the screen works in this document's project (its shared markers)
        super().__init__(doc, parent=parent)
        self._picture_open = bool(self.doc.data.get("picture"))     # the corner opens by itself on a song with a picture
        self._follow_render = picture.Follow(lambda: (self.pictureChoice, self.doc.folder), self)
        self._follow_render.changed.connect(self.timelineChanged)       # the linked item has a newer render
        self._marks = MarkerWatch(self.doc.folder, self, self.who, self._fail, "sound")
        self._marks.changed.connect(self._markers_changed)
        self.join_history(self._marks)                      # marker edits undo with the screen's one history
        self.selectionChanged.connect(self._follow_selection)
        self.selectionChanged.connect(self._drop_point)
        self._follow_selection()
        self._rebuild()
        self.transport = Transport(self._schedule, self._length, self)
        self.transport.playingChanged.connect(self.playingChanged)
        self.transport.renderChanged.connect(self.renderChanged)
        self.transport.stateChanged.connect(self.soundChanged)
        self.transport.failed.connect(self._fail)
        self.transport.moved.connect(self._moved)
        self.transport.render()

    # ---- reads for QML ----------------------------------------------------------------------------------------
    @Property(str, constant=True)
    def docName(self):
        return self.name

    @Property(str, notify=S.pageChanged)
    def page(self):
        return self._page

    @Property(float, notify=S.timeChanged)
    def time(self):
        return self._t

    @Property(bool, notify=S.playingChanged)
    def playing(self):
        return self.transport.playing

    @Property("QVariantMap", notify=S.timelineChanged)
    def song(self):
        return self._view["song"]

    @Property("QVariantList", notify=S.timelineChanged)
    def tracks(self):
        return self._view["rows"]

    @Property("QVariantList", notify=S.timelineChanged)
    def markers(self):
        return self._view["markers"]

    @Property("QVariantMap", notify=S.timelineChanged)
    def roll(self):
        """The piano roll of the selection's track (or the last one picked)."""
        return self._view["roll"]

    @Property("QVariantMap", notify=S.renderChanged)
    def lastRender(self):
        return self.transport.last

    @Property(str, notify=S.soundChanged)
    def soundState(self):
        """A short line about the sound: rendering, no output on this machine, or that the render failed."""
        return self.transport.state

    @Slot(str, float, float, float, result=str)
    def blockAt(self, track_id, t, lane, tol):
        """The note / hit / clip under the pointer in an arrangement row ("" when none)."""
        row = next((r for r in self._view["rows"] if r["id"] == track_id), None)
        return pick.block_at(row["blocks"], t, lane, tol, 0.3) if row else ""

    @Slot(float, float, float, result=str)
    def rollAt(self, t, row, tol):
        """The note / hit / clip under the pointer in the piano roll ("" when none)."""
        return pick.roll_at(self._view["roll"], t, row, tol)

    # ---- the kit's hooks: names, times shown in seconds but written in the item's own form, fields on the page --
    def label_of(self, item):
        return inspect.label(item)

    def shown_values(self, item):
        return inspect.shown(item, self.doc.data)

    def edit_call(self, item_id, param, value):
        return inspect.edit_call(self.doc, item_id, param, value)

    def on_page(self, item):        # the inspector leaves out what the page's own controls show (onpage.py)
        return onpage.fields(self._page, item.get("type", ""), self.doc.kind.registry)

    # ---- screen state -----------------------------------------------------------------------------------------
    @Slot(str)
    def setPage(self, page):
        if page not in PAGES:
            return self._fail(f'Error: page: "{page}" is not a page ({", ".join(PAGES)}).')
        self._page = page
        self.model.reset(self._rows())
        self.pageChanged.emit()

    @Slot()
    def togglePlay(self):
        self.transport.toggle(self._t)

    # ---- inside -----------------------------------------------------------------------------------------------
    def _follow_selection(self):
        """The piano roll follows the selection's track (a marker or the master keeps the last one)."""
        i = self._sel
        while i and self.doc.has(i) and self.doc.item(i)["type"] not in ("track", "doc", "master", "marker"):
            i = self.doc.parent_of(i)[0]
        if i and self.doc.has(i) and self.doc.item(i)["type"] == "track":
            self._track = i
        elif not (self._track and self.doc.has(self._track)):
            self._track = next((t["id"] for t in self.doc.data.get("tracks", [])), "")
        if self._view:
            self._rebuild()

    def _schedule(self) -> dict:
        """The compiled song. A song with nothing in it yet (a new one, or an instrument with no notes) is still a
        song: it renders as silence the length the screen shows, instead of the engine refusing an empty schedule."""
        s = compile_doc(self.doc)
        if "length" not in s and not any(t.get(k) for t in s["tracks"] for k in SOUNDING):
            s["length"] = self._length()
        return s

    def _length(self) -> float:
        return self._view["song"]["length"]

    def _frame_new_track(self):
        """The first time a track is shown, fit the view to its sounds (a short phrase is not a speck at the left).
        Only while the view is still the screen's own: a person's zoom is left alone."""
        if not self._track or self._track in self._fitted:
            return
        self._fitted.add(self._track)
        blocks = self._view["roll"]["blocks"]
        if blocks and (self._zoom.fit or self._zoom.auto):
            self._zoom.fit_to(min(b["t"] for b in blocks), max(b["t"] + b["dur"] for b in blocks), self._length())

    def _markers_changed(self):
        """A project marker moved, was renamed or deleted (in 2D, by an agent …): follow renames as one recorded
        step, then redraw and render again. A deleted marker the song uses is reported loudly by the render."""
        def go():
            follow = ops_mix.follow_calls(self.doc.data)
            if follow:
                self._apply(follow, "Follow renamed markers")       # a change: _on_doc redraws and re-renders
            else:
                self._rebuild()
                self.transport.changed()
        self._guard(go)

    def _rebuild(self):
        root = self.doc.data
        self._open = {k: v for k, v in self._open.items() if self.doc.has(k)
                      and v in lanes.applicable(self.doc.item(k), root)}
        rows = timeline.rows(root, self._open)
        hue = next((r["hue"] for r in rows if r["id"] == self._track), timeline.HUES[0])
        track = self.doc.item(self._track) if self._track and self.doc.has(self._track) else None
        self._view = {"rows": rows, "markers": timeline.markers(root), "song": timeline.song(root),
                      "roll": timeline.roll(track, root, hue)}
        self._zoom.clamp(self._length())
        self._frame_new_track()
        self.timelineChanged.emit()
        self.viewChanged.emit()

    def _on_doc(self, event):
        super()._on_doc(event)
        self._guard(self._rebuild)
        if event.kind == "change":             # a drag renders once, when it lands
            self.transport.changed()
        if self.autosave and event.kind == "change":
            self._guard(self.doc.save)

    def close(self):
        self.endDrag()
        self._marks.close()
        self.transport.close()
