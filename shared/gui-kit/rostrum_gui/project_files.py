"""The ≡ menu's file actions and the start screen, for any app (QML: `files`; INTERACTION.md 1.19, kit piece 13).
The model and its words are docfiles.py; this is the Qt side.

    files = ProjectFiles(kind, host)    # kind: docfiles.AppFiles; host: .show(doc) puts a document on screen (a new
                                        #   bridge, live when the document has a folder), .bridge is the one shown
    files.launch(path=None, new=False)  # the app's start: that project, else the last one, else the start screen

Every project is live, so nothing here saves. A project made by New and left untouched is removed when it is left,
so pressing New and going elsewhere leaves nothing behind. A refusal (damaged, newer, a taken name) goes to the
message line in words and changes nothing. Scripted runs keep Open recent in their scratch home (userhome).
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

from PySide6.QtCore import Property, QObject, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices
from rostrum_core import RostrumError, codes, live, samples

from . import docfiles as F
from .file_menu import FileMenuSlots
from .keymap import KeyMap

JOBS = {"new": "new", "open": "open", "duplicate": "duplicate_file", "version": "save_version"}
SHOWN_GUIDES = 3


def local(path_or_url: str) -> Path:
    return Path(QUrl(path_or_url).toLocalFile() if "://" in path_or_url else path_or_url)


class ProjectFiles(FileMenuSlots, QObject):
    changed = Signal()
    wanted = Signal(str)                 # "open" | "duplicate" | "version": the menu asks what it must, then acts
    copied = Signal(str)                 # Duplicate made a copy: its name (the menu offers "Open the copy")

    def __init__(self, kind: F.AppFiles, host, parent=None):
        super().__init__(parent)
        self.kind, self.host, self.doc = kind, host, None
        self._fresh, self._copy, self._start, self._said = None, None, False, ""
        km = KeyMap(kind.title)
        self._keys = {v: km.key_of(job) for v, job in JOBS.items()}

    # ---- reads -----------------------------------------------------------------------------------------------
    def _here(self):
        return (str(Path(self.doc.folder).resolve()), self.doc.item_id) if self.has_project() else None

    def has_project(self) -> bool:
        return bool(self.doc is not None and self.doc.folder)

    def _rows(self):
        here = self._here()
        return [{**r, "thumb": QUrl.fromLocalFile(r["thumb"]).toString() if r["thumb"] else ""}
                for r in F.recent(self.kind) if (r["folder"], r["item"]) != here]

    name = Property(str, lambda s: Path(s.doc.folder).name if s.has_project() else "", notify=changed)
    hasProject = Property(bool, has_project, notify=changed)
    recent = Property("QVariantList", _rows, notify=changed)
    startShown = Property(bool, lambda s: s._start, notify=changed)
    projectsFolder = Property(str, lambda s: str(F.projects_root(s.kind)), notify=changed)
    projectsUrl = Property(str, lambda s: QUrl.fromLocalFile(str(F.projects_root(s.kind))).toString(), notify=changed)
    hasSample = Property(bool, lambda s: bool(s.kind.sample), constant=True)
    noun = Property(str, lambda s: s.kind.noun, constant=True)
    keys = Property("QVariantMap", lambda s: dict(s._keys), constant=True)
    copyName = Property(str, lambda s: s._copy[0].name if s._copy else "", notify=changed)
    guides = Property("QVariantList", lambda s: [{"value": QUrl.fromLocalFile(str(p)).toString(), "label": label}
                                                 for p, label in s.kind.guides[:SHOWN_GUIDES]], constant=True)

    @Slot(result=str)
    def versionName(self):
        return F.version_name()

    # ---- start ---------------------------------------------------------------------------------------------------
    def launch(self, path=None, new=False):
        """That project (a double-clicked file), else the last one where it was left, else the start screen. One that
        can't open never stops the app: the start screen shows and the message line says why."""
        if new and self.newProject():
            return
        if path and self.openPath(str(path)):
            return
        rows = [] if path or new else F.recent(self.kind)
        if rows and self._open(rows[0]["folder"], rows[0]["item"]):
            return
        self.put(self.kind.blank(None))                 # nothing open: a blank in memory under the start screen
        self.setStart(True)

    @Slot(bool)
    def setStart(self, on):
        """≡ › Start screen… (on) and its Back / Esc (off)."""
        self._start = bool(on)
        self.changed.emit()

    # ---- the actions -----------------------------------------------------------------------------------------------
    @Slot(result=bool)
    @Slot(str, result=bool)
    def newProject(self, name=""):
        def go():
            root = F.projects_root(self.kind)
            folder = root / F.clean(name) if name else F.new_folder(root, self.kind.untitled)
            if folder.exists():
                raise RostrumError(codes.CONFLICT, "new", str(folder), "already exists", hint="Pick another name.")
            doc = self.kind.blank(folder)
            self.put(doc)
            self._fresh = Path(doc.folder)
        return self._try(go)

    @Slot(str, result=bool)
    def openPath(self, path):
        return self._try(lambda: self._open(*self.kind.resolve(local(path)), quiet=False))

    @Slot(int, result=bool)
    def openRecent(self, i):
        rows = self._rows()
        return 0 <= i < len(rows) and self._try(lambda: self._open(rows[i]["folder"], rows[i]["item"], quiet=False))

    @Slot(result=bool)
    def openSample(self):
        """The app's sample, as the person's own copy (rostrum_core.samples): the original never changes."""
        return self._try(lambda: self._open(*samples.open_copy(self.kind.sample, self.kind.app), quiet=False))

    @Slot(result=bool)
    def openCopy(self):
        return bool(self._copy) and self._try(lambda: self._open(*self._copy, quiet=False))

    @Slot(str, result=bool)
    def duplicate(self, target):
        """A separate copy of the whole project (a name in the projects folder, or a picked folder). This window
        stays on the original and says so; the copy is in Open recent and in "Open the copy"."""
        def go():
            dest = local(target) if ("/" in target or "\\" in target) else F.projects_root(self.kind) / F.clean(target)
            if self.kind.snapshot and self.host.bridge is not None:
                self._picture(self.host.bridge, self.doc)        # the copy shows the same picture on the start screen
            new = F.duplicate(self.doc.folder, dest)
            item = self.doc.item_id
            fix = self.kind.after_copy
            if fix:
                fix(F.open_whole(self.kind, new, item), self.doc.folder, new)
            F.remember(self.kind, new, item, new.name)
            F.remember(self.kind, self.doc.folder, item, self._name())     # the original stays the newest
            self._copy = (new, item)
            self._say(f'Duplicated as "{new.name}". This window stays on "{self._name()}".')
            self.copied.emit(new.name)
        return self._try(go)

    @Slot()
    def showFolder(self):
        if self.has_project():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.doc.folder)))

    @Slot(str, result=bool)
    def saveVersion(self, name):
        """Save a version (Ctrl+S): a name for the document as it is now; the time when no name is given."""
        return bool(self.host.bridge.saveVersion(name.strip() or F.version_name()))

    # ---- inside ------------------------------------------------------------------------------------------------
    def _name(self):
        return F.name_of(self.doc.folder, self.doc.item_id)

    def _open(self, folder, item, quiet=True) -> bool:
        try:
            doc = F.open_whole(self.kind, folder, item)
        except RostrumError as e:
            if not quiet:
                raise
            self._said = F.said(e)
            return False
        self.put(doc)
        return True

    def put(self, doc):
        """Show `doc` (also how an app shows one it opened itself: --doc, --sample); leave the old one (its picture kept for the start screen; a New one nobody changed removed)."""
        old, bridge = self.doc, self.host.bridge
        if doc.folder and doc.item_id:
            live.keep(doc)                               # every project is live (the bridge's LiveLink shows agents' steps)
        if old is not None and old.folder and self.kind.snapshot and bridge is not None:
            self._picture(bridge, old)
        self.host.show(doc)
        if self._fresh and old is not None and Path(old.folder or "") == self._fresh:
            if not old.history.changes and Path(doc.folder or "") != self._fresh:
                shutil.rmtree(self._fresh, ignore_errors=True)
            self._fresh = None
        self.doc, self._start = doc, False
        if self.has_project():
            F.remember(self.kind, doc.folder, doc.item_id, self._name())
        self.changed.emit()
        if self._said:
            self._say("Error: " + self._said)
            self._said = ""

    def _picture(self, bridge, doc):
        try:
            img = self.kind.snapshot(bridge)
            if img is not None and not img.isNull():
                pic = F.thumb(doc.folder, doc.item_id)
                pic.parent.mkdir(parents=True, exist_ok=True)
                img.scaledToWidth(min(480, img.width())).save(str(pic))
        except Exception as e:  # noqa: BLE001  a missing picture never stops leaving a project
            print(f"start screen picture not kept: {e}", file=sys.stderr)

    def close(self):
        """The app is quitting: keep the picture; a New project nobody changed leaves nothing behind."""
        if self.doc is not None and self.has_project() and self.kind.snapshot and self.host.bridge is not None:
            self._picture(self.host.bridge, self.doc)
        if self._fresh and self.doc is not None and not self.doc.history.changes:
            shutil.rmtree(self._fresh, ignore_errors=True)

    def _say(self, line):
        if self.host.bridge is not None:
            self.host.bridge.say(line)

    def _try(self, fn) -> bool:
        try:
            fn()
            return True
        except (RostrumError, OSError, ValueError) as e:
            line = "Error: " + F.said(e)
            if self.host.bridge is None:
                raise
            self._say(line)
            print(line, file=sys.stderr)
            return False
