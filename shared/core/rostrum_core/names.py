"""Words of a name, for guessing what an item is from what it is called (body parts in 2D, mouth shapes in 2D and 3D)."""
from __future__ import annotations

import re


def tokens(name: str) -> list[str]:
    """Lower-case words of a name: camelCase, _ - . and digits split ("leftUpperArm_2" -> left upper arm 2)."""
    spaced = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", name)
    return [w for w in re.split(r"[^a-z0-9]+", spaced.lower()) if w]
