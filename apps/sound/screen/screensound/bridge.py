"""RostrumSound's document bridge: the kit's DocBridge plus the workspace (workspace.py: the bottom dock, the Sounds
panel), the playhead, the arrangement and piano roll
(timeline.py), what is under the pointer (pick.py), the drags (one doc.gesture = one undo step) and the sound
(transport.py: rendered by the engine after each change, played from the playhead).

The slots live in small mix-ins (gui-kit README › parts.py): view_slots (playhead, zoom), picture_slots, song_slots
(music map), lane_slots (automation), edit_slots (edits and drags), rows_view (the rows and the roll, made again
only where a change or a drag's step reached); the signals in signals.py. Every change is an
operation (moves.py builds the calls). The Mixer reads `lastRender` (the engine's render answer, with stems for
every track) and listens to `renderChanged`. The project's shared markers are watched (MarkerWatch): one moved or
renamed in another app re-renders the sound, and a rename is followed as one recorded step (marker.follow).
"""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot
from rostrum_gui import DocBridge, many, pointer_quiet
from rostrum_gui.after_frame import AfterFrame
from rostrum_gui.live_link import LiveLink
from rostrum_gui.markers import MarkerWatch
from rostrum_gui.model import RowsModel
from rostrum_gui.timeview import TimeViewObject
from rostrum_gui.touched import Touched
from rostrum_core import live
from rostrum_sound import clean_clips, compile as compile_doc
from rostrum_sound.doc import markers as MK
from rostrum_sound.doc import sounds
from rostrum_sound.doc import ops_mix

from . import voice_card
from .plain_errors import say as say_error
from . import block_patch, cleanable, feel_rows, inspect, many_rows, onpage, output_pick, picture, pick, screen_seen, timeline
from .action_slots import ActionSlots
from .agent_demo import AgentDemo
from .drum_rows import DrumRowSlots
from .edit_slots import EditSlots
from .grid_slots import GridSlots
from .group_slots import GroupSlots
from .handle_slots import HandleSlots
from .velocity_slots import VelocitySlots
from .key_slots import KeySlots
from .lane_slots import LaneSlots
from .picture_slots import PictureSlots
from .rows_view import RowsView
from .select_slots import SelectSlots
from .signals import SoundSignals as S
from .song_slots import SongSlots
from .transport import Transport
from .view_slots import ViewSlots
from .workspace import Workspace

SOUNDING = ("notes", "hits", "clips", "sounds")       # what makes a compiled track last (engine contract/track.rs)


class SoundBridge(AgentDemo, ViewSlots, PictureSlots, SongSlots, LaneSlots, DrumRowSlots, EditSlots, HandleSlots, VelocitySlots, GridSlots, GroupSlots, ActionSlots, KeySlots, SelectSlots, RowsView, S, DocBridge):
    songChanged = Signal()                  # the ruler's song (length, grid): its own signal, a drag's step rarely moves it
    def __init__(self, doc, name="Untitled song", parent=None):
        self.name = name
        self._asked = cleanable.Asked()     # clips whose Cleanup rows were asked for (cleanable.py)
        self._t, self._track = 0.0, ""
        # the dock changed what the inspector leaves out (onpage.py): its rows change in place, each keeping the
        # delegate that showed the same setting (a reset made every row's control again: ~45 ms per dock switch)
        self.workspace = Workspace(lambda line: self._fail(line), lambda: self.model.update(self._rows(), instant=True))
        self._drag = self._grab = None
        self._span = ("", 0, 0)             # the piano roll's keys shown (track, lo, hi): they only grow while a track stays open
        self._view: dict = {}
        self._made: dict = {}               # track id -> its row as last made, and the song it was made from (_shown):
        self._shown = None                  # a drag's step makes again only the tracks it changed (stepped.py)
        self._stepping = False              # a gesture is open (its steps came, its change not yet): the sound waits
        self._lanes = RowsModel(("track", "blocks"), None)   # the arrangement's rows by track id: a row that stays keeps its delegate
        self._held = block_patch.RowBlocks()  # each row's blocks as the row model holds them (patches since: rows_view)
        self._tv = TimeViewObject()         # which stretch of the song is on screen (screen state, not an edit)
        self._zoom = self._tv.view
        self._open: dict = {}               # track id -> (item id, lane) of the automation lane shown under its row
        self._edit = None                   # the automation point being dragged (lanes.PointEdit)
        self._apt: tuple | None = None      # the selected automation point: (track id, item id, lane, index)
        self._play_lane = "sustain"         # the Editor's playing lane (sustain, dynamics, bend): the person's view
        self._roll_later = AfterFrame(lambda: self._guard(self._show_roll))   # (made before the kit's first selection)
        self._picture_open = False
        MK.use_project(doc.folder)          # the screen works in this document's project (its shared markers)
        super().__init__(doc, parent=parent)
        self._lanes.setParent(self)
        self._roll_later.setParent(self)    # goes with this song (a freed song's job never runs: after_frame)
        self.link = None
        if doc.folder and doc.item_id:      # live: one door for every save, shared with agents' servers (rostrum_core.live)
            live.keep(doc)
            self.link = LiveLink(self, "sound", screen_seen.state)
        self._picture_open = bool(self.doc.data.get("picture"))     # the corner opens by itself on a song with a picture
        self._follow_render = picture.Follow(lambda: (self.pictureChoice, self.doc.folder), self)
        self._follow_render.changed.connect(self.pictureChanged)        # the linked item has a newer render
        self._marks = MarkerWatch(self.doc.folder, self, self.who, self._fail, "sound")
        self._marks.changed.connect(self._markers_changed)
        self.join_history(self._marks)                      # marker edits undo with the screen's one history
        self.selectedItemsChanged.connect(self._follow_kit)      # Sound's list follows the kit's (select_slots)
        self.selectedItemsChanged.connect(self._follow_selection)
        self.docChanged.connect(self._follow_selection)          # the roll's track may have gone (it falls back)
        self.selectedItemsChanged.connect(self._drop_point)
        self.picksChanged.connect(self._roll_picks)              # the velocity readout's blocks (rows_view)
        self._follow_selection()
        self._rebuild()
        self.transport = Transport(self._schedule, self._length, self, pointing=pointer_quiet.busy,   # the amounts popover's
                                   held=lambda: self._stepping and not (hasattr(self, "_hub") and self._hub.amounts.live))   # heard live
        self.transport.playingChanged.connect(self.playingChanged)
        self.transport.renderChanged.connect(self.renderChanged)
        self.transport.stateChanged.connect(self.soundChanged)
        self.transport.failed.connect(lambda line: self._fail(say_error(line, self.doc.data)))
        self.transport.said.connect(self.say)
        self.transport.moved.connect(self._moved)
        self.transport.render()
        self._tv.changed.connect(self.viewChanged)
        self.viewChanged.connect(self._follow_zoom)       # Grid "Auto" follows the zoom (grid_slots.py)
        self._make_actions()                # the one action list: context bar, menus, Ctrl+K, keys (action_slots.py)
        # a moment after the window is up: the settings rows of each kind in the song (a note, a hit, a track …) are
        # made ahead, a kind per frame, so the first note drawn shows its panel as quickly as the tenth (bridge_select)
        QTimer.singleShot(1000, self, lambda: self.make_panels_ahead(self._one_of_each()))

    # ---- reads for QML ----------------------------------------------------------------------------------------
    @Property(str, constant=True)
    def docName(self):
        return self.name

    isLive = Property(bool, lambda self: self.link is not None, constant=True)   # saved after every change: the top bar says "Saved"

    @Property(float, notify=S.timeChanged)
    def time(self):
        return self._t

    @Property(bool, notify=S.playingChanged)
    def playing(self):
        return self.transport.playing

    @Property("QVariantMap", notify=songChanged)
    def song(self):
        return self._view["song"]

    @Property("QVariantList", notify=S.timelineChanged)
    def tracks(self):
        """The arrangement's rows, laid out: without their blocks (those come by `trackRows`' own role, rows_view)."""
        return self._view["shape"]

    @Property(QObject, constant=True)
    def trackRows(self):
        """The rows of `tracks` as a list model keyed by track id: a change redraws the rows that changed in place
        (their lanes keep their picture until it is redrawn); only a row added or removed is made or freed. A plain
        list made every row again on every change, so every lane showed blank until it painted (S63, after a take)."""
        return self._lanes

    @Property("QVariantList", notify=S.rollPickedChanged)
    def rollPicked(self):
        """The roll's selected notes / hits / clips (the velocity strip's readout): only those, never every block."""
        return self.__dict__.get("_roll_picked", [])

    @Property("QVariantList", notify=S.markersChanged)
    def markers(self):
        return self._view["markers"]

    @Property("QVariantMap", notify=S.rollChanged)
    def roll(self):
        """The piano roll of the selection's track (or the last one picked): its layout; the blocks are `rollBlocks`."""
        return self._view["rollShape"]

    @Property("QVariantList", notify=S.rollBlocksChanged)
    def rollBlocks(self):
        """The roll's notes / hits / clips (sent alone: an edit on them leaves the roll's layout as it was)."""
        return self._view["roll"].get("blocks", [])

    @Property("QVariantMap", notify=S.renderChanged)
    def lastRender(self):
        return self.transport.last

    @Property("QVariantMap", notify=S.renderChanged)
    def duckSpans(self):
        """track id -> the dips the last render pulled it down by ([start s, end s, deepest dB]): what each arrangement
        row reads (DuckDips.qml). A row reading `lastRender` copied the whole render answer, twice a row (M4)."""
        return {d["track"]: d["spans"] for d in (self.transport.last or {}).get("ducks") or []}

    @Property(str, notify=S.soundChanged)
    def soundState(self):
        """A short line about the sound: rendering, no output on this machine, or that the render failed."""
        return self.transport.state

    @Slot(str, float, float, float, result=str)
    def blockAt(self, track_id, t, lane, tol):
        """The note / hit / clip under the pointer in an arrangement row ("" when none)."""
        row = next((r for r in self._view["rows"] if r["id"] == track_id), None)
        return pick.block_at(row, t, lane, tol, 0.3) if row else ""

    @Slot(float, float, float, result=str)
    def rollAt(self, t, row, tol):
        """The note / hit / clip under the pointer in the piano roll ("" when none)."""
        return pick.roll_at(self._view["roll"], t, row, tol)

    def reached_here(self, ids) -> bool:
        """The change being announced touched `ids`, an item above one or one inside one. Unlike the kit's `reached`,
        an add or remove elsewhere does not count (a note drawn reaches no master: the loudness and export parts
        stay as they are instead of reading the master again on every click)."""
        t = self._kit.touched
        return t is None or Touched(t.keys, False).reaches(self.doc, list(ids))

    # ---- the kit's hooks: names, times shown in seconds but written in the item's own form, fields on the page --
    def label_of(self, item):
        return inspect.label(item)

    def shown_values(self, item):
        return inspect.shown(item, self.doc.data)

    def edit_call(self, item_id, param, value):
        return inspect.edit_call(self.doc, item_id, param, value)

    def on_page(self, item):        # the inspector leaves out what the workspace's own controls show (onpage.py)
        return onpage.fields(self.workspace.dock, item.get("type", "")) | self._asked.left_out(item)

    @Slot()
    def askClean(self):
        """Clean up…: the selected clips' Cleanup rows appear (screen state) and the panel scrolls to them."""
        self._asked.ids.update(i for i in self._picks.ids if self.doc.has(i) and self.doc.item(i)["type"] == "clip")
        self._refresh()
        self.cleanWanted.emit()

    def _first(self):       # nothing selected at first: the settings panel shows the song (DESIGN.md decision 4)
        return ""

    def list_choices(self, item, param):      # a track's / bus' Output: Master and the buses it may feed; a track's Sound
        if param == "sound" and item.get("type") == "track":
            return sounds.choices(item)
        return output_pick.choices(self.doc, item, self.label_of) if param in (output_pick.FIELD, "bus") else []

    def _rows(self):
        """The kit's rows, each item's with times in bars.beats and pitches as names (inspect.musical_rows) before
        several are merged: notes of one length read "1/2" together, never "1.154 s" (one note never does). Many notes
        or hits: each alike group evaluated once, the rest only their values (many_rows.py)."""
        items, root = [self.doc.item(i) for i in self._kit.selection], self.doc.data
        folded = many_rows.merged(self, items, root)
        if folded is not None:
            return output_pick.without_none(folded)
        each = [inspect.musical_rows(it, self.sound_rows(it), root) for it in items]
        return output_pick.without_none([] if not each else each[0] if len(each) == 1 else many.merge(each))

    def sound_rows(self, it):
        """One item's evaluated rows (the kit's), a track's Played-like-a-person switch as the Feel group (feel_rows)."""
        return feel_rows.rows(it, self._item_rows(it), self._kit.more)

    # ---- screen state -----------------------------------------------------------------------------------------
    @Slot()
    def togglePlay(self):
        self.transport.toggle(self._t)

    # ---- inside -----------------------------------------------------------------------------------------------
    def _follow_selection(self):
        """The piano roll follows the selection's track (a marker or the master keeps the last one)."""
        i = self._sel
        while i and self.doc.has(i) and self.doc.item(i)["type"] not in ("track", "doc", "master", "marker"):
            i = self.doc.parent_of(i)[0]
        was = self._track
        if i and self.doc.has(i) and self.doc.item(i)["type"] == "track":
            self._track = i
        elif not (self._track and self.doc.has(self._track)):
            self._track = next((t["id"] for t in self.doc.data.get("tracks", [])), "")
        if self._view and self._track != was:     # the roll of another track: in the frame after the pick's (rows_view)
            self._roll_later.ask()

    def _one_of_each(self) -> list[str]:
        first: dict = {}
        for it in self.doc.items():
            first.setdefault(it["type"], it["id"])
        return list(first.values())

    def _schedule(self) -> dict:
        """The compiled song. A song with nothing in it yet (a new one, or an instrument with no notes) is still a
        song: it renders as silence the length the screen shows, instead of the engine refusing an empty schedule."""
        side = getattr(self, "side", None)                 # lines being spoken right now play once they are made
        doc = clean_clips.without_pending(self.doc)        # a clip whose cleaned take is not made yet plays its original
        s = compile_doc(voice_card.without(doc, side.voice.making() | side.voice.waiting()) if side else doc,
                        memo=self.__dict__.setdefault("_compiled", {}))      # each track made again only when it changed
        if "length" not in s and not any(t.get(k) for t in s["tracks"] for k in SOUNDING):
            s["length"] = self._length()
        return s

    def _length(self) -> float:
        return self._view["song"]["length"]

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

    def _on_doc(self, event):
        self._stepping = event.kind == "preview"
        super()._on_doc(event)
        known = event.kind != "reset" or event.edits is not None    # a drag taken back says what it undid: those rows
        self._guard(lambda: self._drag_step(change=not self._stepping) if known else self._rebuild())
        if event.kind == "change":             # a drag renders once, when it lands (never during one: Transport.held)
            self.transport.changed()

    def close(self):
        if self.link:
            self.link.close()
        self.endDrag()
        if self.__dict__.get("_keys_heard"):
            self._keys_heard.close()
        self._marks.close()
        self.transport.close()
