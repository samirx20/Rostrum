"""One call from one section to the next (guide transitions-and-carry-overs). Both write ordinary keys, masks and
effects onto the layers the script made, so the change is there to see and edit afterwards, and a re-run writes the
same ids again (nothing doubles).

    transition("push", at=4, dur=0.6, out_of=intro, into=features, direction="left", ease="easeInOut")
    transition("wipe", at="#chapter2", dur=0.8, out_of="intro", into="features", softness=120)
    carry(logo, into=features, at=4, dur=0.8, to=dict(x=200, y=120, scale=0.4))

transition: `out_of` stays on until at + dur (its end), `into` starts at `at` and is drawn right above `out_of` when
the two share a parent. Distances are the frame's view at `at` (comp px at Zoom 1). carry: the layer ends at `at` in
its section and a copy of it (id "<layer>_carry", or id=) takes over in the scene from `at`, where it showed, keyed to
`to` (scene px) at at + dur. No Qt."""
from __future__ import annotations

import copy
import math

from rostrum_core.keys import key_id

from . import script_place as P
from . import script_time as T
from .ops_expr import expr_id

KINDS = ("cut", "fade", "push", "slide", "wipe", "iris", "zoom", "blur")
DIRECTIONS = {"left": (-1, 0), "right": (1, 0), "up": (0, -1), "down": (0, 1)}
OWN = {"cut": (), "fade": ("hold_out",), "push": ("direction",), "slide": ("direction",), "wipe": ("direction", "softness"),
       "iris": ("x", "y", "softness"), "zoom": ("out_scale", "in_scale"), "blur": ("radius",)}
CARRIED = ("x", "y", "scale", "rotation", "opacity")


def _item(build, path):
    from .script import Item
    return Item(build, path[-1])


def _plus(at, dur):
    return at + dur if isinstance(at, T.Time) else round(at + dur, 6)


def _when(build, at, where):
    """(at as written: seconds or a marker Time, its seconds)."""
    s = T.seconds(build, at, where)
    return (T.Time(at) if isinstance(at, str) else float(at)), s


def transition(build, kind="fade", at=0.0, dur=0.5, out_of=None, into=None, ease="smooth", **params):
    where = f'transition("{kind}")'
    if kind not in KINDS:
        raise ValueError(f'transition("{kind}"): kinds are {", ".join(KINDS)}')
    bad = sorted(set(params) - set(OWN[kind]))
    if bad:
        raise ValueError(f'{where}: no "{bad[0]}"; a {kind} takes at, dur, out_of, into, ease'
                         + "".join(f", {p}" for p in OWN[kind]))
    if out_of is None or into is None:
        raise ValueError(f"{where}: give both sections: out_of=<group or layer>, into=<group or layer>")
    if not isinstance(dur, (int, float)) or isinstance(dur, bool) or dur < 0:
        raise ValueError(f"{where}: dur is seconds, 0 or more (got {dur!r})")
    a_path, b_path = P.path_to(build, out_of, f"{where} out_of"), P.path_to(build, into, f"{where} into")
    a, b = _item(build, a_path), _item(build, b_path)
    at, t0 = _when(build, at, f"{where} at")
    dur = 0.0 if kind == "cut" else float(dur)
    t1, end = t0 + dur, _plus(at, dur)
    a.set(end=end)
    b.set(start=at)
    _stack(a_path, b_path)
    if kind == "cut":
        return
    va, vb = P.values(build, a.node, t0), P.values(build, b.node, t1)
    comp = a_path[0]
    left, top, fw, fh = P.view(build, comp, t0)
    if kind == "fade":
        b.key("opacity", {at: 0.0, end: vb["opacity"]}, ease=ease)
        if not params.get("hold_out", False):
            a.key("opacity", {at: va["opacity"], end: 0.0}, ease=ease)
    elif kind in ("push", "slide"):
        dx, dy = _direction(params.get("direction", "left"), where)
        moving = ((a, a_path, va, 0.0, 1.0), (b, b_path, vb, -1.0, 0.0))     # out_of: rest -> one view on; into: one view back -> rest
        for item, path, v, k0, k1 in moving[kind == "slide":]:
            scale = P.product(build, path[1:-1], "scale", t0) or 1e-9
            for prop, d in (("x", dx * fw / scale), ("y", dy * fh / scale)):
                if d:
                    item.key(prop, {at: v[prop] + k0 * d, end: v[prop] + k1 * d}, ease=ease)
    elif kind == "wipe":        # the moving edge travels the way of `direction`; the side it leaves from stays put
        dx, dy = _direction(params.get("direction", "left"), where)
        s = float(params.get("softness", 0.0))
        x0, y0, x1, y1 = _local_box(build, b_path, (left - s, top - s, left + fw + s, top + fh + s), t0)
        m = b.mask(f"{b.id}_wipe", shape="rect", feather=s, x=x0, y=y0, w=x1 - x0, h=y1 - y0)
        size, lo, hi = ("w", x0, x1) if dx else ("h", y0, y1)
        m.key(size, {at: 0.0, end: hi - lo}, ease=ease)
        if (dx or dy) < 0:
            m.key("x" if dx else "y", {at: hi, end: lo}, ease=ease)
    elif kind == "iris":
        s = float(params.get("softness", 0.0))
        cx, cy = float(params.get("x", left + fw / 2)), float(params.get("y", top + fh / 2))
        r = max(math.hypot(px - cx, py - cy) for px in (left, left + fw) for py in (top, top + fh)) + s
        lx, ly = P.from_scene(build, b_path[1:], (cx, cy), t0)
        lr = r / (P.product(build, b_path[1:], "scale", t0) or 1e-9)
        m = b.mask(f"{b.id}_iris", shape="ellipse", feather=s)
        m.key("w", {at: 0.0, end: 2 * lr}, ease=ease).key("h", {at: 0.0, end: 2 * lr}, ease=ease)
        m.key("x", {at: lx, end: lx - lr}, ease=ease).key("y", {at: ly, end: ly - lr}, ease=ease)
    elif kind == "zoom":
        a.key("scale", {at: va["scale"], end: va["scale"] * float(params.get("out_scale", 1.6))}, ease=ease)
        a.key("opacity", {at: va["opacity"], end: 0.0}, ease=ease)
        b.key("scale", {at: vb["scale"] * float(params.get("in_scale", 0.6)), end: vb["scale"]}, ease=ease)
        b.key("opacity", {at: 0.0, end: vb["opacity"]}, ease=ease)
    elif kind == "blur":
        r = float(params.get("radius", 40.0))
        a.effect("blur", f"{a.id}_out_blur", radius=0).key("radius", {at: 0.0, end: r}, ease=ease)
        a.key("opacity", {at: va["opacity"], end: 0.0}, ease=ease)
        b.effect("blur", f"{b.id}_in_blur", radius=r).key("radius", {at: r, end: 0.0}, ease=ease)
        b.key("opacity", {at: 0.0, end: vb["opacity"]}, ease=ease)


def _direction(word, where):
    if word not in DIRECTIONS:
        raise ValueError(f'{where}: direction="{word}"; directions are {", ".join(DIRECTIONS)} (the way the motion goes)')
    return DIRECTIONS[word]


def _local_box(build, path, box, t):
    """A scene-px box -> the box around it in the item's own px (path: [scene, …, item])."""
    pts = [P.from_scene(build, path[1:], (x, y), t) for x in (box[0], box[2]) for y in (box[1], box[3])]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def _stack(a_path, b_path):
    """`into` right above `out_of` when they share a parent and it was below."""
    parent, a, b = a_path[-2], a_path[-1], b_path[-1]
    if b_path[-2] is parent:
        layers = parent["layers"]
        if layers.index(b) < layers.index(a):
            layers.remove(b)
            layers.insert(layers.index(a) + 1, b)


def carry(build, layer, into=None, at=0.0, dur=0.5, to=None, ease="smooth", id=None):
    where = "carry()"
    if not isinstance(to, dict) or not to:
        raise ValueError(f"{where}: to= is the fields it lands on, in scene px: to=dict(x=…, y=…, scale=…)")
    path = P.path_to(build, layer, f"{where} layer")
    at, t0 = _when(build, at, f"{where} at")
    end = _plus(at, float(dur))
    item = _item(build, path)
    if len(path) == 2:          # already in the scene: only the keys
        v = P.values(build, item.node, t0)
        for prop, value in to.items():
            item.key(prop, {at: v.get(prop, value), end: value}, ease=ease)
        return item
    comp, groups, node = path[0], path[1:-1], path[-1]
    v = P.values(build, node, t0)
    x, y = P.to_scene(build, groups, (v["x"], v["y"]), t0)
    start = {"x": x, "y": y, "scale": v["scale"] * P.product(build, groups, "scale", t0),
             "rotation": v["rotation"] + sum(P.values(build, g, t0)["rotation"] for g in groups),
             "opacity": v["opacity"] * P.product(build, groups, "opacity", t0)}
    twin = copy.deepcopy(node)
    _rename(build, twin, id or f"{node['id']}_carry", True)
    twin.update({k: start[k] for k in CARRIED})
    gone = set(CARRIED) | set(to)
    twin["keys"] = [k for k in twin["keys"] if k["prop"] not in gone]
    twin.pop("marker", None), twin.pop("endMarker", None)
    copy_ = _item(build, [twin])
    copy_.set(start=at, end=node.get("end", 36000.0))
    item.set(end=at)
    for prop, value in to.items():
        copy_.key(prop, {at: start.get(prop, v.get(prop, value)), end: value}, ease=ease)
    layers = comp["layers"]
    over = P.path_to(build, into, f"{where} into")[1] if into is not None else None
    layers.insert(layers.index(over) + 1 if over is not None else len(layers), twin)
    return copy_


def _rename(build, node, new, top=False):
    """A copied item's ids made its own: the item `new`, everything inside it "<new>_<old>"; keys and expressions follow."""
    old, node["id"] = node["id"], build.new_id(node["type"], new)
    for k in node.get("keys", []):
        k["id"] = key_id(node["id"], k["prop"], k["t"])
    for e in node.get("exprs", []):
        e["id"] = expr_id(node["id"], e["prop"])
    for value in list(node.values()):
        if isinstance(value, list):
            for c in value:
                if isinstance(c, dict) and "id" in c and c.get("type") not in ("key", "expr"):
                    _rename(build, c, f"{(new if top else node['id'])}_{c['id']}")


def for_script(build) -> dict:
    def transition_(kind="fade", at=0.0, dur=0.5, out_of=None, into=None, ease="smooth", **params):
        """One call from one section to the next: cut, fade, push, slide, wipe, iris, zoom, blur (ordinary keys)."""
        return transition(build, kind, at, dur, out_of, into, ease, **params)

    def carry_(layer, into=None, at=0.0, dur=0.5, to=None, ease="smooth", id=None):
        """A layer carried past its section's end: a copy in the scene from `at`, keyed to `to` at at + dur."""
        return carry(build, layer, into, at, dur, to, ease, id)
    transition_.__name__, carry_.__name__ = "transition", "carry"
    return {"transition": transition_, "carry": carry_}
