"""A figure as one clay from a script (script_figure.py): what breaks silently is a figure floating above the ground
(or its attached eyes left behind when it comes to rest), a ball-on-ball figure whose head or limbs the joint finder
can't name, and a bend from the script landing on the wrong bone or not at every time."""
import numpy as np
import pytest

from rostrum3d import ops_pose, pose_joints as PJ, run_source, skin

from test_pose import _capsule, _grid, _smin

UP = 0.125                     # SHAPE's numbers: heights above the ground (the ball's middle at its radius)
SHAPE = '''
c = clay("buddy", radius=0.07, x=0.0)
c.lump((0, 0.25, 0), 0.055, name="head")
c.lump((0.055, 0.165, 0), 0.02, to=(0.13, 0.125, 0), name="arm")
c.lump((0.035, 0.065, 0), 0.025, to=(0.04, 0.025, 0.02), name="leg")
mesh("eye", shape="sphere", radius=0.01, x=0.02, y=0.265, z=0.05, attach_to=c)
'''


def _items(tree):
    return {n["id"]: n for n in tree["items"]}


def test_a_figure_made_without_a_height_stands_on_the_ground_in_the_scenes_own_heights():
    items = _items(run_source(SHAPE, "f.py"))
    assert items["buddy"]["y"] == pytest.approx(0.0)                     # its space is the scene's: y = height
    first = items["buddy"]["steps"][0]
    assert (first["shape"], first["radius"], first["at"]) == ("sphere", 0.07, [0.0, 0.07, 0.0])
    assert items["eye"]["y"] == pytest.approx(0.265)
    assert items["eye"]["follow"] == "buddy" and items["eye"]["followPose"] is True


def test_a_piece_below_the_ground_lifts_the_figure_and_what_is_attached():
    items = _items(run_source('c = clay("b", radius=0.05)\nc.lump((0, -0.02, 0), 0.02)\n'
                              'mesh("hat", shape="sphere", radius=0.01, y=0.1, attach_to=c)', "b.py"))
    assert items["b"]["y"] == pytest.approx(0.04) and items["hat"]["y"] == pytest.approx(0.14)


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
    return _grid(lambda P: _ball_figure(P - np.array([0, UP, 0])), lo=(-0.16, -0.005, -0.08), hi=(0.16, 0.315, 0.08), cells=cells)


def _agent_figure(P):
    """A bench agent's figure (3d-gaps5 a1r1): the head blended deep into the body (no neck), arms held out low at
    the belly, short feet pointing forward."""
    d = _capsule(P, [0, .06, 0], [0, .06, 0], .06)
    d = _smin(d, _capsule(P, [0, .125, 0], [0, .125, 0], .05), .02)
    for s in (1, -1):
        d = _smin(d, _capsule(P, [s * .05, .05, 0], [s * .11, .03, 0], .017), .0085)
        d = _smin(d, _capsule(P, [s * .025, 0, .02], [s * .03, 0, .045], .02), .01)
    return d


def test_the_finder_names_a_head_with_no_neck_and_low_arms_as_arms():
    names = [j["joint"] for j in PJ.find(_grid(_agent_figure, lo=(-.14, -.03, -.08), hi=(.14, .19, .08)), mirror=True)]
    assert {"head", "arm.L", "arm.R", "foot.L", "foot.R"} <= set(names) and not any(n.startswith("leg") for n in names), names


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
    from rostrum3d import pose_ik
    r = pose_ik.Rig(clay)
    held = r.held(["body"])
    assert {r.joint[n] for n in held} == {"body", "chest"}                     # a held body holds the trunk, not the head
    with pytest.raises(Exception, match="already posed"):                         # a piece after posing: loud
        ops_pose.use_grid(lambda doc, id_, cells: _figure_grid(cells))
        try:
            run_source(src + 'c.lump((0, 0.2, 0), 0.01)\n', "f.py")
        finally:
            ops_pose.use_grid(None)


def test_a_joint_bent_later_in_the_script_keeps_only_its_own_keys():
    # gaps6 Hello r2: the other arm, bent after the wave was keyed, was pinned at rest on every wave key and stayed out
    clay = _items(_posed('c.bend("arm.R", {0: (0, 0, 0), 0.5: (0, 0, -60), 1: (0, 0, -40), 1.5: (0, 0, -60)})\n'
                         'c.bend("arm.L", {0: (0, 0, 0), 0.8: (0, 0, 60), 2: (0, 0, 60)})\n'))["buddy"]
    arm = {b["joint"]: b for b, _ in skin.bones_of(clay)}["arm.L"]
    assert sorted({k["t"] for k in arm["keys"]}) == [0.0, 0.8, 2.0]


def _posed(lines: str):
    ops_pose.use_grid(lambda doc, id_, cells: _figure_grid(cells))
    try:
        return run_source(SHAPE + 'shot("s", camera=camera("cam", z=1), start=0, end=2)\n' + lines, "f.py")
    finally:
        ops_pose.use_grid(None)


def test_pose_at_a_time_moves_several_parts_and_names_the_picture_sides_through_the_camera():
    # the camera at +z looks at the figure's face: its right hand (.R, the −x side) is on the picture's left
    tree = _posed('c.pose(0, **{"picture-left hand": {"up": 0.04}, "left hand": {"up": 0.03}})'
                  '.pose(0.5, **{"picture-left hand": {"up": 0.05, "out": 0.02}})\n')
    bones = {b["joint"]: b for b, _ in skin.bones_of(_items(tree)["buddy"])}
    assert sorted({k["t"] for k in bones["arm.R"]["keys"]}) == [0.0, 0.5]
    assert sorted({k["t"] for k in bones["arm.L"]["keys"]}) == [0.0]          # not named at 0.5: keeps its pose
    assert tree.notes == []
    with pytest.raises(Exception, match='no part "left paw".*hand.R|no part "left paw".*arm.R'):
        _posed('c.pose(0, **{"left paw": (0, 0.2, 0)})\n')


def test_a_pose_target_out_of_reach_or_past_the_middle_is_a_note_not_an_error():
    tree = _posed('c.pose(1, **{"right hand": (0.3, 0.5, 0)})\n')
    assert any("from the shoulder, its reach is" in n and "stops short" in n for n in tree.notes), tree.notes
    assert any("left side, past its middle; did you mean hand.L / picture-right hand?" in n for n in tree.notes), tree.notes
