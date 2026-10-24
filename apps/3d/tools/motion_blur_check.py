# Motion blur (brief 11, 11b): two scenes, each frame rendered through the Render button's path (compile.describe +
# render_fields.settings + the core's render) with motion blur off and on, and the same frame in the viewport's Final
# look (view, renderer cycles) with it on:
#   camera - an orbit-rig turntable round a box (the camera moves);
#   object - a red ball flying across a still camera (the object moves; needs libs/cycles-rostrum.patch, 11b).
# For the ball it prints how wide it and its smear are along its path in each picture. Through the lock:
#   heavy.ps1 run "<team>: motion blur check" gpu <worktree>\.venv\Scripts\python.exe apps\3d\tools\motion_blur_check.py <out folder> [camera|object]
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
SCENES = {
    "camera": '''
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
''',
    # 6 m in 1 s: 25 cm a frame, so a 180-degree shutter smears the 0.3 m ball by about 12 cm (some 50 pixels).
    "object": '''
grey = material("grey", baseColor="#8a8a8a", roughness=0.7)
red = material("red", baseColor="#d03020", roughness=0.4)
mesh("floor", shape="plane", width=8, depth=8, material=grey)
ball = mesh("ball", shape="sphere", radius=0.15, y=0.4, material=red)
ball.key("x", {0: -3, 1: 3}, ease="linear")
light("sky", kind="dome", color="#ffffff", intensity=1)
light("key", kind="distant", intensity=2, angle=2).aim((0, -1, -0.6))
camera("cam", focalLength=35, y=0.5, z=3).aim((0, 0.4, 0))
shot("hero", camera="cam", fps=24, start=0, end=1, width=1280, height=720, renderQuality="good", motionBlur=%s)
''',
}


def scene(name: str, blur: bool):
    doc = Document.new(KIND)
    doc.run_script("s.py", run_source(SCENES[name] % blur, "s.py"))
    info = shot_info(doc.data, "hero")
    return describe(doc.data, "hero"), settings(doc.data["shots"][0], info), info


def ball_width(png: Path) -> int:
    """How wide the ball and its smear are, in pixels: the widest row across it (in front of the plain sky) of pixels
    that differ from that row's sky."""
    px = np.asarray(Image.open(png).convert("RGB")).astype(int)[300:400]
    return int((np.abs(px - px[:, :1]).max(axis=2) > 10).sum(axis=1).max())


def final_view(eng: Engine, s: dict, png: Path):
    """The Final look through the shot camera, same scene, until it has all its samples."""
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
    Image.fromarray(px).convert("RGB").save(png)
    print("wrote", png)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    names = sys.argv[2:] or list(SCENES)
    with Engine() as eng:
        for name in names:
            for blur in (False, True):
                sc, s, info = scene(name, blur)
                print(name, "shot sent to the core:", sc["shot"])
                png = OUT / f"motion-blur-{name}-{'on' if blur else 'off'}.png"
                eng.ensure_scene(sc)
                eng.render(camera=info["camera"], renderer=s["renderer"], frame=FRAME, width=s["width"],
                           height=s["height"], samples=s["samples"], denoise=s["denoise"], png=str(png))
                print("wrote", png)
            final = OUT / f"motion-blur-{name}-final-view.png"
            final_view(eng, s, final)
            if name == "object":
                widths = {p.stem: ball_width(p) for p in (OUT / "motion-blur-object-off.png",
                                                         OUT / "motion-blur-object-on.png", final)}
                print("ball width along its path (pixels):", widths)
                if not widths["motion-blur-object-on"] > widths["motion-blur-object-off"] * 1.2:
                    raise SystemExit("the moving ball is not smeared with motion blur on")


main()
