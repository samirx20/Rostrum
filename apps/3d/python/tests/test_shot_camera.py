"""Make this the shot and Frame the selection (ops_shot_camera.py) would break silently: the picture the camera takes
must be the one asked for (inside a turned group, aimed, or keyed), the framing must hold the items with its margin,
and each is one undo step."""
import math

from rostrum_core import Document, Who

from rostrum3d import KIND, aim, run_source
from rostrum3d.ops_shot_camera import FILL
from rostrum3d.resolve import Frames

SAM = Who.person()
SRC = '''
mesh("box", shape="box", width=0.4, height=0.2, depth=0.3, x=0.5, y=0.1)
with group("rigged", ry=30, x=1):
    camera("cam", focalLength=50, z=4)
camera("aimed", y=1, z=3).aim((0, 0, 0))
camera("moving", z=5).key("z", {0: 5, 1: 6})
shot("hero", camera="cam", fps=24, start=0, end=1, width=1600, height=900)
shot("aim", camera="aimed", fps=24, start=0, end=1)
shot("move", camera="moving", fps=24, start=0, end=1)
'''


def doc():
    d = Document.new(KIND)
    d.run_script("s.py", run_source(SRC, "s.py"))
    return d


def seen(d, cam, t=0.0):
    """(eye, forward) of a camera in the world at `t`."""
    f = round(t * 1000)
    w = Frames(d.data, range(f, f + 1), 1000.0).world(cam, f)
    eye = aim.point(w, [0, 0, 0])
    fwd = [a - b for a, b in zip(aim.point(w, [0, 0, -1]), eye)]
    n = math.hypot(*fwd)
    return eye, [x / n for x in fwd]


def test_take_view_puts_the_camera_at_the_view_and_undoes_in_one_step():
    for shot, cam in (("hero", "cam"), ("aim", "aimed")):
        d = doc()
        before = seen(d, cam)
        d.apply({"op": "shot.take_view", "target": [shot],
                 "args": {"position": [2, 1.5, 3], "lookAt": [0, 0.5, 0], "focalLength": 35}}, SAM)
        eye, fwd = seen(d, cam)
        to = [0 - 2, 0.5 - 1.5, 0 - 3]
        n = math.hypot(*to)
        assert math.dist(eye, [2, 1.5, 3]) < 1e-5
        assert sum(a * b / n for a, b in zip(fwd, to)) > 0.99999
        assert d.item(cam)["focalLength"] == 35
        d.undo(SAM)
        assert math.dist(seen(d, cam)[0], before[0]) < 1e-9


def test_take_view_keys_a_moving_camera_at_the_time_given():
    d = doc()
    d.apply({"op": "shot.take_view", "target": ["move"],
             "args": {"position": [0, 1, 2], "lookAt": [0, 0, 0], "focalLength": 50, "at": 0.5}}, SAM)
    assert math.dist(seen(d, "moving", 0.5)[0], [0, 1, 2]) < 1e-5
    assert math.dist(seen(d, "moving", 1.0)[0], [0, 1, 6]) < 1e-5      # its other z key is kept (y has no keys)


def _framing(d, cam, w, h, focal=50):
    """(how far off the middle the box's middle is, the worst corner's share of the half frame) through `cam`."""
    inv = aim.invert(Frames(d.data, range(0, 1), 1000.0).world(cam, 0))
    tan_w = 36 / (2 * focal)
    tan_h = tan_w * h / w
    mx, my, mz = aim.point(inv, [0.5, 0.1, 0.0])
    worst = 0.0
    for c in [[(0.3, 0.7)[i & 1], (0.0, 0.2)[i >> 1 & 1], (-0.15, 0.15)[i >> 2 & 1]] for i in range(8)]:
        x, y, z = aim.point(inv, c)
        worst = max(worst, abs(x) / (-z * tan_w), abs(y) / (-z * tan_h))
    return math.hypot(mx / -mz, my / -mz), worst


def test_frame_keeps_the_direction_and_fills_the_frame_with_the_margin():
    for shot, cam, size in (("hero", "cam", (1600, 900)), ("aim", "aimed", (1920, 1080))):
        d = doc()
        eye0, fwd0 = seen(d, cam)
        d.apply({"op": "shot.frame", "target": [shot], "args": {"items": ["box"]}}, SAM)
        assert sum(a * b for a, b in zip(seen(d, cam)[1], fwd0)) > 0.99999          # the same direction
        off, worst = _framing(d, cam, *size)
        assert off < 1e-6 and abs(worst - FILL) < 1e-4        # in the middle, the tightest corner on the margin
        d.undo(SAM)
        assert math.dist(seen(d, cam)[0], eye0) < 1e-9
