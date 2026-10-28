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


def measure(rgba: np.ndarray, own: np.ndarray, b: int) -> dict | None:
    """One area's numbers: `rgba` premultiplied HxWx4, `own` HxW bool (its pixels), `b` block px."""
    lum = (rgba[..., :3] + (1 - rgba[..., 3:4]) * PAPER) @ LUMA
    blk, ob = _blocks(lum, b), _blocks(own, b).all(axis=(2, 3))
    inner = ob.copy()
    inner[1:] &= ob[:-1]; inner[:-1] &= ob[1:]; inner[:, 1:] &= ob[:, :-1]; inner[:, :-1] &= ob[:, 1:]
    inner[0] = inner[-1] = False; inner[:, 0] = inner[:, -1] = False
    if inner.sum() < 12:
        return None
    rim = ob & ~inner
    mean = blk.mean(axis=(2, 3))
    spread = float(mean[inner].std()) * 100
    edge = float(mean[inner].mean() - mean[rim].mean()) * 100 if rim.any() else 0.0
    grain = float(blk.std(axis=(2, 3))[inner].mean()) * 100
    return {"spread": round(spread, 2), "edge": round(edge, 2), "grain": round(grain, 2),
            "flat": spread < FLAT}


def facts(comp: dict, t: float) -> list[dict]:
    from rostrum_paint import canvas, compose
    rows, (cw, ch) = [], comp_size(comp)
    for node in flatten(comp, t):
        layer = node.get("layer") or {}
        if layer.get("type") != "drawing" or not node.get("in_time", True):
            continue
        frame = D.frame_at(layer, node["frame"])
        washes = _washes(frame) if frame else []
        if not washes or write_on.amount_at(layer, t) < 1:
            continue
        w, h = D.canvas_size(layer)
        u8 = canvas.rgba8(frame, w, h)                      # the drawing's own picture (kept on disk once made)
        rgba = u8.astype(np.float32) / 255
        rgba[..., :3] *= rgba[..., 3:4]
        b, later = max(1, round(w / SEE)), np.zeros((h, w), bool)
        for paint, s, mask in reversed(washes):            # top first: a later wash hides the one under it
            inside = compose.mask_array(mask, w, h) > 0.5
            own = inside & ~later
            later |= inside
            share = float(own.sum()) / (cw * ch)
            m = measure(rgba, own, b) if share >= MIN_SHARE else None
            if m:
                rows.append({"drawing": layer["id"], "paint": paint, "stroke": s["id"], "area": round(share, 3), **m})
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
