"""Scripted steps for swap stepping and the Export sheet's presets (called from steps.py):

    swap-demo                  three short sounds of different lengths stand in for the Library's results, the selected clip
                               stays selected and the Library is open on My sounds (no folder is read or changed)
    swap-step <+1|-1> | swap-keep | swap-back                 (↓ / ↑, Enter, Esc in the Library)
    voice-model-panel          (the question that asks before the voice model is downloaded, open, for a screenshot)
    export-preset <name> | export-stems <off|all|groups> | export-markers <on|off>      (the Export sheet's choices)
"""
from __future__ import annotations

import tempfile
from pathlib import Path

WORDS = ("swap-demo", "swap-step", "swap-keep", "swap-back", "export-preset", "export-stems", "export-markers", "voice-model-panel")
LENGTHS = (("short tick", 0.4), ("medium whoosh", 1.2), ("long riser", 3.0))


def _make_files(folder: Path) -> list[dict]:
    import numpy as np
    import soundfile as sf
    rows = []
    for i, (name, seconds) in enumerate(LENGTHS):
        n = int(44100 * seconds)
        t = np.arange(n) / 44100
        x = (0.4 * np.sin(2 * np.pi * (300 + 500 * i) * t) * np.minimum(1, (n - np.arange(n)) / 4410)).astype("float32")
        path = folder / f"{name}.wav"
        sf.write(str(path), x, 44100)
        rows.append({"path": str(path), "start": 0.0, "end": seconds, "name": path.name, "kind": "whoosh", "peak_s": 0, "onset_s": 0,
                     "what": f"whoosh · {seconds:.2f} s · mid · soft attack", "inFile": ""})
    return rows


def do_swap_step(bridge, word, rest):
    lib = bridge.library_panel
    if word == "swap-demo":
        folder = Path(tempfile.mkdtemp(prefix="swap-demo-"))
        bridge.workspace.setLibrary(True)
        bridge.libraryWanted.emit("mine")
        lib._folders, lib._results, lib._total, lib._status = [str(folder)], _make_files(folder), len(LENGTHS), f"{len(LENGTHS)} sounds"
        lib.changed.emit()
    elif word == "swap-step":
        lib.swapStep(int(rest[0]))
    elif word == "swap-keep":
        lib.swapKeep()
    elif word == "swap-back":
        lib.swapBack()
    elif word == "voice-model-panel":
        from rostrum_sound.cleanup import fetch
        bridge.side.voice.download.ask(fetch.NEEDS["voice"])
    elif word == "export-preset":
        bridge.mix.export.usePreset(rest[0])
    elif word == "export-stems":
        bridge.mix.export.setStemsMode(rest[0])
    elif word == "export-markers":
        bridge.mix.export.setMarkers(rest[0] == "on")
