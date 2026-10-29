"""The script's garment(id, pieces=[…], seams=[…], **fields) (PR7): a sewing pattern made like any mesh (re-run safe: the
same id updates it). Pieces and seams are written as lists here and stored as JSON text (garment.py checks them, loudly,
at the call). It is cloth unless simulate= says off, and it is not set on the ground: its pieces' `at` are in its own
space, which sits at the world's origin unless x / y / z move it (y is a plain height here, as y_world= elsewhere).
"""
from __future__ import annotations

from . import garment


def make(b, id_=None, pieces=(), seams=(), **values):
    pieces, seams = list(pieces), list(seams)
    try:
        garment.check(pieces, seams)
    except garment.PatternError as e:
        raise ValueError(f"garment({id_!r}): {e}") from e
    values.setdefault("simulate", "cloth")
    values["y_world"] = values.pop("y", values.pop("y_world", 0.0))
    return b.item("mesh", id_, shape="pattern", pieces=garment.text(pieces), seams=garment.text(seams), **values)
