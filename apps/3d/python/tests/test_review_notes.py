"""review_faults.py and the review notes in the shot's one list (3D review notes, 2026-10-30): the camera inside a shape, an
empty or one-thing picture, a landing above or into a stone, a slide on the ground (not a roll), a planted foot sliding, a
still stretch mid-shot, a subject in near-black, and what could not be measured. Observations with numbers and times; a
good scene stays silent. Synthetic: no engine."""
from PIL import Image

from rostrum_core import Document

from rostrum3d import KIND, ops_pose, run_source
from rostrum3d.compile import shot_info
from rostrum3d.faults import doc_faults
from rostrum3d.mcp import light_faults, shot_faults
from rostrum3d.motion_track import Track

from test_script_figure import SHAPE, _figure_grid

GROUND = 'mesh("ground", shape="plane", width=20, depth=20)\n'


def _doc(src: str) -> Document:
    doc = Document.new(KIND)
    doc.run_script("s.py", run_source(src, "s.py"))
    return doc


def _notes(src: str, shot: str = "hero", at=None, pictures=None) -> dict:
    doc = _doc(src)
    return {f["id"]: f for f in doc_faults(doc.data, shot_info(doc.data, shot), at=at, pictures=pictures)}


def _kinds(found: dict, kind: str) -> dict:
    return {k: v for k, v in found.items() if k.split(":")[0] == kind}


def test_the_camera_inside_a_crate_or_touching_a_ball_is_said_and_one_clear_of_both_is_not():
    src = GROUND + 'camera("cam", z=2, y=0.3)\nmesh("crate", shape="box", width=0.4, height=0.4, depth=0.4, z=Z, y_world=0.3)\n' \
                   'mesh("ball", shape="sphere", radius=0.1, z=0, y_world=0.3)\nshot("hero", camera="cam", fps=24, start=0, end=1)\n'
    inside = _notes(src.replace("Z", "2"))
    assert "camera_inside:crate" in inside and "inside crate" in inside["camera_inside:crate"]["what"], inside
    clear = _notes(src.replace("Z", "1"))
    assert not _kinds(clear, "camera_inside"), clear
    touch = _notes(src.replace("Z", "1").replace('z=0, y_world=0.3', 'z=1.895, y_world=0.3'))
    assert "touches ball" in touch["camera_inside:ball"]["what"] and "exact form" in touch["camera_inside:ball"]["what"], touch


def test_a_far_tiny_ball_leaves_the_frame_empty_and_a_crate_up_close_fills_it():
    src = GROUND + 'camera("cam", z=3, y=0.3)\nmesh("ball", shape="sphere", radius=R, y_world=0.3)\nshot("hero", camera="cam", fps=24, start=0, end=1)\n'
    empty = _notes(src.replace("R", "0.03"))
    assert "empty_frame:hero" in empty and "% of the picture" in empty["empty_frame:hero"]["what"], empty
    full = _notes(src.replace("R", "1.2"))
    assert "fills_frame:ball" in full and "empty_frame:hero" not in full, full
    fine = _notes(src.replace("R", "0.4"))
    assert not _kinds(fine, "empty_frame") and not _kinds(fine, "fills_frame"), fine


HOP = GROUND + '''camera("cam", z=2.5, y=0.6, rx=-10)
mesh("stone", shape="box", width=0.3, height=0.1, depth=0.3, x=0.5)
mesh("hopper", shape="box", width=0.1, height=0.1, depth=0.1).key("x", {0: 0, 1: 0.5, 2: 0.5}).key("y", {0: 0, 0.5: 0.4, 1: LAND, 2: LAND})
shot("hero", camera="cam", fps=24, start=0, end=2)
'''


def test_a_hop_that_stops_above_or_inside_the_stone_is_a_landing_note_and_one_on_it_is_not():
    above = _notes(HOP.replace("LAND", "0.14"))
    hit = above.get("lands_above:hopper")
    assert hit and "stops 4 cm above stone at 1.0 s" in hit["what"], above
    into = _notes(HOP.replace("LAND", "0.07"))
    assert "lands_in:hopper" in into and "3 cm into stone" in into["lands_in:hopper"]["what"], into
    on = _notes(HOP.replace("LAND", "0.1"))
    assert not _kinds(on, "lands_above") and not _kinds(on, "lands_in"), on


def test_a_crate_pushed_along_the_ground_slides_and_a_rolling_ball_does_not():
    src = GROUND + 'camera("cam", z=2.5, y=0.4)\n' \
                   'mesh("crate", shape="box", width=0.1, height=0.1, depth=0.1).key("x", {0: -0.3, 1: 0.1})\n' \
                   'mesh("ball", shape="sphere", radius=0.1, z=-0.5).key("x", {0: -0.3, 1: 0.328}).key("rz", {0: 0, 1: -360})\n' \
                   'shot("hero", camera="cam", fps=24, start=0, end=2)\n'
    found = _notes(src)
    assert "slides:crate" in found and "40 cm along the ground, 0.0 s–1.0 s" in found["slides:crate"]["what"], found
    assert "slides:ball" not in found, found


def _figure(lines: str) -> dict:
    ops_pose.use_grid(lambda doc, id_, cells: _figure_grid(cells))
    try:
        return _notes(SHAPE + GROUND + 'shot("s", camera=camera("cam", z=0.9, y=0.15), fps=24, start=0, end=3)\n'
                      'c.bend("arm.R", {0: (0, 0, -10), 2: (0, 0, -20)})\n' + lines, "s")
    finally:
        ops_pose.use_grid(None)


def test_a_figure_moved_along_with_its_feet_planted_slides_its_feet_and_a_figure_standing_does_not():
    moved = _figure('c.key("x", {0: 0, 2: 0.2})\n')
    foot = moved.get("slides:buddy.foot.L")
    assert foot and "slides while planted" in foot["what"] and "20 cm" in foot["what"], moved
    still = _figure("")
    assert not [k for k in still if k.startswith("slides:")], still


def test_a_pause_mid_shot_is_a_still_stretch_and_a_short_hold_is_not():
    src = GROUND + 'camera("cam", z=2.5, y=0.4)\nmesh("ball", shape="sphere", radius=0.1).key("x", {0: -0.5, 1: 0, HOLD: 0, 5.5: 0.5})\n' \
                   'shot("hero", camera="cam", fps=24, start=0, end=6)\n'
    long = _kinds(_notes(src.replace("HOLD", "3.5")), "still")
    assert len(long) == 1 and "nothing moves from 1.0 s to 3.5 s" in next(iter(long.values()))["what"], long
    assert not _kinds(_notes(src.replace("HOLD", "2")), "still")


def test_a_lit_crate_near_black_in_its_picture_is_a_dark_subject_and_a_black_one_is_not(tmp_path):
    src = GROUND + 'camera("cam", z=2, y=0.2)\nmaterial("paint", baseColor="COLOUR")\n' \
                   'mesh("crate", shape="box", width=0.4, height=0.4, depth=0.4, y_world=0.2, material="paint")\n' \
                   'shot("hero", camera="cam", fps=24, start=0, end=1)\n'

    def dark(colour, grey):
        doc = _doc(src.replace("COLOUR", colour))
        info = shot_info(doc.data, "hero")
        cam = Track(doc.data, info, range(0, 1)).cams[0]
        png = tmp_path / f"{colour[1:]}_{grey}.png"
        Image.new("RGB", (cam.w, cam.h), (grey,) * 3).save(png)
        return light_faults.dark_subjects(doc.data, info, 0, png)

    hit = dark("#d0a070", 8)
    assert [f["id"] for f in hit] == ["dark_subject:crate"] and "mean brightness 0.03" in hit[0]["what"], hit
    assert not dark("#d0a070", 120) and not dark("#080808", 8)


def test_what_was_not_measured_is_said_so_an_empty_list_is_never_an_all_clear():
    src = GROUND + 'camera("cam", z=2.5, y=0.4)\nmesh("crate", shape="box", width=0.2, height=0.2, depth=0.2)\nshot("hero", camera="cam", fps=24, start=0, end=1)\n'
    none = _notes(src, pictures=False)
    assert "no picture was looked at" in none["not_measured:hero"]["what"], none
    one = _notes(src, at=12)
    assert "need the whole shot" in one["not_measured:hero"]["what"], one
    assert "not_measured:hero" not in _notes(src)            # a whole shot with its pictures, fixed forms only: all of it measured


def test_a_whole_shot_with_pictures_keeps_each_note_once(tmp_path):
    doc = _doc(HOP.replace("LAND", "0.14"))
    info = shot_info(doc.data, "hero")
    png = tmp_path / "f.png"
    Image.new("RGB", (64, 36), (120, 120, 120)).save(png)
    found = shot_faults.check(doc.data, info, [0, 24, 48], {24: png})
    ids = [f["id"] for f in found]
    assert "lands_above:hopper" in ids and len(ids) == len(set(ids)), ids
