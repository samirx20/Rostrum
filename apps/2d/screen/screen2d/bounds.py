"""Where each layer sits on the canvas at a time, in world pixels (the canvas shows the world; at home they are composition px): the selection outline and click-to-pick.
No Qt.

A layer's box: its anchor sits at (x, y) inside its parent (a group's layers are placed from the group's top-left
corner); the box is w x h times scale, turned by `rot` degrees about the anchor (the selection outline turns with it;
picking turns the pointer back the same way). Tilt is not taken into account.
A layer's size is rostrum2d/sizes.py's (a text's is the engine's laid-out box, rostrum2d/textsize.py, on a path too).
A layer in an auto layout is where the layout puts it (rostrum2d/layout.py). The matrix is rostrum2d/boxes.py's (one for
the screen, the agents' geometry and the operations).
A click picks what is painted under it (rostrum2d.boxes.painted, as the agents' look_at): never a group's own box (only
its layers), never a drawing's empty canvas, never a hidden, see-through (opacity 0), locked or out-of-time layer, nor
a layer drawn only as another's track matte.
"""
from __future__ import annotations

import math

from rostrum2d import boxes as BX, fields as F
from rostrum2d.frame import view as camera
from rostrum2d.drawing import frame_number
from rostrum_core.plugin_parts import is_plugin
from rostrum2d.evaluate import resolve
from rostrum2d.layout import solve
from rostrum2d.sizes import own_size
from .handle_kinds import kit_of
from rostrum2d.stepped import FIELD as STEPS


def _stepped(t: float, n: int, fps: float) -> float:
    """The time the engine draws at when timing is on n-frames (rostrum2d/stepped.py holds each pose for n frames)."""
    return math.floor(t * fps / n + 1e-9) * n / fps if n > 1 else t


def _compose(m, a, b, c, d, e, f):
    """Matrix m (a b c d e f: x' = a x + c y + e, y' = b x + d y + f) followed by the affine given after it."""
    return (m[0] * a + m[2] * b, m[1] * a + m[3] * b, m[0] * c + m[2] * d, m[1] * c + m[3] * d,
            m[0] * e + m[2] * f + m[4], m[1] * e + m[3] * f + m[5])


_LAST: list = [None, None, None]         # the last whole list: (the composition it was made from, t, the boxes)


def boxes(comp: dict, t: float, only: set | None = None) -> list[dict]:
    """`_boxes`, the whole list kept for the composition and time it was made from (a composition is never changed in
    place: each change is a new tree, Bridge2D.placed). A drag's press asked for it three times (its parents' frames,
    the snap targets, the pick): ~20 ms each at 200 layers. Callers only read it."""
    if only is not None:
        return _boxes(comp, t, only)
    if _LAST[0] is not comp or _LAST[1] != t:
        _LAST[:] = [comp, t, _boxes(comp, t)]
    return _LAST[2]


def _boxes(comp: dict, t: float, only: set | None = None) -> list[dict]:
    """[{id, x, y, w, h, rot, ax, ay}] for every layer showing at t (with `only`: those layers and the groups they are
    in, nothing else worked out), bottom of the stack first (a group before its layers), all on the canvas (world px): x, y is the unturned top-left of the box about its anchor, w x h the size on
    screen. A layer inside groups is carried through their whole chain (position, turn, scale, anchor), as the engine
    does: a layer sits at (x, y) inside its parent and turns and scales about its anchor, and a group's layers live in
    the group's own px, so they follow the group's turn. Also `lw lh lrot` (the box in its parent's px) and `m` (the
    parent's matrix, a b c d e f), for drags in the parent's frame; `fx fy`: mirrored across / up and down in its parent
    by a negative Stretch, `pm`: the axis ("x", "y"; "" none) its parent shows mirrored on (the box shows the same, `ax ay`
    and `paint` read from the other side, as it shows; `parent_side` turns a knob on screen into the parent's frame). Each layer is read at the stepped time the engine
    draws it at (Timing > Steps on it, its group or the composition). For picking: `up` (its groups, outermost first),
    `opacity` (with its groups'), `handles` (which knobs it shows: handle_kinds.py), `paint` (the part it paints itself, as fractions x0 y0 x1 y1 of w and h; None: none).
    """
    out: list[dict] = []
    fps = comp.get("fps", 30)
    placed: dict[float, dict] = {}
    cam = camera.shot(comp, t)               # the camera showing at the playhead: every top-level layer is drawn through it

    def layout(te):                          # where auto layouts put their layers at time te (rostrum2d/layout.py)
        if te not in placed:
            placed[te] = solve(comp, te)
        return placed[te]

    def wanted(lay) -> bool:
        return only is None or lay["id"] in only or any(wanted(c) for c in lay.get("layers", ()))

    def walk(layers, m, n, locked=False, up=(), seen=1.0):
        mattes = {lay.get("matte") for lay in layers if lay.get("matte")}
        for lay in layers:
            if lay["type"] == "camera" or is_plugin(lay["type"]) or lay.get("hidden") or not wanted(lay):   # not drawn (a plugin's item never is): no box (and no scale)
                continue
            own = lay.get(STEPS, "group")
            ln = n if own == "group" else int(own)
            te = _stepped(t, ln, fps)
            p = {**resolve(lay, te), **layout(te).get(lay["id"], {})}
            if not (p["start"] <= te < p["end"]):
                continue
            w, h = own_size(lay["type"], p)
            if not up:                       # top level: the world view's matrix for this layer (frame/view.py world_matrix, spec 8.3)
                m = camera.world_matrix(comp, cam, p)
            sx, sy = p["scale"] * p["scaleX"], p["scale"] * p["scaleY"]
            ang = math.atan2(m[1], m[0])
            gx, gy = math.hypot(m[0], m[1]), math.hypot(m[2], m[3])
            pm = _mirror_axis(m, ang)               # the parent is mirrored: "x" or "y", read as flipped on that axis, then turned
            ang = ang - math.copysign(math.pi, ang) if pm == "x" else ang
            ax_s, ay_s = m[0] * p["x"] + m[2] * p["y"] + m[4], m[1] * p["x"] + m[3] * p["y"] + m[5]
            fx, fy = sx < 0, sy < 0                  # mirrored by a negative Stretch, in its parent
            sfx, sfy = fx != (pm == "x"), fy != (pm == "y")      # ... and as it shows: the same box, its anchor on the other side
            W, H = w * abs(sx) * gx, h * abs(sy) * gy
            axf, ayf = (1 - p["anchorX"] if sfx else p["anchorX"]), (1 - p["anchorY"] if sfy else p["anchorY"])
            opacity = seen * min(1.0, max(0.0, p["opacity"]))
            paint = BX.painted(lay, w, h, frame_number(te, fps), p) if lay["id"] not in mattes else None
            if paint and (sfx or sfy):
                x0, y0, x1, y1 = paint
                paint = (w - x1 if sfx else x0, h - y1 if sfy else y0, w - x0 if sfx else x1, h - y0 if sfy else y1)
            out.append({"up": up, "opacity": opacity, "frame": frame_number(te, fps),
                        "paint": [v / (w or 1) if i % 2 == 0 else v / (h or 1) for i, v in enumerate(paint)] if paint else None,
                        "id": lay["id"], "type": lay["type"], "x": ax_s - axf * W, "y": ay_s - ayf * H,
                        "w": W, "h": H, "rot": (-p["rotation"] if pm else p["rotation"]) + math.degrees(ang), "ax": axf, "ay": ayf,
                        "lw": w * abs(sx), "lh": h * abs(sy), "lrot": p["rotation"], "m": m, "handles": kit_of(lay["type"], p),
                        "fx": fx, "fy": fy, "pm": pm, "locked": locked or bool(lay.get("locked"))})
            if lay["type"] == "group":
                inner = _compose(m, *BX.matrix(p, w, h))           # this group's own px -> the screen's
                walk(lay.get("layers", []), inner, ln, locked or bool(lay.get("locked")), up + (lay["id"],), opacity)

    walk(comp.get("layers", []), (1.0, 0.0, 0.0, 1.0, 0.0, 0.0), int(comp.get(STEPS, "1")))
    return out


def parent_delta(b: dict, dx: float, dy: float) -> tuple[float, float]:
    """A drag of (dx, dy) on screen as the same drag in the layer's parent's px (a turned, scaled group)."""
    a, bb, c, d = b["m"][:4]
    det = a * d - bb * c or 1.0
    return (d * dx - c * dy) / det, (-bb * dx + a * dy) / det


def _mirror_axis(m, ang: float) -> str:
    """The axis a mirrored matrix (a negative determinant) is read as flipped on, "" for none: across ("x") when that
    leaves the smaller turn (a group mirrored across shows its layers unturned, not upside down and half turned)."""
    if m[0] * m[3] - m[1] * m[2] >= 0:
        return ""
    return "x" if abs(ang) > math.pi / 2 else "y"


def parent_side(b: dict, hx: int, hy: int) -> tuple[int, int, float, float]:
    """A knob's sides and the anchor's place across the box (hx, hy, ax, ay) as they are in the layer's parent's px:
    inside a group mirrored on an axis (`pm`), the box on screen runs the other way on it."""
    if b.get("pm") == "x":
        return -hx, hy, 1 - b["ax"], b["ay"]
    if b.get("pm") == "y":
        return hx, -hy, b["ax"], 1 - b["ay"]
    return hx, hy, b["ax"], b["ay"]


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


def inside(b: dict, x: float, y: float, part=(0.0, 0.0, 1.0, 1.0)) -> bool:
    """(x, y) is in the box (or in `part` of it: fractions x0 y0 x1 y1 of its unturned width and height)."""
    c, s = math.cos(math.radians(-b["rot"])), math.sin(math.radians(-b["rot"]))
    ox, oy = b["x"] + b["ax"] * b["w"], b["y"] + b["ay"] * b["h"]
    lx, ly = ox + c * (x - ox) - s * (y - oy), oy + s * (x - ox) + c * (y - oy)
    return (b["x"] + part[0] * b["w"] <= lx <= b["x"] + part[2] * b["w"]
            and b["y"] + part[1] * b["h"] <= ly <= b["y"] + part[3] * b["h"])


def pickable(b: dict) -> bool:
    return BX.can_pick(b["paint"], b["opacity"], b["locked"])


def _inked(comp: dict, b: dict, x: float, y: float) -> bool:
    """A drawing is picked only where it has a painted pixel under (x, y), not anywhere in the rectangle round its
    strokes (rostrum2d.boxes.ink_at); every other kind: its painted part is the rectangle."""
    if b["type"] != "drawing":
        return True
    c, s = math.cos(math.radians(-b["rot"])), math.sin(math.radians(-b["rot"]))
    ox, oy = b["x"] + b["ax"] * b["w"], b["y"] + b["ay"] * b["h"]
    lx, ly = ox + c * (x - ox) - s * (y - oy), oy + s * (x - ox) + c * (y - oy)
    layer = next(i for i in _layers(comp) if i["id"] == b["id"])
    return BX.ink_at(layer, b["frame"], (lx - b["x"]) / (b["w"] or 1), (ly - b["y"]) / (b["h"] or 1))


_pickable = [(None, None, [])]   # [(composition, t, its pickable boxes)]: a press and its click ask twice, and every
                                 # click until the next change or playhead move asks the same (a walk of every layer)


def under_chains(comp: dict, t: float, x: float, y: float) -> list[list[str]]:
    """Every layer painted under (x, y), top first, each as its groups (outermost first) and the layer last. The boxes
    are worked out once per composition state (every change gives a new one) and time."""
    got = _pickable[0]
    if got[0] is not comp or got[1] != t:
        got = _pickable[0] = (comp, t, [b for b in boxes(comp, t) if pickable(b)])
    return [[*b["up"], b["id"]] for b in reversed(got[2]) if inside(b, x, y, b["paint"]) and _inked(comp, b, x, y)]


def under(comp: dict, t: float, x: float, y: float) -> list[str]:
    """The ids of every layer painted under (x, y), top first (the pieces themselves; picking.py's `behind` turns them
    into what a click picks at the open depth). The one list: a click, Alt+click and Select layer all read it."""
    return [c[-1] for c in under_chains(comp, t, x, y)]


def pick_chain(comp: dict, t: float, x: float, y: float) -> list[str]:
    """The topmost layer painted under (x, y) with its groups, outermost first ([] for none): what a click can select
    (picking.py chooses which of them)."""
    return next(iter(under_chains(comp, t, x, y)), [])


def pick(comp: dict, t: float, x: float, y: float) -> str:
    """The topmost layer painted under (x, y) itself (the deepest piece), or ""."""
    chain = pick_chain(comp, t, x, y)
    return chain[-1] if chain else ""


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
    while item_id and doc.item(item_id)["type"] not in F.ROWS:
        if doc.item(item_id)["type"] == "comp":
            return ""
        item_id = doc.parent_of(item_id)[0]
    return item_id
