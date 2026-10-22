"""Hearing a Library entry (DESIGN.md §3.2b, §3.7): the entry is rendered by the sound engine (rostrum_sound.audition,
the same request as export) and the WAV is played by the engine's live player (live_transport.LivePlay), on its own
process so a song that is playing is left alone. Picking another entry, Esc or closing the panel stops the one that
plays. A failed render or player is said (`failed`), never a silent nothing.

    a = Auditioner(bridge); a.start(entry, "Grand piano", track="pad"); a.stop()
`busy` is "" when idle, else what is being rendered or played ("Grand piano"); `playing` is True once it is sounding.
`program` is the player's test seam (as LivePlay.program).
"""
from __future__ import annotations

import copy
import threading

from PySide6.QtCore import QObject, Signal

from .live_transport import LivePlay


class Auditioner(QObject):
    changed = Signal()
    failed = Signal(str)
    _made = Signal(int, str, str)             # (request, WAV, error) from the render thread

    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        self.bridge, self.busy, self.playing, self.program = bridge, "", False, None
        self._serial, self._engine, self._player = 0, None, None
        self._made.connect(self._ready)

    def start(self, entry: dict, label: str, track: str | None = None):
        """Render `entry` (rostrum_sound.audition) and play it; the newest request wins."""
        self._serial += 1
        self._stop_player()
        self.busy, self.playing = label, False
        self.changed.emit()
        doc = copy.deepcopy(self.bridge.doc.data)
        track = track if any(t["id"] == track for t in doc.get("tracks", [])) else None
        threading.Thread(target=self._render, args=(self._serial, entry, doc, track), daemon=True,
                         name="audition-render").start()

    def stop(self):
        self._serial += 1                      # a render still going is not played when it finishes
        self._stop_player()
        self._idle()

    def close(self):
        self.stop()
        if self._player:
            self._player.close()
        if self._engine:
            self._engine.close()

    # ---- inside -----------------------------------------------------------------------------------------------
    def _render(self, n, entry, doc, track):
        from rostrum_sound.audition import render_audition
        from .playback import open_engine
        try:
            self._engine = self._engine or open_engine()
            r = render_audition(self._engine, entry, doc, track)
            self._made.emit(n, r["file"], "")
        except Exception as e:  # noqa: BLE001  said on the screen, never swallowed
            self._made.emit(n, "", f"Error: audition: {getattr(e, 'line', lambda: e)()}")

    def _ready(self, n, file, err):
        if n != self._serial:
            return
        if err:
            self._idle()
            return self.failed.emit(err)
        if self._player is None:
            self._player = LivePlay(self)
            self._player.program = self.program
            self._player.ended.connect(lambda _t: self._idle())
            self._player.problem.connect(self._problem)
        self._player.load(file)
        self._player.play(0.0)
        self.playing = True
        self.changed.emit()

    def _problem(self, line):
        self._idle()
        self.failed.emit(line)

    def _stop_player(self):
        if self._player and self._player.playing:
            self._player.stop()

    def _idle(self):
        self.busy, self.playing = "", False
        self.changed.emit()
