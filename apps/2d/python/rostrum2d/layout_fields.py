"""Auto layout's fields (layout.py is the solver): a group's layout settings (a CSS flex / grid box) and a laid-out
layer's own place in it (grow, shrink, align itself, margin, span, size mode, shift).

They are Python-side only: layoutbake.py turns them into the children's x / y (and w / h, a text's boxWidth) keys per
frame, so the engine's scene never sees them (scene.py leaves py_only(type) out of what it sends). Rule of
individuality: a group's spacing controls appear only once it has a layout; a layer's own layout controls only inside
a laid-out group (the `inLayout` fact, kind.py); a laid-out layer's X and Y are absent (the layout places it) unless it
is set apart. A group's background and corner radius are its Background fields (group_bg.py); its overflow is `clip`.
"""
from __future__ import annotations

from rostrum_core import Param

IS = lambda name, value: {"is": [name, value]}  # noqa: E731
ON = {"not": IS("layout", "none")}
FLOW = {"any": [IS("layout", "row"), IS("layout", "column")]}
GRID = IS("layout", "grid")
FIT = {"all": [ON, {"any": [IS("sizeW", "fit"), IS("sizeH", "fit")]}]}
IN_LAYOUT = {"fact": "inLayout"}
PLACED = {"all": [IN_LAYOUT, IS("layoutApart", False)]}       # the layout sets this layer's x, y
FREE_XY = {"not": PLACED}

G = "Auto layout"
SIZE_WORDS = {"fixed": "Fixed", "fit": "Fit content", "fill": "Fill", "percent": "Percent"}
ALIGNS = ["start", "center", "end", "stretch", "baseline"]
ALIGN_WORDS = {"start": "Start", "center": "Centre", "end": "End", "stretch": "Stretch", "baseline": "Text baseline"}


def _n(name, label, default, when, lo=0, hi=20000, step=1, unit="px", imp="primary", integer=False, help="", words=None):
    return Param.number(name, label=label, group=G, min=lo, max=hi, step=step, unit=unit, importance=imp,
                        valid_when=when, integer=integer, default=default, help=help, words=words or {})


def _c(name, options, label, default, when, labels=None, imp="primary", help=""):
    return Param.choice(name, options, label=label, group=G, default=default, importance=imp, valid_when=when,
                        labels=labels or {}, help=help)


def _t(name, label, default, when, imp="secondary", help=""):
    return Param.toggle(name, label=label, group=G, default=default, importance=imp, valid_when=when, help=help)


def _size(axis, options, default, when):
    word = "width" if axis == "W" else "height"
    return [_c(f"size{axis}", options, f"{word.capitalize()} mode", default, when, {o: SIZE_WORDS[o] for o in options},
               help=f"Fixed: its own {word}; Fit content: follows what is inside it; Fill: takes the room the parent "
                    f"layout leaves; Percent: a share of the parent's {word}"),
            _n(f"pct{axis}", f"{word.capitalize()} %", 100.0, {"all": [when, IS(f"size{axis}", "percent")]}, hi=100,
               step=1, unit="%", help=f"Its {word} as a share of the parent layout's {word}")]


# A group's sizes: fit needs its own layout, fill / percent a parent layout; fixed is always right.
_GROUP_SIZED = {"any": [ON, IN_LAYOUT]}

GROUP = [
    _c("layout", ["none", "row", "column", "grid", "stack"], "Auto layout", "none", None,
       {"none": "Off", "stack": "Stack"},
       help="Arrange the group's layers in a row, a column, a grid, or stacked on top of each other, again on every "
            "frame (a layer that grows pushes the others along)"),
    _n("gap", "Gap", 16.0, ON, help="Space between layers (between columns in a grid)"),
    _n("padding", "Padding", 10.0, ON, help="Space inside the group's edge, all round"),
    _n("paddingX", "Padding left / right", -1.0, ON, lo=-1, imp="secondary", words={-1.0: "Same as padding"},
       help="Overrides Padding at the left and right (Same as padding: left out)"),
    _n("paddingY", "Padding top / bottom", -1.0, ON, lo=-1, imp="secondary", words={-1.0: "Same as padding"},
       help="Overrides Padding at the top and bottom (Same as padding: left out)"),
    _c("justify", ["start", "center", "end", "between", "around", "evenly"], "Spread", "start", ON,
       {"start": "From the start", "center": "Centred", "end": "To the end", "between": "Space between",
        "around": "Space around", "evenly": "Space evenly"},
       help="Along the row or column (across a stack): where the layers sit and how the room left is shared"),
    _c("align", ALIGNS, "Align", "start", ON, ALIGN_WORDS,
       help="Across the row (or column, or grid cell, or stack): top, middle, bottom, stretched to fill it, or on "
            "the first line of text"),
    _t("wrap", "Wrap", False, FLOW, help="Start a new line when the next layer doesn't fit"),
    _n("columns", "Columns", 3, GRID, lo=1, hi=100, unit="", integer=True),
    Param.text("columnsTemplate", label="Column sizes", group=G, default="", importance="deep", valid_when=GRID,
               help='CSS column sizes ("1fr 2fr 200px", "repeat(3, 1fr)"); empty = Columns equal columns'),
    _n("rowGap", "Line gap", 16.0, {"any": [GRID, {"all": [FLOW, IS("wrap", True)]}]},
       help="Space between wrapped lines (between rows in a grid)"),
    *_size("W", ["fixed", "fit", "fill", "percent"], "fit", _GROUP_SIZED),
    *_size("H", ["fixed", "fit", "fill", "percent"], "fit", _GROUP_SIZED),
    _t("hugPin", "Keep top-left fixed", True, FIT,
       help="A group that fits its content grows right and down from its top-left (left of a row, top of a column), "
            "as a design tool's frame does; off, it grows around its anchor. An anchor you moved off the middle "
            "always keeps its own place."),
]

CHILD_APART = _t("layoutApart", "Set apart", False, IN_LAYOUT, imp="deep",
                 help="Not arranged by the group's layout: placed by its own X and Y (a badge on a card)")
CHILD_GROW = _n("layoutGrow", "Fill space", 0.0, PLACED, lo=0, hi=100, step=0.1, unit="×", imp="secondary",
                help="Takes this share of the room left along the row or column (0 = keeps its own size)")


def _shrink(default):
    return _n("layoutShrink", "Shrink", default, PLACED, lo=0, hi=100, step=0.1, unit="×", imp="deep",
              help="How much it gives up when the row or column is too small (0 = never smaller than its own size)")


CHILD_PLACE = [
    _c("alignSelf", ["auto"] + ALIGNS, "Align itself", "auto", PLACED, {"auto": "As the group", **ALIGN_WORDS},
       imp="deep", help="Its own place across the row or column, instead of the group's Align"),
    _n("margin", "Margin", 0.0, PLACED, lo=-20000, imp="deep", help="Extra space round it, all round"),
    _n("colSpan", "Columns spanned", 1, PLACED, lo=1, hi=100, unit="", integer=True, imp="deep",
       help="In a grid: how many columns it covers"),
    Param.number("shiftX", label="Shift X", group=G, min=-20000, max=20000, step=1, unit="px", default=0.0,
                 importance="secondary", valid_when=PLACED,
                 help="Moves it on top of its laid-out place without pushing the others (animate it for a slide-in)"),
    Param.number("shiftY", label="Shift Y", group=G, min=-20000, max=20000, step=1, unit="px", default=0.0,
                 importance="secondary", valid_when=PLACED,
                 help="Moves it on top of its laid-out place without pushing the others (animate it for a slide-in)"),
]
SIZED = ("shape", "image", "group")      # w, h are animatable fields the layout may set (fill, stretch, fit)
GROWS = SIZED + ("text",)                # a text grows too: its box widens and it wraps there (boxWidth)
SHRINKS = ("text", "group")              # shrink 1 by default (as CSS); shapes, images and the rest keep their size


def child_fields(kind: str) -> list[Param]:
    """A layer type's own layout fields (every layer type but the camera)."""
    out = [CHILD_APART, *CHILD_PLACE, _shrink(1.0 if kind in SHRINKS else 0.0)]
    if kind in GROWS:
        out.append(CHILD_GROW)
    if kind in ("shape", "image"):       # a group's size modes are in GROUP (it also fits its content)
        out += [*_size("W", ["fixed", "fill", "percent"], "fixed", PLACED),
                *_size("H", ["fixed", "fill", "percent"], "fixed", PLACED)]
    return out


# A size the layout sets is absent: a group fitting its content, a layer filling its slot or a share of it.
_SHARED = {a: {"all": [PLACED, {"any": [IS(f"size{A}", "fill"), IS(f"size{A}", "percent")]}]} for a, A in (("w", "W"), ("h", "H"))}
SIZE_SET = {a: {"not": {"any": [{"all": [ON, IS(f"size{A}", "fit")]}, _SHARED[a]]}} for a, A in (("w", "W"), ("h", "H"))}
_BOTH = {"not": {"all": [_SHARED["w"], _SHARED["h"]]}}      # a shape's or an image's Size (W | H) is one setting: one
LAYER_SIZE_SET = {"w": _BOTH, "h": _BOTH}                    # rule for both halves, shown unless the layout sets both
_OWN = {p.name for p in child_fields("shape") + child_fields("text")}


def py_only(kind: str) -> set[str]:
    """The layout fields of an item type, which stay on the Python side (other types' "align" or "gap" are theirs)."""
    return _OWN | {p.name for p in GROUP} if kind == "group" else _OWN
