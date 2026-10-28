"""What agents rely on for limbs that read in a still and legs that act: limb() makes a tapered, outlined piece with a
joint shape that saves and reopens as made; step() side-steps foot by foot (the other foot stays planted) and lands both
feet `by` px on; an IK foot stays flat while the hip crouches."""
from rostrum_core import Document
from rostrum_core.keys import keys_of

from rostrum2d import KIND, run_source
from rostrum2d.evaluate import value_at

SRC = '''
comp("c", width=960, height=540, duration=4, fps=30)
with rig("bot", w=960, h=540, x=480, y=270):
    hip = bone("hip", x=480, y=360, angle=-90, length=0)
    chest = bone("chest", parent=hip, length=100)
    body = shape("body", w=140, h=150, x=480, y=300, fill="#e8b64a")
    bind(layer=body, bone=chest)
    legL = limb("legL", parent=hip, x=455, y=365, lengths=(45, 42, 18), widths=(24, 22, 16), kind="leg")
    legR = limb("legR", parent=hip, x=505, y=365, lengths=(45, 42, 18), widths=(24, 22, 16), kind="leg")
    armL = limb("armL", parent=chest, x=410, y=262, lengths=(62, 58, 11), widths=(22, 19, 31), joint="ball")
    done = step(legs=[legL, legR], by=120, at=0.5)
    pose({hip: {"moveY": 30}}, at=3.0)
'''


def _doc(folder=None):
    d = Document.new(KIND, folder=folder, item="bot" if folder else None)
    d.run_script("bot.py", run_source(SRC, "bot.py"))
    return d


def test_a_limb_tapers_has_a_joint_and_an_outline_and_reopens_as_made(tmp_path):
    d = _doc(tmp_path)
    d.save()
    d = Document.open(tmp_path, "bot", KIND)
    arm, joint = d.item("armL"), d.item("armL_joint")
    assert arm["type"] == "path" and arm["d"].startswith("M ")             # a tapered outline, bent by its bind
    binds = {b["layer"]: (b["bone"], b["bone2"]) for b in d.item("bot")["binds"]}
    assert binds["armL"] == ("armL_upper", "armL_lower") and binds["armL_joint"][0] == "armL_lower"
    assert arm["fill"] == "#e8b64a" and arm["stroke"] and arm["strokeColor"] != arm["fill"]   # body colour, darker line
    layers = [n["id"] for n in d.item("bot")["layers"]]
    assert layers.index("armL_joint") > layers.index("armL")              # "ball": drawn on top of the arm
    assert layers.index("legL_joint") < layers.index("legL")              # "round" (default): under the leg


def test_step_moves_one_foot_at_a_time_and_lands_both_by_the_distance():
    d = _doc()
    ikL, ikR, hip = d.item("legL_ik"), d.item("legR_ik"), d.item("hip")
    end = 0.5 + 0.25 * 2 * 2                                              # 120 px = 2 side-steps of 4 swings
    assert abs(value_at(ikR, "targetX", end) - (505 + 120)) < 0.5         # both feet `by` px on
    assert abs(value_at(ikL, "targetX", end) - (455 + 120)) < 0.5
    assert abs(value_at(hip, "moveX", end) - 120) < 0.5
    lead = [value_at(ikR, "targetX", t) for t in (0.5, 0.62, 0.75)]       # the right foot leads a step to the right ...
    trail = [value_at(ikL, "targetX", t) for t in (0.5, 0.62, 0.75)]      # ... while the left stays planted
    assert lead[-1] - lead[0] > 50 and max(trail) - min(trail) < 0.5
    assert value_at(ikL, "targetX", 1.0) - 455 > 50                        # then the left follows


def test_an_ik_foot_stays_flat_while_the_hip_crouches():
    d = _doc()
    foot = d.item("legL_end")
    assert keys_of(foot, "rotation")                                      # the shin's turn is taken off the foot
    shin_turn_cancelled = value_at(foot, "rotation", 3.0)
    assert abs(shin_turn_cancelled) > 1                                   # a crouch bends the knee, the foot counters it
