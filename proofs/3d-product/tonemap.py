"""EXR (scene-linear, Rec.709) -> display PNG for looking at the proof render.

The standalone Cycles app writes linear EXR with no view transform, so this applies one:
exposure, then the ACES RRT+ODT fit by Stephen Hill (sRGB output), then the sRGB curve.
Throwaway proof tool; Rostrum3D will use OpenColorIO for this.

  uv run --with openexr --with numpy --with pillow python -I tonemap.py in.exr out.png [--exposure 0]
"""
import argparse
import numpy as np
import OpenEXR
from PIL import Image

ACES_IN = np.array([[0.59719, 0.35458, 0.04823], [0.07600, 0.90834, 0.01566], [0.02840, 0.13383, 0.83777]])
ACES_OUT = np.array([[1.60475, -0.53108, -0.07367], [-0.10208, 1.10813, -0.00605], [-0.00327, -0.07276, 1.07602]])


def aces_hill(rgb):
    v = rgb @ ACES_IN.T
    a = v * (v + 0.0245786) - 0.000090537
    b = v * (0.983729 * v + 0.4329510) + 0.238081
    return np.clip((a / b) @ ACES_OUT.T, 0.0, 1.0)


def srgb(x):
    return np.where(x <= 0.0031308, 12.92 * x, 1.055 * np.power(x, 1 / 2.4) - 0.055)


def read_rgb(path):
    with OpenEXR.File(path) as f:
        ch = f.channels()
        if "RGBA" in ch or "RGB" in ch:
            px = ch["RGBA" if "RGBA" in ch else "RGB"].pixels
            return np.asarray(px, dtype=np.float32)[..., :3]
        names = sorted(k for k in ch if k.split(".")[-1] in ("R", "G", "B"))
        if len(names) != 3:
            raise SystemExit(f"no RGB channels in {path}: {list(ch)}")
        order = {n.split(".")[-1]: n for n in names}
        return np.stack([np.asarray(ch[order[c]].pixels, np.float32) for c in "RGB"], -1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("exr")
    ap.add_argument("png")
    ap.add_argument("--exposure", type=float, default=0.0, help="stops")
    a = ap.parse_args()
    rgb = np.nan_to_num(read_rgb(a.exr), nan=0.0, posinf=0.0).clip(0) * 2.0 ** a.exposure
    out = (srgb(aces_hill(rgb)) * 255 + 0.5).astype(np.uint8)
    Image.fromarray(out).save(a.png)
    print(f"{a.png}: {out.shape[1]}x{out.shape[0]}, linear max {rgb.max():.2f}")


if __name__ == "__main__":
    main()
