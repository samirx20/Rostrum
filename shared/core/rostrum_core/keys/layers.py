"""Animation layers: a stack of moves over the Base, each with a weight (a breathing layer over a walk).

    doc ─ animLayers ─ animLayer {id, type, name, weight 0..1, mode "add" | "replace", on} ─ keys (its weight's)

The stack is read bottom first (the list's order). A key belongs to a layer by `layer: <id>` and still lives on the
item it moves; a key without one is the Base, so `keys_of` (evaluate.py) reads only the Base and every older reader
keeps working. A layer's own `weight` can have keys (prop "weight" on the layer), so a layer can fade in.

The value of a field at t (`value`): the Base (its keys, else the still value), then each layer that is on and has
keys for that field, in order:
- add: value + weight × the layer's curve (its keys hold offsets: 0 = no change). Numbers only.
- replace: the value moved toward the layer's curve by weight (1 = the layer's value). Numbers and colours.
A toggle or a shape is never layered: it reads its Base. A file without layers reads exactly as before.

Writing: `key_for` is the one rule for the key a layer needs so the field shows a value (the window's route, K,
the pose ops); `curve_now` is what K keys on a layer (the picture doesn't change).
"""
from __future__ import annotations

from collections.abc import Callable

from .evaluate import keys_of, mix_color, track_value
from .marked import order

LIST, TYPE, FIELD = "animLayers", "animLayer", "layer"     # the doc's list, a layer's type, a key's field
MODES = ("add", "replace")
LISTS = {"doc": [LIST], TYPE: ["keys"]}
HOLDS = {LIST: (TYPE,)}


def with_lists(lists: dict) -> dict:
    """An app's LISTS with the layer stack added (doc › animLayers, a layer › its weight keys)."""
    out = {k: list(v) for k, v in lists.items()}
    for k, v in LISTS.items():
        out[k] = [*out.get(k, []), *(x for x in v if x not in out.get(k, []))]
    return out


def stack_of(doc: dict) -> list[dict]:
    """The document's layers, bottom first ([] for a file without any)."""
    return list(doc.get(LIST) or [])


def layer_keys(owner: dict, prop: str, layer: str) -> list[dict]:
    """One layer's keys of a field, by time."""
    return sorted((k for k in owner.get("keys", []) if k.get("prop") == prop and k.get(FIELD) == layer),
                  key=lambda k: order(k["t"]))


def weight_at(layer: dict, t: float) -> float:
    keys = [k for k in layer.get("keys", []) if k.get("prop") == "weight"]
    w = track_value(sorted(keys, key=lambda k: k["t"]), t) if keys else layer.get("weight", 1.0)
    return min(1.0, max(0.0, float(w)))


def _number(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def mixed(value, layer_value, weight: float, mode: str):
    """One layer laid over `value`."""
    if mode == "add" and _number(value) and _number(layer_value):
        return value + weight * layer_value
    if mode == "replace" and _number(value) and _number(layer_value):
        return value + (layer_value - value) * weight
    if mode == "replace" and isinstance(value, str) and isinstance(layer_value, str) and value.startswith("#"):
        return mix_color(value, layer_value, weight)
    return value                                             # a toggle, a shape, a colour under add: the Base


def value(owner: dict, prop: str, t: float, stack: list[dict], base, read: Callable = track_value):
    """The field's value at t with the stack laid over `base` (the Base's value now: keys or still). `read(keys, t)`
    is the app's reader of a sorted key list (a toggle's on / off reader in 3D)."""
    if isinstance(base, bool):
        return base
    for layer in stack:
        if not layer.get("on", True) or not (keys := layer_keys(owner, prop, layer["id"])):
            continue
        if (w := weight_at(layer, t)) > 0:
            base = mixed(base, read(keys, t), w, layer.get("mode", "add"))
    return base


def layered(owner: dict) -> set[str]:
    """The fields that have keys on some layer."""
    return {k["prop"] for k in owner.get("keys", []) if k.get(FIELD)}


def base_at(owner: dict, prop: str, t: float, still=None):
    """The Base's value of a field at t: its Base keys, else the still value (`still` when the item has none)."""
    keys = keys_of(owner, prop)
    return track_value(keys, t) if keys else owner.get(prop, still)


def shown_at(owner: dict, prop: str, t: float, stack: list[dict], still=None):
    """The value a field shows at t: the Base with the stack laid over it (what is on screen)."""
    return value(owner, prop, t, stack, base_at(owner, prop, t, still))


def key_for(owner: dict, prop: str, t: float, stack: list[dict], layer_id: str, v, base=None):
    """The value a key on layer `layer_id` at t needs so the field shows `v` (a person's drag, a pose, K): the layer's
    curve now + what is missing, over its weight (add: an offset, replace: the value it moves toward). A layer at
    weight 0 or off counts at weight 1, so its key holds what it would show turned up. `v` = the value shown now
    gives the layer's own curve now (K on a layer: add 0 where it has no keys, replace the value as shown). `base`:
    the Base's value now, when the caller read it already (else read here). A non-number keys `v` as given."""
    layer = next((x for x in stack if x["id"] == layer_id), None)
    base = base_at(owner, prop, t) if base is None else base
    if layer is None or not _number(v) or not _number(base):
        return v
    shown = value(owner, prop, t, stack, base)
    mine = layer_keys(owner, prop, layer_id)
    now = track_value(mine, t) if mine else (0.0 if layer.get("mode", "add") == "add" else shown)
    w = weight_at(layer, t) if layer.get("on", True) else 0.0
    return round(now + (v - shown) / (w if w > 0 else 1.0), 6)


def curve_now(owner: dict, prop: str, t: float, stack: list[dict], layer_id: str, base=None):
    """What K keys on a layer: the key that leaves the field showing what it shows now (the layer's own curve now)."""
    base = base_at(owner, prop, t) if base is None else base
    return key_for(owner, prop, t, stack, layer_id, value(owner, prop, t, stack, base), base)


def base_for(owner: dict, prop: str, t: float, stack: list[dict], v, still=None):
    """The Base value that makes the field show `v` with the stack laid over it (a person editing the Base under
    layers: the picture shows what they set). The layers are taken off top first: add subtracts its share, replace
    undoes its pull; a replace layer at full weight hides the Base, so the Base keeps its value. A non-number: `v`."""
    if not _number(v):
        return v
    for layer in reversed(stack):
        if not layer.get("on", True) or not (keys := layer_keys(owner, prop, layer["id"])):
            continue
        w, lv = weight_at(layer, t), track_value(keys, t)
        if w <= 0 or not _number(lv):
            continue
        if layer.get("mode", "add") == "add":
            v = v - w * lv
        elif w < 1:
            v = (v - lv * w) / (1 - w)
        else:
            return base_at(owner, prop, t, still)
    return round(v, 6)
