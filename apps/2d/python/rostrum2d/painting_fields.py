"""A painting's own fields (paintings.py): its size, whether it tiles without a seam, and how its drawings run. Its
strokes are the painting kit's canvas, held in `frames` exactly as on a drawing (kind.py). Never keyed: a painting is
what is painted, not a moment."""
from __future__ import annotations

from rostrum_core import Param

from . import looping
from .paint_fields import EACH_FRAME_HELP, _new_hold

G = "Painting"
FIELDS = [
    Param.text("name", label="Name", group=G, default="Painting", importance="primary"),
    Param.number("w", label="Width", group=G, min=1, max=8192, step=1, unit="px", integer=True, default=512, importance="primary",
                 help="The painting's size in px; strokes keep their px, from the top-left"),
    Param.number("h", label="Height", group=G, min=1, max=8192, step=1, unit="px", integer=True, default=512, importance="primary"),
    Param.toggle("seamless", label="Seamless", group=G, default=False, importance="primary",
                 help="On: paint that crosses an edge comes back on the opposite side, so tiles always meet (strokes "
                      "already painted stay as they are)"),
    Param.toggle("eachFrame", label="Draw each frame", group=G, default=False, importance="secondary", help=EACH_FRAME_HELP),
    _new_hold(G, {"is": ["eachFrame", True]}),
    Param.choice("loop", ["loop", "pingpong"], label="Loop", group=G, default="loop", importance="secondary",
                 valid_when={"is": ["eachFrame", True]}, labels={"loop": "Loop", "pingpong": "Ping-pong"},
                 help="A painted fill never runs out: its drawings repeat, start again or back and forth"),
]
