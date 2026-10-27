"""Coverage: how much of a drawing's canvas is painted, per paint layer and all together, and where bare paper shows.

    report(frame, w, h, amount)  -> {"painted", "thin", "bare", "layers": [...], "gaps": [...]}, bare mask
    picture(rgba, bare, gaps)    -> the drawing with bare paper tinted and each gap boxed and numbered

A pixel is **painted** when the paint over it is at least SOLID opaque, **thin** between THIN and SOLID (a pale glaze the
background shows through), **bare** below THIN (the paper, or the composition's background, shows as it is). `amount` is
drawn so far (write_on.py): the report is of the paint as it stands at that moment, the stroke the pen is on as far as
it got. Gaps are the bare areas, found on a grid of CELL px and given as canvas px boxes, biggest first, with a word for
their shape ("strip along the bottom edge, the full width", "patch at the top-left corner"), so a wash that stops short of an edge is named, not guessed.
"""
from __future__ import annotations

import numpy as np

from . import write_on

SOLID, THIN = 0.6, 0.15     # alpha (0..1) at and above which a pixel is painted / at least thinly painted
CELL = 8                    # the grid gaps are found on (px); a gap smaller than MIN_SHARE of the canvas is left out
MIN_SHARE = 0.002
MAX_GAPS = 8


def _alpha(rgba: np.ndarray) -> np.ndarray:
    return rgba[..., 3].astype(np.float32) / 255


def _layer_frame(frame: dict, li: int, amount: float) -> tuple[dict, float]:
    """Paint layer `li` alone, and how much of it is drawn when the whole drawing is `amount` drawn."""
    marks = write_on.marks(frame)
    k, f = write_on.cut(frame, amount)
    mine = [(i, w) for i, (l, _, w) in enumerate(marks) if l == li]
    total = sum(w for _, w in mine)
    done = sum(w for i, w in mine if i < k) + sum(w * f for i, w in mine if i == k)
    alone = {**frame, "paints": [frame["paints"][li]]}
    return alone, (done / total if total else 1.0)


def _shares(a: np.ndarray) -> dict:
    n = a.size
    painted = float((a >= SOLID).sum()) / n
    thin = float(((a >= THIN) & (a < SOLID)).sum()) / n
    return {"painted": round(painted, 4), "thin": round(thin, 4), "bare": round(1 - painted - thin, 4)}


def _components(grid: np.ndarray) -> list[list[tuple[int, int]]]:
    """4-connected groups of True cells (a small grid: a plain flood fill)."""
    seen = np.zeros_like(grid, bool)
    out = []
    H, W = grid.shape
    for y0, x0 in zip(*np.nonzero(grid)):
        if seen[y0, x0]:
            continue
        stack, cells = [(y0, x0)], []
        seen[y0, x0] = True
        while stack:
            y, x = stack.pop()
            cells.append((y, x))
            for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
                if 0 <= ny < H and 0 <= nx < W and grid[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    stack.append((ny, nx))
        out.append(cells)
    return out


def _shape(box, w, h) -> str:
    """In words: "strip along the bottom edge, the full width", "patch at the top-left corner", "patch inside the canvas"."""
    x0, y0, x1, y1 = box
    bw, bh = x1 - x0, y1 - y0
    wide, tall = bw >= 0.9 * w, bh >= 0.9 * h
    if wide and tall:
        return "area over most of the canvas"
    if wide or tall:
        thin = (bh if wide else bw) <= 0.25 * (h if wide else w)
        ends = (("top", y0 <= 0), ("bottom", y1 >= h)) if wide else (("left", x0 <= 0), ("right", x1 >= w))
        at = [n for n, hit in ends if hit]
        where = f"along the {at[0]} edge" if len(at) == 1 else "across the middle" if wide else "down the middle"
        return f"{'strip' if thin else 'band'} {where}, the full {'width' if wide else 'height'}"
    v = "top" if y0 <= 0 else "bottom" if y1 >= h else ""
    s_ = "left" if x0 <= 0 else "right" if x1 >= w else ""
    if v and s_:
        return f"patch at the {v}-{s_} corner"
    if v or s_:
        return f"patch on the {v or s_} edge"
    return "patch inside the canvas"


def gaps(bare: np.ndarray) -> list[dict]:
    h, w = bare.shape
    gh, gw = -(-h // CELL), -(-w // CELL)
    padded = np.zeros((gh * CELL, gw * CELL), bool)
    padded[:h, :w] = bare
    grid = padded.reshape(gh, CELL, gw, CELL).mean(axis=(1, 3)) >= 0.5
    out = []
    for cells in _components(grid):
        ys, xs = np.array(cells).T
        box = [int(xs.min() * CELL), int(ys.min() * CELL), int(min(w, (xs.max() + 1) * CELL)), int(min(h, (ys.max() + 1) * CELL))]
        x0, y0, x1, y1 = box
        share = float(bare[y0:y1, x0:x1].sum()) / bare.size
        if share < MIN_SHARE:
            continue
        out.append({"box": box, "share": round(share, 4), "shape": _shape(box, w, h),
                    "words": f"bare paper: a {x1 - x0}×{y1 - y0} px {_shape(box, w, h)}, x {x0}–{x1}, y {y0}–{y1}"})
    out.sort(key=lambda g: -g["share"])
    return out[:MAX_GAPS]


def _cut(a: np.ndarray, window) -> np.ndarray:
    """The window [x0, y0, x1, y1] of a canvas array (canvas px, may reach past the canvas: nothing is painted there)."""
    if window is None:
        return a
    x0, y0, x1, y1 = window
    out = np.zeros((y1 - y0, x1 - x0) + a.shape[2:], a.dtype)
    h, w = a.shape[:2]
    cx0, cy0, cx1, cy1 = max(0, x0), max(0, y0), min(w, x1), min(h, y1)
    if cx1 > cx0 and cy1 > cy0:
        out[cy0 - y0:cy1 - y0, cx0 - x0:cx1 - x0] = a[cy0:cy1, cx0:cx1]
    return out


def report(frame: dict, w: int, h: int, amount: float = 1.0, window=None, comp_size=None) -> tuple[dict, np.ndarray, np.ndarray]:
    """(the report, the drawing's RGBA as it stands, the bare mask), over `window` (canvas px [x0, y0, x1, y1]: the
    part the composition shows, `comp_size` px) or the whole canvas. Gap boxes are canvas px either way; with a window
    each gap also has `comp_box`, the same box in composition px."""
    rgba = _cut(write_on.pixels(frame, w, h, amount), window)
    a = _alpha(rgba)
    layers = []
    for li, paint in enumerate(frame.get("paints", [])):
        alone, share = _layer_frame(frame, li, amount)
        layers.append({"paint": paint["id"], "name": paint.get("name", paint["id"]), "drawn": round(share, 4),
                       **(_shares(_alpha(_cut(write_on.pixels(alone, w, h, share), window))) if paint.get("visible", True)
                          else {"painted": 0.0, "thin": 0.0, "bare": 1.0, "hidden": True})})
    bare = a < THIN
    found = gaps(bare)
    if window is not None:          # boxes back in canvas px; the words name the edges of the window (the frame)
        for g in found:
            g["box"] = [g["box"][0] + window[0], g["box"][1] + window[1], g["box"][2] + window[0], g["box"][3] + window[1]]
            x0, y0, x1, y1 = g["box"]
            g["words"] = f"bare paper: a {x1 - x0}×{y1 - y0} px {g['shape']}, canvas x {x0}–{x1}, y {y0}–{y1}"
            if comp_size:
                kx, ky = comp_size[0] / (window[2] - window[0]), comp_size[1] / (window[3] - window[1])
                cb = [round((x0 - window[0]) * kx), round((y0 - window[1]) * ky), round((x1 - window[0]) * kx), round((y1 - window[1]) * ky)]
                g["comp_box"] = cb
                g["words"] += f" (composition x {cb[0]}–{cb[2]}, y {cb[1]}–{cb[3]})"
    return {**_shares(a), "layers": layers, "gaps": found}, rgba, bare


def picture(rgba: np.ndarray, bare: np.ndarray, found: list[dict], window=None):
    """The drawing (its window) over light grey, bare paper tinted magenta, each gap boxed and numbered (1 = the biggest)."""
    from PIL import Image, ImageDraw
    a = _alpha(rgba)[..., None]
    out = rgba[..., :3].astype(np.float32) * a + 200 * (1 - a)
    out[bare] = out[bare] * 0.35 + np.array([255, 0, 200], np.float32) * 0.65
    im = Image.fromarray(out.astype(np.uint8))
    d = ImageDraw.Draw(im)
    lw = max(2, im.width // 400)
    for n, g in enumerate(found, 1):
        x0, y0, x1, y1 = (np.array(g["box"]) - ([window[0], window[1]] * 2 if window else 0)).tolist()
        d.rectangle([x0, y0, x1 - 1, y1 - 1], outline=(255, 255, 0), width=lw)
        d.text((x0 + 2 * lw, y0 + 2 * lw), str(n), fill=(255, 255, 0))
    return im


def comp_window(layer: dict, comp: dict, w: int, h: int, t: float):
    """The canvas px [x0, y0, x1, y1] the composition's area covers at t (the frame at rest), for a drawing placed straight
    in the composition (not in a group, not turned or tilted); None otherwise (the whole canvas is reported then)."""
    from .evaluate import value_at
    if layer not in comp.get("layers", []):
        return None
    v = {k: float(value_at(layer, k, t)) for k in ("x", "y", "scale", "scaleX", "scaleY", "anchorX", "anchorY", "rotation", "tiltX", "tiltY")}
    if v["rotation"] % 360 or v["tiltX"] or v["tiltY"]:
        return None
    sx, sy = v["scale"] * v["scaleX"], v["scale"] * v["scaleY"]
    if not sx or not sy:
        return None
    ox, oy = v["anchorX"] * w - v["x"] / sx, v["anchorY"] * h - v["y"] / sy
    xs = sorted((ox, ox + comp["width"] / sx))
    ys = sorted((oy, oy + comp["height"] / sy))
    return [int(round(xs[0])), int(round(ys[0])), int(round(xs[1])), int(round(ys[1]))]
