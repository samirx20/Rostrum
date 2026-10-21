"""Scene-linear EXR -> display PNG through OpenColorIO (replaces H1's hand-written ACES fit).

Config: OCIO's built-in ASWF "CG config" (ocio://cg-config-latest, BSD-3-Clause, ships inside
the OpenColorIO library: nothing to download). Input space = the config's scene_linear role
unless --input says otherwise; that must match what Cycles rendered in (render.ps1 sets OCIO to
the same config, so Cycles renders in that role too).

  uv run --with opencolorio --with openexr --with numpy --with pillow python -I view.py in.exr out.png
      [--view "ACES 2.0 - SDR 100 nits (Rec.709)"] [--display "sRGB - Display"] [--exposure 0]
      [--grain 0.0 --grain-png out-graded.png]   (grain: a simple film-grain pass, kept separate)
"""
import argparse
import numpy as np
import OpenEXR
import PyOpenColorIO as ocio
from PIL import Image

CONFIG = "ocio://cg-config-latest"


def read_rgb(path):
    with OpenEXR.File(path) as f:
        ch = f.channels()
        key = "RGBA" if "RGBA" in ch else "RGB" if "RGB" in ch else None
        if key is None:
            raise SystemExit(f"no RGB(A) channels in {path}: {list(ch)}")
        return np.ascontiguousarray(np.asarray(ch[key].pixels, dtype=np.float32)[..., :3])


def grain(rgb_display, amount, seed=7):
    """Luminance grain, strongest in the mid-tones, slightly soft (2-px clumps); display-referred."""
    h, w, _ = rgb_display.shape
    rng = np.random.default_rng(seed)
    n = rng.standard_normal((h // 2 + 1, w // 2 + 1)).astype(np.float32)
    n = np.kron(n, np.ones((2, 2), np.float32))[:h, :w]
    n = 0.5 * n + 0.5 * rng.standard_normal((h, w)).astype(np.float32)
    lum = rgb_display.mean(-1, keepdims=True)
    weight = 4.0 * lum * (1.0 - lum)
    return np.clip(rgb_display + amount * weight * n[..., None], 0, 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("exr"); ap.add_argument("png")
    ap.add_argument("--view", default="ACES 2.0 - SDR 100 nits (Rec.709)")
    ap.add_argument("--display", default="sRGB - Display")
    ap.add_argument("--input", default=None, help="input colour space (default: scene_linear role)")
    ap.add_argument("--exposure", type=float, default=0.0, help="stops, applied in scene-linear")
    ap.add_argument("--grain", type=float, default=0.0)
    ap.add_argument("--grain-png", default=None)
    a = ap.parse_args()
    cfg = ocio.Config.CreateFromFile(CONFIG)
    src = a.input or cfg.getColorSpace(ocio.ROLE_SCENE_LINEAR).getName()
    tr = ocio.DisplayViewTransform(src=src, display=a.display, view=a.view)
    cpu = cfg.getProcessor(tr).getDefaultCPUProcessor()
    rgb = np.nan_to_num(read_rgb(a.exr), nan=0.0, posinf=0.0) * np.float32(2.0 ** a.exposure)
    cpu.applyRGB(rgb)                         # in place, float32
    out = np.clip(rgb, 0, 1)
    Image.fromarray((out * 255 + 0.5).astype(np.uint8)).save(a.png)
    print(f"{a.png}: {cfg.getName()} | {src} -> {a.display} / {a.view}")
    if a.grain_png:
        g = grain(out, a.grain)
        Image.fromarray((g * 255 + 0.5).astype(np.uint8)).save(a.grain_png)
        print(f"{a.grain_png}: grain {a.grain}")


if __name__ == "__main__":
    main()
