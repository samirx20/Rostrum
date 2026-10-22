"""The soundtrack following 2D's playback (soundtrack.py owns one): RostrumSound's live player (rostrum_sound.
live_play.LivePlay, the one player both screens use) on the rendered mix. Play / stop / loop come from playback.py,
a scrub burst from the ruler; `heard()` is where the speaker is, so the picture follows the sound.

The player is made on the first need (the first mix: `warm` opens it stopped, so the first Play has no start-up
wait) and ended by its own handle in close(). Its problems (no sound output, the player stopped) go out as `problem`.
"""
from __future__ import annotations

import time

from PySide6.QtCore import QObject, QTimer, Signal

BURST_MS = 90                # a scrub plays this much of the mix at the pointer
WAIT_S = 1.5                 # the picture waits this long at most for the speaker to start


class SoundtrackPlay(QObject):
    problem = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._player, self._file, self._asked = None, "", 0.0
        self._burst = QTimer(self, singleShot=True, interval=BURST_MS, timeout=self._end_burst)

    def load(self, file: str, warm: bool):
        """The newest mix: sent to the player; with `warm`, the player is opened now (stopped) if it isn't yet."""
        self._file = file
        if self._player:
            self._player.load(file)
        elif warm:
            self._live().warm()

    def alive(self) -> bool:
        """The player is open and can sound (False: it said why through `problem`)."""
        return bool(self._player and self._player.alive)

    def play(self, t: float):
        self._burst.stop()
        self._asked = time.monotonic()
        self._live().play(t)

    def stop(self):
        self._burst.stop()
        if self._player:
            self._player.stop()

    def scrub(self, t: float):
        """A short burst of the mix at t (the playhead dragged while not playing)."""
        self._live().play(t)
        self._burst.start()

    def heard(self) -> float | None:
        """Where the speaker is while the mix plays (the picture waits while the output starts, up to WAIT_S),
        else None (the picture runs on its own clock)."""
        p = self._player
        if not (p and p.playing and p.alive) or (not p.rolled and time.monotonic() - self._asked > WAIT_S):
            return None
        return p.position()

    def _end_burst(self):
        if self._player:
            self._player.stop()

    def _live(self):
        if self._player is None:
            from rostrum_sound.live_play import LivePlay
            self._player = LivePlay(self)
            self._player.problem.connect(self.problem)
            self._player.load(self._file)
        return self._player

    def close(self):
        self._burst.stop()
        if self._player:
            self._player.close()
