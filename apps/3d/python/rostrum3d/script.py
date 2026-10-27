"""The 3D script layer: Python an agent (or a person) writes to build a document. Running it gives a tree;
rostrum_core merges that tree in (`doc.run_script`), so a re-run never wipes what someone else changed (a light a
person moved stays where they put it).

    alu = material("alu", start="brushed metal", baseColor="#c9ccd1")   # a start's values, then the given fields
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
    head = clay("head", y=1.6)                 # a clay: its shape is its steps, in order (ops_clay.py)
    head.lump((0, 0, 0), 0.1).lump((0, -0.02, 0.09), 0.03, name="nose")          # pieces: spheres, capsules (to=)
    head.stroke(path=[(0.03, 0.02, 0.2), (0.05, 0.02, 0.2)], dir=(0, 0, -1), brush="carve", size=0.01)
    buddy = clay("buddy", draw=[(-.1, 0, 0), (.1, 0, 0), (.08, .3, 0), (-.08, .3, 0)], facing=(0, 0, 1))  # drawn
    buddy.draw([(.07, .2, 0), (.2, .25, 0), (.2, .28, 0), (.07, .26, 0)], name="arm")   # joined; its own space
    vase = clay("vase", spin=[(0, 0, 0), (.05, 0, 0), (.04, .1, 0), (0, .12, 0)])          # spun round +Y

Ids: the first argument; left out, they are counted per type (mesh_1, mesh_2 …), skipping every quoted word in the
script, so adding one item never renames another. An item's name (what the screen shows) is its id unless `name=` says. Unknown fields and bad values fail loudly, naming the line.
"""
from __future__ import annotations

import ast
import math

from rostrum_core import ids
from rostrum_core.errors import RostrumError, codes
from rostrum_core.keys import key_id

from . import aim, build, clay_detail, copies_fields as CF, clay_steps, fields as F, mirror, ops_import, shape_size, surface_place
from .kind import KIND, PRIM_ID
from .material_starts import STARTS, start_key, start_values
from .clay_steps import piece_values, stroke_values
from .resolve import Frames

SAFE = {n: __builtins__[n] if isinstance(__builtins__, dict) else getattr(__builtins__, n)
        for n in ("range", "len", "min", "max", "abs", "round", "enumerate", "zip", "list", "dict", "float", "int",
                  "str", "sorted", "reversed", "sum", "isinstance", "tuple", "ValueError")}
REFS = {p.name for ps in F.FIELDS.values() for p in ps if p.type == "text" and p.kind}   # fields naming another thing: an Item handle may be passed
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
        curve settings given here (x1 y1 x2 y2 for ease="custom", stiffness damping for "spring") go on every key.
        "visible" takes True / False (1 / 0): shown or hidden from that key to the next, never in between."""
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
            e = F.param("key", "ease").check(e, where)
            if F.is_toggle(self.node["type"], prop):       # visible: on / off, held to the next key (fields.toggle_at)
                if value not in (0, 1):
                    raise ValueError(f"{where}: {prop} is on / off; a key's value is True / 1 or False / 0")
                value = 1.0 if value else 0.0
            else:
                value = p.check(value, where)
            k = {"id": key_id(self.id, prop, t), "type": "key", "prop": prop, "t": float(t),
                 ("c" if p.type == "color" else "v"): value, "ease": e}
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

    def place_on(self, other, at=None, normal=None) -> "Item":
        """Stand this mesh on `other`. Without `at`: on top of a mesh made earlier in the same group, its base on that
        mesh's top, over its middle (move it along the top afterwards with .set(x=…, z=…)); both unturned. With
        `at=(x, y, z)`, a point in the world on `other`'s surface (a clay or a mesh made earlier anywhere): its base
        on the surface there, standing along `normal` (left out: straight out from `other`'s upright middle line).
        On a clay whose Mirror is on, a point off its middle also makes the mesh's mirrored copy, which follows it
        (mesh.mirror; edit_place_on does the same from a pixel of a look)."""
        if at is not None:
            return self._place_at(other, [float(c) for c in at], normal)
        o = other.node if isinstance(other, Item) else next(
            (n for n in self._siblings() if n["id"] == other), None)
        if o is None or o not in self._siblings():
            raise ValueError(f"{self.id}.place_on: {_id_of(other)!r} is not a mesh made earlier in the same group")
        mine, theirs = self.node, o
        for n, v in ((self.id, mine), (o["id"], theirs)):
            if v["type"] != "mesh" or any(v.get(k, 0) for k in ("rx", "ry", "rz")):
                raise ValueError(f"{self.id}.place_on: {n} must be an unturned mesh")
        y = theirs["y"] + shape_size.half_height(theirs) * theirs["sy"] + shape_size.half_height(mine) * mine["sy"]
        return self.set(x=theirs["x"], y=round(y, 6), z=theirs["z"])

    def _place_at(self, other, at, normal) -> "Item":
        oid = _id_of(other)
        if self.node["type"] != "mesh":
            raise ValueError(f"{self.id}.place_on: only a mesh is placed on a surface (this is a {self.node['type']})")
        if oid not in self._b.taken or self._b.taken[oid] not in ("mesh", "clay"):
            raise ValueError(f"{self.id}.place_on: {oid!r} is not a mesh or clay made earlier in the script")
        fr = Frames(self._b.root, range(0, 1), 1.0)
        world, holder = fr.world(oid, 0), (self._b.holders[-1]["id"] if self._b.holders else "")
        if normal is None:                  # out from the upright line through its middle, level
            mid = aim.point(world, [0.0, 0.0, 0.0])
            normal = [at[0] - mid[0], 0.0, at[2] - mid[2]]
            normal = normal if math.hypot(*normal) > 1e-9 else [0.0, 1.0, 0.0]
        placed = surface_place.stand(self.node, at, [float(c) for c in normal])
        self.set(**surface_place.into_parent(placed, fr.world(holder, 0) if holder else aim.IDENTITY))
        if surface_place.mirrors(fr.items[oid], world, at, shape_size.extent(self.node) or 0.0):
            self._b.item("mesh", f"{self.id}_mirrored", name=f"{self.node['name']}{mirror.SUFFIX}", **mirror.stored(self.node), mirror=self.id,
                         mirrorOn=oid)
        return self

    def _siblings(self) -> list:
        return self._b.holders[-1]["children"] if self._b.holders else self._b.root["items"]

    def part(self, path: str, **values) -> "Item":
        """An import's part: a prim inside its file that gets its own material or is hidden."""
        if self.node["type"] != "import":
            raise ValueError(f"{self.id} is a {self.node['type']}; .part() is for an import")
        node = build.make("part", self._b.new_id(build.part_id(self.id, path), loose=True),
                          {"name": path, "path": path, **_ids(values)}, f"script › {self.id}")
        self.node["parts"].append(node)
        return Item(self._b, node)

    def effector(self, kind: str = "scale", near=None, id=None, **values) -> "Item":
        """Change the copies near an item: kind scale | turn | push | colour, `near` = the item the change is centred on
        (a handle or an id), radius, amount, falloff, axis, colour. Key amount / radius / colour for change over time."""
        if self.node["type"] != "copies":
            raise ValueError(f"{self.id} is a {self.node['type']}; .effector() is for a copies item")
        values = {"amount": CF.STARTING_AMOUNT.get(kind, 0.5), **values, "kind": kind}
        if near is not None:
            values["near"] = near
        return self._b.add("effector", id, values, self.node["children"])

    def lump(self, at, radius: float = 0.15, to=None, **values) -> "Item":
        """A clay's piece: a sphere at `at` (a capsule to `to`), joined (mode="add") or carved; blend, symmetry, name."""
        return self._step(piece_values(self.node, {"at": list(at), "radius": radius,
                                                   "to": list(to) if to is not None else None, **values},
                                       "capsule" if to is not None else "sphere"))

    def stroke(self, **values) -> "Item":
        """A clay's brush stroke: path=[(x, y, z) …] + dir=(x, y, z) (each dab where a ray along dir meets the clay),
        or dabList; brush, size, strength, symmetry, accumulate default to the clay's brush settings."""
        return self._step(stroke_values(self.node, {k: ([list(q) for q in v] if k in ("path", "dabList") else
                                                        list(v) if k == "dir" else v) for k, v in values.items()}))

    def draw(self, outline, **values) -> "Item":
        """A clay's drawn shape (clay.draw): outline=[(x, y, z) …] in the clay's own space, puffed up; facing, puff,
        mode, blend, symmetry, name. A tiny one is a lump."""
        pts, node = [list(p) for p in outline], self.node
        return self._step(clay_steps.draw_values(node, _vec(values), pts, clay_detail.detail(self._b.root, node)))

    def spin(self, profile, **values) -> "Item":
        """A clay's spun shape (clay.spin): profile=[(x, y, z) …] in the clay's own space, turned round axis=
        ((x, y, z), (x, y, z)) (left out: up through the first point); mode, blend, symmetry, name."""
        pts, node = [list(p) for p in profile], self.node
        return self._step(clay_steps.spin_values(node, _vec(values), pts, clay_detail.detail(self._b.root, node)))

    def _step(self, values: dict) -> "Item":
        if self.node["type"] != "clay":
            raise ValueError(f"{self.id} is a {self.node['type']}; .lump(), .draw(), .spin() and .stroke() are for "
                             "a clay")
        step_id = self._b.new_id(f"{self.id}.s{len(self.node['steps']) + 1}", loose=True)   # an operation's: .step_N
        self.node["steps"].append(build.make("claystep", step_id, values, f"script › {self.id}"))
        return self

    def __enter__(self):
        if self.node["type"] not in F.HOLDERS:
            raise ValueError(f"{self.id} is a {self.node['type']}; only a group, rig, import or combine holds items")
        self._b.holders.append(self.node)
        return self

    def __exit__(self, *exc):
        self._b.holders.pop()


def _vec(values: dict) -> dict:
    """Tuples → lists in a drawing's settings (facing, axis)."""
    return {k: ([list(p) for p in v] if k == "axis" else list(v) if k == "facing" else v) for k, v in values.items()}


def _clay(b: "Build", id_=None, draw=None, spin=None, facing=None, axis=None, puff=None, **values) -> Item:
    """clay(id, **fields), or clay(id, draw=[…] / spin=[…]) made from a drawing in the scene (as clay.add's)."""
    if draw is None and spin is None:
        return b.item("clay", id_, **values)
    args = _vec({k: v for k, v in (("facing", facing), ("axis", axis), ("puff", puff)) if v is not None})
    args.update({"draw" if draw is not None else "spin": [list(p) for p in (draw if draw is not None else spin)],
                 "symmetry": values.get("symmetry") or "x"})
    placed, local = clay_steps.standing(args)
    it = b.item("clay", id_, **{**placed, **values})
    make = clay_steps.draw_values if draw is not None else clay_steps.spin_values
    first = make(it.node, local, local["points"], clay_steps.DEFAULT["detail"])
    it.set(brushSize=values.get("brushSize") or round(max(clay_steps.size_of(first) / 4, 0.0005), 4))
    return it._step(first)


def _copies(b: "Build", id_=None, source=None, **values) -> Item:
    """copies(id, source, layout=…, count=…): `source` (an item or a list of them, made earlier in the same list) goes inside
    the new copies item, which takes its place (it stands at the copies item's origin, keeping its turn and size). Without
    `source`, it is a holder: `with copies("buds", layout="circle", count=8): mesh(…)`."""
    mine = list(source) if isinstance(source, (list, tuple)) else [] if source is None else [source]
    it = b.item("copies", id_, **values)
    if not mine:
        return it
    siblings = it._siblings()
    nodes = [m.node if isinstance(m, Item) else next((n for n in siblings if n["id"] == m), None) for m in mine]
    if None in nodes or any(n not in siblings for n in nodes):
        raise ValueError(f"{it.id}: its source must be made earlier in the same list (the same group or the top level)")
    it.node.update({k: round(sum(n.get(k, 0.0) for n in nodes) / len(nodes), 6) for k in "xyz"})
    siblings.remove(it.node)
    siblings[siblings.index(nodes[0]):siblings.index(nodes[0])] = [it.node]     # takes the first source's place
    for n in nodes:
        siblings.remove(n)
        n.update(x=0.0, y=0.0, z=0.0)
        it.node["children"].insert(len([c for c in it.node["children"] if c["type"] != "effector"]), n)
    return it


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
        if type_ == "import" and values.get("file"):     # read like import.add: metres, upright, base on x y z, its meshes
            keep = values.pop("keepSize", False)
            values, found = ops_import.read_file(values, keep)
            parts += [p for p in found if p not in parts]
        it = self.add(type_, id_, values, into)
        names = ops_import.part_names(parts)
        for path in parts:
            it.part(path, name=names[path])
        return it


def _reserved(source: str) -> set[str]:
    try:
        return {n.value for n in ast.walk(ast.parse(source)) if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    except SyntaxError:
        return set()


def _start(name, values: dict) -> dict:
    """A starting point's values (material_starts.py) by key or label, any case; the script's own fields win."""
    if name is None:
        return values
    key = start_key(name)
    if key is None:
        raise ValueError(f'start "{name}" is not a starting point; starts: {", ".join(STARTS)}')
    return start_values(key, values)


def _import(name, *args, **kw):
    if name == "math":
        return math
    raise ImportError(f"scripts can't import {name!r}; math, range, len, min, max, abs, round, zip … are already there")


API = ["group(id, **fields)", "mesh(id, shape=, **fields)", "light(id, kind=, **fields)", "camera(id, **fields)", "rig(id, rig=orbit|crane|dolly, **fields)",
       "import_usd(id, file=, parts=[...])", "combine(id, op=union|subtract|intersect)", "copies(id, source, layout=line|grid|circle|surface, count=, spacingX=, columns=, radius=, surface=, seed=, varyMove=, varyTurn=, varyScale=)", "copies.effector(kind=scale|turn|push|colour, near=, radius=, amount=)", "clay(id, **fields)", "clay(id, draw=[(x, y, z) …] or spin=[…], facing=, axis=, puff=)", "material(id, start=, **fields)", "shot(id, camera=, fps=, start=, end=)",
       "item.set(**fields)", "item.key(field, {seconds: value}, ease=)", "item.aim(item or (x, y, z), roll=)", "item.place_on(other mesh) / item.place_on(clay or mesh, at=(x, y, z), normal=)",
       "import.part(path, material=, visible=)",
       "clay.lump(at, radius, to=, mode=add|carve, blend=)", "clay.draw(outline, facing=, puff=, mode=, blend=, name=)", "clay.spin(profile, axis=, mode=, blend=, name=)", "clay.stroke(path=, dir=, brush=, size=, strength=)", "with group(...): / with rig(...): / with import_usd(...): / with combine(...): / with copies(...):"]


def run_source(source: str, name: str) -> dict:
    """Python source → the document tree it builds. Any error is a loud BAD_ARGUMENT naming the line; nothing merged."""
    b = Build(_reserved(source))
    scope = {"__builtins__": {**SAFE, "__import__": _import}, "math": math,
             "material": lambda id=None, start=None, **v: b.add("material", id, _start(start, v), b.root["materials"]),
             "shot": lambda id=None, **v: b.add("shot", id, v, b.root["shots"]),
             "import_usd": lambda id=None, **v: b.item("import", id, **v),
             "clay": lambda id=None, **v: _clay(b, id, **v),
             "copies": lambda id=None, source=None, **v: _copies(b, id, source, **v),
             **{t: (lambda id=None, _t=t, **v: b.item(_t, id, **v)) for t in ("group", "mesh", "combine", "light", "camera", "rig")}}
    try:
        exec(compile(source, name, "exec"), scope)
    except Exception as e:
        import traceback
        line = next((f" (line {fr.lineno})" for fr in traceback.extract_tb(e.__traceback__) if fr.filename == name), "")
        raise RostrumError(codes.BAD_ARGUMENT, "", f'script "{name}"', f"failed{line}: {type(e).__name__}: {e}",
                           API) from e
    return b.root
