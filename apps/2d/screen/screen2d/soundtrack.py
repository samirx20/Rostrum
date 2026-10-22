"""The project's sound in 2D (`backend.soundtrack`; UX_SPEC 3.28, AGENTS.md rule 9). No mixer, no audio engine here:
RostrumSound's engine renders the scene's `soundtrack` (a Sound item; empty = the project's main mix,
rostrum2d/project_sound.py) when the song,
the markers or the pick change (soundtrack_render.py; a cheap stat once a second), and its live player plays it with
2D's playback (soundtrack_play.py: play / stop / loop / scrub; the picture follows the speaker, `heard`). Mute is
2D only. No output, no engine, a broken song: said once, loudly (status line, Sound row); the picture plays on its
clock. `beat_times()` / `bar_times()`: the tempo grid in seconds (Show beats, snapping, Shift+, / .). The engine
and player start only when needed and end by their own handles in close().
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot

from rostrum2d import sound_cues

from .song_history import SongHistory
from .soundtrack_play import SoundtrackPlay
from .soundtrack_render import SoundtrackRender
from .video_sound import VideoSound

REPO = Path(__file__).resolve().parents[4]


class Soundtrack(QObject):
    changed = Signal()

    def __init__(self, bridge):
        super().__init__(bridge)
        self.b = bridge
        self._info, self._song, self._stamp, self._problem, self._said = {}, None, None, "", set()
        self._muted, self._beats_on = False, False
        self._play = SoundtrackPlay(self)
        self._play.problem.connect(self._say)
        self._render = SoundtrackRender(self)
        self._render.rendered.connect(self._on_rendered)
        self._render.failed.connect(self._on_failed)
        self._unfollow = sound_cues.watch(bridge.doc, self._say)    # cues follow their layers, videos' sound goes to Sound
        self.history = SongHistory(bridge, self)
        bridge.join_history(self.history)                           # Ctrl+Z takes back Add a sound here (song_history.py)
        self._videos = VideoSound(self, bridge)                     # the timeline's Video sound rows (video_sound.py)
        self._poll = QTimer(self, interval=1000, timeout=self.check)
        self._poll.start()
        self.check()

    # ---- what QML reads ---------------------------------------------------------------------------------------
    present = Property(bool, lambda self: self._song is not None, notify=changed)       # the Sound row exists
    name = Property(str, lambda self: self._song["name"] if self._song else "", notify=changed)
    item = Property(str, lambda self: self._song["id"] if self._song else "", notify=changed)
    seconds = Property(float, lambda self: self._info.get("seconds", 0.0), notify=changed)
    peaks = Property("QVariantList", lambda self: self._info.get("peaks", []), notify=changed)
    rate = Property(float, lambda self: self._info.get("rate", 100.0), notify=changed)
    problem = Property(str, lambda self: self._problem, notify=changed)
    muted = Property(bool, lambda self: self._muted, notify=changed)
    hasBeats = Property(bool, lambda self: bool(self.beat_times()), notify=changed)
    showBeats = Property(bool, lambda self: self._beats_on and bool(self.beat_times()), notify=changed)
    bpm = Property(float, lambda self: self._info.get("grid", {}).get("bpm", 0.0), notify=changed)
    lines = Property("QVariantList", lambda self: self._info.get("lines", []), notify=changed)   # voice-over: [{t, end, text}]
    videos = Property(QObject, lambda self: self._videos, constant=True)    # a video layer's own sound (video_sound.py)

    @Property("QVariantList", notify=changed)
    def beats(self):
        """Show beats' lines: [{t, bar}] (bar: its number on a bar start, else 0); empty while it is off."""
        if not self.showBeats:
            return []
        bars = {round(t, 6): i + 1 for i, t in enumerate(self.bar_times())}
        return [{"t": t, "bar": bars.get(round(t, 6), 0)} for t in self.beat_times()]

    def beat_times(self) -> list[float]:
        return list(self._info.get("grid", {}).get("beats", []))

    def bar_times(self) -> list[float]:
        return list(self._info.get("grid", {}).get("bars", []))

    def describe(self) -> dict:
        """What plays, for agents (inspect) and the steps: item, name, seconds, bpm, beats per bar, or the problem."""
        g = self._info.get("grid", {})
        return {"item": self.item, "name": self.name, "seconds": self.seconds, "bpm": g.get("bpm"),
                "beatsPerBar": g.get("beatsPerBar"), "muted": self._muted, "file": self._info.get("file", ""),
                "problem": self._problem} if self._song else {}

    # ---- what the screen calls --------------------------------------------------------------------------------
    @Slot()
    def check(self):
        """The song, the markers or the scene's choice changed: render again (newest wins)."""
        folder = self.b.doc.folder
        try:
            from rostrum_sound import soundtrack
            from rostrum2d import project_sound
            song = project_sound.song(folder, self.b.comp().get("soundtrack", ""))
            stamp = soundtrack.stamp(folder, song["id"]) if song else None
        except Exception as e:  # noqa: BLE001  a named song that isn't there, rostrum_sound missing: loud
            return self._on_failed(e.line() if hasattr(e, "line") else f"Error: soundtrack: {e}")
        if stamp == self._stamp:
            return
        self._song, self._stamp = song, stamp
        self.history.touch()
        self._videos.refresh()                                      # a mute set in Sound's window shows here too
        if song is None:
            self._info, self._problem = {}, ""
        else:
            self._render.request(str(folder), song, self.b.comp()["duration"])
        self.changed.emit()

    def busy(self) -> bool:
        return self._render.busy()

    @Slot(bool)
    def setMuted(self, on):
        self._muted = bool(on)
        if self._muted:
            self._play.stop()
        elif self.b.playing:
            self.play(self.b.time)
        self.changed.emit()

    @Slot(bool)
    def setShowBeats(self, on):
        self._beats_on = bool(on)
        self.changed.emit()

    @Slot(int, result=bool)
    def stepBeat(self, direction):
        """Shift+, (-1) / Shift+. (+1): the playhead to the previous / next beat."""
        half = 0.5 / self.b.comp()["fps"]
        t, beats = self.b.time, self.beat_times()
        to = next((b for b in reversed(beats) if b < t - half), None) if direction < 0 else \
            next((b for b in beats if b > t + half), None)
        if to is not None:
            self.b.setTime(to)
        return to is not None

    @Slot()
    def openInSound(self):
        """The Sound row's Open in RostrumSound: the Sound app on this project's song (tools/rostrum.ps1)."""
        if self._song:
            subprocess.Popen(self.open_command(), creationflags=getattr(subprocess, "DETACHED_PROCESS", 0))

    def open_command(self) -> list[str]:
        return ["pwsh", "-NoProfile", "-File", str(REPO / "tools" / "rostrum.ps1"), "sound", "-Doc",
                str(self.b.doc.folder), self._song["id"]]

    # ---- following playback (playback.py, the ruler; soundtrack_play.py) -------------------------------------
    def _ready(self) -> bool:
        return bool(self._info) and not self._muted

    def play(self, t: float):
        if self._ready():
            self._play.play(t)

    def stop(self):
        self._play.stop()

    def heard(self) -> float | None:
        return self._play.heard()

    @Slot(float)
    def scrub(self, t):
        """The playhead dragged (not playing): a short burst of the mix at t."""
        if not self.b.playing and self._ready():
            self._play.scrub(t)

    # ---- answers ----------------------------------------------------------------------------------------------
    def _on_rendered(self, info):
        if not self._song or info["item"] != self._song["id"]:
            return
        self._info, self._problem = dict(info), ""
        self._play.load(info["file"], warm=not self._muted)     # opened (stopped) now: Play sounds at once
        self.changed.emit()

    def _on_failed(self, line):
        self._problem = line
        self._say(line)
        self.changed.emit()

    def _say(self, line):
        """Said once per reason in the status line (fail loudly); the Sound row keeps showing it."""
        if line not in self._said:
            self._said.add(line)
            self.b._fail(line)
        if not self._play.alive():
            self._problem = line
            self.changed.emit()

    def close(self):
        self._unfollow()
        self._videos.close()
        self._poll.stop()
        self._play.close()
        self._render.close()
