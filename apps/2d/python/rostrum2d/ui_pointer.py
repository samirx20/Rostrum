"""A pointer on a product screen and taps with it (guide ui-and-product-animation, "A pointer and taps").

    cur = pointer()                              # an arrow, its tip at the group's (0, 0): it moves, scales and lands by the tip
    tap(cur, layer("pay"), at=2.0)              # glides there, presses (pointer and button), a ripple under the tip (its colour the pointer's outline)

`pointer(id="cursor", kind="arrow"|"touch", x=, y=, size=, color=, outline=, shadow=)` is a group made of plain
layers (`<id>_arrow` a path, or `<id>_dot`), so it is restyled or keyed like any other. `tap(pointer, target, at)`
moves the tip from where it was onto the target with keys on the pointer's x / y, eased; the spot is beside the
target's words (right part of a button, lower right of a card), never on them: each candidate spot is tried and the
first where the pointer's whole shape misses every text of the target wins. `spot=(fx, fy)` gives the spot as a
share of the target's box instead. The target scales down and back around its centre (`press`, False for none).
The pointer is moved to the top of its group at each tap, so it draws over what was made after it.
"""
from __future__ import annotations

from . import pathdata, ui_layout as U

SPOTS = ((0.84, 0.6), (0.84, 0.8), (0.64, 0.84), (0.93, 0.5), (0.16, 0.84), (0.5, 1.1))
ARROW = [(0, 0), (0, 0.84), (0.21, 0.64), (0.35, 0.96), (0.47, 0.91), (0.33, 0.6), (0.6, 0.6)]   # tip at (0, 0), 1 tall


def for_script(build) -> dict:
    L = build.layer
    made: dict[str, dict] = {}              # pointer id -> {parent, x, y, t, size, kind, taps}

    def pointer(id="cursor", kind="arrow", x=None, y=None, size=None, color="#ffffff", outline="#111827", shadow=True):
        """A pointer whose (x, y) is its tip, made in the group it is called in (start: lower right of it)."""
        if kind not in ("arrow", "touch"):
            raise ValueError(f'pointer {id}: kind "{kind}" is not one of arrow, touch')
        pw, ph = U.parent_size(build)
        u = pw / U.BASE_W
        s = float(size or (34 if kind == "arrow" else 44) * u)
        x, y = float(pw * 0.78 if x is None else x), float(ph * 0.82 if y is None else y)
        if kind == "arrow":
            g = L("group", id, x=x, y=y, w=s * 0.6, h=s, anchorX=0, anchorY=0)
            with g:
                d = "M " + " L ".join(f"{px * s:.2f} {py * s:.2f}" for px, py in ARROW) + " Z"
                part = L("path", f"{id}_arrow", d=pathdata.check(d, id), x=0, y=0, w=s * 0.6, h=s * 0.96, anchorX=0, anchorY=0, fill=color, stroke=True, strokeColor=outline,
                         strokeWidth=max(s * 0.06, 1.5))
        else:
            g = L("group", id, x=x, y=y, w=s, h=s)
            with g:
                part = L("shape", f"{id}_dot", shape="ellipse", x=s / 2, y=s / 2, w=s, h=s, fill=color, fillOpacity=0.55,
                         stroke=True, strokeColor=outline, strokeWidth=max(s * 0.04, 1.5))
        if shadow:
            part.effect("shadow", f"{id}_shadow", dy=s * 0.12, radius=s * 0.22, strength=0.35)
        made[id] = {"parent": build.holders[-1]["id"], "x": x, "y": y, "t": None, "size": s, "kind": kind, "taps": 0, "outline": outline}
        return g

    def footprint(p, tx, ty):
        s = p["size"]
        return (tx - s * 0.08, ty - s * 0.08, s * 0.7, s * 1.08) if p["kind"] == "arrow" else (tx - s / 2, ty - s / 2, s, s)

    def texts(node):
        for c in node.get("layers", []):
            if c["type"] == "text":
                yield c["id"]
            yield from texts(c)

    def landing(p, target, given, at):
        bx, by, bw, bh = U.box_in(build.root, target.id, p["parent"], at)
        if given is not None:
            return bx + bw * given[0], by + bh * given[1]
        labels = [U.box_in(build.root, t, p["parent"], at) for t in texts(target.node)]
        best = None
        for fx, fy in SPOTS:
            tx, ty = bx + bw * fx, by + bh * fy
            hit = sum(overlap(footprint(p, tx, ty), lab) for lab in labels)
            if best is None or hit < best[0]:
                best = (hit, tx, ty)
            if hit == 0:
                break
        return best[1], best[2]

    def tap(pointer, target, at, move=0.7, ease="easeInOut", press=0.95, ripple=True, spot=None, ripple_color=None):
        """The pointer's tip glides (over `move` s) from where it was onto `target` beside its words, landing at `at`;
        a press scales the pointer and the target (to `press`) and back; `ripple` spreads a ring under the tip."""
        p = made.get(pointer.id)
        if p is None:
            raise ValueError(f"tap: {pointer.id} is not a pointer made in this script; make one with pointer()")
        tx, ty = landing(p, target, spot, at)
        t0 = max(at - move, p["t"] + 0.05 if p["t"] is not None else 0.0)
        pointer.key("x", {t0: (p["x"], ease), at: tx}).key("y", {t0: (p["y"], ease), at: ty})
        pointer.key("scale", {at: 1, at + 0.08: 0.86, at + 0.26: 1}, ease="easeOut")
        if press:
            bx, by, bw, bh = U.own_box(target.node, at)
            target.pivot(bx + bw / 2, by + bh / 2, at=at)
            target.key("scale", {at: 1, at + 0.08: press, at + 0.3: 1}, ease="easeOut")
        holder = U.chain(build.root, p["parent"])[-1]["layers"]
        holder.remove(pointer.node)
        if ripple:
            s = p["size"] * 1.6
            r = build.add("shape", f"{pointer.id}_ripple{p['taps']}", {"shape": "ellipse", "x": tx, "y": ty, "w": s, "h": s,
                          "fill": ripple_color or p["outline"], "fillOpacity": 0.22, "start": at, "end": at + 0.6}, holder)
            r.key("scale", {at: 0.2, at + 0.5: 1.4}, ease="easeOut").key("opacity", {at: 1, at + 0.5: 0}, ease="easeOut")
        holder.append(pointer.node)
        p.update(x=tx, y=ty, t=at + 0.26, taps=p["taps"] + 1)
        return pointer

    return {"pointer": pointer, "tap": tap}


def overlap(a, b) -> float:
    w = min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0])
    h = min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1])
    return w * h if w > 0 and h > 0 else 0.0
