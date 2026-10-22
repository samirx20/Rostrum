"""The open song and the window around it: New, Open, Open recent, Save As, crash recovery (projects.py does the
files; this swaps what is on screen). QML sees it as `songs`.

Switching songs builds a fresh bridge and pages for the new document and loads the window again; the old window
and its engine processes are closed first. Leaving an untitled song that has changes asks first (`askKeep`):
Save… (then the switch goes on), Don't keep, or Cancel.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Property, QObject, QUrl, Signal, Slot

from . import projects


def local(path_or_url: str) -> Path:
    return Path(QUrl(path_or_url).toLocalFile() if "://" in path_or_url else path_or_url)


class Songs(QObject):
    changed = Signal()
    askKeep = Signal()                 # an untitled song with changes is about to be left: Save… / Don't keep / Cancel
    wantSaveAs = Signal()              # open the Save As dialog
    recoverOffered = Signal()          # untitled songs left by a crash are waiting (`recoverable`)

    def __init__(self, show, parent=None):
        """`show(doc, name, untitled)` puts a document on screen (main.py: bridge, pages, window)."""
        super().__init__(parent)
        self._show, self._doc, self._pending, self._error = show, None, None, ""
        self._recoverable: list[Path] = []
        self._drop = None              # an untitled song the person chose not to keep: removed once it is left

    # ---- reads -------------------------------------------------------------------------------------------------
    @Property(bool, notify=changed)
    def untitled(self):
        return bool(self._doc) and projects.is_untitled(self._doc.folder)

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
        return QUrl.fromLocalFile(str(projects.settings.projects_dir())).toString()

    def needs_asking(self) -> bool:
        return self.untitled and projects.changed(self._doc)

    # ---- opening --------------------------------------------------------------------------------------------------
    def start(self, doc):
        """The first song on screen; then offer back any untitled song a crash left behind."""
        self._put(doc)
        self._recoverable = [f for f in projects.to_recover() if f != Path(doc.folder)]
        if self._recoverable:
            self.changed.emit()
            self.recoverOffered.emit()

    def _put(self, doc):
        old = self._doc
        name = projects.title(doc.folder, doc.item_id)
        untitled = projects.is_untitled(doc.folder)
        self._show(doc, name + (" — not saved yet" if untitled else ""), untitled)
        projects.lock(doc.folder)
        if old is not None and Path(old.folder) != Path(doc.folder):
            projects.unlock(old.folder)
            if projects.is_untitled(old.folder) and (not projects.changed(old) or self._drop == old.folder):
                projects.discard_untitled(old.folder)          # an untouched (or not kept) untitled song leaves nothing
        self._doc, self._error = doc, ""
        projects.remember(doc.folder, doc.item_id)
        self.changed.emit()

    def _go(self, action):
        """Run `action` now, or after asking when it would leave an untitled song with changes."""
        if self.needs_asking():
            self._pending = action
            self.askKeep.emit()
            return
        self._try(action)

    def _try(self, action):
        try:
            action()
        except Exception as e:  # noqa: BLE001  shown on screen, in words
            self._error = str(e)
            self.changed.emit()

    @Slot()
    def newSong(self):
        self._go(lambda: self._put(projects.new_song()))

    @Slot(str)
    def openPath(self, path_or_url):
        def go():
            folder, item = projects.resolve(local(path_or_url))
            self._put(projects.open_song(folder, item))
        self._go(go)

    @Slot(str, str)
    def openRecent(self, folder, item):
        self._go(lambda: self._put(projects.open_song(folder, item)))

    @Slot()
    def openSample(self):
        """File › Open sample: the person's own copy of the Lull score (rostrum_core.samples copies it once)."""
        from rostrum_core import samples
        self._go(lambda: self._put(projects.open_song(*samples.open_copy("lull", "sound"))))

    @Slot(str)
    def recover(self, folder):
        def go():
            self._recoverable = [f for f in self._recoverable if str(f) != folder]
            self._put(projects.open_song(folder, projects.ITEM))
        self._go(go)

    @Slot(str)
    def discardRecovered(self, folder):
        self._recoverable = [f for f in self._recoverable if str(f) != folder]
        self._try(lambda: projects.discard_untitled(folder))
        self.changed.emit()

    # ---- saving ----------------------------------------------------------------------------------------------------
    @Slot(result=str)
    def save(self):
        """Ctrl+S. An untitled song asks for a name and place; a named one is already saved (every change is)."""
        if self.untitled:
            self.wantSaveAs.emit()
            return ""
        self._try(self._doc.save)
        return "Saved. Every change is kept as you make it."

    @Slot(str)
    def saveAs(self, path_or_url):
        def go():
            doc = self._doc
            dest = projects.save_as(doc.folder, doc.item_id, local(path_or_url))
            self._doc = None                    # the untitled source is gone; nothing to unlock or discard
            self._put(projects.open_song(dest, doc.item_id))
        self._try(go)
        if self._pending and not self.untitled:
            self.answer("go")

    @Slot(str)
    def answer(self, choice):
        """The askKeep prompt: "save" (Save As, then go on), "discard" (drop the untitled song, go on), "go", "cancel"."""
        action, self._pending = self._pending, None
        if choice == "save":
            self._pending = action
            self.wantSaveAs.emit()
        elif choice in ("discard", "go") and action:
            if choice == "discard":
                self._drop = self._doc.folder
            self._try(action)
        self.changed.emit()

    @Slot(result=bool)
    def mayClose(self) -> bool:
        """The window's close button: ask first for an untitled song with changes (quitting is the pending action)."""
        if not self.needs_asking():
            return True
        from PySide6.QtCore import QCoreApplication
        self._pending = lambda: QCoreApplication.instance().quit()
        self.askKeep.emit()
        return False

    def close(self):
        """The app is quitting: unlock the song; an untouched (or not kept) untitled one leaves nothing behind. An
        untitled song with changes nobody decided about (the app was ended, not closed by the person) keeps its lock,
        so the next start offers it back like after a crash."""
        doc = self._doc
        if doc is None:
            return
        if not projects.is_untitled(doc.folder):
            projects.unlock(doc.folder)
        elif not projects.changed(doc) or self._drop == doc.folder:
            projects.discard_untitled(doc.folder)
        else:
            projects.lock(doc.folder, pid=0)            # no process: offered back on the next start
