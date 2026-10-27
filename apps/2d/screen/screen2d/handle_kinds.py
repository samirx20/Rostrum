"""Which canvas handles a picked layer shows: one table, read by bounds.boxes (the box's `handles`) and by the
handle drags. No Qt.

"box"  : a corner square on each corner and one on each side, a turn zone outside each corner (most layers).
"text" : a text: a corner square on each corner (they scale the letters) and one on the left and right sides (they set the
         wrap width, `boxWidth`: the letters keep their size and the lines re-flow; shape_handle_slots.py). No top and
         bottom squares: a text's height is its lines'. The side squares show on a short text too (a line of words is
         rarely 36 px tall on screen).
"ends" : a line or an arrow: one square on each end point (drag it to move that end: the length and the turn follow,
         the other end stays; Alt: from the middle; Shift: 15 degree steps). No middle squares (they would sit on the
         line and steal a press meant to move it), no turn zones (an end turns it).
The anchor ring (anchor_slots.py) shows on every kit that says "anchor", while the Anchor group is open.
SHAPE_HANDLES: the orange setting handles a picked shape shows over its knobs, per shape kind (ShapeHandles.qml; where
each sits, how it hides by size and what its drag sets: shape_handle_geom.HANDLES).
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
    "text": {"knobs": [*(_knob(*k) for k in ((-1, -1), (1, -1), (1, 1), (-1, 1))), _knob(1, 0, True), _knob(-1, 0, True)], "turn": True, "anchor": True, "sides": "wrap"},
}
ENDS = {("shape", "line"), ("shape", "arrow")}          # (layer type, shape kind) drawn from one end to the other
BY_TYPE = {"text": "text"}                              # a layer type's own kit ("box" for the rest)
SHAPE_HANDLES = {
    "rect": ("radius:nw", "radius:ne", "radius:se", "radius:sw"),
    "ellipse": ("start", "end"),                        # dragging one makes it an arc, the same box
    "arc": ("start", "end", "hole"),
    "star": ("points", "inner", "radius"),
    "polygon": ("sides", "radius"),
    "triangle": ("tip", "radius"),
    "spiral": ("turns",),
}


def dressed(box: dict) -> dict:
    """The box as the canvas draws its knobs (Handles.qml): its kit (`kit`, by its `handles`; a group's box: "box") and
    each knob's `resize` pointer angle (`angles`, the knob's direction plus the box's turn: transform.resize_cursor), in the box itself. Asked of
    Python per knob, each box change made ~8 calls back from the screen (~1.5 ms a Ctrl+G)."""
    from .transform import resize_cursor
    kit = KITS.get(box.get("handles") or "box", KITS["box"])
    rot = box.get("rot") or 0
    return {**box, "kit": kit, "angles": [resize_cursor(k["hx"], k["hy"], rot) for k in kit["knobs"]]}


def kit_of(layer_type: str, p: dict) -> str:
    """The kit's name for a layer (p: its values)."""
    return "ends" if (layer_type, p.get("shape")) in ENDS else BY_TYPE.get(layer_type, "box")
