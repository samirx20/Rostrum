"""A layer's fill as one paint (fill_fields.py): read it (`of`), hand it to the engine (`lower`, `engine_props`) and
bring an old file's gradient effect into the fill (`upgrade`).

    {"type": "none" | "solid" | "linear" | "radial" | "angular" | "picture" | "painted", "color": "#rrggbb", "opacity": 0..1 (solid),
     "stops": [{"at": 0..1, "color": "#rrggbb" | "#rrggbbaa", "opacity": 0..1}, …], "angle": °, "cx": 0..1, "cy": 0..1,
     "span": "box" | "points", "x1", "y1", "x2", "y2", "rx", "ry": 0..1, "picture": path, "painting": id, "fit", "scale",
     "offsetX", "offsetY", "rotation", "driftX", "driftY", "under": colour | None, "blend", "phase"}

The engine draws a gradient as its `gradient` effect with the stops as its `stops` children (any number, anywhere in
0..1, see-through allowed; each stop's colour, position and opacity keyed like any field). A stop colour written
#rrggbbaa (keyed too) goes as written; the engine multiplies its alpha into the stop's opacity. A solid fill's opacity is the layer's own `fillOpacity` (the engine multiplies it into the colour's alpha, keys too). A picture fill is the layer's own
fillPicture / fillFit / fillScale … (fill_fields.PICTURE), read by the engine. A painted fill names a painting of the
document (`fillPainting`, paintings.py), shares Fit, Scale and the per-use fields with a picture fill and goes to the engine
as the node's `fillFrames` (painted_fill.py).
"""
from __future__ import annotations

import copy

from rostrum_core.keys import keys_of

from . import fill_fields as FF

STYLE = {"linear": "linear", "radial": "radial", "angular": "conic"}       # fill type -> the engine effect's style
AS_FILL = {v: k for k, v in STYLE.items()}
LAYER_GEOMETRY = {"gradAngle": "angle", "gradX": "cx", "gradY": "cy"}      # layer field -> effect field
GEOMETRY = {"gradSpan": "span", "gradX1": "x1", "gradY1": "y1", "gradX2": "x2", "gradY2": "y2", "gradRX": "rx", "gradRY": "ry"}


def colour_field(item: dict) -> str:
    return "color" if item["type"] == "text" else "fill"


def kind_of(item: dict) -> str:
    """The fill's type; "none" when a shape or path isn't filled."""
    if item["type"] != "text" and not item.get("filled", True):
        return "none"
    return item.get("fillType", "solid")


def colour_kept(item: dict) -> str | None:
    """The colour a layer keeps under a painting it is given: its solid colour, when it has one and no colour under it
    yet (a blank painting then leaves it looking as it did). None otherwise."""
    if item.get("filled", True) and kind_of(item) == "solid" and item.get("fillUnder") is None:
        return item.get(colour_field(item), "#ffffff")
    return None


def stops_of(item: dict) -> list[dict]:
    return sorted(item.get("stops", []), key=lambda s: s.get("at", 0.0))


def of(item: dict) -> dict:
    """The paint as one value (the inspector's Fill row, the picker, inspect)."""
    return {"type": kind_of(item), "color": item.get(colour_field(item), "#ffffff"), "opacity": item.get("fillOpacity", 1.0),
            "stops": [{"at": s.get("at", 0.0), "color": s.get("color", "#ffffff"), "opacity": s.get("opacity", 1.0)}
                      for s in stops_of(item)],
            "angle": item.get("gradAngle", 90.0), "cx": item.get("gradX", 0.5), "cy": item.get("gradY", 0.5),
            **{short: item.get(name, _default(name)) for name, short in GEOMETRY.items()},
            "picture": item.get("fillPicture", ""), "fit": item.get("fillFit", "fill"), "scale": item.get("fillScale", 1.0),
            "painting": item.get("fillPainting", ""),
            **{short: item.get(name, _default_raster(name)) for name, short in RASTER.items()}}


RASTER = {"fillOffsetX": "offsetX", "fillOffsetY": "offsetY", "fillRotation": "rotation", "fillDriftX": "driftX",
          "fillDriftY": "driftY", "fillUnder": "under", "fillBlend": "blend", "fillPhase": "phase"}


def _default_raster(name: str):
    return next(p.default for p in FF.PICTURE if p.name == name)


def _default(name: str):
    return next(p.default for p in FF.LAYER if p.name == name)


def _renamed(keys: list[dict], prop: str) -> list[dict]:
    return [{**k, "prop": prop} for k in keys]


def lower(item: dict) -> dict | None:
    """The gradient effect item the engine draws for this layer's gradient fill (None: not a gradient). Raises
    ValueError, in words, for a gradient it can't be (fewer than 2 stops)."""
    kind = kind_of(item)
    if kind in ("picture", "painted") and item["type"] == "text":
        raise ValueError(f'{item["id"]}: a text’s letters take no {kind} fill yet; use a colour or a gradient')
    if kind not in FF.GRADIENTS:
        return None
    stops = stops_of(item)
    if len(stops) < 2:
        raise ValueError(f'{item["id"]}: its {kind} fill has {len(stops)} stop{"s" * (len(stops) != 1)} (a gradient needs 2)')
    fx = {"id": f'{item["id"]}.fill', "type": "gradient", "style": STYLE[kind], "angle": item.get("gradAngle", 90.0),
          "cx": item.get("gradX", 0.5), "cy": item.get("gradY", 0.5), "color1": stops[0].get("color", "#ffffff")[:7],
          "color2": stops[-1].get("color", "#ffffff")[:7], "middle": False,
          **{short: item.get(name, _default(name)) for name, short in GEOMETRY.items()},
          "keys": [], "stops": [_stop(item, i, s) for i, s in enumerate(stops)]}
    for field, prop in {**LAYER_GEOMETRY, **GEOMETRY}.items():
        fx["keys"] += _renamed(keys_of(item, field), prop)
    return fx


def _stop(item: dict, i: int, stop: dict) -> dict:
    """One stop as the engine's `stop` item. A #rrggbbaa colour goes as written, keyed ones too: the engine mixes the
    alpha with the colour and multiplies it into the stop's opacity (scene/stage_fill.rs)."""
    return {"id": stop.get("id") or f'{item["id"]}.stop{i}', "type": "stop", "at": stop.get("at", 0.0),
            "color": stop.get("color", "#ffffff"), "opacity": stop.get("opacity", 1.0), "keys": stop.get("keys", [])}


RASTER_KINDS = ("picture", "painted")
NO_COLOUR = "#00000000"                      # the engine reads a fully see-through colour as "no colour under it"


def engine_props(item: dict, props: dict) -> dict:
    """A shape's or path's props as sent: its picture only while the fill type is picture (a painted fill goes as the node's
    `fillFrames`, painted_fill.py), its colour under it only while the fill is a picture or a painting (a colour chosen once
    and then left for a colour fill is kept but not drawn)."""
    kind = kind_of(item)
    if "fillPicture" in props and kind != "picture":
        props["fillPicture"] = ""
    if "fillUnder" in props and (kind not in RASTER_KINDS or props["fillUnder"] is None):
        props["fillUnder"] = NO_COLOUR
    return props


def engine_anim(item: dict, anim: dict) -> dict:
    """The animated fields as sent: a picture or painting's own keys (offset, rotation, colour under it …) only while the
    fill is one; the Python-only ones (fillPainting, fillPhase) and a gradient's (its effect carries them) never."""
    keep = kind_of(item) in RASTER_KINDS
    return {k: v for k, v in anim.items() if k not in FF.NAMES and (keep or k not in FF.PICTURE_NAMES)}


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


def _gradient(layer: dict):
    """The layer's shown gradient effect that can move into its fill, or None."""
    fx = next((e for e in layer.get("effects", []) if e.get("type") == "gradient" and not e.get("hidden")), None)
    return fx if fx is not None and _movable(layer, fx) else None


def upgrade(data: dict, lists: dict):
    """(new data, label) with every layer's gradient effect moved into its fill, or None when there is none."""
    from rostrum_core.tree import index, walk
    if not any(_gradient(layer) for layer in walk(data, lists)):     # nothing to move: no copy of a big document
        return None
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
        fx = _gradient(layer)
        if fx is not None:
            _move(layer, fx, new_id)
            moved += 1
    return (work, f"Gradient effect{'s' * (moved > 1)} moved into the fill") if moved else None
