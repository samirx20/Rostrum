"""Paint on an element (UX_SPEC.md §3.8, §3.9): the fields a painted shape, text, picture or path carries, and a
drawing's "Draw each frame". The paint itself is the element's `frames` (painting-kit canvases, kind.py); these
fields only say how it sits on the element. Python-side: scene.py sends the paint as `node["paint"]` instead.

Rule of individuality: the Paint group appears only once the element holds paint (the `hasPaint` fact, kind.py).
"""
from __future__ import annotations

from rostrum_core import Param

TYPES = ("shape", "text", "image", "video", "path")      # elements that may hold paint (a drawing is only paint)
HAS_PAINT = {"fact": "hasPaint"}
G = "Paint"

EACH_FRAME_HELP = "On: each frame can have its own drawing (hand-drawn animation; Alt+N adds the next). Off: one painting"

ELEMENT = [
    Param.toggle("paintInside", label="Inside the outline", group=G, default=True, importance="secondary",
                 valid_when=HAS_PAINT, help="On: the paint shows only where the element itself is drawn. Off: it covers the whole box"),
    # Valid before any paint (an animation starts on an empty element: the first stroke makes drawing 1 at the
    # playhead); the brush panel's "Painting on" is its one place, so the inspector never lists it (shown="script").
    Param.toggle("eachFrame", label="Draw each frame", group=G, default=False, importance="secondary",
                 shown="script", help=EACH_FRAME_HELP),
    Param.number("paintW", label="Paint width", group=G, min=0, max=8192, step=1, unit="px", integer=True, default=0,
                 importance="deep", valid_when=HAS_PAINT,
                 help="The paint's own size in px, set by the first stroke from the element's box; it is stretched over the box"),
    Param.number("paintH", label="Paint height", group=G, min=0, max=8192, step=1, unit="px", integer=True, default=0,
                 importance="deep", valid_when=HAS_PAINT),
]
DRAWING = [Param.toggle("eachFrame", label="Draw each frame", group="Drawing", default=False, importance="secondary",
                        help=EACH_FRAME_HELP)]


def _new_hold(group, when):
    return Param.number("newHold", label="New ones hold", group=group, min=1, max=4, step=1, unit="frames", integer=True,
                        default=2, importance="secondary", valid_when=when,
                        help="How many frames a new drawing is held (1: on ones, 2: on twos …); frame.add uses it when "
                             "its frame is left out")


ELEMENT.append(_new_hold(G, {"all": [HAS_PAINT, {"is": ["eachFrame", True]}]}))
DRAWING.append(_new_hold("Drawing", {"is": ["eachFrame", True]}))
NAMES = {p.name for p in ELEMENT}          # never sent to the engine (scene.python_only); paintW / paintH are still
