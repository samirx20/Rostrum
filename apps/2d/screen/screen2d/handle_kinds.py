"""Which canvas handles a picked layer shows: one table, read by bounds.boxes (the box's `handles`) and by the
handle drags. No Qt.

"box"  : a corner square on each corner and one on each side, a turn zone outside each corner (most layers).
"ends" : a line or an arrow: one square on each end point (drag it to move that end: the length and the turn follow,
         the other end stays; Alt: from the middle; Shift: 15 degree steps). No middle squares (they would sit on the
         line and steal a press meant to move it), no turn zones (an end turns it).
The anchor ring (anchor_slots.py) shows on every kit that says "anchor", while the Anchor group is open.
A knob is {hx, hy, name, always}: -1 left / top, 1 right / bottom, 0 the middle; `always` shows it on a thin box too
(Handles.qml hides a side knob of a small box).
"""
from __future__ import annotations

NAMES = {(-1, -1): "nw", (1, -1): "ne", (1, 1): "se", (-1, 1): "sw", (0, -1): "n", (1, 0): "e", (0, 1): "s", (-1, 0): "w"}


def _knob(hx, hy, always=False):
    return {"hx": hx, "hy": hy, "name": NAMES[(hx, hy)], "always": always}


KITS = {
    "box": {"knobs": [_knob(*k) for k in ((-1, -1), (1, -1), (1, 1), (-1, 1), (0, -1), (1, 0), (0, 1), (-1, 0))], "turn": True, "anchor": True},
    "ends": {"knobs": [_knob(1, 0, True), _knob(-1, 0, True)], "turn": False, "anchor": True},
}
ENDS = {("shape", "line"), ("shape", "arrow")}          # (layer type, shape kind) drawn from one end to the other


def kit_of(layer_type: str, p: dict) -> str:
    """The kit's name for a layer (p: its values)."""
    return "ends" if (layer_type, p.get("shape")) in ENDS else "box"
