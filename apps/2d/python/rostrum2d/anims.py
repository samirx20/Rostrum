"""2D's names for its settings (SPEC §9.3), for the shared animation reading (rostrum_core.keys.anims: anim.list and
the timeline's stretches and lines). X and Y of Position (W and H of Size, …) are one setting.
"""
from __future__ import annotations

from rostrum_core.keys import anims as core

from . import fields as F

PAIRS = {"position": ("x", "y"), "size": ("w", "h"), "anchor": ("anchorX", "anchorY"), "stretch": ("scaleX", "scaleY"),
         "tilt": ("tiltX", "tiltY")}
LABELS = {"position": "Position", "size": "Size", "anchor": "Anchor", "stretch": "Stretch", "tilt": "Tilt"}
# the plain word a person says for an animation (SPEC §9.3); any other setting goes by its own name
WORDS = {"position": "Move", "scale": "Scale", "stretch": "Scale", "rotation": "Turn", "opacity": "Fade", "size": "Size",
         "fill": "Colour", "color": "Colour", "d": "Shape", "blur": "Blur", "pathOffset": "Draw on", "rideAlong": "Follow"}


def _label(owner: dict, setting: str) -> str | None:
    p = F.param(owner["type"], setting)
    return p.label if p else None


NAMES = core.Names(PAIRS, LABELS, WORDS, _label)
setting_of = NAMES.setting_of


def animations(owner: dict, markers: dict | None = None, origin: float = 0.0) -> list[dict]:
    """A layer's (effect's, mask's) animations in 2D's names: rostrum_core.keys.anims.animations."""
    return core.animations(owner, NAMES, markers, origin)
