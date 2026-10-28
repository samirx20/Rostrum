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


def test_ui_blocks_make_one_counting_text_and_a_column_screen():
    d = Document.new(KIND)
    src = '''
comp("c", duration=3)
scr = device("phone", kind="phone")
with scr:
    rows = list_rows([("Ana", "owes you", "$42.00"), "Ben"])
    total = counter("total", 0, 186.4, at=1, duration=1.5, decimals=2, prefix="$")
'''
    d.run_script("ui.py", run_source(src, "ui.py"))
    total = d.item("total")
    assert total["counter"] and total["countPrefix"] == "$" and [k["v"] for k in keys_of(total, "count")] == [0, 186.4]
    assert d.item("phone_screen")["layout"] == "column" and d.item("list_r1_title")["body"] == "Ben"


def test_an_arm_keyed_on_its_upper_bone_alone_bends_at_rest_and_follows_the_swing_and_takes_the_body_colour():
    src = '''
comp("c", duration=4, fps=30)
with rig("bot", w=1200, h=900):
    hip = bone("hip", x=600, y=600, angle=-90, length=0)
    chest = bone("chest", parent=hip, length=200)
    body = shape("body", w=200, h=240, x=600, y=480, fill="#f2b23c")
    bind(layer=body, bone=chest)
    armR = limb("armR", parent=chest, x=720, y=420, lengths=(120, 110, 20), widths=(40, 34, 50))
    assert armR.out == -1                                     # negative turns swing a screen-right arm away from the body
    armR.upper.key("rotation", {0: 0, 1: 0, 1.6: -130, 4: -130})
    legL = limb("legL", parent=hip, x=560, y=600, lengths=(150, 140, 40), kind="leg")
    legR = limb("legR", parent=hip, x=640, y=600, lengths=(150, 140, 40), kind="leg")
    idle(chest, legs=[legL, legR], start=0, end=4)
    pose({armR: -60, layer("chest"): {"rotation": 6}}, at=3.5, take=0.6)
'''
    d = Document.new(KIND)
    d.run_script("bot.py", run_source(src, "bot.py"))
    lo, up = d.item("armR_lower"), d.item("armR_upper")
    assert value_at(lo, "rotation", 0.5) > 12                            # relaxed: the elbow bent, hand toward the body
    assert value_at(lo, "rotation", 2.5) < -20                           # raised: the forearm bends on up the way it swung
    assert d.item("armR")["fill"] == "#f2b23c"                           # no colour given: the body's
    lift = value_at(up, "rotation", 3.5 - 0.6 * 0.55)                    # pose: a pull back before the move ...
    assert lift < -130 and value_at(up, "rotation", 3.5) > -60           # ... a swing past, then it settles
    assert abs(value_at(up, "rotation", 3.85) + 60) < 0.01
    hip = d.item("hip")                                                  # weight shift: the hip slides foot to foot
    xs = [value_at(hip, "moveX", t) for t in (0.5, 1.5, 2.5, 3.5)]
    assert max(xs) - min(xs) > 3

