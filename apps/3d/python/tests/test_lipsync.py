"""Lip sync in 3D (brief 19): keys land at the right times for a known line, and making them is one undo step.
(The phones are given, not heard: no model runs in the test.)"""
from rostrum_core import Document, Who
from rostrum_core.lipsync import phonemes

from rostrum3d import KIND, run_source

SAM = Who.person()
PHONES = [{"phone": "m", "start": 0.50, "end": 0.52}, {"phone": "ɑː", "start": 0.60, "end": 0.62}]
SRC = '''
with group("mouth", y=0.5, sx=1):
    mesh("mouth_rest", shape="disc", radius=0.05)
    mesh("mouth_closed", shape="disc", radius=0.04, sx=2)
    mesh("mouth_wide", shape="disc", radius=0.07)
cam = camera("cam", z=3)
shot("s", camera=cam, fps=24, start=0, end=3)
'''


def _doc(monkeypatch):
    monkeypatch.setattr(phonemes, "analyse", lambda *a, **k: {"phones": PHONES, "words": [], "end": 2.0, "mode": "decoded",
                                                              "device": "cpu", "computed": False})
    d = Document.new(KIND)
    d.run_script("t.py", run_source(SRC, "t.py"))
    return d


def _shown(d, child, t):
    """The child's Scale X at time t as its keys hold it (the last key at or before t)."""
    ks = [k for k in d.item(child)["keys"] if k["prop"] == "sx" and k["t"] <= t + 1e-9]
    return ks[-1]["v"] if ks else None


def test_keys_land_on_the_sounds_and_one_shape_shows_at_a_time(monkeypatch):
    d = _doc(monkeypatch)
    d.apply({"op": "lipsync.make", "target": ["mouth"], "args": {"file": "take.wav", "at": 1.0}}, SAM)
    # the line starts at 1.0 s; the mouth leads the sound by a frame (24 fps): closed for the m at 0.5 s, wide for the aa at 0.6 s
    assert [(k["t"], k["v"]) for k in d.item("mouth_closed")["keys"] if k["prop"] == "sx"] ==         [(1.0, 0.0001), (1.4583, 2.0), (1.5417, 0.0001)]                 # rest first, closed on the m, then gone
    assert [(k["t"], k["v"]) for k in d.item("mouth_wide")["keys"] if k["prop"] == "sx"] ==         [(1.0, 0.0001), (1.5417, 1.0), (1.7083, 0.0001)]                 # wide on the aa, rest again after it
    assert _shown(d, "mouth_closed", 1.5) == 2.0 and _shown(d, "mouth_wide", 1.5) == 0.0001        # closed shows (at its own Scale 2)
    assert _shown(d, "mouth_wide", 1.6) == 1.0 and _shown(d, "mouth_closed", 1.6) == 0.0001        # then D alone
    assert all(k["ease"] == "hold" for k in d.item("mouth_wide")["keys"])


def test_it_is_one_undo_step_and_a_second_run_adds_nothing(monkeypatch):
    d = _doc(monkeypatch)
    call = {"op": "lipsync.make", "target": ["mouth"], "args": {"file": "take.wav", "at": 1.0}}
    d.apply(call, SAM)
    d.undo(SAM)                                                          # one undo takes every key on every shape back
    assert not d.item("mouth_wide").get("keys") and not d.item("mouth_closed").get("keys") and not d.item("mouth_rest").get("keys")
    d.redo(SAM)
    keys = len(d.item("mouth_wide")["keys"])
    d.apply(call, SAM)
    assert len(d.item("mouth_wide")["keys"]) == keys
