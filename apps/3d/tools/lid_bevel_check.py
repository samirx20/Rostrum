# Lid bevel check (brief 8): the lid made editable, its top edge loop bevelled 2 mm with 4 segments. Through the lock:
#   heavy.ps1 run "<team>: lid bevel check" gpu <venv python> apps\3d\tools\lid_bevel_check.py <out>
# Saves lid-bevel-4.png (Storm, 1646×900).
import sys
from pathlib import Path

WT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(WT / "apps" / "3d" / "python"), str(WT / "shared" / "core")]
from rostrum_core import Document, Who                       # noqa: E402
from rostrum3d import KIND, ops_mesh, run_source             # noqa: E402
from rostrum3d.compile import describe                       # noqa: E402
from rostrum3d.engine import Engine                          # noqa: E402
from rostrum3d.mesh_select import parse                      # noqa: E402
from rostrum3d.poly import faces_of                          # noqa: E402

SCENE = '''
plastic = material("plastic", baseColor="#d9dde3", roughness=0.35)
mesh("lid", shape="box", width=0.064, height=0.01, depth=0.048, y=0.005, material=plastic)
light("key", kind="rect", width=0.4, height=0.4, intensity=30, x=-0.25, y=0.4, z=0.3, rx=-55, ry=-35)
light("fill", kind="dome", intensity=0.35)
cam = camera("cam", focalLength=85, x=0.06, y=0.07, z=0.11).aim((0.012, 0.006, 0.0))
shot("hero", camera=cam, fps=24, start=0, end=1)
'''

if __name__ == "__main__":
    out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
    doc = Document.new(KIND)
    doc.run_script("s.py", run_source(SCENE, "s.py"))
    with Engine() as eng:
        ops_mesh.use_engine(eng)
        doc.apply([{"op": "mesh.edit", "target": ["lid"], "args": {}}], Who.person())
        lid = doc.item("lid")
        (top,) = parse("top", lid)[1]
        f = faces_of(lid)[top]
        loop = "edges " + " ".join(f"{min(a, b)}-{max(a, b)}" for a, b in zip(f, f[1:] + f[:1]))
        doc.apply([{"op": "edges.bevel", "target": ["lid"], "args": {"edges": loop, "width": 0.002, "segments": 4}}],
                  Who.person())
        eng.load(describe(doc.data, "hero"))
        eng.render(camera="cam", renderer="storm", frame=0, width=1646, height=900, png=str(out / "lid-bevel-4.png"))
        ops_mesh.use_engine(None)
    print("faces", len(doc.item("lid")["faceCounts"]))
