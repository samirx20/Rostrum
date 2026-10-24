# Smooth surface check (brief 8): a box made editable, then Smooth surface 2 (a pebble), then the same with its top
# edges kept sharp and its top face in another material. Through the lock:
#   heavy.ps1 run "<team>: smooth check" gpu <venv python> apps\3d\tools\smooth_check.py <out> [cycles]
# Saves smooth-off.png, smooth-2.png, smooth-2-sharp.png (Storm, or Cycles with `cycles`) at 1646×900.
import sys
from pathlib import Path

WT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(WT / "apps" / "3d" / "python"), str(WT / "shared" / "core")]
from rostrum_core import Document, Who                       # noqa: E402
from rostrum3d import KIND, ops_mesh, run_source             # noqa: E402
from rostrum3d.compile import describe                       # noqa: E402
from rostrum3d.engine import Engine                          # noqa: E402

SCENE = '''
clay = material("clay", baseColor="#c9b8a6", roughness=0.55)
red = material("red", baseColor="#c23a2b", roughness=0.4)
ground = material("ground", baseColor="#3a3d42", roughness=0.8)
mesh("pebble", shape="box", width=0.1, height=0.06, depth=0.08, y=0.03, material=clay)
mesh("floor", shape="plane", width=3, depth=3, material=ground)
light("key", kind="rect", width=0.5, height=0.5, intensity=30, x=-0.3, y=0.5, z=0.4, rx=-50, ry=-30)
light("fill", kind="dome", intensity=0.35)
cam = camera("cam", focalLength=70, x=0.18, y=0.17, z=0.3).aim((0, 0.03, 0))
shot("hero", camera=cam, fps=24, start=0, end=1)
'''


def top_edges(item):
    """The point pairs around the box's top face (the highest y)."""
    pts = item["points"]
    top = max(p[1] for p in pts)
    ids = [i for i, p in enumerate(pts) if abs(p[1] - top) < 1e-6]
    k, face = 0, None
    for n in item["faceCounts"]:
        f = item["faceIndices"][k:k + n]; k += n
        if set(f) == set(ids):
            face = f
    return [v for i in range(len(face)) for v in (face[i], face[(i + 1) % len(face)])], face


if __name__ == "__main__":
    out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
    renderer = "cycles" if "cycles" in sys.argv[2:] else "storm"
    doc = Document.new(KIND)
    doc.run_script("s.py", run_source(SCENE, "s.py"))
    with Engine() as eng:
        ops_mesh.use_engine(eng)

        def run(op, args):
            doc.apply([{"op": op, "target": ["pebble"], "args": args}], Who.person())
        run("mesh.edit", {})

        def shoot(name):
            eng.load(describe(doc.data, "hero"))
            eng.render(camera="cam", renderer=renderer, frame=0, width=1646, height=900, samples=64, denoise=True,
                       png=str(out / f"{name}.png"))
        shoot("smooth-off")
        run("mesh.set", {"subdivide": 2})
        shoot("smooth-2")
        item = doc.item("pebble")
        creases, face = top_edges(item)
        k, n_face, top_index = 0, 0, None
        for n in item["faceCounts"]:
            if item["faceIndices"][k:k + n] == face:
                top_index = n_face
            k += n; n_face += 1
        mats = [""] * len(item["faceCounts"]); mats[top_index] = "red"
        run("mesh.set", {"creases": creases, "faceMaterials": mats})
        shoot("smooth-2-sharp")
        ops_mesh.use_engine(None)
    print("saved", sorted(p.name for p in out.glob("*.png")))
