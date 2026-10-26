"""Lip sync in 3D (brief 19): keys land at the right times for a known line, and making them is one undo step.
(The phones are given, not heard: no model runs in the test.)"""
from rostrum_core import Document, Who
from rostrum_core.lipsync import phonemes

from rostrum3d import KIND, run_source
from rostrum3d.compile import describe

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
    """Whether the child shows at time t as its Visible keys hold it (the last key at or before t)."""
    ks = [k for k in d.item(child)["keys"] if k["prop"] == "visible" and k["t"] <= t + 1e-9]
    return ks[-1]["v"] if ks else None


def test_keys_land_on_the_sounds_and_one_shape_shows_at_a_time(monkeypatch):
    d = _doc(monkeypatch)
    d.apply({"op": "lipsync.make", "target": ["mouth"], "args": {"file": "take.wav", "at": 1.0}}, SAM)
    # the line starts at 1.0 s; the mouth leads the sound by a frame (24 fps): closed for the m at 0.5 s, wide for the aa at 0.6 s
    assert [(k["t"], k["v"]) for k in d.item("mouth_closed")["keys"] if k["prop"] == "visible"] ==         [(1.0, 0.0), (1.4583, 1.0), (1.5417, 0.0)]                         # rest first, closed on the m, then gone
    assert [(k["t"], k["v"]) for k in d.item("mouth_wide")["keys"] if k["prop"] == "visible"] ==         [(1.0, 0.0), (1.5417, 1.0), (1.7083, 0.0)]                         # wide on the aa, rest again after it
    assert _shown(d, "mouth_closed", 1.5) == 1.0 and _shown(d, "mouth_wide", 1.5) == 0.0
    assert _shown(d, "mouth_wide", 1.6) == 1.0 and _shown(d, "mouth_closed", 1.6) == 0.0          # then D alone
    assert all(k["ease"] == "hold" for k in d.item("mouth_wide")["keys"])
    assert not any(k["prop"] in ("sx", "sy", "sz") for c in ("mouth_rest", "mouth_closed", "mouth_wide")
                   for k in d.item(c)["keys"])                            # nothing is shrunk: Scale is left alone
    scene = describe(d.data, "s")
    closed = next(c for c in scene["items"][0]["children"] if c["id"] == "mouth_closed")
    assert closed["props"]["sx"] == 2.0 and "sx" not in closed.get("anim", {})
    shown = closed["anim"]["visible"]                                       # one True / False per frame for the core
    assert shown[34] is False and shown[35] is True and shown[37] is False  # on for the m (frame 35), off at the aa (37)


def test_a_keyed_visible_holds_on_or_off_until_the_next_key():
    """Off at frame 12 hides it from 12 on, even with a smooth ease (never part way), and the next on-key shows it."""
    d = Document.new(KIND)
    d.run_script("t.py", run_source('''
box = mesh("box", shape="box")
box.key("visible", {0: True, 0.5: False, 1.0: True})
cam = camera("cam", z=3)
shot("s", camera=cam, fps=24, start=0, end=2)
''', "t.py"))
    assert all(k["ease"] == "smooth" for k in d.item("box")["keys"])
    shown = describe(d.data, "s")["items"][0]["anim"]["visible"]
    assert shown[:12] == [True] * 12 and shown[12:24] == [False] * 12 and shown[24:] == [True] * 24
    d.apply({"op": "key.add", "target": ["box"], "args": {"prop": "visible", "t": 1.5, "v": 0}}, SAM)
    assert describe(d.data, "s")["items"][0]["anim"]["visible"][36:] == [False] * 12


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
