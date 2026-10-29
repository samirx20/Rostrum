"""contact_faults.py / still_faults.py: two things passing through each other by their real forms (Ink, gaps6: a ball rolled
through a cone and a box, a ring sank into its plinth) and a shot whose end stands still (Spill/Drape: "hangs still"), in the
shot's one fault list (faults.doc_faults); touching and a short settle stay silent."""
from rostrum_core import Document

from rostrum3d import KIND, run_source
from rostrum3d.compile import shot_info
from rostrum3d.faults import doc_faults

SET = '''
camera("cam", z=2.2, y=0.5, rx=-10)
mesh("ground", shape="plane", width=20, depth=20)
mesh("plinth_top", shape="box", width=0.6, height=0.1, depth=0.3, x=0.6, y_world=0.05)
mesh("crate", shape="box", width=0.16, height=0.12, depth=0.16, x=-0.1, y_world=0.06, ry=20)
mesh("cone", shape="cone", radius=0.05, height=0.16, x=0.2, y_world=0.08)
mesh("ring", shape="torus", radius=0.08, tube=0.02, rx=90, x=0.6, y_world=RING)
mesh("ball", shape="sphere", radius=0.07, x=-0.5, z=Z, y_world=0.07).key("x", {0: -0.5, 2: 0.3}, ease="linear")
shot("hero", camera="cam", fps=24, start=0, end=4)
'''


def _faults(src: str) -> dict:
    doc = Document.new(KIND)
    doc.run_script("s.py", run_source(src, "s.py"))
    return {f["id"]: f for f in doc_faults(doc.data, shot_info(doc.data, "hero"))}


def test_a_ball_rolling_through_a_cone_and_a_box_and_a_sunk_ring_pass_through_and_touching_does_not():
    found = _faults(SET.replace("RING", "0.17").replace("Z", "0"))
    assert {"passes_through:ball~crate", "passes_through:ball~cone", "passes_through:plinth_top~ring"} <= set(found), found
    hit = found["passes_through:ball~cone"]
    assert hit["what"].startswith("ball passes through cone: ") and "cm deep at" in hit["what"], hit
    assert hit["fix"].startswith("move ball") and "along +z around 1.8 s (add a z key" in hit["fix"], hit   # across its path
    assert "ring" in found["passes_through:plinth_top~ring"]["fix"], found
    # the ring standing on the plinth (touching), the ball rolling past in front of both: nothing passes through
    found = _faults(SET.replace("RING", "0.2").replace("Z", "0.25"))
    assert not [i for i in found if i.startswith("passes_through:")], found


def test_a_shot_whose_last_seconds_stand_still_is_a_frozen_end_and_a_short_settle_is_not():
    found = _faults(SET.replace("RING", "0.2").replace("Z", "0.25").replace("2: 0.3", "1: 0.3"))
    end = found.get("frozen_end:hero")
    assert end and "nothing moves from 1.0 s to the end (3.0 s still" in end["what"] and "ball" in end["what"], found
    assert "end the shot at 1.5 s" in end["fix"], end
    found = _faults(SET.replace("RING", "0.2").replace("Z", "0.25"))          # moves to 2 s of 4: 2 s still is a settle
    assert "frozen_end:hero" not in found, found
