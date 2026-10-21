"""Where each layer is, from its evaluated values alone (no rendering). All boxes are APPROXIMATE: text width is
estimated from its size and letters, and effects (glow, shadow, blur) are not counted.

A layer's box runs from (0,0) to (w,h) in its own coordinates; its anchor sits at (x,y) in its parent, then it is
scaled, turned. A group's children live inside the group's own coordinates (top-left of its box is 0,0). The
composition's camera (camera/view.py, CAMERA.md) then moves each top-level layer by its depth, so corners and boxes
are where the layer shows on screen. Cameras themselves are not listed (they are not drawn).
"""
from __future__ import annotations

import math

from rostrum2d import fields as F, follow
from rostrum2d.camera import view as camera
from rostrum2d.evaluate import resolve

TEXT_EM = 0.55            # average letter width in em, for the text box estimate
VISIBLE_OPACITY = 0.01


def own_size(layer_type: str, p: dict) -> tuple[float, float]:
    if layer_type == "text":
        lines = (p["body"] or " ").split("\n")
        longest = max(len(line) for line in lines)
        width = longest * p["size"] * (TEXT_EM + p["tracking"])
        if p["boxWidth"]:
            wrapped = sum(max(1, math.ceil(len(line) * p["size"] * TEXT_EM / p["boxWidth"])) for line in lines)
            return p["boxWidth"], wrapped * p["size"] * p["lineHeight"]
        return max(width, p["size"] * 0.5), len(lines) * p["size"] * p["lineHeight"]
    return p["w"], p["h"]


def _mul(m, n):
    a, b, c, d, e, f = m
    A, B, C, D, E, Fv = n
    return (a * A + c * B, b * A + d * B, a * C + c * D, b * C + d * D, a * E + c * Fv + e, b * E + d * Fv + f)


def _matrix(p: dict, w: float, h: float):
    r = math.radians(p["rotation"])
    cos, sin = math.cos(r), math.sin(r)
    sx, sy = p["scale"] * p["scaleX"], p["scale"] * p["scaleY"]
    place = (1, 0, 0, 1, p["x"], p["y"])
    turn = (cos, sin, -sin, cos, 0, 0)
    size = (sx, 0, 0, sy, 0, 0)
    anchor = (1, 0, 0, 1, -p["anchorX"] * w, -p["anchorY"] * h)
    return _mul(_mul(_mul(place, turn), size), anchor)


def _apply(m, x, y):
    return (m[0] * x + m[2] * y + m[4], m[1] * x + m[3] * y + m[5])


def _invert(m):
    a, b, c, d, e, f = m
    det = a * d - b * c
    if abs(det) < 1e-12:
        return None
    return (d / det, -b / det, -c / det, a / det, (c * f - d * e) / det, (b * e - a * f) / det)


def flatten(comp: dict, t: float) -> list[dict]:
    """Every layer of a composition at time t, bottom of the stack first. Each: id, type, name, props (evaluated),
    opacity (with its groups' opacity), in_time, corners (4 points in the comp), matrix, box (w, h own size)."""
    out: list[dict] = []
    cam = camera.shot(comp, t)

    def walk(layers, parent_m, parent_opacity, parent_in_time, path):
        for layer in layers:
            if layer["type"] == "camera":
                continue
            p = resolve(layer, t)
            w, h = own_size(layer["type"], p)
            if took := follow.taken(layer, layers, t):     # a text on a path layer: the path's place and box
                w, h = took.pop("w"), took.pop("h")
                p.update(took)
            outer = parent_m if path else camera.layer_matrix(comp, cam, p)
            m = _mul(outer, _matrix(p, w, h))
            opacity = parent_opacity * min(1.0, max(0.0, p["opacity"]))
            in_time = parent_in_time and p["start"] <= t < p["end"]
            out.append({"id": layer["id"], "type": layer["type"], "name": layer.get("name", ""), "props": p, "opacity": opacity,
                        "in_time": in_time, "matrix": m, "size": (w, h), "within": path,
                        "broken": follow.problem(layer, layers),
                        "corners": [_apply(m, x, y) for x, y in ((0, 0), (w, 0), (w, h), (0, h))]})
            if layer["type"] == "group":
                walk(layer.get("layers", []), m, opacity, in_time, path + (layer["id"],))

    walk(comp.get("layers", []), (1, 0, 0, 1, 0, 0), 1.0, True, ())
    return out


def aabb(corners) -> tuple[float, float, float, float]:
    xs, ys = [c[0] for c in corners], [c[1] for c in corners]
    return min(xs), min(ys), max(xs), max(ys)


def covers(node: dict, x: float, y: float) -> bool:
    inv = _invert(node["matrix"])
    if inv is None:
        return False
    lx, ly = _apply(inv, x, y)
    return 0 <= lx <= node["size"][0] and 0 <= ly <= node["size"][1]


def on_screen(node: dict, width: float, height: float) -> bool:
    x0, y0, x1, y1 = aabb(node["corners"])
    return x1 > 0 and y1 > 0 and x0 < width and y0 < height


def problems_showing(node: dict, width: float, height: float) -> list[str]:
    """Why a layer can't be seen at this moment (empty list = it can)."""
    p, why = node["props"], []
    if node.get("broken"):
        why.append(node["broken"])
    if not node["in_time"]:
        why.append("outside its start/end times")
    if node["opacity"] < VISIBLE_OPACITY:
        why.append("opacity 0")
    if p["scale"] * p["scaleX"] * p["scaleY"] == 0 or node["size"][0] * node["size"][1] == 0:
        why.append("zero size")
    elif not on_screen(node, width, height):
        why.append("outside the frame")
    return why


def comp_size(comp: dict) -> tuple[int, int]:
    return comp.get("width", F.defaults("comp")["width"]), comp.get("height", F.defaults("comp")["height"])
