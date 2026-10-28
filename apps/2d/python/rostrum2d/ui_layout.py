"""Sizes and boxes for product screens (guide ui-and-product-animation, "Framing a device"; screen parts are placed by
the container they are made in, script_layout.py and guide lay-out-a-screen):

- `device_box`: a phone's height a share of the parent's height (`fit`, default 0.82) keeping the 430:900 shape; a
  laptop or browser the same, held inside 86 % of the width; centred, or against the left / right of a title-safe
  area (`anchor`, `margin`).
- `box_in`: an item's box (x, y, w, h) in another group's px, through the groups between, where the layouts place
  them (for tap / pointer).
"""
from __future__ import annotations

from . import fields as F
from rostrum_core.keys import keys_of

from .evaluate import value_at

SHAPES = {"phone": (430, 900), "laptop": (1240, 800), "browser": (1280, 800)}
FIT = {"phone": 0.82, "laptop": 0.74, "browser": 0.74}
INK, MUTED, LINE, PAPER, ACCENT = "#111827", "#6b7280", "#e5e7eb", "#ffffff", "#4f46e5"     # starting colours
BASE_W = 390.0              # the width the blocks' starting sizes are drawn for; they scale with the parent's width


class Rows(list):
    """What list_rows / bars give: their parts, top (or left) first, plus the block's group and its .bottom."""
    group = None

    @property
    def bottom(self) -> float:
        return self.group.bottom


def parent_size(build) -> tuple[float, float]:
    """The width and height of the group (or scene) layers are being made in: the nearest one with a set size."""
    for node in reversed(build.holders):
        if node["type"] == "comp":
            return float(node.get("width", 1920)), float(node.get("height", 1080))
        if node["id"] in build.sized:
            return float(node.get("w", 0)), float(node.get("h", 0))
    return 1920.0, 1080.0


def device_box(kind, build, x=None, y=None, w=None, h=None, fit=None, anchor="center", margin=None):
    """(x, y, w, h) of a device centred on (x, y). Given w / h win; else the size comes from `fit`, the share of the
    parent's height it fills; then x from `anchor` inside a title-safe area `margin` px in (default 8 % of the width)."""
    pw, ph = parent_size(build)
    sw, sh = SHAPES[kind]
    if w is None and h is None:
        h = (FIT[kind] if fit is None else float(fit)) * ph
        w = h * sw / sh
        if w > pw * 0.86 and fit is None:
            w, h = pw * 0.86, pw * 0.86 * sh / sw
    elif w is None:
        w = float(h) * sw / sh
    elif h is None:
        h = float(w) * sh / sw
    w, h = float(w), float(h)
    if anchor not in ("center", "left", "right"):
        raise ValueError(f'device: anchor "{anchor}" is not one of center, left, right')
    m = pw * 0.08 if margin is None else float(margin)
    if x is None:
        x = {"center": pw / 2, "left": m + w / 2, "right": pw - m - w / 2}[anchor]
    return float(x), float(ph / 2 if y is None else y), w, h


def bottom(node) -> float:
    """y + the height below the anchor (a group placed by its top-left: y + h)."""
    d = F.defaults(node["type"])
    h = float(node.get("h", d.get("h", 0))) * float(node.get("scale", 1)) * float(node.get("scaleY", 1))
    return float(node.get("y", d.get("y", 0))) + h * (1 - float(node.get("anchorY", d.get("anchorY", 0.5))))


def right(node) -> float:
    d = F.defaults(node["type"])
    w = float(node.get("w", d.get("w", 0))) * float(node.get("scale", 1)) * float(node.get("scaleX", 1))
    return float(node.get("x", d.get("x", 0))) + w * (1 - float(node.get("anchorX", d.get("anchorX", 0.5))))


def chain(root, id_) -> list:
    """The nodes from a scene down to the item `id_` (scene first)."""
    def down(node, path):
        if node.get("id") == id_:
            return path + [node]
        for c in node.get("layers", []):
            got = down(c, path + [node])
            if got:
                return got
        return None
    for comp in root.get("comps", []):
        got = down(comp, [])
        if got:
            return got
    raise ValueError(f'no layer "{id_}" made yet in this script')


MOVES = ("x", "y", "scale", "scaleX", "scaleY")


def _at(node, k, t, default) -> float:
    """Field k of node: its value at t when keyed (t given), else its own value, else `default`."""
    if t is not None and keys_of(node, k):
        return float(value_at(node, k, t))
    return float(node.get(k, default))


def own_box(node, t=None, placed=None) -> tuple[float, float, float, float]:
    """An item's box in its parent's px (a text's from its size and length: a close guess, no engine call); with `t`,
    where its keys have moved it by then; `placed`: what a layout gives it then ({x, y[, w, h][, boxWidth]})."""
    d = F.defaults(node["type"])
    d = {**d, "scaleX": d.get("scaleX", 1), "scaleY": d.get("scaleY", 1), "scale": d.get("scale", 1)}
    placed = placed or {}
    g = lambda k: float(placed[k]) if k in placed else (_at(node, k, t, d.get(k, 0)) if k in MOVES else float(node.get(k, d.get(k, 0))))
    if node["type"] == "text":
        w, h = len(str(node.get("body", ""))) * g("size") * 0.6, g("size") * 1.2
        if "boxWidth" in placed:
            w = min(w, float(placed["boxWidth"]))
    else:
        w, h = g("w"), g("h")
    sx, sy = g("scale") * g("scaleX"), g("scale") * g("scaleY")
    return g("x") - g("anchorX") * w * sx, g("y") - g("anchorY") * h * sy, w * sx, h * sy


def to_scene(nodes, box, t=None, placed=None):
    """A box in the px of nodes[-1] (a group) up to the scene's px (with `t`: where the groups are then; `placed`:
    the layouts' places then, layout.solve)."""
    x, y, w, h = box
    placed = placed or {}
    for g in reversed(nodes[1:]):
        gx, gy, _, _ = own_box(g, t, placed.get(g["id"]))
        v = lambda k: _at(g, k, t, 1)
        sx, sy = v("scale") * v("scaleX"), v("scale") * v("scaleY")
        x, y, w, h = gx + x * sx, gy + y * sy, w * sx, h * sy
    return x, y, w, h


def box_in(root, id_, holder_id, t=None) -> tuple[float, float, float, float]:
    """Item `id_`'s box in the px of group `holder_id` (or the scene); with `t`, where keys have moved them by then."""
    path = chain(root, id_)
    placed = laid_out_places(path[0], t)
    sx, sy, sw, sh = to_scene(path[:-1], own_box(path[-1], t, placed.get(id_)), t, placed)
    hold = chain(root, holder_id)
    ox, oy, ow, oh = to_scene(hold, (0, 0, 1, 1), t, placed)
    return (sx - ox) / ow, (sy - oy) / oh, sw / ow, sh / oh


def laid_out_places(comp, t=None) -> dict:
    """{id: {x, y[, w, h][, boxWidth]}} the scene's layouts give at t (empty with no layout in it)."""
    from . import layout
    if not any(layout.laid_out(c) for c in comp.get("layers", ())):
        return {}
    return layout.solve(comp, 0.0 if t is None else float(t))
