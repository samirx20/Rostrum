"""Keyboard takes on the screen, through the engine's live transport (the same process that plays the song): with a
notes or drum track armed (recording.py's arm) and a MIDI keyboard connected, the player opens that keyboard
(`--midi <n>`, the device chosen in the take panel, record_setup.py) with a monitor instrument for the track
(`--instrument`, rostrum_sound.midi.keyboard.monitor_spec: an SFZ track plays its own file, others a plain synth;
the render plays the real instrument). Record keys arms the engine's recording and plays from the take's start
(take_clock.py: count-in, punch); the engine reports each note at the mix time heard with it ({"note"}), so Stop
puts the take on the armed track as one `note.add_many` (drum tracks: `hit.add_many`), one undo step, a person's
edit, snapped to the grid when Quantize is on, and the piano roll shows that track. The device list is read again
on every arm; "No MIDI keyboard found" when there is none. `list_devices` is the test seam (with
LivePlay.program, fake_play.py stands in for the keyboard). Not tried with a real keyboard on this machine.
"""
from __future__ import annotations

import hashlib
import json
import threading

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot
from rostrum_core import RostrumError, codes
from rostrum_sound.midi import keyboard

from .playback import SCRATCH
from .take_clock import TakeClock

SETTLE_MS = 300                      # after stop: the notes still held come back right after the engine's stop


class KeysRecording(QObject):
    devicesChanged = Signal()
    recordingChanged = Signal()
    notesChanged = Signal()
    _found = Signal(int, "QVariantList")              # from the lookup thread, delivered on the screen's thread

    def __init__(self, bridge, recorder, parent=None):
        super().__init__(parent)
        self.bridge, self.recorder, self.setup = bridge, recorder, recorder.setup
        recorder.keys = self
        self.list_devices = keyboard.devices
        self.clock = TakeClock(bridge, self.setup, self)
        self._devices, self._take, self._look, self._taking = [], None, 0, False
        self._tick = QTimer(self, interval=100, timeout=lambda: self.notesChanged.emit())
        self._settle = QTimer(self, singleShot=True, interval=SETTLE_MS, timeout=lambda: self._guard(self._land))
        self._found.connect(self._got)
        recorder.player.note.connect(self._noted)
        recorder.armedChanged.connect(self.look_for_keyboards)

    @Property("QVariantList", notify=devicesChanged)
    def devices(self):
        """The connected keyboards' names ([] = none: Record keys is absent)."""
        return self._devices

    @Property(bool, notify=devicesChanged)
    def usable(self):
        """Record keys can be pressed: a keyboard is connected and the armed track takes notes or hits."""
        return bool(self._devices) and self.setup.kind in ("notes", "drums")

    @Property(bool, notify=recordingChanged)
    def recording(self):
        return self._taking

    @Property(int, notify=notesChanged)
    def notes(self):
        return len(self._take or [])

    @Property(int, notify=notesChanged)
    def counting(self):
        return self.clock.counting

    def player_opts(self) -> dict:
        """The keyboard and its monitor instrument for the player (recording.py's configure); {} when unusable."""
        if not (self.recorder.armed and self.usable):
            return {}
        spec = json.dumps(keyboard.monitor_spec(self.bridge.doc.item(self.recorder.armed)), sort_keys=True)
        f = SCRATCH / f"keys-{hashlib.sha1(spec.encode()).hexdigest()[:10]}.json"   # a new monitor: a new file
        if not f.is_file():
            f.write_text(spec, encoding="utf-8")
        return {"midi": self.setup.device(), "instrument": str(f)}

    def look_for_keyboards(self):
        if not self.recorder.armed:
            return
        self._look += 1
        n, ask = self._look, self.list_devices

        def look():
            try:
                found = ask()
            except (RostrumError, OSError, ValueError):
                found = []                       # no engine or no keyboards: "No MIDI keyboard found"
            self._found.emit(n, found)
        threading.Thread(target=look, daemon=True).start()

    def _got(self, n, found):
        if n == self._look:                      # an older lookup that ended late changes nothing
            self._devices = list(found)
            if self.setup.device() >= len(self._devices):
                self.setup.values["midiDevice"] = "0"
            self.setup.refresh(devices=self._devices)
            self.devicesChanged.emit()
            self.recorder.configure()            # the player opens the keyboard

    @Slot()
    def toggleRecord(self):
        if self._taking:
            self._stop()
        elif self.recorder.armed and self.usable and not self.recorder.recording and not self._settle.isActive():
            self._guard(self._begin)

    def _begin(self):
        if not self.recorder.player.alive:
            raise RostrumError(codes.INTERNAL, "keyboard take", "the MIDI keyboard",
                               f"is not open: {self.recorder.player.reason}", [], "Arm the track again.")
        self.recorder.configure(at=self.clock.start_time())
        self._take, self._taking = [], True
        self.clock.begin()
        self._tick.start()
        self.recordingChanged.emit()
        self.notesChanged.emit()

    def _noted(self, n):
        if self._take is not None and (self._taking or self._settle.isActive()):
            self._take.append(dict(n))

    def _stop(self):
        self._taking = False
        self._tick.stop()
        self.clock.stop()
        self._settle.start()
        self.recordingChanged.emit()

    def _land(self):
        notes, self._take = self._take or [], None
        self.notesChanged.emit()
        track = self.bridge.doc.item(self.recorder.armed)
        call = keyboard.take_call(track, notes, 0.0, self.bridge.doc.data, self.setup.grid())   # notes: mix seconds
        if call is not None:
            self.bridge._apply([call], "Record keyboard take")
            self.bridge.select(track["id"])                    # the piano roll shows what was played
        else:                                                  # a take with no notes is said, never a quiet nothing
            self.bridge._fail("Keyboard take: no notes were played, so nothing was recorded"
                              + ("" if self.recorder.player.alive else f" ({self.recorder.player.reason})") + ".")

    def _guard(self, fn):
        try:
            fn()
        except RostrumError as e:
            if self._taking:
                self._taking = False
                self._tick.stop()
                self.clock.stop()
                self.recordingChanged.emit()
            self.bridge._fail(e.line())

    def close(self):
        self._settle.stop()
        if self._taking:
            self._taking = False
            self.clock.stop()
