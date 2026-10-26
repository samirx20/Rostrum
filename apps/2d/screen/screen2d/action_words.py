"""The status line after Fill the frame, Fit inside the frame, Stay put when the frame moves and Crop to a box, in plain
words (action_rules.said reads `told`): what was done and to how many layers, and for the pin whether anything shows yet.
No Qt."""
from __future__ import annotations

from rostrum_core.keys import keys_of

from rostrum2d.frame import view as frame_view

FRAME_FIELDS = ("x", "y", "zoom", "rotation")


def _layers(n: int) -> str:
    return "1 layer" if n == 1 else f"{n} layers"


def _frame_moves(doc, ids) -> bool:
    """The frame of the scene these layers sit in is keyed (it moves), so pinning shows."""
    parent = doc.item(doc.parent_of(ids[0])[0])
    fr = frame_view.of(parent) if parent["type"] == "comp" else None
    return fr is not None and any(keys_of(fr, f) for f in FRAME_FIELDS)


def told(calls: list[dict], doc) -> str:
    """The plain words for these calls, "" when they are not one of the four."""
    for c in calls:
        op, args = c["op"], c["args"]
        if op == "layer.fill_frame":
            n = _layers(len(c["target"]))
            return f"Filled the frame with {n}" if args.get("mode", "cover") == "cover" else f"Fitted {n} inside the frame"
        if op == "group.make" and args.get("as") == "clip":
            return f"Cropped {_layers(len(c['target']))} to a box: what is outside it is hidden"
        if op == "layer.pin":
            n, on = _layers(len(c["target"])), bool(args.get("on"))
            if not on:
                return f"Unstuck {n} from the shot: {'it moves' if len(c['target']) == 1 else 'they move'} with the scene again"
            stay = "it stays" if len(c["target"]) == 1 else "they stay"
            tail = "" if _frame_moves(doc, c["target"]) else " (nothing changes until the frame moves)"
            return f"Stuck {n} to the shot: {stay} in place on screen when the frame moves{tail}"
    return ""
