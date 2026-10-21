"""The blend modes, read from blends.txt beside this file: the one list the engine also compiles in
(engine/render/src/scene/blends.rs). A bad line fails the import, naming the line."""
from __future__ import annotations

from pathlib import Path

FILE = Path(__file__).with_name("blends.txt")


def _read() -> list[tuple[str, str, int, str]]:
    rows = []
    for n, line in enumerate(FILE.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        cols = [c.strip() for c in line.split(" | ")]
        if len(cols) != 4 or not cols[3] or not cols[2].isdigit():
            raise ValueError(f"{FILE} line {n}: expected 'name | css | lottie number | label', got {line!r}")
        rows.append((cols[0], cols[1], int(cols[2]), cols[3]))
    return rows


ROWS = _read()
BLENDS = [r[0] for r in ROWS]                    # the `blend` field's options, in the inspector's order
LABELS = {r[0]: r[3] for r in ROWS}               # what the inspector shows
CSS = {r[0]: r[1] for r in ROWS}                  # the painter's mix-blend-mode
LOTTIE = {r[0]: r[2] for r in ROWS}               # Lottie's `bm` number
# Photoshop's and Figma's names (MULTIPLY, COLOR_DODGE …; "Linear dodge" is our add, "Pass through" is normal).
DESIGN_APPS = {**{n.upper().replace("-", "_"): n for n in BLENDS if n != "add"}, "LINEAR_DODGE": "add", "PASS_THROUGH": "normal"}
