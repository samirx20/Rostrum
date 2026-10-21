"""Camera rigs: what rides on a rig is where the rig says, every frame, and a handheld drift is the same every render
(agents compare renders; a drift that changed per run would look like a bug they made)."""
import math

from rostrum3d import compile as C
from rostrum3d.script import run_source

SRC = """
r = rig("spin", rig="orbit", radius=2, height=1, y=0.5, handheld={hh})
with r:
    camera("cam")
r.key("angle", {{0: 0, 2: 360}}, ease="linear")
shot("s", camera="cam", fps=4, start=0, end=2)
"""


def _cam_world(data, f):
    fr = C._Frames(data, range(0, 8), 4)
    return fr.world("cam", f)


def test_orbit_faces_centre_every_frame():
    data = run_source(SRC.format(hh=False), "t")
    for f in range(8):
        m, p = _cam_world(data, f)
        a = math.radians(360 * f / 8)
        assert math.isclose(p[0], 2 * math.sin(a), abs_tol=1e-6) and math.isclose(p[2], 2 * math.cos(a), abs_tol=1e-6)
        assert math.isclose(p[1], 1.5, abs_tol=1e-6)
        look = [-m[i][2] for i in range(3)]                     # the camera's −Z in the world
        to_centre = [0 - p[0], 0.5 - p[1], 0 - p[2]]
        n = math.hypot(*to_centre)
        assert sum(a_ * b / n for a_, b in zip(look, to_centre)) > 0.99999
    scene = C.describe(data, "s")
    spin = scene["items"][0]
    assert spin["type"] == "group" and len(spin["anim"]["ry"]) == 8
    assert all(b - a < 180 for a, b in zip(spin["anim"]["ry"], spin["anim"]["ry"][1:]))   # unwrapped


def test_handheld_is_repeatable_and_small():
    a, b = (C.describe(run_source(SRC.format(hh=True), "t"), "s") for _ in range(2))
    assert a == b
    plain = C.describe(run_source(SRC.format(hh=False), "t"), "s")
    shaken, still = (C._Frames(run_source(SRC.format(hh=h), "t"), range(8), 4) for h in (True, False))
    for f in range(8):
        (ms, ps), (m0, p0) = shaken.world("cam", f), still.world("cam", f)
        assert 0 < math.dist(ps, p0) < 0.05
        cos = sum(-ms[i][2] * -m0[i][2] for i in range(3))     # the two view directions
        assert math.degrees(math.acos(min(1.0, cos))) < 2
