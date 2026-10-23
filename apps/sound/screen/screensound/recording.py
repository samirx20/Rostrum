"""Recording on the screen: which track is armed (screen state, not a document edit), the take, and its meter, all
through the engine's live transport (live_transport.py), the same process that plays the song.

Arming opens the microphone in that process (`--mic`, the playhead kept); the meter is its input level (`{"input"}`,
the one source for the level), and "Hear input" mixes the microphone into the output. Record arms the engine's
recording and plays from the take's start (take_clock.py: the engine's count-in, the punch range); the engine
writes each pass as a take placed at the mix time heard with it (its clock, minus the calibrated microphone delay),
and the take lands as one `clip.add` (one undo step) at that time. With punch on, the engine keeps only the range and
the take ends by itself past it. A microphone that cannot open is said loudly and the track is disarmed.
While it records, `take` is the take growing in its lane: where it starts, how long it is so far and the microphone's
level along it (the same input level the meter shows), kept on screen until the take lands as its clip.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot
from rostrum_core import RostrumError, codes
from rostrum_sound import record as rec
from rostrum_sound.doc import meter, tempo

from .playback import SCRATCH
from .record_setup import RecordSetup
from .take_clock import TakeClock

BEATS_UNTIL = 3600.0             # beat times handed to the engine reach an hour into the song
TAKES = SCRATCH / "takes"           # where the engine writes takes before they move to the project's media folder
SETTLE_MS = 500                     # after stop: the engine's last take line arrives well within this
FLOOR_DB = -60.0                    # the live take's level drawing: this level is flat, 0 dBFS fills the lane


class Recording(QObject):
    armedChanged = Signal()
    recordingChanged = Signal()
    levelChanged = Signal()

    def __init__(self, bridge, setup=None, parent=None):
        super().__init__(parent)
        self.bridge, self.player, self.keys = bridge, bridge.transport.player, None
        self.setup = setup or RecordSetup(bridge, self)
        self.setup.on_set = self._setting
        self.clock = TakeClock(bridge, self.setup, self)
        self._armed, self._taking, self._takes, self._level, self._rolled = "", False, [], None, False
        self._trace, self._held = [], 0.0          # the live take: [seconds into it, level 0..1]; its length at Stop
        self.player.take.connect(self._took)
        self.player.level.connect(self._heard_level)
        self.player.changed.connect(self._player_changed)
        self.player.ended.connect(self._song_ended)
        bridge.transport.renderChanged.connect(lambda: None if self._taking else self.configure())
        self._tick = QTimer(self, interval=50, timeout=lambda: self.levelChanged.emit())
        self._settle = QTimer(self, singleShot=True, interval=SETTLE_MS, timeout=lambda: self._guard(self._land))

    @Property(str, notify=armedChanged)
    def armed(self):
        """The armed track's id ("" when none)."""
        return self._armed

    @Property(bool, notify=recordingChanged)
    def recording(self):
        return self._taking

    @Property("QVariant", notify=levelChanged)
    def level(self):
        """The microphone's latest peak in dBFS while it is open; null otherwise."""
        return self._level if self.player.mic else None

    @Property(float, notify=levelChanged)
    def elapsed(self):
        return max(0.0, self.player.position() - self.clock.at) if self._taking and self.player.rolled else 0.0

    @Property("QVariantMap", notify=levelChanged)
    def take(self):
        """The take as it grows (from the moment the mix rolls until it lands as a clip): {track, t, dur, levels:
        [[seconds into the take, 0..1], …]}; {} when there is none."""
        dur = self.elapsed if self._taking else self._held if self._settle.isActive() else 0.0
        if dur <= 0:
            return {}
        return {"track": self._armed, "t": self.clock.at, "dur": dur, "levels": self._trace}

    @Property(int, notify=levelChanged)
    def counting(self):
        return self.clock.counting

    @Slot(str)
    def arm(self, track_id):
        """Arm a track (a second click disarms): the microphone opens (closes) in the player. Not while recording."""
        if not self._taking:
            self._armed = "" if self._armed == track_id else track_id
            if not self._armed:
                self.setup.values["hear"] = False
                self.player.state.pop("hear", None)   # a player without a microphone is not told about hearing it
            self.configure()
            self.armedChanged.emit()

    def configure(self, at=None):
        """The player's set-up: the song's beats the metronome and count-in click on, armed or not (each render
        brings them up to date), and for what is armed the microphone and the keyboard (keys_record.py). The beats:
        its tempo, or, when the tempo changes or a main beat is not a quarter (6/8 clicks on 1 and 4), every main
        beat's time from the bar map (meter.click_seconds, through the one beat-to-seconds place), so a count-in
        anywhere clicks at that tempo; the accents: every bar's start from the bar map when the time signature
        changes (meter.py); the count-in counts a real bar where the take starts: its main beats."""
        root = self.bridge.doc.data
        at = self.clock.start_time() if at is None and self._taking else at
        here = meter.seg_at(root, tempo.beat_at(root, at or 0.0))
        opts = {"bpm": round(tempo.start_bpm(root), 4), "beats": meter.main_beats(here)[0]}
        SCRATCH.mkdir(parents=True, exist_ok=True)
        if len(tempo.segments(root)) > 1 or not meter.plain(root):
            beats = SCRATCH / "beat-times.json"
            beats.write_text(json.dumps(meter.click_seconds(root, BEATS_UNTIL)), encoding="utf-8")
            opts.update(beat_times=str(beats), tempo=json.dumps([tempo.contract(root), meter.segments(root)]))   # a new map reopens the player
        if root.get("meters"):
            bars = SCRATCH / "bar-times.json"
            bars.write_text(json.dumps(meter.bar_seconds(root, BEATS_UNTIL)), encoding="utf-8")
            opts.update(bar_times=str(bars), meters=json.dumps(meter.segments(root)))
        if self._armed:
            TAKES.mkdir(parents=True, exist_ok=True)
            opts["mic"] = str(TAKES)
            if self.keys is not None:
                opts.update(self.keys.player_opts())
        self.player.configure(**opts)
        self._show()

    @Slot()
    def toggleRecord(self):
        """Record / Stop (the button is always there; R). With no track armed it arms the selected track, else the
        first that can take sound, or says why not."""
        if self._taking:
            self.stop()
            return
        if not self._armed:
            track = self._default_track()
            if not track:
                return self.bridge.say("Nothing to record on: add a Microphone track (+ Add, Track with a sound)")
            self.arm(track)
        if self._armed and not self._settle.isActive():
            self._guard(self._begin)

    def _default_track(self):
        """The track a bare Record arms: the selected one (or the one holding the selected item) that takes sound,
        else the first audio track."""
        doc = self.bridge.doc
        rows = {r["id"]: r for r in self.bridge.tracks if not r.get("mix")}
        for i in self.bridge._picks.ids:
            t = i if i in rows else (doc.parent_of(i) or [None])[0] if doc.has(i) else None
            if t in rows and rows[t]["kind"] in ("audio", "empty"):
                return t
        return next((i for i, r in rows.items() if r["kind"] in ("audio", "empty")), "")

    def _begin(self):
        if not self.player.alive:
            raise RostrumError(codes.INTERNAL, "record", "the microphone", f"is not open: {self.player.reason}", [],
                               "Check the sound output and the microphone, then arm the track again.")
        self.configure(at=self.clock.start_time())
        self._taking, self._takes, self._trace = True, [], []
        self.clock.begin()
        self._tick.start()
        self._show()
        self.recordingChanged.emit()

    @Slot()
    def stop(self):
        if self._taking:
            self._held = self.elapsed            # the live take stays drawn, this long, until it lands
            self._taking = False
            self._rolled = self.player.rolled
            self.clock.stop()
            self._tick.stop()
            self._settle.start()                 # the engine's take line comes right after the stop
            self._show()
            self.recordingChanged.emit()
            self.levelChanged.emit()

    def _took(self, take):
        if self._taking or self._settle.isActive():
            if self.keys is not None and self.keys.recording:
                Path(take["file"]).unlink(missing_ok=True)   # the microphone ran along with a keyboard take
                return
            self._takes.append(dict(take))
            if self._taking and self.setup.punch():
                self.stop()                                  # the engine finished the punch range
        else:
            Path(take.get("file", "")).unlink(missing_ok=True)

    def _land(self):
        try:
            self._land_takes()
        finally:                                 # the live take gives way to its clip (or to the message why not)
            self._held = 0.0
            self.levelChanged.emit()

    def _land_takes(self):
        takes, self._takes = self._takes, []
        if not takes:
            if self._rolled:
                raise RostrumError(codes.INTERNAL, "record", "the take", "came back empty from the player",
                                   [], "Nothing was recorded. Check the microphone in Settings; its meter should move while you speak.")
            self.bridge._fail("Take stopped before playback rolled: nothing was recorded")
            return
        self.bridge._apply([rec.land_take(self.bridge.doc, self._armed, t) for t in takes], "Record take")

    def _song_ended(self, _t):
        if self._taking:
            self.stop()

    def _heard_level(self, db):
        self._level = db
        if self._taking and self.player.rolled:
            self._trace.append([round(self.elapsed, 3), round(max(0.0, min(1.0, 1 - db / FLOOR_DB)), 3)])
        self.levelChanged.emit()

    def _setting(self, key):
        if key in ("hear", "hearGain"):
            self._send_hear()
        elif key == "midiDevice":
            self.configure()

    def _send_hear(self):
        on = bool(self.setup.values["hear"]) and bool(self.player.mic)
        self.player.set_state(hear={"gain": self.setup.values["hearGain"]} if on else False)

    def _player_changed(self):
        if self._armed and not self.player.alive and self.player.opts.get("mic"):
            line = f"Error: record: the microphone could not be opened, so {self._armed} is disarmed ({self.player.reason})"
            if self._taking:
                self.stop()
            self._armed = ""
            self.configure()                     # the player again, without the microphone
            self.armedChanged.emit()
            self.bridge._fail(line)
        if self.player.mic and self.setup.values["hear"]:
            self._send_hear()
        self._show()

    def _show(self):
        self.setup.refresh(armed=self._armed, recording=self._taking, mic=self.player.mic if self._armed else None)
        self.levelChanged.emit()

    def _guard(self, fn) -> bool:
        try:
            fn()
            return True
        except RostrumError as e:
            if self._taking:
                self._taking = False
                self.clock.stop()
                self._tick.stop()
                self.recordingChanged.emit()
            self.bridge._fail(e.line())
            return False

    def close(self):
        if self._taking:
            self._taking = False
            self.clock.stop()
        self._settle.stop()
