# Quick view against Cycles (H20): contact shading and depth of field, side by side. Through the lock:
#   heavy.ps1 run "<team>: quick vs cycles" gpu <worktree>\.venv\Scripts\python.exe apps\3d\tools\quick_vs_cycles.py <out folder>
# ao-storm-vs-cycles.png: a rough grey ball and a box on a grey floor under an even white sky, nothing else (H19's
#   "see-through ball"): the quick view without and with contact shading, then Cycles.
# dof-storm-vs-cycles.png: three balls at different distances through a wide-open lens focused on the middle one:
#   the quick view without and with depth of field, then Cycles.
import sys
from pathlib import Path

WT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(WT / "apps" / "3d" / "python"), str(WT / "shared" / "core")]
import numpy as np                                           # noqa: E402
from PIL import Image, ImageDraw, ImageFont                  # noqa: E402
from rostrum_core import Document                            # noqa: E402
from rostrum3d import KIND, run_source                       # noqa: E402
from rostrum3d.compile import describe                       # noqa: E402
from rostrum3d.engine import Engine                          # noqa: E402

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else None
W, H = 640, 360
AO = '''
grey = material("grey", baseColor="#9a9a9a", roughness=0.8)
mesh("floor", shape="plane", width=8, depth=8, material=grey)
mesh("ball", shape="sphere", radius=0.25, x=-0.35, y=0.25, material=grey)
mesh("box", shape="box", width=0.4, height=0.4, depth=0.4, x=0.4, y=0.2, z=-0.1, material=grey)
light("sky", kind="dome", color="#ffffff", intensity=1)
cam = camera("cam", focalLength=40, y=0.9, z=2.4).aim((0, 0.2, 0))
shot("hero", camera=cam, fps=24, start=0, end=1)
'''
DOF = '''
grey = material("grey", baseColor="#9a9a9a", roughness=0.8)
red = material("red", baseColor="#c0503c", roughness=0.4)
mesh("floor", shape="plane", width=12, depth=12, material=grey)
mesh("near", shape="sphere", radius=0.2, x=-0.5, y=0.2, z=1.2, material=red)
mesh("mid", shape="sphere", radius=0.2, x=0.0, y=0.2, z=0.0, material=red)
mesh("far", shape="sphere", radius=0.2, x=0.6, y=0.2, z=-2.0, material=red)
light("sky", kind="dome", color="#ffffff", intensity=1)
light("key", kind="distant", intensity=2, angle=2).aim((0, -1, -0.6))
cam = camera("cam", focalLength=50, dof=True, fStop=1.4, focusDistance=2.6, y=0.6, z=2.5).aim((0, 0.2, 0))
shot("hero", camera=cam, fps=24, start=0, end=1)
'''


def scene(src):
    doc = Document.new(KIND)
    doc.run_script("s.py", run_source(src, "s.py"))
    return describe(doc.data, "hero")


def view(eng, **req):
    v, w, h, stride, _ = eng.view(camera="cam", frame=0, width=W, height=H, renderer="storm", **req)
    try:
        px = np.frombuffer(v, np.uint8).reshape(h, stride)[:, :w * 4].reshape(h, w, 4).copy()
    finally:
        v.release()
    return Image.fromarray(px).convert("RGB")


def strip(pictures, labels, file):
    font = ImageFont.load_default(size=18)
    out = Image.new("RGB", (W * len(pictures), H + 30), "white")
    d = ImageDraw.Draw(out)
    for i, (p, t) in enumerate(zip(pictures, labels)):
        out.paste(p, (i * W, 30))
        d.text((i * W + 8, 5), t, fill="black", font=font)
    out.save(file)
    print("wrote", file)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with Engine() as eng:
        for name, src, off, on, labels in [
            ("ao", AO, {"ao": 0, "dof": False}, {"ao": 1, "dof": False},
             ["Quick view, no contact shading", "Quick view, contact shading 1", "Cycles (final)"]),
            ("dof", DOF, {"ao": 1, "dof": False}, {"ao": 1, "dof": True},
             ["Quick view, no depth of field", "Quick view, depth of field", "Cycles (final)"])]:
            eng.load(scene(src))
            png = OUT / f"{name}-cycles.png"
            eng.render(camera="cam", renderer="cycles", frame=0, width=W, height=H, samples=128, png=str(png))
            strip([view(eng, **off), view(eng, **on), Image.open(png).convert("RGB")], labels,
                  OUT / f"{name}-storm-vs-cycles.png")


if __name__ == "__main__":
    main()
