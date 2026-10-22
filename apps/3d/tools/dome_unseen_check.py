# Dome lights, camera doesn't see it (H22): a Cycles render with a dome `seenByCamera=False` must keep a clear
# background (alpha 0) while the dome still lights and shows in reflections. Through the lock:
#   heavy.ps1 run "<team>: dome check" gpu <worktree>\.venv\Scripts\python.exe apps\3d\tools\dome_unseen_check.py <out>
# Writes dome-seen.png / dome-unseen.png (each over a checkerboard, so clear = checks) and exits 1 when the unseen
# dome's background isn't clear or the object went dark.
import sys
from pathlib import Path

WT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(WT / "apps" / "3d" / "python"), str(WT / "shared" / "core")]
import numpy as np, OpenEXR                                  # noqa: E401,E402
from PIL import Image                                         # noqa: E402
from rostrum_core import Document                            # noqa: E402
from rostrum3d import KIND, run_source                       # noqa: E402
from rostrum3d.compile import describe                       # noqa: E402
from rostrum3d.engine import Engine                          # noqa: E402

W, H = 640, 360
SCENE = '''
chrome = material("chrome", baseColor="#d8d8d8", metallic=1, roughness=0.12)
paint = material("paint", baseColor="#c23b22", roughness=0.4)
mesh("ball", shape="sphere", radius=0.3, x=-0.35, y=0.3, material=chrome)
mesh("box", shape="box", width=0.45, height=0.45, depth=0.45, bevel=0.03, x=0.4, y=0.225, ry=30, material=paint)
light("sky", kind="dome", intensity=1, color="#9fc3ff", seenByCamera={seen})
light("key", kind="rect", width=0.8, height=0.8, intensity=12, x=-1, y=1.6, z=1.2).aim((0, 0.2, 0))
cam = camera("cam", focalLength=40, y=0.6, z=2.4).aim((0, 0.25, 0))
shot("hero", camera=cam, fps=24, start=0, end=1)
'''


def rgba(p: Path) -> np.ndarray:
    with OpenEXR.File(str(p)) as f:
        ch = f.channels()
        if "RGBA" in ch:
            return np.asarray(ch["RGBA"].pixels, float)
        return np.stack([np.asarray(ch[c].pixels, float) for c in "RGBA"], -1)


def over_checks(png: Path, alpha: np.ndarray, out: Path) -> None:
    """The PNG (the background laid in black where the render is clear) over grey checks, by the EXR's alpha."""
    im = np.asarray(Image.open(png).convert("RGB"), float)
    y, x = np.mgrid[0:im.shape[0], 0:im.shape[1]]
    checks = np.where(((x // 20 + y // 20) % 2) == 0, 200.0, 140.0)[..., None]
    a = np.clip(alpha, 0, 1)[..., None]
    Image.fromarray(np.clip(im + checks * (1 - a), 0, 255).astype(np.uint8)).save(out)


if __name__ == "__main__":
    out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
    res = {}
    with Engine() as eng:
        for seen in (True, False):
            name = "dome-seen" if seen else "dome-unseen"
            doc = Document.new(KIND)
            doc.run_script("s.py", run_source(SCENE.format(seen=seen), "s.py"))
            eng.load(describe(doc.data, "hero"))
            eng.render(camera="cam", renderer="cycles", frame=0, width=W, height=H, samples=128, denoise=True,
                       exr=str(out / f"{name}.exr"), png=str(out / f"{name}-raw.png"))
            px = rgba(out / f"{name}.exr")
            over_checks(out / f"{name}-raw.png", px[..., 3], out / f"{name}.png")
            (out / f"{name}-raw.png").unlink()
            res[seen] = {"corner_alpha": float(px[:20, :20, 3].mean()),
                         "box": float(px[int(H * .55):int(H * .65), int(W * .66):int(W * .72), :3].mean())}
            print(name, res[seen])
    bad = []
    if res[False]["corner_alpha"] > 0.01:
        bad.append(f"unseen dome: background alpha {res[False]['corner_alpha']:.3f}, should be 0")
    if res[True]["corner_alpha"] < 0.99:
        bad.append(f"seen dome: background alpha {res[True]['corner_alpha']:.3f}, should be 1")
    if abs(res[False]["box"] / res[True]["box"] - 1) > 0.1:
        bad.append(f"the box's light changed with the dome hidden: {res[True]['box']:.4f} -> {res[False]['box']:.4f}")
    if bad:
        sys.exit("dome check FAILED:\n  " + "\n  ".join(bad))
    print("dome check: hidden dome leaves a clear background and lights the same")
