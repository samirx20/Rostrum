"""The inspector's Fill row: one paint (kit PaintField: a swatch and "Linear · 3 stops"; a click opens the picker) in
place of the colour row and the fill's own fields (on / off, type, gradient angle and centre: the picker and the canvas
handles set those). Not a stored field: the row is rostrum2d.fill_paint.of(item) and an edit is the agents'
`layer.fill`. What the engine can draw today bounds the picker (fill_paint.ENGINE_REQUEST). No Qt."""
from __future__ import annotations

from rostrum2d import fill_fields, fill_paint

ROW = "paint"
HIDDEN = {"filled", *fill_fields.NAMES}
OPTIONS = {"maxStops": 3, "stopOpacity": False}          # the engine's gradient today (fill_paint.ENGINE_REQUEST)


def rows(rows: list[dict], item: dict | None) -> list[dict]:
    if not item or item.get("type") not in fill_fields.OWNERS:
        return rows
    colour = fill_paint.colour_field(item)
    types = (["none"] if item["type"] != "text" else []) + list(fill_fields.TYPES)
    out = []
    for r in rows:
        if r["row"] == "param" and r["id"] == colour:
            out.append({**r, "id": ROW, "label": "Fill" if colour == "fill" else "Colour", "type": "paint", "valid": True,
                        "value": fill_paint.of(item), "options": {**OPTIONS, "types": types}, "anim": "", "default": None})
        elif not (r["row"] == "param" and r["id"] in HIDDEN) and not (r.get("members") and set(r["members"]) <= HIDDEN):
            out.append(r)                                # (a fold of only the fill's own fields goes with them)
    return out


def call(item_id: str, paint: dict) -> dict:
    args = {"type": paint["type"]}
    if paint["type"] == "solid" and paint.get("color"):
        args["color"] = paint["color"]
    if paint["type"] in fill_fields.GRADIENTS:
        args["stops"] = [f'{s["color"]} {round(s["at"] * 100, 2)} {round(s.get("opacity", 1.0) * 100, 2)}'
                         for s in sorted(paint.get("stops", []), key=lambda s: s["at"])] or None
        args.update({k: paint[k] for k in ("angle", "cx", "cy") if paint.get(k) is not None})
    return {"op": "layer.fill", "target": [item_id], "args": {k: v for k, v in args.items() if v is not None}}
