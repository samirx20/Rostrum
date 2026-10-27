# The 3D leftovers (copies + imports) checked against the built core, pictures and numbers into <out folder>:
#   gltf   - CesiumMan.glb / BoxAnimated.glb (Khronos samples, CC-BY 4.0, not in the repo): inspect_usd says animated, and
#            three Quick frames show it move (gltf-<name>-f<frame>.png)
#   save   - a plain save (no flatten) of a scene with a glTF import writes <name>_imports\ beside it, and the saved
#            file opens again on its own (inspect_usd lists the import's meshes)
#   frame  - shot.frame on a copies item frames all its copies (the core's copies_box)
#   clay   - copies scattered on a clay: the scene builds and every copy is laid out
#   colour - Change near colour, Quick (and with --final the Final look) of a row of red copies turned yellow near a ball
# Through the lock (the Final look loads the GPU):
#   heavy.ps1 run "<team>: leftovers check" gpu <python> apps\3d\tools\leftovers_check.py <out> <glb folder> [--final]
import sys
from pathlib import Path

WT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(WT / "apps" / "3d" / "python"), str(WT / "shared" / "core")]
from rostrum_core import Document, Who                       # noqa: E402
from rostrum3d import KIND, item_bounds, ops_mesh, run_source  # noqa: E402
from rostrum3d.compile import describe                       # noqa: E402
from rostrum3d.engine import Engine                          # noqa: E402

OUT, GLB, FINAL = Path(sys.argv[1]), Path(sys.argv[2]), "--final" in sys.argv
LIGHTS = '''
light("sky", kind="dome", color="#ffffff", intensity=1)
light("key", kind="distant", intensity=2, angle=2).aim((0, -1, -0.6))
'''
FAILED = []


def check(ok: bool, what: str):
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        FAILED.append(what)


def doc_of(src: str) -> Document:
    d = Document.new(KIND)
    d.run_script("s.py", run_source(LIGHTS + src, "s.py"))
    return d


def quick(eng: Engine, d: Document, png: Path, frame: int = 0, renderer: str = "storm"):
    eng.ensure_scene(describe(d.data, "hero", OUT))
    eng.render(camera="cam", renderer=renderer, frame=frame, width=960, height=540, samples=64, png=str(png))
    print("wrote", png)


def gltf(eng: Engine):
    for name in ("CesiumMan", "BoxAnimated"):
        f = GLB / f"{name}.glb"
        info = eng.inspect_usd(f)
        check(info.get("animated") and info["endFrame"] > info["startFrame"],
              f"{name}: animated, frames {info.get('startFrame')}..{info.get('endFrame')} at {info.get('framesPerSecond')}")
        d = doc_of(f'''import_usd("model", file=r"{f.as_posix()}")
camera("cam", y=0.8, z=3.2).aim((0, 0.7, 0))
shot("hero", camera="cam", fps=24, start=0, end=2)''')
        for frame in (0, 12, 24):
            quick(eng, d, OUT / f"gltf-{name}-f{frame}.png", frame)


def save(eng: Engine):
    f = GLB / "CesiumMan.glb"
    d = doc_of(f'''import_usd("model", file=r"{f.as_posix()}")
camera("cam", z=3)
shot("hero", camera="cam", fps=24, start=0, end=1)''')
    eng.ensure_scene(describe(d.data, "hero", OUT))
    saved = OUT / "save-plain" / "scene.usda"
    saved.parent.mkdir(parents=True, exist_ok=True)
    eng.save(saved)
    kept = list((saved.parent / "scene_imports").glob("*.usdc"))
    check(len(kept) == 1, f"plain save wrote the import beside it: {[k.name for k in kept]}")
    back = eng.inspect_usd(saved)
    meshes = [p["path"] for p in back.get("prims", []) if p.get("type") == "Mesh"]
    check(bool(meshes), f"the saved file opens on its own with the import's meshes ({len(meshes)})")


def frame(eng: Engine):
    d = doc_of('''bud = mesh("bud", shape="sphere", radius=0.1)
copies("buds", bud, layout="line", count=6, spacingX=0.5)
camera("cam", z=3)
shot("hero", camera="cam", fps=24, start=0, end=1)''')
    ops_mesh.use_engine(eng, OUT)
    try:
        lo, hi = item_bounds.world_box(d.data, ["buds"])
    finally:
        ops_mesh.use_engine(None)
    check(abs((hi[0] - lo[0]) - 2.7) < 0.02 and abs((hi[1] - lo[1]) - 0.2) < 0.02,
          f"the copies' box: {lo} .. {hi} (6 buds of 0.2 m, 0.5 m apart: 2.7 m wide)")


def clay(eng: Engine):
    d = doc_of('''clay("hill", spin=[[0, 0, 0], [0.8, 0, 0], [0.6, 0.3, 0], [0, 0.45, 0]], axis=[[0, 0, 0], [0, 1, 0]])
peb = mesh("peb", shape="sphere", radius=0.03, x=3)
copies("pebbles", peb, layout="surface", surface="hill", count=40, onlySeen=False)
camera("cam", y=1.2, z=2.2).aim((0, 0.2, 0))
shot("hero", camera="cam", fps=24, start=0, end=1)''')
    eng.ensure_scene(describe(d.data, "hero", OUT))
    n = (eng.copies or {}).get("pebbles", {}).get("count")
    check(n == 40, f"copies scattered on a clay: {n} of 40 laid out")
    quick(eng, d, OUT / "clay-scatter.png")


def colour(eng: Engine):
    d = doc_of('''red = material("red", baseColor="#c03020", roughness=0.5)
bud = mesh("bud", shape="sphere", radius=0.12, material=red)
ball = mesh("ball", shape="sphere", radius=0.05, y=0.6)
with copies("buds", bud, layout="line", count=9, spacingX=0.32, x=-1.28) as c:
    c.effector(kind="colour", near="ball", radius=0.9, amount=1, colour="#ffd000")
camera("cam", y=0.4, z=2.6).aim((0, 0, 0))
shot("hero", camera="cam", fps=24, start=0, end=1)''')
    quick(eng, d, OUT / "colour-quick.png")
    if FINAL:
        quick(eng, d, OUT / "colour-final.png", renderer="cycles")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with Engine() as eng:
        for step in (gltf, save, frame, clay, colour):
            try:
                step(eng)
            except Exception as e:                           # one step's failure is named, the rest still run
                check(False, f"{step.__name__}: {e}")
    print("FAILED:" if FAILED else "all passed", *FAILED, sep="\n  ")
    sys.exit(1 if FAILED else 0)


main()
