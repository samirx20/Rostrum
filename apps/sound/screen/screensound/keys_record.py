"""Keyboard takes on the screen: with a notes or drum track armed (recording.py's arm) and a MIDI keyboard connected,
Record keys starts the keyboard (the engine's `live`, rostrum_sound.midi.keyboard; the device chosen in the take
panel, record_setup.py), counts in when asked and plays the mix from the take's start (take_clock.py); Stop puts the
take on the armed track as one `note.add_many` (drum tracks: `hit.add_many`), one undo step, a person's edit, and
the piano roll shows that track. Notes land at the times they were played relative to playback (the keyboard's
stream started before playback was heard; that lead is taken off), snapped to the grid when Quantize is on.
The device list is read again on every arm; "No MIDI keyboard found" when there is none. `list_devices` and
`command` are the test seams (fake_midi.py stands in for a keyboard). Not tried with a real keyboard on this machine.
"""
from __future__ import annotations

import threading

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot
from rostrum_core import RostrumError
from rostrum_sound.midi import keyboard

from .take_clock import TakeClock


class KeysRecording(QObject):
    devicesChanged = Signal()
    recordingChanged = Signal()
    notesChanged = Signal()
    _found = Signal(int, "QVariantList")              # from the lookup thread, delivered on the screen's thread

    def __init__(self, bridge, recorder, parent=None):
        super().__init__(parent)
        self.bridge, self.recorder, self.setup = bridge, recorder, recorder.setup
        recorder.keys = self
        self.list_devices, self.command = keyboard.devices, None
        self.clock = TakeClock(bridge, self.setup, self)
        self._devices, self._take, self._count, self._look = [], None, 0, 0
        self._tick = QTimer(self, interval=100, timeout=self._poll)
        self._found.connect(self._got)
        recorder.armedChanged.connect(self.look_for_keyboards)
        self.clock.countChanged.connect(self.notesChanged)

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
        return self._take is not None

    @Property(int, notify=notesChanged)
    def notes(self):
        return self._count

    @Property(int, notify=notesChanged)
    def counting(self):
        return self.clock.counting

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

    @Slot()
    def toggleRecord(self):
        if self._take is not None:
            self._guard(self._finish)
        elif self.recorder.armed and self.usable:
            self._guard(self._begin)

    def _begin(self):
        self.setup.set("checkInput", False)
        self.clock.begin()
        take = keyboard.Take(self.bridge.doc.item(self.recorder.armed), device=self.setup.device(), command=self.command)
        take.start()
        self._take, self._count = take, 0
        self.clock.start()
        self._tick.start()
        self.recordingChanged.emit()
        self.notesChanged.emit()

    def _poll(self):
        def go():
            self._count = len(self._take.poll())
            self.notesChanged.emit()
        self._guard(go)

    def _finish(self):
        take = self._take
        try:
            notes = take.stop()
        finally:
            self._end(take)
        track = self.bridge.doc.item(self.recorder.armed)
        zero = self.clock.at - self.clock.lead                 # the timeline time of the keyboard's stream start
        call = keyboard.take_call(track, notes, zero, self.bridge.doc.data, self.setup.grid())
        if call is not None:
            self.bridge._apply([call], "Record keyboard take")
            self.bridge.select(track["id"])                    # the piano roll shows what was played

    def _end(self, take):
        self._take = None
        self._tick.stop()
        take.kill()
        self.clock.stop()
        self.recordingChanged.emit()

    def _guard(self, fn):
        try:
            fn()
        except RostrumError as e:
            if self._take is not None:
                self._end(self._take)
            self.bridge._fail(e.line())

    def close(self):
        if self._take is not None:
            self._end(self._take)
