"""Round sound-ascent: a brief that asks to begin quiet or end quiet has its arc read against the piece's own loudest
3 s (listen/arc.py); a brief that does not ask is never held to it."""
from types import SimpleNamespace

import numpy as np
import soundfile as sf

from rostrum_sound.listen import arc

SR = 48000
ASCENT = "Begins quiet (soft strings), builds steadily over 30+ s, climax at 38 s, then settles to a quiet ending at 50 s."


def _swell(path, under_db):
    """20 s: a 220 Hz tone `under_db` under its peak for the first and last 5 s, at the peak in between."""
    t = np.arange(20 * SR) / SR
    gain = np.where((t < 5) | (t >= 15), 10 ** (-under_db / 20), 1.0)
    y = 0.5 * np.sin(2 * np.pi * 220 * t) * gain
    sf.write(path, np.stack([y, y], axis=1), SR, subtype="PCM_24")
    return str(path)


def _doc(brief):
    return SimpleNamespace(data={"brief": brief}, folder=None)


def test_a_shallow_arc_is_a_fault_only_when_the_brief_asks_for_quiet(tmp_path):
    shallow, deep = _swell(tmp_path / "s.wav", 12), _swell(tmp_path / "d.wav", 30)
    assert {f["id"] for f in arc.fault(_doc(ASCENT), shallow)} == {"loud_opening", "loud_ending"}
    assert arc.fault(_doc(ASCENT), deep) == []
    assert arc.fault(_doc("A 4-bar piano chord progression at 90 bpm"), shallow) == []
