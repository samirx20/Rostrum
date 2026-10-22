"""Reading paint: a drawing layer's, or the paint on any element (a shape, text, picture or path holding `frames`,
paint_fields.py). Which drawing shows at a frame (the "Draw each frame" rule), its neighbours (onion skin), the
paint canvas's size and picture, and composition px -> canvas px. The one place these rules live; the scene, the
screen, the operations and the MCP tools use it.

The paint covers the element's own box (sizes.own_size; a drawing's box is its canvas w × h) and is stretched over
it: canvas px (0, 0)..(cw, ch) = the box's (0, 0)..(w, h), so it moves, scales and turns with the element.
"""
from __future__ import annotations

import math
from pathlib import Path

from rostrum_paint import canvas

from .sizes import own_size


def each_frame(item: dict) -> bool:
    """Draw each frame: each drawing shows at its own frame. Off: only the first drawing (one painting). Missing (an
    older document) = on when there are several drawings."""
    on = item.get("eachFrame")
    return len(item.get("frames", [])) > 1 if on is None else bool(on)


def shown_frames(item: dict) -> list[dict]:
    """The drawings that can show: all of them with Draw each frame on, else the first."""
    frames = item.get("frames", [])
    return frames if each_frame(item) else frames[:1]


def frame_at(drawing: dict, n: int) -> dict | None:
    """The drawing exposed at frame number `n`: the last one with at <= n (held until the next); None before the first."""
    shown = None
    for f in shown_frames(drawing):
        if f["at"] <= n:
            shown = f
        else:
            break
    return shown


def frame_number(t: float, fps: float) -> int:
    return int(math.floor(t * fps + 1e-6))


def neighbours(drawing: dict, frame_id: str, k: int = 2) -> tuple[list, list]:
    """(up to k drawings before, nearest first; up to k after, nearest first)."""
    frames = shown_frames(drawing)
    i = next((n for n, f in enumerate(frames) if f["id"] == frame_id), None)
    if i is None:
        raise KeyError(f"no drawing {frame_id!r} in {drawing['id']}")
    return frames[max(0, i - k):i][::-1], frames[i + 1:i + 1 + k]


def canvas_size(item: dict) -> tuple[int, int]:
    """The paint canvas in px: a drawing's w × h; an element's paintW × paintH (set by its first stroke)."""
    if item["type"] == "drawing":
        return int(item.get("w", 1920)), int(item.get("h", 1080))
    if not item.get("paintW") or not item.get("paintH"):
        raise ValueError(f'{item["id"]} has no paint yet (its first stroke sets the paint size)')
    return int(item["paintW"]), int(item["paintH"])


def paint_size(item: dict, props: dict) -> tuple[int, int]:
    """The canvas size a stroke paints at: canvas_size once there is paint; before the first stroke, the element's box
    at these values (`props`: resolved), in whole px."""
    if item["type"] == "drawing" or item.get("paintW"):
        return canvas_size(item)
    w, h = own_size(item["type"], props)
    return max(1, round(w)), max(1, round(h))


def picture(item: dict, frame: dict) -> Path:
    """One drawing's picture (content-keyed PNG, canvas size, straight alpha) for the engine to draw."""
    return canvas.png(frame, *canvas_size(item))


def to_canvas(item: dict, props: dict, x: float, y: float) -> tuple[float, float]:
    """Composition px -> the item's paint canvas px, for an item at top level with its values at this moment
    (`props`: resolved x, y, anchor, scale, stretch, rotation …). Tilt is not inverted."""
    from .boxes import matrix                        # boxes reads drawings too
    w, h = own_size(item["type"], props)
    a, b, c, d, e, f = matrix(props, w, h)
    det = a * d - b * c
    if not det or not w or not h:
        raise ValueError(f'{item["id"]} is scaled to nothing; there is no canvas point here')
    dx, dy = x - e, y - f
    lx, ly = (d * dx - c * dy) / det, (a * dy - b * dx) / det
    cw, ch = paint_size(item, props)
    return lx * cw / w, ly * ch / h
