"""A painted fill as the engine reads it: the node's `fillFrames` [{"at": comp frame, "src": png}, …], the same form as a
drawing's `frames`. One picture per drawing of the painting, made by the painting kit's content-keyed PNG (drawing.picture),
so every layer using a painting names the same files.

A painting that draws each frame (2+ drawings) always loops (the painting's Loop: loop or ping-pong; "off" loops too, a fill
has no "hold the last"), from the layer's own start: a layer that starts at 2 s shows drawing 1 at 2 s, shifted by the
layer's `fillPhase` (the drawing this use starts on). Any other painting shows its first drawing.
"""
from __future__ import annotations

import math

from . import drawing, looping, retime


def of(item: dict, fps: float, where: dict | None) -> list[dict]:
    """The fill's frames for a layer filled with a painting. ValueError (in words) when the painting is not in the document."""
    where = where or {}
    painting = (where.get("paintings") or {}).get(item.get("fillPainting", ""))
    if painting is None:
        raise ValueError(f'{item["id"]}: its painted fill names no painting of this document ("{item.get("fillPainting") or "(none)"}")')
    drawings = sorted(drawing.shown_frames(painting), key=lambda f: f["at"])
    if not drawings:
        return []
    later = where.get("later")
    start = drawing.frame_number(item.get("start", 0.0), fps)
    pic: dict = {}

    def src(frame: dict) -> str:
        if frame["id"] not in pic:
            pic[frame["id"]] = str(drawing.picture(painting, frame, later))
        return pic[frame["id"]]
    if len(drawings) < 2:
        return [{"at": start, "src": src(drawings[0])}]
    mode = "pingpong" if looping.mode_of(painting.get("loop")) == "pingpong" else "loop"
    loop = {**painting, "loop": mode}
    begin = drawings[int(item.get("fillPhase", 0)) % len(drawings)]["at"]
    until = min(item.get("end", retime.END_OF_COMP), where.get("until", 0.0) or 60.0)
    out, last = [], None
    for n in range(start, max(math.ceil(until * fps), start + 1)):
        shown = drawing.frame_at(loop, begin + n - start)
        if shown is not last:
            out.append({"at": n, "src": src(shown)})
            last = shown
    return out
