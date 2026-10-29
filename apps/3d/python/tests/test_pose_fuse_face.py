"""rostrum3d/pose_fuse.py, pose_touch.py, pose_face.py: gaps7 Hello's judges saw the raised arm "melt into the side of the
head" and two eyes of different size ("the brow shrinks one eye"); each fault fires there and stays silent on a good figure."""
from rostrum_core import Document

from rostrum3d import KIND, ops_pose, run_source
from rostrum3d.compile import shot_info
from rostrum3d.faults import doc_faults

from test_script_figure import SHAPE, _figure_grid

SHOT = 'shot("s", camera=camera("cam", z=0.9, y=0.15), fps=24, start=0, end=36)\n'
EYES = SHAPE + 'mesh("eye2", shape="sphere", radius=0.01, x=-0.02, y=0.265, z=0.05, attach_to=c)\n'
STILL_HEAD = 'c.bend("head", {0: (0, 5, 0), 1.5: (0, 5, 0)})\n'


def _found(lines: str, shape: str = SHAPE) -> dict:
    ops_pose.use_grid(lambda doc, id_, cells: _figure_grid(cells))
    try:
        doc = Document.new(KIND)
        doc.run_script("f.py", run_source(shape + SHOT + lines, "f.py"))
    finally:
        ops_pose.use_grid(None)
    return {f["id"]: f for f in doc_faults(doc.data, shot_info(doc.data, "s"))}


def _arm(deg: float) -> str:
    return f'c.bend("arm.R", {{0: (0, 0, 0), 1.5: (0, 0, {deg})}})\n'


def _head_blend(b: float) -> str:
    return SHAPE.replace('name="head"', f'name="head", blend={b}')


def test_a_head_blend_reaching_the_shoulder_webs_head_and_arm_and_a_tight_one_does_not():
    found = _found(_arm(-60), _head_blend(0.06))   # its arm 5.2 cm from the head: inside a 6 cm blend
    hit = found.get("fused:buddy.head~arm")
    assert hit and "web of clay" in hit["what"] and 'name="head", blend=' in hit["fix"], found
    assert not [k for k in _found(_arm(-60), _head_blend(0.008)) if k.startswith("fused:")]


def test_a_raised_arm_grazing_the_head_touches_it_and_one_held_out_does_not():
    found = _found(_arm(-70), _head_blend(0.008))
    hit = found.get("touches_body:buddy.arm.R")
    assert hit and "one lump" in hit["what"] and "°" in hit["fix"], found
    good = _found(_arm(-60), _head_blend(0.008))
    assert not [k for k in good if k.split(":")[0] in ("touches_body", "through_body")], good


def test_eyes_of_two_sizes_or_one_under_a_brow_are_unmatched_and_a_three_quarter_turn_is_not():
    big = _found(STILL_HEAD, EYES.replace("radius=0.01, x=-0.02", "radius=0.013, x=-0.02"))
    assert "radius 0.0130" in big["face_unmatched:eye2~eye"]["fix"], big
    brow = _found(STILL_HEAD, EYES + 'c.lump((0.02, 0.27, 0.062), 0.011, name="brow", symmetry="off")\n')
    assert "brow lump covers it" in brow["face_unmatched:eye2~eye"]["what"], brow
    turned = _found('c.bend("head", {0: (0, 28, 0), 1.5: (0, 28, 0)})\n', EYES)
    assert not [k for k in turned if k.startswith("face_unmatched:")], turned
