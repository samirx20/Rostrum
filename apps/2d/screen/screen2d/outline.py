"""The timeline's rows, which are also the layers list, from one composition. No Qt.

Layers top of the stack first (as they look: the last drawn is on top). Each layer row carries its bar (`start`, `end`
in composition seconds, clamped to the composition; `startMarker` / `endMarker`: the shared marker an end is tied to,
or ""), all its keys as one summary line (its effects' and masks' too) and, for a drawing, its frames (`frames`: where
each starts and how long it is held). An open layer shows one row per animated field, then its effects and masks
(their keys), then its own layers, indented. One fold state: a layer with layers inside (a group) is open unless
folded; any other layer is closed unless opened (`flipped`: the ids whose default was turned round).
"""
from __future__ import annotations

from rostrum2d import fields as F
from rostrum2d.names import display_name
from rostrum2d.retime import END, FIELD
from rostrum_core.keys import animated, keys_of, marked

from . import framing


def label_of(item: dict, owner: dict | None = None) -> str:
    """A key reads as its layer, field and time ("title · Opacity at 0.9 s"); everything else by its name, or its
    id while the name is only the type's ("Text")."""
    if item.get("type") == "key" and owner is not None:
        p = F.param(owner["type"], item["prop"])
        return f"{label_of(owner)} · {p.label if p else item['prop']} at {marked.label(item['t'])}"
    return display_name(item)


def _owned(layer: dict) -> list[dict]:
    return [*layer.get("effects", []), *layer.get("masks", [])]


def _fields(layer: dict) -> list[tuple[dict, str]]:
    """(owner, prop) for every animated field of a layer and of its effects and masks, in field-table order."""
    out = []
    for owner in [layer, *_owned(layer)]:
        props = animated(owner)
        out += [(owner, p.name) for p in F.FIELDS[owner["type"]] if p.name in props]
    return out


def _keys(owner: dict, prop: str) -> list[dict]:
    """A field's keys for the timeline; a key on a shared marker (placed by retime.placed) carries its words."""
    return [{"id": k["id"], "t": k["t"], **({"marker": marked.label(k["ref"])} if "ref" in k else {})}
            for k in keys_of(owner, prop)]


def _row(kind: str, owner: dict, depth: int, label: str, keys: list, prop: str = "") -> dict:
    """kind: "layer", "field" (one animated setting of the layer) or "owned" (an effect or mask)."""
    return {"row": kind, "id": owner["id"] if kind != "field" else f"{owner['id']}.{prop}", "owner": owner["id"],
            "prop": prop, "label": label, "kind": owner["type"], "shape": owner.get("shape", "") if kind == "layer" else "",
            "depth": depth, "owned": kind != "layer", "fold": "", "keys": keys, "frames": [], "bar": False}


def rows(comp: dict, flipped: set[str]) -> list[dict]:
    """`comp` as placed (every time in composition seconds): bridge.placed()."""
    out: list[dict] = []
    duration = comp["duration"]

    def walk(layers, depth):
        for lay in reversed(layers):
            fields = _fields(lay)
            summary = sorted((k for o, p in fields for k in _keys(o, p)), key=lambda k: k["t"])
            inside = bool(fields or _owned(lay) or lay.get("layers"))
            is_open = inside and (bool(lay.get("layers")) != (lay["id"] in flipped))
            row = _row("layer", lay, depth, label_of(lay), summary)
            if F.param(lay["type"], "start") is not None:   # a camera, a shape …: when it shows, as a bar
                row.update(bar=True, start=min(max(lay.get("start", 0.0), 0.0), duration),
                           end=min(max(lay.get("end", duration), 0.0), duration),
                           startMarker=lay.get(FIELD) or "", endMarker=lay.get(END) or "")
            row.update(locked=bool(lay.get("locked")), hidden=bool(lay.get("hidden")))
            row["fold"] = "" if not inside else "open" if is_open else "closed"
            if lay["type"] == "drawing":
                row["frames"] = framing.marks(lay, comp["fps"], duration)
            out.append(row)
            if not is_open:
                continue
            out.extend(_row("field", lay, depth + 1, F.param(lay["type"], p).label, _keys(lay, p), p)
                       for o, p in fields if o is lay)
            for o in _owned(lay):
                keys = sorted((k for p in animated(o) for k in _keys(o, p)), key=lambda k: k["t"])
                out.append(_row("owned", o, depth + 1, label_of(o), keys))
            walk(lay.get("layers", []), depth + 1)

    walk(comp.get("layers", []), 0)
    return out
