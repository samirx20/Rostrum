"""The 3D script layer: Python an agent (or a person) writes to build a document. Running it gives a tree;
rostrum_core merges that tree in (`doc.run_script`), so a re-run never wipes what someone else changed (a light a
person moved stays where they put it).

    alu = material("alu", baseColor="#c9ccd1", metallic=1, roughness=0.32)
    with group("device", ry=-12) as device:                  # items made inside go into the group
        mesh("body", shape="box", width=0.074, height=0.017, depth=0.098, bevel=0.004, material=alu)
    device.key("ry", {0: -12, 2: 12}, ease="smooth")         # {seconds: value} or {seconds: (value, ease)}
    device.key("y", {0: 0.1, 1: 0}, ease="spring", stiffness=240, damping=14)   # ease="custom", x1=…, y2=… for a curve
    light("key", kind="rect", width=0.7, height=0.45, intensity=7, x=0.4, y=0.5, z=0.6).aim(device)
    light("strip", kind="strip", lightsOnly=[device], x=-0.4, y=0.2, z=0.3).aim(device, roll=90)   # standing on end
    cam = camera("cam", focalLength=100, z=0.4).aim((0, 0, 0))
    with import_usd("phone", file=r"C:/assets/phone.usdc") as phone:
        phone.part("Body/Screen", material="glass")
    shot("hero", camera=cam, fps=24, start=0, end=2)

Ids: the first argument; left out, they are counted per type (mesh_1, mesh_2 …), skipping every quoted word in the
script, so adding one item never renames another. An item's name (what the screen shows) is its id unless `name=` says. Unknown fields and bad values fail loudly, naming the line.
"""
from __future__ import annotations

import ast
import math

from rostrum_core import ids
from rostrum_core.errors import RostrumError, codes
from rostrum_core.keys import key_id

from . import build, fields as F
from .kind import KIND, PRIM_ID

SAFE = {n: __builtins__[n] if isinstance(__builtins__, dict) else getattr(__builtins__, n)
        for n in ("range", "len", "min", "max", "abs", "round", "enumerate", "zip", "list", "dict", "float", "int",
                  "str", "sorted", "reversed", "sum", "isinstance", "tuple", "ValueError")}
REFS = {"material", "camera", "aimItem", "frontMaterial", "bevelMaterial", "sideMaterial", "backMaterial"}       # fields that name another thing: an Item handle may be passed
ID_LISTS = {"lightsOnly"}           # fields holding ids separated by spaces: an Item, or a list of Items / ids, may be passed
CURVE = ("x1", "y1", "x2", "y2", "stiffness", "damping")      # a key's ease settings (custom curve, spring)


class Item:
    """A handle on one thing the script made."""

    def __init__(self, b: "Build", node: dict):
        self._b, self.node, self.id = b, node, node["id"]

    def set(self, **values) -> "Item":
        build.fill(self.node, _ids(values), f"script › {self.id}")
        return self

    def key(self, prop: str, keys: dict, ease: str = "smooth", **curve) -> "Item":
        """{seconds: value}, {seconds: (value, ease)} or {seconds: {"v": value, "ease": "spring", "stiffness": 240}};
        curve settings given here (x1 y1 x2 y2 for ease="custom", stiffness damping for "spring") go on every key."""
        allowed = F.animatable(self.node["type"])
        if prop not in allowed:
            raise ValueError(f'{self.id}: "{prop}" can\'t be animated on a {self.node["type"]}; animatable: '
                             f"{', '.join(allowed)}")
        p = F.param(self.node["type"], prop)
        for t, v in sorted(keys.items()):
            where = f"{self.id}.{prop} at {t} s"
            if isinstance(v, dict):
                v = dict(v)
                value, e, own = v.pop("v", v.pop("value", None)), v.pop("ease", ease), {**curve, **v}
            else:
                (value, e), own = (v if isinstance(v, tuple) else (v, ease)), dict(curve)
            if value is None:
                raise ValueError(f'{where}: a key given as a dict needs its value as "v"')
            F.param("key", "ease").check(e, where)
            k = {"id": key_id(self.id, prop, t), "type": "key", "prop": prop, "t": float(t),
                 ("c" if p.type == "color" else "v"): p.check(value, where), "ease": e}
            if set(own) - set(CURVE):
                raise ValueError(f'{where}: {", ".join(sorted(set(own) - set(CURVE)))} is not a key setting; '
                                 f'a key takes v, ease and {", ".join(CURVE)}')
            build.fill(k, own, where)                      # checked, and loud when a setting doesn't fit the ease
            self.node["keys"].append(k)
        return self

    def aim(self, target, roll: float | None = None) -> "Item":
        """Point −Z at an item (or its id) or at a point (x, y, z), every frame; `roll` (degrees) then turns it around
        the way it points (90 stands a strip light on end)."""
        extra = {} if roll is None else {"roll": roll}
        if isinstance(target, (tuple, list)):
            x, y, z = target
            return self.set(aim="point", aimX=float(x), aimY=float(y), aimZ=float(z), **extra)
        return self.set(aim="item", aimItem=target, **extra)

    def part(self, path: str, **values) -> "Item":
        """An import's part: a prim inside its file that gets its own material or is hidden."""
        if self.node["type"] != "import":
            raise ValueError(f"{self.id} is a {self.node['type']}; .part() is for an import")
        node = build.make("part", self._b.new_id(build.part_id(self.id, path), loose=True),
                          {"name": path, "path": path, **_ids(values)}, f"script › {self.id}")
        self.node["parts"].append(node)
        return Item(self._b, node)

    def __enter__(self):
        if self.node["type"] not in F.HOLDERS:
            raise ValueError(f"{self.id} is a {self.node['type']}; only a group, rig, import or combine holds items")
        self._b.holders.append(self.node)
        return self

    def __exit__(self, *exc):
        self._b.holders.pop()


def _id_of(v):
    return v.id if isinstance(v, Item) else v


def _ids(values: dict) -> dict:
    """Item handles → their ids, in fields that name other things."""
    out = {}
    for k, v in values.items():
        if k in ID_LISTS and isinstance(v, (Item, list, tuple)):
            v = " ".join(str(_id_of(x)) for x in (v if isinstance(v, (list, tuple)) else [v]))
        out[k] = _id_of(v) if k in REFS else v
    return out


class Build:
    def __init__(self, reserved=()):
        self.root, self.holders, self.reserved, self.taken = KIND.blank(), [], set(reserved), {}      # taken: id -> kind

    def new_id(self, type_or_id: str, id_: str | None = None, loose=False) -> str:
        if loose:                                        # a part's id from its path: already unique per import
            id_ = type_or_id
        elif id_ is None:
            id_ = ids.counted(self.taken, type_or_id, self.reserved)
        if not (ids.is_valid(id_) if loose else PRIM_ID.match(id_)):
            raise ValueError(f'"{id_}" is not a usable id (letters, digits and _, not starting with a digit)')
        if id_ in self.taken:
            raise ValueError(f'id "{id_}" is used twice in the script (already {F.LABELS.get(self.taken[id_], "an item").lower()})')
        self.taken[id_] = type_or_id if not loose else "part"
        return id_

    def add(self, type_: str, id_, values: dict, into: list) -> Item:
        node = build.make(type_, self.new_id(type_, id_), _ids(values),
                          f"script › {type_} {id_ or ''}".strip())
        into.append(node)
        return Item(self, node)

    def item(self, type_: str, id_=None, **values) -> Item:
        into = self.holders[-1]["children"] if self.holders else self.root["items"]
        parts = values.pop("parts", []) if type_ == "import" else []
        it = self.add(type_, id_, values, into)
        for path in parts:
            it.part(path)
        return it


def _reserved(source: str) -> set[str]:
    try:
        return {n.value for n in ast.walk(ast.parse(source)) if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    except SyntaxError:
        return set()


def _import(name, *args, **kw):
    if name == "math":
        return math
    raise ImportError(f"scripts can't import {name!r}; math, range, len, min, max, abs, round, zip … are already there")


API = ["group(id, **fields)", "mesh(id, shape=, **fields)", "light(id, kind=, **fields)", "camera(id, **fields)", "rig(id, rig=orbit|crane|dolly, **fields)",
       "import_usd(id, file=, parts=[...])", "combine(id, op=union|subtract|intersect)", "material(id, **fields)", "shot(id, camera=, fps=, start=, end=)",
       "item.set(**fields)", "item.key(field, {seconds: value}, ease=)", "item.aim(item or (x, y, z), roll=)",
       "import.part(path, material=, visible=)", "with group(...): / with rig(...): / with import_usd(...): / with combine(...):"]


def run_source(source: str, name: str) -> dict:
    """Python source → the document tree it builds. Any error is a loud BAD_ARGUMENT naming the line; nothing merged."""
    b = Build(_reserved(source))
    scope = {"__builtins__": {**SAFE, "__import__": _import}, "math": math,
             "material": lambda id=None, **v: b.add("material", id, v, b.root["materials"]),
             "shot": lambda id=None, **v: b.add("shot", id, v, b.root["shots"]),
             "import_usd": lambda id=None, **v: b.item("import", id, **v),
             **{t: (lambda id=None, _t=t, **v: b.item(_t, id, **v)) for t in ("group", "mesh", "combine", "light", "camera", "rig")}}
    try:
        exec(compile(source, name, "exec"), scope)
    except Exception as e:
        import traceback
        line = next((f" (line {fr.lineno})" for fr in traceback.extract_tb(e.__traceback__) if fr.filename == name), "")
        raise RostrumError(codes.BAD_ARGUMENT, "", f'script "{name}"', f"failed{line}: {type(e).__name__}: {e}",
                           API) from e
    return b.root
