# Clay stroke height and mirror-line check (CL7b). Draws Add strokes by script on a 5 cm clay ball and measures, with
# picks straight down the ball's front (a 1° free camera per sample), how high each stroke rose in mm:
#  - height: one Add stroke (strength 0.5, Mirror off) per brush size at each grain. The rise should follow the brush,
#    not the grain: the same stroke at 0.2 mm and at 2 mm should rise about the same (the stroke cap is 0.25 x radius
#    at strength 0.5). Before CL7b a big brush at a fine grain rose far less (each dab held to 2 grains).
#  - mirror: with Mirror on, a stroke running down near the middle (its mirrored copy overlapping it) and one across
#    it; the profile across x = 0 and its bend there ("kink": the jump in slope at x = 0, against the largest jump
#    elsewhere on the profile). A crease down the middle shows as a kink well above the rest.
#  - pictures: the mirror strokes close up, Quick (Storm) and Final (Cycles), and the big strokes side by side.
# Through the lock (renders and picks use the GPU):
#   heavy.ps1 run "<team>: clay height" gpu <venv python> apps\3d\tools\clay_height_check.py <out folder>
#       [grains=0.0002,0.0005,0.002] [sizes=0.004,0.012,0.025] [nopics] [nocycles] [cycles=<grain>: Final only at that grain]
# Writes <out>\height.json and prints a table; pictures <out>\mirror-<grain>-storm.png / -cycles.png and
# <out>\strokes-<grain>-storm.png.
import json
import math
import sys
import time
from pathlib import Path

WT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(WT / "apps" / "3d" / "python"), str(WT / "shared" / "core")]
from rostrum_core import Document, Who                       # noqa: E402
from rostrum3d import KIND, run_source                       # noqa: E402
from rostrum3d.compile import describe                       # noqa: E402
from rostrum3d.engine import Engine                          # noqa: E402
import rostrum3d.ops_clay  # noqa: E402,F401

R, CY = 0.05, 0.05          # the ball: radius, centre height (centre x = z = 0)
STRENGTH = 0.5
SCENE = '''
ground = material("ground", baseColor="#5a5d62", roughness=0.8)
mesh("floor", shape="plane", width=4, depth=4, material=ground)
light("key", kind="rect", width=0.4, height=0.4, intensity=20, x=-0.5, y=0.6, z=0.6, rx=-35, ry=-35)
light("fill", kind="dome", intensity=0.4)
cam = camera("cam", focalLength=50, x=0.0, y=0.075, z=0.22).aim((0, 0.06, 0.03))
close = camera("close", focalLength=100, x=0.03, y=0.07, z=0.2).aim((0, 0.062, 0.045))
shot("hero", camera=cam, fps=24, start=0, end=1)
'''


def new_doc(grain, sym):
    doc = Document.new(KIND)
    doc.run_script("s.py", run_source(SCENE, "s.py"))
    doc.apply([{"op": "clay.add", "args": {"at": [0, CY, 0], "radius": R, "symmetry": sym}}], Who.person())
    cid = [i for i in doc.data["items"] if i.get("type") == "clay" or i.get("kind") == "clay"][-1]["id"]
    doc.apply([{"op": "clay.set", "target": [cid],
                "args": {"detailMode": "fixed", "detail": grain}}], Who.person())
    return doc, cid


def stroke(doc, cid, pts, size, brush="add"):
    doc.apply([{"op": "clay.stroke", "target": [cid], "args": {
        "brush": brush, "size": size, "strength": STRENGTH, "path": [list(p) for p in pts], "dir": [0, 0, -1]}}],
        Who.person())


def front(x, y):  # a point on the ball's front at world (x, y), a little in front of it, in the CLAY's own space
    # (a stroke's path is in the clay's space: the ball's centre is its origin; the clay item sits at (0, CY, 0))
    yl = y - CY
    if x * x + yl * yl >= R * R:
        raise SystemExit(f"FAIL: stroke point ({x}, {y}) is off the ball")
    return (x, yl, math.sqrt(R * R - x * x - yl * yl) + 0.002)


def heights(eng, samples):
    """z of the surface straight down -z at each (x, y): a 1° free camera there, the middle pixel picked."""
    out = []
    for x, y in samples:
        r = eng.pick(eye=[x, y, 0.6], target=[x, y, 0.0], fov=1.0, frame=0, width=32, height=32, x=16, y=16)
        out.append(r["point"][2] if r.get("hit") else None)
    return out


def rise(before, after):
    d = [a - b for a, b in zip(after, before) if a is not None and b is not None]
    return max(d) if d else None


def kink(xs, h):
    """the jump in slope at x = 0 (mm per mm), and the largest such jump elsewhere on the profile"""
    jumps = []
    for i in range(1, len(xs) - 1):
        if None in (h[i - 1], h[i], h[i + 1]):
            continue
        s0 = (h[i] - h[i - 1]) / (xs[i] - xs[i - 1])
        s1 = (h[i + 1] - h[i]) / (xs[i + 1] - xs[i])
        jumps.append((abs(xs[i]), abs(s1 - s0)))
    mid = [j for x, j in jumps if x < 1e-9]
    rest = [j for x, j in jumps if x > 1e-9]
    return (mid[0] if mid else None), (max(rest) if rest else None)


def main():
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    kv = dict(a.split("=", 1) for a in sys.argv[2:] if "=" in a)
    grains = [float(g) for g in kv.get("grains", "0.0002,0.0005,0.002").split(",")]
    sizes = [float(s) for s in kv.get("sizes", "0.004,0.012,0.025").split(",")]
    pics, cycles = "nopics" not in sys.argv, "nocycles" not in sys.argv
    result = {"strength": STRENGTH, "ball": R, "height": [], "mirror": []}
    y0 = CY + 0.012                                    # the height strokes run across the ball at this height
    with Engine() as eng:
        for g in grains:
            # the bare ball, then one stroke per size on a fresh ball (strokes never meet)
            doc, cid = new_doc(g, "off")
            eng.load(describe(doc.data, "hero"))
            for size in sizes:
                ys = [y0 + size * (-1.5 + 3.0 * i / 40) for i in range(41)]
                line = [(0.0, y) for y in ys]
                bare = heights(eng, line)
                d2, c2 = new_doc(g, "off")
                stroke(d2, c2, [front(-0.02 + 0.04 * i / 24, y0) for i in range(25)], size)
                t0 = time.perf_counter()
                eng.load(describe(d2.data, "hero"))
                load_s = time.perf_counter() - t0
                h = rise(bare, heights(eng, line))
                if h is None or h < 0.1 * 0.5 * STRENGTH * size:
                    raise SystemExit(f"FAIL: the {size * 1e3:g} mm stroke at grain {g * 1e3:g} mm rose {h} m: it "
                                     "changed (almost) nothing; the measurement or the stroke is wrong")
                row = {"grain_mm": g * 1e3, "size_mm": size * 1e3, "grains_across_radius": round(size / g, 1),
                       "rise_mm": None if h is None else round(h * 1e3, 3),
                       "expected_cap_mm": round(0.5 * STRENGTH * size * 1e3, 3), "load_s": round(load_s, 2)}
                result["height"].append(row)
                print("height", row, flush=True)
                if pics and size == sizes[-1]:
                    eng.render(camera="cam", renderer="storm", frame=0, width=960, height=720,
                               png=str(out / f"strokes-{g * 1e3:g}mm-{size * 1e3:g}-storm.png"))
                    if cycles and ("cycles" not in kv or abs(float(kv["cycles"]) - g) < 1e-9):
                        eng.render(camera="cam", renderer="cycles", frame=0, width=960, height=720, samples=48,
                                   denoise=True, png=str(out / f"strokes-{g * 1e3:g}mm-{size * 1e3:g}-cycles.png"))
                eng.load(describe(doc.data, "hero"))
            # mirror: a stroke down near the middle (x = 0.25 x its radius: its copy overlaps it) and one across it
            size = 0.008
            dm, cm = new_doc(g, "x")
            stroke(dm, cm, [front(0.25 * size, CY - 0.005 + 0.03 * i / 24) for i in range(25)], size)
            stroke(dm, cm, [front(-0.03 + 0.06 * i / 24, CY - 0.018) for i in range(25)], size)
            xs = [0.012 * (-1 + 2 * i / 48) for i in range(49)]      # x = 0 is sample 24
            for y in (CY + 0.01, CY - 0.018):
                line = [(x, y) for x in xs]
                eng.load(describe(dm.data, "hero"))
                after = heights(eng, line)
                db, _ = new_doc(g, "x")
                eng.load(describe(db.data, "hero"))
                h = [None if a is None or b is None else (a - b) * 1e3 for a, b in zip(after, heights(eng, line))]
                k0, kr = kink([x * 1e3 for x in xs], h)
                if max((v for v in h if v is not None), default=0) < 0.2:
                    raise SystemExit(f"FAIL: the mirror stroke at grain {g * 1e3:g} mm rose under 0.2 mm on the profile")
                row = {"grain_mm": g * 1e3, "stroke": "down the middle" if y > CY else "across the middle",
                       "kink_at_middle": None if k0 is None else round(k0, 3),
                       "largest_kink_elsewhere": None if kr is None else round(kr, 3),
                       "profile_mm": [None if v is None else round(v, 3) for v in h]}
                result["mirror"].append(row)
                print("mirror", {k: v for k, v in row.items() if k != "profile_mm"}, flush=True)
            if pics:
                eng.load(describe(dm.data, "hero"))
                eng.render(camera="close", renderer="storm", frame=0, width=960, height=720,
                           png=str(out / f"mirror-{g * 1e3:g}mm-storm.png"))
                if cycles and ("cycles" not in kv or abs(float(kv["cycles"]) - g) < 1e-9):
                    eng.render(camera="close", renderer="cycles", frame=0, width=960, height=720, samples=48,
                               denoise=True, png=str(out / f"mirror-{g * 1e3:g}mm-cycles.png"))
    (out / "height.json").write_text(json.dumps(result, indent=1), encoding="utf-8")
    print("\nrise (mm) by grain x brush radius, strength", STRENGTH)
    for row in result["height"]:
        print(f"  grain {row['grain_mm']:5.2f} mm  radius {row['size_mm']:5.1f} mm ({row['grains_across_radius']:6.1f}"
              f" grains): rise {row['rise_mm']} mm (cap {row['expected_cap_mm']})")
    print("ok")


if __name__ == "__main__":
    main()
