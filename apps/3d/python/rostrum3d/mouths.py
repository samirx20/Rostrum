"""What a mouth is in 3D (SPEC §9 Lip sync): a group whose children are the mouth shapes, one child per shape of the
shared table (rostrum_core.lipsync: X rest · A closed · B … H tongue up). Which child is which shape is read from its
name, else its id ("mouth_rest", "mouth_closed", "mouth_wide", "M B P"; as in 2D, a lone letter is the sound: "mouth A" is the wide AH); `lipsync.make` takes `shapeX` … `shapeH` to say it outright.
Pure: no Qt, no document changes.
"""
from __future__ import annotations

from rostrum_core.lipsync import mouths as M

from . import fields as F

SHOWS = ("sx", "sy", "sz")                  # a shape shows at its own Scale and is hidden by scaling it to nothing (HIDDEN)
HIDDEN = 1e-4                               # not 0: a zero matrix has no normals to light; 0.1 mm at 1 m can't be seen


def kids(item: dict) -> list[dict]:
    """The children that can be shown and hidden by Scale (a mesh, group, combine, import, rig)."""
    return [c for c in item.get("children", []) if c.get("type") in F.ITEMS and {*SHOWS} <= set(F.animatable(c["type"]))]


def shape_of_child(child: dict) -> str:
    return M.shape_of(str(child.get("name") or "")) or M.shape_of(child["id"])


def guess(item: dict) -> dict[str, str]:
    """{shape: child id}: the first child that says a shape takes it."""
    out = {}
    for c in kids(item):
        s = shape_of_child(c)
        if s and s not in out:
            out[s] = c["id"]
    return out


def is_mouth(item: dict) -> bool:
    """A group named like a mouth with shapes in it, or one with two or more children that name different shapes."""
    if item.get("type") != "group":
        return False
    found = guess(item)
    named = bool({"mouth", "mouths", "lips"} & set(M.tokens(str(item.get("name") or "") + " " + item["id"])))
    return len(found) >= (1 if named else 2)
