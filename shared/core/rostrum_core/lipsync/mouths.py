"""Which mouth shape an item is, read from its name ("mouth A" -> D wide open, "mouth M B P" -> A closed, "rest" -> X),
and a plain-words label for each of the nine shapes. Shared by 2D (a swap set's drawings) and 3D (a mouth group's
meshes). Pure; no Qt.
"""
from __future__ import annotations

from ..names import tokens
from .visemes import SHAPES

WORDS = {"X": "rest", "A": "closed (M B P)", "B": "slightly open", "C": "open", "D": "wide open", "E": "rounded",
         "F": "puckered (OO W)", "G": "teeth on lip (F V)", "H": "tongue up (L)"}
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
    """The mouth shape a name says ("" when it says none)."""
    words = [w for w in tokens(name) if w not in NOISE]
    whole = "".join(words)
    if whole in WHOLE:
        return WHOLE[whole]
    return next((s for s, says in WORD if any(w in says for w in words)), "")


def guess(named: list[tuple[str, str]]) -> dict[str, str]:
    """{shape: id} from (id, name) pairs; the first one that says a shape takes it."""
    out = {}
    for id_, name in named:
        s = shape_of(name)
        if s and s not in out:
            out[s] = id_
    return out


def rows(named: list[tuple[str, str]], chosen: dict[str, str]) -> list[dict]:
    """One row per mouth shape for a sheet: {shape, words, layer ("" = shows the nearest shape given), options}."""
    options = [{"value": "", "label": "Nearest given"}] + [{"value": i, "label": n} for i, n in named]
    return [{"shape": s, "words": WORDS[s], "layer": chosen.get(s, ""), "options": options} for s in SHAPES]


__all__ = ["SHAPES", "WORDS", "shape_of", "guess", "rows"]
