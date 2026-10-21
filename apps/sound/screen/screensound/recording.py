"""Recording on the screen: which track is armed (screen state, not a document edit), the take, and its meter, all
through the engine's live transport (live_transport.py), the same process that plays the song.

Arming opens the microphone in that process (`--mic`, the playhead kept); the meter is its input level (`{"input"}`,
the one source for the level), and "Hear input" mixes the microphone into the output. Record arms the engine's
recording and plays from the take's start (take_clock.py: the engine's count-in, the punch range); the engine
writes each pass as a take placed at the mix time heard with it (its clock, minus the calibrated microphone delay),
and the take lands as one `clip.add` (one undo step) at that time. With punch on, the engine keeps only the range and
the take ends by itself past it. A microphone that cannot open is said loudly and the track is disarmed.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot
from rostrum_core import RostrumError, codes
from rostrum_sound import record as rec
from rostrum_sound.doc import tempo

from .playback import SCRATCH
from .record_setup import RecordSetup
from .take_clock import TakeClock

BEATS_UNTIL = 3600.0             # beat times handed to the engine reach an hour into the song
TAKES = SCRATCH / "takes"           # where the engine writes takes before they move to the project's media folder
SETTLE_MS = 500                     # after stop: the engine's last take line arrives well within this


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
        self.player.take.connect(self._took)
        self.player.level.connect(self._heard_level)
        self.player.changed.connect(self._player_changed)
        self.player.ended.connect(self._song_ended)
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
        """The player's set-up for what is armed: the microphone, the keyboard (keys_record.py), and the song's
        beats the metronome and count-in click on: its tempo, or, when the tempo changes, every beat's time from
        the tempo map (tempo.beats, the one beat-to-seconds place), so a count-in anywhere clicks at that tempo."""
        opts = {}
        if self._armed:
            TAKES.mkdir(parents=True, exist_ok=True)
            root = self.bridge.doc.data
            opts = {"mic": str(TAKES), "bpm": round(tempo.start_bpm(root), 4), "beats": int(root.get("beatsPerBar", 4))}
            if len(tempo.segments(root)) > 1:
                beats = TAKES.parent / "beat-times.json"
                beats.write_text(json.dumps(tempo.beats(root, BEATS_UNTIL)), encoding="utf-8")
                opts.update(beat_times=str(beats), tempo=json.dumps(tempo.contract(root)))   # a new tempo reopens the player
            if self.keys is not None:
                opts.update(self.keys.player_opts())
        self.player.configure(**opts)
        self._show()

    @Slot()
    def toggleRecord(self):
        if self._taking:
            self.stop()
        elif self._armed and not self._settle.isActive():
            self._guard(self._begin)

    def _begin(self):
        if not self.player.alive:
            raise RostrumError(codes.INTERNAL, "record", "the microphone", f"is not open: {self.player.reason}", [],
                               "Check the sound output and the microphone, then arm the track again.")
        self.configure(at=self.clock.start_time())
        self._taking, self._takes = True, []
        self.clock.begin()
        self._tick.start()
        self._show()
        self.recordingChanged.emit()

    @Slot()
    def stop(self):
        if self._taking:
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
        takes, self._takes = self._takes, []
        if not takes:
            if self._rolled:
                raise RostrumError(codes.INTERNAL, "record", "the take", "the engine sent no take for this pass",
                                   [], "Is the microphone working? The input meter should move while you speak.")
            self.bridge._fail("Take stopped before playback rolled: nothing was recorded")
            return
        self.bridge._apply([rec.land_take(self.bridge.doc, self._armed, t) for t in takes], "Record take")

    def _song_ended(self, _t):
        if self._taking:
            self.stop()

    def _heard_level(self, db):
        self._level = db
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
