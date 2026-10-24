# Motion blur (brief 11): an orbit-rig turntable round a box, one frame rendered through the Render button's path
# (compile.describe + render_fields.settings + the core's render) with motion blur off and on, and the same frame in
# the viewport's Final look (view, renderer cycles) with it on. Through the lock:
#   heavy.ps1 run "<team>: motion blur check" gpu <worktree>\.venv\Scripts\python.exe apps\3d\tools\motion_blur_check.py <out folder>
import sys
import time
from pathlib import Path

WT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(WT / "apps" / "3d" / "python"), str(WT / "shared" / "core")]
import numpy as np                                           # noqa: E402
from PIL import Image                                        # noqa: E402
from rostrum_core import Document                            # noqa: E402
from rostrum3d import KIND, run_source                       # noqa: E402
from rostrum3d.compile import describe, shot_info            # noqa: E402
from rostrum3d.engine import Engine                          # noqa: E402
from rostrum3d.render_fields import settings                 # noqa: E402

OUT = Path(sys.argv[1])
FRAME = 12
SRC = '''
grey = material("grey", baseColor="#8a8a8a", roughness=0.7)
red = material("red", baseColor="#c0503c", roughness=0.4)
mesh("floor", shape="plane", width=8, depth=8, material=grey)
mesh("box", shape="box", width=0.5, height=0.5, depth=0.5, y=0.25, material=red)
mesh("post", shape="cylinder", radius=0.05, height=0.8, x=0.6, y=0.4, z=0.3, material=grey)
light("sky", kind="dome", color="#ffffff", intensity=1)
light("key", kind="distant", intensity=2, angle=2).aim((0, -1, -0.6))
r = rig("spin", rig="orbit", radius=2.0, height=0.6, y=0.25)
with r:
    camera("cam", focalLength=35)
r.key("angle", {0: 0, 2: (360, "linear")})
shot("hero", camera="cam", fps=24, start=0, end=2, width=1280, height=720, renderQuality="good", motionBlur=%s)
'''


def scene(blur: bool):
    doc = Document.new(KIND)
    doc.run_script("s.py", run_source(SRC % blur, "s.py"))
    info = shot_info(doc.data, "hero")
    return describe(doc.data, "hero"), settings(doc.data["shots"][0], info), info


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with Engine() as eng:
        for blur in (False, True):
            sc, s, info = scene(blur)
            print("shot sent to the core:", sc["shot"])
            png = OUT / f"motion-blur-{'on' if blur else 'off'}.png"
            eng.ensure_scene(sc)
            eng.render(camera=info["camera"], renderer=s["renderer"], frame=FRAME, width=s["width"], height=s["height"],
                       samples=s["samples"], denoise=s["denoise"], png=str(png))
            print("wrote", png)
        # The Final look through the shot camera, same scene (motion blur on), until it has all its samples.
        t0 = time.time()
        while True:
            v, w, h, stride, reply = eng.view(camera="cam", frame=FRAME, width=s["width"], height=s["height"],
                                              renderer="cycles", samples=s["samples"], denoise=s["denoise"])
            if reply["final"]["converged"] or time.time() - t0 > 300:
                break
            v.release()
            time.sleep(0.2)
        try:
            px = np.frombuffer(v, np.uint8).reshape(h, stride)[:, :w * 4].reshape(h, w, 4).copy()
        finally:
            v.release()
        if not reply["final"]["converged"]:
            raise SystemExit("the Final look did not finish within 300 s")
        Image.fromarray(px).convert("RGB").save(OUT / "motion-blur-final-view.png")
        print("wrote", OUT / "motion-blur-final-view.png")


main()
