"""Reading drawing layers: which drawing shows at a frame, its neighbours (onion skin), its canvas size and picture,
and composition px -> canvas px. The one place these rules live; the scene, the screen and the MCP tools use it.
"""
from __future__ import annotations

import math
from pathlib import Path

from rostrum_paint import canvas


def frame_at(drawing: dict, n: int) -> dict | None:
    """The drawing exposed at frame number `n`: the last one with at <= n (held until the next); None before the first."""
    shown = None
    for f in drawing.get("frames", []):
        if f["at"] <= n:
            shown = f
        else:
            break
    return shown


def frame_number(t: float, fps: float) -> int:
    return int(math.floor(t * fps + 1e-6))


def neighbours(drawing: dict, frame_id: str, k: int = 2) -> tuple[list, list]:
    """(up to k drawings before, nearest first; up to k after, nearest first)."""
    frames = drawing.get("frames", [])
    i = next((n for n, f in enumerate(frames) if f["id"] == frame_id), None)
    if i is None:
        raise KeyError(f"no drawing {frame_id!r} in {drawing['id']}")
    return frames[max(0, i - k):i][::-1], frames[i + 1:i + 1 + k]


def canvas_size(drawing: dict) -> tuple[int, int]:
    return int(drawing.get("w", 1920)), int(drawing.get("h", 1080))


def picture(drawing: dict, frame: dict) -> Path:
    """The drawing's picture (content-keyed PNG, w × h, straight alpha) for the engine to draw."""
    return canvas.png(frame, *canvas_size(drawing))


def to_canvas(props: dict, x: float, y: float) -> tuple[float, float]:
    """Composition px -> the drawing's canvas px, for a drawing at top level with its values at this moment
    (`props`: resolved x, y, anchor, scale, stretch, rotation). Tilt is not inverted."""
    w, h = props["w"], props["h"]
    sx, sy = props["scale"] * props["scaleX"], props["scale"] * props["scaleY"]
    if not sx or not sy:
        raise ValueError("the drawing is scaled to nothing; there is no canvas point here")
    dx, dy = x - props["x"], y - props["y"]
    a = math.radians(-props.get("rotation", 0.0))
    dx, dy = dx * math.cos(a) - dy * math.sin(a), dx * math.sin(a) + dy * math.cos(a)
    return dx / sx + props["anchorX"] * w, dy / sy + props["anchorY"] * h
