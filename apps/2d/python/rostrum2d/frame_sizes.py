"""The named frame sizes, one list of data: Scene settings' Size choice (screen2d/size_rows.py) and the agents' `comp.size`
(ops_frame.py) both read it. The numbers stay typeable (the scene's own Width and Height)."""
from __future__ import annotations

# id, name, width, height. The first is the new scene's default shape (files2d.BLANK).
SIZES = [
    ("wide", "Wide 16:9", 1920, 1080),
    ("uhd", "4K 16:9", 3840, 2160),
    ("vertical", "Vertical 9:16", 1080, 1920),
    ("square", "Square 1:1", 1080, 1080),
    ("post", "Post 4:5", 1080, 1350),
]
IDS = [s[0] for s in SIZES]


def label(size: tuple) -> str:
    """The name alone: Width and Height sit right under the choice, and a narrow panel would cut the numbers off."""
    return size[1]


def named(w: float, h: float) -> str | None:
    """The id of the named size that is exactly w × h, else None (a custom size)."""
    return next((s[0] for s in SIZES if (s[2], s[3]) == (round(w), round(h))), None)


def get(size_id: str) -> tuple:
    return next(s for s in SIZES if s[0] == size_id)


def options(w: float, h: float) -> list[dict]:
    """Choice options for a scene of w × h: the named sizes, plus its own numbers first when none matches."""
    out = [{"value": s[0], "label": label(s)} for s in SIZES]
    if named(w, h) is None:
        out.insert(0, {"value": "custom", "label": "Custom"})
    return out
