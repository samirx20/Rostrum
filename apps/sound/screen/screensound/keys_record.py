"""Keyboard takes on the screen: with a track armed (recording.py's arm) and a MIDI keyboard connected, Keys records
what is played (the engine's `live`, rostrum_sound.midi.keyboard) while the mix plays from the playhead; Stop puts
the take on the armed track as one `note.add_many` (drum tracks: `hit.add_many`), one undo step, a person's edit.
Absent when no keyboard is connected (the device list is read again on every arm). Built against the engine's
output lines; not tried with a real keyboard on this machine (it has none).
"""
from __future__ import annotations

import threading

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot
from rostrum_core import RostrumError
from rostrum_sound.midi import keyboard


class KeysRecording(QObject):
    devicesChanged = Signal()
    recordingChanged = Signal()
    notesChanged = Signal()

    def __init__(self, bridge, recorder, parent=None):
        super().__init__(parent)
        self.bridge, self.recorder = bridge, recorder
        self._devices, self._take, self._at, self._started_play, self._count = [], None, 0.0, False, 0
        self._tick = QTimer(self, interval=100, timeout=self._poll)
        recorder.armedChanged.connect(self._look_for_keyboards)

    @Property("QVariantList", notify=devicesChanged)
    def devices(self):
        """The connected keyboards' names ([] = none: the Keys button is absent)."""
        return self._devices

    @Property(bool, notify=recordingChanged)
    def recording(self):
        return self._take is not None

    @Property(int, notify=notesChanged)
    def notes(self):
        return self._count

    def _look_for_keyboards(self):
        if not self.recorder.armed:
            return
        def look():
            try:
                found = keyboard.devices()
            except (RostrumError, OSError, ValueError):
                found = []                       # no engine or no keyboards: the button stays absent
            if found != self._devices:
                self._devices = found
                self.devicesChanged.emit()
        threading.Thread(target=look, daemon=True).start()

    @Slot()
    def toggleRecord(self):
        if self._take is not None:
            self._guard(self._finish)
        elif self.recorder.armed and self._devices:
            self._guard(self._begin)

    def _begin(self):
        track = self.bridge.doc.item(self.recorder.armed)
        take = keyboard.Take(track, device=0)
        take.start()
        self._take, self._at, self._count = take, self.bridge.time, 0
        self._started_play = not self.bridge.playing
        if self._started_play:
            self.bridge.togglePlay()
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
        call = keyboard.take_call(track, notes, round(self._at, 3), self.bridge.doc.data)
        if call is not None:
            self.bridge._apply([call], "Record keyboard take")

    def _end(self, take):
        self._take = None
        self._tick.stop()
        take.kill()
        if self._started_play and self.bridge.playing:
            self.bridge.togglePlay()
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
