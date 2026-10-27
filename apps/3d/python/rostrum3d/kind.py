"""The 3D document kind: where items live, what each list may hold, the whole-document check, and one field
operation per type (`mesh.set`, `light.set`, `material.set`, `shot.set` …) generated from the fields table.

    doc ─ items     ─ group  ─ children (items …) ─ keys
                    ─ import ─ children, parts ─ keys
                    ─ combine ─ children (2+ meshes / combines) ─ keys
                    ─ mesh ─ bones (a chain: bone ─ bones …, keys) ─ keys
                    ─ clay ─ steps (claystep: pieces and strokes, in order), bones (its joints, as a mesh's chain),
                             paints (as a mesh's) ─ keys
                    ─ light | camera ─ keys
        ─ materials ─ material
        ─ shots     ─ shot
"""
from __future__ import annotations

import re

import rostrum_paint
from rostrum_core import DocKind, Registry, plugin_parts
from rostrum_core.tree import walk

from . import clay_dabs, clay_fields, fields as F, paint_fields

LISTS = {**F.LISTS, **rostrum_paint.LISTS}          # a mesh is a paint canvas: paints › strokes (the shared kit)
HOLDS = {"items": F.ITEMS, "children": F.ITEMS, "materials": ("material",), "shots": ("shot",),
         "parts": ("part",), "keys": ("key",), "poses": ("pose",), "bones": ("bone",), "steps": ("claystep",), **rostrum_paint.HOLDS}
PRIM_ID = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")    # scene items and materials become USD prim names

REGISTRY = Registry()


def _set_fields(ctx, targets, args):
    for t in targets:
        for k, v in args.items():
            ctx.set(t, k, v)


for _type, _params in F.FIELDS.items():
    _label = F.LABELS[_type].lower()
    REGISTRY.operation(f"{_type}.set", f"Change a {_label}'s settings.", target=_type, params=_params,
                       label=f"Edit {_label}", fields=True)(_set_fields)


def facts(item: dict) -> dict:
    if item.get("type") == "key":
        return {"number": "v" in item, "color": "c" in item}
    if item.get("type") in F.KEYED:
        return {"animated": F.animated_fact(item), "animating": True,    # a screen overrides animating with its page
                "sculpting": True,                                       # and sculpting with its Clay tool being on
                "boned": bool(item.get("bones")),                         # a mesh with a chain / a clay with joints
                "painted": bool(item.get("paints"))}                      # a mesh / clay with paint layers: Paint size shows
    return {}


def _check_keys(owner: dict, problems: list):
    seen, allowed = set(), F.animatable(owner["type"])
    for k in owner.get("keys", []):
        prop = k.get("prop")
        if prop not in allowed:
            problems.append(f'key {k["id"]}: a {owner["type"]} ({owner["id"]}) has no animatable field "{prop}" '
                            f"(it has: {', '.join(allowed)})")
            continue
        want = "c" if F.param(owner["type"], prop).type == "color" else "v"
        if want not in k:
            problems.append(f'key {k["id"]}: a {prop} key needs {"c (a colour)" if want == "c" else "v (a number)"}')
        if (prop, k.get("t")) in seen:
            problems.append(f'{owner["id"]}: two {prop} keys at {k.get("t")} s')
        seen.add((prop, k.get("t")))


def _check_combine(item: dict, problems: list):
    """A combine holds two or more solids (meshes or combines), none of them animated: the core makes the result
    once per shot (ops_combine.py)."""
    kids = item.get("children", [])
    if len(kids) < 2:
        problems.append(f'combine {item["id"]}: holds {len(kids)} solid{"" if len(kids) == 1 else "s"}; it needs two or '
                        "more (undo, or add another mesh into it)")
    for c in kids:
        if c.get("type") not in F.SOLIDS:
            problems.append(f'combine {item["id"]}: {c["id"]} is a {c.get("type")}; a combine holds meshes and combines')
        elif c.get("keys"):
            problems.append(f"combine {item['id']}: its input {c['id']} has keys; a combine's inputs can't be "
                            "animated yet (key the combine itself)")


def _ref(problems, item, field, value, ids, what):
    if value and value not in ids:
        problems.append(f'{item["id"]}.{field}: no {what} "{value}" (there are: {", ".join(sorted(ids)) or "none"})')


_KNOWN = {t: {"id", "type", "name", *(["prop"] if t == "key" else []), *(p.name for p in ps), *LISTS.get(t, [])}
          for t, ps in F.FIELDS.items()}


def check(data: dict) -> list[str]:
    """Lists hold their own kinds; prim-safe ids; keys name animatable fields; every reference points at a real
    thing of the right type (materials, a shot's camera, an aim's item)."""
    problems, everything = [], list(walk(data, LISTS))
    by_type = lambda *types: {i["id"] for i in everything if i.get("type") in types}  # noqa: E731
    materials, items, cameras = by_type("material"), by_type(*F.ITEMS), by_type("camera")
    for item in everything:
        for key in LISTS.get(item.get("type"), []):
            for child in item.get(key, []):
                if child.get("type") not in HOLDS[key] and not plugin_parts.is_plugin(child.get("type")):   # a plugin's: kept as it is
                    problems.append(f'{item["id"]}.{key} can\'t hold a {child.get("type")} ({child["id"]}); '
                                    f"it holds: {', '.join(HOLDS[key])}")
        t = item.get("type")
        stray = sorted(k for k in set(item) - _KNOWN.get(t, set(item)) if not plugin_parts.is_plugin(k))
        if stray:                                        # e.g. a re-run that gave an id another kind (light → mesh)
            problems.append(f'{t} {item["id"]}: has {", ".join(stray)}, which a {t} does not have (did a script give '
                            f'the id "{item["id"]}" to a different kind of thing? Use a new id for the new kind)')
        if t in (*F.KEYED, "material") and not PRIM_ID.match(item["id"]):
            problems.append(f'id "{item["id"]}": a {t} id is letters, digits and _ only, not starting with a digit')
        if t in F.KEYED:
            _check_keys(item, problems)
            if item.get("aim") == "item":
                if not item.get("aimItem"):
                    problems.append(f'{item["id"]}: aims at an item but aimItem is empty')
                elif item["aimItem"] == item["id"]:
                    problems.append(f'{item["id"]}: can\'t aim at itself')
                _ref(problems, item, "aimItem", item.get("aimItem"), items, "item")
            for ref, word in (("follow", "follow"), ("stick", "stick to")):         # follow.py's constraints
                if item.get(ref) == item["id"]:
                    problems.append(f"{item['id']}: can't {word} itself")
                _ref(problems, item, ref, item.get(ref), items, "item")
        if t == "light" and item.get("kind") != "dome":     # light linking: every named id a real item, not itself
            for linked in item.get("lightsOnly", "").split():
                _ref(problems, item, "lightsOnly", linked, items - {item["id"]}, "item")
        if t == "combine":
            _check_combine(item, problems)
        if t == "clay":
            by_id = {i["id"]: i for i in everything}               # a step made from an item names it (CL3)
            for step in item.get("steps", []):
                clay_fields.check_step(item, step, problems, by_id)
        if t in ("mesh", "clay"):
            paint_fields.check_strokes(item, problems)
        if t in ("mesh", "combine", "import", "part", "clay"):
            _ref(problems, item, "material", item.get("material"), materials, "material")
        if t == "mesh":
            for face in ("frontMaterial", "bevelMaterial", "sideMaterial", "backMaterial"):
                _ref(problems, item, face, item.get(face), materials, "material")
        if t == "shot":
            _ref(problems, item, "camera", item.get("camera"), cameras, "camera")
            if item.get("end", 0) <= item.get("start", 0):
                problems.append(f'shot {item["id"]}: ends ({item.get("end")} s) before it starts ({item.get("start")} s)')
    return problems


KIND = DocKind("3d", ".trd", REGISTRY, lists=LISTS, check=check, facts=facts, tidy=clay_dabs.tidy,
               new=lambda: {"id": "root", "type": "doc", "items": [], "materials": [], "shots": [], "poses": []})

# painting on meshes and clays (SPEC §5): the shared kit's paint layers, strokes and masks, each layer painting one
# channel; a clay's strokes are kept on its surface (anchors, reach: paint_fields.STROKE, clay_paint.py)
rostrum_paint.register(REGISTRY, canvas_types=("mesh", "clay"), layer_fields=paint_fields.LAYER,
                       stroke_fields=paint_fields.STROKE)

from .modules import OPS  # noqa: E402
OPS.load()  # noqa: E402  (they register on REGISTRY: rostrum3d/modules.py)
