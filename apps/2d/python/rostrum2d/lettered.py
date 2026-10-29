"""Painted words count as text for the checks. paint.letters (and letters() in a script) lays a title as brush strokes
on a drawing; each stroke carries the words it letters (`words`, a stroke field of 2D's own, registered on the paint
kit). The layout checks used to ask `type == "text"`, so a hand-lettered title on a canvas-sized drawing was a
1920 x 1080 box spanning the picture: never cut by the edge, never near it (Night Market, rebench 3E: the title clipped
at the top in both runs, named in neither). `texts(nodes)` gives the text layers plus one text-like row per lettering,
its box where its strokes are drawn so far, so every text check reads painted words the same way."""
from __future__ import annotations

from .drawing import canvas_size, frame_at
from . import write_on


def boxes(layer: dict, w: float, h: float, n: int, t: float) -> dict[str, tuple]:
    """{words: (x0, y0, x1, y1) in the layer's own px} of the lettering a drawing shows at frame n (time t): only the
    strokes drawn so far, with their brush size. {} for anything else."""
    if layer.get("type") != "drawing":
        return {}
    frame = frame_at(layer, n)
    if not frame:
        return {}
    k, part = write_on.cut(frame, write_on.amount_at(layer, t))
    cw, ch = canvas_size(layer)
    kx, ky = w / (cw or 1), h / (ch or 1)
    out: dict[str, list] = {}
    i = 0
    for paint in frame.get("paints", []):
        for s in paint.get("strokes", []):
            shown = i < k or (i == k and part > 0)
            i += 1
            if not (shown and paint.get("visible", True) and s.get("words")):
                continue
            r = s.get("size", 0) / 2
            b = out.setdefault(s["words"], [float("inf"), float("inf"), float("-inf"), float("-inf")])
            for q in s.get("points", []):
                b[0], b[1] = min(b[0], q[0] - r), min(b[1], q[1] - r)
                b[2], b[3] = max(b[2], q[0] + r), max(b[3], q[1] + r)
    return {words: (b[0] * kx, b[1] * ky, b[2] * kx, b[3] * ky) for words, b in out.items()}


def texts(nodes: list[dict]) -> list[dict]:
    """The text layers of `nodes` (geometry.flatten rows) and, for each drawing's lettering, a text-like row: the drawing's
    row with `paint` set to the lettering's box, `words` its words, and the drawing's id (with the words when one drawing
    letters several)."""
    out = [n for n in nodes if n["type"] == "text"]
    for n in nodes:
        if n["type"] != "drawing":
            continue
        found = boxes(n["layer"], *n["size"], n["frame"], n["t"])
        for words, box in found.items():
            lid = n["id"] if len(found) == 1 else f'{n["id"]} "{words[:24]}"'
            out.append({**n, "id": lid, "type": "text", "paint": box, "words": words, "lettering": n["id"]})
    return out
