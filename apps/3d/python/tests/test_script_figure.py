"""A figure as one clay from a script (script_figure.py): what breaks silently is a figure floating above the ground
(or its attached eyes left behind when it comes to rest), a ball-on-ball figure whose head or limbs the joint finder
can't name, and a bend from the script landing on the wrong bone or not at every time."""
import numpy as np
import pytest

from rostrum3d import ops_pose, pose_joints as PJ, run_source, skin

from test_pose import _capsule, _grid, _smin

SHAPE = '''
c = clay("buddy", radius=0.07)
c.lump((0, 0.125, 0), 0.055, name="head")
c.lump((0.055, 0.04, 0), 0.02, to=(0.13, 0.0, 0), name="arm")
c.lump((0.035, -0.06, 0), 0.025, to=(0.04, -0.1, 0.02), name="leg")
mesh("eye", shape="sphere", radius=0.01, x=0.02, y=0.14, z=0.05, attach_to=c)
'''


def _items(tree):
    return {n["id"]: n for n in tree["items"]}


def test_a_figure_made_without_a_height_rests_on_the_ground_and_its_parts_come_along():
    items = _items(run_source(SHAPE, "f.py"))
    assert items["buddy"]["y"] == pytest.approx(0.125)                   # the leg's end (-0.1 - 0.025) on y = 0
    assert items["eye"]["y"] == pytest.approx(0.14 + 0.125)
    assert items["eye"]["follow"] == "buddy" and items["eye"]["followPose"] is True
    first = items["buddy"]["steps"][0]
    assert (first["shape"], first["radius"], first["at"]) == ("sphere", 0.07, [0.0, 0.0, 0.0])


def test_a_ball_or_capsule_clay_at_a_given_place_stays_there():
    items = _items(run_source('clay("b", at=(0.5, 0.3, 0), radius=0.05)\nclay("k", at=(0, 0.2, 0), to=(0, 0.4, 0), radius=0.03)', "b.py"))
    assert (items["b"]["x"], items["b"]["y"]) == (0.5, 0.3)
    k = items["k"]["steps"][0]
    assert k["shape"] == "capsule" and k["to"] == [0.0, 0.2, 0.0]


def _ball_figure(P):
    """SHAPE's clay as a distance (the engine's smooth join, blend half each piece's radius)."""
    d = _capsule(P, [0, 0, 0], [0, 0, 0], 0.07)
    d = _smin(d, _capsule(P, [0, 0.125, 0], [0, 0.125, 0], 0.055), 0.0275)
    for s in (1, -1):
        d = _smin(d, _capsule(P, [s * 0.055, 0.04, 0], [s * 0.13, 0.0, 0], 0.02), 0.01)
        d = _smin(d, _capsule(P, [s * 0.035, -0.06, 0], [s * 0.04, -0.1, 0.02], 0.025), 0.0125)
    return d


def _figure_grid(cells=48):
    return _grid(_ball_figure, lo=(-0.16, -0.13, -0.08), hi=(0.16, 0.19, 0.08), cells=cells)


def test_the_finder_names_a_ball_figures_head_arms_and_feet():
    names = {j["joint"] for j in PJ.find(_figure_grid(), mirror=True)}
    assert {"body", "chest", "head", "arm.L", "arm.R", "foot.L", "foot.R"} <= names, names


def test_bend_from_the_script_keys_that_joint_at_every_time():
    ops_pose.use_grid(lambda doc, id_, cells: _figure_grid(cells))
    try:
        src = SHAPE + 'shot("s", camera=camera("cam", z=1), start=0, end=2)\n' \
                      'c.bend("arm.R", {0: (0, 0, 0), 1: (0, 0, -100), 2: (0, 0, 0)})\n'
        clay = _items(run_source(src, "f.py"))["buddy"]
    finally:
        ops_pose.use_grid(None)
    bones = {b["joint"]: b for b, _ in skin.bones_of(clay)}
    arm = bones["arm.R"]
    times = sorted({k["t"] for k in arm["keys"]})
    assert times == [0.0, 1.0, 2.0]
    rz = {k["t"]: k["v"] for k in arm["keys"] if k["prop"] == "rz"}
    assert rz[0.0] == pytest.approx(rz[2.0], abs=1e-4) and abs(rz[1.0] - rz[0.0]) > 30
    assert not any(b["keys"] for j, b in bones.items() if j != "arm.R")          # nothing else moved
    with pytest.raises(Exception, match="already posed"):                         # a piece after posing: loud
        ops_pose.use_grid(lambda doc, id_, cells: _figure_grid(cells))
        try:
            run_source(src + 'c.lump((0, 0.2, 0), 0.01)\n', "f.py")
        finally:
            ops_pose.use_grid(None)
