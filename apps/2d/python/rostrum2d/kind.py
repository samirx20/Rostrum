"""The 2D document kind: where items live, what each list may hold, the whole-document check, and one field
operation per item type (`text.set`, `glow.set`, `key.set` …) generated from the fields table.

    doc ─ comps ─ comp ─ layers ─ shape | text | image | group (group ─ layers …)
                                  | drawing ─ frames ─ frame ─ paints ─ paint ─ strokes (painting kit)
                                  shape | text | image | video | path may hold frames too (paint on an element)
                                                                   ─ paintmasks
                                  each layer ─ effects (blur, glow, gradient, shadow) ─ keys
                                             ─ masks ─ keys
                                             ─ keys
"""
from __future__ import annotations

import rostrum_paint
from rostrum_core import DocKind, Registry

from . import exprbake, fields as F, fill_fields, fill_paint, fontcheck, paint_fields, pathdata, shared_paints, widthprofile
from .rig import model as rig_model

OWNED = ["effects", "masks", "keys"]
LISTS = {"doc": ["comps", "textStyles", "swatches"], "comp": ["layers"], "group": ["layers", *OWNED], "drawing": ["frames", *OWNED],
         "frame": rostrum_paint.CANVAS_LISTS, **rostrum_paint.LISTS,
         "rig": ["layers", "bones", "iks", "binds", "poses", *OWNED], "bone": ["keys"], "ik": ["keys"], "camera": ["keys"],
         **{t: OWNED for t in ("shape", "text", "image", "video", "render3d", "path")},
         **{t: ["frames", *OWNED] for t in paint_fields.TYPES},     # paint on an element (paint_fields.py)
         **{t: ["keys"] for t in (*F.EFFECTS, "mask", "stop")}}
for _t in fill_fields.OWNERS:          # a gradient fill's stops (fill_fields.py)
    LISTS[_t] = [*LISTS[_t], "stops"]
for _t, _owned in LISTS.items():       # whatever animates a field may also hold its expression (ops_expr.py)
    if _t in F.ANIMATED_OWNERS and "exprs" not in _owned:
        _owned.append("exprs")
HOLDS = {"comps": ("comp",), "stops": ("stop",), "swatches": ("swatch",), "layers": F.LAYERS, "effects": F.EFFECTS, "masks": ("mask",), "keys": ("key",),
         "exprs": ("expr",), "textStyles": ("textstyle",),
         "frames": ("frame",), "bones": ("bone",), "iks": ("ik",), "binds": ("bind",), "poses": ("pose",), **rostrum_paint.HOLDS}

REGISTRY = Registry()


def _set_fields(ctx, targets, args):
    for t in targets:
        for k, v in args.items():
            ctx.set(t, k, v)
        text_styles.after_set(ctx, t, args)          # a style reaches its texts; a text set by hand leaves its style


for _type, _params in F.FIELDS.items():
    _label = F.LABELS[_type].lower()
    REGISTRY.operation(f"{_type}.set", f"Change a {_label}'s settings.", target=_type, params=_params,
                       label=f"Edit {_label}", fields=True)(_set_fields)


def facts(item: dict, doc=None) -> dict:
    if item.get("type") == "key":
        return {"number": "v" in item, "color": "c" in item, "shape": "d" in item,      # rawSpring: keys.spring
                "rawSpring": not {"bounce", "speed"} & set(item)}
    out = {"hasPaint": bool(item.get("frames"))} if item.get("type") in paint_fields.TYPES else {}
    if item.get("type") in F.LAYERS and doc is not None:      # inside a group with an auto layout (layout.py)
        parent = doc.parent(item)
        out["inLayout"] = bool(parent) and parent.get("type") == "group" and parent.get("layout", "none") != "none"
    return out


_NEEDS = {"v": "v (a number)", "c": "c (a colour)", "d": "d (text: path data, or a width profile \"pos,mult …\")"}


def check_text(prop: str, text: str):
    """A text key's value read by its own parser (a path's `d` or its `widthProfile`); ValueError says what is wrong."""
    (widthprofile.parse if prop == "widthProfile" else pathdata.commands)(text)


def _check_keys(owner: dict, problems: list):
    seen = set()
    allowed = F.animatable(owner["type"])
    for k in owner.get("keys", []):
        prop = k.get("prop")
        if prop not in allowed:
            problems.append(f'key {k["id"]}: {owner["type"]} {owner["id"]} has no animatable field "{prop}" '
                            f"(it has: {', '.join(allowed)})")
        want = F.key_field(owner["type"], prop) if prop in allowed else "v"
        if want not in k:
            problems.append(f'key {k["id"]}: a {prop} key needs {_NEEDS[want]}')
        elif want == "d":
            try:
                check_text(prop, k["d"])
            except ValueError as e:
                problems.append(f'key {k["id"]}: {owner["id"]}.{prop} at {k.get("t")} s: {e}')
        if (prop, k.get("t")) in seen:
            problems.append(f'{owner["id"]}: two {prop} keys at {k.get("t")} s')
        seen.add((prop, k.get("t")))


_LEAVES = frozenset(t for t, owned in rostrum_paint.LISTS.items() if not owned)   # strokes, fills: nothing inside


def _check_owner(item: dict, problems: list, opening: bool = False):
    """What one item's own fields and lists must satisfy (its keys, a rig's parts, a path's data, its drawings' order,
    a gradient's two stops). `opening`: a file being opened is not refused for a fill it already had (export still says)."""
    if not opening and item.get("fillType") in fill_fields.GRADIENTS and len(item.get("stops", [])) < 2:
        n = len(item.get("stops", []))
        problems.append(f'{item["id"]}: a {item["fillType"]} fill needs at least 2 colour stops, it has {n} '
                        f'(use layer.fill with stops, or set the fill type through layer.fill, which adds them)')
    if item.get("type") in F.ANIMATED_OWNERS:
        _check_keys(item, problems)
    if item.get("type") == "rig":
        problems += rig_model.problems_of(item)
    if item.get("type") == "path":
        try:
            pathdata.commands(item["d"])
        except ValueError as e:
            problems.append(f'{item["id"]}.d: {e}')
        try:
            widthprofile.parse(item.get("widthProfile", ""))
        except ValueError as e:
            problems.append(f'{item["id"]}.widthProfile: {e}')
    if item.get("frames"):              # a drawing's, or an element's paint
        ats = [f["at"] for f in item["frames"]]
        if ats != sorted(set(ats)):
            problems.append(f'{item["id"]}: drawings must be at different frames, in order (they are at {ats})')
        problems += shared_paints.problems(item)       # every drawing holds the layer's paint layers


def check(data: dict, items=None) -> list[str]:
    """Each list holds only its own kinds of item; keys name real animatable fields, one per field per time.
    `items`: the items a change set or brought in (rostrum_core.kind); then only they and the items holding them are
    checked in full (a key's owner sees its duplicate times), and only their texts' fonts. None: everything, as on open."""
    problems, stack = [], [data]
    changed = None if items is None else {i["id"] for i in items}
    owners = []
    while stack:
        item = stack.pop()
        for key in LISTS.get(item.get("type"), []):
            held = HOLDS[key]
            for child in item.get(key, []):
                t = child.get("type")
                if changed is not None and child["id"] in changed and (not owners or owners[-1] is not item):
                    owners.append(item)
                if t not in held:
                    problems.append(f'{item["id"]}.{key} can\'t hold a {t} ({child["id"]}); '
                                    f"it holds: {', '.join(held)}")
                if t not in _LEAVES:            # thousands of strokes: only their kind is looked at
                    stack.append(child)
        if changed is None:
            _check_owner(item, problems, opening=True)
    if changed is not None:
        for item in {id(i): i for i in [*owners, *items]}.values():
            _check_owner(item, problems)
    texts = data if items is None else {"layers": [i for i in items if i.get("type") == "text"]}
    return problems + exprbake.problems_of_doc(data) + fontcheck.problems_of_doc(texts)


def upgrade(data: dict, lists: dict):
    """An older file brought up to date, one step after another: (new data, label) or None."""
    labels = []
    for step in (fill_paint.upgrade, shared_paints.upgrade):
        up = step(data, lists)
        if up:
            data, label = up
            labels.append(label)
    return (data, "; ".join(labels)) if labels else None


KIND = DocKind("2d", ".mtn", REGISTRY, lists=LISTS, check=check, facts=facts, upgrade=upgrade,
               new=lambda: {"id": "root", "type": "doc", "comps": []})

rostrum_paint.register(REGISTRY, canvas_types=("frame",), peers=shared_paints.peers)
from . import ops_draw, ops_expr, ops_items, ops_keys  # noqa: E402,F401  (they register on REGISTRY)
from . import follow  # noqa: E402,F401  (text.follow: a text on a path layer)
from . import ops_path, ops_stroke  # noqa: E402,F401  (vector paths, booleans, stroke width)
from .rig import ops as _rig_ops, poses as _rig_poses, guess as _rig_guess, joints as _rig_joints, draw as _rig_draw, mirror as _rig_mirror  # noqa: E402,F401  (bones, IK chains, binds, poses, Bones from part names, joints and posing, the Bone tool, Mirror pose)
from .lipsync import ops as _lipsync_ops  # noqa: E402,F401  (lipsync.apply)
from . import ops_swap  # noqa: E402,F401  (swap.show, blink.add)
from . import ops_timing  # noqa: E402,F401  (layer.shift, layer.trim: move and trim a layer in time)
from . import ops_background  # noqa: E402,F401  (background.add, background.fit, background.move: painted backgrounds)
from . import ops_group, ops_mask, ops_state, ops_align, ops_look  # noqa: E402,F401  (select first, then act)
from . import ops_clip  # noqa: E402,F401  (layer.paste: copy / cut / paste of layers)
from . import ops_paint, ops_fill, paint_transform  # noqa: E402,F401  (paint.stroke, paint.fill, stroke.transform: paint, fill and move paint on any element or drawing)
from . import ops_frame  # noqa: E402,F401  (comp.size, layer.fill_frame)
from . import ops_keytime, ops_stagger  # noqa: E402,F401  (key.scale, key.paste, layer.stagger: retiming)
from . import ops_anim  # noqa: E402,F401  (anim.ease: ease whole stretches; anims.py: anim.list)
from . import ops_fill_paint  # noqa: E402,F401  (layer.fill, swatch.add / remove / rename: the fill as a paint, project colours)
from . import text_styles  # noqa: E402  (style.define, style.use, style.detach, style.remove: named text styles)
