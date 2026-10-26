"""Hearing a Library entry (DESIGN.md §3.2b, §3.7): the entry is rendered by the sound engine (rostrum_sound.audition,
the same request as export) and the WAV is played by the engine's live player (live_transport.LivePlay), on its own
process so a song that is playing is left alone. Picking another entry, Esc or closing the panel stops the one that
plays. A failed render or player is said (`failed`, a sentence in words: plain_errors.say_preview; the full line goes to
the console), never a silent nothing.

    a = Auditioner(bridge); a.start(entry, "Grand piano", track="pad"); a.stop()
    a.start({"key": 60}, "C4", track="melody")      # one key of the track's own instrument (the Editor's keyboard)
    a.start({"drum": "snare"}, "Snare", track="kit")  # one hit of a drum row's drum (click a drum's name)
`busy` is "" when idle, else what is being rendered or played ("Grand piano"); `playing` is True once it is sounding.
`program` is the player's test seam (as LivePlay.program).
`loop` True: a sound that runs out starts again (through the same engine player, never Qt Multimedia) until it is
stopped or another is picked.
"""
from __future__ import annotations

import copy
import sys
import threading

from PySide6.QtCore import QObject, Signal

from .live_transport import LivePlay
from .plain_errors import say_preview


class Auditioner(QObject):
    changed = Signal()
    failed = Signal(str)
    _made = Signal(int, str, str)             # (request, WAV, error) from the render thread

    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        self.bridge, self.busy, self.playing, self.program = bridge, "", False, None
        self.loop = False                      # Loop (the Library's toggle): the sound repeats while you browse
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
        threading.Thread(target=self._render, args=(self._serial, entry, doc, track, label), daemon=True,
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
    def _render(self, n, entry, doc, track, label):
        from rostrum_sound.audition import render_audition, render_hit, render_key
        from .playback import open_engine
        try:
            self._engine = self._engine or open_engine()
            r = (render_key(self._engine, doc, track, entry["key"]) if "key" in entry
                 else render_hit(self._engine, doc, track, entry["drum"]) if "drum" in entry and "instrument" not in entry
                 else render_audition(self._engine, entry, doc, track))
            self._made.emit(n, r["file"], "")
        except Exception as e:  # noqa: BLE001  said on the screen, never swallowed
            line = f"Error: audition: {getattr(e, 'line', lambda: e)()}"
            print(line, file=sys.stderr)
            self._made.emit(n, "", say_preview(label, line))

    def _ready(self, n, file, err):
        if n != self._serial:
            return
        if err:
            self._idle()
            return self.failed.emit(err)
        if self._player is None:
            self._player = LivePlay(self)
            if self.program:                   # a stand-in player (steps); else the one every LivePlay uses
                self._player.program = self.program
            self._player.ended.connect(lambda _t: self._ended())
            self._player.problem.connect(self._problem)
        self._player.load(file)
        self._player.play(0.0)
        self.playing = True
        self.changed.emit()

    def _ended(self):
        """The sound ran out: with Loop on it starts again from its beginning (until stopped or another is picked)."""
        if self.loop and self.playing and self._player is not None:
            self._player.play(0.0)
        else:
            self._idle()

    def _problem(self, line):
        self._idle()
        self.failed.emit(line)

    def _stop_player(self):
        if self._player and self._player.playing:
            self._player.stop()

    def _idle(self):
        self.busy, self.playing = "", False
        self.changed.emit()
