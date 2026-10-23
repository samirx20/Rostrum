"""A layer's fill as one paint (fill_fields.py): read it (`of`), hand it to the engine (`lower`) and bring an old
file's gradient effect into the fill (`upgrade`).

    {"type": "none" | "solid" | "linear" | "radial" | "angular", "color": "#rrggbb",
     "stops": [{"at": 0..1, "color": "#rrggbb", "opacity": 0..1}, …], "angle": °, "cx": 0..1, "cy": 0..1}

The engine draws a gradient as its `gradient` effect (two colours at 0 % and 100 %, an optional middle one), so a
gradient fill goes to it as that effect, its stop keys as the effect's colour keys. What the engine can't draw yet (more
than three stops, an end stop off 0 % / 100 %, a see-through stop) is refused in words, never drawn wrong (ENGINE_REQUEST
in this file: the engine's next step).
"""
from __future__ import annotations

import copy

from rostrum_core.keys import keys_of

from . import fill_fields as FF

STYLE = {"linear": "linear", "radial": "radial", "angular": "conic"}       # fill type -> the engine effect's style
AS_FILL = {v: k for k, v in STYLE.items()}
LAYER_GEOMETRY = {"gradAngle": "angle", "gradX": "cx", "gradY": "cy"}      # layer field -> effect field
ENGINE_REQUEST = ("the drawing engine draws a gradient fill of up to 3 stops, the first at 0 %, the last at 100 %, "
                  "all fully opaque, until it learns stop lists")


def colour_field(item: dict) -> str:
    return "color" if item["type"] == "text" else "fill"


def kind_of(item: dict) -> str:
    """The fill's type; "none" when a shape or path isn't filled."""
    if item["type"] != "text" and not item.get("filled", True):
        return "none"
    return item.get("fillType", "solid")


def stops_of(item: dict) -> list[dict]:
    return sorted(item.get("stops", []), key=lambda s: s.get("at", 0.0))


def of(item: dict) -> dict:
    """The paint as one value (the inspector's Fill row, the picker, inspect)."""
    return {"type": kind_of(item), "color": item.get(colour_field(item), "#ffffff"),
            "stops": [{"at": s.get("at", 0.0), "color": s.get("color", "#ffffff"), "opacity": s.get("opacity", 1.0)}
                      for s in stops_of(item)],
            "angle": item.get("gradAngle", 90.0), "cx": item.get("gradX", 0.5), "cy": item.get("gradY", 0.5)}


def _renamed(keys: list[dict], prop: str) -> list[dict]:
    return [{**k, "prop": prop} for k in keys]


def lower(item: dict) -> dict | None:
    """The gradient effect item the engine draws for this layer's gradient fill (None: not a gradient). Raises
    ValueError, in words, for a gradient the engine can't draw yet."""
    kind = kind_of(item)
    if kind not in FF.GRADIENTS:
        return None
    stops = stops_of(item)
    why = _undrawable(stops)
    if why:
        raise ValueError(f'{item["id"]}: its {kind} fill {why}; {ENGINE_REQUEST}')
    first, last = stops[0], stops[-1]
    fx = {"id": f'{item["id"]}.fill', "type": "gradient", "style": STYLE[kind], "angle": item.get("gradAngle", 90.0),
          "cx": item.get("gradX", 0.5), "cy": item.get("gradY", 0.5), "color1": first.get("color", "#ffffff"),
          "color2": last.get("color", "#ffffff"), "middle": len(stops) == 3,
          "keys": _renamed(keys_of(first, "color"), "color1") + _renamed(keys_of(last, "color"), "color2")}
    for field, prop in LAYER_GEOMETRY.items():
        fx["keys"] += _renamed(keys_of(item, field), prop)
    if len(stops) == 3:
        mid = stops[1]
        fx.update(color3=mid.get("color", "#ffffff"), mid=mid.get("at", 0.5))
        fx["keys"] += _renamed(keys_of(mid, "color"), "color3") + _renamed(keys_of(mid, "at"), "mid")
    return fx


def _undrawable(stops: list[dict]) -> str:
    if len(stops) < 2:
        return f"has {len(stops)} stop{'s' * (len(stops) != 1)} (a gradient needs 2)"
    if len(stops) > 3:
        return f"has {len(stops)} stops"
    if stops[0].get("at", 0.0) != 0.0 or stops[-1].get("at", 0.0) != 1.0 or keys_of(stops[0], "at") or keys_of(stops[-1], "at"):
        return "has an end stop away from 0 % or 100 %"
    if any(s.get("opacity", 1.0) != 1.0 or keys_of(s, "opacity") for s in stops):
        return "has a see-through stop"
    return ""


# ── old files: a gradient effect becomes the fill (one way, on open: rostrum_core DocKind.upgrade) ──────────────────

def _movable(layer: dict, fx: dict) -> bool:
    """A gradient effect that is the fill: the layer's first one that is drawn, on a filled shape / path or a text,
    with no expression of its own (an expression stays where it was written)."""
    if layer["type"] not in FF.OWNERS or fx.get("hidden") or fx.get("exprs"):
        return False
    shown = [e for e in layer.get("effects", []) if e["type"] == "gradient" and not e.get("hidden")]
    return bool(shown) and shown[0] is fx and kind_of(layer) == "solid"


def _move(layer: dict, fx: dict, new_id):
    keys = fx.get("keys", [])
    take = lambda prop: [{**k, "prop": p} for k in keys if k["prop"] == prop for p in [_TARGET[prop][1]]]  # noqa: E731
    stops = [(fx.get("color1", "#ffffff"), 0.0, "color1", None), (fx.get("color2", "#808080"), 1.0, "color2", None)]
    if fx.get("middle"):
        stops.insert(1, (fx.get("color3", "#c0c0c0"), fx.get("mid", 0.5), "color3", "mid"))
    layer["stops"] = [{"id": new_id("stop"), "type": "stop", "name": "Gradient stop", "at": at, "color": colour,
                       "opacity": 1.0, "keys": take(c_prop) + (take(at_prop) if at_prop else [])}
                      for colour, at, c_prop, at_prop in stops]
    layer.update(fillType=AS_FILL.get(fx.get("style", "linear"), "linear"), gradAngle=fx.get("angle", 180.0),
                 gradX=fx.get("cx", 0.5), gradY=fx.get("cy", 0.5))
    layer.setdefault("keys", []).extend(k for prop in ("angle", "cx", "cy") for k in take(prop))
    layer["effects"] = [e for e in layer["effects"] if e is not fx]


_TARGET = {"color1": ("stop", "color"), "color2": ("stop", "color"), "color3": ("stop", "color"), "mid": ("stop", "at"),
           "angle": ("layer", "gradAngle"), "cx": ("layer", "gradX"), "cy": ("layer", "gradY")}


def upgrade(data: dict, lists: dict):
    """(new data, label) with every layer's gradient effect moved into its fill, or None when there is none."""
    from rostrum_core.tree import index, walk
    work = copy.deepcopy(data)
    ids = set(index(work, lists))
    moved = 0

    def new_id(type_):
        n = 1
        while f"{type_}_{n}" in ids:
            n += 1
        ids.add(f"{type_}_{n}")
        return f"{type_}_{n}"
    for layer in list(walk(work, lists)):
        fx = next((e for e in layer.get("effects", []) if e.get("type") == "gradient" and not e.get("hidden")), None)
        if fx is not None and _movable(layer, fx):
            _move(layer, fx, new_id)
            moved += 1
    return (work, f"Gradient effect{'s' * (moved > 1)} moved into the fill") if moved else None
