"""The Library panel (Instruments page): the user's own sound folders, searched by kind and shape, each sound heard
on its own and placed on a track at the playhead. Exposed to QML as `soundLibrary`.

Rule of individuality: with no folder yet the panel offers only "Add a sound folder"; the search, the shape choices
and the results appear once there is something to search. Indexing a folder runs off the screen's thread (the first
time a large folder takes a while; an unchanged one comes back from the index at once). Auditioning renders the entry
through the engine and plays it on the engine's live player (auditioner.py): a file's own stretch, or an adder entry
(an instrument on the selected track's notes, a kit). Placing is one operation call (`clip.add`, plus
`track.add` when there is no track to put it on), so it is one undo step, exactly what an agent would call.
"""
from __future__ import annotations

import threading

from PySide6.QtCore import Property, QObject, QUrl, Signal, Slot
from rostrum_sound import userlib
from rostrum_sound.userlib.kinds import OFFERED

from .adder import ENTRIES, placed_at
from .auditioner import Auditioner
from .swap_trial import SwapTrial

ANY = ""
LIMIT = 60
TRACK = "sfx"                       # where sounds go when the selected track plays an instrument


def _choices(values) -> list[dict]:
    return [{"value": ANY, "label": "Any"}] + [{"value": v, "label": v.capitalize()} for v in values]


def _row(s: dict) -> dict:
    name = s["path"].replace("\\", "/").rsplit("/", 1)[-1]
    return {"path": s["path"], "start": s["start"], "end": s["end"], "name": name, "kind": s["kind"],
            "peak_s": s.get("peak_s", 0), "onset_s": s.get("onset_s", 0),
            "what": f"{s['kind']} · {s['seconds']:.2f} s · {s['words']['brightness']} · {s['words']['attack']} attack",
            "inFile": f"at {s['start']:.2f} s in the file" if s["start"] > 0.05 else ""}


PEAKED = ("whoosh", "riser")       # placed by their loudest moment; the rest by their onset (DESIGN.md §3.13 point 2)


class LibraryPanel(QObject):
    changed = Signal()
    _indexed = Signal(str, str)         # (folder, error) from the indexing thread

    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        self.bridge = bridge
        self._folders = userlib.list_folders()
        self._text, self._kind, self._length, self._bright = "", ANY, ANY, ANY
        self._results: list[dict] = []
        self._total, self._busy, self._status = 0, "", ""
        self._heard = Auditioner(bridge, self)
        self._heard.changed.connect(self.changed)
        self._heard.failed.connect(self._heard_failed)
        self._trial = SwapTrial(bridge)
        bridge.picksChanged.connect(self._picked)       # a clip picked: the rows offer Swap; another pick ends a trial
        bridge.docChanged.connect(self._doc)
        bridge.library_panel = self             # the scripted steps reach the panel from the bridge
        self._indexed.connect(self._done)
        if self._folders:
            self._index(self._folders)

    def _doc(self):
        """Of the song, the panel shows only which clip a result may take the place of (`swapTarget`): a change is
        news here only when that moved (every note drawn re-ran every row's bindings)."""
        self._follow_target()

    def _follow_target(self):
        now = self.swapTarget
        if now != self.__dict__.get("_target_shown"):
            self._target_shown = now
            self.changed.emit()

    # ---- reads for QML ----------------------------------------------------------------------------------------
    @Property(str, notify=changed)
    def swapTarget(self):
        """The one selected clip a result can take the place of ("" when none: the rows only Place)."""
        ids = self.bridge.selectedIds
        return ids[0] if len(ids) == 1 and self.bridge.doc.has(ids[0]) and self.bridge.doc.item(ids[0])["type"] == "clip" else ""

    @Property(int, notify=changed)
    def swapRow(self):
        """The result on show in the clip's place while stepping (-1: the original, or not stepping)."""
        return self._trial.row

    @Property(bool, notify=changed)
    def swapping(self):
        """Stepping through candidates: Enter keeps the one on show, Esc puts the original back."""
        return self._trial.active

    @Property(bool, notify=changed)
    def hasFolders(self):
        return bool(self._folders)

    @Property("QStringList", notify=changed)
    def folders(self):
        return self._folders

    @Property(str, notify=changed)
    def busy(self):
        """What is being indexed right now ("" when idle)."""
        return self._busy

    @Property(str, notify=changed)
    def status(self):
        return self._status

    @Property(str, notify=changed)
    def text(self):
        return self._text

    @Property(str, notify=changed)
    def kind(self):
        return self._kind

    @Property(str, notify=changed)
    def length(self):
        return self._length

    @Property(str, notify=changed)
    def brightness(self):
        return self._bright

    @Property(int, notify=changed)
    def filterCount(self):
        """How many of kind / length / tone narrow the list now (the Filter button says so)."""
        return sum(bool(v) for v in (self._kind, self._length, self._bright))

    @Property("QVariantList", constant=True)
    def kindChoices(self):
        return _choices(OFFERED)

    @Property("QVariantList", constant=True)
    def lengthChoices(self):
        return _choices(["short", "medium", "long"])

    @Property("QVariantList", constant=True)
    def brightnessChoices(self):
        return _choices(["dark", "mid", "bright"])

    @Property("QVariantList", notify=changed)
    def results(self):
        return self._results

    @Property(int, notify=changed)
    def total(self):
        return self._total

    # ---- actions ----------------------------------------------------------------------------------------------
    @Slot(str)
    def addFolder(self, chosen):
        """A folder from the folder picker (a file:// URL or a path): listed in the user's settings, then indexed."""
        path = QUrl(chosen).toLocalFile() if chosen.startswith("file:") else chosen
        try:
            path = userlib.folders.add(path)
        except Exception as e:  # noqa: BLE001  a refusal (not a folder) is said, never swallowed
            return self._say(f"Error: {getattr(e, 'line', lambda: e)()}")
        self._folders = userlib.list_folders()
        self._index([path])

    @Slot(str)
    def setText(self, t):
        self._text = t.strip()
        self._search()

    @Slot(str, str)
    def setFilter(self, which, value):
        """which: "kind", "length" or "brightness"; value "" = any."""
        setattr(self, {"kind": "_kind", "length": "_length", "brightness": "_bright"}[which], value)
        self._search()

    @Property(str, notify=changed)
    def auditioning(self):
        """What is being heard right now ("" when nothing is): the stop control shows only then."""
        return self._heard.busy

    @Slot(int)
    def audition(self, i):
        """Play result `i` on its own: its stretch of the file, through the engine."""
        r = self._results[i]
        self._heard.start({"media": r["path"], "in": r["start"], "length": r["end"] - r["start"]}, r["name"])

    @Slot(str)
    def auditionEntry(self, key):
        """Hear a Library entry (adder key): an instrument plays the selected track's notes, else a short phrase.
        Hearing only: nothing is written to the song and the selected track's sound never changes (that is the track's
        own Sound picker; Add makes a new track). Esc, ■ Stop, another pick and closing the Library end it."""
        e = next((x for x in ENTRIES if x["key"] == key), None)
        if e is None:
            return self._say(f'Error: audition: no sound "{key}".')
        b = self.bridge
        track = b._track if getattr(b, "_track", "") else None
        self._heard.start({k: v for k, v in e["fields"].items() if k != "name"}, e["label"], track)

    @Slot()
    def stopAudition(self):
        """The audition stops (Esc, ■ Stop, another track picked, closing the Library)."""
        self._heard.stop()
        self.changed.emit()

    @Property(bool, notify=changed)
    def loop(self):
        return self._heard.loop

    @Slot(bool)
    def setLoop(self, on):
        """Loop while browsing: the heard sound repeats until stopped or another is picked."""
        self._heard.loop = bool(on)
        self.changed.emit()

    def _heard_failed(self, line):
        self._say(line)

    @Slot(int)
    def place(self, i):
        """Put result `i` at the playhead on the selected track when it plays recordings (no instrument), else on the
        "sfx" track (made in the same call when missing): one operation call, one undo step."""
        r, b = self._results[i], self.bridge
        tracks = {t["id"]: t for t in b.doc.data.get("tracks", [])}
        sel = tracks.get(b._track)
        track = b._track if sel and sel.get("instrument", "none") == "none" else TRACK
        calls = []
        if track not in tracks:
            calls.append({"op": "track.add", "args": {"id": track, "name": "Sound effects"}})
        lead = r.get("peak_s", 0) if r["kind"] in PEAKED else r.get("onset_s", 0)   # its moment lands on the playhead
        at, _ = placed_at(b, float(lead or 0))
        calls.append({"op": "clip.add", "target": [track], "args": {
            "media": r["path"], "at": at, "in": r["start"], "length": round(r["end"] - r["start"], 4)}})
        b._guard(lambda: b._apply(calls, "Place sound"))

    @Slot(int)
    def swap(self, i):
        """Result `i` in place of the selected clip: its time, length, level (matched by loudness) and fades stay
        (`clip.swap`, one operation call, one undo step)."""
        r, clip = self._results[i], self.swapTarget
        if not clip:
            return self._say("Error: swap: select one clip first.")
        if self._trial.active:                  # a button on a row while stepping: that row, kept
            self.swapTo(i)
            return self.swapKeep()
        args = {"media": r["path"], **({"in": r["start"]} if r["start"] > 0.05 else {})}
        self.bridge._guard(lambda: self.bridge._apply([{"op": "clip.swap", "target": [clip], "args": args}], "Swap sound"))

    @Slot(int)
    def swapStep(self, delta):
        """↓ (+1) / ↑ (-1): the next / previous result in the selected clip's place, played in a loop round the spot."""
        n = len(self._results)
        clip = self.swapTarget
        if not (n and clip):
            return
        self._heard.stop()
        self.swapTo(max(0, min(n - 1, (self._trial.row if self._trial.active else -1) + delta)))

    def swapTo(self, i):
        clip = self.swapTarget
        if clip and self.bridge._guard(lambda: self._trial.step(clip, self._results[i], i)):
            self.changed.emit()

    @Slot()
    def swapKeep(self):
        self._trial.keep()
        self.changed.emit()

    @Slot()
    def swapBack(self):
        self._trial.back()
        self.changed.emit()

    def _picked(self):
        if self._trial.active and self.swapTarget != self._trial.clip:
            self._trial.back()                  # another pick: the original goes back, nothing recorded
            self.changed.emit()
        self._follow_target()                   # a pick elsewhere (a note) is not news here

    def close(self):
        self._trial.back()
        self._heard.close()

    # ---- inside -----------------------------------------------------------------------------------------------
    def _index(self, paths):
        self._busy = paths[0] if len(paths) == 1 else f"{len(paths)} folders"
        self.changed.emit()

        def run():
            err = ""
            try:
                for p in paths:
                    userlib.index.index_folder(p)
            except Exception as e:  # noqa: BLE001  reported on the panel and the console
                err = f"Error: indexing {p}: {e}"
            self._indexed.emit(self._busy, err)
        threading.Thread(target=run, name="index-sounds", daemon=True).start()

    def _done(self, _what, err):
        self._busy = ""
        if err:
            self._say(err)
        self._search()

    def _search(self):
        if self._busy or not self._folders:
            return self.changed.emit()
        try:
            r = userlib.search(kind=self._kind or None, words=self._text, length=self._length or None,
                               brightness=self._bright or None, limit=LIMIT)
        except Exception as e:  # noqa: BLE001
            return self._say(f"Error: search: {getattr(e, 'line', lambda: e)()}")
        self._results, self._total = [_row(s) for s in r["sounds"]], r["total"]
        self._status = (f"{r['total']} sounds" + (f", showing {LIMIT}" if r["more"] else "")) if r["total"] else \
            "No sounds match. Loosen the search."
        self.changed.emit()

    def _say(self, line):
        print(line) if not line.startswith("Error") else self.bridge._fail(line)
        self._status = line
        self.changed.emit()
