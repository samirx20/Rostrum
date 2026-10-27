"""The Clay brush ring (clay_ring.py): what would break silently is the ring drawn somewhere else than where the brush
lands (its quick per-move sums drifting from the camera's own projection, or a cached view kept after the camera moved),
and Ctrl's mark saying the wrong thing ("−" while the stroke will add)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rostrum_core import Document  # noqa: E402
from rostrum3d import KIND  # noqa: E402
from rostrum3d.compile import describe, shot_info  # noqa: E402
from rostrum3d.script import run_source  # noqa: E402
from screen3d import clay_ring as R  # noqa: E402
from screen3d.gizmo import View  # noqa: E402

SRC = '''
head = clay("head", y=1.6, sx=2, sy=2, sz=2)
head.lump((0, 0, 0), 0.1)
camera("near", z=1, y=1.7, rx=-5)
shot("s", camera="near")
'''


def _scene():
    d = Document.new(KIND)
    d.run_script("s.py", run_source(SRC, "s.py"))
    info = shot_info(d.data, "s")
    return describe(d.data, "s"), info["start"]


def _slow(cam, scene, frame, point, normal, radius):
    """The ring as View.project gives it, point by point."""
    v = View.of(cam, scene, frame, cam["width"], cam["height"])
    n = R._norm(normal)
    a = R._norm(R._cross(n, [0.0, 1.0, 0.0]))
    b = R._cross(n, a)
    out = []
    for c, s in R._TURN:
        q = v.project([point[k] + (a[k] * c + b[k] * s) * radius for k in range(3)])
        out.append([q[0] / v.w, q[1] / v.h])
    return out


def test_ring_lands_where_the_camera_projects_it_and_follows_the_camera():
    scene, frame = _scene()
    point, normal = [0.02, 1.62, 0.18], [0.2, 0.3, 1.0]
    rg = R.Ringer()
    for cam in ({"camera": "near", "frame": frame, "width": 1300, "height": 850},
                {"eye": [0.6, 1.9, 1.1], "target": [0, 1.6, 0], "fov": 40, "frame": frame, "width": 900, "height": 900},
                {"eye": [-0.4, 1.5, 0.9], "target": [0, 1.6, 0], "fov": 30, "frame": frame, "width": 900, "height": 900}):
        got = rg.ring(cam, scene, frame, point, normal, "head", 0.03)
        want = _slow(cam, scene, frame, point, normal, 0.03 * 2)          # the clay's scale (2) makes it world size
        assert len(got) == R.RING_POINTS
        assert max(abs(g - w) for gp, wp in zip(got, want) for g, w in zip(gp, wp)) < 1e-9


def test_ctrl_mark_says_what_the_stroke_will_do():
    assert [R.mark(b, True, False) for b in ("add", "carve", "smooth", "pull", "flatten", "crease", "mask")] == \
        ["−", "+", "", "", "+", "+", "−"]
    assert R.mark("add", False, False) == "" and R.mark("carve", True, True) == ""      # no Ctrl / Shift's Smooth
    assert R.mark_of("add", "carve", False) == "−" and R.mark_of("mask", "mask", True) == "−"
    assert 0 < R.inner(0) < R.inner(0.5) < R.inner(1) < 1                               # harder edge: further out
