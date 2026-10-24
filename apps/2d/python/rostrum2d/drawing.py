"""Reading paint: a drawing layer's, or the paint on any element (a shape, text, picture or path holding `frames`,
paint_fields.py). Which drawing shows at a frame (the "Draw each frame" rule), its neighbours (onion skin), the
paint canvas's size and picture. The one place these rules live; the scene, the
screen, the operations and the MCP tools use it.

The paint covers the element's own box (sizes.own_size; a drawing's box is its canvas w × h) and is stretched over
it: canvas px (0, 0)..(cw, ch) = the box's (0, 0)..(w, h), so it moves, scales and turns with the element. Composition
px -> canvas px is placement.py's (the engine's own placement of the layer).
"""
from __future__ import annotations

import math
from pathlib import Path

from rostrum_core import filestamps
from rostrum_paint import canvas, ink

from . import looping
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


def cycle(drawing: dict) -> tuple[int, int] | None:
    """(the frame the cycle starts at, its length in frames) for a drawing that loops; None when it holds its last
    drawing (Loop off) or has no run to repeat. The last drawing is held as long as the one before it."""
    fr = sorted((f["at"] for f in shown_frames(drawing)))
    if looping.mode_of(drawing.get("loop")) == "off" or len(fr) < 2:
        return None
    return fr[0], fr[-1] - fr[0] + max(fr[-1] - fr[-2], 1)


def frame_at(drawing: dict, n: int) -> dict | None:
    """The drawing exposed at frame number `n`: the last one with at <= n (held until the next); None before the first.
    A looping drawing (Loop: loop or ping-pong) repeats its run from the first drawing on, through looping.fold."""
    run = cycle(drawing)
    if run and n >= run[0]:
        n = run[0] + looping.fold(n - run[0], run[1], looping.mode_of(drawing.get("loop")))
    shown = None
    for f in shown_frames(drawing):
        if f["at"] <= n:
            shown = f
        else:
            break
    return shown


def repeats(drawing: dict, last: int) -> list[tuple[int, dict]]:
    """[(frame number, drawing)] for each change of picture from the first drawing to frame `last`: what a looping
    drawing shows over its layer's length (the engine reads explicit frames)."""
    run, out = cycle(drawing), []
    if not run:
        return [(f["at"], f) for f in shown_frames(drawing)]
    for n in range(run[0], max(last, run[0] + 1)):
        here = frame_at(drawing, n)
        if not out or out[-1][1] is not here:
            out.append((n, here))
    return out


def frame_number(t: float, fps: float) -> int:
    return int(math.floor(t * fps + 1e-6))


def neighbours(drawing: dict, frame_id: str, k: int = 2) -> tuple[list, list]:
    """(up to k drawings before, nearest first; up to k after, nearest first)."""
    frames = shown_frames(drawing)
    i = next((n for n, f in enumerate(frames) if f["id"] == frame_id), None)
    if i is None:
        raise KeyError(f"no drawing {frame_id!r} in {drawing['id']}")
    return frames[max(0, i - k):i][::-1], frames[i + 1:i + 1 + k]


CANVASES = ("drawing", "painting")      # items that are a canvas of their own (w × h), not paint on an element


def canvas_size(item: dict) -> tuple[int, int]:
    """The paint canvas in px: a drawing's or a painting's w × h; an element's paintW × paintH (set by its first stroke)."""
    if item["type"] in CANVASES:
        return int(item.get("w", 1920)), int(item.get("h", 1080))
    if not item.get("paintW") or not item.get("paintH"):
        raise ValueError(f'{item["id"]} has no paint yet (its first stroke sets the paint size)')
    return int(item["paintW"]), int(item["paintH"])


def paint_size(item: dict, props: dict) -> tuple[int, int]:
    """The canvas size a stroke paints at: canvas_size once there is paint; before the first stroke, the element's box
    at these values (`props`: resolved), in whole px."""
    if item["type"] in CANVASES or item.get("paintW"):
        return canvas_size(item)
    w, h = own_size(item["type"], props)
    return max(1, round(w)), max(1, round(h))


_SHOWN: dict = {}           # frame id -> (the frame as it was, w, h, its PNG): the last picture made of each drawing


def picture(item: dict, frame: dict, later: list | None = None) -> Path:
    """One drawing's picture (content-keyed PNG, canvas size, straight alpha) for the engine to draw. A drawing equal
    to the one last pictured (a document is never changed in place: each change is a new tree) reuses its PNG without
    keying every stroke again, so a change elsewhere costs a compare, not 10,000 strokes' keys.
    `later` (a screen, which must not wait for pixels): a picture not made yet is added to it as a job (a call that
    makes it) to run off the screen's thread, and its last picture (or a blank one) stands in meanwhile."""
    w, h = canvas_size(item)
    got = _SHOWN.get(frame["id"])
    if got and got[1:3] == (w, h) and (got[0] is frame or got[0] == frame) and filestamps.is_file(got[3]):
        return got[3]
    if later is not None and canvas.made(frame, w, h) is None:
        later.append(lambda: canvas.png(frame, w, h))
        return got[3] if got and got[1:3] == (w, h) and filestamps.is_file(got[3]) else canvas.png({"paints": []}, w, h)
    path = canvas.png(frame, w, h)
    if len(_SHOWN) > 512:
        _SHOWN.clear()
    _SHOWN[frame["id"]] = (frame, w, h, path)
    return path


_INKED: dict = {}           # frame id -> (the frame as it was, w, h, its entry): the last ink picture of each drawing


def inked(item: dict, frame: dict, later: list | None = None) -> dict:
    """A drawing layer's picture as the engine's frame entry: {"src": the ink's PNG, "crop": [x, y, w, h] in canvas px}
    (rostrum_paint.ink: only the painted rectangle), no crop for a drawing with no ink. Remembered and `later` as
    `picture`; the stand-in meanwhile is the last entry, moved as far as the drawing grew left or up since (or nothing
    painted), so a stroke that grows the drawing never blinks the rest of it away."""
    w, h = canvas_size(item)
    got = _INKED.get(frame["id"])
    if got and got[1:3] == (w, h) and (got[0] is frame or got[0] == frame) and filestamps.is_file(got[3]["src"]):
        return got[3]
    done = ink.made(frame, w, h)
    if done is None and later is not None:
        later.append(lambda: ink.png(frame, w, h))
        if got and filestamps.is_file(got[3]["src"]):
            return _moved(got[3], got[0], frame)
        return _entry(ink.png({"paints": []}, w, h))
    entry = _entry(done or ink.png(frame, w, h))
    if len(_INKED) > 512:
        _INKED.clear()
    _INKED[frame["id"]] = (frame, w, h, entry)
    return entry


def _entry(made: tuple) -> dict:
    return {"src": str(made[0]), **({"crop": made[1]} if made[1] else {})}


def _moved(entry: dict, old: dict, new: dict) -> dict:
    """The entry with its crop moved by the growth between two states of a drawing (paperX / paperY, paint_grow.py)."""
    if "crop" not in entry:
        return entry
    (ox, oy), (nx, ny) = canvas.origin(old), canvas.origin(new)
    x, y, w, h = entry["crop"]
    return {**entry, "crop": [x + nx - ox, y + ny - oy, w, h]}
