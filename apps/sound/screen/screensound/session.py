"""The open song and the window around it: New, Open, Open recent, Duplicate, Show folder, crash recovery
(projects.py does the files; this swaps what is on screen). QML sees it as `songs`.

Saving is automatic (INTERACTION.md §1.19): every change is on disk as it happens, so there is no Save, no "unsaved"
mark and no question when leaving a song. A brand-new song nobody changed is removed when it is left, so pressing
New and going elsewhere leaves nothing behind. Switching songs builds a fresh bridge for the new document and loads
the window again; the old window and its engine processes are closed first. (Kit piece 13 replaces this later.)
"""
from __future__ import annotations

import shutil
from pathlib import Path

from PySide6.QtCore import Property, QObject, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices

from rostrum_sound import opening

from . import projects

VERSIONS_LATER = "Everything is saved as you go. Named versions come with the History sheet."


def local(path_or_url: str) -> Path:
    return Path(QUrl(path_or_url).toLocalFile() if "://" in path_or_url else path_or_url)


class Songs(QObject):
    changed = Signal()
    recoverOffered = Signal()          # untitled songs left by a crash (from before saving was automatic) are waiting
    refused = Signal()                 # an open or a duplicate was refused: `error` says why

    def __init__(self, show, parent=None):
        """`show(doc, name)` puts a document on screen (main.py: bridge, its parts, window)."""
        super().__init__(parent)
        self._show, self._doc, self._error = show, None, ""
        self._recoverable: list[Path] = []
        self._fresh: set[str] = set()      # songs made by New in this window (removed when left untouched)

    # ---- reads -------------------------------------------------------------------------------------------------
    @Property(str, notify=changed)
    def folder(self):
        return str(self._doc.folder) if self._doc else ""

    @Property("QVariantList", notify=changed)
    def recent(self):
        here = (str(Path(self._doc.folder).resolve()), self._doc.item_id) if self._doc else None
        return [r for r in projects.recent() if (r["folder"], r["item"]) != here]

    @Property(str, notify=changed)
    def error(self):
        return self._error

    @Property("QVariantList", notify=changed)
    def recoverable(self):
        """The untitled songs a crash left, newest first: each with when it was last changed, in words."""
        return [{"folder": str(f), "when": projects.when_text(f)} for f in self._recoverable]

    @Property(str, constant=True)
    def projectsFolder(self):
        return QUrl.fromLocalFile(str(projects.songs_root())).toString()

    # ---- opening --------------------------------------------------------------------------------------------------
    def start(self, doc, refused: str = ""):
        """The first song on screen (`refused`: why the asked-for song didn't open); then offer back any untitled
        song a crash left behind."""
        self._put(doc)
        if refused:
            self._error = refused
            self.changed.emit()
            self.refused.emit()
        self._recoverable = [f for f in projects.to_recover() if f != Path(doc.folder)]
        if self._recoverable:
            self.changed.emit()
            self.recoverOffered.emit()

    def _put(self, doc):
        old = self._doc
        self._show(doc, projects.title(doc.folder, doc.item_id))
        projects.lock(doc.folder)
        if old is not None and Path(old.folder) != Path(doc.folder):
            projects.unlock(old.folder)
            self._drop_if_untouched(old)
        self._doc, self._error = doc, ""
        projects.remember(doc.folder, doc.item_id)
        self.changed.emit()

    def _drop_if_untouched(self, doc):
        if str(doc.folder) in self._fresh and not projects.changed(doc):
            shutil.rmtree(doc.folder, ignore_errors=True)
        self._fresh.discard(str(doc.folder))

    def _try(self, action) -> bool:
        try:
            action()
            return True
        except Exception as e:  # noqa: BLE001  shown on screen, in words
            self._error = opening.said(e)
            self.changed.emit()
            self.refused.emit()
            return False

    @Slot()
    def newSong(self):
        def go():
            doc = projects.new_song()
            self._fresh.add(str(doc.folder))
            self._put(doc)
        self._try(go)

    @Slot(str)
    def openPath(self, path_or_url):
        def go():
            folder, item = projects.resolve(local(path_or_url))
            self._put(projects.open_song(folder, item))
        self._try(go)

    @Slot(str, str)
    def openRecent(self, folder, item):
        self._try(lambda: self._put(projects.open_song(folder, item)))

    @Slot()
    def openSample(self):
        """≡ › Open sample: the person's own copy of the Lull score (rostrum_core.samples copies it once)."""
        from rostrum_core import samples
        self._try(lambda: self._put(projects.open_song(*samples.open_copy("lull", "sound"))))

    @Slot(str)
    def recover(self, folder):
        def go():
            self._recoverable = [f for f in self._recoverable if str(f) != folder]
            self._put(projects.open_song(folder, projects.ITEM))
        self._try(go)

    @Slot(str)
    def discardRecovered(self, folder):
        self._recoverable = [f for f in self._recoverable if str(f) != folder]
        self._try(lambda: projects.discard_untitled(folder))
        self.changed.emit()

    # ---- the ≡ menu's file actions ---------------------------------------------------------------------------------
    @Slot(result=str)
    def saveVersion(self):
        """Ctrl+S. Every change is already on disk; named versions come with the kit's History (`version.save`)."""
        self._try(self._doc.save)
        return VERSIONS_LATER

    @Slot(str, result=str)
    def duplicate(self, path_or_url):
        """Ctrl+Shift+S: a separate copy of the song in a new folder; this window stays on the original."""
        out = []

        def go():
            dest = projects.duplicate(self._doc.folder, self._doc.item_id, local(path_or_url))
            out.append(f"Duplicated to {dest}. This window stays on the original; the copy is in Open recent.")
            projects.remember(dest, self._doc.item_id)
            projects.remember(self._doc.folder, self._doc.item_id)      # the original stays the newest
        self._try(go)
        self.changed.emit()
        return out[0] if out else ""

    @Slot()
    def showFolder(self):
        if self._doc is not None:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._doc.folder)))

    def close(self):
        """The app is quitting: unlock the song; a brand-new one nobody changed leaves nothing behind."""
        doc = self._doc
        if doc is None:
            return
        projects.unlock(doc.folder)
        self._drop_if_untouched(doc)
