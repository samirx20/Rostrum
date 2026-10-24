"""3D's names for its settings (SPEC §9), for the shared animation reading (rostrum_core.keys.anims: anim.list, the
timeline's stretches and lines, the picked stretch's panel). X, Y and Z of Position are one setting, a "Move"; Turn
X / Y / Z one "Turn"; Scale X / Y / Z one "Scale". Every other field goes by its own label (fields.py).
"""
from __future__ import annotations

from rostrum_core.keys import anims as core

from . import fields as F

PAIRS = {"position": ("x", "y", "z"), "turn": ("rx", "ry", "rz"), "scale": ("sx", "sy", "sz")}
WORDS = {"position": "Move", "turn": "Turn", "scale": "Scale"}
GROUP_LABELS = {"position": "Position", "turn": "Turn", "scale": "Scale"}


def _label(owner: dict, setting: str) -> str | None:
    """A setting's label: one keyed axis of Position / Turn / Scale by its own name ("Turn X"), several by the group's
    ("Turn"); any other field by its label."""
    if setting in PAIRS:
        keyed = [p for p in PAIRS[setting] if any(k.get("prop") == p for k in owner.get("keys", []))]
        p = F.param(owner["type"], keyed[0]) if len(keyed) == 1 else None
        return p.label if p else GROUP_LABELS[setting]
    p = F.param(owner["type"], setting)
    return p.label if p else None


NAMES = core.Names(PAIRS, {}, WORDS, _label)


def animations(owner: dict) -> list[dict]:
    """A scene item's animations in 3D's names (rostrum_core.keys.anims.animations; times in document seconds)."""
    return core.animations(owner, NAMES)
