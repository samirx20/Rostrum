"""The keys a track's recorded sound can play, for the Editor's roll (hand composer r2 #5: timpani A1 drawn under its
lowest sample C2 without a word, then every render failed). The range is the engine's own (note_ranges: `range`, asked
once per sound and kept); this asks it on its own thread with its own engine, so a track's first show never waits for
the engine, and the roll shades its rows (`rollPlayable`) when the answer comes. Synths and models play any key: no
range, nothing shaded, nothing refused.

The refusals read only what was kept (never the engine): a Draw click on a shaded row, a drag or a transpose that
would take notes out of their track's range says so in the top bar ("Timpani plays C2–C4: A1 is below it") and changes
nothing (a drag stops at the last key that fits).
"""
from __future__ import annotations

import json
import threading

from PySide6.QtCore import QObject, Signal
from rostrum_sound import note_ranges

from . import playback, timing


class Asker(QObject):
    """Asks the engine for sounds' ranges, one at a time on a worker thread; `answered` on the window's thread."""
    answered = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._lock, self._queue, self._asked, self._running = threading.Lock(), [], set(), False

    def want(self, inst: dict):
        key = json.dumps(inst, sort_keys=True)
        with self._lock:
            if key in self._asked:                 # asked already (a failed ask is not asked again this run)
                return
            self._asked.add(key)
            self._queue.append(inst)
            if self._running:
                return
            self._running = True
        threading.Thread(target=self._run, name="sound-ranges", daemon=True).start()

    def _run(self):
        eng = None
        try:
            while True:
                with self._lock:
                    if not self._queue:
                        self._running = False
                        return
                    inst = self._queue.pop(0)
                try:
                    eng = eng or playback.open_engine()
                    note_ranges.ask(eng, inst)
                except Exception:                  # no answer: the roll shades nothing (the render still says it)
                    continue
                self.answered.emit()
        finally:
            if eng is not None:
                try:
                    eng.close()
                except Exception:
                    pass


def playable(root: dict, track_id: str) -> tuple[int, int] | None:
    """(lowest, highest) MIDI the track's sound plays, from what was kept; None: any key, or not known yet."""
    inst = note_ranges.sound_of(root, track_id)
    return note_ranges.kept(inst)[1] if inst is not None else None


def outside(root: dict, work: dict, ranges: dict) -> tuple[str, int, int, list[int]] | None:
    """The first track in `ranges` ({track: (lo, hi)}) whose notes in `work` (the song after an edit) went outside its
    range, with the keys: (track, lo, hi, keys); None when every new or re-pitched note fits. A note whose pitch did not
    change (moved in time only) is not judged."""
    tracks_before = {t["id"]: t for t in root.get("tracks", [])}
    for t in work.get("tracks", []):
        if t["id"] not in ranges or t is tracks_before.get(t["id"]):
            continue
        lo, hi = ranges[t["id"]]
        was = {n["id"]: n.get("pitch") for n in tracks_before.get(t["id"], {}).get("notes", [])}
        bad = [m for n in t.get("notes", []) if n["id"] not in was or was[n["id"]] != n.get("pitch")
               for m in _keys(n.get("pitch")) if not lo <= m <= hi]
        if bad:
            return t["id"], lo, hi, bad
    return None


def _keys(pitch) -> list[int]:
    try:
        return list(timing.keys(pitch))
    except Exception:
        return []


def name_of(root: dict, track_id: str) -> str:
    t = next((t for t in root.get("tracks", []) if t["id"] == track_id), None)
    return (t.get("name") or track_id) if t else track_id
