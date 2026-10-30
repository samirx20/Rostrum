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
from rostrum_core import nearest
from rostrum_core.errors import RostrumError, codes, did_you_mean
from rostrum_core.keys import key_id, marked
from rostrum_core.keys.ops import SHAPE_EASE
from rostrum_core.seeded import SeededRandom, no_classes

from . import fields as F, fontlist, mathtype, paint_fields, paint_grow, pathdata, plot, script_frame, script_music, script_others, script_sample, script_scramble, script_words as W, shafts, text_anchor, text_measure, text_runs
from .evaluate import script_marks
from .expr import ExprError, parse
from .frame import make as frame_make, view as frame_view
from .group_fit import fit
from .kind import KIND, LISTS
from .ops_expr import expr_id, link_source
from .rig import motion as rig_motion, script as rig_script
from .swap import child_index
from . import script_layout, ui_blocks, ui_pointer
from . import script_icons, script_inert, script_time, script_transitions
from .lipsync import script as lipsync_script

# Python's plain built-ins a script may use (script-reference.md lists them; keep the two the same). No print (the MCP
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
    _OWN = ("_b", "node", "id", "d_shift", "drawings", "holder", "frame_node")      # the handle's own attributes, not the item's fields

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
        calls = [n for n in dir(type(self)) if not n.startswith("_")]
        raise NoField(f'{node["id"]}.{name}: a {node["type"]} has no field "{name}".{_hint(name, known + calls)} Its fields: {", ".join(known)}')

    def set(self, **values) -> "Item":
        self._b.fill(self.node, values)
        return self

    @property
    def bottom(self) -> float:
        """Where it ends below, in its parent's px: y + its height under the anchor (a screen block's y + h)."""
        from .ui_layout import bottom
        return bottom(self.node)

    @property
    def right(self) -> float:
        """Where it ends on the right, in its parent's px: x + its width right of the anchor."""
        from .ui_layout import right
        return right(self.node)

    def measure(self, at: float = 0) -> tuple[float, float]:
        """A text's box (w, h) in its own px at `at` (before scale), measured by the engine code that draws it: lay
        out a line by its real width (`x = 1800 - t.measure()[0] * t.scale`). `at` may be a marker time ("#drop+0.2")."""
        self._need("text", "measure")
        from .evaluate import resolve
        from .textsize import size
        return size(resolve(self.node, script_time.seconds(self._b, at, f"{self.id}.measure at")))

    def run(self, which) -> "text_runs.Run":
        """A styled run of this text by its words or number (text_runs.py): `t.run("move").key("color", {…})`."""
        self._need("text", "run")
        return text_runs.Run(self, text_runs.number(self.node, which))

    def pivot(self, x: float, y: float, at: float = 0) -> "Item":
        """The anchor (what it turns and scales around) on the point (x, y) of the parent's px (comp px, or the group's
        box), the picture staying where it shows at `at` (layer.anchor point). A drawing's canvas that grows with its
        strokes keeps it on the same spot, so it may come before or after the strokes."""
        script_frame.run(self._b, self.node, "layer.anchor", {"point": [x, y], "at": at})
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
                value = pathdata.shifted(pathdata.check(value, f"{self.id}.d at {t} s"), self.d_shift)
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
        script_inert.given(self._b, self.node, [prop])
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

    def sample(self, prop: str, values, start: float = 0, end: float | None = None, every: int = 1) -> "Item":
        """Key a field from Python: a function of seconds or a list, one key per frame (script_sample.py)."""
        return script_sample.sample(self, prop, values, start, end, every)

    def link(self, prop: str, of: str, field: str, scale: float = 1.0, offset: float = 0.0) -> "Item":
        """Bind a field to another item's field: value = other · scale + offset."""
        return self.expr(prop, link_source(of, field, scale, offset))

    def effect(self, type_: str, id: str | None = None, **values) -> "Item":
        """Adds an effect and returns it, so it can be keyed: `t.effect("blur", radius=20).key("radius", {...})`.
        Either order of type and id works: `effect("blur", "soft")` and `effect("soft", "blur")` are the same."""
        if type_ not in F.EFFECTS and id in F.EFFECTS:
            type_, id = id, type_
        if type_ not in F.EFFECTS:
            raise ValueError(f'"{type_}" is not an effect; effects: {", ".join(F.EFFECTS)}' + _hint(type_, F.EFFECTS))
        return self._b.add(type_, id, values, self.node["effects"])

    def mask(self, id: str | None = None, **values) -> "Item":
        return self._b.add("mask", id, values, self.node["masks"])

    # drawing layers (painting kit): drawing.frame(at) -> frame.paint() -> paint.stroke(points, **brush)
    def frame(self, at: int, id: str | None = None) -> "Item":
        self._need(("drawing", "painting"), "frame")
        at = F.param("frame", "at").check(at, "frame")
        frames = self.node["frames"]
        same = next((f for f in frames if f["at"] == at), None)
        if same is not None:                # asked again: the drawing already there, to paint more on
            if id is not None and id != same["id"]:
                raise ValueError(f'{self.id} already has a drawing at frame {at} ("{same["id"]}"); '
                                 f"{self.id}.frame({at}) gives it again, or use another frame")
            item = Item(self._b, same)
            item.drawings, item.holder = frames, self.node
            return item
        node = {"id": self._b.new_id("frame", id), "type": "frame", "at": at, "paints": [], "paintmasks": []}
        frames.insert(sum(1 for f in frames if f["at"] < node["at"]), node)
        item = Item(self._b, node)
        item.drawings, item.holder = frames, self.node
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
        item = self._b.add_kit("paint", id, values, paints)
        item.frame_node, item.holder = self.node, self.__dict__.get("holder")
        return item

    def paintmask(self, points, id: str | None = None, **values) -> "Item":
        self._need("frame", "paintmask")
        return self._b.add_kit("paintmask", id, {"points": points, **values}, self.node["paintmasks"])

    def stroke(self, points, id: str | None = None, **brush) -> "Item":
        if self.node["type"] == "painting":              # the shortcut: its first drawing and its Ink layer, made when missing
            return self._ink().stroke(points, id, **brush)
        self._need("paint", "stroke")
        if "mask" in brush:             # mask=f.paintmask(...): the object it gave, or its id
            brush["mask"] = getattr(brush["mask"], "id", brush["mask"])
        return self._b.add_kit("stroke", id, {"points": points, **brush}, self.node["strokes"])

    def letters(self, text: str, x: float = 0, y: float = 0, height: float = 120, font: str = "script", **values) -> list:
        """Words as brush strokes on this paint layer, the way a hand letters them (the same as paint.letters): x, y the
        baseline start in the canvas's px; tracking=, line=, slant=, align=, hand= (0–1), hand_seed=, path= / start= as
        paint.letters; any brush setting. Gives its strokes in writing order (key drawnSoFar 0 → 1 to write them on)."""
        from .lettering import strokes
        self._need("paint", "letters")
        own = {k: values.pop(k) for k in ("tracking", "line", "slant", "align", "hand", "hand_seed", "path", "start") if k in values}
        lines = strokes(text, font_name=font, size=float(height), x=float(x), y=float(y), align=own.get("align", "left"),
                        spacing=float(own.get("tracking", 0)), line=float(own.get("line", 1.6)), slant=float(own.get("slant", 0)),
                        hand=float(own.get("hand", 0)), seed=int(own.get("hand_seed", 0)), path=own.get("path", ""),
                        start=float(own.get("start", 0)))
        return [self.stroke(pts, words=text, **values) for pts in lines]

    def wash(self, box=None, outline=None, id: str | None = None, **values) -> list:
        """A wash to the edges on this paint layer (paint_wash.py, the same as paint.wash): `p.wash(color="#1b2a5c")` covers
        the whole canvas; box=[x0, y0, x1, y1] or outline=[[x, y], …] a region, with bleed= / edge= px; to= and bands=
        a graded wash; any brush setting. Gives its strokes (a flat wash is one)."""
        from .drawing import canvas_size
        from .paint_wash import plan
        self._need("paint", "wash")
        if self.__dict__.get("frame_node") is None or self.__dict__.get("holder") is None:
            raise ValueError(f"{self.id}: .wash() needs the paint layer as frame.paint() gave it")
        w, h = canvas_size(self.holder)
        mask, strokes = plan(outline or box or "whole", w, h, values)
        from rostrum_paint.ops import build
        base = self._b.new_id("wash", id)       # the first stroke's id; the others <id>_2 …, the mask <id>_edge
        if mask:
            mask = self._b.add_kit("paintmask", f"{base}_edge", mask, self.frame_node["paintmasks"]).id
        out = []
        for i, s in enumerate(strokes):
            s = {**s, **({"mask": mask} if mask else {})}
            if i:
                out.append(self._b.add_kit("stroke", f"{base}_{i + 1}", s, self.node["strokes"]))
            else:
                self.node["strokes"].append(build("stroke", base, s, f"wash {base}"))
                out.append(Item(self._b, self.node["strokes"][-1]))
        return out

    def fill(self, points, id: str | None = None, **values) -> "Item":
        """A filled polygon on this paint layer, sharp-edged, in painting order (the kit's fill: what paint.fill makes
        from a click): `ink.fill([(x, y), …], color="#2a2340")` for a ridge or a silhouette; [x, y, ring] for holes."""
        self._need("paint", "fill")
        if "mask" in values:
            values["mask"] = getattr(values["mask"], "id", values["mask"])
        return self._b.add_kit("fill", id, {"points": [[*p[:2], p[2] if len(p) > 2 else 0] for p in points], **values},
                               self.node["strokes"])

    def _ink(self) -> "Item":
        frames = self.node["frames"]
        frame = Item(self._b, frames[0]) if frames else self.frame(0)
        paints = frame.node["paints"]
        if not paints:
            return frame.paint(name="Ink")
        item = Item(self._b, paints[0])
        item.frame_node, item.holder = frame.node, self.node
        return item

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
            fit(self.node, pointed=self.id in self._b.pointed)


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

    def fit(self, items=None, at=0, rect=None, pad=None, keep_rotation=None, ease=None, keep=None) -> "FrameItem":
        script_frame.run(self._b, self.node, "frame.fit", script_frame.args_of(items, at=at, rect=rect, pad=pad, keep_rotation=keep_rotation, ease=ease, keep=keep))
        return self

    def cut(self, at, to=None, items=None, rect=None, pad=None, keep_rotation=None, keep=None) -> "FrameItem":
        script_frame.run(self._b, self.node, "frame.cut", script_frame.args_of(items, at=at, to=to, rect=rect, pad=pad, keep_rotation=keep_rotation, keep=keep))
        return self

    def home(self, at=0) -> "FrameItem":
        script_frame.run(self._b, self.node, "frame.home", {"at": at})
        return self


class Build:
    def __init__(self, reserved=()):
        self.root, self.holders, self.reserved, self.taken = KIND.blank(), [], set(reserved), set()
        self.sized = set()          # groups whose script gave a size (w or h): never refitted
        self.pointed = set()        # unsized groups whose script gave x / y: their children count from that point
        self.loose: list = []       # (layer, container): set apart with no x / y where the layout sizes the box
        self.counts: dict[str, int] = {}     # type -> the last counted N (new_id)
        self.given: dict[str, tuple] = {}    # item id -> (node, the fields the script gave it): script_inert.py

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
        values = script_time.fill(self, node, values)        # start= / end= on a marker ("#reveal+0.5", script_time.py)
        if node["type"] == "text":
            values = text_runs.split(node, values)          # body=["… ", ("words", {"color": …}), …]: styled runs
        params = F.FIELDS[node["type"]]
        known = [p.name for p in params]
        kinds = {p.name: p.type for p in params}
        given, before = W.resolve(node["type"], values, known, kinds.get), dict(node)
        for k, v in given.items():
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
        script_inert.given(self, node, [k for k in given if k != "name"])   # a field's switch turned, said if inert
        if node["type"] == "text":                   # Align moves a point text's anchor with it (text_anchor.py)
            node.update(text_anchor.follow(before, node, given))
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
        node = build(type_, self.new_id(type_, id_), values, f"{type_} {id_ or ''}".strip(),
                     paint_fields.STROKE if type_ == "stroke" else ())
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
        script_others.check_comp(self, id)          # a scene another script (or a person) made is theirs
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
        if type_ == "drawing":          # placed by its canvas: with no x / y its top-left is the comp's (or the group's
            dflt = F.defaults("drawing")    # box's), so canvas px = comp px whatever its size and strokes go where given
            for xy, size, anchor in (("x", "w", "anchorX"), ("y", "h", "anchorY")):
                if xy not in values:
                    values[xy] = float(values.get(size, dflt[size])) * float(values.get(anchor, dflt[anchor]))
        if values.get("ridePath"):         # rides a path: the path places it, its own x / y are an offset (as layer.ride
            values = {**values, "x": values.get("x", 0.0), "y": values.get("y", 0.0)}     # sets), 0 when the script gave none
        pointed = type_ == "group" and bool({"x", "y"} & values.keys()) and not ({"w", "h", "layout"} & values.keys())             and not script_layout.in_layout(self) and not ({"anchorX", "anchorY", "origin", "anchor"} & values.keys())
        loose = script_layout.loose(self, values)                    # set apart where its place can't be known: said
        values = script_layout.centre(self, type_, values)           # no x / y: the parent's centre
        if type_ == "group":        # a script's hugging group grows around its anchor; keeping top-left is the canvas's
            values.setdefault("hugPin", False)
        values = script_layout.prepare(self, type_, id, values)       # origin, tw, container words (guide lay-out-a-screen)
        made = self.add(type_, id, values, self.holders[-1]["layers"])
        if pointed:
            self.pointed.add(made.id)   # group("arm", x=520, y=650): a child at (0, 80) sits 80 px below that point
        if loose:
            self.loose.append((made.node, self.holders[-1]))
        return made


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


def _brief(b: "Build", words) -> None:
    """brief("..."): the brief's own words, stored on the document (doc.data["brief"]) for the person and the
    notes; it changes nothing in an export."""
    if not isinstance(words, str) or not words.strip():
        raise ValueError('brief(...) takes the brief\'s own words as one text: brief("A 20 s launch film for ...")')
    b.root["brief"] = words.strip()


class Tree(dict):
    """The document tree a script built, with `notes`: lines for run_script's reply (fields given where they do nothing)."""

    def __init__(self, root: dict, notes: list[str]):
        super().__init__(root)
        self.notes = notes


def run_source(source: str, name: str, doc=None) -> dict:
    """Python source -> the document tree it builds. Any error is a loud BAD_ARGUMENT naming the line; nothing is merged.
    `doc`: the document it will be merged into (run_script passes it), so the ids it already holds are left alone."""
    b = Build(_reserved(source) | _held_ids(doc, name))
    b.doc, b.name = doc, name           # who made what is already there (script_others: layer() / comp() say so)
    rnd = SeededRandom(1)
    scope = {"__builtins__": {**SAFE, "__import__": _importer(rnd), "__build_class__": no_classes}, "math": math, "random": rnd, "comp": b.comp,
             **{t: (lambda id=None, _t=t, **v: b.layer(_t, id, **v)) for t in F.PLACED}, "frame": b.frame, "camera": b.camera, "painting": b.painting, "painted": Painted,
             "brief": lambda words: _brief(b, words),
             "pin": lambda layer, on=True, at=0, keep="shown": script_frame.pin(b, layer, on, at, keep),
             "set_depth": lambda layer, depth, at=0, keep="shown": script_frame.set_depth(b, layer, depth, at, keep),
             **pathdata.for_script(b.layer), **plot.for_script(), **mathtype.for_script(b.layer), **text_measure.for_script(), **rig_script.for_script(b), **rig_motion.for_script(b), **script_layout.for_script(b), **ui_blocks.for_script(b), **ui_pointer.for_script(b), **shafts.for_script(b),
             **lipsync_script.for_script(b), **script_scramble.for_script(b), **script_music.for_script(b), **script_time.for_script(b),
             **script_transitions.for_script(b), **script_icons.for_script(b)}
    try:
        with script_marks(lambda: script_time.times(b)):   # the script's own reads see marker keys at their moment
            exec(compile(source, name, "exec"), scope)
            for finish in getattr(b, "finishers", ()):     # end-of-script passes (rig.motion: limbs' natural bend, colour)
                finish()
        _grow_drawings(b.root)
        _check_links(b.root, b.taken)
        script_time.publish(b)                       # last: the script's markers only once everything else passed
    except Exception as e:
        raise _failed(e, name, scope) from e
    return Tree(b.root, script_inert.notes(b) + [script_layout.loose_note(n, h) for n, h in b.loose])


run_source.wants_doc = True            # rostrum_core's run_script tool then passes the document

API = ["brief(\"the brief's own words\"): stored on the document; a final export's keep quotes it", "comp(id, **fields)", "shape / text / image / path / group(id, **fields)", "frame(**fields): the scene's frame",
       "frame().fit(layers | rect=(x, y, w, h), at=, ease=, keep=[layers kept whole too]) / .cut(at=, to=, rect=) / .home(at=)", "pin(layer, on=True, at=0)", "set_depth(layer, depth, at=0)", "item.key(field, {time: value}, ease=)",
       "item.sample(field, lambda t: … | [values], start=, end=, every=): keys from Python, one per frame", "item.pivot(x, y): the anchor on a point in comp px, nothing moves", "text(id, body=[\"plain \", (\"words\", {\"color\": …, \"weight\": …}), …]): styled runs in one text; text.run(\"words\").key(\"color\" | \"weight\" | \"scale\" | \"opacity\", {…}) (guide styled-words)", "text.measure(): (w, h) of a text's box", "measure_text(body, size=, font=, …): (w, h) a text would have, no layer made", "icon(name, id=, size=24, color=, stroke_width=, **group fields): a Lucide / Tabler icon by name (\"arrow-right\", \"tabler:heart-filled\") as a group of path layers","item.effect(type, id, **fields)", "item.mask(id, **fields)", "item.set(**fields) / item.field = value",
       "with group(id, **fields): …", "with rig(id): bone(id, parent=, ...) / ik(id, bone=) / bind(layer=, bone=)",
       "layer(id): an item made earlier in the script", "limb(id, x=, y=, lengths=, widths=, kind=arm|leg, parent=, taper=, joint=round|ball|none, outline=)",
       "walk(legs=[l, r], arms=, body=, start=, end=, step=, stride=) / step(legs=[l, r], by=px, at=) / idle(chest, head=, arms=, legs=) / follow(bone) / pose({limb: turn, bone: {field: v}}, at=) / blink(slot, open=, closed=)",
       "with row / column / grid / stack(id, padding=, gap=, align=, justify=, w=px|\"50%\"|\"fill\"|\"fit\", bg=, radius=, tw=): layers made inside are placed for you (grow=, align_self=, margin=, span=, shift_x=; x / y only with apart=True); anchor=\"top-left\"|\"top\"|\"left\"|\"center\"|…|(0, 1) (or origin=) on any layer; no x / y = the parent's centre; guide lay-out-a-screen",
       "device(id, kind=phone|laptop|browser (left out: the kind the id names, device(\"laptop\") is a laptop; else phone), fit=, anchor=center|left|right, screen=) returns its screen, a column / status_bar / nav_bar / tab_bar / list_rows / card / button / toggle / bars / counter / chart / lower_third: placed by the container they are made in; guide ui-and-product-animation",
       "pointer(id=\"cursor\", kind=arrow|touch) / tap(pointer, target, at=, move=, press=, ripple=, spot=, then=, hold=): the tip lands on the target's centre, follows it if it moves, reacts (guide tap-and-react)",
       "scramble(id, body, start=, end=, rate=, chars=, order=, **text fields): characters cycling and locking into words", "beats(start=, end=) the song's beats / beats(bpm=, start=, count=) a beat grid without a song", "marker(name, at) -> \"#name\": a shared project marker; any time may be \"#name+0.5\" (start=, end=, at=, keys)", "after(item, gap=): when its last key lands + gap", "transition(kind=cut|fade|push|slide|wipe|iris|zoom|blur, at=, dur=, out_of=, into=, ease=, …): one section into the next as ordinary keys, masks, effects; carry(layer, into=, at=, dur=, to=dict(x=, y=, scale=, …)): a layer carried past its section's end (guide transitions-and-carry-overs)","stagger(items, every=, start=) -> [(time, item), …]", "light_shafts(id, x=, y=, count=, spread=, length=, lean=, color=, strength=, sway=): beams of light, a group (guide frame-parallax-motion-blur)",
       "path(id, d=star(5, 100, 45))", "math_text(id, r\"\\frac{a}{b}\", x=, y=, size=, color=): a typeset equation as a group of path layers (guide data-math-and-graphs)", "plot_area / curve_points / line_d / nice_ticks / view3d / surface_lines / parse_table: guide data-math-and-graphs", "drawing.frame(at)", "frame.paint(id)", "paint.stroke(points, **brush)", "paint.letters(text, x=, y=, height=, font=, **brush): hand-lettered words as brush strokes", "paint.fill(points, color=)",
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
        hint = f"Write {W.NOT_A_NAME[e.name]}" if e.name in W.NOT_A_NAME else None
    elif isinstance(e, TypeError) and (m := re.search(r"unexpected keyword argument '(\w+)'", str(e))):
        hint = W.NOT_A_FIELD.get(m.group(1))
    near = None if hint else nearest.script_hint(e, scope, _item_names)      # "did you mean …": names only, in place of the list
    if near:
        return RostrumError(codes.BAD_ARGUMENT, where, f"{type(e).__name__}:", near)
    return RostrumError(codes.BAD_ARGUMENT, where, f"{type(e).__name__}:", str(e) + (f". {hint}" if hint else ""), API)


def _item_names(obj) -> list[str]:
    """An item handle's fields, for "did you mean" (dir() shows only its calls)."""
    node = obj.__dict__.get("node") if isinstance(obj, Item) else None
    return [p.name for p in F.FIELDS.get(node["type"], [])] if node else []


def _frames(e):
    import traceback
    return traceback.extract_tb(e.__traceback__)
