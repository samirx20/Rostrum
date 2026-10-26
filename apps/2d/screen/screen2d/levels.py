"""The layers at one level, in the layer list's order (the top of the list first): what Tab, Shift+Tab, Enter and Shift+Enter walk.
`parent` is the open group, or the scene. Hidden and locked layers are in it (the list picks them too); the scene's frame is not
(Ctrl+A leaves it out as well). No Qt."""
from __future__ import annotations

from . import picking


def siblings(doc, parent: str) -> list[str]:
    """The ids of `parent`'s layers, top of the list first."""
    return [c["id"] for c in reversed(doc.item(parent).get("layers", [])) if c["type"] != "camera"]


def level_of(doc, picked: list[str], scene: str) -> list[str]:
    """Ctrl+A: every layer at the level the first picked layer is in (a group's layers once you are inside it); with nothing
    picked, the scene's."""
    return siblings(doc, doc.parent_of(picked[0])[0] if picked else scene)


def next_to(doc, picked: list[str], sign: int, scene: str) -> str:
    """Tab (sign 1) or Shift+Tab (-1) from the last picked layer, at its level, wrapping round; with nothing picked the scene's
    first (its last for Shift+Tab). "" when the level is empty."""
    row = siblings(doc, doc.parent_of(picked[-1])[0] if picked else scene)
    if not row:
        return ""
    if not picked or picked[-1] not in row:
        return row[0] if sign > 0 else row[-1]
    return row[(row.index(picked[-1]) + sign) % len(row)]


def first_child(doc, layer: str) -> str:
    """Enter on a group: the layer at the top of its list ("" for anything else, or an empty group)."""
    return next(iter(siblings(doc, layer)), "") if doc.item(layer)["type"] == "group" else ""


def parent_group(doc, layer: str) -> str:
    """Shift+Enter: the group the layer is in ("" at the top of the scene)."""
    return next(iter(reversed(picking.groups_of(doc, layer))), "")
