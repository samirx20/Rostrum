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

Anything directly in the scene (the new scene's shot_1, ground, sky …, another script's, one made by hand) made again under
the same id (`light("sky", kind="dome", intensity=0.5)`) is replaced by it, field by field, in the run's one undo step;
`edit("ground", baseColor=…)` (or `item("ground")`) is a handle on it changing only the fields given, and on anything this
script made earlier; asked twice, the same handle. `remove("a", "b")` takes things out. The script then owns them (a re-run
under its name changes them again); a field a person changed since is held back, as for any script. A re-run that leaves
out most of what its last run made goes through and its reply names what went (script_rerun.py). A shot with no camera
is seen through the default view, said in the reply (script_shot.default_view).

Ground first (script_ground.py): a mesh, import or group made directly in the scene stands on the ground, its `y` the height of
its base above it (`y_world=` for its origin's world height); place by relation with place_on / row (script_place.py); frame
with shot(frame=…) and light in stops with light(brightness=…) (script_shot.py).

Ids: the first argument; left out, they are counted per type (mesh_1, mesh_2 …), skipping every quoted word in the
script, so adding one item never renames another. An item's name (what the screen shows) is its id unless `name=` says. Unknown fields and bad values fail loudly, naming the line;
a field that doesn't apply to the item (seenByCamera on a strip light) is not used and said in the reply, the rest applied.
"""
from __future__ import annotations

import ast
import copy
import math

from rostrum_core import ids, nearest
from rostrum_core.errors import RostrumError, codes
from rostrum_core.keys import key_id

from . import aim, build, clay_detail, start_lights, copies_fields as CF, clay_steps, fields as F, mirror, ops_import, shape_size, surface_place
from rostrum_core.tree import walk

from . import script_figure, script_ground, script_place, script_pose, script_rerun, script_shot
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
        if "y_world" in values:                          # its origin at a world height: no longer grounded
            script_ground.release(self._b, self.id)
            values["y"] = values.pop("y_world")
        build.fill(self.node, _ids(values), f"script › {self.id}", self._b.notes)
        self._b.given.setdefault(self.id, set()).update(values)
        if self.id in self._b.grounded:                  # y = its base's height above the ground (script_ground.py)
            script_ground.settle(self._b, self.node, "y" in values)
        return self

    def key(self, prop: str, keys, ease: str = "smooth", **curve) -> "Item":
        """{seconds: value}, {seconds: (value, ease)} or {seconds: {"v": value, "ease": "spring", "stiffness": 240}}, or
        key.add's shape: a list of {"t": seconds, "v": value, "ease": …} ("at" is taken for "t");
        curve settings given here (x1 y1 x2 y2 for ease="custom", stiffness damping for "spring") go on every key.
        "visible" takes True / False (1 / 0): shown or hidden from that key to the next, never in between.
        The first key() of a field in a run replaces that field's keys (so keys on a thing taken over with edit() are
        never doubled); a later key() of it in the same run adds to them, a key at the same time replacing."""
        if self.node["type"] == "shot" and prop == "frame":    # a push-in: camera keys (script_shot.py)
            script_shot.key_frame(self._b, self.node, self._b.framing.get(self.id, {}), keys, ease)
            return self
        keys = _key_dict(self.id, prop, keys)
        if (id(self.node), prop) not in self._b.keyed:
            self._b.keyed.add((id(self.node), prop))
            self.node["keys"] = [k for k in self.node["keys"] if k.get("prop") != prop]
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
                value = script_ground.key_value(self._b, self.node, prop, p.check(value, where))
            k = {"id": key_id(self.id, prop, t), "type": "key", "prop": prop, "t": float(t),
                 ("c" if p.type == "color" else "v"): value, "ease": e}
            if wrong := sorted(set(own) - set(CURVE)):
                near = nearest.did_you_mean(wrong[0], ["v", "ease", *CURVE])
                raise ValueError(f'{where}: {", ".join(wrong)} is not a key setting; '
                                 f'a key takes v, ease and {", ".join(CURVE)}' + (f". {near}" if near else ""))
            build.fill(k, own, where, self._b.notes)       # checked; a setting that doesn't fit the ease is said, not used
            self.node["keys"] = [o for o in self.node["keys"] if o["id"] != k["id"]] + [k]
        if self.id in self._b.grounded and prop != "y":    # a turn or a size keyed: its base measured again
            script_ground.settle(self._b, self.node, False)
        return self

    def aim(self, target, roll: float | None = None) -> "Item":
        """Point −Z at an item (or its id) or at a point (x, y, z), every frame; `roll` (degrees) then turns it around
        the way it points (90 stands a strip light on end)."""
        extra = {} if roll is None else {"roll": roll}
        if isinstance(target, (tuple, list)):
            x, y, z = target
            return self.set(aim="point", aimX=float(x), aimY=float(y), aimZ=float(z), **extra)
        return self.set(aim="item", aimItem=target, **extra)

    def simulate(self, kind: str = "falls", **values) -> "Item":
        """Make it part of the shot's simulation (only things directly in the scene): "falls", "still", "cloth" (a shape
        only) or "off", with Simulation fields (mass=, massFromSize=, bounce=, friction=, starts="asleep", fallStart=1.5 (seconds into the shot it holds still
        until, then falls), simShape="box";
        cloth: clothWeight=, stiffness=, clothAir=, clothWind=, clothWindTurn=, pinned="back", over=<item>). Computing it is the run_simulation tool (or sim.run), never the
        script. Cloth with over=<item> (made earlier, or already in the scene) also places the sheet over it: centred,
        a little above its top, level, and a plane too small to drape it made big enough to reach the floor."""
        over = values.pop("over", None)
        self.set(simulate=kind, **values)
        if over is not None:
            from .sim.cloth_check import over as place
            if kind != "cloth":
                raise ValueError(f"{self.id}.simulate: over= only places a cloth")
            script_ground.release(self._b, self.id)
            tree = self._b.root if _id_of(over) in self._b.taken else (self._b.doc.data if self._b.doc else self._b.root)
            self.set(**place(tree, self.node, _id_of(over)))
        return self

    def start_in_view(self, from_top: float = 0.1, shot=None) -> "Item":
        """Raise (or lower) this falling thing or cloth so it starts inside the shot camera's picture, its top `from_top`
        of the picture's height below the picture's top edge (0.1 default), as the camera sees it at its fallStart: it
        then falls straight down, on screen (the sim.start_in_view operation). Call it after .simulate(...) and after the
        shot and its camera are made; `shot` (an id or the shot) defaults to the first shot."""
        from .sim.in_view import NotInView, lift
        from .sim.inputs import value
        tree = self._b.doc.data if self._b.doc and self.id not in self._b.taken else self._b.root
        if value(self.node, "simulate") not in ("falls", "cloth"):
            raise ValueError(f"{self.id}.start_in_view: set .simulate(\"falls\") or .simulate(\"cloth\") first")
        shots = tree.get("shots", [])
        sid = _id_of(shot) if shot is not None else (shots[0]["id"] if shots else "")
        if not sid:
            raise ValueError(f"{self.id}.start_in_view: make the shot (with its camera) first")
        try:
            dy = lift(tree, self.id, sid, float(from_top))
        except NotInView as e:
            raise ValueError(f"{self.id}.start_in_view: can't start in view of shot {sid!r}: {e}") from None
        script_ground.release(self._b, self.id)
        return self.set(y=round(float(self.node.get("y", 0.0)) + dy, 4))

    def take_view(self, pos, look_at) -> "Item":
        """A camera: stand at `pos` (world) and aim at `look_at` (a point (x, y, z) or an item)."""
        return script_shot.take_view(self, pos, look_at)

    def place_on(self, other=None, at=None, normal=None, beside=None, side=None, in_front_of=None,
                 gap: float = 0.0) -> "Item":
        """Place this thing by another, by both things' real room in the world (turned, in groups; script_place.py):
        place_on(other) its base on other's top, over its middle (gap= metres between); place_on(other,
        beside="left"|"right"|"front"|"back") or place_on(beside=other, side=…) next to it on that world side (front =
        +Z), lined up with its middle, gap= metres between, its base level with the other's; place_on(in_front_of=other). With
        `at=(x, y, z)`, a point in the world on `other`'s surface (a clay or a mesh made earlier anywhere): its base
        on the surface there, standing along `normal` (left out: straight out from `other`'s upright middle line).
        On a clay whose Mirror is on, a point off its middle (farther than the mesh's half size) also makes the
        mesh's mirrored copy, which follows it (mesh.mirror; edit_place_on does the same from a pixel of a look). On a
        clay the mesh also follows its pose (follow=<clay>, followPose): posed, it moves with the bone nearest it."""
        if at is not None:
            script_ground.release(self._b, self.id)
            return self._place_at(other, [float(c) for c in at], normal)
        script_place.place(self._b, self.node, other, beside, side, in_front_of, float(gap))
        return self

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
        if self._b.taken[oid] == "clay":    # it bends with the clay's pose there (follow.py followPose)
            self.set(follow=oid, followPose=True)
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
                          {"name": path, "path": path, **_ids(values)}, f"script › {self.id}", self._b.notes)
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

    def shape(self, shape: str, at, radius: float = 0.15, to=None, **values) -> "Item":
        """An exact piece, as clay.shape: shape="sphere" or "capsule" (to its other end `to`); mode, blend, symmetry,
        name. The same piece `lump` makes, with the shape said out loud."""
        if shape not in ("sphere", "capsule"):
            raise ValueError(f'clay shape "{shape}": sphere or capsule')
        if shape == "capsule" and to is None:
            raise ValueError("a capsule needs `to`, its other end")
        return self.lump(at, radius, to if shape == "capsule" else None, **values)

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

    def pose(self, at, keys=None, holds=None, ease: str = "smooth", clear=None, **parts) -> "Item":
        """Pose a clay figure at one time: .pose(seconds, **{"hand.R": target, "head": target, …}); chain calls for a
        motion. A target is a world point (x, y, z) or {"up": m, "out": m, "forward": m} from where the part is at rest
        (the figure's own up / away from its middle / the way it faces). Names: "hand.R", "right hand", "picture-left
        hand" (as the shot's camera sees it). holds= joints that stay put. The older .pose("hand.R", {seconds: target})
        still works. Out of reach / far side of the body: a note in the reply. clear=m (asked for, never by
        default): turn the limb out just enough to keep m metres from the head, with a note saying how far it turned. Pose after the last lump (a lump after is made; the joints stay as found)."""
        node = self._clay_node("pose")
        if isinstance(at, str):
            script_pose.pose(self._b, node, at, keys, holds, ease, clear)
        else:
            script_pose.pose_at(self._b, node, at, parts, holds, ease, clear)
        return self

    def bend(self, joint: str, keys, ease: str = "smooth") -> "Item":
        """Turn a clay figure's joint: {seconds: (x, y, z)} degrees about the clay's own X / Y / Z (it faces +Z) from
        its rest, at each time ("arm.R" (0, 0, 120) raises the right arm; "head" (0, 30, 0) turns the head)."""
        script_figure.bend(self._b, self._clay_node("bend"), joint, keys, ease)
        return self

    def _clay_node(self, what: str) -> dict:
        if self.node["type"] != "clay":
            raise ValueError(f"{self.id} is a {self.node['type']}; .{what}() poses a clay")
        return self.node

    def _step(self, values: dict) -> "Item":
        if self.node["type"] != "clay":
            raise ValueError(f"{self.id} is a {self.node['type']}; .lump(), .draw(), .spin() and .stroke() are for "
                             "a clay")
        if self.node.get("bones"):                         # made as written; its joints stay as found (out of date)
            self._b.notes.append(f"{self.id}: a lump, draw, spin or stroke after .pose / .bend: its joints were found from "
                                 "the shape before it and stay as they are (shown as out of date); make the whole shape "
                                 "before the first .pose / .bend to have them found from all of it")
        step_id = self._b.new_id(f"{self.id}.s{len(self.node['steps']) + 1}", loose=True)   # an operation's: .step_N
        self.node["steps"].append(build.make("claystep", step_id, values, f"script › {self.id}", self._b.notes))
        return self

    def __enter__(self):
        if self.node["type"] not in F.HOLDERS:
            raise ValueError(f"{self.id} is a {self.node['type']}; only a group, rig, import or combine holds items")
        self._b.holders.append(self.node)
        return self

    def __exit__(self, *exc):
        self._b.holders.pop()
        if self.id in self._b.grounded:                  # a group stands on the ground as a whole
            script_ground.settle(self._b, self.node, False)


def _key_dict(owner: str, prop: str, keys) -> dict:
    """key()'s keys as {seconds: value or dict}: a list of key.add-shaped dicts ({"t": 1.5, "v": 2}) becomes that."""
    if isinstance(keys, dict):
        return keys
    if not isinstance(keys, (list, tuple)) or not all(isinstance(k, dict) for k in keys):
        raise ValueError(f'{owner}.key("{prop}", …): keys are {{seconds: value}} or a list of {{"t": seconds, "v": value}}')
    out = {}
    for k in map(dict, keys):
        t = k.pop("t", k.pop("at", None))
        if t is None:
            raise ValueError(f'{owner}.key("{prop}", …): each key in the list needs "t", its time in seconds ("at" works too)')
        out[t] = {"v": k.pop("v", k.pop("c", k.pop("value", None))), **k}
    return out


def _vec(values: dict) -> dict:
    """Tuples → lists in a drawing's settings (facing, axis)."""
    return {k: ([list(p) for p in v] if k == "axis" else list(v) if k == "facing" else v) for k, v in values.items()}


def _clay(b: "Build", id_=None, draw=None, spin=None, facing=None, axis=None, puff=None, **values) -> Item:
    """clay(id, **fields): a ball of `radius` (at `at`, its middle; `to` = a capsule), or empty for .lump / .draw; or
    clay(id, draw=[…] / spin=[…]) made from a drawing in the scene (as clay.add's). Made without a height (no at, y,
    draw or spin) it stands on the ground, its own space the scene's (script_figure.py)."""
    if draw is None and spin is None:
        values, first, grounded = script_figure.start(values)
        it = b.item("clay", id_, **values)
        b.figures[it.id] = {"ground": grounded}
        return it._step(first) if first else it
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
    the new copies item, which takes its place (it stands at the copies item's origin, keeping its turn and size; an x / y / z
    given here places the copies item instead). Without
    `source`, it is a holder: `with copies("buds", layout="circle", count=8): mesh(…)`."""
    mine = list(source) if isinstance(source, (list, tuple)) else [] if source is None else [source]
    it = b.item("copies", id_, **values)
    if not mine:
        return it
    siblings = it._siblings()
    nodes = [m.node if isinstance(m, Item) else next((n for n in siblings if n["id"] == m), None) for m in mine]
    if None in nodes or any(n not in siblings for n in nodes):
        raise ValueError(f"{it.id}: its source must be made earlier in the same list (the same group or the top level)")
    it.node.update({k: round(sum(n.get(k, 0.0) for n in nodes) / len(nodes), 6) for k in "xyz" if k not in values})
    siblings.remove(it.node)
    siblings[siblings.index(nodes[0]):siblings.index(nodes[0])] = [it.node]     # takes the first source's place
    for n in nodes:
        siblings.remove(n)
        script_ground.release(b, n["id"])                # inside the copies now: its y is plain
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
    def __init__(self, reserved=(), doc=None, name=""):
        self.root, self.holders, self.reserved, self.taken = KIND.blank(), [], set(reserved), {}      # taken: id -> kind
        self.doc, self.name, self.owned = doc, name, {}                    # owned: id -> its list, things already in the document it takes
        self.reserved |= script_rerun.reserved(doc, name)                  # a counted id never lands on another's id
        self.handles, self.removing, self.keyed = {}, set(), set()         # edit()'s handles; remove()'s ids; (node, field) keyed this run
        self.notes = []                                                    # sentences for the reply's warnings (run_source's Tree)
        self.figures = {}                                                  # clay id -> {ground}: rests on the ground at the end (script_figure.py)
        self.grounded = {}                                                 # id -> the offset from its base to its y (script_ground.py)
        self.given = {}                                                    # id -> the fields the script gave (a remade start item keeps the rest)
        self.framing, self.bright = {}, {}                                 # shot id -> frame= settings; light id -> (stops, at_distance)
        self.bright_default = set()                                        # lights made with no strength: brightness=0 when aimed
        self.replace_lights = False                                        # light(..., replace_start_lights=True)

    def _found(self, id_: str, what: str) -> tuple[str, dict]:
        """(its list, the document's node) of a thing directly in the scene, for edit / remove."""
        if self.doc is None:
            raise ValueError(f"{what}({id_!r}): only a script run on an open document (run_script) can change what is there")
        for lst in ROOT_LISTS:
            node = next((n for n in self.doc.data.get(lst, []) if n.get("id") == id_), None)
            if node is not None:
                return lst, node
        raise ValueError(f"{what}({id_!r}): there is no {id_!r} directly in the scene (an item, material or shot); "
                         "things inside a group are changed through their own script or an operation")

    def edit(self, id_: str, **values) -> "Item":
        """A handle on a thing by its id, with the given fields changed: one this script made earlier (anywhere), or one
        directly in the scene (taken over: its fields as they are, then the ones given). Asked again: the same handle."""
        id_ = _id_of(id_)
        if id_ in self.handles:
            return self.handles[id_].set(**values)
        if id_ in self.taken:                                # made earlier in this script
            node = next((n for n in walk(self.root, KIND.lists) if n.get("id") == id_), None)
            if node is None or node.get("type") == "part":
                raise ValueError(f'edit({id_!r}): {id_!r} is a part of an import; change it with .part()')
            self.handles[id_] = Item(self, node)
            return self.handles[id_].set(**values)
        lst, node = self._found(id_, "edit")
        self.taken[id_], self.owned[id_] = node.get("type", "item"), lst
        mine = copy.deepcopy(node)
        self.root[lst].append(mine)
        self.handles[id_] = Item(self, mine)
        return self.handles[id_].set(**values)

    def remove(self, *ids_):
        """Things already in the document (made by hand, another script or this script's last run), taken out by this
        run (one undo step with the rest)."""
        for id_ in map(_id_of, ids_):
            self.removing.add(id_)
            if self.doc is not None and self.name in self.doc.script_bases and not any(
                    n.get("id") == id_ for lst in ROOT_LISTS for n in self.doc.data.get(lst, [])):
                continue                                     # a re-run: this script took it out already
            lst, _ = self._found(id_, "remove")
            if id_ in self.taken:
                raise ValueError(f'remove({id_!r}): the script also makes {id_!r}')
            self.owned[id_] = lst

    def take_over(self, name: str):
        """Before the merge: what this run takes over moves into its script's last output (the merge's base), out of any
        other script's, so the merge sees an edit or a removal of it, never a second thing under a taken id. The base
        copy is the other script's last output of it when there is one (so a person's later edit is held back, as for any
        script), else the document's own."""
        doc = self.doc
        if doc is not None:
            script_rerun.guard(self)                         # a re-run leaving out most of what it made: said in the reply
            before = set(self.owned)
            script_rerun.remade(self)                        # made again under an id already in the scene: replaces it
            for lst in ROOT_LISTS:                           # made again under a new-scene id: replaces that one
                for n in self.root[lst]:
                    if n["id"] not in self.owned and _start_owned(doc, n["id"], lst):
                        self.owned[n["id"]] = lst
            script_rerun.keep_fields(self, set(self.owned) - before - set(self.handles))   # keeps what it didn't say
            for id_ in start_lights.replaced(doc, self.root["items"], lambda i, lst: _start_owned(doc, i, lst),
                                             self.replace_lights):              # replace_start_lights=True, or a dome
                self.owned.setdefault(id_, "items")
        if doc is None or not self.owned:
            return
        base = doc.script_bases.setdefault(name, KIND.blank())
        for id_, lst in self.owned.items():
            if any(n.get("id") == id_ for n in base.get(lst, [])):
                continue                                     # this script owns it already
            was = None
            for other, b in doc.script_bases.items():
                if other != name and (hit := next((n for n in b.get(lst, []) if n.get("id") == id_), None)):
                    b[lst].remove(hit)
                    was = was or hit
            made = next((n for n in self.root[lst] if n.get("id") == id_), None)
            base[lst].append(copy.deepcopy(was) if was is not None else script_rerun.unheld_copy(doc, lst, id_, made))

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
                          f"script › {type_} {id_ or ''}".strip(), self.notes)
        self.given[node["id"]] = set(values)
        into.append(node)
        return Item(self, node)

    def _attach(self, type_: str, on) -> dict:
        """attach_to=<item>: it follows that item (follow.py), riding the posed bone nearest it on a clay,
        so a part placed on a body never drifts off it."""
        oid = _id_of(on)
        if oid not in self.taken and not (self.doc is not None and any(
                n.get("id") == oid for n in walk(self.doc.data, KIND.lists))):
            raise ValueError(f"attach_to={oid!r}: no such item made earlier in the script or in the scene")
        kind = self.taken.get(oid) or next(n.get("type") for n in walk(self.doc.data, KIND.lists) if n.get("id") == oid)
        return {"follow": oid, "followPose": kind == "clay"}

    def item(self, type_: str, id_=None, **values) -> Item:
        into = self.holders[-1]["children"] if self.holders else self.root["items"]
        floating = "y_world" in values
        if floating:
            values["y"] = values.pop("y_world")
        light = {k: values.pop(k) for k in ("replace_start_lights", "brightness", "at_distance") if k in values}
        if light and type_ != "light":
            raise ValueError(f"{', '.join(light)}: only a light takes these")
        self.replace_lights |= bool(light.get("replace_start_lights"))
        parts = values.pop("parts", []) if type_ == "import" else []
        if (on := values.pop("attach_to", None)) is not None:      # moves (and bends) with what it is attached to
            values.update(self._attach(type_, on))
        if type_ == "import" and values.get("file"):     # read like import.add: metres, upright, base on x y z, its meshes
            keep = values.pop("keepSize", False)
            values, found = ops_import.read_file(values, keep)
            parts += [p for p in found if p not in parts]
        it = self.add(type_, id_, values, into)
        if "brightness" in light:
            self.bright[it.id] = (float(light["brightness"]), light.get("at_distance"))
        elif (type_ == "light" and it.id not in START_LIGHTS and not {"intensity", "exposure", "normalize"} & values.keys()
              and values.get("kind", "rect") not in ("dome", "distant")):
            self.bright_default.add(it.id)          # no strength given: lit as the start key (brightness=0) once it aims
        names = ops_import.part_names(parts)
        for path in parts:
            it.part(path, name=names[path])
        if not floating and script_ground.wants(it.node, not self.holders):
            self.grounded[it.id] = 0.0
            script_ground.settle(self, it.node, True)
        return it


ROOT_LISTS = ("items", "materials", "shots")
START_LIGHTS = {"sky", "key_light", "rim_light"}  # the new scene's lights (start_scene.py): made again, they keep their own strength
START_SCRIPT = "start.py"                     # the new scene's script (start_scene.py, mcp/server.py, files_3d.py)


def _start_owned(doc, id_: str, lst: str) -> bool:
    """Whether the new scene made this one (and it is still there): a script making it again replaces it."""
    base = doc.script_bases.get(START_SCRIPT) or {}
    return any(n.get("id") == id_ for n in base.get(lst, [])) and any(n.get("id") == id_ for n in doc.data.get(lst, []))


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


API = ["y = height of the base above the ground (mesh, import, group made in the scene); y_world= for the origin's world height",
       "group(id, **fields)", "mesh(id, shape=, **fields)", "light(id, kind=, brightness= stops, at_distance=, replace_start_lights=, **fields)", "camera(id, **fields)", "rig(id, rig=orbit|crane|dolly, **fields)",
       "import_usd(id, file=, parts=[...])", "combine(id, op=union|subtract|intersect)", "copies(id, source, layout=line|grid|circle|surface|pour, count=, spacingX=, columns=, radius=, surface=, seed=, varyMove=, varyTurn=, varyScale=, varyStart= (once it falls), pourTime=, pourSpeed=, pourSpread=)", "copies.effector(kind=scale|turn|push|colour, near=, radius=, amount=)", "clay(id, radius=, at=, to=, **fields): a ball (a capsule with to=); no at / y: on the ground, positions = heights above it", "clay(id, draw=[(x, y, z) …] or spin=[…], facing=, axis=, puff=)", "material(id, start=, **fields; stylized blocks: lines=True, linesWidth=, lightToColor=True, litColor=, shadowBelow=, halftone=True, halftoneSize= …)", "shot(id, camera=, fps=, start=, end=, frame=item_or_list, at=(1/3, 0.5), fill=0.6)", "shot.key(\"frame\", {seconds: {\"fill\": 0.4}})", "camera.take_view(pos, look_at)", "row([a, b, c], gap=0.1, centre=True, axis=\"x\", at=)",
       "item.set(**fields)", "item.key(field, {seconds: value} or [{\"t\": seconds, \"v\": value}], ease=)", "item.aim(item or (x, y, z), roll=)", "item.place_on(other, gap=) / place_on(other, beside=\"left\"|\"right\"|\"front\"|\"back\", gap=) / place_on(in_front_of=other) / place_on(clay or mesh, at=(x, y, z), normal=)",
       "import.part(path, material=, visible=)", "edit(id, **fields) or item(id): a handle on a thing by id (made earlier in the script, or in the scene: shot_1, ground …)", "remove(id, …)",
       "clay.lump(at, radius, to=, mode=add|carve, blend=)", "clay.draw(outline, facing=, puff=, mode=, blend=, name=)", "clay.spin(profile, axis=, mode=, blend=, name=)", "clay.stroke(path=, dir=, brush=, size=, strength=)", "clay.pose(seconds, **{\"right hand\": (x, y, z) or {\"up\": m, \"out\": m, \"forward\": m}, \"head\": …}, holds=): one pose per call, chain for motion; names hand.R / right hand / picture-left hand", "clay.bend(joint, {seconds: (x, y, z) degrees})", "any item: attach_to=<item> (moves and bends with it)", "with group(...): / with rig(...): / with import_usd(...): / with combine(...): / with copies(...):"]


def run_source(source: str, name: str, doc=None) -> dict:
    """Python source → the document tree it builds. Any error is a loud BAD_ARGUMENT naming the line; nothing merged.
    With the open document (`doc`, as run_script passes it): edit / remove, and the new scene's things made again by id,
    are taken over (Build.take_over) before the merge."""
    b = Build(_reserved(source), doc, name)
    scope = {"__builtins__": {**SAFE, "__import__": _import}, "math": math,
             "material": lambda id=None, start=None, **v: b.add("material", id, _start(start, v), b.root["materials"]),
             "shot": lambda id=None, **v: script_shot.make(b, id, v),
             "row": lambda items, gap=0.1, centre=True, axis="x", at=None: script_place.row(
                 b, [b.edit(i).node for i in items], float(gap), centre, axis, at),
             "import_usd": lambda id=None, **v: b.item("import", id, **v),
             "clay": lambda id=None, **v: _clay(b, id, **v),
             "copies": lambda id=None, source=None, **v: _copies(b, id, source, **v),
             "edit": lambda id, **v: b.edit(id, **v), "item": lambda id: b.edit(id), "remove": lambda *ids: b.remove(*ids),
             **{t: (lambda id=None, _t=t, **v: b.item(_t, id, **v)) for t in ("group", "mesh", "combine", "light", "camera", "rig")}}
    try:
        exec(compile(source, name, "exec"), scope)
    except Exception as e:
        import traceback
        line = next((f" (line {fr.lineno})" for fr in traceback.extract_tb(e.__traceback__) if fr.filename == name), "")
        if isinstance(e, RostrumError) and e.hint:                  # its own "did you mean": its names, not the script list
            raise RostrumError(e.code, "", f'script "{name}"', f"failed{line}: {e.where + ': ' if e.where else ''}"
                               f"{' '.join(w for w in (e.subject, e.problem) if w)}", e.accepted, e.hint) from e
        if near := nearest.script_hint(e, scope):                   # a wrong name, call or argument: the closest real ones
            raise RostrumError(codes.BAD_ARGUMENT, "", f'script "{name}"', f"failed{line}: {type(e).__name__}: {near}") from e
        raise RostrumError(codes.BAD_ARGUMENT, "", f'script "{name}"', f"failed{line}: {type(e).__name__}: {e}",
                           () if "Did you mean" in str(e) else API) from e
    try:
        for clay_id in b.figures:
            node = next((n for n in walk(b.root, KIND.lists) if n.get("id") == clay_id), None)
            if node is not None:
                script_ground.settle_clay(b, node)
        for light_id, (stops, far) in b.bright.items():
            script_shot.brightness(b, next(n for n in walk(b.root, KIND.lists) if n.get("id") == light_id), stops, far)
        for light_id in b.bright_default - b.bright.keys():     # canary r8: a rect with no strength came out ~4 stops under the sky fill
            node = next((n for n in walk(b.root, KIND.lists) if n.get("id") == light_id), None)
            if node is not None and node.get("aim", "none") != "none" and (node.get("intensity", 1.0), node.get("exposure", 0.0),
                                                                     node.get("normalize", False)) == (1.0, 0.0, False):
                script_shot.brightness(b, node, 0.0)
                b.notes.append(f"{light_id}: no intensity or brightness given, so it lights its subject as the start key does "
                               "(brightness=0); give brightness= in stops (−1 half, +1 twice) to change it")
    except ValueError as e:
        raise RostrumError(codes.BAD_ARGUMENT, "", f'script "{name}"', f"failed: {e}", API) from e
    script_shot.default_view(b)                              # a shot with no camera: the default view, said
    b.take_over(name)
    return Tree(b.root, b.notes)


class Tree(dict):
    """run_source's document tree, carrying the run's notes (Build.notes: a pose target out of reach …), which
    run_script adds to its reply's warnings."""

    def __init__(self, root: dict, notes: list):
        super().__init__(root)
        self.notes = list(dict.fromkeys(notes))


run_source.wants_doc = True            # rostrum_core's run_script tool then passes the open document
