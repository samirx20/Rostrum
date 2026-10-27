# CL4 pictures (3d-cl4), by the agent path (document operations + the engine, what the MCP tools do), no window:
#   quick-vs-final.png      a sculpted clay, Quick (Storm) and Final (Cycles) side by side: the same clay
#   stripe-before-after.png a red stripe painted across the clay, then a lump added under it: Quick and Final, before
#                           and after (the stripe follows the surface)
#   relief.png              a Relief layer of wrinkle lines: Final without it and with it
# The lead runs it:  heavy.ps1 run "sam: cl4 shots" gpu <venv python> apps\3d\tools\clay_paint_shots.py <out folder>
import json
import math
import sys
import tempfile
import time
from pathlib import Path

WT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(WT / "apps" / "3d" / "app"))
import main  # noqa: E402,F401  (this checkout's code and engine first)
import numpy as np  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402
from rostrum_core import Document, Who  # noqa: E402
from rostrum3d import KIND  # noqa: E402
from rostrum3d.compile import describe  # noqa: E402
from rostrum3d.engine import Engine  # noqa: E402
from rostrum3d.script import run_source  # noqa: E402

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(r"C:\Users\Sam\.rostrum\waves\results\3d-cl4\pictures")
W, H = 560, 420
AGENT = Who.agent("cl4-shots") if hasattr(Who, "agent") else Who.person()
SCENE = '''
grey = material("grey", baseColor="#9a9a9a", roughness=0.7)
clayc = material("clayc", baseColor="#c9b8a6", roughness=0.55)
mesh("ground", shape="plane", width=3, depth=3, material=grey)
light("key", kind="rect", width=0.6, height=0.4, intensity=30, x=-0.5, y=0.7, z=0.6).aim((0, 0.1, 0))
light("sky", kind="dome", color="#c8d2e0", intensity=0.5)
cam = camera("cam", focalLength=50, y=0.14, z=0.55).aim((0, 0.1, 0))
shot("hero", camera=cam, fps=24, start=0, end=1)
'''
REPORT = {"steps": []}


def note(what, **kw):
    REPORT["steps"].append({"what": what, **kw})
    print(what, json.dumps(kw)[:300], flush=True)


def call(doc, calls):
    doc.apply(calls, AGENT)


def send(eng, doc, folder):
    t = time.perf_counter()
    eng.ensure_scene(describe(doc.data, "hero", folder))
    return round((time.perf_counter() - t) * 1000)


def quick(eng):
    v, w, h, stride, _ = eng.view(camera="cam", frame=0, width=W, height=H, renderer="storm")
    try:
        px = np.frombuffer(v, np.uint8).reshape(h, stride)[:, :w * 4].reshape(h, w, 4).copy()
    finally:
        v.release()
    return Image.fromarray(px).convert("RGB")


def final(eng, name):
    png = OUT / f"_{name}.png"
    eng.render(camera="cam", renderer="cycles", frame=0, width=W, height=H, samples=96, png=str(png))
    return Image.open(png).convert("RGB")


def strip(pictures, labels, file):
    font = ImageFont.load_default(size=17)
    out = Image.new("RGB", (W * len(pictures), H + 28), "white")
    d = ImageDraw.Draw(out)
    for i, (p, t) in enumerate(zip(pictures, labels)):
        out.paste(p, (i * W, 28))
        d.text((i * W + 8, 5), t, fill="black", font=font)
    out.save(file)
    print("wrote", file, flush=True)


def anchors_along(eng, pixels):
    """Pick each pixel on the clay; its surface point and normal in the clay's own space (look_at's local)."""
    out = []
    for x, y in pixels:
        r = eng.pick(camera="cam", frame=0, width=W, height=H, x=x, y=y)
        if r.get("hit") and r.get("item") == "blob" and r.get("local"):
            out.append([*r["local"], *r["localNormal"], 1.0])
    return out


def main_():
    OUT.mkdir(parents=True, exist_ok=True)
    folder = Path(tempfile.mkdtemp(prefix="rostrum-cl4-"))
    doc = Document.new(KIND, folder=folder, item="scene")
    doc.run_script("scene.py", run_source(SCENE, "scene.py"))
    call(doc, [{"op": "clay.add", "args": {"id": "blob", "at": [0, 0.1, 0], "radius": 0.08, "material": "clayc"}}])
    call(doc, [{"op": "clay.set", "target": ["blob"], "args": {"detailMode": "fixed", "detail": 0.0015}}])
    # a little sculpting so it's a sculpted clay, not a ball: a brow ridge, a nose bump, a carved mouth groove
    call(doc, [{"op": "clay.lump", "target": ["blob"], "args": {"at": [0, 0.01, 0.07], "radius": 0.022}}])
    call(doc, [{"op": "clay.lump", "target": ["blob"], "args": {"at": [-0.03, 0.035, 0.06], "to": [0.03, 0.035, 0.06],
                                                               "radius": 0.012}}])
    call(doc, [{"op": "clay.stroke", "target": ["blob"], "args": {
        "brush": "crease", "size": 0.008, "strength": 0.8, "path": [[-0.025, -0.025, 0.2], [0, -0.03, 0.2],
                                                                    [0.025, -0.025, 0.2]], "dir": [0, 0, -1]}}])
    doc.save()
    with Engine() as eng:
        note("scene", ms=send(eng, doc, folder))
        strip([quick(eng), final(eng, "qf")], ["Quick (Storm)", "Final (Cycles)"], OUT / "quick-vs-final.png")

        # a stripe across the front, below the brow, through the agent path: pick -> anchors -> stroke.add
        y = int(H * 0.52)
        pts = anchors_along(eng, [(x, y) for x in range(int(W * 0.30), int(W * 0.70), 6)])
        note("stripe anchors", count=len(pts))
        call(doc, [{"op": "paint.add", "target": ["blob"], "args": {"id": "colour1", "name": "Colour 1",
                                                                     "channel": "colour"}},
                   {"op": "stroke.add", "target": ["colour1"], "args": {
                       "anchors": pts, "reach": 0.004, "color": "#d0201a", "size": 12, "brush": "round",
                       "opacity": 1.0}}])
        note("painted scene", ms=send(eng, doc, folder))
        q0, f0 = quick(eng), final(eng, "s0")

        # reshape under the stripe: a lump pushes the cheek out where the stripe runs
        call(doc, [{"op": "clay.lump", "target": ["blob"], "args": {"at": [0.035, -0.005, 0.06], "radius": 0.025}}])
        note("reshaped scene (new unfold)", ms=send(eng, doc, folder))
        q1, f1 = quick(eng), final(eng, "s1")
        strip([q0, f0, q1, f1], ["Quick: stripe", "Final: stripe", "Quick: lump added under it",
                                 "Final: lump added under it"], OUT / "stripe-before-after.png")

        # Relief: wrinkle lines on the brow (a height layer, white = raised); shows in Final
        rows = []
        for k, yy in enumerate((0.33, 0.36, 0.39)):
            line = anchors_along(eng, [(x, int(H * yy + 4 * math.sin(x / 9))) for x in
                                       range(int(W * 0.38), int(W * 0.62), 5)])
            rows.append(line)
        call(doc, [{"op": "paint.add", "target": ["blob"], "args": {"id": "relief1", "name": "Relief 1",
                                                                     "channel": "height"}}]
             + [{"op": "stroke.add", "target": ["relief1"], "args": {
                 "anchors": r, "reach": 0.0015, "color": "#ffffff", "size": 4, "brush": "round", "opacity": 1.0}}
                for r in rows if len(r) > 1])
        note("relief scene", ms=send(eng, doc, folder), lines=[len(r) for r in rows])
        f2 = final(eng, "r1")
        call(doc, [{"op": "paint.set", "target": ["relief1"], "args": {"visible": False}}])
        send(eng, doc, folder)
        f3 = final(eng, "r0")
        strip([f3, f2], ["Final: no Relief", "Final: Relief wrinkles (white strokes = raised)"], OUT / "relief.png")
    (OUT / "clay_paint_shots.json").write_text(json.dumps(REPORT, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main_()
