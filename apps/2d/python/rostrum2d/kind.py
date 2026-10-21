"""The 2D document kind: where items live, what each list may hold, the whole-document check, and one field
operation per item type (`text.set`, `glow.set`, `key.set` …) generated from the fields table.

    doc ─ comps ─ comp ─ layers ─ shape | text | image | group (group ─ layers …)
                                  each layer ─ effects (blur, glow, gradient, shadow) ─ keys
                                             ─ masks ─ keys
                                             ─ keys
"""
from __future__ import annotations

from rostrum_core import DocKind, Registry

from . import fields as F

OWNED = ["effects", "masks", "keys"]
LISTS = {"doc": ["comps"], "comp": ["layers"], "group": ["layers", *OWNED],
         **{t: OWNED for t in ("shape", "text", "image")},
         **{t: ["keys"] for t in (*F.EFFECTS, "mask")}}
HOLDS = {"comps": ("comp",), "layers": F.LAYERS, "effects": F.EFFECTS, "masks": ("mask",), "keys": ("key",)}

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
    return {}


def _check_keys(owner: dict, problems: list):
    seen = set()
    allowed = F.animatable(owner["type"])
    for k in owner.get("keys", []):
        prop = k.get("prop")
        if prop not in allowed:
            problems.append(f'key {k["id"]}: {owner["type"]} {owner["id"]} has no animatable field "{prop}" '
                            f"(it has: {', '.join(allowed)})")
        is_color = F.param(owner["type"], prop) is not None and F.param(owner["type"], prop).type == "color"
        if ("c" if is_color else "v") not in k:
            problems.append(f'key {k["id"]}: a {prop} key needs {"c (a colour)" if is_color else "v (a number)"}')
        if (prop, k.get("t")) in seen:
            problems.append(f'{owner["id"]}: two {prop} keys at {k.get("t")} s')
        seen.add((prop, k.get("t")))


def check(data: dict) -> list[str]:
    """Each list holds only its own kinds of item; keys name real animatable fields, one per field per time."""
    problems, stack = [], [data]
    while stack:
        item = stack.pop()
        for key in LISTS.get(item.get("type"), []):
            for child in item.get(key, []):
                if child.get("type") not in HOLDS[key]:
                    problems.append(f'{item["id"]}.{key} can\'t hold a {child.get("type")} ({child["id"]}); '
                                    f"it holds: {', '.join(HOLDS[key])}")
                stack.append(child)
        if item.get("type") in F.ANIMATED_OWNERS:
            _check_keys(item, problems)
    return problems


KIND = DocKind("2d", ".mtn", REGISTRY, lists=LISTS, check=check, facts=facts,
               new=lambda: {"id": "root", "type": "doc", "comps": []})

from . import ops_items, ops_keys  # noqa: E402,F401  (they register on REGISTRY)
