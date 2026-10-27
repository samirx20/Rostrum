"""The project's shared markers on a screen (rostrum_core.markers): a list QML can draw as flags, kept fresh when
another app or an agent changes them, the one snap rule for anything dragged along time, and the ruler's marker
edits (add at the playhead, move, rename, delete). Each edit is one marker operation through
rostrum_core.markers.edit, recorded with the person's name in the project's marker history: the same operations
agents call (edit_markers). The watch joins the screen's one undo history (DocBridge.join_history): the screen's
undo takes back a marker edit like any other, and an agent's marker edit shows as who changed what.

A document outside a project folder has no shared markers: `available` is false and the screen shows no marker
controls (rule of individuality). A refused edit (a name taken, a bad time) is reported through `fail`, never
swallowed.
"""
from __future__ import annotations

import sys

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot

from rostrum_core import RostrumError, Who
from rostrum_core import filestamps, live, song_markers
from rostrum_core.markers import current, edit, listing, open_markers, refresh, times, version, watch

from . import marker_menu

POLL_MS = 500          # another process (an agent, Sound) may move a marker: look at the file this often (cheap)
# The poll is also the screen's file tick (rostrum_core.filestamps): between two polls a document change asks the disk
# nothing about project files (the marker file, the joint file, project.json); this process's own writes forget theirs.


class MarkerWatch(QObject):
    changed = Signal()

    def __init__(self, folder, parent=None, who=None, fail=None, owner=""):
        super().__init__(parent)
        self.folder, self.who, self.owner = folder, who or Who.person("sam"), owner
        self._fail = fail or (lambda line: print(line, file=sys.stderr))
        self._stamp, self.times, self._rows, self._last, self._empty = None, {}, [], None, None
        self._unwatch = watch(folder) if folder is not None else (lambda: None)     # the marker document: read on our poll
        self._unfiles = filestamps.watching() if folder is not None else (lambda: None)   # file looks: once per poll
        self._read()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        if folder is not None:
            self._timer.start(POLL_MS)

    def refresh(self):
        filestamps.tick()                               # what the files showed may be old now: each is looked at once again
        if self._read():
            self.changed.emit()

    def rows(self) -> list[dict]:
        """[{id, name, at, colour}] by time, for the ruler's flags; outside RostrumSound's own screen, then each song's
        own markers as read-only flags ({…, shared: False, song: its song's name}: the same markers inspect_markers
        and timing read, rostrum_core.song_markers), one that a project marker repeats at the same time left out."""
        return self._rows

    def snap(self, t: float, within: float) -> float:
        """t moved onto the nearest marker when one is within `within` seconds; else t unchanged."""
        near = min(self.times.values(), key=lambda m: abs(m - t), default=None)
        return near if near is not None and abs(near - t) <= within else t

    def close(self):
        self._timer.stop()
        self._unwatch()
        self._unfiles()

    # ---- one history with the screen's document (DocBridge.join_history) ------------------------------------
    def history_doc(self):
        """The marker document as it is on disk now (None outside a project); live once it exists, so an undo in it
        goes through the one door (rostrum_core.live) like every other save. The document is the one read when the file
        last changed (`_read`): asked on every change of the screen, it looks at no file."""
        if self.folder is None:
            return None
        doc = current(self.folder)                      # one copy per project (rostrum_core.markers): no file work
        if doc is None:
            self._empty = self._empty or open_markers(self.folder)    # no markers yet: one empty document, not saved
            return self._empty
        live.keep(doc)                                  # (idempotent: a live document stays as it is)
        return doc

    def stepped(self, doc):
        """An undo or redo landed in `doc` (from history_doc, saved by its door): show it."""
        doc.save()                                       # (a live document: only catches up; never writes over others)
        self.refresh()

    def last_change(self):
        return self._last

    # ---- edits from the ruler: each one marker operation, one change ------------------------------------------
    @Property(bool, constant=True)
    def available(self):
        return self.folder is not None

    @Slot(float, result=str)
    def add(self, at):
        """A new marker at `at` seconds, named "Marker n" (the first free n); returns its id ("" if refused)."""
        return self.addNamed(self.free_name(), at)

    def free_name(self) -> str:
        """"Marker n", the first n no marker is called yet (what the ruler's name box starts from)."""
        taken = {n.strip().lower() for n in self.times}
        return f"Marker {next(i for i in range(1, len(taken) + 2) if f'marker {i}' not in taken)}"

    @Property(str, notify=changed)
    def freeName(self):
        return self.free_name()

    @Slot(str, float, result=str)
    def addNamed(self, name, at):
        """A new marker called `name` at `at` seconds (the ruler's name box, Enter); its id ("" if refused: said)."""
        args = {"name": name, "at": round(max(at, 0.0), 6), **({"owner": self.owner} if self.owner else {})}
        before = {m["id"] for m in self._rows}
        if not self._edit([{"op": "marker.add", "args": args}], "Add marker"):
            return ""
        return next((m["id"] for m in self._rows if m["id"] not in before), "")

    @Slot(str, float, result=bool)
    def move(self, marker_id, at):
        return self._edit([{"op": "marker.move", "target": [marker_id], "args": {"at": round(max(at, 0.0), 6)}}],
                          "Move marker")

    @Slot(str, str, result=bool)
    def rename(self, marker_id, name):
        return self._edit([{"op": "marker.rename", "target": [marker_id], "args": {"name": name}}], "Rename marker")

    @Slot(str, result=bool)
    def remove(self, marker_id):
        return self._edit([{"op": "marker.remove", "target": [marker_id]}], "Delete marker")

    # ---- the right-click menu (marker_menu.py): rows from the marker operations; a choice is one change -------------
    def _facts(self, marker_id, playhead, shared):
        at = next((m["at"] for m in self._rows if m["id"] == marker_id), 0.0)
        return marker_menu.MarkerFacts([marker_id], playhead, at, self.available, shared)

    @Slot(str, float, bool, result="QVariantList")
    def menu(self, marker_id, playhead, shared):
        """The menu for one marker: only what applies to it now (INTERACTION.md 1.6). `shared`: it is the project's."""
        return marker_menu.rows(self._facts(marker_id, playhead, shared))

    @Slot(str, str, float, bool, result=str)
    def choose(self, marker_id, value, playhead, shared):
        """A row of menu() chosen: its operations run as one change ("" back); the screen's own ones come back as
        their word ("rename": the flag's name field; "share": the app flips shared / own)."""
        try:
            e = marker_menu.entry(self._facts(marker_id, playhead, shared), value)
        except ValueError as err:
            self._fail("Error: " + str(err))
            return ""
        if e["do"]:
            return e["do"]
        self._edit(e["calls"], e["label"])
        return ""

    # ---- inside -----------------------------------------------------------------------------------------------
    def _read(self) -> bool:
        """Re-read when the marker file changed (any edit: time, name, colour); True when it did."""
        stamp = (version(self.folder) if self.folder is not None else 0, self._song_stamp())
        if stamp == self._stamp:
            return False
        if self.folder is not None:
            refresh(self.folder)                        # the shared copy takes in the new lines (or is read again)
        self._stamp, self.times, self._empty = stamp, times(self.folder), None
        doc = current(self.folder) if stamp[0] else None
        self._rows = [{k: m[k] for k in ("id", "name", "at", "colour")} for m in listing(self.folder)] if doc else []
        self._rows = sorted(self._rows + self._song_rows(), key=lambda m: m["at"])
        changes = doc.history.changes if doc else []
        self._last = changes[-1] if changes else None
        return True

    def _song_stamp(self):
        return song_markers.stamp(self.folder) if self.owner != "sound" and self.folder is not None else ()

    def _song_rows(self) -> list[dict]:
        if self.owner == "sound" or self.folder is None:
            return []                                   # Sound's screen draws its songs' markers itself
        mine = {(m["name"].strip().lower(), round(m["at"], 3)) for m in self._rows}
        return [{"id": f'song:{m["item"]}:{m["name"]}', "name": m["name"], "at": m["at"], "colour": "", "shared": False,
                 "song": m["song"]} for m in song_markers.listing(self.folder)
                if (m["name"].strip().lower(), round(m["at"], 3)) not in mine]

    def _edit(self, calls, label) -> bool:
        if self.folder is None:
            self._fail("Error: markers: this document is not in a project folder; shared markers belong to a project.")
            return False
        try:
            edit(self.folder, calls, self.who, label=label)
        except RostrumError as e:
            self._fail(e.line())
            return False
        self.refresh()
        return True
