"""The picture corner: the video (a file or a linked 2D item's newest render) the song is made against
(picture.py does the work; each change is one operation on the document)."""
from __future__ import annotations

from PySide6.QtCore import Property, Slot

from . import picture
from .signals import SoundSignals as S


class PictureSlots:
    @Property(bool, notify=S.pictureOpenChanged)
    def pictureOpen(self):
        return self._picture_open

    @Property(str, notify=S.pictureChanged)
    def pictureChoice(self):
        """The document's `picture` field: a video file or a 2D item's link ("" when none)."""
        return str(self.doc.data.get("picture") or "")

    @Property(str, notify=S.pictureChanged)
    def picture(self):
        """The video file to show: the chosen file, or the linked 2D item's newest render ("" when none)."""
        return picture.resolve(self.pictureChoice, self.doc.folder)[0]

    @Property(str, notify=S.pictureChanged)
    def pictureProblem(self):
        """Why a linked picture shows nothing ("not rendered yet" …); "" when fine or none chosen."""
        return picture.resolve(self.pictureChoice, self.doc.folder)[1] or picture.start(self.doc.data)[1]

    @Property(float, notify=S.pictureChanged)
    def pictureStart(self):
        """When the picture's first frame is (seconds): a marker's time, so it follows the marker."""
        return picture.start(self.doc.data)[0]

    @Property(str, notify=S.pictureChanged)
    def pictureMarker(self):
        """The shared marker the picture starts on ("" when a plain time)."""
        return picture.start_marker(self.doc.data)

    @Property(str, notify=S.pictureChanged)
    def pictureName(self):
        return picture.name(self.pictureChoice, self.doc.folder)

    @Property("QVariantList", notify=S.pictureChanged)
    def pictureItems(self):
        """The project's 2D items, to link one as the picture: [{id, label}]."""
        return picture.items(self.doc.folder)

    @Property(str, notify=S.pictureChanged)
    def pictureUrl(self):
        return picture.url(self.picture)

    @Slot(float)
    def setPictureLength(self, seconds):
        """How long the shown video is, as its player reads it (PictureCorner; 0 with none): screen state. The song
        on screen is at least as long as the picture, so its cuts can be marked before any music is written."""
        seconds = max(0.0, float(seconds or 0))
        if abs(seconds - self.__dict__.get("_picture_len", 0.0)) > 1e-3:
            self._picture_len = seconds
            self._guard(self._rebuild)

    def _picture_end(self) -> float:
        """Where the shown picture ends on the song's clock (seconds; 0 with none)."""
        n = self.__dict__.get("_picture_len", 0.0)
        return picture.start(self.doc.data)[0] + n if n > 0 else 0.0

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

    @Slot(str)
    def linkPicture(self, item_id):
        """Show a 2D item's newest render as the picture (follows new renders): one operation on the document."""
        def go():
            self._apply([picture.link_call(item_id)], "Set picture")
            self.setPictureOpen(True)
        self._guard(go)

    @Slot(str)
    def setPictureStart(self, marker):
        """The picture's first frame sits on a shared marker (its name), or at the song's start ("")."""
        self._guard(lambda: self._apply([picture.start_call(marker)], "Set picture start"))
