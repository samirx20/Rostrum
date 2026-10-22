# Light accounting (H19): does every renderer give the light USD's rules say? Through the lock:
#   heavy.ps1 run "<team>: light check" gpu <worktree>\.venv\Scripts\python.exe apps\3d\tools\light_check.py <out folder>
# Two flat planes (grey #9a9a9a = 0.3231 linear, white #ffffff = 1), roughness 1, seen from above; one light at a time,
# nothing else. The grey plane is measured in LINEAR light from the EXRs and compared with the hand-computed value;
# exits 1 when a renderer is more than 5% off (report.json in the out folder has every number).
import json, math, sys
from pathlib import Path

WT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(WT / "apps" / "3d" / "python"), str(WT / "shared" / "core")]
import numpy as np, OpenEXR                                  # noqa: E401,E402
from rostrum_core import Document                            # noqa: E402
from rostrum3d import KIND, run_source                       # noqa: E402
from rostrum3d.compile import describe                       # noqa: E402
from rostrum3d.engine import Engine                          # noqa: E402

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else None
W, H = 320, 180
GREY = 0.3231
SAMPLES = 128
BASE = '''
grey = material("grey", baseColor="#9a9a9a", roughness=1)
white = material("white", baseColor="#ffffff", roughness=1)
mesh("g", shape="plane", width=1.2, depth=1.6, x=-0.7, material=grey)
mesh("w", shape="plane", width=1.2, depth=1.6, x=0.7, material=white)
cam = camera("cam", focalLength=35, y=4.0, z=0.02).aim((0, 0, 0))
shot("hero", camera=cam, fps=24, start=0, end=1)
'''
G = (slice(int(H * .40), int(H * .60)), slice(int(W * .30), int(W * .38)))   # centre of the grey plane
Wp = (slice(int(H * .40), int(H * .60)), slice(int(W * .62), int(W * .70)))  # centre of the white plane
SKY = (slice(0, 8), slice(0, 8))


def read(p):
    with OpenEXR.File(str(p)) as f:
        ch = f.channels()
        k = next((k for k in ("RGB", "RGBA") if k in ch), None)
        px = np.asarray(ch[k].pixels, float) if k else np.stack([np.asarray(ch[c].pixels, float) for c in "RGB"], -1)
    return px[..., :3]


def write(p, px):
    OpenEXR.File({"compression": OpenEXR.ZIP_COMPRESSION, "type": OpenEXR.scanlineimage},
                 {"RGB": px.astype(np.float32)}).write(str(p))


def sun_dome():
    """A black lat-long dome with one small round sun 50° up; returns (file, its irradiance on a level floor per unit
    picture value), integrated by hand over the pixels (solid angle × cos of the angle from straight up)."""
    w, h = 1024, 512
    v, u = np.mgrid[0:h, 0:w]
    polar = (v + 0.5) / h * math.pi                      # 0 = straight up
    az = (u + 0.5) / w * 2 * math.pi
    d = np.stack([np.sin(polar) * np.cos(az), np.cos(polar), np.sin(polar) * np.sin(az)], -1)
    el, a0 = math.radians(50), math.pi
    c = np.array([math.cos(el) * math.cos(a0), math.sin(el), math.cos(el) * math.sin(a0)])
    disc = (d @ c) > math.cos(math.radians(1.5))
    L = 500.0
    px = np.zeros((h, w, 3)); px[disc] = L
    omega = (2 * math.pi / w) * (math.pi / h) * np.sin(polar)
    E = float((L * omega * np.cos(polar))[disc].sum())
    p = OUT / "sun-dome.exr"
    write(p, px)
    return p, E


def render(name, light):
    doc = Document.new(KIND)
    doc.run_script("s.py", run_source(BASE + light, "s.py"))
    res = {}
    with Engine() as eng:
        eng.load(describe(doc.data, "hero"))
        for r, extra in (("storm", {}), ("cycles", {"samples": SAMPLES, "denoise": SAMPLES > 128})):
            exr = OUT / f"{name}-{r}.exr"
            eng.render(camera="cam", renderer=r, frame=0, width=W, height=H, png=str(OUT / f"{name}-{r}.png"),
                       exr=str(exr), **extra)
            e = read(exr)
            res[r] = {"grey": float(e[G].mean()), "white": float(e[Wp].mean()), "sky": float(e[SKY].mean())}
    return res


if __name__ == "__main__":
    if OUT is None:
        sys.exit("usage: light_check.py <out folder>")
    OUT.mkdir(parents=True, exist_ok=True)
    sun_file, sun_E = sun_dome()
    cases = {
        # UsdLux: a distant light, normalize on -> intensity is the illuminance on a facing surface (lux)
        "distant": ('light("sun", kind="distant", intensity=3.14159, normalize=True, shadows=False, rx=-90)\n',
                    3.14159),
        "distant-unnormalized": ('light("sun", kind="distant", intensity=3.14159, shadows=False, rx=-90)\n', None),
        # UsdLux: a dome of intensity 1 is seen as 1; a level floor under it gets E = π × 1
        "flat-dome": ('light("sky", kind="dome", intensity=1)\n', math.pi),
        "sun-dome": (f'light("sky", kind="dome", texture=r"{sun_file.as_posix()}", intensity=1)\n', sun_E),
    }
    # a 0.5 m square panel 2 m over the grey plane's centre, facing down, radiance 10 (normalize off); E integrated
    n = 400; xs = (np.arange(n) + 0.5) / n * 0.5 - 0.25; X, Z = np.meshgrid(xs, xs)
    r2 = X ** 2 + Z ** 2 + 4.0
    E_rect = float((10 * (2.0 / np.sqrt(r2)) ** 2 / r2 * (0.5 / n) ** 2).sum())
    cases["rect"] = ('light("panel", kind="rect", width=0.5, height=0.5, intensity=10, shadows=False, x=-0.7, y=2, rx=-90)\n',
                     E_rect)
    # the same panel with normalize on: intensity 2.5 over its 0.25 m² is radiance 10 again (Cycles was 10 000× off until H23)
    cases["rect-normalized"] = ('light("panel", kind="rect", width=0.5, height=0.5, intensity=2.5, normalize=True, shadows=False, '
                                'x=-0.7, y=2, rx=-90)\n', E_rect)
    report = {}
    for name, (light, E) in cases.items():
        res = render(name, light)
        exp = None if E is None else {"grey": GREY * E / math.pi, "white": E / math.pi}
        report[name] = {"E_spec": E, "expected": exp, **res}
        print(name, json.dumps(report[name], indent=None))
    (OUT / "report.json").write_text(json.dumps(report, indent=2))
    off = [f"{n} {r}: {v[r]['grey']:.4f}, should be {v['expected']['grey']:.4f}" for n, v in report.items()
           if v["expected"] for r in ("storm", "cycles") if abs(v[r]["grey"] / v["expected"]["grey"] - 1) > 0.05]
    if off:
        sys.exit("light check FAILED:\n  " + "\n  ".join(off))
    print("light check: every case within 5% of the hand-computed value")
