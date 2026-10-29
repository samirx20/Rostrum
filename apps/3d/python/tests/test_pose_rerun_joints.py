"""Re-running a posed figure's script finds the same joints (3d-hello "What's left" 3: a re-run with only the camera
changed failed with "IndexError: list index out of range"). The clay's detail follows the shot camera, so a re-run,
whose scene still has the last run's camera, samples the same clay a hair differently; on that grid the arm and the leg
left the body in one band ring, the finder kept one of them and named it a leg, and "picture-right hand" then found no
hand. files/buddy_grids.json holds the two real grids (first run, re-run) of that figure."""
import base64
import json
import zlib
from pathlib import Path

import pytest

from rostrum3d import pose_joints as PJ, pose_names

GRIDS = json.loads((Path(__file__).parent / "files" / "buddy_grids.json").read_text())


def _grid(tag):
    g = GRIDS[tag]
    return {"dims": g["dims"], "origin": g["origin"], "cell": g["cell"],
            "inside": base64.b64encode(zlib.decompress(base64.b64decode(g["inside_zlib"]))).decode()}


def test_the_same_figure_sampled_twice_gets_the_same_joints():
    first, again = ([j["joint"] for j in PJ.find(_grid(t), mirror=True)] for t in ("first_run", "re_run"))
    assert again == first
    assert {"arm.L", "arm.R", "forearm.L", "leg.L", "shin.L", "foot.L", "foot.R", "head"} <= set(again)


class _Legs:
    """A rig with legs and no arms."""
    joint = ["body", "head", "leg.L", "shin.L", "leg.R", "shin.R"]

    def find(self, name):
        if name in self.joint:
            return self.joint.index(name)
        raise ValueError(name)


def test_a_picture_side_hand_on_a_figure_without_arms_is_a_plain_error():
    with pytest.raises(ValueError, match='no part "picture-right hand"'):
        pose_names.resolve("picture-right hand", _Legs(), "buddy.pose", seen=lambda part: [])
