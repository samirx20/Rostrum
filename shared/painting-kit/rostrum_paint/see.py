"""Seeing: the painter's eyes. Arrays in (HxWx3 or HxWx4 uint8, straight alpha), PIL images out.

Canvas pixels are the only coordinates anywhere: grid labels, zoom boxes and outlines are all canvas pixels.

Enlarging (`sampling`): "pixels" blows each canvas pixel up into a sharp square, to place strokes on the pixel grid;
"smooth" resamples (bicubic up, Lanczos down), to judge texture, edges and gradients as they will be seen. "auto"
(the default) is pixels when a grid is drawn and smooth when it isn't (grid=0): the grid is for placing, no grid
is for looking.
"""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw, ImageFont

GRIDS = (1, 2, 5, 10, 16, 25, 32, 50, 64, 100, 128, 200, 256, 500, 512, 1000, 1024, 4096)
BG = (28, 28, 28)
SAMPLINGS = ("auto", "pixels", "smooth")

def _font(px):
    try:
        return ImageFont.load_default(size=px)
    except TypeError:
        return ImageFont.load_default()


def check_zoom(zoom, w, h):
    """(x, y, w, h) ints inside the canvas from a canvas-px box (x0, y0, x1, y1); raises ValueError saying what is wrong."""
    if zoom is None:
        return 0, 0, w, h
    x0, y0, x1, y1 = (int(round(v)) for v in zoom)
    if x1 <= x0 or y1 <= y0:
        raise ValueError(f"zoom {list(zoom)}: x1 must be above x0 and y1 above y0")
    if x0 < 0 or y0 < 0 or x1 > w or y1 > h:
        raise ValueError(f"zoom {list(zoom)} is outside the {w}x{h} canvas (x 0..{w}, y 0..{h})")
    return x0, y0, x1 - x0, y1 - y0


def _flat(img, checker=True):
    """RGB float 0..1 from RGB or straight-alpha RGBA; transparency shows a checkerboard (or black)."""
    a = np.asarray(img)
    rgb = a[..., :3].astype(np.float32) / 255
    if a.shape[2] == 3:
        return rgb
    h, w = a.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w]
    under = np.where(((xx // 8 + yy // 8) % 2 == 0)[..., None], 0.35, 0.55) if checker else np.zeros((h, w, 1))
    al = a[..., 3:4].astype(np.float32) / 255
    return rgb * al + under * (1 - al)

def _u8(a):
    return (np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8)


def _scaled(rgb, zoom, size, sampling="smooth"):
    x, y, zw, zh = zoom
    s = size / zw
    img = Image.fromarray(_u8(rgb[y:y + zh, x:x + zw]))
    how = Image.LANCZOS if s < 1.5 else Image.NEAREST if sampling == "pixels" and s >= 3 else Image.BICUBIC
    return img.resize((size, max(1, round(zh * s))), how), s


def _grid(img, zoom, s, grid):
    """Label a grid in canvas pixels onto `img`, which shows `zoom` at scale `s`. Lines sit on pixel edges."""
    x, y, zw, zh = zoom
    grid = grid or next(g for g in GRIDS if zw / g <= 10)
    lay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d, f = ImageDraw.Draw(lay), _font(13)
    for k in range(-(-x // grid) * grid, x + zw + 1, grid):
        px = round((k - x) * s)
        if 0 <= px < img.width:
            d.line([(px, 0), (px, img.height)], fill=(255, 0, 255, 120))
            d.rectangle([px + 1, 0, px + 8 * len(str(k)) + 4, 15], fill=(0, 0, 0, 175))
            d.text((px + 3, 1), str(k), fill=(255, 255, 255, 255), font=f)
    for k in range(-(-y // grid) * grid, y + zh + 1, grid):
        py = round((k - y) * s)
        if 0 <= py < img.height:
            d.line([(0, py), (img.width, py)], fill=(0, 255, 255, 120))
            d.rectangle([0, py + 1, 8 * len(str(k)) + 4, py + 16], fill=(0, 0, 0, 175))
            d.text((2, py + 2), str(k), fill=(255, 255, 255, 255), font=f)
    return Image.alpha_composite(img.convert("RGBA"), lay).convert("RGB")


def _titled(img, text, h=22):
    can = Image.new("RGB", (img.width, img.height + h), BG)
    can.paste(img, (0, h))
    ImageDraw.Draw(can).text((6, 3), text, fill=(235, 235, 235), font=_font(15))
    return can


def _hstack(imgs, gap=10):
    can = Image.new("RGB", (sum(i.width for i in imgs) + gap * (len(imgs) - 1), max(i.height for i in imgs)), BG)
    x = 0
    for i in imgs:
        can.paste(i, (x, 0))
        x += i.width + gap
    return can


def _panel(rgb, zoom, size, grid, sampling="auto"):
    if sampling not in SAMPLINGS:
        raise ValueError(f"sampling must be one of {SAMPLINGS}, got {sampling!r}")
    img, s = _scaled(rgb, zoom, size, ("pixels" if grid != 0 else "smooth") if sampling == "auto" else sampling)
    return _grid(img, zoom, s, grid) if grid != 0 else img, s


def view(img, zoom=None, grid=None, size=1200, label=None, checker=True, sampling="auto"):
    """Crop `zoom` (x0, y0, x1, y1 canvas px), scale to `size` px wide, label a grid in canvas px (grid=0: none).
    sampling: "pixels" | "smooth" | "auto" (pixels with a grid, smooth without; module doc)."""
    if size < 16:
        raise ValueError("size must be at least 16 px")
    rgb = _flat(img, checker)
    zoom = check_zoom(zoom, rgb.shape[1], rgb.shape[0])
    out = _panel(rgb, zoom, size, grid, sampling)[0]
    return _titled(out, label) if label else out


def changed_box(a, b, thresh=1):
    """(x0, y0, x1, y1) of pixels where a and b differ by more than `thresh` (0..255, any channel), or None."""
    if a.shape != b.shape:
        a, b = (np.dstack([x, np.full(x.shape[:2], 255, np.uint8)]) if x.shape[2] == 3 else x for x in (a, b))
    d = np.abs(np.asarray(a, np.int16) - np.asarray(b, np.int16)).max(axis=2) > thresh
    if not d.any():
        return None
    ys, xs = np.where(d)
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def _diff(a, b):
    """Dark picture of `b` with every changed pixel burned red/yellow by how much it changed."""
    d = np.abs(a - b).max(axis=2)
    base = np.repeat(b.mean(axis=2, keepdims=True) * 0.35, 3, axis=2)
    k = np.clip(d * 4, 0, 1)[..., None]
    hot = np.stack([np.ones_like(d), np.clip(d * 2, 0, 1), np.zeros_like(d)], axis=2)
    return base * (1 - k) + hot * k


def before_after(a, b, zoom=None, grid=None, size=600, sampling="auto"):
    """before | after | difference, the changed box outlined in all three and its coordinates written on top."""
    if a.shape[:2] != b.shape[:2]:
        raise ValueError(f"before is {a.shape[1]}x{a.shape[0]} but after is {b.shape[1]}x{b.shape[0]}: they must be the same size")
    box = changed_box(a, b)
    fa, fb = _flat(a), _flat(b)
    zoom_t = check_zoom(zoom, fa.shape[1], fa.shape[0])
    panels = []
    for name, arr in (("BEFORE", fa), ("AFTER", fb), ("DIFFERENCE", _diff(fa, fb))):
        img, s = _panel(arr, zoom_t, size, grid, sampling)
        if box:
            x0, y0, x1, y1 = box
            ImageDraw.Draw(img).rectangle([(x0 - zoom_t[0]) * s - 2, (y0 - zoom_t[1]) * s - 2,
                                           (x1 - zoom_t[0]) * s + 2, (y1 - zoom_t[1]) * s + 2], outline=(0, 255, 0), width=2)
        panels.append(_titled(img, name))
    note = f"changed box x {box[0]}..{box[2]}, y {box[1]}..{box[3]}" if box else "nothing changed"
    return _titled(_hstack(panels), note)


def _grey(rgb):
    return rgb @ np.array([0.2126, 0.7152, 0.0722], np.float32)


def values(img, steps=5, size=600):
    """Colour | greyscale | greyscale in `steps` value steps (shows the big shapes), with each step's share."""
    if steps < 2:
        raise ValueError("steps must be at least 2")
    rgb = _flat(img)
    g = _grey(rgb)
    post = np.minimum(np.floor(g * steps), steps - 1) / (steps - 1)
    zoom = (0, 0, rgb.shape[1], rgb.shape[0])
    panels = [_titled(_scaled(arr, zoom, size)[0], name) for name, arr in (
        ("COLOUR", rgb), ("GREY", np.repeat(g[..., None], 3, 2)), (f"{steps} VALUE STEPS", np.repeat(post[..., None], 3, 2)))]
    share = np.bincount(np.minimum((g * steps).astype(int), steps - 1).ravel(), minlength=steps) / g.size
    return _titled(_hstack(panels), "share per step (dark->light): " + "  ".join(f"{v * 100:.0f}%" for v in share))


def small(img, width=480):
    """The canvas as seen small (thumbnail, far away). No grid: that is the point."""
    rgb = _flat(img)
    h, w = rgb.shape[:2]
    if not 16 <= width <= w * 4:
        raise ValueError(f"width {width}: use 16..{w * 4}")
    out = Image.fromarray(_u8(rgb)).resize((width, max(1, round(h * width / w))), Image.LANCZOS)
    return _titled(out, f"small: {width}px wide")


def side_by_side(img, ref_path, size=600, diff=False):
    """REFERENCE | WORK (| DIFFERENCE). The reference is stretched to the canvas size so pixels line up."""
    work = _flat(img)
    h, w = work.shape[:2]
    ref = np.asarray(Image.open(ref_path).convert("RGB").resize((w, h), Image.LANCZOS), np.float32) / 255
    items = [("REFERENCE", ref), ("WORK", work)]
    if diff:
        items.append(("DIFFERENCE (brighter = further off)", np.repeat(np.clip(np.abs(ref - work).mean(axis=2, keepdims=True) * 3, 0, 1), 3, 2)))
    return _hstack([_titled(_scaled(arr, (0, 0, w, h), size)[0], name) for name, arr in items])


def onion(now, before, after, opacity=0.35):
    """`now` over its neighbours: earlier drawings tinted red, later ones green, nearer frames stronger.
    `before` and `after` are lists of HxWx4 uint8, nearest first. Returns HxWx4 uint8 straight alpha."""
    h, w = now.shape[:2]
    layers = []
    for imgs, tint in ((before, (1.0, 0.2, 0.2)), (after, (0.2, 0.9, 0.2))):
        layers += [(i, tint, opacity * (1 - i_n / (len(imgs) + 1))) for i_n, i in enumerate(imgs)]
    layers.sort(key=lambda t: t[2])                     # weakest first: nearer ones land on top
    out = np.zeros((h, w, 4), np.float32)               # premultiplied
    for src, tint, strength in layers:
        s = np.asarray(src, np.float32) / 255
        lum = _grey(s[..., :3] / np.maximum(s[..., 3:4], 1e-6))[..., None]
        a = s[..., 3:4] * strength
        out = np.concatenate([np.array(tint, np.float32) * (0.4 + 0.6 * lum) * a, a], axis=2) + out * (1 - a)
    n = np.asarray(now, np.float32) / 255
    na = n[..., 3:4]
    out = np.concatenate([n[..., :3] * na, na], axis=2) + out * (1 - na)    # `now` is premultiplied here
    al = out[..., 3:4]
    rgb = np.where(al > 1e-6, out[..., :3] / np.maximum(al, 1e-6), 0)
    return _u8(np.concatenate([rgb, al], axis=2))
