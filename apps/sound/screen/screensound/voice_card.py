"""A voice track's card: its lines as text + time, and Make voice. No Qt widgets; the worker is a thread like the
listen pictures (`listen_pics.py`), so the screen never waits on the voice model. Making a take edits nothing in the
document (the cache holds the audio), so there is no history entry; the song is re-rendered when it is done."""
from __future__ import annotations

import copy
import os
import threading
from types import SimpleNamespace

from PySide6.QtCore import QObject, Signal
from rostrum_sound import voice, voice_lines
from rostrum_sound.cleanup import fetch

from . import voice_takes
from .model_fetch import ModelFetch


def when_text(at) -> str:
    """A line's time as it was written: "12.5 s", "beat 8", "#drop+0.5"."""
    if isinstance(at, dict):
        return f"beat {at.get('beat', 0):g}"
    return f"{at:g} s" if isinstance(at, (int, float)) else str(at)


def card_roles(track: dict, state: dict) -> dict:
    """The card's voice roles; a track that is not a voice shows none of it."""
    if track.get("instrument") != "voice":
        return {"isVoice": False, "lines": [], "missing": 0, "voiceStatus": "", "voiceBusy": False,
                "voiceFailed": False}
    making = set(state.get("ids", ())) if state.get("busy") else set()
    lines = [{"id": ln["id"], "text": ln["text"], "when": when_text(ln["at"]), "making": ln["id"] in making,
              "made": voice_lines.take_of(track, ln) is not None, "take": voice_takes.label(track, ln),
              "canBack": voice_takes.neighbour(track, ln, -1) is not None,
              "canNext": voice_takes.neighbour(track, ln, 1) is not None} for ln in track.get("lines", [])]
    return {"isVoice": True, "lines": lines, "missing": sum(not ln["made"] for ln in lines),
            "voiceStatus": state.get("status", ""), "voiceBusy": state.get("busy", False),
            "voiceFailed": state.get("failed", False), "voiceMissing": model_missing()}


def models_to_fetch() -> list:
    """The voice model's files not on this computer yet (the download registry's: voice_models.py). A model folder set
    by hand (ROSTRUM_QWENTTS_DIR) is the person's own: only its presence counts, nothing is downloaded into it."""
    if os.environ.get("ROSTRUM_QWENTTS_DIR"):
        d = voice.model_dir()
        return [] if all((d / n).is_file() for n in (voice.EXE, voice.CODEC, voice.TALKER)) else list(fetch.NEEDS["voice"])
    return fetch.needed("voice")


def model_missing() -> str:
    """One sentence when the voice model is not on this computer ("" when it is); the screen asks to download it."""
    if not models_to_fetch():
        return ""
    if os.environ.get("ROSTRUM_QWENTTS_DIR"):
        return f"The voice model isn't in {voice.model_dir()}, so lines can't be spoken."
    return "The voice model isn't on this computer yet, so lines can't be spoken until it is downloaded."


def without(doc, ids):
    """The document as the screen's render reads it while these lines are being spoken: without them (they are on
    their way, and the song re-renders when they land). A line not made and not being made still fails the render
    loudly, and export never takes this path."""
    if not ids:
        return doc
    data = copy.deepcopy(doc.data)
    for t in data.get("tracks", []):
        if t.get("lines"):
            t["lines"] = [ln for ln in t["lines"] if ln["id"] not in ids]
    return SimpleNamespace(data=data, folder=getattr(doc, "folder", None))


def mark_speaking(rows: list[dict], ids) -> None:
    """A line being spoken reads "Speaking… · <words>" on its block (the arrangement's rows and the Editor's roll),
    not "not made"."""
    if not ids:
        return
    for r in rows:
        for b in r.get("blocks", []):
            if b["type"] == "line" and b["id"] in ids:
                b["label"] = "Speaking… · " + b["label"].removeprefix("not made · ")
                b["making"] = True


def mark_waiting(rows: list[dict], ids) -> None:
    """A line waiting for the voice model to be downloaded says so on its block."""
    for r in rows:
        for b in r.get("blocks", []):
            if b["type"] == "line" and b["id"] in ids:
                b["label"] = "Waiting for the voice model · " + b["label"].removeprefix("not made · ")


class VoiceMaker(QObject):
    changed = Signal()
    _done = Signal(str, str)      # track id, error ("" = made)

    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        self.bridge, self._state, self._threads = bridge, {}, []
        self.download = ModelFetch(self)                    # the same question the clean-up models get
        self._waiting = ""                                  # the track whose lines wait for the download
        self.download.ready.connect(self._downloaded)
        self.download.changed.connect(self._download_moved)
        self._done.connect(self._finish)

    def making(self) -> set:
        """The ids of every line being spoken now."""
        return {i for st in self._state.values() if st.get("busy") for i in st.get("ids", ())}

    def waiting(self) -> set:
        """The ids of the lines held back until the voice model is downloaded (they play once it is)."""
        if not self._waiting or not self.bridge.doc.has(self._waiting):
            return set()
        track = self.bridge.doc.item(self._waiting)
        return {ln["id"] for ln in track.get("lines", []) if voice_lines.take_of(track, ln) is None}

    def state(self, track_id: str) -> dict:
        return self._state.get(track_id, {})

    def start(self, track_id: str):
        if self.state(track_id).get("busy"):                     # a line typed meanwhile waits its turn (and says so)
            track = next(t for t in self.bridge.doc.data["tracks"] if t["id"] == track_id)
            st = self._state[track_id]
            st["ids"] = list(dict.fromkeys([*st["ids"], *(ln["id"] for ln in track.get("lines", [])
                                                           if voice_lines.take_of(track, ln) is None)]))
            st["again"] = True
            self.changed.emit()
            return
        need = models_to_fetch()
        if need and not os.environ.get("ROSTRUM_QWENTTS_DIR"):     # ask first (size, licence); "Download" carries on
            self._waiting = track_id
            self._state[track_id] = {"status": "Waiting for the voice model."}
            self.download.ask(need)
            return
        gone = model_missing()
        if gone:                                  # said in one plain sentence, never a silent failure
            self._state[track_id] = {"failed": True, "status": gone}
            self.changed.emit()
            return
        track = next(t for t in self.bridge.doc.data["tracks"] if t["id"] == track_id)
        ids = [ln["id"] for ln in track.get("lines", []) if voice_lines.take_of(track, ln) is None]
        if not ids:
            return
        self._state[track_id] = {"busy": True, "ids": ids, "status": f"Making {len(ids)} line{'s' if len(ids) > 1 else ''}… "
                                 "(the first one loads the voice)"}
        self.changed.emit()
        snapshot = copy.deepcopy(self.bridge.doc.data)     # the thread reads this copy, never the live document
        t = threading.Thread(target=self._work, args=(track_id, snapshot, ids), daemon=True)
        self._threads.append(t)
        t.start()

    def _downloaded(self):
        track, self._waiting = self._waiting, ""
        self._state.pop(track, None)
        if track:
            self.start(track)                       # the lines typed while it was missing are spoken now

    def _download_moved(self):
        if self.download.state == "idle" and self._waiting:      # "Not now", Close or a cancelled download
            track, self._waiting = self._waiting, ""
            self._state[track] = {"failed": True, "status": model_missing()}   # the lines stay silent, and the card says why
        self.changed.emit()

    def _work(self, track_id, snapshot, ids):
        try:
            voice_lines.make_lines(snapshot, ids)
            error = ""
        except Exception as e:  # noqa: BLE001  shown red on the card, whatever it was
            error = e.line() if hasattr(e, "line") else f"{type(e).__name__}: {e}"
        self._done.emit(track_id, error)

    def _finish(self, track_id, error):
        again = self._state.get(track_id, {}).get("again") and not error
        self._state[track_id] = {"failed": bool(error), "status": error}
        if again:                                 # lines typed while this one was spoken: the next round
            self.start(track_id)
            if self.state(track_id).get("busy"):
                return
        self.changed.emit()
        if not error:
            self.bridge.transport.render()      # the song now has its voice: hear it

    def close(self):
        self.download.close()
        for t in self._threads:
            t.join(timeout=60)
