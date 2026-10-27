"""The frame's fields (apps/2d/FRAME.md). The Rust engine reads the same names and kinds (engine/render/src/frame/
mod.rs `FIELDS`), so change both together. Merged into `rostrum2d.fields.FIELDS` and `LABELS`. Its x, y are the
world point at the frame's centre, not where a box is placed. Every field can be keyed except home (written when the
scene is made, changed by nothing else) and the ride's path and where on it. Depth of field (`dof`, then `focus` and
`focusBlur` keyed like the rest): engine/render/src/frame/mod.rs `Dof`."""
from __future__ import annotations

from ..fields import D, IS, N, P, RIDE, T

FIELDS = {
    "camera": [
        N("x", "X", "Frame", -1000000, 1000000, 1, "px", P, default=960.0,
          help="The world point at the frame's centre: move it to move the shot"),
        N("y", "Y", "Frame", -1000000, 1000000, 1, "px", P, default=540.0),
        N("zoom", "Zoom", "Frame", 0.01, 100, 0.01, "×", P, default=1.0,
          help="How close the frame looks: 2 = twice as close; far layers (depth) grow less"),
        N("rotation", "Rotation", "Frame", -36000, 36000, 0.1, "°", P,
          help="Turns the frame clockwise, so the picture turns the other way"),
        N("homeX", "Home X", "Home", -1000000, 1000000, 1, "px", D, default=960.0,
          help="Where the frame's centre was when the scene was made: there every layer shows as placed, at any depth"),
        N("homeY", "Home Y", "Home", -1000000, 1000000, 1, "px", D, default=540.0),
        T("dof", "Depth of field", "Focus", False, P,
          help="Blurs each layer by how far its depth is from the focus depth, as a lens does"),
        N("focus", "Focus depth", "Focus", -0.99, 1000, 0.01, "", P, IS("dof", True),
          help="The depth that is sharp: 0 = the layers as placed, higher = further back (the layers' Depth)"),
        N("focusBlur", "Blur", "Focus", 0, 500, 0.5, "px", P, IS("dof", True), default=20.0,
          help="How soft a layer far behind the focus gets; one as far in front (twice as near) gets as much"),
        *RIDE,      # the frame rides a path as a layer does (layer.ride): its centre sits on the path
        T("locked", "Locked", "Frame", False, D, help="Locked: drags and operations refuse to move the frame until it is unlocked"),
    ],
}
LABELS = {"camera": "Frame"}
STILL = {"camera": {"homeX", "homeY"}}
FIXED = {"camera": {"homeX", "homeY"}}
# An engine older than its frame fields refuses them: a new field the engine can't read yet is listed here by type, so
# the scene keeps it back until the engine is built.
NOT_IN_ENGINE_YET: dict = {}     # fields the scene keeps from the engine until it can read them (none now)
