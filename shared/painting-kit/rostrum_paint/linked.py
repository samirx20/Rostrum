"""Paint layers shared by several canvases (2D: the drawings of one Draw each frame layer, painting spec §2.3.6):
every canvas holds the same paint layers in the same order with the same settings, each with its own strokes.

A paint layer's **key** links its copies: its `layer` field, or its own id when it has none (a layer made before
sharing, or the first copy). The host says which canvases share (`peers`, given to `register`); the kit's paint layer
operations then act on every copy in the same change, and the host's document check keeps them equal (`problems`).
Strokes, fills and Clear paint stay per canvas.
"""
from __future__ import annotations

from copy import deepcopy

SHARED = ("name", "mode", "opacity", "visible", "locked")     # a paint layer's settings, the same in every copy


def key(paint: dict) -> str:
    return paint.get("layer") or paint["id"]


def blank(paint: dict, id_: str) -> dict:
    """An empty copy of a paint layer for another canvas: same key and settings, no strokes."""
    return {**{k: deepcopy(v) for k, v in paint.items() if k != "strokes"}, "id": id_, "layer": key(paint), "strokes": []}


def copies(ctx, paint_id: str, canvas_id: str, peers) -> list[str]:
    """The paint layer and its copies in every canvas sharing with its canvas, this one first."""
    k = key(ctx.item(paint_id))
    out = [paint_id]
    for c in peers(ctx, canvas_id):
        if c != canvas_id:
            out += [p["id"] for p in ctx.item(c)["paints"] if key(p) == k]
    return out


def add(ctx, canvas_id: str, paint: dict, index, peers):
    """Insert a new paint layer into a canvas and an empty copy at the same place in every canvas sharing with it."""
    ctx.insert(canvas_id, "paints", paint, index)
    for c in peers(ctx, canvas_id):
        if c != canvas_id:
            ctx.insert(c, "paints", blank(paint, ctx.new_id("paint")), index)


def problems(owner_id: str, canvases: list[dict]) -> list[str]:
    """What breaks sharing between these canvases (keys, order or settings differ), in plain words."""
    if len(canvases) < 2:
        return []
    want = [(key(p), {k: p.get(k) for k in SHARED}) for p in canvases[0].get("paints", [])]
    out = []
    for c in canvases[1:]:
        got = [(key(p), {k: p.get(k) for k in SHARED}) for p in c.get("paints", [])]
        if got != want:
            out.append(f'{owner_id}: drawing {c["id"]} must have the same paint layers as {canvases[0]["id"]} '
                       f"(same order and settings): {_names(c)} vs {_names(canvases[0])}. Give every drawing's paint the same "
                       f'layer="…" (in a script paint(f"ink{{i}}", layer="ink") in each drawing; in an edit pass layer: "ink" '
                       f"to paint.stroke), and the same number of paint layers in the same order")
            break                      # one is enough to act on; the others differ the same way
    return out


def _names(canvas: dict) -> str:
    return "[" + ", ".join(f'{p.get("name")} ({key(p)})' for p in canvas.get("paints", [])) + "]"
