"""The camera's fields (apps/2d/CAMERA.md). The Rust engine reads the same names and kinds (engine/render/src/camera/
mod.rs `FIELDS`), so change both together. Merged into `rostrum2d.fields.FIELDS` and `LABELS`. A camera has no
transform of its own: its x, y are where it looks, not where it is placed. Every field can be keyed except start/end."""
from __future__ import annotations

from ..fields import N, P, S  # noqa: F401  (the table helpers)

FIELDS = {
    "camera": [
        N("x", "Looks at X", "Camera", -20000, 20000, 1, "px", P, default=960.0,
          help="The point of the composition shown at the centre of the screen; the centre of the composition = at rest"),
        N("y", "Looks at Y", "Camera", -20000, 20000, 1, "px", P, default=540.0),
        N("zoom", "Zoom", "Camera", 0.01, 100, 0.01, "×", P, default=1.0,
          help="2 = twice as close; far layers (depth) grow less"),
        N("rotation", "Roll", "Camera", -36000, 36000, 0.1, "°", S, help="Turns the camera clockwise, so the picture turns the other way"),
        N("start", "Starts at", "Timing", 0, 36000, 0.01, "s", S, help="From this time this camera is the one used (a cut)"),
        N("end", "Ends at", "Timing", 0, 36000, 0.01, "s", S, default=36000.0, help="From this time it isn't",
          words={36000.0: "End of comp"}),
    ],
}
LABELS = {"camera": "Camera"}
STILL: dict = {}
