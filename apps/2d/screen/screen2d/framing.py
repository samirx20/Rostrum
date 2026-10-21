"""Frame-by-frame on a drawing layer: what the timeline shows and the calls for the buttons. No Qt.

A drawing shows its frame with the largest `at` <= the current frame number, held until the next one. The last
frame is held to the end of the composition, so only a frame with a next one can be held longer or shorter.
"""
from __future__ import annotations

from rostrum2d.drawing import frame_at
from rostrum_core.ids import random_id


def marks(drawing: dict, fps: float, duration: float) -> list[dict]:
    """[{id, at, t0, t1}] sorted by `at`: where each drawing starts and until when it is held (seconds)."""
    fr = sorted(drawing.get("frames", []), key=lambda f: f["at"])
    ends = [f["at"] for f in fr[1:]] + [round(duration * fps)]
    return [{"id": f["id"], "at": f["at"], "t0": f["at"] / fps, "t1": max(end, f["at"] + 1) / fps}
            for f, end in zip(fr, ends)]


def state(drawing: dict, n: int) -> dict:
    """What the buttons need at frame number n: which of them apply (the rest are absent from the screen)."""
    fr = sorted(drawing.get("frames", []), key=lambda f: f["at"])
    here = frame_at(drawing, n)
    nxt = next((f for f in fr if f["at"] > n), None)
    held = (nxt["at"] - here["at"]) if here and nxt else 0
    return {"has": here is not None, "exact": here is not None and here["at"] == n,
            "prev": next((f["at"] for f in reversed(fr) if f["at"] < n), None), "next": nxt["at"] if nxt else None,
            "held": held, "canHold": bool(held), "canShorten": held > 1}


def new_frame(drawing: dict, n: int, copy: bool) -> tuple[list[dict], str]:
    """`frame.add` at n, optionally with the paint of the drawing shown now (the previous one)."""
    args = {"id": random_id("frame"), "at": n}
    here = frame_at(drawing, n)
    if copy and here is not None:
        args["copy"] = here["id"]
    return [{"op": "frame.add", "target": [drawing["id"]], "args": args}], "New drawing"


def hold(drawing: dict, n: int, delta: int) -> tuple[list[dict], str]:
    here, s = frame_at(drawing, n), state(drawing, n)
    frames = max(1, s["held"] + delta)
    return ([{"op": "frame.hold", "target": [here["id"]], "args": {"frames": frames}}],
            "Hold drawing longer" if delta > 0 else "Hold drawing shorter")
