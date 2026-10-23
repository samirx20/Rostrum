"""The timeline's rows, which are also the layers list, from one composition. No Qt.

Layers top of the stack first (as they look: the last drawn is on top). Each layer row carries its bar (`start`, `end`
in composition seconds, clamped to the composition; `startMarker` / `endMarker`: the shared marker an end is tied to,
or ""), all its keys as one summary line (its effects', masks' and a rig's bones' too) and, for a drawing, its frames
(`frames`: where each starts and how long it is held). An open layer shows one row per animated field, then its
effects and masks (their keys) and a rig's keyed bones and IK chains, then its own layers, indented. One fold state:
a layer with layers inside (a group) is open unless folded; any other layer is closed unless opened (`flipped`: the
ids whose default was turned round).
"""
from __future__ import annotations

from rostrum2d import fields as F
from rostrum2d.anims import PRESET_LABELS, animations
from rostrum2d.drawing import each_frame
from rostrum2d.names import display_name
from rostrum2d.retime import END, FIELD
from rostrum_core.keys import animated, keys_of, marked

from . import eases

from . import framing, key_ghosts


def label_of(item: dict, owner: dict | None = None, beats=None) -> str:
    """A key reads as its layer, field and time ("title · Opacity at 0.9 s", or "… at bar 5" on a beat of the music:
    `beats(t)` gives the beat words of the key's own time, beat_words.py); everything else by its name, or its id while
    the name is only the type's ("Text")."""
    if item.get("type") == "key" and owner is not None:
        p = F.param(owner["type"], item["prop"])
        on = beats(item["t"]) if beats and isinstance(item["t"], (int, float)) else ""
        return f"{label_of(owner)} · {p.label if p else item['prop']} at {on or marked.label(item['t'])}"
    return display_name(item)


def _owned(layer: dict) -> list[dict]:
    """What a layer holds that can carry keys of its own: effects, masks and, on a rig, its bones and IK chains (a
    pose keys the bones, so the rig's bar shows them like any of its keys)."""
    return [*layer.get("effects", []), *layer.get("masks", []), *layer.get("bones", []), *layer.get("iks", [])]


def _fields(layer: dict) -> list[tuple[dict, str]]:
    """(owner, prop) for every animated field of a layer and of its effects and masks, in field-table order."""
    out = []
    for owner in [layer, *_owned(layer)]:
        props = animated(owner)
        out += [(owner, p.name) for p in F.FIELDS[owner["type"]] if p.name in props]
    return out


def _keys(owner: dict, prop: str) -> list[dict]:
    """A field's keys for the timeline; a key on a shared marker (placed by retime.placed) carries its words."""
    return [{"id": k["id"], "ids": [k["id"]], "t": k["t"],
             **({"marker": marked.label(k["ref"])} if "ref" in k else {})} for k in keys_of(owner, prop)]


def _stretches(owner: dict, anims: list[dict]) -> list[dict]:
    """The clickable stretches of these animations (anims.py), as the track draws them: from key to key, with the
    tooltip words ("Position · 1.00 → 2.00 s · Out"). A Hold moves nothing: drawn and picked as nothing."""
    out = []
    for a in anims:
        for s in a["stretches"]:
            if s["ease"] == "hold":
                continue
            end = s["start"] + s["length"]
            words = PRESET_LABELS.get(s["preset"], eases.label_of(s["ease"]))
            out.append({"owner": owner["id"], "ids": s["ids"], "endIds": s["endIds"], "t0": s["start"], "t1": end,
                        "tip": f'{a["label"]} · {s["start"]:.2f} → {end:.2f} s · {words}'})
    return out


def _lines(lay: dict, depth: int, is_open: bool) -> tuple[dict, list[dict]]:
    """(line 0's stretches and the key ids on other lines, the rows of lines 1, 2 …): a layer's animations that overlap
    in time go on lines of their own under it (anims.py packs them), each named by its settings, in grey. Those lines
    are rows under the layer like any other: only while it is open. Folded, its one row holds every key (the later lines' stretches wait for it to be
    opened: drawn on one row they would lie over each other)."""
    anims = animations(lay)
    if not is_open:
        return {"stretches": _stretches(lay, [a for a in anims if a["line"] == 0]), "elsewhere": set()}, []
    rows, elsewhere = [], set()
    for n in range(1, 1 + max((a["line"] for a in anims), default=0)):
        mine = [a for a in anims if a["line"] == n]
        elsewhere |= {k["id"] for a in mine for k in a["keys"]}
        row = _row("field", lay, depth + 1, ", ".join(a["label"] for a in mine),
                   sorted((k for a in mine for p in a["props"] for k in _keys(lay, p)), key=lambda k: k["t"]))
        row.update(id=f'{lay["id"]}#line{n}', line=True, stretches=_stretches(lay, mine))
        rows.append(row)
    return {"stretches": _stretches(lay, [a for a in anims if a["line"] == 0]), "elsewhere": elsewhere}, rows


def _row(kind: str, owner: dict, depth: int, label: str, keys: list, prop: str = "") -> dict:
    """kind: "layer", "field" (one animated setting of the layer) or "owned" (an effect or mask)."""
    return {"row": kind, "id": owner["id"] if kind != "field" else f"{owner['id']}.{prop}", "owner": owner["id"],
            "prop": prop, "label": label, "kind": owner["type"], "shape": owner.get("shape", "") if kind == "layer" else "",
            "depth": depth, "owned": kind != "layer", "fold": "", "keys": keys, "frames": [], "bar": False,
            "ghosts": [], "tails": []}


def _one_per_frame(keys: list[dict], fps: float) -> list[dict]:
    """A layer's summary line: keys of several settings at the same frame are ONE diamond (the first one's id; `ids`:
    every key it stands for, so a click picks them all), never one drawn over another."""
    by_frame: dict[int, dict] = {}
    for k in keys:
        f = round(k["t"] * fps)
        if f in by_frame:
            by_frame[f]["ids"].append(k["id"])
        else:
            by_frame[f] = {**k, "ids": [k["id"]]}
    return list(by_frame.values())


def rows(comp: dict, flipped: set[str], anim_only: set[str] = frozenset()) -> list[dict]:
    """`comp` as placed (every time in composition seconds): bridge.placed(). `anim_only`: layers opened by A, showing
    only their animated settings (theirs, their effects' and masks'), not their own layers."""
    out: list[dict] = []
    duration = comp["duration"]

    def past(pairs) -> dict:
        """The faint marks past the keys (Repeat, Back and forth, a spring's tail) of these (owner, prop) fields."""
        return key_ghosts.marks([(keys_of(o, p), duration) for o, p in pairs], comp["fps"])

    def walk(layers, depth):
        for lay in reversed(layers):
            fields = _fields(lay)
            inside = bool(fields or _owned(lay) or lay.get("layers"))
            only = lay["id"] in anim_only
            is_open = bool(fields) if only else inside and (bool(lay.get("layers")) != (lay["id"] in flipped))
            first, lines = _lines(lay, depth, is_open)
            summary = _one_per_frame(sorted((k for o, p in fields for k in _keys(o, p) if k["id"] not in first["elsewhere"]),
                                            key=lambda k: k["t"]), comp["fps"])
            row = _row("layer", lay, depth, label_of(lay), summary)
            row["stretches"] = first["stretches"]
            row.update(past(fields))
            if F.param(lay["type"], "start") is not None:   # a camera, a shape …: when it shows, as a bar
                row.update(bar=True, start=min(max(lay.get("start", 0.0), 0.0), duration),
                           end=min(max(lay.get("end", duration), 0.0), duration),
                           startMarker=lay.get(FIELD) or "", endMarker=lay.get(END) or "")
            row.update(locked=bool(lay.get("locked")), hidden=bool(lay.get("hidden")))
            row["fold"] = "" if not inside else "open" if is_open else "closed"
            if lay["type"] == "drawing" or (lay.get("frames") and each_frame(lay)):   # drawings, as cells (FrameMarks.qml)
                row["frames"] = framing.marks(lay, comp["fps"], duration)
                row["again"] = framing.again(lay, comp["fps"], duration)    # a looping drawing's later rounds, faint
            out.append(row)
            out.extend(lines)                      # overlapping animations: a line each under the layer (SPEC §9.4)
            if not is_open:
                continue
            out.extend({**_row("field", lay, depth + 1, F.param(lay["type"], p).label, _keys(lay, p), p), **past([(lay, p)])}
                       for o, p in fields if o is lay)
            for o in _owned(lay):
                keys = sorted((k for p in animated(o) for k in _keys(o, p)), key=lambda k: k["t"])
                if keys or not (only or o["type"] in ("bone", "ik")):   # unkeyed bones would only crowd the list
                    out.append({**_row("owned", o, depth + 1, label_of(o), keys), **past((o, p) for p in animated(o))})
            if not only:
                walk(lay.get("layers", []), depth + 1)

    walk(comp.get("layers", []), 0)
    return out
