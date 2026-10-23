"""The inspector's Fill row: one paint (kit PaintField: a swatch and "Linear · 3 stops"; a click opens the picker) in
place of the colour row and the fill's own fields (on / off, type, gradient angle and centre: the picker and the canvas
handles set those). Not a stored field: the row is rostrum2d.fill_paint.of(item) and an edit is the agents'
`layer.fill`. The engine draws any number of stops anywhere in 0..1, see-through too (E8).
The row's key mark (`anim_state`, `animate_calls`): a solid fill is its colour's; a gradient's is its stops' colours (and an
inner stop's position): keyed when any is, a click keys them all at the playhead or stops them all. The picker shows the
paint at the playhead and an edit keys what is animated there (layer.fill `at`). No Qt."""
from __future__ import annotations

from rostrum2d import fill_fields, fill_paint
from rostrum2d.evaluate import resolve
from rostrum_core.keys import keys_of

from . import route

ROW = "paint"
HIDDEN = {"filled", *fill_fields.NAMES}
OPTIONS = {"maxStops": 32, "stopOpacity": True}         # the engine draws any number of stops, see-through too (E8)


def rows(rows: list[dict], item: dict | None, t: float = 0.0, fps: float = 30.0) -> list[dict]:
    if not item or item.get("type") not in fill_fields.OWNERS:
        return rows
    colour = fill_paint.colour_field(item)
    types = (["none"] if item["type"] != "text" else []) + list(fill_fields.TYPES if item["type"] != "text" else fill_fields.TEXT_TYPES)
    out = []
    for r in rows:
        if r["row"] == "param" and r["id"] == colour:
            out.append({**r, "id": ROW, "label": "Fill" if colour == "fill" else "Colour", "type": "paint", "valid": True,
                        "value": fill_paint.of(_at(item, t)), "options": {**OPTIONS, "types": types},
                        "anim": anim_state(item, t, fps), "default": None})
        elif not (r["row"] == "param" and r["id"] in HIDDEN) and not (r.get("members") and set(r["members"]) <= HIDDEN):
            out.append(r)                                # (a fold of only the fill's own fields goes with them)
    return out


def call(item_id: str, paint: dict, t: float = 0.0) -> dict:
    args = {"type": paint["type"], "at": t}
    if paint["type"] == "solid" and paint.get("color"):
        args["color"] = paint["color"]
    if paint["type"] in fill_fields.GRADIENTS:
        args["stops"] = [f'{s["color"]} {round(s["at"] * 100, 2)} {round(s.get("opacity", 1.0) * 100, 2)}'
                         for s in sorted(paint.get("stops", []), key=lambda s: s["at"])] or None
        args.update({k: paint[k] for k in ("angle", "cx", "cy") if paint.get(k) is not None})
    return {"op": "layer.fill", "target": [item_id], "args": {k: v for k, v in args.items() if v is not None}}


def _at(item: dict, t: float) -> dict:
    """The layer with its colour and stops as they are at `t` (its own seconds)."""
    return {**item, **resolve(item, t), "stops": [{**s, **resolve(s, t)} for s in item.get("stops", [])]}


def _parts(item: dict) -> list[tuple[dict, str]]:
    """(item, field) pairs the mark keys: the solid colour, or each stop's colour and position."""
    kind = fill_paint.kind_of(item)
    if kind == "solid":
        return [(item, fill_paint.colour_field(item))]
    if kind not in fill_fields.GRADIENTS:
        return []
    stops = fill_paint.stops_of(item)
    return [(s, "color") for s in stops] + [(s, "at") for s in stops]


def anim_state(item: dict, t: float, fps: float) -> str:
    states = {route.anim_state(it, f, t, fps) for it, f in _parts(item)} - {""}
    return next((s for s in ("onkey", "keyed", "still") if s in states), "")


def animate_calls(item: dict, t: float) -> tuple[list[dict], str]:
    parts = _parts(item)
    if any(keys_of(it, f) for it, f in parts):
        return [{"op": "key.clear", "target": [it["id"]], "args": {"prop": f, "at": t}} for it, f in parts if keys_of(it, f)],             "Stop animating Fill"
    calls = []
    for it, f in parts:
        c = route.value_call(it, f, resolve(it, t).get(f, it.get(f)), t)
        c["op"] = "key.add"
        c["args"]["t"] = c["args"].pop("at")
        calls.append(c)
    return calls, "Animate Fill"
