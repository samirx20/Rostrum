"""look_frame's flat-wash fact: a wash with its drying turned off is named as one flat value; one at paint.wash's
defaults is not (the defaults must stay strong enough to read at frame size)."""
from rostrum2d import run_source
from rostrum2d.mcp import look_wash

SRC = '''
comp("c", width=480, height=270, fps=10, duration=1, background="#efe6d2")
d = drawing("sky", w=480, h=270)
p = d.frame(0).paint("w")
p.wash(color="#7fa3c8", box=[20, 20, 460, 250]{extra})
'''


def _facts(extra=""):
    comp = run_source(SRC.format(extra=extra), "w.py")["comps"][0]
    return look_wash.facts(comp, 0.5)


def test_a_wash_with_no_drying_is_named_flat_and_a_default_one_is_not():
    off = _facts(", edge_darken=0, granulation=0, pooling=0, grain=0, bleed=0")
    assert len(off) == 1 and off[0]["flat"] and off[0]["spread"] < 1
    assert "one flat value at frame size" in look_wash.words(off) and "sky" in look_wash.words(off)
    on = _facts()
    assert len(on) == 1 and not on[0]["flat"] and on[0]["edge"] >= look_wash.EDGE
    assert look_wash.words(on) == ""
