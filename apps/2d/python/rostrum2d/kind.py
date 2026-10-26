"""The 2D document kind: where items live, what each list may hold, the whole-document check, and one field
operation per item type (`text.set`, `glow.set`, `key.set` …) generated from the fields table.

    doc ─ paintings ─ painting ─ frames ─ frame ─ paints … (a painting of the scene: paintings.py)
        ─ comps ─ comp ─ layers ─ camera (the scene's one frame, first: frame/) | shape | text | image | group (group ─ layers …)
                                  | drawing ─ frames ─ frame ─ paints ─ paint ─ strokes (painting kit)
                                  shape | text | image | video | path may hold frames too (paint on an element)
                                                                   ─ paintmasks
                                  each layer ─ effects (blur, glow, gradient, shadow) ─ keys
                                             ─ masks ─ keys
                                             ─ keys
"""
from __future__ import annotations

import re

import rostrum_paint
from rostrum_core import DocKind, Registry, plugin_parts

from . import advice, exprbake, fields as F, fill_fields, fill_paint, fontcheck, fontlist, layout_pin, media, migrations, names, paint_fields, paintings, pathdata, refusals, shared_paints, text_anchor, widthprofile
from .frame import make as frame_make, rules as frame_rules
from .rig import model as rig_model

OWNED = ["effects", "masks", "keys"]
LISTS = {"doc": ["comps", "paintings", "textStyles", "swatches"], "painting": ["frames"], "comp": ["layers"], "group": ["layers", *OWNED], "drawing": ["frames", *OWNED],
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
HOLDS = {"comps": ("comp",), "paintings": ("painting",), "stops": ("stop",), "swatches": ("swatch",), "layers": F.LAYERS, "effects": F.EFFECTS, "masks": ("mask",), "keys": ("key",),
         "exprs": ("expr",), "textStyles": ("textstyle",),
         "frames": ("frame",), "bones": ("bone",), "iks": ("ik",), "binds": ("bind",), "poses": ("pose",), **rostrum_paint.HOLDS}

REGISTRY = Registry()


def _set_fields(ctx, targets, args):
    for t in targets:
        item = ctx.item(t)
        size = (item.get("width", 0.0), item.get("height", 0.0))
        if item.get("type") in ("text", "textstyle") and {"font", "italic"} & set(args) and (why := fontlist.setting_refusal(
                t, args.get("font", item.get("font", "")), args.get("italic", item.get("italic", False)))):
            raise ValueError(why)                       # never drawn in another font: refused when set
        before = dict(item) if item.get("type") == "text" else None
        for k, v in args.items():
            ctx.set(t, k, v)
        if before is not None:                       # Align moves a point text's anchor with it (text_anchor.py)
            for k, v in text_anchor.follow(before, ctx.item(t), args).items():
                ctx.set(t, k, v)
        names.after_set(ctx, t, args)                # a new shape is named for its kind, counted per kind
        text_styles.after_set(ctx, t, args)          # a style reaches its texts; a text set by hand leaves its style
        frame_make.resized(ctx, t, size)             # a scene's new size: its pinned layers keep their distance from the frame's centre


for _type, _params in F.FIELDS.items():
    _label = F.LABELS[_type].lower()
    REGISTRY.operation(f"{_type}.set", f"Change a {_label}'s settings.", target=_type, label=f"Edit {_label}",
                       params=[p for p in _params if p.name not in F.FIXED.get(_type, ())], fields=True)(_set_fields)


def facts(item: dict, doc=None) -> dict:
    if item.get("type") == "key":
        return {"number": "v" in item, "color": "c" in item, "shape": "d" in item,      # rawSpring: keys.spring
                "rawSpring": not {"bounce", "speed"} & set(item)}
    out = {"hasPaint": bool(item.get("frames"))} if item.get("type") in paint_fields.TYPES else {}
    if item.get("fillType") == "painted" and doc is not None:     # Start at drawing: its painting draws each frame
        out["paintingBoils"] = _boils(doc, item.get("fillPainting", ""))
    if item.get("type") == "camera":                       # frame.home is offered only while the frame is away
        from .ops_frame_fit import away
        out["frameAway"] = away(item)
    if item.get("type") in ("text", "textstyle"):         # Italic shows where the family has one (or it is on)
        out["fontItalic"] = bool(item.get("italic")) or _has_italic(item.get("font", F.defaults("text")["font"]))
    if item.get("type") in F.LAYERS and doc is not None:      # inside a group with an auto layout (layout.py)
        parent = doc.parent(item)
        out["inLayout"] = bool(parent) and parent.get("type") == "group" and parent.get("layout", "none") != "none"
        # a scene's own layer with a camera beside it: Depth and Pinned to screen mean something (fields.UNDER_CAMERA)
        out["underCamera"] = bool(parent) and parent.get("type") == "comp" \
            and any(c.get("type") == "camera" for c in parent.get("layers", []))
        if out["underCamera"]:                                # Cover the frame's move (background.fit) needs a move
            from .frame import view
            out["frameMoves"] = view.moves(view.of(parent))
    return out


def _boils(doc, painting_id: str) -> bool:
    painting = doc.item(painting_id) if painting_id else None
    return bool(painting) and bool(painting.get("eachFrame")) and len(painting.get("frames", [])) > 1


def _has_italic(family: str) -> bool:
    try:
        return bool((fontlist.family(family) or {}).get("italic"))
    except Exception:  # noqa: BLE001  no engine built: the row stays away (nothing can be drawn then anyway)
        return False


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
        if want != "v" and ({"out", "in"} & set(k)):
            problems.append(f'key {k["id"]}: out / in (spatial handles) belong on a number key only, not a {prop} key')
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
    if not opening:
        problems += refusals.problems(item)
    if item.get("type") == "rig":
        problems += rig_model.problems_of(item)
    if item.get("type") == "text" and item.get("path"):
        follow = ('to make a text follow a path layer write text.follow with path:"<path layer id>" '
                  '(in a script: text(..., pathLayer="<id>"))')
        try:
            pathdata.commands(item["path"])
        except ValueError as e:
            what = f'"{item["path"]}" is not path data' if re.fullmatch(r"[A-Za-z_][\w.-]{2,}", item["path"]) else str(e)
            problems.append(f'{item["id"]}.path: {what}. `path` is SVG path data (M L C Z); {follow}')
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


def check(data: dict, items=None, idx=None) -> list[str]:
    """Each list holds only its own kinds of item; keys name real animatable fields, one per field per time.
    `items`: the items a change set or brought in (rostrum_core.kind); then only they and the items holding them are
    checked in full (a key's owner sees its duplicate times), and only their texts' fonts. None: everything, as on open.
    `idx` (with `items`): the document's index, so the items holding them are looked up, not walked to."""
    if items is not None and idx is not None:
        return _check_changed(data, items, idx)
    problems, stack = [], [data]
    changed = None if items is None else {i["id"] for i in items}
    owners = []
    while stack:
        item = stack.pop()
        for key in LISTS.get(item.get("type"), []):
            held = HOLDS[key]
            for child in item.get(key, []):
                t = child.get("type")
                if plugin_parts.is_plugin(t):   # a plugin's item: kept as it is, never looked inside (plugin_parts.py)
                    continue
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
    return problems + paintings.problems(data, items) + frame_rules.problems(data, items) + exprbake.problems_of_doc(data) + fontcheck.problems_of_doc(texts)


def _check_changed(data: dict, items, idx) -> list[str]:
    """check() of the items a change set or brought in, each found in its parent's list through the index."""
    problems, owners = [], {}
    for child in items:
        loc = idx.get(child["id"])
        if loc is None or loc.parent is None or plugin_parts.is_plugin(child.get("type")):
            continue
        parent, up = idx[loc.parent].item, idx[loc.parent]
        while up is not None and not plugin_parts.is_plugin(up.item.get("type")):
            up = idx[up.parent] if up.parent is not None else None
        if up is not None:                      # inside a plugin's item: kept as it is, never looked inside
            continue
        owners[id(parent)] = parent
        held = HOLDS[loc.key]
        if child.get("type") not in held:
            problems.append(f'{parent["id"]}.{loc.key} can\'t hold a {child.get("type")} ({child["id"]}); '
                            f"it holds: {', '.join(held)}")
    for item in {**owners, **{id(i): i for i in items}}.values():
        _check_owner(item, problems)
    texts = {"layers": [i for i in items if i.get("type") == "text"]}
    return problems + paintings.problems(data, items) + frame_rules.problems(data, items) + exprbake.problems_of_doc(data) + fontcheck.problems_of_doc(texts)


def upgrade(data: dict, lists: dict, folder=None):
    """An older file brought up to date, one step after another: (new data, label) or None."""
    labels = []
    for step in (fill_paint.upgrade, shared_paints.upgrade, layout_pin.upgrade, lambda d, l: media.upgrade(d, l, folder)):
        up = step(data, lists)
        if up:
            data, label = up
            labels.append(label)
    return (data, "; ".join(labels)) if labels else None


KIND = DocKind("2d", ".mtn", REGISTRY, lists=LISTS, check=check, facts=facts, upgrade=upgrade, advise=advice.advise,
               version=migrations.FORMAT, migrations=migrations.STEPS,
               new=lambda: {"id": "root", "type": "doc", "comps": [], "paintings": []})

rostrum_paint.register(REGISTRY, canvas_types=("frame",), peers=shared_paints.peers, seamless=paintings.seamless_canvas)
from .modules import OPS  # noqa: E402
OPS.load()  # noqa: E402  (they register on REGISTRY: rostrum2d/modules.py)
from . import text_styles  # noqa: E402  (loaded by OPS; used below)
