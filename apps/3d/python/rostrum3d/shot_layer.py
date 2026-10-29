"""Only in this shot (PR1): a shot's own changes laid over the document before the compiler builds that shot.

A shot holds `overrides` = {item or material id: {field: value}}: in that shot the field has that value; everywhere
else the document's. An overridden field that has keys holds the one value through that shot (its keys don't play
there): the simplest honest rule, and what a person sees in the settings panel. An override naming an item or field
that is gone is skipped (an old override never stops a shot from building). Old documents have no `overrides`: nothing
changes. Collections named in a light's `lightsOnly` become their members here too (collection_kit.py), so the core only
ever sees item ids.
"""
from __future__ import annotations

from . import collection_kit as COL, fields as F, mirror
from .copies_fields import COPY_KEYS, COPY_KEYS_FROM, HELD
from .sim import fields as SIM

FIELD = "overrides"                                    # the shot's: {id: {field: value}}
TYPES = (*F.ITEMS, "material")                         # what a shot may override
NEVER = {"kind", "shape", *SIM.NAMES, *mirror.FIELDS, HELD, COPY_KEYS, COPY_KEYS_FROM}   # changes what the thing is, or data


def overridable(type_: str, name: str) -> bool:
    """A field a shot may hold its own value for: a real setting of an item or material, never what kind of thing it
    is (a light's kind, a mesh's shape), data an operation writes, or a clay's next-stroke brush."""
    p = F.param(type_, name) if type_ in TYPES else None
    return p is not None and name not in NEVER and p.group not in F.DATA_GROUPS and p.group != "Brush"


def of(shot: dict | None) -> dict:
    return (shot or {}).get(FIELD) or {}


def _laid(item: dict, ov: dict) -> dict:
    own = ov.get(item["id"])
    out = item
    if own:
        out = {**item, **own}
        if item.get("keys"):
            out["keys"] = [k for k in item["keys"] if k.get("prop") not in own]
    if item.get("children"):
        out = {**out, "children": [_laid(c, ov) for c in item["children"]]}
    return out


def lay(data: dict, shot_id: str) -> dict:
    """The document as the shot `shot_id` sees it: its overrides laid on, collections in light linking expanded. The
    caller's document is never changed (touched items and the lists holding them are copies)."""
    shot = next((s for s in data.get("shots", []) if s.get("id") == shot_id), None)
    ov = of(shot)
    linked = COL.has_links(data)
    if not ov and not linked:
        return data
    out = {**data, "items": [_laid(i, ov) for i in data.get("items", [])]} if ov else dict(data)
    if ov and any(m["id"] in ov for m in data.get("materials", [])):
        out["materials"] = [{**m, **ov[m["id"]]} if m["id"] in ov else m for m in data["materials"]]
    if linked:
        out["items"] = COL.expand_links(out, out["items"])
    return out


def shown(data: dict, shot_id: str, item: dict) -> dict:
    """One item's values as the shot shows them (the settings panel in "Only this shot")."""
    shot = next((s for s in data.get("shots", []) if s.get("id") == shot_id), None)
    own = of(shot).get(item.get("id"))
    if not own:
        return item
    out = {**item, **own}
    if item.get("keys"):
        out["keys"] = [k for k in item["keys"] if k.get("prop") not in own]
    return out


def problems(shot: dict, by_id: dict) -> list[str]:
    """The document check's part: an override is a mapping of real setting names (a gone item is allowed: skipped)."""
    out = []
    ov = shot.get(FIELD)
    if ov is None:
        return out
    if not isinstance(ov, dict):
        return [f'shot {shot["id"]}.{FIELD}: is {type(ov).__name__}; it is {{item id: {{field: value}}}}']
    for id_, values in ov.items():
        it = by_id.get(id_)
        if not isinstance(values, dict):
            out.append(f'shot {shot["id"]}.{FIELD}.{id_}: is {type(values).__name__}; it is {{field: value}}')
        elif it is not None:
            out += [f'shot {shot["id"]}: {id_}.{k} is not a setting a shot can change on a {it["type"]}'
                    for k in values if not overridable(it["type"], k)]
    return out
