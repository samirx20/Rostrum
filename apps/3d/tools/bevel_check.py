# Bevel check (H22): are an extruded outline's normals right across its bevel? Through the lock:
#   heavy.ps1 run "<team>: bevel check" gpu <worktree>\.venv\Scripts\python.exe apps\3d\tools\bevel_check.py <out> [render]
# Saves the scene as .usda and measures, for every bevel and side face, the angle between each corner's normal and the
# face's own (geometric) normal: a smooth surface sampled finely keeps that small (about half a step's turn). Big angles
# are the kind of fault that shades as a dark, jagged rim. With `render`: a Cycles close-up (bevel-closeup.png) and the
# whole logo and word (bevel-wide.png).
import json, re, sys
from pathlib import Path

WT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(WT / "apps" / "3d" / "python"), str(WT / "shared" / "core")]
import numpy as np                                           # noqa: E402
from rostrum_core import Document                            # noqa: E402
from rostrum3d import KIND, run_source                       # noqa: E402
from rostrum3d.compile import describe                       # noqa: E402
from rostrum3d.engine import Engine                          # noqa: E402

RING = "M 0 -50 A 50 50 0 1 1 -0.01 -50 Z M 0 -34 A 34 34 0 1 0 0.01 -34 Z"
SCENE = f'''
copper = material("copper", baseColor="#e8a878", metallic=1, roughness=0.18)
wall = material("wall", baseColor="#202226", roughness=0.6)
mesh("word", shape="text", text="Rostrum", font="Inter", weight=700, size=0.1, depth=0.02, bevel=0.0018, x=0.17, material=copper)
mesh("ring", shape="svg", pathData="{RING}", svgWidth=0.08, depth=0.02, bevel=0.003, x=-0.13, y=0.035, material=copper)
mesh("back", shape="plane", width=2, depth=2, z=-0.05, rx=90, material=wall)
light("key", kind="rect", width=0.6, height=0.15, intensity=40, x=-0.2, y=0.4, z=0.5, rx=-35)
light("fill", kind="dome", intensity=0.15)
cam = camera("cam", focalLength=85, x=-0.06, y=0.03, z=0.55).aim((-0.06, 0.03, 0))
camera("wide", focalLength=50, x=0.1, y=0.03, z=0.9).aim((0.1, 0.03, 0))
shot("hero", camera=cam, fps=24, start=0, end=1)
'''


def floats(block: str) -> np.ndarray:
    return np.array([float(x) for x in re.findall(r"-?\d+(?:\.\d+)?(?:e-?\d+)?", block)])


def mesh_arrays(usda: str, name: str) -> dict:
    """points / normals / counts / indices of the mesh prim `name` in a saved .usda (no USD Python needed)."""
    m = re.search(r'def Mesh "' + name + r'"(.*?)\n    }', usda, re.S) or re.search(r'def Mesh "' + name + r'"(.*)', usda, re.S)
    body = m.group(1)
    get = lambda key: re.search(key + r"\s*=\s*\[(.*?)\]", body, re.S).group(1)  # noqa: E731
    return {"points": floats(get(r"point3f\[\] points")).reshape(-1, 3),
            "normals": floats(get(r"normal3f\[\] normals")).reshape(-1, 3),
            "counts": floats(get(r"int\[\] faceVertexCounts")).astype(int),
            "indices": floats(get(r"int\[\] faceVertexIndices")).astype(int)}


def worst_angles(m: dict) -> dict:
    """Per face with 4 corners (bevel and side bands): the angle between each corner normal and the face normal."""
    out, k = [], 0
    for c in m["counts"]:
        idx = m["indices"][k:k + c]; k += c
        if c != 4:
            continue
        p = m["points"][idx]
        fn = np.cross(p[2] - p[0], p[3] - p[1])
        if np.linalg.norm(fn) < 1e-14:
            continue
        fn /= np.linalg.norm(fn)
        cos = np.clip(m["normals"][idx] @ fn, -1, 1)
        out.append(np.degrees(np.arccos(cos)).max())
    a = np.array(out)
    return {"faces": int(a.size), "median_deg": float(np.median(a)), "p99_deg": float(np.percentile(a, 99)),
            "max_deg": float(a.max()), "over_20deg": int((a > 20).sum())}


if __name__ == "__main__":
    out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
    doc = Document.new(KIND)
    doc.run_script("s.py", run_source(SCENE, "s.py"))
    with Engine() as eng:
        eng.load(describe(doc.data, "hero"))
        eng.save(out / "bevel.usda")
        usda = (out / "bevel.usda").read_text(encoding="utf-8")
        report = {n: worst_angles(mesh_arrays(usda, n)) for n in ("word", "ring")}
        print(json.dumps(report, indent=1))
        (out / "bevel-normals.json").write_text(json.dumps(report, indent=1))
        if "render" in sys.argv[2:]:
            eng.render(camera="cam", renderer="cycles", frame=0, width=1600, height=900, samples=256, denoise=True,
                       png=str(out / "bevel-closeup.png"))
            eng.render(camera="wide", renderer="cycles", frame=0, width=1600, height=900, samples=256, denoise=True,
                       png=str(out / "bevel-wide.png"))
