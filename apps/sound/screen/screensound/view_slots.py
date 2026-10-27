"""The playhead and which stretch of the song is on screen (zoom, scroll): screen state, never an edit. The view itself
is the kit's `TimeView` (`backend.timeView`, a `TimeViewObject`: HScroll binds to it); these slots are Sound's names for
it, and the playhead's page-follow."""
from __future__ import annotations

from PySide6.QtCore import Property, QCoreApplication, QObject, Slot
from rostrum_sound.doc import musical

from . import timing
from .view_kept import ViewKept
from .signals import SoundSignals as S

WORK_BARS = 8       # the Editor opens on this many bars when the view shows more (a whole song: a quarter note ~8 px)


class ViewSlots:
    timeView = Property(QObject, lambda self: self._tv, constant=True)     # HScroll's view

    @Slot(float, "QVariant", result=str)
    def positionText(self, t, _song=None):
        """A time as people read it: bars.beats, then the clock ("5.3  0:09.60"), from the one formatter (musical.py)
        that every field and agent report uses; the ticks are left off here. QML passes something of `backend.song` (its
        length: not the whole map, which would be converted on every tempo step) so the text follows a tempo or time
        signature edit, not only the playhead."""
        return ".".join(musical.position(t, self.doc.data).split(".")[:2]) + "  " + musical.clock(t)

    @Slot(str, result=str)
    def jumpTo(self, text):
        """The position field: typed bars.beats ("5.3", "5.3.480"), a clock ("0:09.6") or seconds ("9.6 s") moves the playhead
        there (the one parser, musical.py). "" when it did; else the refusal, in words, for the field to show."""
        try:
            t = musical.parse(text.split("  ")[0], self.doc.data)
        except ValueError as e:
            return str(e)
        if t > self._view["song"]["length"] + 1e-6:
            return f"The song is {musical.clock(self._view['song']['length'])} long: {musical.clock(t)} is past its end"
        self.setTime(t)
        return ""

    @Property(float, notify=S.viewChanged)
    def viewStart(self):
        """The time (seconds) at the left edge of every timeline: ruler, rows, markers, playhead, piano roll."""
        return self._zoom.start

    @Property(float, notify=S.viewChanged)
    def viewSpan(self):
        """How many seconds those timelines show across their width."""
        return self._zoom.span

    @Property(bool, notify=S.viewChanged)
    def viewFit(self):
        return self._zoom.fit

    @Slot(float)
    def setTime(self, t):
        self._t = min(max(float(t), 0.0), self._view["song"]["length"])
        self.transport.seek(self._t)
        self._tv.follow(self._t)
        self.timeChanged.emit()

    @Slot(float, float, bool, bool, float, bool, result=bool)
    def viewWheel(self, dx, dy, ctrl, shift, frac, vertical):
        """A wheel turn over a timeline (kit TimeView.wheel). False: the caller should scroll up and down."""
        return self._tv.wheel(dx, dy, ctrl, shift, frac, vertical)

    @Slot(float, float)
    def zoomAt(self, factor, frac):
        """Zoom in by `factor` (a pinch's scale, a wheel notch) keeping the moment at `frac` across the width."""
        self._tv.zoomAt(factor, frac)

    @Slot(float)
    def zoomStep(self, factor):
        """A key's zoom: around the playhead when it is on screen, else the middle."""
        self._tv.zoomStep(factor, self._t)

    @Slot()
    def fitView(self):
        self._tv.showAll()

    @Slot(float)
    def setViewStart(self, t):
        self._tv.setStart(t)

    def _editor_zoom(self):
        """The Editor just opened: when the view shows more than WORK_BARS, show WORK_BARS from the bar before the
        selection's first note or hit on this track (else the playhead), so a click lands where the person aims
        (critic r8). A narrower view the person chose stays, and so does the Editor's view the song was closed with
        (its first opening after a reopen, critic r12 must-fix 2)."""
        bars = self._view["song"]["bars"] if self._view else []
        if self.workspace.dock != "editor":
            return
        if self.__dict__.pop("_editor_view_back", False):
            return
        if len(bars) <= WORK_BARS or self._zoom.span <= bars[WORK_BARS] - bars[0]:
            return
        root, mine = self.doc.data, self.__dict__.get("_track", "")
        times = [timing.sec(self.doc.item(i)["at"], root, i) for i in self._picks.ids
                 if self.doc.has(i) and self.doc.item(i)["type"] in ("note", "hit") and self.doc.parent_of(i)[0] == mine]
        at = min(times) if times else self._t
        first = max(0, max((k for k, b in enumerate(bars) if b <= at + 1e-6), default=0) - 1)
        first = min(first, len(bars) - 1 - WORK_BARS)
        self._tv.fitTo(bars[first], bars[first + WORK_BARS])

    # ---- the view kept with the song (view_kept.py): the time view, and each track's roll keys -----------------
    def _kept_view(self) -> ViewKept:
        """Made on the song's first build (the view's length is known then): the kept time view is put back before
        anything is shown, and from then on every change of it is kept."""
        kept = self.__dict__.get("_view_kept")
        if kept is None:
            kept = self.__dict__["_view_kept"] = ViewKept(self.doc.folder, self.doc.item_id, self)
            t = kept.time
            if t and not t.get("fit") and t.get("span", 0) > 0:
                v = self._zoom
                self._tv.zoomAt(v.length / t["span"], 0.0)      # from the whole song (a new view's fit) to its span
                self._tv.setStart(t["start"])
                self.__dict__["_editor_view_back"] = t["span"] if t.get("editor") else False
            self._tv.changed.connect(self._keep_time)
            QCoreApplication.instance().aboutToQuit.connect(kept.flush)
        return kept

    def _keep_time(self):
        v = self._zoom
        back = self.__dict__.get("_editor_view_back")
        if back and self.workspace.dock != "editor" and abs(v.span - back) > back * 0.01:
            self.__dict__.pop("_editor_view_back", None)  # the person zoomed since: the Editor's working zoom applies again
            # (only a zoom: the window settling or a scroll on open must not lose the kept view, the real-window r1 check)
        editor = self.workspace.dock == "editor" or bool(self.__dict__.get("_editor_view_back"))   # put back, not yet left
        self._kept_view().keep_time(v.start, v.span, v.fit, editor)

    def _close_view(self):
        """The song closes: a kept view still waiting is written."""
        if "_view_kept" in self.__dict__:
            self._view_kept.flush()

    @Property("QVariantMap", constant=True)
    def rollPlaces(self):
        """Each track's roll keys as the person left them (PianoRoll's `kept`): "<track>/<kind>[/rows]" -> [key at the
        view's middle, how far into its row]."""
        return dict(self._kept_view().rolls)

    @Slot(str, int, float)
    def keepRollPlace(self, shown, key, into):
        self._kept_view().keep_roll(shown, key, into)

    def _moved(self, t):
        self._t = t
        self._tv.follow(t)
        self.timeChanged.emit()
