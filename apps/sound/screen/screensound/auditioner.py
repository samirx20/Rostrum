"""Hearing a Library entry (DESIGN.md §3.2b, §3.7): the entry is rendered by the sound engine (rostrum_sound.audition,
the same request as export) and the WAV is played by the engine's live player (live_transport.LivePlay), on its own
process so a song that is playing is left alone. Picking another entry, Esc or closing the panel stops the one that
plays. A failed render or player is said (`failed`, a sentence in words: plain_errors.say_preview; the full line goes to
the console), never a silent nothing.

    a = Auditioner(bridge); a.start(entry, "Grand piano", track="pad"); a.stop()
    a.start({"key": 60}, "C4", track="melody")      # one key of the track's own instrument (the Editor's keyboard)
    a.start({"drum": "snare"}, "Snare", track="kit")  # one hit of a drum row's drum (click a drum's name)
    a.start(entry, "Grand piano", phrase=True)       # a Library sound: a short phrase in the song's key and tempo
    a.toggle(entry, "Grand piano", phrase=True)      # the same click again stops it (the Library's rows)
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

from rostrum_sound.doc import keys

from .live_transport import LivePlay
from .plain_errors import say_preview


INSTRUMENTS = ("builtIn", "synth", "model", "sfz", "plugin")
PHRASE_DEGREES = (0, 2, 4, 7, 4, 2)         # the key's 1 3 5 8 5 3, then its triad held: a few seconds at any tempo
TRACK = "audition_phrase"


def phrase_track(doc: dict, at: float = 0.0) -> dict:
    """A track of notes in the key playing at `at` seconds (C major without one), a step per beat at the song's tempo
    (half a beat when it is slow, so the phrase stays a few seconds). `render_audition` plays a track's own notes
    through the sound it is given, so a Library sound is heard as the song would use it."""
    key = keys.key_for(doc, at) or "C major"
    tonic, mode = keys.parse(key)
    scale = keys.MODES[mode]
    base = 48 + tonic if tonic < 6 else 36 + tonic
    step = 1.0 if doc.get("tempo", 120) >= 100 else 0.5

    def midi(d):
        return base + scale[d % 7] + 12 * (d // 7)
    notes = [{"id": f"p{i}", "type": "note", "pitch": keys.pitch_name(midi(d), key), "at": {"beat": round(i * step, 4)},
              "dur": {"beats": round(step * 0.9, 4)}, "vel": 0.7} for i, d in enumerate(PHRASE_DEGREES)]
    notes.append({"id": "pc", "type": "note", "pitch": [keys.pitch_name(midi(d), key) for d in (0, 2, 4)],
                  "at": {"beat": round(len(PHRASE_DEGREES) * step, 4)}, "dur": {"beats": round(2 * step, 4)}, "vel": 0.6})
    return {"id": TRACK, "type": "track", "notes": notes}


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

    def start(self, entry: dict, label: str, track: str | None = None, phrase: bool = False):
        """Render `entry` (rostrum_sound.audition) and play it; the newest request wins. `phrase`: an instrument plays
        a short phrase in the song's key and tempo (at the playhead) instead of the selected track's own notes."""
        self._serial += 1
        self._stop_player()
        self.busy, self.playing = label, False
        self.changed.emit()
        doc = copy.deepcopy(self.bridge.doc.data)
        track = track if any(t["id"] == track for t in doc.get("tracks", [])) else None
        if phrase and entry.get("instrument") in INSTRUMENTS:
            doc["tracks"] = [*doc.get("tracks", []), phrase_track(doc, float(getattr(self.bridge, "_t", 0.0) or 0.0))]
            track = TRACK
        threading.Thread(target=self._render, args=(self._serial, entry, doc, track, label), daemon=True,
                         name="audition-render").start()

    def toggle(self, entry: dict, label: str, track: str | None = None, phrase: bool = False):
        """The same click again stops what plays (or is being made ready); another entry replaces it."""
        if self.busy and self.busy == label:
            return self.stop()
        self.start(entry, label, track, phrase)

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
