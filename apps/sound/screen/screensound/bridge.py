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

from . import inspect, lanes, moves, pick, picture, timeline
from .transport import Transport
from .view import STEP, View

PAGES = ("instruments", "timeline", "mix")


class SoundBridge(DocBridge):
    pageChanged = Signal()
    timeChanged = Signal()
    playingChanged = Signal()
    timelineChanged = Signal()
    renderChanged = Signal()
    soundChanged = Signal()
    viewChanged = Signal()
    pictureOpenChanged = Signal()
    pointChanged = Signal()

    def __init__(self, doc, name="Untitled song", autosave=False, parent=None):
        self.name, self.autosave = name, autosave
        self._page, self._t, self._track = "timeline", 0.0, ""
        self._drag = self._grab = None
        self._view: dict = {}
        self._zoom = View()                 # which stretch of the song is on screen (screen state, not an edit)
        self._open: dict = {}               # track id -> (item id, lane) of the automation lane shown under its row
        self._edit = None                   # the automation point being dragged (lanes.PointEdit)
        self._apt: tuple | None = None      # the selected automation point: (track id, item id, lane, index)
        self._picture_open = False
        super().__init__(doc, parent=parent)
        self._picture_open = bool(self.doc.data.get("picture"))     # the corner opens by itself on a song with a picture
        self.selectionChanged.connect(self._follow_selection)
        self.selectionChanged.connect(self._drop_point)
        self._follow_selection()
        self._rebuild()
        self.transport = Transport(lambda: compile_doc(self.doc), self._length, self)
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

    @Property(float, notify=viewChanged)
    def viewStart(self):
        """The time (seconds) at the left edge of every timeline: ruler, rows, markers, playhead, piano roll."""
        return self._zoom.start

    @Property(float, notify=viewChanged)
    def viewSpan(self):
        """How many seconds those timelines show across their width."""
        return self._zoom.span(self._length())

    @Property(bool, notify=viewChanged)
    def viewFit(self):
        return self._zoom.fit

    @Property("QVariantMap", notify=pointChanged)
    def point(self):
        """The selected automation point: track, item, lane, index ({} when none)."""
        a = self._apt
        return {"track": a[0], "item": a[1], "lane": a[2], "index": a[3]} if a else {}

    @Property(bool, notify=pictureOpenChanged)
    def pictureOpen(self):
        return self._picture_open

    @Property(str, notify=timelineChanged)
    def picture(self):
        """The video file the song is made to (the document's `picture` field; "" when none)."""
        return str(self.doc.data.get("picture") or "")

    @Property(str, notify=timelineChanged)
    def pictureName(self):
        return picture.name(self.picture)

    @Property(str, notify=timelineChanged)
    def pictureUrl(self):
        return picture.url(self.picture)

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
        if self._zoom.follow(self._t, self._length()):
            self.viewChanged.emit()
        self.timeChanged.emit()

    @Slot(float, float, bool, bool, float, bool, result=bool)
    def viewWheel(self, dx, dy, ctrl, shift, frac, vertical):
        """A wheel turn over a timeline. Ctrl: zoom around the pointer (`frac` across the width). Shift or a sideways
        swipe: scroll in time. A plain turn scrolls in time only when the caller has nothing to scroll up and down
        (`vertical` false). Returns false when the caller should scroll up and down."""
        if ctrl:
            self.zoomAt(STEP ** (dy / 120.0), frac)
        elif dx or shift or not vertical:
            self._zoom.scroll(-(dx or dy) / 120.0 * self.viewSpan * 0.1, self._length())
            self.viewChanged.emit()
        else:
            return False
        return True

    @Slot(float, float)
    def zoomAt(self, factor, frac):
        """Zoom in by `factor` (a pinch's scale, a wheel notch) keeping the moment at `frac` across the width."""
        self._zoom.zoom(factor, frac, self._length())
        self.viewChanged.emit()

    @Slot(float)
    def zoomStep(self, factor):
        """A key's zoom: around the playhead when it is on screen, else the middle."""
        z = self._zoom
        frac = (self._t - z.start) / z.span(self._length())
        self.zoomAt(factor, frac if 0 <= frac <= 1 else 0.5)

    @Slot()
    def fitView(self):
        self._zoom.show_all()
        self.viewChanged.emit()

    @Slot(float)
    def setViewStart(self, t):
        self._zoom.set_start(t, self._length())
        self.viewChanged.emit()

    @Slot(bool)
    def setPictureOpen(self, on):
        self._picture_open = bool(on)
        self.pictureOpenChanged.emit()

    @Slot(str)
    def setPicture(self, chosen):
        """Choose the video (a path or file:// URL; "" clears it): one operation on the document."""
        def go():
            self._apply([picture.set_call(picture.local(chosen))], "Set picture")
            if chosen:
                self.setPictureOpen(True)
        self._guard(go)

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

    @Slot(str)
    def toggleLanes(self, track_id):
        """Open (or close) the automation lane under a track's row; it opens on the track's volume."""
        self.openLane(track_id, "" if track_id in self._open else track_id, "volume")

    @Slot(str, str, str)
    def openLane(self, track_id, target, lane):
        """Show `lane` of `target` (the track or one of its sends) under the track's row; "" closes."""
        if not target:
            self._open.pop(track_id, None)
        elif (target, lane) in lanes.applicable(self.doc.item(track_id), self.doc.data):
            self._open[track_id] = (target, lane)
        else:
            return self._fail(f'Error: lane: "{lane}" of "{target}" is not a lane on {track_id}.')
        self._rebuild()

    @Slot(str, str, str, float, float, float, float, bool)
    def laneBegin(self, track_id, target, lane, t, yfrac, tol_t, tol_y, free):
        """Press in a lane (`yfrac` 0 top .. 1 bottom, tolerances: seconds and a fraction of the height): grab
        the point there or add one, and start one gesture."""
        self.endDrag()
        self.select(track_id)

        def go():
            track = self.doc.item(track_id)
            e = lanes.PointEdit(target, lanes.owner_of(track, target), self.doc.data, lane)
            span = e.hi - e.lo
            call = e.press(t, e.lo + (1 - yfrac) * span, tol_t, tol_y * span, free)
            self._edit, self._drag = e, Drag(self.doc, self.who, "Automate")
            if call:
                self._drag.preview([call])
            self._apt = (track_id, target, lane, e.index)
            self.pointChanged.emit()
        self._guard(go)

    @Slot(float, float, bool)
    def laneDrag(self, t, yfrac, free):
        e = self._edit
        if e is not None and self._drag is not None:
            self._guard(lambda: self._drag.preview([e.move(t, e.lo + (1 - yfrac) * (e.hi - e.lo), free)]))

    @Slot()
    def clearPoint(self):
        if self._apt:
            self._apt = None
            self.pointChanged.emit()

    @Slot()
    def removeSelected(self):
        if self._apt:
            return self._remove_point()
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

    def _length(self) -> float:
        return self._view["song"]["length"]

    def _drop_point(self):
        if self._apt and self._sel != self._apt[0]:
            self.clearPoint()

    def _remove_point(self):
        track_id, target, lane, i = self._apt
        e = lanes.PointEdit(target, lanes.owner_of(self.doc.item(track_id), target), self.doc.data, lane)
        e.index = i
        self._apt = None
        self.pointChanged.emit()
        self._guard(lambda: self._apply([e.remove()], "Delete point"))

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
        self.timelineChanged.emit()
        self.viewChanged.emit()

    def _on_doc(self, event):
        super()._on_doc(event)
        self._guard(self._rebuild)
        if event.kind == "change":             # a drag renders once, when it lands
            self.transport.changed()
        if self.autosave and event.kind == "change":
            self._guard(self.doc.save)

    def _moved(self, t):
        self._t = t
        if self._zoom.follow(t, self._length()):
            self.viewChanged.emit()
        self.timeChanged.emit()

    def close(self):
        self.endDrag()
        self.transport.close()
