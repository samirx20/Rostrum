"""Paint mode's rules, no Qt (SPEC §5, mockup 06; paint_mode_qt.py puts them on screen). A brush drag on the viewport
is picked point by point by the engine (`pick` gives the surface's `uv`; on a clay its `local` point and normal);
this turns those answers into one call list: `stroke.add` with the whole path (and the layer first when the item has
none yet), one change, one undo step. On a mesh the path is in canvas pixels, and where it jumps across a cut of the
unfolded surface (a seam) the stroke stops and a new one starts on the far side, still in the same call list. On a
clay it is kept on the surface (`anchors`, `reach`): the clay's surface is unfolded anew with each shape, and the
stroke is laid on it every time (rostrum3d.clay_paint, which splits it at seams the same way).
"""
from __future__ import annotations

import re

from rostrum3d import clay_paint, paint_scene
from rostrum3d.paint_fields import CHANNELS, LAYER
from rostrum_paint.fields import BAR, BRUSH, brush_defaults

SEAM = 0.08            # a step longer than this share of the canvas (and many tips long) crossed a seam
CANVASES = ("mesh", "clay")              # what Paint paints on
GUESS_MPP = 0.001      # metres per brush px on a clay before anything says (a first click on a clay never painted)
CHANNEL = next(p for p in LAYER if p.name == "channel")


def canvas_px(uv, size: int) -> list[float]:
    """A surface (u, v) → canvas pixels (x right, y down: the picture's rows; t counts up)."""
    return [round(uv[0] * size, 2), round((1.0 - uv[1]) * size, 2)]


def crosses_seam(a, b, size: int, tip: float) -> bool:
    d = ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5
    return d > SEAM * size and d > 6 * tip


def split(points: list, size: int, tip: float) -> list[list]:
    """The path's runs: a new run wherever a step crosses a seam."""
    runs: list[list] = []
    for p in points:
        if runs and not crosses_seam(runs[-1][-1], p, size, tip):
            runs[-1].append(p)
        else:
            runs.append([p])
    return runs


def stroke_calls(item: dict, layer: str, points: list, brush: dict, new_layer: dict | None,
                 anchors: list | None = None, reach: float = 0.0) -> list[dict]:
    """The calls for one finished drag: the new layer (when asked) and one stroke.add per run (a clay: one stroke
    with its `anchors` and `reach`, laid on the surface whenever its picture is made)."""
    calls = []
    if new_layer is not None:
        calls.append({"op": "paint.add", "target": [item["id"]], "args": new_layer})
    if item.get("type") == "clay":
        calls.append({"op": "stroke.add", "target": [layer], "args": {**brush, "anchors": anchors, "reach": reach}})
        return calls
    for run in split(points, item.get("paintSize", 2048), float(brush.get("size", 12))):
        pts = run if len(run) > 1 else [run[0], [run[0][0] + 0.01, run[0][1], *run[0][2:]]]   # a click: one dab
        calls.append({"op": "stroke.add", "target": [layer], "args": {**brush, "points": pts}})
    return calls


def layer_rows(item: dict, active: str) -> list[dict]:
    """The Paint layers list, top first (as a panel lists layers): name, what it paints, visible, the active one."""
    return [{"id": p["id"], "name": p.get("name", p["id"]), "channel": p.get("channel", "colour"),
             "paints": CHANNELS[p.get("channel", "colour")][0], "visible": p.get("visible", True),
             "active": p["id"] == active} for p in reversed(item.get("paints", []))]


def new_layer_args(item: dict, channel: str, skip: str = "") -> dict:
    """A layer named after what it paints and how many of those there are: "Roughness 2"."""
    n = sum(1 for p in item.get("paints", []) if p.get("channel", "colour") == channel and p["id"] != skip) + 1
    return {"name": f"{CHANNELS[channel][0]} {n}", "channel": channel}


AUTO_NAME = re.compile(r"^(" + "|".join([v[0] for v in CHANNELS.values()] + ["Height"]) + r") \d+$")   # Height: Relief's old name


def channel_args(item: dict, layer: dict, channel: str) -> dict:
    """Paints → `channel`; a layer still named as made ("Colour 1") is named after its new channel too, a name the
    person gave stays."""
    if AUTO_NAME.match(layer.get("name", "")):
        return new_layer_args(item, channel, skip=layer["id"])
    return {"channel": channel}


def channels() -> list[dict]:
    return CHANNEL.choices()


BAR_PARAMS = [next(p for p in BRUSH if p.name == n) for n in BAR]      # the Brush group: tip, size, colour, opacity


def start_brush() -> dict:
    """The brush a session starts with: the kit's defaults, a size that reads on a 2048 picture."""
    return {**{k: v for k, v in brush_defaults().items() if k in BAR}, "size": 24.0, "color": "#ffffff"}


def clay_mpp(scene: dict, item_id: str, anchor: list) -> float | None:
    """Metres per canvas px of the clay's unfolded surface at `anchor` (its local point and normal), or None while the
    clay has no surface made yet (never painted, or a new shape the engine hasn't unfolded)."""
    f = paint_scene.surface_of(scene, item_id)
    return clay_paint.metres_per_px(clay_paint.read(f), anchor[:3], anchor[3:6]) if f else None


def clay_rest_normal(scene: dict, item_id: str, rest: list, posed_normal: list) -> list:
    """The rest surface's normal at `rest` (a spot picked on a posed clay, carried to its rest shape); while the clay
    has no unfolded surface yet, the drawn (posed) normal: the stroke's point is on the surface, so only the side it
    faces is read from it."""
    f = paint_scene.surface_of(scene, item_id)
    return clay_paint.rest_normal(clay_paint.read(f), rest) if f else list(posed_normal)


def clay_reach(size_px: float, mpp_canvas: float | None, mpp_screen: float | None) -> float:
    """A clay stroke's reach (brush radius, metres): the brush size (canvas px across) on the surface where it landed;
    with no surface yet, the brush's px are the screen's there."""
    return round(max(1e-5, size_px / 2 * (mpp_canvas or mpp_screen or GUESS_MPP)), 6)


# --- Stamp (an "alpha"): on a Relief layer a click lays one whole picture (rostrum3d.ops_paint_stamp, paint.stamp)
HOWS = [{"value": "stroke", "label": "Brush"}, {"value": "stamp", "label": "Stamp"}]
STAMP_CHANNEL = "height"                 # Stamp is offered while the active layer paints Relief


def start_stamp() -> dict:
    """The stamp's own settings (the size is the brush's): the first built-in tip picture, half depth, no turn."""
    from rostrum3d.ops_paint_stamp import DEPTH, TURN
    first = next(p for p in BRUSH if p.name == "texture").choices()
    return {"texture": next((c["value"] for c in first if c["value"] != "none"), "none"),
            "depth": DEPTH.default, "turn": TURN.default}


def stamp_calls(item: dict, layer: str, stamp: dict, size_px: float, anchors: list, points: list,
                reach: float) -> list[dict]:
    """One click's stamp as one call: on a clay at its first anchor (the stamp's width 2 × reach, metres), on a mesh
    at its first canvas point (the brush size, px)."""
    args = {"picture": stamp["texture"], "depth": stamp["depth"], "turn": stamp["turn"], "layer": layer}
    if item.get("type") == "clay":
        args.update(at=list(anchors[0][:6]), size=round(2 * reach, 6))
    else:
        args.update(point=list(points[0][:2]), size=float(size_px))
    return [{"op": "paint.stamp", "target": [item["id"]], "args": args}]


def view_stamp_calls(items: list[str], paint_item: str, active: str, stamp: dict, size_px: float,
                     view: dict) -> list[dict]:
    """A Stamp click From the view: one paint.stamp per item under it (the painted item on its active layer; another
    on its top Relief layer, made when it has none), at the click's px of that view (size in screen px)."""
    cam = {k: view[k] for k in ("eye", "target", "fov", "frame", "width", "height")}
    base = {"picture": stamp["texture"], "depth": stamp["depth"], "turn": stamp["turn"], "size": float(size_px),
            "viewPoint": list(view["points"][0][:2]), **cam}
    return [{"op": "paint.stamp", "target": [i], "args": {**base, **({"layer": active} if i == paint_item and active
                                                                       else {})}} for i in items]


# --- From the view (brief 21b): the drag is stored as drawn (screen points of the view it was drawn in) on each
# paintable item it crosses; the canvas lays it when it is made (rostrum3d.paint_view), so it stays editable.
WHERE = [{"value": "surface", "label": "On the surface"}, {"value": "view", "label": "From the view"}]


def view_pose(eye, target, fov, frame: int, width: int, height: int) -> dict:
    """A stroke's `view` without its points: the camera it was drawn through and the picture's size (device px)."""
    return {"eye": [round(v, 6) for v in eye], "target": [round(v, 6) for v in target], "fov": round(fov, 4),
            "frame": int(frame), "width": int(width), "height": int(height)}


def crossed(item_at, points: list) -> list[str]:
    """The items under the drawn path, in the order it reaches them (`item_at(x, y)` -> item id or "")."""
    out: list[str] = []
    for x, y, *_ in points:
        it = item_at(x, y)
        if it and it not in out:
            out.append(it)
    return out


def view_calls(doc, items: list[str], paint_item: str, active: str, channel: str, brush: dict, view: dict,
               taken=()) -> list[dict]:
    """One drawn stroke From the view as one call list: on every paintable item it crosses, a stroke.add with `view`
    (the item being painted on its active layer; any other on its top layer of the same channel, made when it has
    none; a mesh with no unfolded surface is unfolded first)."""
    calls, used = [], set(taken)

    def fresh():
        n = next(n for n in range(1, 10**6) if not doc.has(f"paint_{n}") and f"paint_{n}" not in used)
        used.add(f"paint_{n}")
        return f"paint_{n}"
    for iid in items:
        it = doc.item(iid)
        if it.get("type") not in CANVASES:
            continue
        if it["type"] == "mesh" and not it.get("uvs"):
            calls.append({"op": "mesh.unfold", "target": [iid], "args": {}})
        layer = active if iid == paint_item and active else next(
            (p["id"] for p in reversed(it.get("paints", [])) if p.get("channel", "colour") == channel), "")
        if not layer:
            layer = fresh()
            calls.append({"op": "paint.add", "target": [iid], "args": {**new_layer_args(it, channel), "id": layer}})
        calls.append({"op": "stroke.add", "target": [layer], "args": {**brush, "view": view}})
    return calls
