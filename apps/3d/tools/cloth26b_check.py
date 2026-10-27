# Brief 26b check (cloth): a scratch project, no window. A plinth (a box that Stays still) on the ground, a 0.8 m cloth plane
# 10 cm above it pinned along its back edge, a camera and two lights; shot "drape" (72 frames at 24 fps). The simulation is
# computed through the document's own path (rostrum3d.sim.compute: its own engine process, stored in the shared cache),
# the core's reply printed (frames, frameMs, the cloth's points and triangles), then three Quick (Storm) stills of the
# drape, early / mid / end, read from the stored result the way the viewport and renders read it (sim="strict").
# Then the same request again: it must come back from the cache (same key, nothing computed).
# Needs the core built with brief 26b. The lead runs it:
#   heavy.ps1 run "sam: 3d-26b cloth" gpu <venv python> apps\3d\tools\cloth26b_check.py <out folder>
# Exit 0 = done; the pictures are cloth26b-<frame>.png in the out folder. Look at them: the cloth hangs from its back edge
# and folds over the plinth's top and front, its middle resting on it, nothing passing through the plinth.
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

WT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(WT / "apps" / "3d" / "python"), str(WT / "shared" / "core")]
from rostrum_core import Document                            # noqa: E402
from rostrum_core.cache import CACHE                         # noqa: E402
from rostrum3d import KIND, run_source                       # noqa: E402
from rostrum3d.compile import describe, shot_info            # noqa: E402
from rostrum3d.engine import Engine                          # noqa: E402
from rostrum3d.sim import inputs as SI                       # noqa: E402
from rostrum3d.sim.compute import compute                    # noqa: E402
from rostrum3d.sim.result import read                        # noqa: E402

OUT = Path(sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else r"C:\Users\Sam\.rostrum\waves\results\3d-26b\sam")
STILLS = (6, 30, 71)
W, H = 960, 540
SCENE = '''
stone = material("stone", baseColor="#9a948a", roughness=0.8)
cloth = material("clothmat", baseColor="#b8402f", roughness=0.9, sheen=0.5)
floor = material("floor", baseColor="#5d6670", roughness=0.7)
mesh("ground", shape="plane", width=6, depth=6, material=floor)
mesh("plinth", shape="box", width=0.4, height=0.4, depth=0.4, y=0.2, material=stone).simulate("still")
mesh("sheet", shape="plane", width=0.8, depth=0.8, y=0.46, z=0.2, material=cloth).simulate(
    "cloth", clothWeight=0.2, stiffness=0.2, pinned="back")
light("sky", kind="dome", color="#ffffff", intensity=0.6)
light("key", kind="distant", intensity=2.5, angle=3).aim((-0.5, -1, -0.7))
camera("cam", focalLength=35, x=1.25, y=0.95, z=1.45).aim((0, 0.3, 0))
shot("drape", camera="cam", fps=24, start=0, end=3, width=%d, height=%d)
''' % (W, H)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    folder = Path(tempfile.mkdtemp(prefix="cloth26b-"))
    doc = Document.new(KIND)
    doc.run_script("s.py", run_source(SCENE, "s.py"))
    data = doc.data
    req, key = SI.sim_inputs(data, "drape", folder)
    print("request bodies:", json.dumps(req["bodies"]))

    t0 = time.time()
    got = compute(data, "drape", folder, progress=lambda i, n, f: i % 24 or print(f"  frame {i} of {n}"))
    assert got == key, f"compute stored key {got}, the inputs say {key}"
    res = read(CACHE.get(SI.KIND, key))
    r = res.reply
    print(f"simulated in {time.time() - t0:.1f} s (with the engine's start): frames {r['frames']}, ms {r['ms']}, "
          f"frameMs {r['frameMs']}, sim {r['sim']}, jolt {r['jolt']}")
    print("cloth:", json.dumps(r.get("cloth")))
    if not r.get("cloth") or r["cloth"][0]["points"] < 1000:
        raise SystemExit("the plane was not refined into a fine grid (expected 1681 points)")

    t1 = time.time()
    again = compute(data, "drape", folder)
    print(f"again: {'same key' if again == key else 'A NEW KEY'} in {time.time() - t1:.2f} s (should be instant: stored)")
    if again != key:
        raise SystemExit("the same request gave another key")

    scene = describe(data, "drape", folder, sim="strict")
    node = next(n for n in scene["items"] if n["id"] == "sheet")
    print("the sheet's node carries:", json.dumps(node.get("cloth")))
    info = shot_info(data, "drape")
    with Engine() as eng:
        eng.ensure_scene(scene)
        for f in STILLS:
            png = OUT / f"cloth26b-{f:03d}.png"
            eng.render(camera=info["camera"], renderer="storm", frame=f, width=W, height=H, png=str(png))
            print("wrote", png)
        if "--video" in sys.argv:          # every frame at 1280 x 720, then an MP4 (master) and its -share copy
            frames = Path(tempfile.mkdtemp(prefix="cloth26b-frames-"))
            for f in range(info["start"], info["end"] + 1):
                eng.render(camera=info["camera"], renderer="storm", frame=f, width=1280, height=720,
                           png=str(frames / f"f{f:04d}.png"))
            fps = str(info["fps"])
            for name, q in (("cloth26b-drape.mp4", ["-crf", "12"]), ("cloth26b-drape-share.mp4", ["-b:v", "4M"])):
                subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", fps, "-i", str(frames / "f%04d.png"),
                                "-c:v", "libx264", "-pix_fmt", "yuv420p", *q, str(OUT / name)], check=True)
                print("wrote", OUT / name)
            shutil.rmtree(frames, ignore_errors=True)
    shutil.rmtree(folder, ignore_errors=True)
    print("done; look at the pictures")


main()
