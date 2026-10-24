"""Auto layout: where a group's layers go at one time, when the group has a `layout` (row, column, grid). The one
solver: the scene bake (layoutbake.py), the screen's boxes and the agents' geometry all read `solve`.

The rules, like a design tool's auto layout (fields: layout_fields.py):
- Sizes are the layers' own boxes (w × h; a text's laid-out box from the engine, sizes.py), before scale and turn: animating
  scale is a pop that doesn't push the others; animating w or h re-flows them.
- Row / column: layers one after another, `gap` apart, inside `padding`. `justify` spreads them along the line,
  `align` places them across it (stretch fills it). `layoutGrow` shares out the room left along the line. `wrap`
  starts a new line (`rowGap` apart) when the next layer doesn't fit.
- Grid: `columns` equal columns `gap` apart, rows `rowGap` apart, each row as tall as its tallest layer;
  `align` places a layer in its cell (stretch fills the cell).
- `hugWidth` / `hugHeight`: the group's size follows what is inside it (no wrapping along a hugged line). With `hugPin`
  (on for new groups) it grows from its top-left, as a design tool's frame: see `hugged`.
- A layer outside its start..end takes no room; a layer `layoutApart` keeps its own x, y.
- Layers are placed by their anchor: x = slot left + anchorX × w (a group's layers live in its px from its top-left).
- Only shapes, images and groups change size (fill, stretch, hug); other layers keep theirs.
"""
from __future__ import annotations

import math

from . import boxes, textsize
from .evaluate import resolve
from .exprbake import items_of
from .layout_fields import SIZED
from .sizes import own_size

INF = math.inf


def has_layout(item: dict) -> bool:
    return item.get("type") == "group" and item.get("layout", "none") != "none"


def laid_out(item: dict) -> bool:
    """It, or a group inside it, has an auto layout (nothing else ever gets a place from `solve`)."""
    return has_layout(item) or any(laid_out(c) for c in item.get("layers", ()))


def members(group: dict, t: float, p_of=None) -> list[dict]:
    """The layers of a laid-out group that take a slot at t, in slot order (not cameras, not set apart, showing)."""
    p_of = p_of or (lambda c: resolve(c, t))
    return [c for c in group.get("layers", []) if c["type"] != "camera" and not p_of(c).get("layoutApart")
            and p_of(c)["start"] <= t < p_of(c)["end"]]


def solve(comp: dict, t: float, props=None) -> dict[str, dict]:
    """{layer id: {x, y[, w, h]}} for every layer an auto layout places or sizes at time t (others are left out).
    `props(item, t)`: the item's evaluated fields (default evaluate.resolve; the bake passes one that sees
    expressions)."""
    props = props or resolve
    memo_p, memo_m, out = {}, {}, {}

    def p_of(item):
        if item["id"] not in memo_p:
            memo_p[item["id"]] = props(item, t)
        return memo_p[item["id"]]

    def kids(group):
        return members(group, t, p_of)

    def measure(item):
        """The item's own size, with a hugging layout group's size from its layers."""
        if item["id"] not in memo_m:
            p = p_of(item)
            w, h = own_size(item["type"], p)
            if has_layout(item) and (p["hugWidth"] or p["hugHeight"]):
                _, cw, ch = arrange(item, INF if p["hugWidth"] else w, INF if p["hugHeight"] else h)
                pad = 2 * p["padding"]
                w, h = (cw + pad if p["hugWidth"] else w), (ch + pad if p["hugHeight"] else h)
            memo_m[item["id"]] = (w, h)
        return memo_m[item["id"]]

    def arrange(group, W, H):
        """([(layer, left, top, w, h)] in the group's px, content w, content h) for a group of size W × H."""
        p = p_of(group)
        if p["layout"] == "grid":
            return _grid(p, kids(group), measure, W, H)
        return _flow(p, kids(group), measure, lambda k: max(0.0, p_of(k).get("layoutGrow", 0.0)), W, H)

    def place(item, size):
        if has_layout(item):
            slots, _, _ = arrange(item, *size)
            for child, left, top, w, h in slots:
                cp = p_of(child)
                o = {"x": left + cp["anchorX"] * w, "y": top + cp["anchorY"] * h}
                if child["type"] in SIZED and (abs(w - cp["w"]) > 1e-9 or abs(h - cp["h"]) > 1e-9):
                    o.update(w=w, h=h)
                out[child["id"]] = {k: round(v, 4) for k, v in o.items()}
                place(child, (w, h))
            for child in item.get("layers", []):
                if child["id"] not in out:
                    free(child)
        else:                                      # a plain group may hold laid-out groups
            for child in item.get("layers", []):
                free(child)

    def free(child):
        """A layer no layout places: its own x, y, with a hugging group's size (and pinned edge) from its layers."""
        if not laid_out(child):                    # nothing in it is laid out: nothing to place (and nothing read)
            return
        size = measure(child)
        if has_layout(child) and size != own_size(child["type"], p_of(child)):
            out[child["id"]] = hugged(p_of(child), size)
        place(child, size)

    laid = [layer for layer in comp.get("layers", []) if laid_out(layer)]
    if laid:
        textsize.prime([p_of(i) for i in items_of(comp).values() if i["type"] == "text"])    # the frame's texts, one engine trip
    for layer in laid:
        free(layer)
    return out


def hugged(p: dict, size) -> dict:
    """A hugging group's own w, h and, with `hugPin`, its x, y moved so the edge the layout starts from stays where it
    was: left for a row (top for a column, both for a grid), the other way across a row by `align`. An anchor off the
    middle is the person's choice: that axis keeps the anchor's own place, as it always did."""
    w0, h0 = own_size("group", p)
    o = {"w": size[0], "h": size[1]}
    if p["hugPin"]:
        across = {"start": 0.0, "stretch": 0.0, "center": 0.5, "end": 1.0}[p["align"]]
        fx, fy = {"row": (0.0, across), "column": (across, 0.0)}.get(p["layout"], (0.0, 0.0))
        gx = (p["anchorX"] - fx) * (size[0] - w0) if abs(p["anchorX"] - 0.5) < 1e-9 else 0.0
        gy = (p["anchorY"] - fy) * (size[1] - h0) if abs(p["anchorY"] - 0.5) < 1e-9 else 0.0
        a, b, c, d, _, _ = boxes.matrix(p, w0, h0)          # the box's own axes in the parent (scale and turn)
        o["x"], o["y"] = p["x"] + a * gx + c * gy, p["y"] + b * gx + d * gy
    return {k: round(v, 4) for k, v in o.items()}


def _flow(p, kids, measure, grow, W, H):
    row = p["layout"] == "row"
    pad, gap = p["padding"], p["gap"]
    inner_main = (W if row else H) - 2 * pad
    inner_cross = (H if row else W) - 2 * pad
    sizes = [(m[0], m[1]) if row else (m[1], m[0]) for m in map(measure, kids)]     # (main, cross)
    lines, line = [], []
    used = 0.0
    for k, s in zip(kids, sizes):
        if line and p["wrap"] and inner_main < INF and used + gap + s[0] > inner_main + 1e-6:
            lines.append(line)
            line, used = [], 0.0
        used += (gap if line else 0.0) + s[0]
        line.append([k, s[0], s[1]])
    if line:
        lines.append(line)
    slots, cross_at, content_main = [], 0.0, 0.0
    for line in lines:
        total = sum(e[1] for e in line) + gap * (len(line) - 1)
        free = inner_main - total if inner_main < INF else 0.0
        grows = sum(grow(e[0]) for e in line)
        if free > 0 and grows > 0:
            for e in line:
                e[1] += free * grow(e[0]) / grows
            total, free = total + free, 0.0
        free = max(free, 0.0)
        start, step = {"start": (0.0, gap), "center": (free / 2, gap), "end": (free, gap),
                       "between": (0.0, gap + (free / (len(line) - 1) if len(line) > 1 else 0.0))}[p["justify"]]
        lc = max(e[2] for e in line)
        if len(lines) == 1 and inner_cross < INF:
            lc = inner_cross
        at = start
        for k, main, cross in line:
            if p["align"] == "stretch" and k["type"] in SIZED:
                cross = lc
            off = {"start": 0.0, "center": (lc - cross) / 2, "end": lc - cross, "stretch": 0.0}[p["align"]]
            m0, c0 = pad + at, pad + cross_at + off
            slots.append((k, m0, c0, main, cross) if row else (k, c0, m0, cross, main))
            at += main + step
        content_main = max(content_main, total)
        cross_at += lc + p["rowGap"]
    content_cross = max(cross_at - p["rowGap"], 0.0) if lines else 0.0
    return slots, (content_main if row else content_cross), (content_cross if row else content_main)


def _grid(p, kids, measure, W, H):
    pad, gap, rgap, n = p["padding"], p["gap"], p["rowGap"], max(1, int(p["columns"]))
    sizes = [measure(k) for k in kids]
    cols = min(n, len(kids)) or 1
    inner = W - 2 * pad
    cell_w = (inner - gap * (n - 1)) / n if inner < INF else max((s[0] for s in sizes), default=0.0)
    slots, top = [], pad
    for r in range(0, len(kids), n):
        row = list(zip(kids[r:r + n], sizes[r:r + n]))
        rh = max(s[1] for _, s in row)
        for c, (k, (w, h)) in enumerate(row):
            if p["align"] == "stretch" and k["type"] in SIZED:
                w, h = cell_w, rh
            fx = {"start": 0.0, "center": 0.5, "end": 1.0, "stretch": 0.0}[p["align"]]
            slots.append((k, pad + c * (cell_w + gap) + fx * (cell_w - w), top + fx * (rh - h), w, h))
        top += rh + rgap
    content_w = cols * cell_w + gap * (cols - 1) if kids else 0.0
    content_h = max(top - rgap - pad, 0.0) if kids else 0.0
    return slots, content_w, content_h
