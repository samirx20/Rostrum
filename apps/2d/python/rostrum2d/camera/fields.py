"""The camera's fields (CAMERA.md). STUB by the lead; member A owns it. Merged into `rostrum2d.fields.FIELDS`."""
from __future__ import annotations

from ..fields import N, S  # noqa: F401  (the table helpers)

FIELDS = {
    "camera": [
        N("x", "Looks at X", "Camera", -20000, 20000, 1, "px", default=960.0),
        N("y", "Looks at Y", "Camera", -20000, 20000, 1, "px", default=540.0),
        N("zoom", "Zoom", "Camera", 0.01, 100, 0.01, "×", default=1.0),
        N("rotation", "Roll", "Camera", -36000, 36000, 0.1, "°"),
        N("start", "Starts at", "Timing", 0, 36000, 0.01, "s", S),
        N("end", "Ends at", "Timing", 0, 36000, 0.01, "s", S, default=36000.0),
    ],
}
LABELS = {"camera": "Camera"}
STILL: dict = {}
