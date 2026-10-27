# CL6 pictures (3d-cl6), by the agent path (document operations + the engine, what the MCP tools do), no window:
#   skin-ear.png   a clay head with thin ears, a light behind it facing the camera: Clay vs Skin, Quick and Final
#                  (Skin's thin ears should glow red in Final, the head solid with no block seams (the Cycles
#                  whole, clay_whole.h); Quick only warms its colour)
#   starts.png     the four clay starts (Clay, Skin, Wax / soap, Stone) on the same lump, Final, lit from the side
# The lead runs it:  heavy.ps1 run "sam: cl6 shots" gpu <venv python> apps\3d\tools\cl6_skin_shots.py <out folder>
import sys
import tempfile
from pathlib import Path

WT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(WT / "apps" / "3d" / "app"))
import main  # noqa: E402,F401  (this checkout's code and engine first)
from rostrum_core import Document, Who  # noqa: E402
from rostrum3d import KIND  # noqa: E402
from rostrum3d.compile import describe  # noqa: E402
from rostrum3d.engine import Engine  # noqa: E402
from rostrum3d.script import run_source  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from clay_paint_shots import H, W, quick, strip  # noqa: E402
import clay_paint_shots as CPS  # noqa: E402

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(r"C:\Users\Sam\.rostrum\waves\results\3d-cl6\pictures")
CPS.OUT = OUT
WHO = Who.person()
SCENE = '''
grey = material("grey", baseColor="#5a5a5a", roughness=0.8)
mesh("ground", shape="plane", width=3, depth=3, material=grey)
light("back", kind="rect", width=0.25, height=0.25, intensity=60, x=0.0, y=0.12, z=-0.35).aim((0, 0.12, 0.3))
light("front", kind="rect", width=0.6, height=0.4, intensity=3, x=-0.5, y=0.5, z=0.8).aim((0, 0.1, 0))
light("sky", kind="dome", color="#c8d2e0", intensity=0.15)
cam = camera("cam", focalLength=85, y=0.13, z=0.6).aim((0, 0.12, 0))
shot("hero", camera=cam, fps=24, start=0, end=1)
'''


def final(eng, name):
    return CPS.final(eng, name)


def head(doc):
    """A clay head (11 cm) with a thin ear each side, about 4-5 mm thick like a real ear: a flat oval drawn facing the
    camera and puffed a little (Mirror X makes the second), its root inside the head. Real-size, so Skin's 3.7 mm
    reads as it would on a real head: the ears glow red against the back light, the head itself stays solid."""
    import math
    doc.apply([{"op": "clay.add", "args": {"id": "head", "at": [0, 0.12, 0], "radius": 0.055, "symmetry": "x"}}], WHO)
    doc.apply([{"op": "clay.set", "target": ["head"], "args": {"detailMode": "fixed", "detail": 0.0007}}], WHO)
    oval = [[0.062 + 0.017 * math.cos(a), 0.004 + 0.024 * math.sin(a), -0.01]
            for a in (2 * math.pi * k / 20 for k in range(20))]
    doc.apply([{"op": "clay.draw", "target": ["head"], "args": {"outline": oval, "facing": [0, 0, 1], "puff": 0.14,
                                                                "blend": 0.004, "name": "ear"}}], WHO)


def main_():
    OUT.mkdir(parents=True, exist_ok=True)
    folder = Path(tempfile.mkdtemp(prefix="rostrum-cl6-"))
    doc = Document.new(KIND, folder=folder, item="scene")
    doc.run_script("scene.py", run_source(SCENE, "scene.py"))
    head(doc)
    doc.apply([{"op": "material.from", "args": {"start": "skin", "id": "skin", "baseColor": "#d9a58c"}},
               {"op": "material.from", "args": {"start": "clay", "id": "clayc", "baseColor": "#d9a58c"}}], WHO)
    pics, labels = [], []
    with Engine() as eng:
        for mat in ("clayc", "skin"):
            doc.apply([{"op": "material.assign", "target": ["head"], "args": {"material": mat}}], WHO)
            doc.save()
            eng.ensure_scene(describe(doc.data, "hero", folder))
            pics += [quick(eng), final(eng, mat)]
            word = "Clay" if mat == "clayc" else "Skin"
            labels += [f"{word}: Quick", f"{word}: Final"]
        strip(pics, labels, OUT / "skin-ear.png")
        print("wrote", OUT / "skin-ear.png", flush=True)


if __name__ == "__main__":
    main_()
