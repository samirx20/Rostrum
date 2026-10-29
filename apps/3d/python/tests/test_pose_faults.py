"""rostrum3d/pose_faults.py: a posed figure's mistakes judges cap a piece for (gaps6 Hello: the waving arm through the head,
a "wave" too small to see, an eye left behind by a turning head), in the shot's one fault list; silent on a good pose."""
from rostrum_core import Document

from rostrum3d import KIND, ops_pose, run_source
from rostrum3d.compile import shot_info
from rostrum3d.faults import doc_faults

from test_script_figure import SHAPE, _figure_grid

SHOT = 'shot("s", camera=camera("cam", z=0.9, y=0.15), fps=24, start=0, end=72)\n'


def _found(lines: str, shape: str = SHAPE) -> dict:
    ops_pose.use_grid(lambda doc, id_, cells: _figure_grid(cells))
    try:
        doc = Document.new(KIND)
        doc.run_script("f.py", run_source(shape + SHOT + lines, "f.py"))
    finally:
        ops_pose.use_grid(None)
    info = shot_info(doc.data, "s")
    return {f["id"]: f for f in doc_faults(doc.data, info)}


def _pose(found: dict) -> dict:
    return {k: v for k, v in found.items() if k.split(":")[0] in ("through_body", "off_body", "reads_still")}


def test_an_arm_swung_through_the_head_names_the_joint_and_how_far_to_turn_it():
    found = _found('c.bend("arm.R", {0: (0, 0, 0), 1.5: (0, 0, -150), 3: (0, 0, -150)})\n')
    hit = [v for k, v in found.items() if k.startswith("through_body:buddy.")]
    assert hit and "into its head" in hit[0]["what"] and "°" in hit[0]["fix"], found
    good = _found('c.bend("arm.R", {0: (0, 0, 0), 1.5: (0, 0, -60), 3: (0, 0, -60)})\n')
    assert not [k for k in good if k.startswith("through_body:")], good


def test_a_wave_of_a_degree_reads_still_and_a_real_wave_does_not():
    def wave(deg):
        keys = ", ".join(f"{0.4 + i * 0.3:.1f}: (0, 0, {deg if i % 2 else -deg})" for i in range(6))
        return 'c.bend("arm.R", {0: (0, 0, -60), 3: (0, 0, -60)})\nc.bend("forearm.R", {0: (0, 0, 0), ' + keys + '})\n'
    assert "reads_still:buddy.forearm.R" in _found(wave(1)), "a 1° wave is not seen"
    assert not _pose(_found(wave(30))), "a 30° wave is a fine wave"


def test_an_eye_left_unattached_while_the_head_turns_slides_off_and_an_attached_one_rides_the_head():
    turn = 'c.bend("head", {0: (0, 0, 0), 1.5: (0, 50, 0), 3: (0, 50, 0)})\n'
    loose = SHAPE.replace(", attach_to=c)", ")")
    found = _found(turn, loose)
    assert "off_body:eye" in found and "not attached" in found["off_body:eye"]["what"], found
    assert "off_body:eye" not in _found(turn), "attach_to=c rides the head"
