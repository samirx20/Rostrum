"""review's layout jump: a layer an auto layout (row / column / grid / stack) places that jumps a large share of the
frame from one frame to the next with no key moving it: the layout moved it, not an animation (a sibling's size keyed
on a hold, a box re-sizing at once). Canary 3E R8 asked for it after a row of cards looked as if it re-centred while
they faded in. The places are where the laid-out layers sit in the picture (a row re-centring as it re-sizes counts); a move
with a key on the layer, on a group it is in or on the camera in that frame is an animation, not named. A jump seen between two samples is
narrowed down to one frame, so a smooth re-flow (a keyed w over a second) is never named. Only the outermost jumping
layer is named (the card, not each of its words)."""
from __future__ import annotations

from rostrum2d.evaluate import keys_of
from rostrum2d.layout import has_layout, laid_out

from .geometry import flatten
from .review_sample import SEEN, Sampled

JUMP = 0.05         # a move over one frame past this share of the frame's width / height: a client sees it jump
MOVES = ("x", "y", "shiftX", "shiftY")      # keys that move a layer on purpose (on it or on its group) ...
OWN = ("w", "h")                            # ... or re-size it (its anchor moves with its size)
TURNS = ("scale", "scaleX", "scaleY", "rotation")    # a group's keys that carry its layers along


def _places(comp: dict, t: float) -> dict[str, tuple[float, float]]:
    """{id: its box's top-left in the picture} of each laid-out group and each layer one places (the row itself
    re-centring when it re-sizes counts too), while it shows (a layer not in its time or clear can't be seen jump)."""
    nodes = flatten(comp, t)
    groups = {n["id"]: n["layer"] for n in nodes if has_layout(n["layer"])}
    return {n["id"]: n["corners"][0] for n in nodes if n["in_time"] and n["opacity"] >= SEEN and
            (n["id"] in groups or (n["within"] and n["within"][-1] in groups and not n["props"].get("layoutApart")))}


def _moved(a: dict, b: dict, W: float, H: float) -> dict[str, float]:
    """{id: the share of the frame it moved} between two sets of places."""
    return {k: max(abs(b[k][0] - p[0]) / W, abs(b[k][1] - p[1]) / H) for k, p in a.items() if k in b}


def _one_frame(comp: dict, t0: float, t1: float, fps: float, W: float, H: float) -> tuple[float, float, dict[str, float]]:
    """Halve [t0, t1] towards the half that moves most until it is one frame: (start, end, {id: share moved in it})."""
    a, b = round(t0 * fps), round(t1 * fps)
    pa, pb = _places(comp, a / fps), _places(comp, b / fps)
    while b - a > 1:
        m = (a + b) // 2
        pm = _places(comp, m / fps)
        if max(_moved(pa, pm, W, H).values(), default=0) >= max(_moved(pm, pb, W, H).values(), default=0):
            b, pb = m, pm
        else:
            a, pa = m, pm
    return a / fps, b / fps, _moved(pa, pb, W, H)


def _keyed(layer: dict, t0: float, t1: float, fields=MOVES) -> bool:
    return any(isinstance(k["t"], (int, float)) and t0 - 1e-9 <= k["t"] <= t1 + 1e-9 for f in fields for k in keys_of(layer, f))


def facts(s: Sampled) -> list[dict]:
    if not any(laid_out(layer) for layer in s.comp.get("layers", [])) or len(s.times) < 2:
        return []
    fps = float(s.comp.get("fps", 30))
    places = [_places(s.comp, t) for t in s.times]
    cams = [c for c in s.comp.get("layers", []) if c["type"] == "camera"]        # a camera move or cut moves everything
    out, named = [], set()
    for i in range(len(s.times) - 1):
        if max(_moved(places[i], places[i + 1], s.W, s.H).values(), default=0) <= JUMP:
            continue
        t0, t1, moved = _one_frame(s.comp, s.times[i], s.times[i + 1], fps, s.W, s.H)
        nodes = {n["id"]: n for n in s.frames[i][1]}
        jumped = {k for k, v in moved.items() if v > JUMP and k in nodes}
        for lid in sorted(jumped):
            n = nodes[lid]
            if any(a in jumped for a in n["within"]) or (lid, t0) in named:      # its group jumps: the group is named
                continue
            if (_keyed(n["layer"], t0, t1, MOVES + OWN) or any(_keyed(nodes[a]["layer"], t0, t1, MOVES + TURNS) for a in n["within"])
                    or any(_keyed(c, t0, t1, tuple(k["prop"] for k in c.get("keys", ()))) for c in cams)):
                continue
            named.add((lid, t0))
            share = round(100 * moved[lid])
            out.append({"kind": "layout_jump", "start": round(t0, 2), "end": round(t1, 2), "id": lid, "ids": [lid],
                        "text": f'{t0:g}–{t1:g} s: "{lid}" jumps {share} % of the frame in one frame, moved by its '
                                f'layout ({"/".join(n["within"][-1:]) or "its box"}), not by a key: something in the layout '
                                f'changed size or left at once; key that change over time (ease it), or keep the sizes '
                                f'still and animate with opacity / scale / shiftX / shiftY, which never move the others'})
    return out
