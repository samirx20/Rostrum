"""Where each layer sits on the canvas at a time, in composition pixels: the selection outline and click-to-pick.
No Qt.

A layer's box: its anchor sits at (x, y) inside its parent (a group's layers are placed from the group's top-left
corner); the box is w x h times scale, turned by `rot` degrees about the anchor (the selection outline turns with it;
picking turns the pointer back the same way). Tilt is not taken into account.
A layer's size is rostrum2d/sizes.py's (a text's is the engine's laid-out box, rostrum2d/textsize.py, on a path too).
A layer in an auto layout is where the layout puts it (rostrum2d/layout.py).
"""
from __future__ import annotations

import math

from rostrum2d import fields as F
from rostrum2d.evaluate import resolve
from rostrum2d.layout import solve
from rostrum2d.sizes import own_size
from rostrum2d.stepped import FIELD as STEPS


def _stepped(t: float, n: int, fps: float) -> float:
    """The time the engine draws at when timing is on n-frames (rostrum2d/stepped.py holds each pose for n frames)."""
    return math.floor(t * fps / n + 1e-9) * n / fps if n > 1 else t


def _compose(m, a, b, c, d, e, f):
    """Matrix m (a b c d e f: x' = a x + c y + e, y' = b x + d y + f) followed by the affine given after it."""
    return (m[0] * a + m[2] * b, m[1] * a + m[3] * b, m[0] * c + m[2] * d, m[1] * c + m[3] * d,
            m[0] * e + m[2] * f + m[4], m[1] * e + m[3] * f + m[5])


def boxes(comp: dict, t: float) -> list[dict]:
    """[{id, x, y, w, h, rot, ax, ay}] for every layer showing at t, bottom of the stack first (a group before its
    layers), all on screen (composition px): x, y is the unturned top-left of the box about its anchor, w x h the size on
    screen. A layer inside groups is carried through their whole chain (position, turn, scale, anchor), as the engine
    does: a layer sits at (x, y) inside its parent and turns and scales about its anchor, and a group's layers live in
    the group's own px, so they follow the group's turn. Also `lw lh lrot` (the box in its parent's px) and `m` (the
    parent's matrix, a b c d e f), for drags in the parent's frame. Each layer is read at the stepped time the engine
    draws it at (Timing > Steps on it, its group or the composition).
    """
    out: list[dict] = []
    fps = comp.get("fps", 30)
    placed: dict[float, dict] = {}

    def layout(te):                          # where auto layouts put their layers at time te (rostrum2d/layout.py)
        if te not in placed:
            placed[te] = solve(comp, te)
        return placed[te]

    def walk(layers, m, n, locked=False):
        for lay in layers:
            if lay["type"] == "camera" or lay.get("hidden"):         # not drawn: no box (and no scale)
                continue
            own = lay.get(STEPS, "group")
            ln = n if own == "group" else int(own)
            te = _stepped(t, ln, fps)
            p = {**resolve(lay, te), **layout(te).get(lay["id"], {})}
            if not (p["start"] <= te < p["end"]):
                continue
            w, h = own_size(lay["type"], p)
            sx, sy = p["scale"] * p["scaleX"], p["scale"] * p["scaleY"]
            ang = math.atan2(m[1], m[0])
            gx, gy = math.hypot(m[0], m[1]), math.hypot(m[2], m[3])
            ax_s, ay_s = m[0] * p["x"] + m[2] * p["y"] + m[4], m[1] * p["x"] + m[3] * p["y"] + m[5]
            W, H = w * sx * gx, h * sy * gy
            out.append({"id": lay["id"], "type": lay["type"], "x": ax_s - p["anchorX"] * W, "y": ay_s - p["anchorY"] * H,
                        "w": W, "h": H, "rot": p["rotation"] + math.degrees(ang), "ax": p["anchorX"], "ay": p["anchorY"],
                        "lw": w * sx, "lh": h * sy, "lrot": p["rotation"], "m": m,
                        "locked": locked or bool(lay.get("locked"))})
            if lay["type"] == "group":
                c, s = math.cos(math.radians(p["rotation"])), math.sin(math.radians(p["rotation"]))
                inner = _compose(m, c * sx, s * sx, -s * sy, c * sy, p["x"], p["y"])           # parent px -> this layer's px
                inner = _compose(inner, 1, 0, 0, 1, -p["anchorX"] * w, -p["anchorY"] * h)
                walk(lay.get("layers", []), inner, ln, locked or bool(lay.get("locked")))

    walk(comp.get("layers", []), (1.0, 0.0, 0.0, 1.0, 0.0, 0.0), int(comp.get(STEPS, "1")))
    return out


def parent_delta(b: dict, dx: float, dy: float) -> tuple[float, float]:
    """A drag of (dx, dy) on screen as the same drag in the layer's parent's px (a turned, scaled group)."""
    a, bb, c, d = b["m"][:4]
    det = a * d - bb * c or 1.0
    return (d * dx - c * dy) / det, (-bb * dx + a * dy) / det


def corners(b: dict) -> list[tuple[float, float]]:
    """The four corners of a box (turned about its anchor), composition px."""
    c, s = math.cos(math.radians(b["rot"])), math.sin(math.radians(b["rot"]))
    ox, oy = b["x"] + b["ax"] * b["w"], b["y"] + b["ay"] * b["h"]
    return [(ox + c * (px - ox) - s * (py - oy), oy + s * (px - ox) + c * (py - oy))
            for px, py in ((b["x"], b["y"]), (b["x"] + b["w"], b["y"]), (b["x"] + b["w"], b["y"] + b["h"]), (b["x"], b["y"] + b["h"]))]


def extent(b: dict) -> tuple[float, float, float, float]:
    """x0, y0, x1, y1 of the box's corners."""
    xs, ys = zip(*corners(b))
    return min(xs), min(ys), max(xs), max(ys)


def inside(b: dict, x: float, y: float) -> bool:
    c, s = math.cos(math.radians(-b["rot"])), math.sin(math.radians(-b["rot"]))
    ox, oy = b["x"] + b["ax"] * b["w"], b["y"] + b["ay"] * b["h"]
    lx, ly = ox + c * (x - ox) - s * (y - oy), oy + s * (x - ox) + c * (y - oy)
    return b["x"] <= lx <= b["x"] + b["w"] and b["y"] <= ly <= b["y"] + b["h"]


def pick(comp: dict, t: float, x: float, y: float) -> str:
    """The topmost layer under (x, y), or "" (groups count only where none of their layers is). A locked layer is not
    picked (a hidden one has no box)."""
    hits = [b for b in boxes(comp, t) if not b["locked"] and inside(b, x, y)]
    return hits[-1]["id"] if hits else ""


def mask_box(comp: dict, t: float, mask_id: str) -> dict:
    """The box of a selected mask at t, like a layer's box (its x, y, w, h are in the layer's own px from its top-left
    corner, so it turns and scales with the layer). {} while the mask has no width or height (a wipe that has not
    started): nothing to outline, never the layer's whole box."""
    for lay in boxes(comp, t):
        item = next((i for i in _layers(comp) if i["id"] == lay["id"]), None)
        mask = next((m for m in item.get("masks", []) if m["id"] == mask_id), None) if item else None
        if mask is None:
            continue
        m, ow = resolve(mask, t), own_size(item["type"], resolve(item, t))[0]
        k = lay["w"] / ow if ow else 1.0
        w, h = m["w"] * k, m["h"] * k
        if w <= 0 or h <= 0:
            return {}
        x, y = lay["x"] + m["x"] * k, lay["y"] + m["y"] * k
        px, py = lay["x"] + lay["ax"] * lay["w"], lay["y"] + lay["ay"] * lay["h"]      # the layer's pivot: the mask turns about it
        return {**lay, "x": x, "y": y, "w": w, "h": h, "ax": (px - x) / w, "ay": (py - y) / h}
    return {}


def _layers(comp: dict):
    for lay in comp.get("layers", []):
        yield lay
        if lay["type"] == "group":
            yield from _layers(lay)


def layer_of(doc, item_id: str) -> str:
    """The layer an effect, mask or key belongs to (itself for a layer); "" for a composition."""
    while item_id and doc.item(item_id)["type"] not in F.LAYERS:
        if doc.item(item_id)["type"] == "comp":
            return ""
        item_id = doc.parent_of(item_id)[0]
    return item_id
