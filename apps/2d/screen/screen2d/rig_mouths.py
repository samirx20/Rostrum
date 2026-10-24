"""What a swap set's drawings are, read from their names (UX_SPEC 3.23 › Lip sync, Blinks): which mouth shape each
mouth drawing is ("mouth A" -> D wide open, "mouth M B P" -> A closed, "rest" -> X), which eye drawing is closed, and
whether a set is a mouth or a pair of eyes (the context bar offers Lip sync… or Add blinks… by it). Pure; no Qt.
The nine shapes and their words are lipsync's own (rostrum_core.lipsync.mouths: SHAPES, WORDS, shape_of, guess).
"""
from __future__ import annotations

from rostrum_core.lipsync import mouths
from rostrum2d.names import display_name
from rostrum_core.names import tokens


def guess(kids: list[dict]) -> dict[str, str]:
    """{shape: drawing id} from the drawings' names; the first drawing that says a shape takes it."""
    return mouths.guess([(k["id"], display_name(k)) for k in kids])


def _says(item: dict, words: set) -> bool:
    return bool(words & set(tokens(display_name(item))))


def is_mouth(item: dict) -> bool:
    """A swap set named like a mouth, or two or more of whose drawings name a mouth shape."""
    if not item.get("swap") or is_eyes(item):
        return False
    return _says(item, {"mouth", "mouths", "lip", "lips"}) or len(guess(item.get("layers", []))) >= 2


def closed_of(kids: list[dict]) -> tuple[str, str, str]:
    """(open, closed, half) drawing ids of an eyes set from their names (closed: "closed", "shut", "blink"; half:
    "half"); without names saying so the first drawing is open and the last closed."""
    closed = next((k["id"] for k in kids if _says(k, {"closed", "shut", "blink", "close"})), kids[-1]["id"] if kids else "")
    half = next((k["id"] for k in kids if _says(k, {"half"}) and k["id"] != closed), "")
    opened = next((k["id"] for k in kids if _says(k, {"open"}) and k["id"] not in (closed, half)),
                  next((k["id"] for k in kids if k["id"] not in (closed, half)), ""))
    return opened, closed, half


def is_eyes(item: dict) -> bool:
    """A swap set named like eyes, or with a drawing named closed / shut / blink."""
    kids = item.get("layers", [])
    return bool(item.get("swap")) and len(kids) >= 2 and (
        _says(item, {"eye", "eyes", "blink", "lids"}) or any(_says(k, {"closed", "shut", "blink"}) for k in kids))
