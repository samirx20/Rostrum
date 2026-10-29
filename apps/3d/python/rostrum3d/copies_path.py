"""Copies along a path (layout `path`): the path item is a text, svg or path2d mesh, and its outlines are the path. The
compiler works its points out once, here: every contour of the outline (each shape's outer and its holes, a word's every
letter) on the item's flat XY plane, carried into the world by the path item's place at the shot's first frame, then into
the copies item's own space. The core spreads the copies over all of them by length (ENGINE_CONTRACT § 2, Copies).
"""
from __future__ import annotations

from . import aim, copies_fields, outline as outlines


def points(item: dict, fr) -> tuple[list[list[list[float]]], list[bool]]:
    """(pathPoints, pathClosed) of a copies item laid out along its path: one list of [x, y, z] per contour, in the copies
    item's space, and whether each closes on itself (an outline's contours always do)."""
    why = copies_fields.path_problem(item, fr.items)
    if why:
        raise ValueError(f'{item["id"]}: {why}')
    path, first = item["path"], fr.frames[0]
    shapes = outlines.for_item({**fr.values(path, first), "id": path}, fr.folder)
    to_copies = aim.invert(fr.world(item["id"], first))
    placed = aim.compose(to_copies, fr.world(path, first))
    contours = [[[round(v, 6) for v in aim.point(placed, [x, y, 0.0])] for x, y in c]
                for shape in shapes for c in (shape["outer"], *shape["holes"])]
    if not contours:
        raise ValueError(f'{item["id"]}: its path "{path}" has no outline yet (empty words or drawing)')
    return contours, [True] * len(contours)
