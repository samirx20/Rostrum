"""Plain words for instruments (no Qt): an instrument's own name spaced out, and the family a played (procedural)
instrument belongs to. Used by the Sounds panel's list (adder.py)."""
from __future__ import annotations

import re
from pathlib import Path

# Plain words for a procedural instrument (its `model` field); an unknown one is just its own name, spaced out.
FAMILY = {"guitar": "Steel-string pluck", "nylonGuitar": "Soft nylon pluck", "violin": "Bowed string",
          "marimba": "Struck bar", "vibraphone": "Struck bar", "glockenspiel": "Struck bar", "tubularBell": "Struck bar"}


def spaced(name: str) -> str:
    """"grandPiano" -> "Grand piano"; "Violin_Section.sfz" -> "Violin Section"."""
    stem = Path(str(name).replace("\\", "/")).stem if str(name).lower().endswith(".sfz") else str(name)
    words = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", stem).replace("_", " ").strip()
    return words[:1].upper() + words[1:]
