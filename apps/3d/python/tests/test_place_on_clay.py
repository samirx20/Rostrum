"""A part placed on a clay (SPEC §1 at 3:40 and 5:00): what breaks silently is an eye sized for the whole body instead
of the face, a click off the middle that gets no mirrored copy, and parts left floating when the clay is posed."""
import math

from rostrum_core import Document, Who

from rostrum3d import KIND, aim, ops_pose, run_source, skin, surface_place as SP
from rostrum3d.compile import _Frames
from rostrum3d.follow import nearest_bone
from test_pose import pear

SAM = Who.person()


def _pear_outline(n=48):
    """A drawn pear facing +Z: a belly up to 0.44 m wide, a narrower head on top, 0.7 m tall."""
    out = []
    for i in range(n):
        a = 2 * math.pi * i / n
        y = 0.35 - 0.35 * math.cos(a)
        half = 0.22 * math.sin(a) * (1 - 0.45 * (y / 0.7) ** 2) if y < 0.45 else 0.12 * math.sin(a)
        out.append([half, y])
    return out


def test_a_part_on_a_face_is_sized_for_the_face_and_gets_its_pair():
    clay = {"id": "c", "type": "clay", "symmetry": "x",
            "steps": [{"id": "body", "shape": "outline", "plane": [0, 0, 0, 1, 0, 0, 0, 1, 0], "outline": _pear_outline()}]}
    world = aim.local({"x": 0.0, "y": 0.0, "z": 0.0, "rx": 0, "ry": 0, "rz": 0, "sx": 1, "sy": 1, "sz": 1})
    face = [0.04, 0.6, 0.1]                                               # on the head, a bit off the middle
    eye = SP.part_size(clay, world, face)
    head = 2 * 0.12 * math.sin(math.acos((0.35 - face[1]) / 0.35))       # the head's width there
    assert eye and head / 7 <= eye <= head / 5                            # about a sixth of the head across
    belly = SP.part_size(clay, world, [0.0, 0.3, 0.15])
    assert belly > eye * 1.5                                              # the belly is wider: a bigger part there
    assert SP.mirrors(clay, world, face, eye)                             # 4 cm off the middle: a pair
    assert not SP.mirrors(clay, world, [eye / 4, 0.6, 0.1], eye)          # on the middle (a nose): one
    assert SP.part_size({"id": "floor", "type": "mesh", "shape": "plane"}, world, [0, 0, 0]) is None   # not a clay


def test_a_part_on_a_clay_moves_with_its_bone_and_its_copy_with_its_own_side(tmp_path):
    d = Document.new(KIND, folder=tmp_path, item="scene")
    d.run_script("t.py", run_source('''
c = clay("c", symmetry="x")
band = mesh("band", shape="sphere", radius=0.02).place_on("c", at=(0.45, 0.6, 0.05), normal=(0, 0, 1))
cam = camera("cam", z=3, y=0.4)
shot("s", camera=cam, fps=2, start=0, end=1.0)
''', "t.py"))
    assert d.item("band")["follow"] == "c" and d.item("band")["followPose"] and d.has("band_mirrored")
    d.apply({"op": "clay.shape", "target": ["c"], "args": {"shape": "sphere", "at": [0, 0.3, 0], "radius": 0.3}}, SAM)
    ops_pose.use_grid(lambda doc, id_, cells: pear(cells))
    try:
        d.apply({"op": "pose.find_joints", "target": ["c"]}, SAM)
        before = [aim.point(_Frames(d.data, range(0, 3), 2).world(i, 2), [0, 0, 0]) for i in ("band", "band_mirrored")]
        d.apply({"op": "pose.drag", "target": ["c"], "args": {"part": "forearm.L", "to": [0.5, 0.95, 0.1],
                                                               "holds": ["foot.L", "foot.R"], "at": 1.0}}, SAM)
    finally:
        ops_pose.use_grid(None)
    fr = _Frames(d.data, range(0, 3), 2)
    band, copy = (aim.point(fr.world(i, 2), [0, 0, 0]) for i in ("band", "band_mirrored"))
    assert math.dist(band, before[0]) > 0.05                              # the left arm went up: the band with it
    chain = skin.bones_of(d.item("c"))                                    # each on its own side's bone, as the core
    for spot, now_at, side in ((before[0], band, "L"), (before[1], copy, "R")):   # bends the clay (it stands at 0)
        i = nearest_bone(d.item("c"), spot)
        assert chain[i][0]["joint"] in (f"arm.{side}", f"forearm.{side}")
        move = aim.compose(skin.transforms(chain, 1.0, [])[i], aim.invert(skin.transforms(chain)[i]))
        assert math.dist(now_at, aim.point(move, spot)) < 1e-6
    d.undo(SAM)
    assert math.dist(aim.point(_Frames(d.data, range(0, 3), 2).world("band", 2), [0, 0, 0]), before[0]) < 1e-6
