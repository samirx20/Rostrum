"""What a swap set's drawings are, read from their names (UX_SPEC 3.23 › Lip sync, Blinks): which mouth shape each
mouth drawing is ("mouth A" -> D wide open, "mouth M B P" -> A closed, "rest" -> X), which eye drawing is closed, and
whether a set is a mouth or a pair of eyes (the context bar offers Lip sync… or Add blinks… by it). Pure; no Qt.
The nine shapes and their words are lipsync's own (rostrum2d.lipsync.visemes.SHAPES, lipsync.ops.WORDS).
"""
from __future__ import annotations

from rostrum2d.lipsync.ops import WORDS
from rostrum2d.lipsync.visemes import SHAPES
from rostrum2d.names import display_name
from rostrum2d.rig.bodynames import tokens

NOISE = {"mouth", "mouths", "lip", "lips", "shape", "viseme", "face"}
# whole name (its words run together) first, then any one word; first match wins
WHOLE = {"mbp": "A", "fv": "G", "wq": "F", "oo": "F", "ee": "B", "ai": "D", "ah": "D", "aa": "D", "eh": "C", "th": "H"}
WORD = [("X", {"rest", "neutral", "idle", "x", "default", "silent"}),
        ("A", {"m", "b", "p", "closed", "close", "shut"}),
        ("G", {"f", "v", "teeth"}),
        ("H", {"l", "tongue"}),
        ("F", {"w", "q", "u", "pucker", "puckered", "kiss"}),
        ("E", {"o", "round", "rounded", "oh"}),
        ("B", {"e", "i", "smile", "s"}),
        ("C", {"c", "ae", "open"}),
        ("D", {"a", "wide", "big", "yell"})]


def shape_of(name: str) -> str:
    """The mouth shape a drawing's name says ("" when it says none)."""
    words = [w for w in tokens(name) if w not in NOISE]
    whole = "".join(words)
    if whole in WHOLE:
        return WHOLE[whole]
    return next((s for s, says in WORD if any(w in says for w in words)), "")


def guess(kids: list[dict]) -> dict[str, str]:
    """{shape: drawing id} from the drawings' names; the first drawing that says a shape takes it."""
    out = {}
    for k in kids:
        s = shape_of(display_name(k))
        if s and s not in out:
            out[s] = k["id"]
    return out


def rows(kids: list[dict], chosen: dict[str, str]) -> list[dict]:
    """One row per mouth shape: {shape, words, layer ("" = shows the nearest shape given), options}."""
    options = [{"value": "", "label": "Nearest given"}] + [{"value": k["id"], "label": display_name(k)} for k in kids]
    return [{"shape": s, "words": WORDS[s], "layer": chosen.get(s, ""), "options": options} for s in SHAPES]


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
