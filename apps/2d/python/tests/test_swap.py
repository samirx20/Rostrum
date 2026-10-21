"""Swap sets: the scene shows exactly one child per frame from the `show` keys (own opacity keys kept); blink.add never
adds over what is there (a moved key stays); lip sync into a slot keys `show`, not each layer's opacity."""
from rostrum_core import Document, Who
from rostrum_core.keys import keys_of, track_value

from rostrum2d import KIND, run_source
from rostrum2d.lipsync import phonemes
from rostrum2d.scene import describe

SAM = Who.person("sam")
SRC = '''
comp("scene", fps=10, duration=1)
mouth = group("mouth", swap=True)
with mouth:
    shape("a"); shape("b"); shape("z")
mouth.show({0: "a", 0.3: 1, 0.6: "z"})
'''
OWN = SRC + 'b = None\n'


def opacity(node, t):
    keys = node.get("anim", {}).get("opacity")
    return track_value(keys, t) if keys else node["props"]["opacity"]


def test_scene_shows_one_child_a_frame_and_keeps_own_opacity_keys():
    d = Document.new(KIND)
    d.run_script("s.py", run_source(SRC, "s.py"))
    d.apply({"op": "key.add", "target": "b", "args": {"prop": "opacity", "t": 0, "v": 0.5}}, SAM)
    d.apply({"op": "key.add", "target": "b", "args": {"prop": "opacity", "t": 1, "v": 1.0}}, SAM)
    kids = {n["id"]: n for n in describe(d.data)["comp"]["layers"][0]["layers"]}
    for f in range(10):
        t = f / 10
        shown = [k for k, n in kids.items() if opacity(n, t) > 0]
        assert shown == [["a", "b", "z"][0 if t < 0.3 else 1 if t < 0.6 else 2]], (t, shown)
    assert abs(opacity(kids["b"], 0.4) - track_value(keys_of(d.item("b"), "opacity"), 0.4)) < 1e-9          # its own fade, times being the one shown
    assert "swap" not in kids and "show" not in describe(d.data)["comp"]["layers"][0]["props"]


def test_blinks_add_keys_once_and_a_moved_key_stays():
    d = Document.new(KIND)
    d.run_script("s.py", run_source('comp("c", fps=10, duration=12)\neyes = group("eyes", swap=True)\n'
                                    'with eyes:\n    shape("open"); shape("closed")\n', "s.py"))
    blink = {"op": "blink.add", "target": "eyes", "args": {"open": "open", "closed": "closed", "seed": 3}}
    d.apply(blink, SAM)
    keys = d.item("eyes")["keys"]
    assert len(keys) >= 3 and all(k["ease"] == "hold" for k in keys)
    moved = keys[1]
    d.apply({"op": "key.set", "target": moved["id"], "args": {"t": moved["t"] + 0.05}}, SAM)
    d.apply(blink, SAM)
    assert len(d.item("eyes")["keys"]) == len(keys) and d.item(moved["id"])["t"] == moved["t"] + 0.05


def test_lip_sync_into_a_slot_keys_show(monkeypatch):
    phones = [{"phone": "m", "start": 0.5, "end": 0.52}, {"phone": "ɑː", "start": 0.6, "end": 0.62}]
    monkeypatch.setattr(phonemes, "analyse", lambda *a, **k: {"phones": phones, "words": [], "end": 2.0,
                                                              "mode": "decoded", "device": "cpu", "computed": False})
    src = ('comp("c", fps=25, duration=3)\nface = group("face", swap=True)\nwith face:\n'
           '    rest = shape("m_X"); closed = shape("m_A"); wide = shape("m_D")\n'
           'lipsync("take.wav", shapes={"X": rest, "A": closed, "D": wide}, slot=face)\n')
    d = Document.new(KIND)
    d.run_script("t.py", run_source(src, "t.py"))
    shows = [(k["t"], k["v"]) for k in d.item("face")["keys"] if k["prop"] == "show"]
    assert shows and {v for _, v in shows} <= {0, 1, 2} and 1 in {v for _, v in shows}
    assert not any(k["prop"] == "opacity" for n in ("m_X", "m_A", "m_D") for k in d.item(n).get("keys", []))
    d2 = Document.new(KIND)           # the operation does the same on a document
    d2.run_script("t.py", run_source(src.split("lipsync(")[0], "t.py"))
    d2.apply({"op": "lipsync.apply", "target": "face", "args": {"source": "take.wav", "shapeX": "m_X",
                                                                  "shapeA": "m_A", "shapeD": "m_D"}}, SAM)
    assert [(k["t"], k["v"]) for k in d2.item("face")["keys"] if k["prop"] == "show"] == shows
