"""RostrumSound's document bridge: the kit's DocBridge plus pages, the playhead, the arrangement and piano roll
(timeline.py), what is under the pointer (pick.py), the drags (one doc.gesture = one undo step) and the sound
(transport.py: rendered by the engine after each change, played from the playhead).

Every change is an operation (moves.py builds the calls). The Mix page reads `lastRender` (the engine's render
answer, with stems for every track) and listens to `renderChanged`.
"""
from __future__ import annotations

from PySide6.QtCore import Property, Signal, Slot
from rostrum_gui import DocBridge
from rostrum_gui.edits import Drag
from rostrum_sound import compile as compile_doc

from . import inspect, moves, pick, timeline
from .transport import Transport

PAGES = ("instruments", "timeline", "mix")


class SoundBridge(DocBridge):
    pageChanged = Signal()
    timeChanged = Signal()
    playingChanged = Signal()
    timelineChanged = Signal()
    renderChanged = Signal()
    soundChanged = Signal()

    def __init__(self, doc, name="Untitled song", autosave=False, parent=None):
        self.name, self.autosave = name, autosave
        self._page, self._t, self._track = "timeline", 0.0, ""
        self._drag = self._grab = None
        self._view: dict = {}
        super().__init__(doc, parent=parent)
        self.selectionChanged.connect(self._follow_selection)
        self._follow_selection()
        self._rebuild()
        self.transport = Transport(lambda: compile_doc(self.doc), lambda: self._view["song"]["length"], self)
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

    @Property(str, notify=pageChanged)
    def page(self):
        return self._page

    @Property(float, notify=timeChanged)
    def time(self):
        return self._t

    @Property(bool, notify=playingChanged)
    def playing(self):
        return self.transport.playing

    @Property("QVariantMap", notify=timelineChanged)
    def song(self):
        return self._view["song"]

    @Property("QVariantList", notify=timelineChanged)
    def tracks(self):
        return self._view["rows"]

    @Property("QVariantList", notify=timelineChanged)
    def markers(self):
        return self._view["markers"]

    @Property("QVariantMap", notify=timelineChanged)
    def roll(self):
        """The piano roll of the selection's track (or the last one picked)."""
        return self._view["roll"]

    @Property("QVariantMap", notify=renderChanged)
    def lastRender(self):
        return self.transport.last

    @Property(str, notify=soundChanged)
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

    # ---- the kit's hooks: names, and times shown in seconds but written in the item's own form ------------------
    def label_of(self, item):
        return inspect.label(item)

    def shown_values(self, item):
        return inspect.shown(item, self.doc.data)

    def edit_call(self, item_id, param, value):
        return inspect.edit_call(self.doc, item_id, param, value)

    # ---- screen state -----------------------------------------------------------------------------------------
    @Slot(str)
    def setPage(self, page):
        if page not in PAGES:
            return self._fail(f'Error: page: "{page}" is not a page ({", ".join(PAGES)}).')
        self._page = page
        self.pageChanged.emit()

    @Slot(float)
    def setTime(self, t):
        self._t = min(max(float(t), 0.0), self._view["song"]["length"])
        self.transport.seek(self._t)
        self.timeChanged.emit()

    @Slot()
    def togglePlay(self):
        self.transport.toggle(self._t)

    # ---- edits: every one an operation ------------------------------------------------------------------------
    @Slot(str, str)
    def toggleTrack(self, track_id, field):
        def go():
            call, label = moves.toggle_call(self.doc, track_id, field)
            self._apply([call], label)
        self._guard(go)

    @Slot(float, int)
    def addNote(self, t, key):
        if not self._track:
            return

        def go():
            before = {n["id"] for n in self.doc.item(self._track).get("notes", [])}
            self._apply([moves.add_note_call(self.doc, self._track, t, key)], "Add note")
            new = [n["id"] for n in self.doc.item(self._track)["notes"] if n["id"] not in before]
            if new:
                self.select(new[0])
        self._guard(go)

    @Slot()
    def removeSelected(self):
        if self._sel and self.doc.has(self._sel):
            self._guard(lambda: self._apply([moves.remove_call(self.doc, self._sel)], "Delete"))

    @Slot(str, result=bool)
    def beginDrag(self, item_id):
        """Press on a note, hit, clip or marker: select it and start one gesture."""
        self.endDrag()
        self.select(item_id)

        def go():
            self._grab = moves.grab(self.doc, item_id)
            self._drag = Drag(self.doc, self.who, moves.LABELS[self._grab["type"]])
        return self._guard(go)

    @Slot(float, int, bool)
    def dragBy(self, dt, dsemi, free):
        """Total move from the press: dt seconds, dsemi semitones (notes), snapped to 1/4 beat unless free."""
        if self._drag is not None:
            self._guard(lambda: self._drag.preview(moves.drag_calls(self.doc, self._grab, dt, dsemi, free)))

    @Slot()
    def endDrag(self):
        d, self._drag, self._grab = self._drag, None, None
        if d is not None:
            self._guard(lambda: self._done(d.end(), ""))

    @Slot()
    def cancelDrag(self):
        d, self._drag, self._grab = self._drag, None, None
        if d is not None:
            self._guard(lambda: d.end(cancel=True))

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

    def _rebuild(self):
        root = self.doc.data
        rows = timeline.rows(root)
        hue = next((r["hue"] for r in rows if r["id"] == self._track), timeline.HUES[0])
        track = self.doc.item(self._track) if self._track and self.doc.has(self._track) else None
        self._view = {"rows": rows, "markers": timeline.markers(root), "song": timeline.song(root),
                      "roll": timeline.roll(track, root, hue)}
        self.timelineChanged.emit()

    def _on_doc(self, event):
        super()._on_doc(event)
        self._guard(self._rebuild)
        if event.kind == "change":             # a drag renders once, when it lands
            self.transport.changed()
        if self.autosave and event.kind == "change":
            self._guard(self.doc.save)

    def _moved(self, t):
        self._t = t
        self.timeChanged.emit()

    def close(self):
        self.endDrag()
        self.transport.close()
