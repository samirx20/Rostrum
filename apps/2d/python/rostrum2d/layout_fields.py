"""Auto layout's fields (layout.py is the solver): a group's layout settings and a laid-out layer's own two.

They are Python-side only: layoutbake.py turns them into the children's x / y (and w / h) keys per frame, so the
engine never sees them (scene.py leaves py_only(type) out of what it sends). Rule of individuality: a group's spacing
controls appear only once it has a layout; a layer's own layout controls only inside a laid-out group (the
`inLayout` fact, kind.py); a laid-out layer's X and Y are absent (the layout places it) unless it is set apart.
"""
from __future__ import annotations

from rostrum_core import Param

IS = lambda name, value: {"is": [name, value]}  # noqa: E731
ON = {"not": IS("layout", "none")}
FLOW = {"any": [IS("layout", "row"), IS("layout", "column")]}
GRID = IS("layout", "grid")
HUGGING = {"all": [ON, {"any": [IS("hugWidth", True), IS("hugHeight", True)]}]}
IN_LAYOUT ={"fact": "inLayout"}
PLACED = {"all": [IN_LAYOUT, IS("layoutApart", False)]}       # the layout sets this layer's x, y
FREE_XY = {"not": PLACED}

G = "Auto layout"


def _n(name, label, default, when, lo=0, hi=20000, step=1, unit="px", imp="primary", integer=False, help=""):
    return Param.number(name, label=label, group=G, min=lo, max=hi, step=step, unit=unit, importance=imp,
                        valid_when=when, integer=integer, default=default, help=help)


def _c(name, options, label, default, when, labels=None, imp="primary", help=""):
    return Param.choice(name, options, label=label, group=G, default=default, importance=imp, valid_when=when,
                        labels=labels or {}, help=help)


def _t(name, label, default, when, imp="secondary", help=""):
    return Param.toggle(name, label=label, group=G, default=default, importance=imp, valid_when=when, help=help)


GROUP = [
    _c("layout", ["none", "row", "column", "grid"], "Auto layout", "none", None, {"none": "Off"},
       help="Arrange the group's layers in a row, a column or a grid, again on every frame (a layer that grows "
            "pushes the others along)"),
    _n("gap", "Gap", 16.0, ON, help="Space between layers (between columns in a grid)"),
    _n("padding", "Padding", 10.0, ON, help="Space inside the group's edge, all round"),
    _c("justify", ["start", "center", "end", "between"], "Spread", "start", FLOW,
       {"start": "From the start", "center": "Centred", "end": "To the end", "between": "Space between"}),
    _c("align", ["start", "center", "end", "stretch"], "Align", "start", ON,
       {"start": "Start", "center": "Centre", "end": "End", "stretch": "Stretch"},
       help="Across the row (or column, or grid cell): top, middle, bottom, or stretched to fill it"),
    _t("wrap", "Wrap", False, FLOW, help="Start a new line when the next layer doesn't fit"),
    _n("columns", "Columns", 3, GRID, lo=1, hi=100, unit="", integer=True),
    _n("rowGap", "Line gap", 16.0, {"any": [GRID, {"all": [FLOW, IS("wrap", True)]}]},
       help="Space between wrapped lines (between rows in a grid)"),
    _t("hugWidth", "Width hugs layers", True, ON, help="The group's width follows what is inside it"),
    _t("hugHeight", "Height hugs layers", True, ON, help="The group's height follows what is inside it"),
    _t("hugPin", "Keep top-left fixed", True, HUGGING,
       help="A group that hugs its layers grows right and down from its top-left (left of a row, top of a column), "
            "as a design tool's frame does; off, it grows around its anchor. An anchor you moved off the middle "
            "always keeps its own place."),
]

CHILD_APART = _t("layoutApart", "Set apart", False, IN_LAYOUT, imp="deep",
                 help="Not arranged by the group's layout: placed by its own X and Y (a badge on a card)")
CHILD_GROW = _n("layoutGrow", "Fill space", 0.0, PLACED, lo=0, hi=100, step=0.1, unit="×", imp="secondary",
                help="Takes this share of the room left along the row or column (0 = keeps its own size)")
CHILD = [CHILD_APART]                    # every layer; CHILD_GROW only where the size is a field (SIZED)
SIZED = ("shape", "image", "group")      # w, h are animatable fields the layout may set (fill, stretch, hug)

SIZE_SET = {"w": {"not": {"all": [ON, IS("hugWidth", True)]}}, "h": {"not": {"all": [ON, IS("hugHeight", True)]}}}
_OWN = {CHILD_APART.name, CHILD_GROW.name}


def py_only(kind: str) -> set[str]:
    """The layout fields of an item type, which stay on the Python side (other types' "align" or "gap" are theirs)."""
    return _OWN | {p.name for p in GROUP} if kind == "group" else _OWN
