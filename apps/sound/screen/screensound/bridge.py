"""RostrumSound's document bridge: the kit's DocBridge plus the workspace (workspace.py: the bottom dock, the Sounds
panel), the playhead, the arrangement and piano roll
(timeline.py), what is under the pointer (pick.py), the drags (one doc.gesture = one undo step) and the sound
(transport.py: rendered by the engine after each change, played from the playhead).

The slots live in small mix-ins (gui-kit README › parts.py): view_slots (playhead, zoom), picture_slots, song_slots
(music map), lane_slots (automation), edit_slots (edits and drags); the signals in signals.py. Every change is an
operation (moves.py builds the calls). The Mixer reads `lastRender` (the engine's render answer, with stems for
every track) and listens to `renderChanged`. The project's shared markers are watched (MarkerWatch): one moved or
renamed in another app re-renders the sound, and a rename is followed as one recorded step (marker.follow).
"""
from __future__ import annotations

from PySide6.QtCore import Property, Slot
from rostrum_gui import DocBridge
from rostrum_gui.live_link import LiveLink
from rostrum_gui.markers import MarkerWatch
from rostrum_gui.timeview import TimeViewObject
from rostrum_core import live
from rostrum_sound import clean_clips, compile as compile_doc
from rostrum_sound.doc import markers as MK
from rostrum_sound.doc import ops_mix

from . import voice_card, voice_takes
from . import inspect, lanes, onpage, output_pick, picture, pick, screen_seen, timeline
from .action_slots import ActionSlots
from .agent_demo import AgentDemo
from .edit_slots import EditSlots
from .grid_slots import GridSlots
from .group_slots import GroupSlots
from .handle_slots import HandleSlots
from .velocity_slots import VelocitySlots
from .key_slots import KeySlots
from .lane_slots import LaneSlots
from .picture_slots import PictureSlots
from .select_slots import SelectSlots
from .signals import SoundSignals as S
from .song_slots import SongSlots
from .transport import Transport
from .view_slots import ViewSlots
from .workspace import Workspace

SOUNDING = ("notes", "hits", "clips", "sounds")       # what makes a compiled track last (engine contract/track.rs)


class SoundBridge(AgentDemo, ViewSlots, PictureSlots, SongSlots, LaneSlots, EditSlots, HandleSlots, VelocitySlots, GridSlots, GroupSlots, ActionSlots, KeySlots, SelectSlots, S, DocBridge):
    def __init__(self, doc, name="Untitled song", parent=None):
        self.name = name
        self._t, self._track = 0.0, ""
        self.workspace = Workspace(lambda line: self._fail(line), lambda: self.model.reset(self._rows()))
        self._drag = self._grab = None
        self._view: dict = {}
        self._tv = TimeViewObject()         # which stretch of the song is on screen (screen state, not an edit)
        self._zoom = self._tv.view
        self._open: dict = {}               # track id -> (item id, lane) of the automation lane shown under its row
        self._edit = None                   # the automation point being dragged (lanes.PointEdit)
        self._apt: tuple | None = None      # the selected automation point: (track id, item id, lane, index)
        self._play_lane = "sustain"         # the Editor's playing lane (sustain, dynamics, bend): the person's view
        self._picture_open = False
        MK.use_project(doc.folder)          # the screen works in this document's project (its shared markers)
        super().__init__(doc, parent=parent)
        self.link = None
        if doc.folder and doc.item_id:      # live: one door for every save, shared with agents' servers (rostrum_core.live)
            live.keep(doc)
            self.link = LiveLink(self, "sound", screen_seen.state)
        self._picture_open = bool(self.doc.data.get("picture"))     # the corner opens by itself on a song with a picture
        self._follow_render = picture.Follow(lambda: (self.pictureChoice, self.doc.folder), self)
        self._follow_render.changed.connect(self.timelineChanged)       # the linked item has a newer render
        self._marks = MarkerWatch(self.doc.folder, self, self.who, self._fail, "sound")
        self._marks.changed.connect(self._markers_changed)
        self.join_history(self._marks)                      # marker edits undo with the screen's one history
        self.selectedItemsChanged.connect(self._follow_kit)      # Sound's list follows the kit's (select_slots)
        self.selectedItemsChanged.connect(self._follow_selection)
        self.docChanged.connect(self._follow_selection)          # the roll's track may have gone (it falls back)
        self.selectedItemsChanged.connect(self._drop_point)
        self._follow_selection()
        self._rebuild()
        self.transport = Transport(self._schedule, self._length, self)
        self.transport.playingChanged.connect(self.playingChanged)
        self.transport.renderChanged.connect(self.renderChanged)
        self.transport.stateChanged.connect(self.soundChanged)
        self.transport.failed.connect(self._fail)
        self.transport.said.connect(self.say)
        self.transport.moved.connect(self._moved)
        self.transport.render()
        self._tv.changed.connect(self.viewChanged)
        self.viewChanged.connect(self._follow_zoom)       # Grid "Auto" follows the zoom (grid_slots.py)
        self._make_actions()                # the one action list: context bar, menus, Ctrl+K, keys (action_slots.py)

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

    @Property("QVariantMap", notify=S.timelineChanged)
    def song(self):
        return self._view["song"]

    @Property("QVariantList", notify=S.timelineChanged)
    def tracks(self):
        return self._view["rows"]

    @Property("QVariantList", notify=S.timelineChanged)
    def markers(self):
        return self._view["markers"]

    @Property("QVariantMap", notify=S.rollChanged)
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

    def on_page(self, item):        # the inspector leaves out what the workspace's own controls show (onpage.py)
        return onpage.fields(self.workspace.dock, item.get("type", ""))

    def _first(self):       # nothing selected at first: the settings panel shows the song (DESIGN.md decision 4)
        return ""

    def list_choices(self, item, param):      # a track's / bus' Output: Master and the buses it may feed
        return output_pick.choices(self.doc, item, self.label_of) if param == output_pick.FIELD else []

    def _rows(self):
        rows = output_pick.without_none(super()._rows())
        sel = self._kit.selection          # times in bars.beats, pitches as names (inspect.musical_rows)
        return inspect.musical_rows(self.doc.item(sel[0]), rows, self.doc.data) if len(sel) == 1 else rows

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
        if self._view and self._track != was:
            self._show_roll()

    def _show_roll(self):
        """The Editor shows another track: only the roll is made again, the arrangement's rows stay (rebuilding every
        row on a click cost ~250 ms on a 16-track song, S59)."""
        self._view["roll"] = self._roll(self._view["rows"])
        self.rollChanged.emit()

    def _schedule(self) -> dict:
        """The compiled song. A song with nothing in it yet (a new one, or an instrument with no notes) is still a
        song: it renders as silence the length the screen shows, instead of the engine refusing an empty schedule."""
        side = getattr(self, "side", None)                 # lines being spoken right now play once they are made
        doc = clean_clips.without_pending(self.doc)        # a clip whose cleaned take is not made yet plays its original
        s = compile_doc(voice_card.without(doc, side.voice.making() | side.voice.waiting()) if side else doc)
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

    def _rebuild(self):
        root = self.doc.data
        self._open = {k: v for k, v in self._open.items() if self.doc.has(k)
                      and v in lanes.applicable(self.doc.item(k), root)}
        rows = timeline.rows(root, self._open, self._folded)
        self._marks_on(rows)
        self._view = {"rows": rows, "markers": timeline.markers(root), "song": timeline.song(root),
                      "roll": self._roll(rows)}
        self._tv.setLength(self._length())        # the view is the person's: nothing new on screen zooms or scrolls it
        self.timelineChanged.emit()
        self.rollChanged.emit()
        self.viewChanged.emit()

    def _roll(self, rows) -> dict:
        """The Editor's piano roll of the current track (`_track`), in its row's colour."""
        root = self.doc.data
        hue = next((r["hue"] for r in rows if r["id"] == self._track), timeline.HUES[0])
        track = self.doc.item(self._track) if self._track and self.doc.has(self._track) else None
        roll = timeline.roll(track, root, hue, self._play_lane)
        self._marks_on([roll])
        return roll

    def _marks_on(self, rows):
        side = getattr(self, "side", None)               # lines being spoken say so on their blocks
        if side:
            voice_card.mark_speaking(rows, side.voice.making())
            voice_card.mark_waiting(rows, side.voice.waiting())
            voice_takes.mark_takes(rows, self.doc.data)

    def _on_doc(self, event):
        super()._on_doc(event)
        self._guard(self._rebuild)
        if event.kind == "change":             # a drag renders once, when it lands
            self.transport.changed()

    def close(self):
        if self.link:
            self.link.close()
        self.endDrag()
        if self.__dict__.get("_keys_heard"):
            self._keys_heard.close()
        self._marks.close()
        self.transport.close()
