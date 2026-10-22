"""Shutter (motion blur) and the trail / smear effects (apps/2d/MOTION.md). Merged into `rostrum2d.fields`.
The engine checks the same names and kinds (engine `src/motion/mod.rs`); change both together."""
from __future__ import annotations

from rostrum_core import Param

from ..fields import D, IS, N, P, S, T  # noqa: F401  (the table helpers)

# The composition's shutter. Never keyed (a composition's fields describe it, not a moment).
COMP = [
    N("shutter", "Motion blur", "Motion blur", 0, 720, 1, "°", S, words={0.0: "Off"},
      help="Shutter angle: how long each frame's shutter stays open, in degrees of a frame. 0 = no blur, "
           "180 = half a frame (the film look), 360 = a whole frame"),
    N("shutterSamples", "Blur steps", "Motion blur", 2, 64, 1, "", D, {"not": IS("shutter", 0)}, integer=True, default=8,
      help="How many moments inside the open shutter are drawn and averaged. More = smoother blur on fast moves, "
           "and each frame takes about that many times longer"),
]

FIELDS = {
    # Echo copies of the layer drawn behind it: the layer itself as it was a few frames earlier, each fainter.
    "trail": [
        N("copies", "Copies", "Trail", 1, 32, 1, "", integer=True, default=4, help="How many echoes follow the layer"),
        N("spacing", "Spacing", "Trail", 0.25, 30, 0.25, "f", default=2.0,
          help="Frames between one echo and the next (each echo is the layer this much earlier)"),
        N("fade", "Fade", "Trail", 0, 1, 0.01, "", default=0.6,
          help="Each echo's opacity is the one before times this: 1 = all as strong as the layer, 0.5 = halving"),
    ],
    # The layer stretched along the way it is moving (an animator's smear frame), measured from its real motion.
    "smear": [
        N("amount", "Amount", "Smear", 0, 10, 0.01, "", default=1.0,
          help="How much it stretches per px moved: 1 = a move of its own length in one frame doubles it"),
        N("max", "Longest", "Smear", 1, 20, 0.1, "×", default=4.0, help="The most it ever stretches, times its length"),
        N("minSpeed", "Starts at speed", "Smear", 0, 2000, 0.5, "px/f", S, default=2.0,
          help="Moves slower than this (px per frame) don't smear; faster moves smear by the speed above it"),
        Param.choice("stretch", ["behind", "both"], label="Stretches", group="Smear", default="behind", importance=S,
                     labels={"behind": "Behind it", "both": "Both ways"},
                     help="Behind it: the front edge stays put and the smear trails back along the path. "
                          "Both ways: it stretches about its anchor"),
        T("keepArea", "Thins as it stretches", "Smear", True, S,
          help="Gets narrower across the motion as it gets longer, so it keeps its area"),
    ],
}
EFFECTS = ("trail", "smear")
LABELS = {"trail": "Trail", "smear": "Smear"}
STILL = {"trail": {"copies"}}
