"""H32: transparency defaults off on a solid background (a GIF with the panel's defaults exports); Lottie leaves out a
layer kind it can't carry and lists it; a second K with nothing changed keys nothing (K never makes a flat field);
pulse() is 1 on a beat and falls to 0 over its decay."""
import pytest
from rostrum_core import Document, RostrumError, Who

from rostrum2d import KIND, run_source
from rostrum2d.expr_lib import pulse
from rostrum2d.io.lottie import to_lottie
from rostrum2d.mcp import exporting
from rostrum2d.scene import describe

SAM = Who.person("sam")
SRC = '''
comp("c", width=320, height=180, fps=10, duration=2)
a = shape("a", x=100, w=10, h=10)
'''


def _doc():
    d = Document.new(KIND)
    d.run_script("s.py", run_source(SRC, "s.py"))
    return d


def test_transparency_defaults_to_the_background():
    assert exporting.settings("t", "gif", 2.0)["alpha"] is False
    assert exporting.settings("t", "gif", 2.0, background="transparent")["alpha"] is True
    assert exporting.settings("t", "prores4444", 2.0, background="#00000000")["alpha"] is True
    assert exporting.settings("t", "gif", 2.0, alpha=True)["alpha"] is True      # asked for: kept


def test_lottie_lists_a_kind_it_cannot_carry():
    scene = describe(_doc().data)
    odd = {**scene["comp"]["layers"][-1], "id": "odd", "type": "spotlight"}
    scene["comp"]["layers"].append(odd)
    lottie, report = to_lottie(scene)
    assert any('"odd"' in line and "spotlight" in line for line in report)
    assert lottie["layers"]


def test_k_twice_without_a_change_keys_nothing_new():
    d = _doc()
    d.apply({"op": "key.add", "target": ["a"], "args": {"fields": "pose", "t": 0.5}}, SAM)
    with pytest.raises(RostrumError):                       # nothing to key, said loudly
        d.apply({"op": "key.add", "target": ["a"], "args": {"fields": "pose", "t": 1.0}}, SAM)
    d.apply({"op": "value.set", "target": ["a"], "args": {"prop": "x", "v": 150, "at": 1.0}}, SAM)
    d.apply({"op": "key.add", "target": ["a"], "args": {"fields": "pose", "t": 1.5}}, SAM)
    keyed = {k["prop"] for k in d.item("a")["keys"] if k["t"] == 1.5}       # X moves: the whole pose, the still ones as
    assert "x" in keyed and keyed >= {"y", "opacity"}                          # holds (production round, hand row 24)


def test_pulse_is_one_on_the_beat_and_falls_to_zero():
    beats = [0.5, 1.0, 1.5]
    assert pulse(beats, 0.4, 0.25) == 0.0 and pulse(beats, 0.5, 0.25) == 1.0
    assert pulse(beats, 0.625, 0.25) == pytest.approx(0.5) and pulse(beats, 0.9, 0.25) == 0.0
    assert pulse(beats, 1.0, 0.25) == 1.0
