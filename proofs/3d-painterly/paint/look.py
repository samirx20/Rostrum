"""The painter's eyes: zoomed views with a canvas-pixel grid, UV-guide overlays, before/after.

    python look.py view <in.png> <out.png> [--zoom x y w h] [--grid N] [--size PX]
    python look.py guide <texture.png> <uv_guide.png> <out.png> [--opacity 0.6]
    python look.py compare <a.png> <b.png> <out.png> [--size PX]
    python look.py pick <in.png> x y [--radius R]      (prints the average colour, 0..1 sRGB)
"""
import argparse
import numpy as np
from PIL import Image, ImageDraw, ImageFont


def _font(px):
    try:
        return ImageFont.load_default(size=px)
    except TypeError:  # Pillow < 10.1
        return ImageFont.load_default()


def view(src, out, zoom=None, grid=None, size=1200):
    """Crop canvas region `zoom`=(x, y, w, h), scale to `size` px wide, label a grid in canvas pixels."""
    im = Image.open(src).convert("RGB")
    x, y, w, h = zoom or (0, 0, im.width, im.height)
    if w <= 0 or h <= 0 or x >= im.width or y >= im.height:
        raise ValueError(f"zoom {zoom} is outside the {im.width}x{im.height} image")
    s = size / w
    v = im.crop((x, y, x + w, y + h)).resize((size, max(1, round(h * s))),
                                            Image.NEAREST if s >= 3 else Image.LANCZOS).convert("RGBA")
    if grid is None:  # about 8 lines across, on a round number
        grid = next(g for g in (1, 2, 5, 10, 16, 25, 32, 50, 64, 100, 128, 200, 256, 500, 512, 1000, 1024, 4096)
                    if w / g <= 10)
    lay = Image.new("RGBA", v.size, (0, 0, 0, 0))
    d, f = ImageDraw.Draw(lay), _font(13)
    for k in range((x // grid) * grid, x + w + 1, grid):
        px = round((k - x) * s)
        if 0 <= px < v.width:
            d.line([(px, 0), (px, v.height)], fill=(255, 0, 255, 110))
            d.rectangle([px + 1, 0, px + 8 * len(str(k)) + 4, 15], fill=(0, 0, 0, 170))
            d.text((px + 3, 1), str(k), fill=(255, 255, 255, 255), font=f)
    for k in range((y // grid) * grid, y + h + 1, grid):
        py = round((k - y) * s)
        if 0 <= py < v.height:
            d.line([(0, py), (v.width, py)], fill=(0, 255, 255, 110))
            d.rectangle([0, py + 1, 8 * len(str(k)) + 4, py + 16], fill=(0, 0, 0, 170))
            d.text((2, py + 2), str(k), fill=(255, 255, 255, 255), font=f)
    Image.alpha_composite(v, lay).convert("RGB").save(out)


def guide(tex, uv, out, opacity=0.6):
    """Overlay a UV-layout guide (lines/labels on transparent, same size as the texture)."""
    t = Image.open(tex).convert("RGBA")
    g = Image.open(uv)
    if abs(g.width / g.height - t.width / t.height) > 1e-3:
        raise ValueError(f"guide {g.size} and texture {t.size} have different shapes")
    if g.mode != "RGBA":  # no alpha: treat bright lines on black as the guide
        lum = g.convert("L")
        g = g.convert("RGBA")
        g.putalpha(lum)
    g = g.resize(t.size, Image.LANCZOS)
    a = (np.asarray(g.getchannel("A"), np.float32) * opacity).astype(np.uint8)
    g.putalpha(Image.fromarray(a))
    Image.alpha_composite(t, g).convert("RGB").save(out)


def compare(a, b, out, size=900, labels=("A", "B")):
    """Side by side at the same height, labelled."""
    ims = [Image.open(p).convert("RGB") for p in (a, b)]
    h = min(size, max(i.height for i in ims))
    ims = [i.resize((round(i.width * h / i.height), h), Image.LANCZOS) for i in ims]
    can = Image.new("RGB", (ims[0].width + ims[1].width + 12, h + 24), (30, 30, 30))
    d, x = ImageDraw.Draw(can), 0
    for im, lab in zip(ims, labels):
        can.paste(im, (x, 24))
        d.text((x + 4, 4), lab, fill=(255, 255, 255), font=_font(16))
        x += im.width + 12
    can.save(out)


def pick(src, x, y, radius=2):
    a = np.asarray(Image.open(src).convert("RGB"), np.float32) / 255
    p = a[max(0, y - radius):y + radius + 1, max(0, x - radius):x + radius + 1].reshape(-1, 3).mean(0)
    return tuple(round(float(c), 3) for c in p)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("view"); p.add_argument("src"); p.add_argument("out")
    p.add_argument("--zoom", type=int, nargs=4); p.add_argument("--grid", type=int); p.add_argument("--size", type=int, default=1200)
    p = sub.add_parser("guide"); p.add_argument("tex"); p.add_argument("uv"); p.add_argument("out")
    p.add_argument("--opacity", type=float, default=0.6)
    p = sub.add_parser("compare"); p.add_argument("a"); p.add_argument("b"); p.add_argument("out")
    p.add_argument("--size", type=int, default=900)
    p = sub.add_parser("pick"); p.add_argument("src"); p.add_argument("x", type=int); p.add_argument("y", type=int)
    p.add_argument("--radius", type=int, default=2)
    a = ap.parse_args()
    if a.cmd == "view":
        view(a.src, a.out, a.zoom, a.grid, a.size)
    elif a.cmd == "guide":
        guide(a.tex, a.uv, a.out, a.opacity)
    elif a.cmd == "compare":
        compare(a.a, a.b, a.out, a.size, labels=(a.a.split("\\")[-1].split("/")[-1], a.b.split("\\")[-1].split("/")[-1]))
    else:
        print(*pick(a.src, a.x, a.y, a.radius))
