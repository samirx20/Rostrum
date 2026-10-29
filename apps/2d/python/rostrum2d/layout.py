"""Auto layout: where a group's layers go at one time, when the group has a `layout` (row, column, grid, stack). The one
solver: the scene bake (layoutbake.py), the screen's boxes and the agents' geometry all read `solve`.

A laid-out group is a CSS box (fields: layout_fields.py) and the engine lays it out: every top laid-out group becomes a
tree of nodes (boxes, texts, leaves; ENGINE_CONTRACT.md § 1 `layout`) and the engine's own CSS flex / grid with real
text wrapping (Taffy + Parley, the code that draws the texts) gives each node its box, one round trip for every tree
of a frame (or of many frames: `plans` + `lay_out`). The same trees are answered once (kept by their JSON), so a layout
that doesn't move is one engine call per film.

- Sizes are the layers' own boxes (w × h; a text's laid out by the engine), before scale and turn: animating scale is
  a pop that doesn't push the others; animating w or h re-flows them. `shiftX` / `shiftY` move a layer on top of its
  place without pushing the others.
- Row / column: CSS flex; grid: CSS grid (`columns` equal columns or `columnsTemplate`); stack: every layer in one
  cell, placed by justify (across) and align (down).
- `sizeW` / `sizeH`: fixed (w / h), fit (a laid-out group follows what is inside it; with `hugPin` it grows from its
  top-left, as a design tool's frame: see `hugged`), fill (the room the parent layout leaves) or percent of it.
- A slot is kept, as CSS keeps one under opacity and transform: a layer takes its room for the layout's whole life,
  before its start, after its end, faded out, scaled to 0 or shifted by keys, so a row whose cards come in one by one
  never re-centres or jumps as they arrive or leave. Only a layer hidden on purpose (`hidden`) takes no room; a layer
  `layoutApart` keeps its own x, y (an absolute box). Layers that take turns in one place go in a stack (one cell).
- Layers are placed by their anchor: x = slot left + anchorX × w + shiftX (a group's layers live in its px from its
  top-left). A text the layout makes narrower (or wider) than its one line gets that `boxWidth`, so it wraps where the
  layout did.
- Only shapes, images and groups change size (fill, stretch, fit); a text changes its boxWidth; others keep theirs.
"""
from __future__ import annotations

import json
import threading

from . import boxes, textsize
from .evaluate import resolve
from .layout_fields import GROWS, SIZED
from .sizes import own_size

KEEP = 4096                 # answers kept; past it the table starts again
_lock = threading.RLock()
_answers: dict[str, dict] = {}


def has_layout(item: dict) -> bool:
    return item.get("type") == "group" and item.get("layout", "none") != "none"


def laid_out(item: dict) -> bool:
    """It, or a group inside it, has an auto layout (nothing else ever gets a place from `solve`)."""
    return has_layout(item) or any(laid_out(c) for c in item.get("layers", ()))


def takes_room(c: dict, p: dict) -> bool:
    """It holds a slot in its parent's layout: everything but a camera or a layer hidden on purpose. Its start..end,
    opacity, scale and shifts never free its slot (the module's rule: a layout doesn't jump as layers come and go)."""
    return c["type"] != "camera" and not p.get("hidden")


def members(group: dict, t: float, p_of=None) -> list[dict]:
    """The layers of a laid-out group that take a slot at t, in slot order (not cameras, not hidden, not set apart)."""
    p_of = p_of or (lambda c: resolve(c, t))
    return [c for c in group.get("layers", []) if takes_room(c, p_of(c)) and not p_of(c).get("layoutApart")]


def lay_out(trees: list[dict], per_request: int = 0) -> list[dict[str, tuple]]:
    """The engine's boxes of each tree ({node id: (x, y, w, h)}); trees answered before are not asked again, the rest go
    in one request (`per_request` > 0: at most that many trees a request)."""
    with _lock:
        keys = [json.dumps(t, sort_keys=True, separators=(",", ":")) for t in trees]
        new = list(dict.fromkeys(k for k in keys if k not in _answers))
        fresh = {}
        step = per_request or len(new) or 1
        for i in range(0, len(new), step):
            part = new[i:i + step]
            got = textsize.engine().layout([json.loads(k) for k in part])
            if len(got) != len(part):
                raise textsize.EngineError(f"layout: {len(part)} trees asked, {len(got)} answered")
            fresh.update(zip(part, got))
        out = [fresh[k] if k in fresh else _answers[k] for k in keys]
        if len(_answers) + len(fresh) > KEEP:
            _answers.clear()
        _answers.update(fresh)
        return out


def solve(comp: dict, t: float, props=None) -> dict[str, dict]:
    """{layer id: {x, y[, w, h][, boxWidth]}} for every layer an auto layout places or sizes at time t (others are left
    out). `props(item, t)`: the item's evaluated fields (default evaluate.resolve; the bake passes one that sees
    expressions)."""
    plan = Plan(comp, t, props)
    return plan.result(lay_out(plan.trees)) if plan.trees else {}


class Plan:
    """The layout trees of a composition at t (`trees`, for the engine) and how to read their boxes back (`result`)."""

    def __init__(self, comp: dict, t: float, props=None):
        self.t, self.props = t, props or resolve
        self._p: dict[str, dict] = {}
        self.items: dict[str, dict] = {}         # node id -> its layer
        self.trees: list[dict] = []
        self._in: set[str] = set()               # groups already a box of some tree
        if any(laid_out(layer) for layer in comp.get("layers", [])):
            self._walk(comp.get("layers", []))

    def p_of(self, item):
        if item["id"] not in self._p:
            self._p[item["id"]] = self.props(item, self.t)
        return self._p[item["id"]]

    def _walk(self, layers):
        for layer in layers:
            if has_layout(layer) and layer["id"] not in self._in:
                self.trees.append(self._box(layer, None))
            if layer["type"] == "group":
                self._walk(layer.get("layers", []))

    # ---- the trees ----
    def _box(self, group, parent):
        p = self.p_of(group)
        self._in.add(group["id"])
        self.items[group["id"]] = group
        kind = p["layout"]
        style = {"display": {"grid": "grid", "stack": "stack"}.get(kind, "flex")}
        if kind in ("row", "column"):
            style["direction"] = kind
            main, lines = ("columnGap", "rowGap") if kind == "row" else ("rowGap", "columnGap")
            style[main] = p["gap"]
            if p["wrap"]:
                style.update(wrap=True, **{lines: p["rowGap"]})
        elif kind == "grid":
            style.update(columns=p["columnsTemplate"].strip() or max(1, int(p["columns"])), columnGap=p["gap"],
                         rowGap=p["rowGap"])
        px = p["paddingX"] if p["paddingX"] >= 0 else p["padding"]
        py = p["paddingY"] if p["paddingY"] >= 0 else p["padding"]
        style["padding"] = [py, px, py, px]
        style["justify"], style["align"] = p["justify"], p["align"]
        if kind == "stack":                      # its layers share one cell: justify places each across it
            style["justify"] = _CELL.get(p["justify"], "start")
        if p.get("clip"):
            style["overflow"] = "hidden"
        for axis, field in (("W", "w"), ("H", "h")):
            mode = p[f"size{axis}"]
            if mode == "fit":                    # inside a box: auto, so a stretching parent stretches it (as CSS)
                style["width" if axis == "W" else "height"] = "fit" if parent is None else "auto"
            elif mode == "fixed" or parent is None:
                style["width" if axis == "W" else "height"] = p[field]
        self._child_style(group, p, parent, style)
        kids = [c for c in group.get("layers", []) if takes_room(c, self.p_of(c))         # a text set apart takes
                and not (c["type"] == "text" and self.p_of(c).get("layoutApart"))]             # no room, has nothing to lay out
        return {"id": group["id"], "kind": "box", "style": style, "children": [self._node(c, group) for c in kids]}

    def _node(self, c, group):
        p = self.p_of(c)
        if has_layout(c):
            return self._box(c, group)
        self.items[c["id"]] = c
        style: dict = {}
        if c["type"] == "text" and by_letter(p):        # drawn letter by letter: no wrap, a box of its own line
            w, h = textsize.size(p)
            style.update(width=w, height=h)
            self._child_style(c, p, group, style)
            return {"id": c["id"], "kind": "leaf", "style": style, "w": w, "h": h}
        if c["type"] == "text":
            text = dict(zip(textsize.FIELDS, textsize.key(p)))
            text.pop("boxWidth")
            if p["boxWidth"] > 0:
                style["width"] = p["boxWidth"]
            self._child_style(c, p, group, style)
            return {"id": c["id"], "kind": "text", "style": style, "text": text}
        w, h = own_size(c["type"], p)
        if c["type"] not in SIZED:               # a path, a video …: its size is its own
            style.update(width=w, height=h)
        self._child_style(c, p, group, style)
        return {"id": c["id"], "kind": "leaf", "style": style, "w": w, "h": h}

    def _child_style(self, c, p, group, style):
        """A layer's own place in its parent's layout (none for a tree's root)."""
        if group is None:
            return
        g = self.p_of(group)
        if p.get("layoutApart"):
            w, h = own_size(c["type"], p)
            style.update(position="absolute", left=p["x"] - p["anchorX"] * w, top=p["y"] - p["anchorY"] * h)
            return
        kind = g["layout"]
        cells = kind in ("grid", "stack")
        if kind == "grid":                       # across its cell as down it: as the group's align says
            style["justifySelf"] = _CELL.get(g["align"], "start")
        if p["alignSelf"] != "auto":
            style["alignSelf"] = p["alignSelf"]
        if p["margin"]:
            style["margin"] = p["margin"]
        if kind == "grid" and p["colSpan"] > 1:
            style["colSpan"] = int(p["colSpan"])
        grow = p.get("layoutGrow", 0.0) if c["type"] in GROWS else 0.0
        style["shrink"] = p["layoutShrink"]
        for axis, field in (("W", "width"), ("H", "height")):
            mode = p.get(f"size{axis}", "fixed")
            if mode == "percent":
                style[field] = f'{p[f"pct{axis}"]:g}%'
            elif mode == "fill":
                style[field] = "auto"            # not its own w / h: the layout gives it the room
                if cells:
                    style["justifySelf" if axis == "W" else "alignSelf"] = "stretch"
                elif (axis == "W") == (kind == "row"):           # along the line: takes the room left
                    grow, style["basis"] = max(grow, 1.0), 0
                else:
                    style["alignSelf"] = "stretch"
        if grow > 0:
            style["grow"] = grow

    # ---- the answer ----
    def texts(self, answers: list[dict], wrapped: bool) -> list[dict]:
        """The placed texts' fields: their own line (`wrapped` False), else at the width the layout gave the ones it
        made narrower or wider (their own line already measured). `prime_texts` measures them together."""
        out = []
        for tree in answers:
            for nid, (_, _, w, _) in tree.items():
                item = self.items.get(nid)
                if item is None or item["type"] != "text" or self.p_of(item).get("layoutApart"):
                    continue
                p = self.p_of(item)
                if not wrapped:
                    out.append(p)
                elif _narrowed(p, w) and not by_letter(p):
                    out.append({**p, "boxWidth": w})
        return out

    def result(self, answers: list[dict], primed: bool = False) -> dict[str, dict]:
        """{layer id: {x, y[, w, h][, boxWidth]}} from the engine's boxes of `trees` (`primed`: prime_texts ran)."""
        if not primed:
            prime_texts([(self, answers)])
        out = {}
        for tree, got in zip(self.trees, answers):
            root = self.items[tree["id"]]
            p = self.p_of(root)
            size = got[root["id"]][2:]
            if any(abs(a - b) > 1e-9 for a, b in zip(size, own_size("group", p))):
                out[root["id"]] = hugged(p, size)
            self._read(tree, got, out)
        return out

    def _read(self, node, got, out):
        for child in node.get("children", []):
            c = self.items[child["id"]]
            p = self.p_of(c)
            left, top, w, h = got[child["id"]]
            if p.get("layoutApart"):             # keeps its own x, y; a fitting group says its size
                if child["kind"] == "box" and any(abs(a - b) > 1e-9 for a, b in zip((w, h), own_size("group", p))):
                    out[c["id"]] = hugged(p, (w, h))
            else:
                ah = h
                o = {}
                if c["type"] == "text":
                    own_h = textsize.size(p)[1]
                    if _narrowed(p, w) and not by_letter(p):     # the layout narrowed (or widened) it: it wraps there
                        o["boxWidth"] = w
                        own_h = textsize.size({**p, "boxWidth": w})[1]
                    ah = min(h, own_h)           # stretched taller than its lines: its lines stay at the top
                o.update(x=left + p["anchorX"] * w + p["shiftX"], y=top + p["anchorY"] * ah + p["shiftY"])
                if c["type"] in SIZED and (abs(w - p["w"]) > 1e-9 or abs(h - p["h"]) > 1e-9):
                    o.update(w=w, h=h)
                out[c["id"]] = {k: round(v, 4) for k, v in o.items()}
            if child["kind"] == "box":
                self._read(child, got, out)


_CELL = {v: v for v in ("start", "center", "end", "stretch")}     # a place in a cell (between … baseline: start)


def by_letter(p: dict) -> bool:
    """A text the engine draws letter by letter (on a path, or its keys played letter by letter): it can't wrap, so
    the layout gives it the box of its own line (the engine's stage_type::by_letter)."""
    return bool(p.get("path")) or bool(p.get("letterDelay", 0))


def _narrowed(p: dict, w: float) -> bool:
    """The layout gave a text another width than its own box (half a px either way is the same)."""
    return abs(w - textsize.size(p)[0]) > 0.5


def prime_texts(pairs) -> None:
    """Measure the texts of [(plan, its answers)] in two engine trips: their own lines, then the ones the layout
    resized at their new width."""
    textsize.prime([p for plan, a in pairs for p in plan.texts(a, False)])
    textsize.prime([p for plan, a in pairs for p in plan.texts(a, True)])


def hugged(p: dict, size) -> dict:
    """A fitting group's own w, h and, with `hugPin`, its x, y moved so the edge the layout starts from stays where it
    was: left for a row (top for a column, both for a grid or stack), the other way across a row by `align`. An anchor
    off the middle is the person's choice: that axis keeps the anchor's own place, as it always did."""
    w0, h0 = own_size("group", p)
    o = {"w": size[0], "h": size[1]}
    if p["hugPin"]:
        across = {"center": 0.5, "end": 1.0}.get(p["align"], 0.0)
        fx, fy = {"row": (0.0, across), "column": (across, 0.0)}.get(p["layout"], (0.0, 0.0))
        gx = (p["anchorX"] - fx) * (size[0] - w0) if abs(p["anchorX"] - 0.5) < 1e-9 else 0.0
        gy = (p["anchorY"] - fy) * (size[1] - h0) if abs(p["anchorY"] - 0.5) < 1e-9 else 0.0
        a, b, c, d, _, _ = boxes.matrix(p, w0, h0)          # the box's own axes in the parent (scale and turn)
        o["x"], o["y"] = p["x"] + a * gx + c * gy, p["y"] + b * gx + d * gy
    return {k: round(v, 4) for k, v in o.items()}
