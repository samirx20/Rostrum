"""Frame-by-frame on a drawing layer or a painted element (only the drawings that can show: drawing.shown_frames): what the timeline shows and the calls for the buttons. No Qt.

A drawing shows its frame with the largest `at` <= the current frame number, held until the next one. The last
frame is held to the end of the composition, so only a frame with a next one can be held longer or shorter.
"""
from __future__ import annotations

from rostrum2d.drawing import frame_at, cycle, repeats, shown_frames
from rostrum_core.ids import random_id


def marks(drawing: dict, fps: float, duration: float) -> list[dict]:
    """[{id, n, at, held, t0, t1}] sorted by `at`: each drawing's number (1 …), where it starts, how many frames it is
    held and until when (seconds; the last one to the end of the composition)."""
    fr = sorted(shown_frames(drawing), key=lambda f: f["at"])
    run = cycle(drawing)       # a looping drawing's own run ends where its cycle does; the rounds after are `again`
    ends = [f["at"] for f in fr[1:]] + [run[0] + run[1] if run else round(duration * fps)]
    return [{"id": f["id"], "n": i + 1, "at": f["at"], "held": max(end - f["at"], 1), "t0": f["at"] / fps,
             "t1": max(end, f["at"] + 1) / fps} for i, (f, end) in enumerate(zip(fr, ends))]


def again(drawing: dict, fps: float, duration: float) -> list[dict]:
    """[{n, t0, t1}]: the cells a looping drawing shows again after its own run (empty with Loop off), drawn faintly."""
    run = cycle(drawing)
    if not run:
        return []
    end = round(min(drawing.get("end", duration), duration) * fps)
    shown = repeats(drawing, end)
    order = {f["id"]: i + 1 for i, f in enumerate(sorted(shown_frames(drawing), key=lambda f: f["at"]))}
    stops = [n for n, _ in shown[1:]] + [end]
    return [{"n": order[f["id"]], "t0": n / fps, "t1": max(stop, n + 1) / fps}
            for (n, f), stop in zip(shown, stops) if n >= run[0] + run[1]]


def state(drawing: dict, n: int) -> dict:
    """What the buttons need at frame number n: which of them apply (the rest are absent from the screen)."""
    fr = sorted(shown_frames(drawing), key=lambda f: f["at"])
    here = frame_at(drawing, n)
    nxt = next((f for f in fr if f["at"] > n), None)
    held = (nxt["at"] - here["at"]) if here and nxt else 0
    i = next((k for k, f in enumerate(fr) if here and f["id"] == here["id"]), -1)
    return {"has": here is not None, "exact": here is not None and here["at"] == n, "index": i + 1, "count": len(fr),
            "id": here["id"] if here else "", "last": nxt is None,
            "prev": next((f["at"] for f in reversed(fr) if f["at"] < n), None), "next": nxt["at"] if nxt else None,
            "held": held, "canHold": bool(held), "canShorten": held > 1}


def flip(drawing: dict, n: int, direction: int) -> tuple[int, int] | None:
    """Holding , or .: the next (or previous) drawing's start, round to the first (or the last) at the end, and how
    many frames it shows before the next flip (its hold; the last one: one frame). None with no drawings."""
    fr = sorted(shown_frames(drawing), key=lambda f: f["at"])
    if not fr:
        return None
    s = state(drawing, n)
    at = s["next" if direction > 0 else "prev"]
    at = at if at is not None else fr[0 if direction > 0 else -1]["at"]
    return at, max(1, state(drawing, at)["held"])


def new_frame(drawing: dict, n: int, copy: bool) -> tuple[list[dict], str, int]:
    """New (or a copy of the drawing shown now), and the frame it starts at. On an empty or held frame it goes at the
    playhead; where a drawing starts it goes one New-ones-hold later (`newHold`), the current one held that long and
    the later ones moved on to make room. One change."""
    hold_n = int(drawing.get("newHold") or 2)
    here = frame_at(drawing, n)
    at = n if here is None or here["at"] != n else n + hold_n
    args = {"id": random_id("frame"), "at": at}
    if copy and here is not None:
        args["copy"] = here["id"]
    calls = []
    if at != n and not state(drawing, n)["last"]:           # inserting: here holds 2 × newHold, the new one takes half
        calls.append({"op": "frame.hold", "target": [here["id"]], "args": {"frames": 2 * hold_n}})
    calls.append({"op": "frame.add", "target": [drawing["id"]], "args": args})
    return calls, "Copy drawing" if copy else "New drawing", at


def hold(drawing: dict, n: int, delta: int) -> tuple[list[dict], str]:
    here, s = frame_at(drawing, n), state(drawing, n)
    frames = max(1, s["held"] + delta)
    return ([{"op": "frame.hold", "target": [here["id"]], "args": {"frames": frames}}],
            "Hold drawing longer" if delta > 0 else "Hold drawing shorter")
