"""A voice track's card: its lines as text + time, and Make voice. No Qt widgets; the worker is a thread like the
listen pictures (`listen_pics.py`), so the screen never waits on the voice model. Making a take edits nothing in the
document (the cache holds the audio), so there is no history entry; the song is re-rendered when it is done."""
from __future__ import annotations

import copy
import threading

from PySide6.QtCore import QObject, Signal
from rostrum_sound import voice_lines


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
    lines = [{"id": ln["id"], "text": ln["text"], "when": when_text(ln["at"]),
              "made": voice_lines.take_of(track, ln) is not None} for ln in track.get("lines", [])]
    return {"isVoice": True, "lines": lines, "missing": sum(not ln["made"] for ln in lines),
            "voiceStatus": state.get("status", ""), "voiceBusy": state.get("busy", False),
            "voiceFailed": state.get("failed", False)}


class VoiceMaker(QObject):
    changed = Signal()
    _done = Signal(str, str)      # track id, error ("" = made)

    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        self.bridge, self._state, self._threads = bridge, {}, []
        self._done.connect(self._finish)

    def state(self, track_id: str) -> dict:
        return self._state.get(track_id, {})

    def start(self, track_id: str):
        if self.state(track_id).get("busy"):
            return
        track = next(t for t in self.bridge.doc.data["tracks"] if t["id"] == track_id)
        ids = [ln["id"] for ln in track.get("lines", []) if voice_lines.take_of(track, ln) is None]
        if not ids:
            return
        self._state[track_id] = {"busy": True, "status": f"Making {len(ids)} line{'s' if len(ids) > 1 else ''}… "
                                 "(the first one loads the voice)"}
        self.changed.emit()
        snapshot = copy.deepcopy(self.bridge.doc.data)     # the thread reads this copy, never the live document
        t = threading.Thread(target=self._work, args=(track_id, snapshot, ids), daemon=True)
        self._threads.append(t)
        t.start()

    def _work(self, track_id, snapshot, ids):
        try:
            voice_lines.make_lines(snapshot, ids)
            error = ""
        except Exception as e:  # noqa: BLE001  shown red on the card, whatever it was
            error = e.line() if hasattr(e, "line") else f"{type(e).__name__}: {e}"
        self._done.emit(track_id, error)

    def _finish(self, track_id, error):
        self._state[track_id] = {"failed": bool(error), "status": error}
        self.changed.emit()
        if not error:
            self.bridge.transport.render()      # the song now has its voice: hear it

    def close(self):
        for t in self._threads:
            t.join(timeout=60)
