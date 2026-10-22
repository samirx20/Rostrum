"""The File menu: New, Open, Open recent, Save, Save As, the recovery copy and the unsaved mark (QML: `files`).

A person's file is a project folder (projects.py). Two ways a window holds its document:
- **saved by hand** (New, Open, a launch without --doc): edits mark it unsaved; every AUTOSAVE_S while unsaved a recovery
  copy is written (never over the saved file); Save writes the document and its history and drops the recovery copy.
- **live** (--doc, what launchers and agents use): saved after every change, as before; nothing is ever unsaved.
Save refuses when the saved file changed since this window read it (an agent or another window saved there): nothing
is overwritten; Save As keeps this window's version as a new project.
Opening another document makes a new window for it (session.py); this object lives across them. What to ask the person
first (save changes? which name?) is QML's (FileFlow.qml); every action here acts at once.
"""
from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtCore import Property, QObject, QTimer, QUrl, Signal, Slot
from rostrum2d import KIND, settings
from rostrum_core import Document, RostrumError, Who, codes
from rostrum_core.storage import doc_hash

from . import projects, recent

AUTOSAVE_S = 60


class Files(QObject):
    changed = Signal()
    wanted = Signal(str)                 # a Ctrl+K file command: QML asks what it must (FileFlow.act), then acts

    def __init__(self, host, who: Who | None = None, parent=None):
        super().__init__(parent)
        self.host, self.who = host, who or Who.person("sam")
        self.doc, self.live, self._saved, self._unsub, self._recovery, self._unsaved = None, False, None, None, None, False
        self._recent: list[dict] = []
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.autosave)
        self._timer.start(AUTOSAVE_S * 1000)

    # ---- what the window shows ------------------------------------------------------------------------------
    @Property(str, notify=changed)
    def name(self):
        return Path(self.doc.folder).name if self.doc and self.doc.folder else "Untitled"

    @Property(bool, notify=changed)
    def unsaved(self):
        return self._unsaved

    @Property(bool, notify=changed)
    def hasFolder(self):
        return bool(self.doc and self.doc.folder)

    @Property(str, notify=changed)
    def label(self):
        """The title bar's and the top bar's name: the project, and a dot while there are unsaved changes."""
        return self.name + (" •" if self.unsaved else "")

    @Property(str, notify=changed)
    def recoveryAt(self):
        """When the recovery copy offered on open was written ("" = none to offer)."""
        if not self._recovery:
            return ""
        at = time.localtime(self._recovery)
        day = "today" if time.strftime("%x", at) == time.strftime("%x") else time.strftime("%d %b", at).lstrip("0")
        return f"{day} at {time.strftime('%H:%M', at)}"

    @Property(str, constant=True)
    def projectsFolder(self):
        return str(settings.projects_dir())

    @Property(str, notify=changed)
    def suggestedName(self):
        return projects.untitled() if not self.hasFolder else f"{self.name} copy"

    @Property("QVariantList", notify=changed)
    def menu(self):
        """The File menu's rows: the actions (with their shortcut), then the recent projects by name."""
        return [{**c, "label": c["label"].removeprefix("Open ") if c["hint"] == "Recent" else c["label"]}
                for c in self.commands()]

    # ---- holding a document (session.py calls this for each window) -------------------------------------------
    def hold(self, doc, live: bool, ask_recovery: bool = True):
        """This window's document. `live`: saved after every change (--doc). A newer recovery copy is offered on open."""
        if self._unsub:
            self._unsub()
        self.doc, self.live = doc, live
        self._saved = projects.disk_hash(doc.folder, doc.item_id) if doc.folder else None
        self._unsub = doc.subscribe(lambda ev: self._touched())
        fresh = doc.folder and not live and ask_recovery
        self._recovery = projects.recovery_time(doc.folder, doc.item_id) if fresh else None
        if doc.folder:
            recent.add(doc.folder, doc.item_id)
        here = (str(Path(doc.folder).resolve()), doc.item_id) if doc.folder else None
        self._recent = [r for r in recent.rows() if (r["folder"], r["item"]) != here]
        self._touched()

    def _touched(self):
        self._unsaved = not self.live and doc_hash(self.doc.data) != self._saved
        self.changed.emit()

    # ---- the actions -----------------------------------------------------------------------------------------
    @Slot(str, result=bool)
    def newProject(self, name=""):
        return self._try(lambda: self.host.show(projects.new_project(name or projects.untitled()), False))

    @Slot(str, result=bool)
    def openPath(self, path):
        """A picked doc file or project folder (a file:// url or a path)."""
        path = QUrl(path).toLocalFile() if path.startswith("file:") else path
        def go():
            folder, item = projects.resolve(path)
            self.host.show(Document.open(folder, item, KIND), False)
        return self._try(go)

    @Slot(int, result=bool)
    def openRecent(self, i):
        return 0 <= i < len(self._recent) and self.openPath(self._recent[i]["path"])

    @Slot(result=bool)
    def save(self):
        def go():
            if self.doc.folder is None:
                raise RostrumError(codes.BAD_ARGUMENT, "save", "this document", "has no project folder yet",
                                   hint="Use Save as to give it a name.")
            if projects.disk_hash(self.doc.folder, self.doc.item_id) not in (self._saved, None):
                raise RostrumError(codes.CONFLICT, "save", str(self.doc.folder), "was saved by someone else (an agent or "
                                   "another window) since this window opened it; nothing was overwritten",
                                   hint="Use Save as to keep your version as a new project.")
            self.doc.save()
            projects.clear_recovery(self.doc.folder)
            self._saved, self._recovery = doc_hash(self.doc.data), None
            self._touched()
        return self._try(go)

    @Slot(str, result=bool)
    def saveAs(self, name):
        def go():
            old = self.doc.folder
            new = projects.save_as(self.doc, name, self.who)
            if old:
                projects.clear_recovery(old)      # the unsaved changes now live in the new project
            self.host.show(new, False, ask_recovery=False)
        return self._try(go)

    @Slot(result=bool)
    def autosave(self):
        """The recovery copy, while there are unsaved changes in a project folder."""
        if not (self._unsaved and self.doc.folder):
            return True
        return self._try(lambda: projects.write_recovery(self.doc))

    @Slot(result=bool)
    def restore(self):
        folder, item = self.doc.folder, self.doc.item_id
        return self._try(lambda: self.host.show(projects.open_recovery(folder, item), False, ask_recovery=False))

    @Slot()
    def discard(self):
        """Drop the recovery copy (Discard on open, Don't save before closing or opening another)."""
        if self.doc and self.doc.folder:
            projects.clear_recovery(self.doc.folder)
        self._recovery = None
        self.changed.emit()

    # ---- Ctrl+K ----------------------------------------------------------------------------------------------
    def commands(self) -> list[dict]:
        """The file actions that apply now (absent, not greyed): Save only while there is something to save."""
        out = [("file:new", "New project", "Ctrl N"), ("file:open", "Open…", "Ctrl O")]
        if self._unsaved and self.hasFolder:
            out.append(("file:save", "Save", "Ctrl S"))
        out.append(("file:saveas", "Save as…" if self.hasFolder else "Save…", "Ctrl Shift S"))
        out += [(f"file:recent:{i}", f"Open {r['label']}", "Recent") for i, r in enumerate(self._recent)]
        return [{"key": k, "label": label, "hint": hint} for k, label, hint in out]

    def run(self, key: str) -> bool:
        if not any(c["key"] == key for c in self.commands()):
            self.host.fail(f'Error: command bar: "{key}" is not available right now.')
            return False
        self.wanted.emit(key)
        return True

    # ---- inside ----------------------------------------------------------------------------------------------
    def _try(self, fn) -> bool:
        """Run a file action; a failure is said on screen (the status line, red) and returns False, never a crash."""
        try:
            fn()
            return True
        except (RostrumError, OSError, ValueError, RuntimeError) as e:
            self.host.fail(e.line() if isinstance(e, RostrumError) else f"Error: {e}")
            return False
