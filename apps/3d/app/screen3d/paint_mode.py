"""Paint mode's rules, no Qt (SPEC §5, mockup 06; paint_mode_qt.py puts them on screen). A brush drag on the viewport
is picked point by point by the engine (`pick` gives the surface's `uv`); this turns those answers into one call list:
`stroke.add` with the whole path in canvas pixels (and the layer first when the mesh has none yet), one change, one
undo step. Where the path jumps across a cut of the unfolded surface (a seam) the stroke stops and a new one starts
on the far side, still in the same call list.
"""
from __future__ import annotations

import re

from rostrum3d.paint_fields import CHANNELS, LAYER
from rostrum_paint.fields import BAR, BRUSH, brush_defaults

SEAM = 0.08            # a step longer than this share of the canvas (and many tips long) crossed a seam
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


def stroke_calls(item: dict, layer: str, points: list, brush: dict, new_layer: dict | None) -> list[dict]:
    """The calls for one finished drag: the new layer (when asked) and one stroke.add per run."""
    calls = []
    if new_layer is not None:
        calls.append({"op": "paint.add", "target": [item["id"]], "args": new_layer})
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


AUTO_NAME = re.compile(r"^(" + "|".join(v[0] for v in CHANNELS.values()) + r") \d+$")


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
