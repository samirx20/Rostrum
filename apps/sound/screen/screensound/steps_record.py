"""Scripted steps for takes (see steps.py), each through the same call a click makes:

    take-panel (open the take panel) | take-set <key> <json value> (a take-panel row: countIn, countInBars, punch,
    hear, hearGain, midiDevice, quantize, quantizeGrid) | punch <from s> <to s> (what a drag on the ruler sets) |
    fake-player [<fake_play.py options>] (TEST SEAM: fake_play.py stands in for the engine's player) |
    record-fake <source.wav> (TEST SEAM: fake_play.py stands in for the engine's player and the microphone, then
    Record; the take stays running for the shot) | midi-fake <file.mid | note list> (TEST SEAM: fake_play.py plays
    the notes, two fake keyboards are listed) | keys (Record keys / Stop keys; stopping waits for the take to land)
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

from PySide6.QtCore import QCoreApplication

WORDS = ("take-panel", "take-set", "punch", "fake-player", "record-fake", "midi-fake", "keys")
FAKE = Path(__file__).with_name("fake_play.py")
FAKE_DEVICES = ["Fake keyboard (test)", "Fake pads (test)"]


def pump(until, seconds=5.0):
    end = time.monotonic() + seconds
    while not until() and time.monotonic() < end:
        QCoreApplication.processEvents()
        time.sleep(0.02)


def fake_player(recorder, extra):
    """TEST SEAM: the player becomes fake_play.py (reopened when it runs), keeping what an earlier fake was given."""
    p = recorder.player
    p.program = (p.program or [sys.executable, "-I", str(FAKE)]) + extra
    if p._proc is not None or p._needs_open():
        p._open()
    pump(lambda: bool(p.ready), 3.0)


def do_record_step(recorder, word, rest):
    setup, keys = recorder.setup, recorder.keys
    if word == "take-panel":
        setup.setOpen(True)
    elif word == "take-set":
        from .steps import value
        setup.set(rest[0], value(" ".join(rest[1:])))
    elif word == "punch":
        setup.setPunch(float(rest[0]), float(rest[1]), False)
    elif word == "fake-player":                              # fake-player [<fake_play.py options>]
        fake_player(recorder, rest)
    elif word == "record-fake":
        fake_player(recorder, ["--fake-source", rest[0]])
        recorder.toggleRecord()
        pump(lambda: False, 1.5)                             # let the count-in and a second of levels arrive
    elif word == "midi-fake":
        fake_player(recorder, ["--fake-notes", " ".join(rest)])
        keys.list_devices = lambda: list(FAKE_DEVICES)
        keys.look_for_keyboards()
        pump(lambda: keys.devices == FAKE_DEVICES)
    elif word == "keys":
        was = keys.recording
        keys.toggleRecord()
        pump(lambda: keys.recording != was or not was, 1.0)
