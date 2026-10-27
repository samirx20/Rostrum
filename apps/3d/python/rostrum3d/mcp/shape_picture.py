"""look_shape's picture: the front, side and top outlines on one scale, side by side (PIL).

Each panel is its mask scaled up smoothly (bilinear, then cut at half), filled light with a dark 2 px edge; lines at each
tenth of the height (front and side), the X = 0 line dashed (front and top), thin spots ringed red, a scale bar.
"""
from __future__ import annotations

import math

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

TALL = 440                      # the panels' height in px (the tallest view)
PAD, GAP, HEAD, FOOT = 46, 36, 34, 56
BG, FILL, EDGE, GRID, MID, THIN, INK = (30, 32, 36), (205, 208, 214), (20, 22, 26), (72, 76, 84), (110, 170, 255), (255, 70, 60), (230, 232, 236)


def _font(size):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:                                   # an older Pillow: its one bitmap font
        return ImageFont.load_default()


def _panel(mask: np.ndarray, px: float) -> Image.Image:
    """mask [h, v] (row index = picture row) → an RGB panel, px pixels per cell."""
    rows = (mask.T * 255).astype(np.uint8)
    w, h = max(1, round(rows.shape[1] * px)), max(1, round(rows.shape[0] * px))
    m = Image.fromarray(rows, "L").resize((w, h), Image.BILINEAR).filter(ImageFilter.GaussianBlur(px * 0.6))
    m = m.point(lambda v: 255 if v >= 128 else 0)
    edge = Image.fromarray(np.asarray(m) & ~np.asarray(m.filter(ImageFilter.MinFilter(5))))
    out = Image.new("RGB", (w, h), BG)
    out.paste(FILL, (0, 0, w, h), m)
    out.paste(EDGE, (0, 0, w, h), edge)
    return out


def _nice(m: float) -> float:
    e = 10 ** math.floor(math.log10(m))
    return max(k * e for k in (1, 2, 5) if k * e <= m)


def _length(m: float) -> str:
    return f"{m:g} m" if m >= 1 else f"{m * 100:g} cm" if m >= 0.01 else f"{m * 1000:g} mm"


def draw(v, m: dict, spots: list[dict], dest, title: str):
    """Write the three-panel picture of Views `v` with measures `m` to `dest`."""
    front, side, top = v.front, v.side[::-1], v.top[:, :]           # side: +Z (its front) on the left
    ny = v.front.shape[1]
    px = TALL / max(ny, v.top.shape[1])
    flipy = lambda a: a[:, ::-1]  # noqa: E731  picture rows run down; y runs up
    panels = [("front", _panel(flipy(front), px)), ("side (from its left)", _panel(flipy(side), px)),
              ("top (front down)", _panel(top, px))]
    W = PAD * 2 + sum(p.width for _, p in panels) + GAP * 2
    H = HEAD + max(p.height for _, p in panels) + FOOT
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    f, small = _font(15), _font(12)
    c, (sx, sy, sz) = v.cell, v.start
    to_px = lambda i: (i + 0.5) * px  # noqa: E731  a cell index → panel px (its centre)
    x = PAD
    places = []
    for name, p in panels:
        img.paste(p, (x, HEAD))
        d.text((x, 8), name, fill=INK, font=f)
        places.append(x)
        x += p.width + GAP
    fx, sxp, tx = places
    yrow = lambda y: HEAD + (ny - 0.5 - (y - sy) / c) * px  # noqa: E731  a height (m) → picture row
    for r in m["levels"]:
        yy = yrow(r["y"])
        for x0, p in ((fx, panels[0][1]), (sxp, panels[1][1])):
            d.line([(x0, yy), (x0 + p.width, yy)], fill=GRID, width=1)
        d.text((fx - 36, yy - 7), f'{r["percent"]}%', fill=GRID, font=small)
    mid = (-sx / c)                                                 # X = 0 as a cell index
    for x0, h in ((fx, panels[0][1].height), (tx, panels[2][1].height)):
        cx = x0 + to_px(mid)
        for s in range(0, h, 12):
            d.line([(cx, HEAD + s), (cx, HEAD + s + 6)], fill=MID, width=1)
    nz = v.side.shape[0]
    for s in spots:
        ax, ay, az = s["at"]
        r = max(6, s["thickness"] / c * px)
        for cx, cy in ((fx + to_px((ax - sx) / c), yrow(ay)), (sxp + to_px(nz - 1 - (az - sz) / c), yrow(ay)),
                       (tx + to_px((ax - sx) / c), HEAD + to_px((az - sz) / c))):
            d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=THIN, width=2)
    bar = _nice(max(m["height"] / 3, m["width"] / 6, c))
    by = H - 28
    d.line([(PAD, by), (PAD + bar / c * px, by)], fill=INK, width=3)
    d.text((PAD + bar / c * px + 8, by - 8), _length(bar), fill=INK, font=f)
    d.text((PAD + bar / c * px + 80, by - 8), f'{title}: {_length(round(m["height"], 3))} tall, '
           f'{_length(round(m["width"], 3))} wide, {_length(round(m["depth"], 3))} deep', fill=INK, font=f)
    img.save(dest)
