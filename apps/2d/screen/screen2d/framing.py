"""Frame-by-frame on a drawing layer or a painted element (only the drawings that can show: drawing.shown_frames): what the timeline shows and the calls for the buttons. No Qt.

A drawing shows its frame with the largest `at` <= the current frame number, held until the next one. The last
frame is held to the end of the composition, so only a frame with a next one can be held longer or shorter.
"""
from __future__ import annotations

from rostrum2d.drawing import frame_at, shown_frames
from rostrum_core.ids import random_id


HOLDS = {1: "on ones", 2: "on twos", 3: "on threes", 4: "on fours"}


def marks(drawing: dict, fps: float, duration: float) -> list[dict]:
    """[{id, n, at, held, t0, t1}] sorted by `at`: each drawing's number (1 …), where it starts, how many frames it is
    held and until when (seconds; the last one to the end of the composition)."""
    fr = sorted(shown_frames(drawing), key=lambda f: f["at"])
    ends = [f["at"] for f in fr[1:]] + [round(duration * fps)]
    return [{"id": f["id"], "n": i + 1, "at": f["at"], "held": max(end - f["at"], 1), "t0": f["at"] / fps,
             "t1": max(end, f["at"] + 1) / fps} for i, (f, end) in enumerate(zip(fr, ends))]


def note(drawing: dict) -> str:
    """The row's note: "9 drawings · on twos" (the usual hold, when most drawings share one)."""
    fr = sorted(shown_frames(drawing), key=lambda f: f["at"])
    holds = [b["at"] - a["at"] for a, b in zip(fr, fr[1:])]
    common = max(set(holds), key=holds.count) if holds else 0
    word = f"{len(fr)} drawing" + ("" if len(fr) == 1 else "s")
    return f"{word} · {HOLDS[common]}" if common in HOLDS and holds.count(common) * 2 > len(holds) else word


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
