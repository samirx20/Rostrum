"""Flat washes: look_frame names a painted area that is one even value at frame size (a 1920-wide frame seen ~480 px
wide), where a watercolour wash has a darker dried edge, puddles and grain. A fact with its numbers, never a score.

    facts(comp, t) -> [{drawing, paint, stroke, spread, edge, grain, area, flat}]   every big area on screen at t
    words(rows) -> str                                                               the reply's sentence ("" if none)

Each area is a masked stroke's paint mask (paint.wash lays one per wash) less the masks of the washes laid over it, read
from the drawing's own picture over a light paper (no restamping: the picture is kept on disk once made); areas
covering 1 % of the composition's area or more (canvas px against comp px).
It is measured in blocks of canvas/480 px (what frame size keeps): `spread` is the lightness spread (standard
deviation, % of white) of its inner blocks, `edge` how much darker its rim blocks are than its inside (%), `grain` the
fine spread inside one block (%; what reads as grain up close). Flat: spread under FLAT; "no darker edge" under EDGE.
"""
from __future__ import annotations

import json

import numpy as np

from .. import drawing as D, write_on
from .geometry import comp_size, flatten

SEE = 480          # the frame width the check sees (a 1920 frame looked at small)
FLAT = 3.0         # % lightness spread below which an area reads as one value (measured: a wash with no drying 0 %,
#                    the old 0.4 / 0.3 / 0.5 defaults 2-3 %, which a judge read as flat fills; the defaults now 4-6 %)
EDGE = 2.0         # % darker rim below which no dried edge shows
MIN_SHARE = 0.01   # areas smaller than this share of the composition are not judged
PAPER = 0.92       # the light paper a see-through wash is judged over
LUMA = np.array([0.2126, 0.7152, 0.0722], np.float32)


def _washes(frame: dict) -> list[tuple[str, dict, dict]]:
    """(paint id, stroke, its paint mask) of each masked stroke (paint.wash lays one per wash), painting order."""
    masks = {m["id"]: m for m in frame.get("paintmasks", [])}
    return [(p["id"], s, masks[s["mask"]]) for p in frame.get("paints", []) if p.get("visible", True)
            for s in p.get("strokes", []) if s.get("mask") in masks]


def _blocks(a: np.ndarray, b: int) -> np.ndarray:
    H, W = (a.shape[0] // b) * b, (a.shape[1] // b) * b
    return a[:H, :W].reshape(H // b, b, W // b, b, *a.shape[2:]).swapaxes(1, 2)


def lightness(rgba: np.ndarray, b: int) -> tuple[np.ndarray, np.ndarray]:
    """Each block's mean lightness and its fine spread (std) of a premultiplied HxWx4 picture over the paper: the same
    for every area of one drawing, so worked out once per drawing, not once per area."""
    blk = _blocks((rgba[..., :3] + (1 - rgba[..., 3:4]) * PAPER) @ LUMA, b)
    return blk.mean(axis=(2, 3)), blk.std(axis=(2, 3))


def measure(rgba: np.ndarray | None, own: np.ndarray, b: int, blocks: tuple[np.ndarray, np.ndarray] | None = None) -> dict | None:
    """One area's numbers: `rgba` premultiplied HxWx4, `own` HxW bool (its pixels), `b` block px; `blocks` = lightness(rgba, b)
    when already worked out (then `rgba` is not read)."""
    mean, fine = blocks or lightness(rgba, b)
    ob = _blocks(own, b).all(axis=(2, 3))
    inner = ob.copy()
    inner[1:] &= ob[:-1]; inner[:-1] &= ob[1:]; inner[:, 1:] &= ob[:, :-1]; inner[:, :-1] &= ob[:, 1:]
    inner[0] = inner[-1] = False; inner[:, 0] = inner[:, -1] = False
    if inner.sum() < 12:
        return None
    rim = ob & ~inner
    spread = float(mean[inner].std()) * 100
    edge = float(mean[inner].mean() - mean[rim].mean()) * 100 if rim.any() else 0.0
    grain = float(fine[inner].mean()) * 100
    return {"spread": round(spread, 2), "edge": round(edge, 2), "grain": round(grain, 2),
            "flat": spread < FLAT}


_KEPT: dict = {}        # (drawing content, canvas w, h, comp w, h) -> its rows: the same picture measures the same
KEEP = 64


def _picture(frame: dict, w: int, h: int) -> np.ndarray:
    """The drawing's own picture, HxWx4 uint8 straight alpha: read from its ink PNG (the picture the engine draws: the
    same pixels, only its painted rectangle; made when the scene was described) when there is one, else made."""
    from PIL import Image
    from rostrum_paint import canvas, ink
    made = ink.made(frame, w, h)
    if made is None:
        return canvas.rgba8(frame, w, h)
    path, crop = made
    u8 = np.zeros((h, w, 4), np.uint8)
    if crop:
        x, y, cw, ch = crop
        with Image.open(path) as im:
            u8[y:y + ch, x:x + cw] = np.asarray(im.convert("RGBA"))
    return u8


def _grid_box(box: tuple, b: int, w: int, h: int) -> tuple[int, int, int, int]:
    """`box` (x0, y0, x1, y1) widened to whole blocks of the canvas's b px grid (the canvas's own edge stays)."""
    return box[0] // b * b, box[1] // b * b, min(w, -(-box[2] // b) * b), min(h, -(-box[3] // b) * b)


def _rows(layer: dict, frame: dict, washes: list, cw: float, ch: float) -> list[dict]:
    """The areas of one drawing's picture, top first (facts' rows for it). Each area is worked out only in its mask's
    box (compose.mask_box) widened to whole blocks of the canvas's grid, and the blocks' lightness once over the
    washes' joint box: the same blocks and numbers the whole canvas gives (over the whole canvas once per wash it
    took ~0.45 s a look, Night Market's 54 washes)."""
    from rostrum_paint import compose
    w, h = D.canvas_size(layer)
    b, rows = max(1, round(w / SEE)), []
    boxes = [(paint, s, mask, compose.mask_box(mask, w, h)) for paint, s, mask in washes]
    boxes = [(paint, s, mask, _grid_box(box, b, w, h)) for paint, s, mask, box in boxes if box is not None]
    if not boxes:
        return rows
    ux0, uy0 = min(x[3][0] for x in boxes), min(x[3][1] for x in boxes)
    ux1, uy1 = max(x[3][2] for x in boxes), max(x[3][3] for x in boxes)
    later, blocks = np.zeros((uy1 - uy0, ux1 - ux0), bool), None     # where a wash over this one already is
    for paint, s, mask, (x0, y0, x1, y1) in reversed(boxes):          # top first: a later wash hides the one under it
        inside = compose.mask_array(mask, w, h)[y0:y1, x0:x1] > 0.5
        seen = later[y0 - uy0:y1 - uy0, x0 - ux0:x1 - ux0]
        own = inside & ~seen
        seen |= inside
        share = float(own.sum()) / (cw * ch)
        if share >= MIN_SHARE:
            if blocks is None:
                rgba = _picture(frame, w, h)[uy0:uy1, ux0:ux1].astype(np.float32) / 255
                rgba[..., :3] *= rgba[..., 3:4]
                blocks = lightness(rgba, b)
            by, bx = (y0 - uy0) // b, (x0 - ux0) // b
            ny, nx = (y1 - y0) // b, (x1 - x0) // b
            if m := measure(None, own, b, (blocks[0][by:by + ny, bx:bx + nx], blocks[1][by:by + ny, bx:bx + nx])):
                rows.append({"drawing": layer["id"], "paint": paint, "stroke": s["id"], "area": round(share, 3), **m})
    return rows


def _on_screen(comp: dict, t: float):
    """(drawing layer, its frame shown at t, its washes) of each drawing on screen at t that has washes and is drawn whole."""
    for node in flatten(comp, t):
        layer = node.get("layer") or {}
        if layer.get("type") != "drawing" or not node.get("in_time", True):
            continue
        frame = D.frame_at(layer, node["frame"])
        washes = _washes(frame) if frame else []
        if washes and write_on.amount_at(layer, t) >= 1:
            yield layer, frame, washes


def masks(comp: dict, t: float) -> None:
    """The paint masks `facts` reads at t, made now (the painting kit keeps them): a look starts this while it
    describes and draws, since a new drawing's masks take ~1 s and need no picture."""
    from rostrum_paint import compose
    for layer, _, washes in _on_screen(comp, t):
        w, h = D.canvas_size(layer)
        for _, _, mask in washes:
            compose.mask_array(mask, w, h)


def facts(comp: dict, t: float) -> list[dict]:
    from rostrum_paint import canvas
    rows, (cw, ch) = [], comp_size(comp)
    for layer, frame, washes in _on_screen(comp, t):
        w, h = D.canvas_size(layer)
        key = (layer["id"], canvas.content_key(frame, w, h), json.dumps(washes, sort_keys=True), w, h, cw, ch)
        if key not in _KEPT:
            if len(_KEPT) >= KEEP:
                _KEPT.clear()
            _KEPT[key] = _rows(layer, frame, washes, cw, ch)
        rows += [dict(r) for r in _KEPT[key]]
    return rows[::-1]


def words(rows: list[dict]) -> str:
    flat = [r for r in rows if r["flat"]]
    if not flat:
        return ""
    each = "; ".join(f'{r["stroke"]} on {r["drawing"]} (paint {r["paint"]}, {round(100 * r["area"])} % of the frame): one '
                     f'flat value at frame size, lightness spread {r["spread"]:g} %, '
                     + (f'edge {r["edge"]:g} % darker' if r["edge"] >= EDGE else "no darker edge")
                     + f', grain {r["grain"]:g} %' for r in flat[:6])
    more = f" (and {len(flat) - 6} more)" if len(flat) > 6 else ""
    return (f" Flat painted areas: {each}{more}. A watercolour wash at paint.wash's defaults measures a spread of 4-6 % "
            f"and a rim 3-7 % darker; pooling, edge_darken, granulation and grain set them.")
