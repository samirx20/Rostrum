"""PDF text runs → text layers per line. Many PDFs (printed from a browser or an office program) put every letter or word
in its own text object; making a layer of each would leave a page of one-letter layers. Text objects that follow each
other in painting order, in the same style, on the same baseline and close together are one line: one text layer, with a
space where there was a gap. The PDF's own order and positions decide; nothing is guessed from the words.
"""
from __future__ import annotations

SAME_STYLE = ("font", "weight", "slant", "color", "align")
BASELINE = 0.15       # of the font size: how far two runs' baselines may differ and still be one line
SPACE = 0.2           # of the font size: a gap wider than this is a space
REACH = 3.0           # of the font size: a gap wider than this starts a new run (a column, a tab stop)
OVERLAP = 0.3         # of the font size: how far a run may reach back over the one before (kerning)


def _continues(a: dict, b: dict) -> bool:
    pa, pb = a["props"], b["props"]
    size = pa["size"]
    if any(pa.get(k) != pb.get(k) for k in SAME_STYLE) or abs(pa["size"] - pb["size"]) > 0.02 * size:
        return False
    if abs(a["origin"][1] - b["origin"][1]) > BASELINE * size or "\n" in pa["body"] or "\n" in pb["body"]:
        return False
    gap = b["box"][0] - (a["box"][0] + a["box"][2])
    return -OVERLAP * size <= gap <= REACH * size


def _join(a: dict, b: dict) -> None:
    """b's text goes on the end of a's line."""
    pa, size = a["props"], a["props"]["size"]
    gap = b["box"][0] - (a["box"][0] + a["box"][2])
    spaced = pa["body"].endswith(" ") or b["props"]["body"].startswith(" ")
    pa["body"] += ("" if spaced or gap <= SPACE * size else " ") + b["props"]["body"]
    x0, y0 = min(a["box"][0], b["box"][0]), min(a["box"][1], b["box"][1])
    x1, y1 = max(a["box"][0] + a["box"][2], b["box"][0] + b["box"][2]), max(a["box"][1] + a["box"][3], b["box"][1] + b["box"][3])
    a["box"] = [x0, y0, x1 - x0, y1 - y0]
    a["name"] = pa["body"].strip()[:30]


def lines(items: list) -> list:
    """[(node, clips)] in painting order → the same with each line's text runs made one text node (clips must match)."""
    out: list = []
    for node, clips in items:
        if out and node["type"] == "text" and out[-1][0]["type"] == "text" and out[-1][1] == clips and _continues(out[-1][0], node):
            _join(out[-1][0], node)
        else:
            out.append((node, clips))
    for node, _ in out:
        node.pop("origin", None)
    return out
