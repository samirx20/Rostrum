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
    loop, begin = _run(item, painting, drawings)
    until = min(item.get("end", retime.END_OF_COMP), where.get("until", 0.0) or 60.0)
    out, last = [], None
    for n in range(start, max(math.ceil(until * fps), start + 1)):
        shown = drawing.frame_at(loop, begin + n - start)
        if shown is not last:
            out.append({"at": n, "src": src(shown)})
            last = shown
    return out


def _run(item: dict, painting: dict, drawings: list[dict]) -> tuple[dict, int]:
    """(the painting as it loops in a fill, the painting's frame this layer starts on)."""
    mode = "pingpong" if looping.mode_of(painting.get("loop")) == "pingpong" else "loop"
    return {**painting, "loop": mode}, drawings[int(item.get("fillPhase", 0)) % len(drawings)]["at"]


def shown(item: dict, painting: dict, n: int, fps: float) -> dict | None:
    """The painting's drawing this layer shows at composition frame `n` (the one a stroke painted through it lands in);
    None when the painting has no drawing."""
    drawings = sorted(drawing.shown_frames(painting), key=lambda f: f["at"])
    if len(drawings) < 2:
        return drawings[0] if drawings else None
    loop, begin = _run(item, painting, drawings)
    start = drawing.frame_number(item.get("start", 0.0), fps)
    return drawing.frame_at(loop, begin + max(n, start) - start)


def when_shown(item: dict, painting: dict, at: int, now: int, fps: float) -> int:
    """The layer's own frame, from `now` on (else from its start), at which it next shows the painting's drawing that
    starts at painting frame `at`: where a frame tool painting in place puts the playhead. `now` when none does."""
    want = next((f for f in drawing.shown_frames(painting) if f["at"] == at), None)
    if want is None:
        return now
    start = drawing.frame_number(item.get("start", 0.0), fps)
    span = 2 * (max(f["at"] for f in drawing.shown_frames(painting)) + 1) + 240    # a whole round (ping-pong, a long last hold)
    for n in [*range(max(now, start), max(now, start) + span), *range(start, max(now, start))]:
        if shown(item, painting, n, fps) is want:
            return n
    return now
