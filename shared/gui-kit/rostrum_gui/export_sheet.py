"""The Export sheet's state and flow, the same in every app (INTERACTION.md 1.19 item 8; qml ExportSheet.qml, JobChip.qml).

An app subclasses `ExportSheet` and fills in only what is its own: the "What for" list, the ranges its document has,
the default folder, the file's name, and the work itself (`begin` on the GUI thread, `work` on a worker thread,
`stop` to cancel). Everything else is here, once:
- open / closed (one flag: the top bar's Export, Ctrl+E and a scripted step open the same sheet);
- where it goes: the project's Renders folder ("" = the app's default, a new version folder each time, so nothing
  is ever replaced), or a folder the person chose with Browse;
- Export: a file already there is never replaced without asking: `asked(name, canReplace)` → `answer(replace|both|
  cancel)`; Keep both writes "name 2.ext" (`free_path`);
- the job in the background, progress, Cancel; a failure is red, in words, and the old file stays;
- done: the message line says "Exported Main.mp4" (Play · Show in folder beside it) and the version is marked
  ("Exported v003", `doc.mark_version`);
- again (Ctrl+Shift+E): the last settings, without opening the sheet.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import threading
from pathlib import Path

from PySide6.QtCore import Property, QCoreApplication, QObject, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices

from . import export_errors


def free_path(path: Path) -> Path:
    """`path`, or "name 2.ext", "name 3.ext" … the first that isn't there (Keep both: nothing is ever replaced)."""
    path, n, found = Path(path), 2, Path(path)
    while found.exists():
        found = path.with_name(f"{path.stem} {n}{path.suffix}")
        n += 1
    return found


def version_name(result: dict, versions) -> str:
    """"Exported v003": the render's own version when it made one, else the next free number."""
    v = result.get("version")
    if isinstance(v, int) or (isinstance(v, str) and v.isdigit()):
        v = f"v{int(v):03d}"
    if not v:
        n = 1 + sum(1 for k in versions if str(k).startswith("Exported v"))
        while f"Exported v{n:03d}" in versions:
            n += 1
        v = f"v{n:03d}"
    return f"Exported {v}"


class ExportSheet(QObject):
    CHOICES_PICKER = False                        # "What for" as one picker, not rows (see `choicesPicker`)
    RANGE_ROOM = False                            # keep the range picker's place while the document has only "everything" (see `rangeRoom`)
    WHAT = "the file"                            # what a failed save names ("Couldn't save the file: …")
    VERBS = ("Export", "Exporting", "Exported")   # an app whose sheet makes something else says so ("Render", …)
    changed = Signal()
    asked = Signal(str, bool)                  # (the name already there, whether it can be replaced): QML asks
    _landed = Signal("QVariantMap", str)       # (the result, the error line): from the worker thread
    _progressed = Signal(float)

    def __init__(self, bridge, parent=None):
        super().__init__(parent or bridge)
        self.bridge = bridge
        self._open, self._choice, self._range, self._folder = False, "", "all", ""
        self._state, self._note, self._progress, self._result = "", "", 0.0, {}
        self._asked: Path | None = None
        self._stem_chosen = ""                      # the name typed in the sheet ("" = the app's default)
        self._can_replace = True
        self._done_message = ""
        self._thread: threading.Thread | None = None
        self._stopping = False
        self._landed.connect(self._finish)
        self._progressed.connect(self._on_progress)

    # ---- what an app fills in ---------------------------------------------------------------------------------
    def choices_list(self) -> list[dict]:
        """"What for": [{value, label, type}] ("For the web", "MP4 · .mp4")."""
        raise NotImplementedError

    def ranges_list(self) -> list[dict]:
        """[{value, label, start, end}], "all" first; only what the document has (markers, a time range)."""
        return []

    def default_folder(self) -> str:
        """Where it goes when the person chose no folder, in words (the project's Renders folder)."""
        raise NotImplementedError

    NAMEABLE = False                              # True: the person may name the file (an app that implements default_stem + file_ext)

    def default_stem(self) -> str:
        """The file's name without its type when the person named nothing ("Main"); a nameable app says it."""
        raise NotImplementedError

    def file_ext(self) -> str:
        """The file type after the name (".mp4"); "" for a sequence (its folder's name stands alone)."""
        return ""

    def file_name(self) -> str:
        """The file's name for the current choice ("Main.mp4"; a sequence: its folder's name). A nameable app gets it from
        the stem and the type; any other app says its own."""
        return self.stem() + self.file_ext()

    def stem(self) -> str:
        """The name the file is written under (without its type): the person's, else the app's default."""
        return self._stem_chosen or self.default_stem()

    def replaceable(self) -> bool:
        """False for something that can't be replaced in place (a folder of frames): only Keep both / Cancel."""
        return True

    def chose(self):
        """A new choice was made: reset that choice's own settings (the app's)."""

    def begin(self, out: Path | None, overwrite: bool) -> dict:
        """On the GUI thread: snapshot what is exported (edits made while it runs are not in the file) and return
        what `work` needs. Raise (with a sentence) to refuse."""
        raise NotImplementedError

    def work(self, plan: dict, progress) -> dict:
        """On the worker thread: write the file(s). Return {"files": [...], "file": main path, "version"?: "v003"}.
        `progress(0..1)`; raise on failure (the old file stays: write under a temporary name, then rename)."""
        raise NotImplementedError

    def stop(self):
        """Cancel the running work (stop the engine). The default can't: Cancel is not offered."""

    def can_cancel(self) -> bool:
        return type(self).stop is not ExportSheet.stop

    def action_text(self) -> str:
        """The sheet's button: "Export", or the app's own words for what it will make ("Render 120 frames")."""
        return self.VERBS[0]

    # ---- what QML shows ---------------------------------------------------------------------------------------
    @Property(bool, notify=changed)
    def open(self):
        return self._open

    @Property("QVariantList", notify=changed)
    def choices(self):
        return self.choices_list()

    @Property(bool, constant=True)
    def choicesPicker(self):
        """True: "What for" is one picker (a short field with a list) instead of rows. An app with a few plain choices
        and no file type to show beside each one sets it (Sound); the default is the rows."""
        return self.CHOICES_PICKER

    @Property(bool, constant=True)
    def rangeRoom(self):
        """True: the range picker's place stays empty until the document has a range or section, so the picker arriving
        (a section added, a range dragged) never moves the rows under the pointer. An app whose ranges come and go sets it."""
        return self.RANGE_ROOM

    @Property(str, notify=changed)
    def choice(self):
        return self._choice

    @Property("QVariantList", notify=changed)
    def ranges(self):
        return self.ranges_list()

    @Property(str, notify=changed)
    def range(self):
        return self._range

    @Property(str, notify=changed)
    def folder(self):
        """The folder the person chose ("" = the default)."""
        return self._folder

    @Property(str, notify=changed)
    def where(self):
        """Where the file goes: the folder chosen; once an export is done, the folder it really wrote into (the result's
        own path, never the next version's); else what the next export will write."""
        if self._folder:
            return self._folder
        if self._state == "done" and self.path:
            return str(Path(self.path).parent)
        return self.default_folder()

    def short_where(self, where: str) -> str:
        """`where` as the sheet shows it (the whole path shows on hover). The default is all of it; an app with long
        project paths shortens them to the folder's own name."""
        return where

    @Property(str, notify=changed)
    def whereShort(self):
        return self.short_where(self.where)

    @Property(str, notify=changed)
    def fileName(self):
        return self.file_name()

    @Property(bool, constant=True)
    def nameable(self):
        """True: the sheet shows the name as a field the person can type in (nameStem, then the file type after it)."""
        return self.NAMEABLE

    @Property(str, notify=changed)
    def nameStem(self):
        return self.stem() if self.NAMEABLE else ""        # an app that doesn't name its files shows fileName instead

    @Property(str, notify=changed)
    def nameExt(self):
        return self.file_ext() if self.NAMEABLE else ""

    @Property(str, notify=changed)
    def state(self):
        """"" | "running" | "done" | "failed" | "cancelled"."""
        return self._state

    @Property(float, notify=changed)
    def progress(self):
        """0..1, or -1 while the work can't say how far it is."""
        return self._progress

    @Property(str, notify=changed)
    def note(self):
        """While running: "Exporting Main.mp4"; failed: the sentence; done: what was made."""
        return self._note

    @Property(str, notify=changed)
    def path(self):
        return self._result.get("file", "")

    @Property(str, notify=changed)
    def doneMessage(self):
        """The message line's words when it finished ("Exported Main.mp4"): Play · Show in folder show beside it
        while the message still says this."""
        return self._done_message

    @Property(str, notify=changed)
    def actionText(self):
        return self.action_text()

    @Property(str, constant=True)
    def doneWord(self):
        return self.VERBS[2]

    @Property(bool, notify=changed)
    def cancellable(self):
        return self.can_cancel()

    # ---- what a person does -----------------------------------------------------------------------------------
    @Slot(bool)
    def setOpen(self, on):
        if bool(on) != self._open:
            self._open = bool(on)
            self.changed.emit()

    @Slot(str)
    def setChoice(self, value):
        if self.running() or value == self._choice or value not in [c["value"] for c in self.choices_list()]:
            return
        self._choice = value
        self.chose()
        self.stale()
        self.changed.emit()

    def stale(self):
        """A choice changed: the last result's line no longer describes what Export would make (the sheet says what the
        new choices come to instead). Never during a run."""
        if self._state != "running":
            self._state, self._note = "", ""

    @Slot(str)
    def setRange(self, value):
        if not self.running() and value in [r["value"] for r in self.ranges_list()]:
            self._range = value
            self.stale()
            self.changed.emit()

    def range_times(self) -> tuple[float, float] | None:
        """(start, end) of the chosen range; None = everything."""
        r = next((r for r in self.ranges_list() if r["value"] == self._range), None)
        return (float(r["start"]), float(r["end"])) if r and r["value"] != "all" else None

    @Slot(str)
    def setNameStem(self, text):
        """The file's name typed in the sheet (what a file name can't hold is dropped; empty goes back to the default)."""
        if self.NAMEABLE and not self.running():
            self._stem_chosen = re.sub(r"\s+", " ", re.sub(r'[\\/:*?"<>|\x00-\x1f]', " ", text)).strip(" .")
            if self._stem_chosen == self.default_stem():
                self._stem_chosen = ""
            self.stale()
            self.changed.emit()

    @Slot(str)
    def setFolder(self, path):
        """A folder from Browse (a file:// url or a path); "" goes back to the default."""
        if not self.running():
            self._folder = QUrl(path).toLocalFile() if path.startswith("file:") else path
            self.changed.emit()

    def planned(self) -> Path | None:
        """The exact path that will be written (None: a new version folder, which can't clash)."""
        return Path(self._folder) / self.file_name() if self._folder else None

    @Slot()
    def request(self):
        """The Export button: ask first when the file is already there, else start."""
        if self.running():
            return
        out = self.planned()
        if out is not None and out.exists():
            self._asked, self._can_replace = out, self.replaceable()
            return self.asked.emit(out.name, self._can_replace)
        self._go(out, False)

    @Slot(str)
    def answer(self, choice):
        """replace | both (Keep both: " 2" added) | anything else cancels: nothing is written."""
        out, self._asked = self._asked, None
        if out is None or choice not in ("replace", "both") or (choice == "replace" and not self._can_replace):
            return
        self._go(free_path(out) if choice == "both" else out, choice == "replace")

    def asking(self) -> bool:
        return self._asked is not None

    @Slot()
    def again(self):
        """Ctrl+Shift+E: export with the last settings, without opening the sheet (a file there is still asked about).
        With no export made yet there are no "last settings": it says so and starts nothing."""
        if not self._started:
            return self.bridge._set_status(f"Nothing {self.VERBS[2].lower()} yet — Ctrl+E to {self.VERBS[0].lower()}", False)
        self.request()

    @Slot()
    def cancel(self):
        if self.running() and not self._stopping and self.can_cancel():
            self._stopping = True
            self._note = "Cancelling…"
            self.changed.emit()
            self.stop()

    @Slot()
    def dismiss(self):
        """The job chip's failure, read: it goes."""
        if not self.running():
            self._state, self._note = "", ""
            self.changed.emit()

    @Slot()
    def play(self):
        """Open the result in the computer's own player."""
        if self.path:
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.path))

    @Slot()
    def showInFolder(self):
        f = self.path
        if not f:
            return
        if sys.platform == "win32":
            subprocess.Popen(["explorer", f"/select,{os.path.normpath(f)}"] if Path(f).is_file() else ["explorer", str(Path(f).parent)])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", f])
        else:
            subprocess.Popen(["xdg-open", str(Path(f).parent)])

    # ---- the job ----------------------------------------------------------------------------------------------
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive() or self._state == "running"

    def wait(self, timeout_s: float) -> bool:
        """For scripted steps: block until the job is over (True) or the time is up; the result lands on this thread."""
        if self._thread is not None:
            self._thread.join(timeout_s)
        QCoreApplication.processEvents()
        return not self.running()

    _started = False                             # an export was started in this window (Ctrl+Shift+E repeats it)

    def _go(self, out, overwrite):
        try:
            plan = self.begin(out, overwrite)
        except Exception as e:  # noqa: BLE001  refused before it started: say why, nothing written
            return self._finish({}, export_errors.said(e, self.WHAT))
        self._started = True
        self._result, self._progress, self._stopping = {}, 0.0, False
        self._state, self._note = "running", f"{self.VERBS[1]} {out.name if out else self.file_name()}"
        self.changed.emit()
        self.bridge._set_status(self._note + "…")

        def run():
            try:
                self._landed.emit(dict(self.work(plan, self._progressed.emit)), "")
            except Exception as e:  # noqa: BLE001  fail loudly, whatever it was (a cancel is the one expected stop)
                self._landed.emit({}, "" if self._stopping else export_errors.said(e, self.WHAT))
        self._thread = threading.Thread(target=run, name="export", daemon=True)
        self._thread.start()

    def _shown_name(self) -> str:
        """What the finished export is called to a person: the file's name; a sequence (its path holds {frame}): its real
        first and last file, "48 pictures, Scene_0001.png to Scene_0048.png"."""
        name = Path(self.path).name
        if "{frame}" not in name:
            return name
        rx = re.compile(re.escape(name).replace(re.escape("{frame}"), r"\d+") + "$")
        found = sorted(p.name for p in Path(self.path).parent.iterdir() if rx.match(p.name)) if Path(self.path).parent.is_dir() else []
        if not found:
            return name.replace("{frame}", "0001")
        return found[0] if len(found) == 1 else f"{len(found)} pictures, {found[0]} to {found[-1]}"

    def _on_progress(self, p):
        if self._state == "running":
            self._progress = p
            self.changed.emit()

    def _finish(self, result, error):
        self._thread = None
        b = self.bridge
        if self._stopping and not error and not result.get("files"):
            self._state, self._note, self._result, self._done_message = "cancelled", "Cancelled", {}, ""
            b._set_status(f"{self.VERBS[0]} cancelled")
        elif error or not result.get("files"):
            self._state, self._result, self._done_message = "failed", {}, ""
            self._note = error or "Error: export: nothing was written. The old file, if any, is kept."
            b._set_status(self._note, True)        # (the full line is already on the console: export_errors.said)
        else:
            self._state, self._result, self._progress = "done", dict(result), 1.0
            mark = getattr(b.doc, "mark_version", None)
            if mark is not None:
                mark(version_name(result, b.doc.versions() if hasattr(b.doc, "versions") else {}))
            self._done_message = f"{self.VERBS[2]} {self._shown_name()}"
            self._note = result.get("summary") or self._done_message
            b._set_status(self._done_message)
        self._stopping = False
        self.changed.emit()
