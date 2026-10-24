"""The picture of the world for look_world and Export › Picture › Area: which world rectangle, the engine's world picture of
it (the same one the canvas draws), and the marks of look_world on top (veil, outline, path, key outlines, ruler)."""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from rostrum_core.errors import RostrumError, codes

from rostrum2d.engine import Engine

from . import render, world_facts as wf

AREAS = {"area": {"anyOf": [{"type": "string", "enum": ["all", "frame"]},
                            {"type": "object", "properties": {k: {"type": "number"} for k in ("x", "y", "w", "h")}, "required": ["x", "y", "w", "h"]}],
                  "description": 'What part of the world: "all" (every layer and the frame\'s whole path; default), "frame" (the frame\'s own box now), '
                                 "or {x, y, w, h} in world px."}}
MOST_PX = 8192                      # the engine's limit: a world picture is at most this many px a side
VEIL, FRAME, PATH, KEY = 0.55, (255, 210, 63), (0, 229, 255), (255, 255, 255)


def area_rect(where: str, comp: dict, area, t: float) -> tuple[float, float, float, float]:
    """The world rectangle (x, y, w, h) an `area` names, at time t. "all" and "frame" get a margin so the edge isn't the picture's."""
    if isinstance(area, dict):
        x, y, w, h = (float(area[k]) for k in ("x", "y", "w", "h"))
        if w <= 0 or h <= 0:
            raise RostrumError(codes.BAD_ARGUMENT, where, f"area {w:g} × {h:g}", "must have a width and a height above 0")
        return x, y, w, h
    x0, y0, x1, y1 = wf.bounds(wf.quad(comp, t)) if area == "frame" else wf.everything(comp, t)
    pad = max(x1 - x0, y1 - y0, 100.0) * 0.04
    return x0 - pad, y0 - pad, x1 - x0 + 2 * pad, y1 - y0 + 2 * pad


def fitted(where: str, rect, width: int | None = None, scale: float | None = None) -> dict:
    """{x, y, w, h, scale}: the rectangle at a scale that makes it `width` px wide (or the given scale, 1 = a world px each),
    never past the engine's limit; a rectangle too big at the asked scale is refused with the scale that fits."""
    x, y, w, h = rect
    k = scale if scale else width / w
    fit = min(MOST_PX / w, MOST_PX / h)
    if scale and k > fit:
        raise RostrumError(codes.BAD_ARGUMENT, where, f"area {w:.0f} × {h:.0f} world px at scale {k:g}",
                           f"would be {w * k:.0f} × {h * k:.0f} px; at most {MOST_PX} px a side", hint=f"Use scale {math.floor(fit * 1000) / 1000:g} or less.")
    return {"x": x, "y": y, "w": w, "h": h, "scale": min(k, fit)}


def pixels_of(eng: Engine, t: float, shown: dict) -> Image.Image:
    """The engine's world picture at t for `shown`, straight-alpha RGBA."""
    import numpy as np
    view, w, h, stride = eng.pixels(t, world={k: shown[k] for k in ("x", "y", "w", "h", "scale")})
    try:
        return Image.fromarray(np.frombuffer(view, np.uint8).reshape(h, stride)[:, :w * 4].reshape(h, w, 4).copy(), "RGBA")
    finally:
        view.release()


def world_png(where: str, scene: dict, t: float, rect, width: int, dest: Path) -> dict:
    """Draw the world rectangle at t into `dest` (a PNG, over a dark ground where the world is see-through). Returns the rectangle and scale."""
    shown = fitted(where, rect, width=width)
    try:
        with Engine() as eng:
            eng.load(scene)
            img = pixels_of(eng, t, shown)
    except Exception as e:  # noqa: BLE001
        raise render._fail(where, f"the world at {t:.3f} s", e) from e
    ground = Image.new("RGBA", img.size, (38, 39, 45, 255))
    Image.alpha_composite(ground, img).convert("RGB").save(dest)
    return shown


def _step(span: float, px: float) -> float:
    """A round ruler step (1, 2, 5 × 10ⁿ world px) about 110 px apart on the picture."""
    want = 110 * span / px
    mag = 10 ** math.floor(math.log10(want))
    return next(m * mag for m in (1, 2, 5, 10) if m * mag >= want)


def draw_overlay(src: Path, dest: Path, comp: dict, t: float, shown: dict, path: bool) -> tuple[int, int]:
    """The marks of look_world on the world picture `src`, written to `dest`: the part outside the frame veiled, the frame's outline
    at t, with `path` its path (a dot per frame, cuts dashed) and a faint outline at each key, and a ruler of world px."""
    from rostrum2d.frame import view
    img = Image.open(src).convert("RGB")
    k, x0, y0 = shown["scale"], shown["x"], shown["y"]
    pt = lambda p: ((p[0] - x0) * k, (p[1] - y0) * k)
    inside = Image.new("L", img.size, 0)
    ImageDraw.Draw(inside).polygon([pt(p) for p in wf.quad(comp, t)], fill=255)
    img = Image.composite(img, Image.blend(img, Image.new("RGB", img.size, (0, 0, 0)), VEIL), inside)
    top = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d, small = ImageDraw.Draw(top), ImageFont.load_default(size=13)
    line = max(2, round(img.width / 640))
    frame, moves = view.of(comp), view.leaves_home(view.of(comp), comp)
    if path and moves:
        for kt in wf.key_times(comp):
            q = [pt(p) for p in wf.quad(comp, kt)]
            d.polygon(q, outline=(*KEY, 110), width=1)
            d.text((q[3][0] + 3, q[3][1] - 15), f"key {kt:.2f} s", fill=(*KEY, 170), font=small)
        times, cuts = wf.frame_times(comp), wf.cuts(comp)
        dots = [pt(_centre(wf.quad(comp, s))) for s in times]
        for (ta, a), (tb, b) in zip(zip(times, dots), zip(times[1:], dots[1:])):
            if any(ta < c <= tb for c in cuts):
                _dashed(d, a, b, (*PATH, 200), line)
            else:
                d.line([a, b], fill=(*PATH, 200), width=line)
        for p in dots:
            d.ellipse([p[0] - line, p[1] - line, p[0] + line, p[1] + line], fill=(*PATH, 255))
    outline = [pt(p) for p in wf.quad(comp, t)]
    d.polygon(outline, outline=(*FRAME, 255), width=line + 1)
    d.text((outline[0][0] + 4, outline[0][1] + 3), f"frame {t:.2f} s", fill=(*FRAME, 255), font=ImageFont.load_default(size=15))
    _ruler(d, img.size, shown, small)
    out = Image.alpha_composite(img.convert("RGBA"), top).convert("RGB")
    out.save(dest)
    return out.size


def _centre(q) -> tuple[float, float]:
    return (q[0][0] + q[2][0]) / 2, (q[0][1] + q[2][1]) / 2


def _dashed(d, a, b, fill, width, dash: float = 10.0):
    n = max(1, int(math.dist(a, b) / dash))
    for i in range(0, n, 2):
        d.line([(a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n),
                (a[0] + (b[0] - a[0]) * min(i + 1, n) / n, a[1] + (b[1] - a[1]) * min(i + 1, n) / n)], fill=fill, width=width)


def _ruler(d, size, shown, font):
    """World px along the top and left edges: a tick and a number every round step."""
    w, h = size
    step, k = _step(shown["w"], w), shown["scale"]
    for axis, lo, length in ((0, shown["x"], w), (1, shown["y"], h)):
        v = math.ceil(lo / step) * step
        while (v - lo) * k < length:
            p = (v - lo) * k
            xy = (p, 0, p, 9) if axis == 0 else (0, p, 9, p)
            d.line(xy, fill=(235, 235, 240, 255), width=1)
            d.text((p + 3, 9) if axis == 0 else (12, p - 7), f"{v:g}", fill=(235, 235, 240, 255), font=font, stroke_width=1, stroke_fill=(0, 0, 0, 255))
            v += step
