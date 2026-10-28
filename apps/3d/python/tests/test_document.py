"""The two things that would break silently: a script re-run keeping a person's edit, and the scene description
the C++ core reads (ENGINE_CONTRACT.md § 2: every field present, one value per frame)."""
import pytest
from rostrum_core import Document, Who
from rostrum_core.errors import RostrumError

from rostrum3d import KIND, run_source
from rostrum3d import fields as F
from rostrum3d.compile import DOCUMENT_ONLY, RESOLVED, describe

SAM = Who.person()
SRC = '''
alu = material("alu", baseColor="#c9ccd1", metallic=1, roughness=0.32)
with group("device", ry=-12) as device:
    mesh("body", shape="box", width=0.07, height=0.02, depth=0.1, bevel=0.004, material=alu)
device.key("ry", {0: -12, 2: 12})
light("key", kind="rect", width=0.7, height=0.45, intensity=7, x=0.4, y=0.5, z=0.6).aim(device)
cam = camera("cam", focalLength=100, z=0.4).aim((0, 0, 0))
cam.key("focalLength", {0: 100, 1: 120})
with import_usd("phone", file="C:/assets/phone.usdc", parts=["Body/Screen"]):
    pass
shot("hero", camera=cam, fps=24, start=0, end=2)
'''


def doc():
    d = Document.new(KIND)
    d.run_script("product.py", run_source(SRC, "product.py"))
    return d


def test_rerun_keeps_a_persons_moved_light():
    d = doc()
    d.apply({"op": "light.set", "target": ["key"], "args": {"x": -0.5, "y": 0.8}}, SAM)
    report = d.run_script("product.py", run_source(SRC.replace("intensity=7, x=0.4", "intensity=9, x=0.3"), "product.py"))
    key = d.item("key")
    assert (key["x"], key["y"], key["intensity"]) == (-0.5, 0.8, 9)      # person's move kept, script's change applied
    assert [h["key"] for h in report.held] == ["key.x"]                  # ... and the agent is told


def test_a_taken_id_is_refused_naming_what_holds_it():
    for op, taken, kind in (("mesh.add", "key", "light"), ("shot.add", "alu", "material"), ("material.add", "cam", "camera")):
        with pytest.raises(RostrumError, match=f'id "{taken}" is already used by a {kind}'):
            doc().apply({"op": op, "args": {"id": taken}}, SAM)


def _check_node(node, n_frames):
    type_ = node["type"]
    want = {p.name for p in F.FIELDS[type_]} - RESOLVED | ({"parts"} if type_ == "import" else set())
    want -= {"turn"} if type_ == "light" else set()                          # a dome's turn is sent as its ry
    want -= DOCUMENT_ONLY if type_ == "mesh" else set()                      # words, fonts, files: compiled to the outline
    want -= {"guide"} if type_ == "mesh" and not node["props"].get("guide") else set()   # sent only when on
    assert set(node["props"]) == want, node["id"]
    assert all(len(v) == n_frames for v in node.get("anim", {}).values()), node["id"]
    for child in node.get("children", []):
        _check_node(child, n_frames)


def test_motion_blur_reaches_the_scene():
    """The shot's shutter (degrees) reaches the core as frames, or 0 when off: nothing else shows it is lost."""
    d = doc()
    shot = d.data["shots"][0]
    shot.update(motionBlur=True, shutter=90.0)
    assert describe(d.data, "hero")["shot"]["shutter"] == 0.25
    shot["motionBlur"] = False
    assert describe(d.data, "hero")["shot"]["shutter"] == 0.0


def test_describe_meets_the_contract():
    scene = describe(doc().data, "hero")
    assert scene["shot"] == {"id": "hero", "fps": 24, "start": 0, "end": 47, "shutter": 0.0}
    for node in scene["items"]:
        _check_node(node, 48)
    by_id = {n["id"]: n for n in scene["items"]}
    assert set(by_id["device"]["anim"]) == {"ry"} and set(by_id["cam"]["anim"]) == {"focalLength"}
    assert set(by_id["key"]["props"]) >= {"rx", "ry"} and abs(by_id["key"]["props"]["ry"] - 33.690068) < 1e-4
    assert scene["materials"][0]["props"]["baseColor"][0] < 0.6                     # linear, not sRGB 0.79
    assert by_id["phone"]["props"]["parts"] == [{"path": "Body/Screen", "material": "", "visible": True}]


def test_pivot_stays_put_while_turning():
    """Position is where the pivot stands: turning and scaling around it never moves that point (compile.pivoted)."""
    from rostrum3d import aim
    from rostrum3d.compile import pivoted
    v = {"x": 1.0, "y": 2.0, "z": 3.0, "rx": 30.0, "ry": 45.0, "rz": 10.0, "sx": 2.0, "sy": 1.0, "sz": 0.5,
         "px": 0.1, "py": -0.2, "pz": 0.3}
    origin = pivoted(v)
    world = aim.local({**v, "x": origin[0], "y": origin[1], "z": origin[2]})
    assert [round(c, 9) for c in aim.point(world, [0.1, -0.2, 0.3])] == [1.0, 2.0, 3.0]
