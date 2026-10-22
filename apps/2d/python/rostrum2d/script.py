"""The 2D script layer: Python an agent (or a person) writes to build a document. Running it gives a tree;
rostrum_core merges that tree in (`run_script`), so a re-run never wipes what someone else changed.

    comp("intro", width=1920, height=1080, fps=30, duration=3, background="#05050a")
    title = text("title", body="Rostrum", size=220, weight=780)
    title.key("opacity", {0.2: 0, 0.9: 1}, ease="snappy")            # {time: value} or {time: (value, ease)}
    title.effect("gradient", color1="#ffffff", color2="#ff7a59")    # gradient letters
    title.mask("title_wipe", w=0).key("w", {0.2: 0, 1.0: 1400})
    title.expr("y", "540 + sin(time * 3) * 12")                      # a field driven by a small safe expression
    subtitle.link("x", of="title", field="x", offset=300)            # bound: value = title.x · scale + offset
    with group("lockup", x=960, y=700):                               # layers made inside go into the group
        shape("dot", shape="ellipse", w=24, h=24)
    flame = drawing("flame", w=800, h=1000)                           # frame-by-frame: one drawing per frame or held
    ink = flame.frame(0).paint("ink")                                 # drawing at frame 0, its paint layer
    ink.stroke([(400, 900), (380, 600, 0.6), (420, 300, 0.2)], color="#ffb040", size=40, brush="bristle")

Ids: the first argument; left out, they are counted per type (text_1, text_2 …), skipping every quoted word in
the script, so adding one item never renames another. Unknown fields and bad values fail loudly.
"""
from __future__ import annotations

import ast
import math

from rostrum_core import ids
from rostrum_core.errors import RostrumError, codes, did_you_mean
from rostrum_core.keys import key_id, marked

from . import fields as F, pathdata
from .expr import ExprError, parse
from .group_fit import fit
from .kind import KIND, LISTS
from .ops_expr import expr_id, link_source
from .rig import script as rig_script
from .swap import child_index
from .lipsync import script as lipsync_script

SAFE = {n: __builtins__[n] if isinstance(__builtins__, dict) else getattr(__builtins__, n)
        for n in ("range", "len", "min", "max", "abs", "round", "enumerate", "zip", "list", "dict", "float", "int",
                  "str", "sorted", "reversed", "sum", "isinstance", "ValueError")}


class Item:
    """A handle on one item the script made."""

    def __init__(self, build: "Build", node: dict):
        self._b, self.node, self.id = build, node, node["id"]

    def set(self, **values) -> "Item":
        self._b.fill(self.node, values)
        return self

    def key(self, prop: str, keys: dict, ease: str = "smooth") -> "Item":
        allowed = F.animatable(self.node["type"])
        if prop not in allowed:
            raise ValueError(f'{self.id}: "{prop}" can\'t be animated on a {self.node["type"]}; animatable: '
                             f"{', '.join(allowed)}" + _hint(prop, allowed))
        p = F.param(self.node["type"], prop)
        for t, v in sorted(keys.items(), key=lambda kv: marked.order(kv[0])):   # a time: seconds or "#drop+0.2"
            value, e = v if isinstance(v, tuple) else (v, ease)
            t = F.param("key", "t").check(t, f"{self.id}.{prop} key time")
            k = {"id": key_id(self.id, prop, t), "type": "key", "prop": prop, "t": t if isinstance(t, str) else float(t),
                 F.key_field(self.node["type"], prop): p.check(value, f"{self.id}.{prop} at {t} s"), "ease": e}
            F.param("key", "ease").check(e, f"{self.id}.{prop} at {t} s")
            self.node["keys"].append(k)
        return self

    def show(self, choices: dict) -> "Item":
        """Key a swap set's choice: `mouth.show({0: "open", 1.2: "closed", 1.3: 0})`, {time: child or its place} (swap.py)."""
        kids = [c["id"] for c in self.node.get("layers", [])]
        return self.key("show", {t: (child_index(kids, getattr(v, "id", v)), "hold") for t, v in choices.items()})

    def expr(self, prop: str, source: str) -> "Item":
        """Drive a field by an expression: `title.expr("x", "sin(time * 3) * 40 + 960")` (expr.py)."""
        allowed = F.animatable(self.node["type"])
        if prop not in allowed:
            raise ValueError(f'{self.id}: "{prop}" can\'t take an expression on a {self.node["type"]}; fields: '
                             f"{', '.join(allowed)}" + _hint(prop, allowed))
        try:
            parse(source)
        except ExprError as e:
            raise ValueError(e.at(f"{self.id}.{prop}", source)) from None
        self.node["exprs"] = [e for e in self.node["exprs"] if e["prop"] != prop]
        self.node["exprs"].append({"id": expr_id(self.id, prop), "type": "expr", "prop": prop, "source": source})
        return self

    def link(self, prop: str, of: str, field: str, scale: float = 1.0, offset: float = 0.0) -> "Item":
        """Bind a field to another item's field: value = other · scale + offset."""
        return self.expr(prop, link_source(of, field, scale, offset))

    def effect(self, type_: str, id: str | None = None, **values) -> "Item":
        if type_ not in F.EFFECTS:
            raise ValueError(f'"{type_}" is not an effect; effects: {", ".join(F.EFFECTS)}' + _hint(type_, F.EFFECTS))
        return self._b.add(type_, id, values, self.node["effects"])

    def mask(self, id: str | None = None, **values) -> "Item":
        return self._b.add("mask", id, values, self.node["masks"])

    # drawing layers (painting kit): drawing.frame(at) -> frame.paint() -> paint.stroke(points, **brush)
    def frame(self, at: int, id: str | None = None) -> "Item":
        self._need("drawing", "frame")
        node = {"id": self._b.new_id("frame", id), "type": "frame", "at": F.param("frame", "at").check(at, "frame"),
                "paints": [], "paintmasks": []}
        frames = self.node["frames"]
        if any(f["at"] == node["at"] for f in frames):
            raise ValueError(f"{self.id} already has a drawing at frame {node['at']}")
        frames.insert(sum(1 for f in frames if f["at"] < node["at"]), node)
        return Item(self._b, node)

    def paint(self, id: str | None = None, **values) -> "Item":
        self._need("frame", "paint")
        return self._b.add_kit("paint", id, values, self.node["paints"])

    def paintmask(self, points, id: str | None = None, **values) -> "Item":
        self._need("frame", "paintmask")
        return self._b.add_kit("paintmask", id, {"points": points, **values}, self.node["paintmasks"])

    def stroke(self, points, id: str | None = None, **brush) -> "Item":
        self._need("paint", "stroke")
        return self._b.add_kit("stroke", id, {"points": points, **brush}, self.node["strokes"])

    def _need(self, type_, what):
        if self.node["type"] != type_:
            raise ValueError(f"{self.id} is a {self.node['type']}; .{what}() is for a {type_}")

    def __enter__(self):
        if self.node["type"] not in ("group", "rig"):
            raise ValueError(f"{self.id} is a {self.node['type']}; only a group or a rig holds layers")
        self._b.holders.append(self.node)
        return self

    def __exit__(self, *exc):
        self._b.holders.pop()
        if self.node["type"] == "group" and not exc[0] and self.id not in self._b.sized:
            fit(self.node)


class Build:
    def __init__(self, reserved=()):
        self.root, self.holders, self.reserved, self.taken = KIND.blank(), [], set(reserved), set()
        self.sized = set()          # groups whose script gave a size (w or h): never refitted

    def new_id(self, type_, id_):
        if id_ is None:
            id_ = ids.counted(self.taken, type_, self.reserved)
        if not ids.is_valid(id_):
            raise ValueError(f'"{id_}" is not a usable id (letters, digits, _ . -; not starting with a digit)')
        if id_ in self.taken:
            raise ValueError(f'id "{id_}" is used twice in the script')
        self.taken.add(id_)
        return id_

    def fill(self, node, values):
        known = [p.name for p in F.FIELDS[node["type"]]]
        for k, v in values.items():
            if k == "name":
                node["name"] = str(v)
                continue
            if k not in known:
                raise ValueError(f'a {node["type"]} has no field "{k}"; it has: {", ".join(known)}' + _hint(k, known))
            node[k] = F.param(node["type"], k).check(v, f'{node["id"]}.{k}')
            if node["type"] == "group" and k in ("w", "h"):
                self.sized.add(node["id"])

    def add(self, type_, id_, values, into: list) -> Item:
        node = {"id": self.new_id(type_, id_), "type": type_, "name": F.LABELS[type_], **F.defaults(type_)}
        for key in LISTS.get(type_, []):
            node[key] = []
        self.fill(node, values)
        into.append(node)
        return Item(self, node)

    def add_kit(self, type_, id_, values, into: list) -> Item:
        from rostrum_paint.ops import build
        node = build(type_, self.new_id(type_, id_), values, f"{type_} {id_ or ''}".strip())
        into.append(node)
        return Item(self, node)

    def comp(self, id=None, **values) -> Item:
        item = self.add("comp", id, values, self.root["comps"])
        self.holders = [item.node]
        return item

    def layer(self, type_, id=None, **values) -> Item:
        if not self.holders:
            raise ValueError(f"make a composition first: comp(...) before {type_}(...)")
        return self.add(type_, id, values, self.holders[-1]["layers"])


def _hint(word, options) -> str:
    h = did_you_mean(word, options)
    return f" {h}" if h else ""


def _reserved(source: str) -> set[str]:
    try:
        return {n.value for n in ast.walk(ast.parse(source)) if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    except SyntaxError:
        return set()


def _import(name, *args, **kw):
    """Scripts can't import; `import math` just gives the math that is already there."""
    if name == "math":
        return math
    raise ImportError(f"scripts can't import {name!r}; math, range, len, min, max, abs, round, enumerate, zip, "
                      "sorted, sum … are already there")


def run_source(source: str, name: str) -> dict:
    """Python source -> the document tree it builds. Any error is a loud BAD_ARGUMENT naming the line; nothing is merged."""
    b = Build(_reserved(source))
    scope = {"__builtins__": {**SAFE, "__import__": _import}, "math": math, "comp": b.comp,
             **{t: (lambda id=None, _t=t, **v: b.layer(_t, id, **v)) for t in F.LAYERS},
             **pathdata.for_script(b.layer), **rig_script.for_script(b),
             **lipsync_script.for_script(b)}
    try:
        exec(compile(source, name, "exec"), scope)
    except Exception as e:
        line = next((f" (line {fr.lineno})" for fr in _frames(e) if fr.filename == name), "")
        raise RostrumError(codes.BAD_ARGUMENT, "", f'script "{name}"', f"failed{line}: {type(e).__name__}: {e}",
                           ["comp(id, **fields)", "shape / text / image / group(id, **fields)",
                            "item.key(field, {time: value}, ease=)", "item.effect(type, id, **fields)",
                            "item.mask(id, **fields)", "item.set(**fields)", "with rig(id): bone(id, parent=, ...) / ik(id, bone=) / bind(layer=, bone=)", "path(id, d=star(5, 100, 45))", "drawing.frame(at)", "frame.paint(id)",
                            "paint.stroke(points, **brush)", "frame.paintmask(points)"]) from e
    return b.root


def _frames(e):
    import traceback
    return traceback.extract_tb(e.__traceback__)
