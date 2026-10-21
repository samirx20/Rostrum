"""Mouth cues → plain opacity keys (ease "hold") on the mouth layers: one layer shows at a time. At the first cue
every mouth layer gets a key (1 for the one showing, 0 for the rest); after that, each change of shape keys only
the two layers that swap. A person edits them like any other key on the timeline."""
from __future__ import annotations

from rostrum_core import RostrumError, codes

from . import visemes as V


def check_shapes(shapes: dict, where: str) -> dict:
    """{shape: layer id}, any subset of the 9 shapes; an item can stand for its id."""
    if not isinstance(shapes, dict) or not shapes:
        raise RostrumError(codes.BAD_ARGUMENT, where, "shapes", "must map shape names to mouth layers",
                           hint='e.g. {"X": "mouth_rest", "A": "mouth_mbp", "D": "mouth_wide"}')
    bad = [s for s in shapes if s not in V.SHAPES]
    if bad:
        raise RostrumError(codes.BAD_ARGUMENT, where, f"shapes {bad}", "are not mouth shapes", list(V.SHAPES))
    return {s: getattr(v, "id", v) for s, v in shapes.items()}


def plan(cues: list[dict], shapes: dict, at: float, clip_start: float) -> tuple[dict, list[dict]]:
    """({layer id: {comp time: 0 or 1}}, the cues as shown: shape asked, shape shown, layer, comp times)."""
    layers = list(dict.fromkeys(shapes.values()))
    keys, shown, current = {lay: {} for lay in layers}, [], None
    for c in cues:
        s = V.resolve(c["shape"], shapes)
        lay, t = shapes[s], round(at + c["start"] - clip_start, 4)
        shown.append({"shape": c["shape"], "shown": s, "layer": lay, "start": t,
                      "end": round(at + c["end"] - clip_start, 4)})
        if current is None:
            for other in layers:
                keys[other][t] = 1.0 if other == lay else 0.0
        elif lay != current:
            keys[current][t], keys[lay][t] = 0.0, 1.0
        current = lay
    return keys, shown


def slot_keys(shown: list[dict], children: list[str]) -> dict[float, int]:
    """{comp time: child index} for a swap set (swap.py): the cues from `plan` as the slot's `show` choices, one where
    the shown mouth changes. Every shape's layer must be one of `children` (ids, in the slot's order)."""
    out, current = {}, None
    for s in shown:
        if s["layer"] != current:
            out[s["start"]] = children.index(s["layer"])
            current = s["layer"]
    return out
