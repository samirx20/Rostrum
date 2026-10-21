"""Surface maps from painted images (a painter's helper, not a look):
  height  <albedo.png> <out_height.png> [--radius 6]   paint thickness from the painting itself:
          local luminance contrast (high-pass), so brush ridges and stroke edges catch light.
  normal  <height.png> <out_normal.png> [--strength 4]  tangent-space normal map (OpenGL, +Y up)
          from a height map; tiling-safe (wraps at the edges).

  uv run --with numpy --with pillow python -I maps.py height|normal in.png out.png [...]
"""
import argparse
import numpy as np
from PIL import Image, ImageFilter


def height_from_albedo(path, radius):
    im = Image.open(path).convert("L")
    blur = im.filter(ImageFilter.GaussianBlur(radius))
    a = np.asarray(im, np.float32) / 255; b = np.asarray(blur, np.float32) / 255
    h = 0.5 + 1.5 * (a - b)
    return np.clip(h, 0, 1)


def normal_from_height(path, strength):
    h = np.asarray(Image.open(path).convert("L"), np.float32) / 255
    dx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) * 0.5 * strength
    dy = (np.roll(h, -1, 0) - np.roll(h, 1, 0)) * 0.5 * strength
    n = np.stack([-dx, dy, np.ones_like(h)], -1)   # image rows run down, UV v runs up -> +dy
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    return n * 0.5 + 0.5


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("kind", choices=["height", "normal"])
    ap.add_argument("src"); ap.add_argument("out")
    ap.add_argument("--radius", type=float, default=6.0)
    ap.add_argument("--strength", type=float, default=4.0)
    a = ap.parse_args()
    img = height_from_albedo(a.src, a.radius) if a.kind == "height" else normal_from_height(a.src, a.strength)
    Image.fromarray((img * 255 + 0.5).astype(np.uint8)).save(a.out)
    print("wrote", a.out)


if __name__ == "__main__":
    main()
