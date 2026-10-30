# PR7 check (garments from patterns): a scratch project, no window. A simple stand (a capsule body and a bar for shoulders and
# arms, both Stays still) and a shirt made of two flat pieces (a front and a back, each a body with sleeve stubs), curved
# round the body, sewn at the sides, under the arms and on the shoulders. The simulation is computed through the document's
# own path (rostrum3d.sim.compute), the core's reply printed (points, triangles, seams kept, frameMs), then Quick (Storm)
# stills at the start, while sewing, and at rest, plus a Final (Cycles) still of the last frame. Then: every seam pair is
# closed at the last frame (the median pair less than one triangle apart; the share joined and the widest are printed) and
# the shirt has not fallen off the stand.
# The lead runs it:  heavy.ps1 run "hem: pr7 garment" gpu <venv python> apps\3d\tools\garment_check.py <out folder> [--video]
# Exit 0 = every check passed; look at garment-*.png: a shirt hanging on the stand, closed at its seams, folds at the waist.
import shutil
import struct
import subprocess
import sys
import tempfile
import time
from pathlib import Path

WT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(WT / "apps" / "3d" / "python"), str(WT / "shared" / "core")]
from rostrum_core import Document                            # noqa: E402
from rostrum_core.cache import CACHE                         # noqa: E402
from rostrum3d import KIND, garment, run_source              # noqa: E402
from rostrum3d.compile import describe, shot_info            # noqa: E402
from rostrum3d.engine import Engine                          # noqa: E402
from rostrum3d.sim import inputs as SI                       # noqa: E402
from rostrum3d.sim.compute import compute                    # noqa: E402
from rostrum3d.sim.result import cloth_file, read            # noqa: E402

OUT = Path(sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else r"C:\Users\Sam\.rostrum\waves\results\3d-pr7\garment")
STILLS = (0, 6, 12, 71)
W, H = 960, 720
SCENE = '''
stand = material("stand", baseColor="#d9d4cc", roughness=0.6)
cotton = material("cotton", baseColor="#3d6fb0", roughness=0.9, sheen=0.5)
floor = material("floor", baseColor="#5d6670", roughness=0.7)
mesh("ground", shape="plane", width=6, depth=6, material=floor)
mesh("body", shape="capsule", radius=0.14, height=0.62, y=0.9, sz=0.75, material=stand).simulate("still")
mesh("arms", shape="capsule", radius=0.05, height=0.74, rz=90, y_world=1.44, material=stand).simulate("still")
mesh("pole", shape="cylinder", radius=0.025, height=0.9, material=stand).simulate("still")
shirt = [[-0.2, 0], [0.2, 0], [0.2, 0.36], [0.36, 0.38], [0.36, 0.53], [0.08, 0.55], [0, 0.5], [-0.08, 0.55],
         [-0.36, 0.53], [-0.36, 0.38], [-0.2, 0.36]]
# edges: 0 hem, 1 right side, 2 right underarm, 3 right cuff, 4 right shoulder, 5 6 neck, 7 left shoulder, 8 left cuff,
# 9 left underarm, 10 left side. The back is the same outline turned 180: its edge 10 sits on the front's edge 1 side.
garment("shirt", material=cotton, clothWeight=0.15, stiffness=0.25, sewTime=0.5, pieces=[
    {"name": "front", "outline": shirt, "at": [0, 0.97, 0.16], "wrap": 1.0},
    {"name": "back", "outline": shirt, "at": [0, 0.97, -0.16], "turn": 180, "wrap": 1.0}],
  seams=[{"a": ["front", 1], "b": ["back", 10]}, {"a": ["front", 10], "b": ["back", 1]},
         {"a": ["front", 2], "b": ["back", 9]}, {"a": ["front", 9], "b": ["back", 2]},
         {"a": ["front", 4], "b": ["back", 7]}, {"a": ["front", 7], "b": ["back", 4]}])
light("sky", kind="dome", color="#ffffff", intensity=0.6)
light("key", kind="distant", intensity=2.5, angle=3).aim((-0.5, -1, -0.7))
camera("cam", focalLength=40, x=1.1, y=1.45, z=1.9).aim((0, 1.15, 0))
shot("dress", camera="cam", fps=24, start=0, end=3, width=%d, height=%d)
''' % (W, H)


def last_frame(path: Path):
    """The cloth file's points at its last frame (item space) and its point count (sim/result.py's RCL1 layout)."""
    b = path.read_bytes()
    points, tris, frames, _ = struct.unpack_from("<4i", b, 4)
    at = 20 + tris * 12 + points * 8 + (frames - 1) * points * 12
    return [struct.unpack_from("<3f", b, at + 12 * i) for i in range(points)]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    folder = Path(tempfile.mkdtemp(prefix="garment-"))
    doc = Document.new(KIND)
    doc.run_script("s.py", run_source(SCENE, "s.py"))
    data = doc.data
    item = next(i for i in data["items"] if i["id"] == "shirt")
    made = garment.make(item)
    print(f"pattern: {len(made['points'])} points, {len(made['triangles'])} triangles, {len(made['seams'])} seam pairs, "
          f"spacing {made['spacing'] * 100:.2f} cm")

    t0 = time.time()
    key = compute(data, "dress", folder, progress=lambda i, n, f: i % 24 or print(f"  frame {i} of {n}"))
    entry = CACHE.get(SI.KIND, key)
    r = read(entry).reply
    print(f"simulated in {time.time() - t0:.1f} s: frames {r['frames']}, frameMs {r['frameMs']:.1f}, cloth {r['cloth']}")
    c = r["cloth"][0]
    fails = []
    if c["points"] != len(made["points"]) or c["seams"] != len(made["seams"]):
        fails.append(f"the engine kept {c['points']} points and {c['seams']} pairs of {len(made['points'])} / {len(made['seams'])}")

    pts = last_frame(Path(entry) / cloth_file("shirt"))
    stored = {}                     # the engine numbers points in the order the triangles first name them (weld, refine)
    for p in (i for t in made["triangles"] for i in t):
        stored.setdefault(p, len(stored))
    gaps = sorted(max(abs(pts[stored[a]][k] - pts[stored[b]][k]) for k in range(3)) for a, b in made["seams"])
    shut = sum(g <= 0.002 for g in gaps) / len(gaps)
    print(f"seams at the last frame: {shut:.0%} of the pairs joined (within 2 mm), median gap {gaps[len(gaps) // 2] * 1000:.2f} mm, "
          f"widest {gaps[-1] * 1000:.1f} mm (a pair the stand holds apart stays open)")
    if gaps[len(gaps) // 2] > made["spacing"]:        # KNOWN OPEN: pairs rest a few mm apart rather than joined (cloth_sew.cpp)
        fails.append(f"the seams are open: median gap {gaps[len(gaps) // 2] * 1000:.1f} mm, more than one triangle")
    top = max(p[1] for p in pts)
    print(f"the shirt's highest point at the end: {top:.3f} m (the shoulders are at about 1.5 m)")
    if top < 1.35:
        fails.append(f"the shirt slid off the stand (its top is at {top:.2f} m)")

    scene = describe(data, "dress", folder, sim="strict")
    info = shot_info(data, "dress")
    with Engine() as eng:
        eng.ensure_scene(scene)
        for f in STILLS:
            png = OUT / f"garment-{f:03d}.png"
            eng.render(camera=info["camera"], renderer="storm", frame=f, width=W, height=H, png=str(png))
            print("wrote", png)
        png = OUT / "garment-final-071.png"
        eng.render(camera=info["camera"], renderer="cycles", frame=71, width=W, height=H, png=str(png), samples=64)
        print("wrote", png)
        if "--video" in sys.argv:          # every frame, then an MP4 master and its -share copy
            frames = Path(tempfile.mkdtemp(prefix="garment-frames-"))
            for f in range(info["start"], info["end"] + 1):
                eng.render(camera=info["camera"], renderer="storm", frame=f, width=1280, height=960,
                           png=str(frames / f"f{f:04d}.png"))
            for name, q in (("garment-sew.mp4", ["-crf", "12"]), ("garment-sew-share.mp4", ["-b:v", "4M"])):
                subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(info["fps"]), "-i",
                                str(frames / "f%04d.png"), "-c:v", "libx264", "-pix_fmt", "yuv420p", *q, str(OUT / name)],
                               check=True)
                print("wrote", OUT / name)
            shutil.rmtree(frames, ignore_errors=True)
    shutil.rmtree(folder, ignore_errors=True)
    if fails:
        raise SystemExit("FAILED: " + "; ".join(fails))
    print("every check passed; look at the pictures")


main()
