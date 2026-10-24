"""Where each layer is, from its evaluated values alone (no rendering). A text's box is the engine's laid-out one
(rostrum2d/textsize.py); effects (glow, shadow, blur) are not counted.

A layer's box runs from (0,0) to (w,h) in its own coordinates; its anchor sits at (x,y) in its parent, then it is
scaled, turned. A group's children live inside the group's own coordinates (top-left of its box is 0,0). The
scene's frame (frame/view.py, FRAME.md) then moves each top-level layer by its depth, so corners and boxes
are where the layer shows on screen. The frame itself is not listed (it is not drawn).
"""
from __future__ import annotations


from rostrum2d import boxes, fields as F, follow
from rostrum2d.drawing import frame_number
from rostrum2d.frame import view as camera
from rostrum2d.evaluate import resolve
from rostrum2d.layout import solve
from rostrum2d.sizes import own_size  # the one size rule

VISIBLE_OPACITY = 0.01


def _mul(m, n):
    a, b, c, d, e, f = m
    A, B, C, D, E, Fv = n
    return (a * A + c * B, b * A + d * B, a * C + c * D, b * C + d * D, a * E + c * Fv + e, b * E + d * Fv + f)


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
    opacity (with its groups' opacity), in_time, corners (4 points in the comp), matrix, box (w, h own size), paint (the
    part of the box it paints itself, own px, or None: boxes.painted)."""
    out: list[dict] = []
    cam = camera.shot(comp, t)
    placed = solve(comp, t)                 # where auto layouts put their layers (rostrum2d/layout.py)

    def walk(layers, parent_m, parent_opacity, parent_in_time, path):
        mattes = _mattes(layers)
        for layer in layers:
            if layer["type"] == "camera":
                continue
            p = {**resolve(layer, t), **placed.get(layer["id"], {})}
            w, h = own_size(layer["type"], p)
            if took := follow.taken(layer, layers, t):     # a text on a path layer (its place and box) or a rider (its place)
                w, h = took.pop("w", w), took.pop("h", h)
                p.update(took)
            outer = parent_m if path else camera.layer_matrix(comp, cam, p)
            m = _mul(outer, boxes.matrix(p, w, h))
            opacity = parent_opacity * min(1.0, max(0.0, p["opacity"]))
            in_time = parent_in_time and p["start"] <= t < p["end"]
            out.append({"id": layer["id"], "type": layer["type"], "name": layer.get("name", ""), "props": p, "opacity": opacity,
                        "in_time": in_time, "matrix": m, "size": (w, h), "within": path,
                        "paint": boxes.painted(layer, w, h, frame_number(t, comp.get("fps", 30)), p),
                        "broken": follow.problem(layer, layers),
                        "matte_for": mattes.get(layer["id"], []), "matte_missing": _missing_matte(layer, layers),
                        "corners": [_apply(m, x, y) for x, y in ((0, 0), (w, 0), (w, h), (0, h))]})
            if layer["type"] == "group":
                walk(layer.get("layers", []), m, opacity, in_time, path + (layer["id"],))

    walk(comp.get("layers", []), (1, 0, 0, 1, 0, 0), 1.0, True, ())
    return out


def _matte_id(layer: dict) -> str:
    return layer.get("matte", "")


def _mattes(layers: list[dict]) -> dict[str, list[str]]:
    """Layer id -> the sibling layers that use it as their track matte (it is drawn only as their matte)."""
    out: dict[str, list[str]] = {}
    for layer in layers:
        if _matte_id(layer):
            out.setdefault(_matte_id(layer), []).append(layer["id"])
    return out


def _missing_matte(layer: dict, layers: list[dict]) -> str:
    """The layer's matte id when no other layer beside it has that id ("" when fine or none)."""
    m = _matte_id(layer)
    ok = not m or any(s["id"] == m and s is not layer and s["type"] != "camera" for s in layers)
    return "" if ok else m


def aabb(corners) -> tuple[float, float, float, float]:
    xs, ys = [c[0] for c in corners], [c[1] for c in corners]
    return min(xs), min(ys), max(xs), max(ys)


def drawn_box(node: dict) -> tuple[float, float, float, float]:
    """(x0, y0, x1, y1) in the comp of what the layer paints itself (a path's curve, a drawing's strokes), else of its
    whole box."""
    if not node["paint"]:
        return aabb(node["corners"])
    x0, y0, x1, y1 = node["paint"]
    return aabb([_apply(node["matrix"], x, y) for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))])


def covers(node: dict, x: float, y: float) -> bool:
    """The layer paints at (x, y) itself (boxes.painted: not a group's empty box, not a drawing's empty canvas): the
    rule the screen's clicks pick by too."""
    inv = _invert(node["matrix"]) if node["paint"] else None
    if inv is None:
        return False
    lx, ly = _apply(inv, x, y)
    x0, y0, x1, y1 = node["paint"]
    return x0 <= lx <= x1 and y0 <= ly <= y1


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
    if node.get("matte_for"):
        why.append("drawn only as the track matte of " + ", ".join(node["matte_for"]))
    if node.get("matte_missing"):
        why.append(f'its track matte "{node["matte_missing"]}" is not a layer beside it (the engine refuses the scene)')
    if node["opacity"] < VISIBLE_OPACITY:
        why.append("opacity 0")
    if p["scale"] * p["scaleX"] * p["scaleY"] == 0 or node["size"][0] * node["size"][1] == 0:
        why.append("zero size")
    elif not on_screen(node, width, height):
        why.append("outside the frame")
    return why


def comp_size(comp: dict) -> tuple[int, int]:
    return comp.get("width", F.defaults("comp")["width"]), comp.get("height", F.defaults("comp")["height"])
