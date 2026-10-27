"""The shot and the page for Bridge3D (a slot mix-in): which shot the screen shows, a new shot from the view, Make this
the shot and Frame the selection (the shown shot's camera moved, one undo step each), and the page (Build / Animate /
Render: screen state, never the document)."""
from __future__ import annotations

from PySide6.QtCore import Property, Slot
from rostrum3d.compile import shot_info

from . import outline, shots as shot_list
from .bridge_signals import Signals3D

PAGES = ("build", "animate", "render")


class ShotMixin:
    @Property("QVariantList", notify=Signals3D.outlineChanged)
    def shots(self):
        return outline.named(self.doc.data, "shots")

    @Slot(str, result="QVariantList")
    def shotEntries(self, view_mode):
        """The crumb's list (shots.crumb_entries): the shots, the shown one checked, Frame the selection while something
        is selected, then New shot (from this view)."""
        return shot_list.crumb_entries(self.shots, self.shot_id, view_mode, self.add.canAddShot, bool(self._framed()))

    def _framed(self) -> list[str]:
        return shot_list.framed(self.doc, list(self.selection), self._info.get("camera", ""))

    def _at(self) -> float:
        """The playhead in seconds (where a moving camera gets its key)."""
        return self._frame / self._info["fps"]

    @Slot()
    def takeView(self):
        """Make this the shot: the shown shot's camera moves to the viewport's view (shot.take_view, one undo step),
        framing what the shot frame drawn in the view holds; then the viewport looks through it."""
        vp = self.viewport
        if vp is None or vp.mode == "shot":
            return
        call = shot_list.take_view_call(self.doc, vp.cam, self.shot_id, vp.taken_fov(), self._at())
        if self._guard(lambda: self._done(self.doc.apply([call], self.who, label="Make this the shot"), "")):
            vp.setPreview(False)
            vp.setMode("shot")

    @Slot()
    def frameSelection(self):
        """Frame the selection: the shown shot's camera slides along its view line until the selection fits (shot.frame,
        one undo step); the viewport then looks through it."""
        items = self._framed()
        if not items:
            return self.fail_line("Error: frame the selection: select a shape, clay, group or light to frame first.")
        call = shot_list.frame_call(self.shot_id, items, self._at())
        if self._guard(lambda: self._done(self.doc.apply([call], self.who, label="Frame the selection"), ""))                 and self.viewport is not None:
            self.viewport.setMode("shot")

    @Slot(str)
    def showShot(self, shot_id):
        """Show another shot (screen state, not an edit): its time, its frame size, its camera in the viewport."""
        if not shot_id or shot_id == self.shot_id:      # "": a failed New shot already said why
            return
        try:
            info = shot_info(self.doc.data, shot_id)
        except ValueError as e:
            return self.fail_line(f"Error: shot: {e}")
        if self._timer.isActive():
            self.togglePlay()
        self.shot_id, self._info = shot_id, info
        self._frame = min(max(self._frame, info["start"]), info["end"])
        self.model.update(self._rows())
        self.shotChanged.emit()
        self.outlineChanged.emit()
        self.frameChanged.emit()

    @Slot()
    def newShotFromView(self):
        """A camera where the viewport looks from, a shot through it (shot.from_view: one undo step); then show it."""
        if self.viewport is None:
            return self.fail_line("Error: new shot from this view: there is no viewport to take the view from.")
        first = shot_info(self.doc.data, self.doc.data["shots"][0]["id"])     # the new shot is framed like the first
        call, new = shot_list.from_view_call(self.doc, self.viewport.cam, first)
        if self._guard(lambda: self._done(self.doc.apply([call], self.who, label="New shot from this view"), "")):
            self.showShot(new)

    @Property(str, notify=Signals3D.pageChanged)
    def page(self):
        """Build | Animate | Render (screen state, never the document): the same document, camera and selection."""
        return self._page

    @Slot(str)
    def setPage(self, page):
        if page not in PAGES:
            return self.fail_line(f"Error: page: {page!r} is not one of {', '.join(PAGES)}.")
        if page != self._page:
            self._page = page
            self.model.update(self._rows())     # a setting that shows only while animating (Timing) comes or goes
            self.pageChanged.emit()
