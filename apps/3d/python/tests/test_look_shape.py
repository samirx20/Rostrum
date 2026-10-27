"""The look tools' numbers (CL7): what breaks silently is a spot named as the wrong step (an agent then reshapes the
body when it meant the arm, on the mirrored side most of all) and a left-right or thin-spot check that says all is
well when it isn't."""
import math

import numpy as np
from rostrum_core import Document, Who

from rostrum3d import KIND, shape_measure as SM, step_find as SF

SAM = Who.person()


def test_a_spot_on_either_arm_is_the_arm_step_and_the_middle_is_the_body():
    d = Document.new(KIND)
    d.apply({"op": "clay.add", "args": {"id": "c", "at": [0, 0, 0], "radius": 0.15, "symmetry": "x"}}, SAM)
    arm = [[-0.24 + 0.14 * math.cos(t), 0.035 * math.sin(t), 0.0] for t in np.linspace(0, 2 * math.pi, 24, endpoint=False)]
    d.apply({"op": "clay.draw", "target": ["c"], "args": {"outline": arm, "name": "arm"}}, SAM)
    steps = d.item("c")["steps"]
    arm_id = steps[-1]["id"]
    for spot in ([-0.33, 0.0, 0.02], [0.33, 0.0, 0.02], [0.33, 0.03, 0.0], [-0.2, -0.032, 0.0]):    # drawn side, mirrored side
        hit = SF.find(steps, spot)
        assert hit["id"] == arm_id and hit["label"] == "arm, drawn", spot
    assert SF.find(steps, [0.0, 0.15, 0.0])["id"] != arm_id                 # the top of the ball
    assert SF.find(steps, [0.0, 0.0, 0.15])["kind"] == "sphere"             # its front
    ids, missing = SF.match(steps, ["arm", "nose"])
    assert ids == {arm_id} and missing == ["nose"]
    joints = [{"joint": "arm.L", "head": [0.1, 0, 0], "tail": [0.3, 0, 0]}, {"joint": "arm.R", "head": [-0.1, 0, 0], "tail": [-0.3, 0, 0]}]
    assert SF.nearest_joint(joints, [0.25, 0.03, 0.0]) == {"joint": "arm.L", "distance": 0.03}


def test_look_shape_measures_a_lopsided_figure():
    cell = 0.01                                          # a 1 cm grid: a 40 cm tall body, one arm longer, a thin neck
    occ = np.zeros((80, 60, 20), bool)                    # x, y, z; X = 0 at index 40
    occ[30:50, 5:45, 5:15] = True                         # body 20 cm wide, 40 cm tall
    occ[39:41, 45:48, 9:11] = True                        # a 2 cm neck
    occ[35:45, 48:55, 6:14] = True                        # head
    occ[50:70, 30:34, 8:12] = True                        # left arm (+X) 20 cm
    occ[20:30, 30:34, 8:12] = True                        # right arm 10 cm
    origin = [-0.4, 0.0, -0.1]
    m = SM.measure(SM.from_grid(occ, origin, cell))
    assert math.isclose(m["height"], 0.50) and math.isclose(m["width"], 0.50) and math.isclose(m["depth"], 0.10)
    assert m["widest"]["width"] == 0.5
    assert m["mirror"]["worst"] > 0.05 and m["mirror"]["offFrom"] is not None
    row = next(r for r in m["levels"] if r["percent"] == 50)               # 25 cm up: the arms' row
    assert row["parts"] == 1 and math.isclose(row["left"], 0.30) and math.isclose(row["right"], 0.20)
    spots = SM.thin_spots(occ, origin, cell, thin=0.035)
    assert spots and all(0.45 <= s["at"][1] <= 0.48 for s in spots[:1])    # the neck comes first
