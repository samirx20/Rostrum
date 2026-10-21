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

    @Property(str, notify=S.timelineChanged)
    def pictureChoice(self):
        """The document's `picture` field: a video file or a 2D item's link ("" when none)."""
        return str(self.doc.data.get("picture") or "")

    @Property(str, notify=S.timelineChanged)
    def picture(self):
        """The video file to show: the chosen file, or the linked 2D item's newest render ("" when none)."""
        return picture.resolve(self.pictureChoice, self.doc.folder)[0]

    @Property(str, notify=S.timelineChanged)
    def pictureProblem(self):
        """Why a linked picture shows nothing ("not rendered yet" …); "" when fine or none chosen."""
        return picture.resolve(self.pictureChoice, self.doc.folder)[1] or picture.start(self.doc.data)[1]

    @Property(float, notify=S.timelineChanged)
    def pictureStart(self):
        """When the picture's first frame is (seconds): a marker's time, so it follows the marker."""
        return picture.start(self.doc.data)[0]

    @Property(str, notify=S.timelineChanged)
    def pictureMarker(self):
        """The shared marker the picture starts on ("" when a plain time)."""
        return picture.start_marker(self.doc.data)

    @Property(str, notify=S.timelineChanged)
    def pictureName(self):
        return picture.name(self.pictureChoice, self.doc.folder)

    @Property("QVariantList", notify=S.timelineChanged)
    def pictureItems(self):
        """The project's 2D items, to link one as the picture: [{id, label}]."""
        return picture.items(self.doc.folder)

    @Property(str, notify=S.timelineChanged)
    def pictureItemsNote(self):
        """Why there are no project items to pick ("" when there are some)."""
        return picture.items_note(self.doc.folder)

    @Property(str, notify=S.timelineChanged)
    def pictureUrl(self):
        return picture.url(self.picture)

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
