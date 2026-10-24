"""Edit mesh's actions as data (SPEC 4.3): which fit which selection type, their operation, their numbers (label, unit,
range) and starting values, and the call's arguments. mesh_actions.py runs them; the panel is built from them. A new
action is a line here. mm numbers are shown in mm and sent in metres; a unit-less number is sent as it is.
"""
from __future__ import annotations

ACTIONS = {"faces": ["extrude", "inset"], "edges": ["bevel", "loopcut", "sharp", "unsharp"], "points": []}
WORDS = {"extrude": "Extrude", "inset": "Inset", "bevel": "Bevel", "loopcut": "Loop cut", "sharp": "Sharp",
         "unsharp": "Not sharp", "material": "Material", "knife": "Knife"}
OPS = {"extrude": "faces.extrude", "inset": "faces.inset", "bevel": "edges.bevel", "loopcut": "edges.loopcut",
       "sharp": "edges.sharp", "unsharp": "edges.sharp", "material": "faces.material", "knife": "mesh.knife"}
# name: [(key, label, unit, from, to, step)]
NUMBERS = {"extrude": [("distance", "Distance", "mm", 0, 1000, 0.1)],
           "inset": [("width", "Width", "mm", 0, 1000, 0.1), ("depth", "Depth", "mm", -1000, 1000, 0.1)],
           "bevel": [("width", "Width", "mm", 0.1, 1000, 0.1), ("segments", "Segments", "", 1, 16, 1)],
           "loopcut": [("count", "Cuts", "", 1, 16, 1), ("slide", "Slide", "", -1, 1, 0.05)]}
START = {"extrude": {"distance": 5.0}, "inset": {"width": 3.0, "depth": 0.0}, "bevel": {"width": 3.0, "segments": 1},
         "loopcut": {"count": 1, "slide": 0.0}}
INTS = {"segments", "count"}
ARROWED = {"extrude": ("distance", "faces"), "bevel": ("width", "edges")}    # last action: its number has a grip in the viewport


def numbers(name, nums):
    """[{name, label, value, unit, from, to, step}] for the panel."""
    return [{"name": k, "label": lab, "value": nums[name][k], "unit": u, "from": lo, "to": hi, "step": st}
            for k, lab, u, lo, hi, st in NUMBERS.get(name, [])]


def args(name, nums, selector):
    """The operation's arguments for the action with these numbers on this selector text."""
    n = nums.get(name, {})
    out = {k: (n[k] / 1000 if u == "mm" else int(n[k]) if k in INTS else n[k]) for k, _, u, _, _, _ in NUMBERS.get(name, [])}
    if name in ("sharp", "unsharp"):
        return {"edges": selector, "sharp": name == "sharp"}
    if name == "loopcut":
        selector = " ".join(selector.split()[:2])         # one edge of the ring names the ring
    return {("faces" if selector.startswith("faces") else "edges"): selector, **out}
