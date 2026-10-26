"""The 2D script layer: Python an agent (or a person) writes to build a document. Running it gives a tree;
rostrum_core merges that tree in (`run_script`), so a re-run never wipes what someone else changed.

    comp("intro", width=1920, height=1080, fps=30, duration=3, background="#05050a")
    title = text("title", body="Rostrum", size=220, weight=780)
    title.key("opacity", {0.2: 0, 0.9: 1}, ease="snappy")            # {time: value}, {time: (value, ease)} or {time: (value, "spring", {"bounce": 0.3, "speed": 0.4})}
    title.effect("gradient", color1="#ffffff", color2="#ff7a59")    # gradient letters
    title.mask("title_wipe", w=0).key("w", {0.2: 0, 1.0: 1400})
    title.expr("y", "540 + sin(time * 3) * 12")                      # a field driven by a small safe expression
    subtitle.link("x", of="title", field="x", offset=300)            # bound: value = title.x · scale + offset
    with group("lockup", x=960, y=700):                               # layers made inside go into the group
        shape("dot", shape="ellipse", w=24, h=24)
    f = frame()                                                       # the scene's frame (its camera), made with comp()
    f.key("x", {0: 960, 4: 2600}, ease="easeInOut")                   # a push across the world
    f.fit(["hills", "tree"], at=6); f.cut(at="#logo lands", to="rect", rect=(3200, 0, 1920, 1080))   # frame layers; a cut
    pin(title); set_depth("hills", 3)                                 # pinned to the frame / far away, each where it shows at 0 s
    flame = drawing("flame", w=800, h=1000)                           # frame-by-frame: one drawing per frame or held
    ink = flame.frame(0).paint("ink")                                 # drawing at frame 0, its paint layer
    ink.stroke([(400, 900), (380, 600, 0.6), (420, 300, 0.2)], color="#ffb040", size=40, brush="bristle")
    grain = painting("paper grain", w=128, h=128, seamless=True)      # a painting of the scene, in its own px (paintings.py)
    grain.stroke([(10, 20, .6), (118, 24, .8)], brush="bristle", color="#c1683a", size=6)     # on its first drawing's Ink layer
    shape("card", w=300, h=380, fill=painted(grain, fit="tile", scale=0.78, drift=(12, 0)))   # many layers may use one

Ids: the first argument; left out, they are counted per type (text_1, text_2 …), skipping every quoted word in
the script, so adding one item never renames another. Unknown fields and bad values fail loudly; `title.end = 4` is
`title.set(end=4)` and `title.end` reads it back, so no write is ever dropped.
"""
from __future__ import annotations

import ast
import math
import re

from rostrum_core import ids
from rostrum_core.errors import RostrumError, codes, did_you_mean
from rostrum_core.keys import key_id, marked
from rostrum_core.keys.ops import SHAPE_EASE
from rostrum_core.seeded import SeededRandom, no_classes

from . import fields as F, fontlist, paint_grow, pathdata, script_frame, script_words as W
from .expr import ExprError, parse
from .frame import make as frame_make, view as frame_view
from .group_fit import fit
from .kind import KIND, LISTS
from .ops_expr import expr_id, link_source
from .rig import script as rig_script
from .swap import child_index
from .lipsync import script as lipsync_script

# Python's plain built-ins a script may use (start-here.md lists them; keep the two the same). No print (the MCP
# server talks over stdout), no open / eval / exec / getattr / type: a script only builds the document.
BUILTINS = ("range", "len", "min", "max", "abs", "round", "sum", "divmod", "pow", "enumerate", "zip", "map", "filter",
            "sorted", "reversed", "any", "all", "list", "dict", "tuple", "set", "frozenset", "float", "int", "str", "bool",
            "isinstance", "chr", "ord", "ValueError", "KeyError", "IndexError", "TypeError", "ZeroDivisionError")
SAFE = {n: __builtins__[n] if isinstance(__builtins__, dict) else getattr(__builtins__, n)
        for n in BUILTINS}


class NoField(AttributeError):
    """Reading a field an item doesn't have: an AttributeError (so getattr(item, name, default) still works), told as
    plainly as a wrong write."""


class Item:
    """A handle on one item the script made. Its fields read and write as attributes through the one field check:
    `title.end = 4` is `title.set(end=4)` and `title.end` reads it back; a name that is not a field fails loudly, so no
    write is ever dropped."""
    _OWN = ("_b", "node", "id", "d_shift", "drawings")      # the handle's own attributes, not the item's fields

    def __init__(self, build: "Build", node: dict):
        object.__setattr__(self, "_b", build)
        object.__setattr__(self, "node", node)
        object.__setattr__(self, "id", node["id"])
        self.d_shift = None         # a path placed from its own points: its d keys move with it (pathdata.for_script)

    def __setattr__(self, name, value):
        if name == "id":
            raise ValueError(f'{self.id}.id = …: an id is given when the item is made ({self.node["type"]}("{value}", …)); '
                             "it can't change after")
        if name in Item._OWN:
            object.__setattr__(self, name, value)
        elif callable(getattr(type(self), name, None)):
            raise ValueError(f"{self.id}.{name} = …: {name} is a call, not a field; write {self.id}.{name}(…)")
        else:
            self.set(**{name: value})

    def __getattr__(self, name):          # only names that aren't the handle's own: the item's fields
        node = self.__dict__.get("node")
        if node is None or name.startswith("__"):
            raise AttributeError(name)
        known = [p.name for p in F.FIELDS.get(node["type"], [])]
        if name in known or name == "name":
            return node.get(name, F.defaults(node["type"]).get(name))
        raise NoField(f'{node["id"]}.{name}: a {node["type"]} has no field "{name}".{_hint(name, known)} Its fields: {", ".join(known)}')

    def set(self, **values) -> "Item":
        self._b.fill(self.node, values)
        return self

    def key(self, prop: str, keys: dict, ease: str = "smooth") -> "Item":
        allowed = F.animatable(self.node["type"])
        prop = W.field(prop, [p.name for p in F.FIELDS[self.node["type"]]], self.node["type"])
        if prop not in allowed:
            raise ValueError(f'{self.id}: "{prop}" can\'t be animated on a {self.node["type"]}{W.not_a_field(prop)}.'
                             f"{'' if W.not_a_field(prop) else _hint(prop, allowed)} Animatable: {', '.join(allowed)}")
        p = F.param(self.node["type"], prop)
        for t, v in sorted(keys.items(), key=lambda kv: marked.order(kv[0])):   # a time: seconds or "#drop+0.2"
            value, e, *shape = v if isinstance(v, tuple) else (v, ease)
            if prop == "d" and isinstance(value, str):
                value = pathdata.shifted(value, self.d_shift)
            if len(shape) > 1 or (shape and not isinstance(shape[0], dict)):
                raise ValueError(f'{self.id}.{prop}: a key is value, (value, "ease") or (value, "ease", {{"bounce": 0.3, "speed": 0.4}})')
            t = F.param("key", "t").check(t, f"{self.id}.{prop} key time")
            k = {"id": key_id(self.id, prop, t), "type": "key", "prop": prop, "t": t if isinstance(t, str) else float(t),
                 F.key_field(self.node["type"], prop): p.check(value, f"{self.id}.{prop} at {t} s"), "ease": e}
            k["ease"] = e = F.param("key", "ease").check(e, f"{self.id}.{prop} at {t} s")
            for name, x in (shape[0] if shape else {}).items():          # a spring's bounce / speed, a custom ease's handles
                if name not in SHAPE_EASE:
                    raise ValueError(f'{self.id}.{prop} at {t} s: "{name}" is not a curve field; they are {", ".join(SHAPE_EASE)}' + _hint(name, SHAPE_EASE))
                if e != SHAPE_EASE[name]:
                    raise ValueError(f'{self.id}.{prop} at {t} s: "{name}" only applies to a {SHAPE_EASE[name]} ease, this key is {e}')
                k[name] = F.param("key", name).check(x, f"{self.id}.{prop} at {t} s {name}")
            # a key at a time this field already has a key (an earlier key() or f.cut / f.fit) replaces it: the later call wins
            self.node["keys"] = [o for o in self.node["keys"] if o["id"] != k["id"]] + [k]
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
        self._need(("drawing", "painting"), "frame")
        node = {"id": self._b.new_id("frame", id), "type": "frame", "at": F.param("frame", "at").check(at, "frame"),
                "paints": [], "paintmasks": []}
        frames = self.node["frames"]
        if any(f["at"] == node["at"] for f in frames):
            raise ValueError(f"{self.id} already has a drawing at frame {node['at']}: call {self.id}.frame({node['at']}) once, "
                             f"keep what it returns (f = {self.id}.frame({node['at']})) and paint more on f, or use another frame")
        frames.insert(sum(1 for f in frames if f["at"] < node["at"]), node)
        item = Item(self._b, node)
        item.drawings = frames
        return item

    def paint(self, id: str | None = None, **values) -> "Item":
        """A paint layer on this drawing. Drawings of one layer share their paint layers: one made without `layer=` joins
        the layer at the same place in the layer's other drawings, so the same call in every drawing is the same paint layer."""
        self._need("frame", "paint")
        paints = self.node["paints"]
        if "layer" not in values:
            ref = next((f["paints"][len(paints)] for f in getattr(self, "drawings", []) if f is not self.node
                        and len(f["paints"]) > len(paints)), None)
            if ref is not None:
                values["layer"] = ref.get("layer") or ref["id"]
        return self._b.add_kit("paint", id, values, paints)

    def paintmask(self, points, id: str | None = None, **values) -> "Item":
        self._need("frame", "paintmask")
        return self._b.add_kit("paintmask", id, {"points": points, **values}, self.node["paintmasks"])

    def stroke(self, points, id: str | None = None, **brush) -> "Item":
        if self.node["type"] == "painting":              # the shortcut: its first drawing and its Ink layer, made when missing
            return self._ink().stroke(points, id, **brush)
        self._need("paint", "stroke")
        return self._b.add_kit("stroke", id, {"points": points, **brush}, self.node["strokes"])

    def fill(self, points, id: str | None = None, **values) -> "Item":
        """A filled polygon on this paint layer, sharp-edged, in painting order (the kit's fill: what paint.fill makes
        from a click): `ink.fill([(x, y), …], color="#2a2340")` for a ridge or a silhouette; [x, y, ring] for holes."""
        self._need("paint", "fill")
        return self._b.add_kit("fill", id, {"points": [[*p[:2], p[2] if len(p) > 2 else 0] for p in points], **values},
                               self.node["strokes"])

    def _ink(self) -> "Item":
        frames = self.node["frames"]
        frame = Item(self._b, frames[0]) if frames else self.frame(0)
        paints = frame.node["paints"]
        return Item(self._b, paints[0]) if paints else frame.paint(name="Ink")

    def _need(self, type_, what):
        types = (type_,) if isinstance(type_, str) else type_
        if self.node["type"] not in types:
            raise ValueError(f"{self.id} is a {self.node['type']}; .{what}() is for a {' or '.join(types)}")

    def __enter__(self):
        if self.node["type"] not in ("group", "rig"):
            raise ValueError(f"{self.id} is a {self.node['type']}; only a group or a rig holds layers")
        self._b.holders.append(self.node)
        return self

    def __exit__(self, *exc):
        self._b.holders.pop()
        if self.node["type"] == "group" and not exc[0] and self.id not in self._b.sized:
            fit(self.node)


class Painted:
    """What `painted(painting, fit=, scale=, offset=(x, y), rotation=, drift=(x, y), under=, blend=, opacity=, phase=)` gives:
    a shape's or path's fill from a painting of the document; `fill=` takes it."""
    NAMES = {"fit": "fillFit", "scale": "fillScale", "rotation": "fillRotation", "under": "fillUnder", "blend": "fillBlend",
             "opacity": "fillOpacity", "phase": "fillPhase"}

    def __init__(self, painting, offset=None, drift=None, **fields):
        unknown = set(fields) - set(self.NAMES)
        if unknown:
            raise ValueError(f'painted() has no "{sorted(unknown)[0]}"; it takes {", ".join(sorted([*self.NAMES, "offset", "drift"]))}')
        self.id = getattr(painting, "id", painting)
        self.values = {self.NAMES[k]: v for k, v in fields.items()}
        for word, prop in (("offset", "fillOffset"), ("drift", "fillDrift")):
            xy = offset if word == "offset" else drift
            if xy is not None:
                if not isinstance(xy, (tuple, list)) or len(xy) != 2:
                    raise ValueError(f"painted({word}=…) is a pair: ({word}=(x, y))")
                self.values[prop + "X"], self.values[prop + "Y"] = xy

    def __setattr__(self, name, value):
        if name in ("id", "values") and name not in self.__dict__:
            return object.__setattr__(self, name, value)
        raise ValueError(f"painted(…).{name} = …: a painted fill is set when made; give it there, "
                         f"painted(painting, {name}=…), and pass that to fill=")

    def fields(self) -> dict:
        return {"filled": True, "fillType": "painted", "fillPainting": self.id, **self.values}


class FrameItem(Item):
    """The scene's frame: an Item that also frames and cuts, through the operations (script_frame.py)."""

    def fit(self, items=None, at=0, rect=None, pad=None, keep_rotation=None) -> "FrameItem":
        script_frame.run(self._b, self.node, "frame.fit", script_frame.args_of(items, at=at, rect=rect, pad=pad, keep_rotation=keep_rotation))
        return self

    def cut(self, at, to=None, items=None, rect=None, pad=None, keep_rotation=None) -> "FrameItem":
        script_frame.run(self._b, self.node, "frame.cut", script_frame.args_of(items, at=at, to=to, rect=rect, pad=pad, keep_rotation=keep_rotation))
        return self

    def home(self, at=0) -> "FrameItem":
        script_frame.run(self._b, self.node, "frame.home", {"at": at})
        return self


class Build:
    def __init__(self, reserved=()):
        self.root, self.holders, self.reserved, self.taken = KIND.blank(), [], set(reserved), set()
        self.sized = set()          # groups whose script gave a size (w or h): never refitted
        self.counts: dict[str, int] = {}     # type -> the last counted N (new_id)

    def new_id(self, type_, id_):
        if id_ is None:         # ids only get taken, so the next free N per type is never below the last one given
            id_ = ids.counted(self.taken, type_, self.reserved, start=self.counts.get(type_, 1))
            self.counts[type_] = int(id_.rsplit("_", 1)[1])
        if not ids.is_valid(id_):
            raise ValueError(f'"{id_}" is not a usable id (letters, digits, _ . -; not starting with a digit)')
        if id_ in self.taken and type_ == "paint":
            raise ValueError(f'paint layer id "{id_}" is used twice: drawings share their paint layers, but each paint layer '
                             f'has its own id. In a loop over drawings write f.paint() (it joins the layer made in the first drawing) '
                             f'or f.paint(f"{id_}{{i}}", layer="{id_}")')
        if id_ in self.taken:
            raise ValueError(f'id "{id_}" is used twice in the script: every id (layers, effects, masks) '
                             f'is one in the whole document. Give each its own (f"{id_}{{i}}" in a loop), or leave the id '
                             f'out and one is counted for you')
        self.taken.add(id_)
        return id_

    def fill(self, node, values):
        if isinstance(values.get("fill"), Painted):         # fill=painted(grain, fit="tile", …): a painted fill, the fields below
            values = {**{k: v for k, v in values.items() if k != "fill"}, **values["fill"].fields()}
        params = F.FIELDS[node["type"]]
        known = [p.name for p in params]
        kinds = {p.name: p.type for p in params}
        for k, v in W.resolve(node["type"], values, known, kinds.get).items():
            if k == "name":
                node["name"] = str(v)
                continue
            if k not in known:
                by = sorted(params, key=lambda p: ("primary", "secondary", "deep").index(p.importance))
                raise ValueError(f'a {node["type"]} has no field "{k}"{W.not_a_field(k) + "." if W.not_a_field(k) else "." + _hint(k, known)} '
                                 f'Its fields, most used first: {", ".join(p.name for p in by)}')
            node[k] = F.param(node["type"], k).check(v, f'{node["id"]}.{k}')
            if node["type"] == "group" and k in ("w", "h"):
                self.sized.add(node["id"])
        if node["type"] in ("text", "textstyle") and {"font", "italic"} & set(node) and (
                why := fontlist.setting_refusal(node["id"], node["font"], node.get("italic", False))):
            raise ValueError(why)                       # a font that isn't here is never swapped for another

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

    def painting(self, id=None, **values) -> Item:
        """A painting of the document (paintings.py): its size, Seamless, its drawings; layers use it with painted().
        The first word is its id; written as words ("paper grain") it is its name and the id is counted."""
        if id is not None and not ids.is_valid(id):
            values.setdefault("name", id)
            id = None
        item = self.add("painting", id, values, self.root.setdefault("paintings", []))
        if "name" not in values:
            item.node["name"] = id or F.LABELS["painting"]
        return item

    def comp(self, id=None, **values) -> Item:
        item = self.add("comp", id, values, self.root["comps"])
        self.holders = [item.node]
        node = frame_make.new(item.node, self.taken | self.reserved)
        self.taken.add(node["id"])
        item.node["layers"].insert(0, node)
        return item

    def frame(self, **values) -> Item:
        """The current scene's frame (made with comp()), its fields set from `values`."""
        if not self.holders:
            raise ValueError("make a composition first: comp(...) before frame()")
        return FrameItem(self, frame_view.of(self.holders[0])).set(**values)

    def camera(self, id=None, **values) -> Item:
        """An older script's camera: the scene's one frame now (FRAME.md). Several cameras are cuts of the frame."""
        timed = sorted({"start", "end", "marker", "endMarker"} & set(values))
        if timed:
            raise ValueError(f"camera({', '.join(f'{k}=' for k in timed)}…): a scene has one frame, which is its camera, "
                             "so there is no camera to switch to. Make a cut instead: frame().key(\"x\", {2.4: (960, \"hold\"), "
                             "2.5: 3200}) jumps the frame at 2.5 s (the key before a cut has the hold ease)")
        return self.frame(**values)

    def layer(self, type_, id=None, **values) -> Item:
        if not self.holders:
            raise ValueError(f"make a composition first: comp(...) before {type_}(...)")
        return self.add(type_, id, values, self.holders[-1]["layers"])


def _hint(word, options) -> str:
    h = did_you_mean(word, options)
    return f" {h}" if h else ""


def _check_links(root: dict, made: set[str]) -> None:
    """A track matte, a followed path and a ridden path must be a layer beside the layer (same group or comp). One the
    script made somewhere else fails here, saying where to make it; one it didn't make may be a person's (diagnose)."""
    def walk(holder):
        layers = holder.get("layers", [])
        beside = {n["id"] for n in layers}
        for n in layers:
            for f in ("matte", "pathLayer", "ridePath"):
                ref = n.get(f)
                if ref and ref not in beside and ref in made:
                    raise ValueError(f'{n["id"]}.{f} = "{ref}": that layer must be beside {n["id"]} (in the same group '
                                     f'or comp), not inside another group. Make "{ref}" next to "{n["id"]}", or move '
                                     f'"{n["id"]}" into the group that holds "{ref}"')
            walk(n)
    for c in root["comps"]:
        walk(c)


def _grow_drawings(root: dict) -> None:
    """Every drawing grown to hold its strokes, as a painted stroke grows it (paint_grow.hold_strokes)."""
    from rostrum_core.tree import walk
    for item in walk(root, KIND.lists):
        if item.get("type") == "drawing":
            paint_grow.hold_strokes(item)


def _reserved(source: str) -> set[str]:
    try:
        return {n.value for n in ast.walk(ast.parse(source)) if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    except SyntaxError:
        return set()


def _importer(rnd):
    """Scripts can't import; `import math` / `import random` just give what is already there (random is seeded)."""
    def _import(name, *args, **kw):
        if name in ("math", "random"):
            return math if name == "math" else rnd
        raise ImportError(f"scripts can't import {name!r}; math and random (seeded: the same numbers every run, "
                          "random(7) for your own seed) are already there, and these built-ins: " + ", ".join(BUILTINS))
    return _import


def _held_ids(doc, name: str) -> set[str]:
    """The ids the document holds that this script did not make last run (a person's, another script's, another scene's
    frame): a new scene or layer must not take them, or the merge can't add it (a scene would arrive without its frame)."""
    from rostrum_core.tree import walk
    if doc is None:
        return set()
    ours = {i["id"] for i in walk(doc.script_bases.get(name) or {"id": "root", "comps": []}, KIND.lists)}
    return {i["id"] for i in walk(doc.data, KIND.lists)} - ours


def run_source(source: str, name: str, doc=None) -> dict:
    """Python source -> the document tree it builds. Any error is a loud BAD_ARGUMENT naming the line; nothing is merged.
    `doc`: the document it will be merged into (run_script passes it), so the ids it already holds are left alone."""
    b = Build(_reserved(source) | _held_ids(doc, name))
    rnd = SeededRandom(1)
    scope = {"__builtins__": {**SAFE, "__import__": _importer(rnd), "__build_class__": no_classes}, "math": math, "random": rnd, "comp": b.comp,
             **{t: (lambda id=None, _t=t, **v: b.layer(_t, id, **v)) for t in F.PLACED}, "frame": b.frame, "camera": b.camera, "painting": b.painting, "painted": Painted,
             "pin": lambda layer, on=True, at=0, keep="shown": script_frame.pin(b, layer, on, at, keep),
             "set_depth": lambda layer, depth, at=0, keep="shown": script_frame.set_depth(b, layer, depth, at, keep),
             **pathdata.for_script(b.layer), **rig_script.for_script(b),
             **lipsync_script.for_script(b)}
    try:
        exec(compile(source, name, "exec"), scope)
        _grow_drawings(b.root)
        _check_links(b.root, b.taken)
    except Exception as e:
        raise _failed(e, name, scope) from e
    return b.root


run_source.wants_doc = True            # rostrum_core's run_script tool then passes the document

API = ["comp(id, **fields)", "shape / text / image / path / group(id, **fields)", "frame(**fields): the scene's frame",
       "frame().fit(layers | rect=(x, y, w, h), at=) / .cut(at=, to=, rect=) / .home(at=)", "pin(layer, on=True, at=0)", "set_depth(layer, depth, at=0)", "item.key(field, {time: value}, ease=)",
       "item.effect(type, id, **fields)", "item.mask(id, **fields)", "item.set(**fields) / item.field = value",
       "with group(id, **fields): …", "with rig(id): bone(id, parent=, ...) / ik(id, bone=) / bind(layer=, bone=)",
       "path(id, d=star(5, 100, 45))", "drawing.frame(at)", "frame.paint(id)", "paint.stroke(points, **brush)", "paint.fill(points, color=)",
       "frame.paintmask(points)", "painting(id, w=, h=, seamless=)", "painting.stroke(points, **brush)",
       "shape / path(id, fill=painted(painting, fit=, scale=, offset=(x, y), rotation=, drift=(x, y), under=, blend=, opacity=))"]


def _failed(e: Exception, name: str, scope: dict) -> RostrumError:
    """The script's error as one line to act on: where (the line), what is wrong, and what to write instead. A value
    check keeps its own Accepted and hint; the list of script names only comes with a wrong name or call."""
    line = e.lineno if isinstance(e, SyntaxError) else next((fr.lineno for fr in reversed(_frames(e)) if fr.filename == name), None)
    where = f'script "{name}"' + (f" line {line}" if line else "")
    if isinstance(e, RostrumError):
        return RostrumError(e.code, f"{where} › {e.where}" if e.where else where, e.subject, e.problem, e.accepted, e.hint)
    if isinstance(e, (ValueError, KeyError, NoField)):
        return RostrumError(codes.BAD_ARGUMENT, where, "", str(e.args[0]) if e.args else str(e))
    hint = None
    if isinstance(e, NameError) and getattr(e, "name", None):
        hint = (f"Write {W.NOT_A_NAME[e.name]}" if e.name in W.NOT_A_NAME
                else did_you_mean(e.name, [k for k in scope if not k.startswith("_")]))
    elif isinstance(e, TypeError) and (m := re.search(r"unexpected keyword argument '(\w+)'", str(e))):
        hint = W.NOT_A_FIELD.get(m.group(1))
    return RostrumError(codes.BAD_ARGUMENT, where, f"{type(e).__name__}:", str(e) + (f". {hint}" if hint else ""), API)


def _frames(e):
    import traceback
    return traceback.extract_tb(e.__traceback__)
