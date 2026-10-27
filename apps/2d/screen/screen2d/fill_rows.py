"""The inspector's Fill row: one paint (kit PaintField: a swatch and "Linear · 3 stops"; a click opens the picker) in
place of the colour row and the fill's own fields (on / off, type, gradient angle and centre: the picker and the canvas
handles set those; a picture's file, fit and scale too: the picker shows them once). Not a stored field: the row is rostrum2d.fill_paint.of(item) and an edit is the agents'
`layer.fill`. The engine draws any number of stops anywhere in 0..1, see-through too (E8).
The row's key mark (`anim_state`, `animate_calls`): a solid fill is its colour's; a gradient's is its stops' colours (and an
inner stop's position): keyed when any is; a click keys them all at the playhead, or deletes their keys at the playhead
when there are some (route.py's key mark); Stop animating stops them all. The picker shows the
paint at the playhead and an edit keys what is animated there (layer.fill `at`).
A picture or painted fill's per-element fields (Scale, Offset, Rotation, Drift, Colour under it, Blend, Opacity, Start at
drawing) stay the panel's own rows, evaluated like any (valid when, key marks), marked `inside` the Fill row: the picker
draws them under its Fit, the panel never does (the kit's InspectorRow). Fit goes with the paint. The picker's Painted
kind shows the scene's paintings as tiles (`options.sources`) and "+ New painting" (`options.add`: the action
layer:painted_new, one change). No Qt."""
from __future__ import annotations

from rostrum2d import drawing, fill_fields, fill_paint, paintings
from rostrum2d.evaluate import resolve
from rostrum_core.keys import keys_of
from rostrum_gui.route import key_at
from rostrum_gui.rows import matches

from . import route
from .fill_aim import used_by

ROW = "paint"
HIDDEN = {"filled", "fillOpacity", *fill_fields.NAMES, *(p.name for p in fill_fields.PICTURE)}
INSIDE = ("fillScale", "fillOffsetX", "fillOffsetY", "fillRotation", "fillDriftX", "fillDriftY", "fillUnder", "fillBlend",
          "fillOpacity", "fillPhase")                    # drawn in the picker (in fill_fields' order)
WORDS = {"fillScale": "Scale", "fillOpacity": "Opacity"}   # the picker's words: no "Picture scale" on a painting
OPTIONS = {"maxStops": 32, "stopOpacity": True}         # the engine draws any number of stops, see-through too (E8)
NEW = "layer:painted_new"                               # + New painting (actions.py)
PAINT_IT = "layer:paint_fill"                           # Paint it: the Brush on the painted fill (actions.py)
WORDS_OF = [{"label": p.label, "group": p.group, "help": p.help or ""}           # what a search reads of the hidden fields
            for p in (*fill_fields.LAYER, *fill_fields.OPACITY, *fill_fields.PICTURE) if p.name in HIDDEN]


def rows(rows: list[dict], item: dict | None, t: float = 0.0, fps: float = 30.0, query: str = "",
         doc: dict | None = None) -> list[dict]:
    if not item or item.get("type") not in fill_fields.OWNERS:
        return rows
    colour = fill_paint.colour_field(item)
    types = (["none"] if item["type"] != "text" else []) + list(fill_fields.TYPES if item["type"] != "text" else fill_fields.TEXT_TYPES)
    out = []
    # The one row stands for the colour and every fill field it hides, so a search for any of them (gradient, angle,
    # direction, picture) finds it, whether or not that field applies now, and a search for anything else (blur) leaves it
    # out. Asked of the fields themselves: the panel's rows no longer hold them (bridge.on_page left them out), so asking
    # the rows found nothing (hand maker row 22: "angle", "gradient" said "No setting matches").
    own = bool(query.strip()) and any(matches(f, query) for f in WORDS_OF)
    raster = "painted" in types
    for r in rows:
        if r["row"] == "param" and r["id"] == colour:
            out.append({**r, "id": ROW, "label": fill_paint.row_label(item), "type": "paint", "valid": r["valid"] or own,
                        "value": value(item, t, doc), "anim": anim_state(item, t, fps), "default": None,
                        "options": {**OPTIONS, "types": types, **({"sources": sources(doc), "add": NEW} if raster else {}),
                                    **paint_it(item, doc)}})
        elif raster and r["row"] == "param" and r["id"] in INSIDE:
            out.append(_inside(r, item))
        elif not (r["row"] == "param" and r["id"] in HIDDEN) and not (r.get("members") and set(r["members"]) <= HIDDEN):
            out.append(r)                                # (a fold of only the fill's own fields goes with them)
    return out


def _inside(r: dict, item: dict) -> dict:
    """A per-element field drawn in the picker: shown while its own valid-when holds (never folded or searched away).
    A colour under it that is none starts, on its "+", from the layer's solid colour."""
    extra = {"options": {"start": item.get("fill", "#ffffff")}} if r["id"] == "fillUnder" else {}
    label = r["label"] if r.get("half") == "first" else WORDS.get(r["id"], r["label"])
    return {**r, **extra, "label": label, "inside": ROW, "valid": bool(r.get("holds", r["valid"]))}


def value(item: dict, t: float, doc: dict | None) -> dict:
    """The paint at `t`; a painted fill adds its painting's name and picture (the swatch shows them, as a style's name)."""
    paint = fill_paint.of(_at(item, t))
    if paint["type"] == "painted":
        found = next((p for p in (doc or {}).get("paintings", []) if p["id"] == paint["painting"]), None)
        paint.update(name=found.get("name", "Painted") if found else "Painted", thumb=picture(found) if found else "")
    elif paint["type"] == "picture":
        paint["thumb"] = paint["picture"]
    return paint


def picture(painting: dict) -> str:
    """The painting's first drawing as a picture file. One not made yet is left to the scene, which makes it off the
    screen's thread (its last one, or a blank one, stands in meanwhile)."""
    frames = drawing.shown_frames(painting)
    return str(drawing.picture(painting, frames[0], later=[])) if frames else ""


def paint_it(item: dict, doc: dict | None) -> dict:
    """A painted fill's Paint it (the action PAINT_IT) and the words beside it: "used by 3 layers"."""
    if item.get("fillType") != "painted" or not doc:
        return {}
    return {"paintIt": PAINT_IT, "paintItNote": used_by(len(paintings.uses(doc, item.get("fillPainting", ""))))}


def sources(doc: dict | None) -> list[dict]:
    """The picker's tiles: each painting of the scene, its name and picture."""
    return [{"value": p["id"], "label": p.get("name", "Painting"), "picture": picture(p)} for p in (doc or {}).get("paintings", [])]


def call(item_id: str, paint: dict, t: float = 0.0) -> dict:
    args = {"type": paint["type"], "at": t}
    if paint["type"] == "solid" and paint.get("color"):
        args["color"] = paint["color"]
        if paint.get("opacity") is not None:            # the picker's opacity slider (a solid fill's own)
            args["opacity"] = round(paint["opacity"], 4)
    if paint["type"] in fill_fields.GRADIENTS:
        args["stops"] = [f'{s["color"]} {round(s["at"] * 100, 2)} {round(s.get("opacity", 1.0) * 100, 2)}'
                         for s in sorted(paint.get("stops", []), key=lambda s: s["at"])] or None
        args.update({k: paint[k] for k in ("angle", "cx", "cy") if paint.get(k) is not None})
    if paint["type"] in ("linear", "radial") and paint.get("span"):     # the canvas handles' length too; "box": the whole shape again
        args["span"] = paint["span"]
        if paint["span"] == "points":
            args.update({k: paint[k] for k in ("x1", "y1", "x2", "y2", "rx", "ry") if paint.get(k) is not None})
    if paint["type"] == "picture":
        args.update(picture=_path(paint.get("picture") or ""), fit=paint.get("fit"))
    if paint["type"] == "painted":
        args.update(painting=paint.get("painting") or None, fit=paint.get("fit"))
    return {"op": "layer.fill", "target": [item_id], "args": {k: v for k, v in args.items() if v is not None}}


def _path(picture: str) -> str | None:
    """The picker's file (the dialog's file:// url, or a path already) as a path."""
    if picture.startswith("file:"):
        from urllib.parse import urlparse
        from urllib.request import url2pathname
        return url2pathname(urlparse(picture).path)
    return picture or None


def _at(item: dict, t: float) -> dict:
    """The layer with its colour and stops as they are at `t` (its own seconds)."""
    return {**item, **resolve(item, t), "stops": [{**s, **resolve(s, t)} for s in item.get("stops", [])]}


def _parts(item: dict) -> list[tuple[dict, str]]:
    """(item, field) pairs the mark keys: the solid colour, or each stop's colour and position."""
    kind = fill_paint.kind_of(item)
    if kind == "solid":
        faded = item.get("fillOpacity", 1.0) != 1.0 or keys_of(item, "fillOpacity")
        return [(item, fill_paint.colour_field(item)), *([(item, "fillOpacity")] if faded else [])]
    if kind not in fill_fields.GRADIENTS:
        return []
    stops = fill_paint.stops_of(item)
    return [(s, "color") for s in stops] + [(s, "at") for s in stops]


def anim_state(item: dict, t: float, fps: float) -> str:
    states = {route.anim_state(it, f, t, fps) for it, f in _parts(item)} - {""}
    return next((s for s in ("onkey", "keyed", "still") if s in states), "")


def animate_calls(item: dict, t: float, fps: float, stop: bool = False) -> tuple[list[dict], str]:
    """The Fill row's key mark, as route.KeyRoute.animate_calls does for one field, over all its parts."""
    parts = _parts(item)
    if stop:
        return [{"op": "key.clear", "target": [it["id"]], "args": {"prop": f, "at": t}} for it, f in parts if keys_of(it, f)],             f"Stop animating {fill_paint.row_label(item)}"
    here = [k for it, f in parts if (k := key_at(keys_of(it, f), t, fps))]
    if here:
        return [{"op": "key.remove", "target": [k["id"] for k in here], "args": {}}], f"Delete {fill_paint.row_label(item)} key at {t:.2f} s"
    calls = []
    for it, f in parts:
        c = route.value_call(it, f, resolve(it, t).get(f, it.get(f)), t)
        c["op"] = "key.add"
        c["args"]["t"] = c["args"].pop("at")
        calls.append(c)
    return calls, f"Key {fill_paint.row_label(item)} at {t:.2f} s" if any(keys_of(it, f) for it, f in parts) else f"Animate {fill_paint.row_label(item)}"
