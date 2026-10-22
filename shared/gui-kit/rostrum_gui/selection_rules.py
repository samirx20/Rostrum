"""How a click, a box and Esc change the selection (INTERACTION.md 1.3), as pure functions every app's screen calls.

Each place keeps its native habit. Lists and timelines (layer rows, tracks, notes, clips, keys) follow Windows and
every file manager: Ctrl toggles one, Shift picks the run from the last clicked. Canvases and the 3D view follow Figma
and Illustrator: a click picks the outer group, Ctrl the deepest piece, Shift toggles. Selecting is never a change
(not an undo step, not saved), so nothing here touches a document: ids in, ids out.

`mods` is any collection of modifier names ("ctrl", "shift", "alt"; any case). A canvas hit is (outer, deepest).
"""
from __future__ import annotations

PLACES = ("list", "canvas")


def _mods(mods) -> set[str]:
    return {m.lower() for m in mods or ()}


def _place(place):
    if place not in PLACES:
        raise ValueError(f'place must be "list" or "canvas", not {place!r}')


def _toggle(ids, one):
    return [i for i in ids if i != one] if one in ids else [*ids, one]


def _union(ids, more):
    return list(dict.fromkeys([*ids, *more]))


def click(ids, anchor, hit, mods, place, order=()):
    """(new ids, new anchor) after a click. `hit`: the id under the pointer (list) or (outer, deepest) (canvas);
    falsy for empty space, which clears unless a modifier is held. `order`: the list's ids top to bottom (or in
    time on a row), for Shift's run."""
    _place(place)
    m, ids = _mods(mods), list(ids)
    if not hit:
        return (ids, anchor) if m & {"ctrl", "shift"} else ([], None)
    if place == "canvas":
        outer, deepest = hit
        if "ctrl" in m:
            return [deepest], deepest
        if "shift" in m:
            return _toggle(ids, outer), outer
        return [outer], outer
    if "ctrl" in m:
        return _toggle(ids, hit), hit
    if "shift" in m and anchor in order and hit in order:
        a, b = sorted((list(order).index(anchor), list(order).index(hit)))
        return list(order)[a:b + 1], anchor
    return [hit], hit


def box(ids, touched, mods, place):
    """The ids after a box drag on empty space. List: `touched` ids; Ctrl adds. Canvas: `touched` is
    [(outer, deepest)]; Shift adds the outer ones, Ctrl picks the deepest pieces."""
    _place(place)
    m = _mods(mods)
    if place == "list":
        return _union(ids, touched) if "ctrl" in m else _union([], touched)
    if "ctrl" in m:
        return _union([], [d for _, d in touched])
    outers = [o for o, _ in touched]
    return _union(ids, outers) if "shift" in m else _union([], outers)


def select_all(ids_in_focused_place) -> list:
    """Ctrl+A: everything of that kind in the focused place (the caller knows the place)."""
    return list(dict.fromkeys(ids_in_focused_place))


ESC_LADDER = (
    ("cancel", ("dragging", "typing")),          # a drag or typing in progress
    ("close", ("popover", "menu", "sheet")),     # an open popover, menu or sheet
    ("clear_inner", ("inner",)),                 # keys or points selected inside an item
    ("clear", ("selected",)),                    # items selected
    ("leave_group", ("entered",)),               # inside a group
)


def esc_step(state: dict):
    """The one step Esc takes now, one level per press: "cancel", "close", "clear_inner", "clear", "leave_group",
    or None. `state`: booleans named in ESC_LADDER (missing = False)."""
    return next((step for step, flags in ESC_LADDER if any(state.get(f) for f in flags)), None)
