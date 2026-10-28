"""Script helpers agents rely on: limb() makes a bending limb with IK, walk() plants each foot while the body travels,
idle() and blink() only add keys, layer() finds an item by id; the UI blocks make a counting number and a clipped screen."""
from rostrum_core import Document
from rostrum_core.keys import keys_of

from rostrum2d import KIND, run_source
from rostrum2d.evaluate import value_at

SRC = '''
comp("c", duration=4, fps=30)
with rig("kid", w=1200, h=900):
    hip = bone("hip", x=400, y=500, angle=-90, length=0)
    chest = bone("chest", parent=hip, length=180)
    legL = limb("legL", parent=hip, x=400, y=500, lengths=(150, 140, 50), widths=(40, 36, 28), kind="leg")
    legR = limb("legR", parent=hip, x=400, y=500, lengths=(150, 140, 50), widths=(40, 36, 28), kind="leg")
    armL = limb("armL", parent=chest, x=400, y=340, lengths=(100, 90, 20), widths=(30, 26, 36))
    with group("eyes", swap=True, w=100, h=40) as eyes:
        shape("open", w=20, h=20); shape("shut", w=20, h=4)
    walk(legs=[legL, legR], arms=[armL], body=hip, start=0, end=2, step=0.5, stride=100)
    idle(chest, arms=[armL], start=2.5, end=4)
    blink(eyes, open="open", closed="shut", every=1.0)
    layer("armL").set(opacity=0.9)
'''


def test_walk_plants_feet_while_the_body_travels_and_everything_is_plain_keys():
    d = Document.new(KIND)
    d.run_script("kid.py", run_source(SRC, "kid.py"))
    assert d.item("legL_ik")["bend"] == "clockwise"                        # knees point the way it walks (right)
    assert d.item("legL_upper")["length"] == 150 and d.item("legL_lower")["parent"] == "legL_upper"
    binds = {b["layer"]: (b["bone"], b["bone2"]) for b in d.item("kid")["binds"]}
    assert binds["legL"] == ("legL_upper", "legL_lower")                 # one piece bent across the knee
    ik, hip = d.item("legL_ik"), d.item("hip")
    stance = [value_at(ik, "targetX", t) for t in (1.05, 1.25, 1.45)]    # leg L on the ground from 1.0 to 1.5 s
    assert max(stance) - min(stance) < 1.0                               # a planted foot stays put ...
    assert value_at(hip, "moveX", 1.5) - value_at(hip, "moveX", 1.0) > 90   # ... while the body walks on
    assert value_at(ik, "targetY", 1.75) < value_at(ik, "targetY", 1.25) - 5   # and lifts in the swing
    assert len(keys_of(ik, "targetX")) < 60                              # thinned, still editable
    assert keys_of(d.item("chest"), "scale") and d.item("armL")["opacity"] == 0.9
    assert len(keys_of(d.item("eyes"), "show")) >= 4


def test_ui_blocks_make_one_counting_text_and_a_clipped_screen():
    d = Document.new(KIND)
    src = '''
comp("c", duration=3)
scr = device("phone", kind="phone")
with scr:
    rows = list_rows([("Ana", "owes you", "$42.00"), "Ben"], y=200, w=scr.w)
    total = counter("total", 0, 186.4, at=1, duration=1.5, decimals=2, prefix="$")
'''
    d.run_script("ui.py", run_source(src, "ui.py"))
    total = d.item("total")
    assert total["counter"] and total["countPrefix"] == "$" and [k["v"] for k in keys_of(total, "count")] == [0, 186.4]
    assert d.item("phone_screen")["clip"] and d.item("list_r1_title")["body"] == "Ben"
