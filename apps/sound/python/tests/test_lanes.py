"""Any setting can be automated through the one `automation.set`: an effect's envelope setting and a plug-in's
parameter reach the engine as envelopes, a lane emptied keeps the sound it started with, and each is one step."""
from rostrum_core import Document, Who

from rostrum_sound import KIND, compile, run_source

CUE = """
tempo(120)
pad = track("pad", builtIn="warmPad")
pad.note("D3", at=0, dur=4)
"""


def _doc():
    doc = Document.new(KIND)
    doc.run_script("cue.py", run_source(CUE, "cue.py"), Who.script("cue.py"))
    doc.apply({"op": "effect.add", "target": ["pad"], "args": {"effect": "compressor", "id": "pad.comp"}}, Who.person())
    return doc


def _lane(doc, target, lane, points, who=None):
    doc.apply({"op": "automation.set", "target": [target], "args": {"lane": lane, "points": points}},
              who or Who.person())


def test_effect_setting_lane_compiles_and_empties_to_its_start():
    doc = _doc()
    _lane(doc, "pad.comp", "threshold", [[0, -30], [{"beat": 4}, -10]], Who.script("agent.py"))
    fx = compile(doc)["tracks"][0]["effects"][0]
    assert fx["threshold"] == [[0, -30], [{"beat": 4}, -10]]  # reaches the engine as an envelope

    _lane(doc, "pad.comp", "threshold", [])
    assert doc.item("pad.comp")["threshold"] == -30            # emptied: the value it started with
    doc.undo(Who.person())
    assert doc.item("pad.comp")["threshold"][1][1] == -10       # one undo brings the lane back


def test_unknown_lane_is_refused_loudly():
    doc = _doc()
    try:
        _lane(doc, "pad.comp", "attack", [[0, 0.01], [1, 0.1]])  # attack takes no envelope
    except Exception as e:
        assert "attack" in str(e)
    else:
        raise AssertionError("attack lane was accepted")


def test_eq_band_lane_reaches_the_engine_and_empties_back_to_its_start():
    doc = _doc()
    doc.apply({"op": "effect.add", "target": ["pad"], "args": {"effect": "eq", "id": "pad.eq",
               "bands": [{"shape": "peak", "freq": 800, "gain": 0, "q": 1}]}}, Who.person())
    _lane(doc, "pad.eq", "band1.gain", [[0, -6], [2, 6]])
    eq = next(f for f in compile(doc)["tracks"][0]["effects"] if f["type"] == "eq")
    assert eq["bands"][0] == {"shape": "peak", "freq": 800, "gain": [[0, -6], [2, 6]], "q": 1}
    _lane(doc, "pad.eq", "band1.gain", [])
    assert doc.item("pad.eq")["bands"][0]["gain"] == -6
