"""Scripted steps for takes (see steps.py), each through the same call a click makes:

    take-panel (open the take panel) | take-set <key> <json value> (a take-panel row: countIn, countInBars, punch,
    punchIn, punchOut, checkInput, midiDevice, quantize, quantizeGrid) |
    midi-fake <file.mid | note list> (TEST SEAM: fake_midi.py stands in for two keyboards) |
    keys (Record keys / Stop keys; stopping waits for the take to land)
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

from PySide6.QtCore import QCoreApplication

WORDS = ("take-panel", "take-set", "midi-fake", "keys")
FAKE_DEVICES = ["Fake keyboard (test)", "Fake pads (test)"]


def pump(until, seconds=5.0):
    end = time.monotonic() + seconds
    while not until() and time.monotonic() < end:
        QCoreApplication.processEvents()
        time.sleep(0.02)


def do_record_step(recorder, word, rest):
    setup, keys = recorder.setup, recorder.keys
    if word == "take-panel":
        setup.setOpen(True)
    elif word == "take-set":
        from .steps import value
        setup.set(rest[0], value(" ".join(rest[1:])))
    elif word == "midi-fake":
        keys.list_devices = lambda: list(FAKE_DEVICES)
        keys.command = [sys.executable, "-I", str(Path(__file__).with_name("fake_midi.py")), " ".join(rest)]
        keys.look_for_keyboards()
        pump(lambda: keys.devices == FAKE_DEVICES)
    elif word == "keys":
        was = keys.recording
        keys.toggleRecord()
        pump(lambda: keys.recording != was or not was, 1.0)
