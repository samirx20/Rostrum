"""review's panel collisions: two sibling blocks holding words (cards, groups with a background, a panel with its
label) at the same level whose drawn boxes run into each other while both show. Shapes without words (a robot's
overlapping parts, a set's wall and cage) overlap by design and are left alone. Film 2d-why-still-broken: three cards placed by hand at
y = 75 / 133 / 191 with h=50 each drew ~80 px tall (their words need it), so each covered the next, and the look said
nothing (text_crossed only names a text under a layer). Measured on where each block really draws (review_blocks.extent:
the size the layout gives, as the render). Not faults: a card on its pane (one mostly inside the other), a backdrop (a
block over most of the frame or of the group they share), a faint one (under OPAQUE), the layers of a stack layout
(drawn on top of each other on purpose)."""
from __future__ import annotations

from . import edge_cut, outline, review_blocks as rb
from .geometry import drawn_box
from .review_layout import _block
from .review_sample import Sampled, runs

OPAQUE = 0.5              # both blocks at least this opaque: a faint one passing over is a fade, not a collision
INTO = 4                  # px of one block running into the other before it counts (a hairline touch is a border)
INSIDE = 0.9              # the smaller block this much inside the other: it sits on it (a card on its pane)
BACKDROP = 0.8            # a block over this share of the frame or of the group the two share is the ground under them
LEAST = 0.5               # s the two overlap before it is named


def _panel(n: dict) -> bool:
    """A layer that paints a panel: a filled shape or a group's background, clear enough to hide what it covers."""
    p = n["props"]
    return (rb.shows(n) and n["opacity"] >= OPAQUE and n["type"] in ("shape", "group") and p.get("blend", "normal") == "normal"
            and p.get("fillOpacity", 1.0) >= OPAQUE and not edge_cut.soft(n["layer"])          # not a beam, a glow, a light
            and not (n["type"] == "shape" and outline.hollow(n)))


def _area(b) -> float:
    return max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])


def _ground(s: Sampled, by: dict, nodes: list[dict], block: str, box) -> bool:
    """The block lies under everything (most of the frame, or of the group it shares with the other block)."""
    par = by[block]["within"][-1] if by[block]["within"] else None
    pbox = drawn_box(by[par]) if par and _area(drawn_box(by[par])) > 4 else rb.extent(nodes, par) if par else None
    return s.share(box) >= BACKDROP or bool(pbox) and _area(_clip(box, pbox)) >= BACKDROP * _area(pbox)


def _clip(a, b):
    return max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])


def facts(s: Sampled) -> list[dict]:
    hits: dict[tuple, dict] = {}            # (block, block) -> {frame index: (px, axis)}
    for i, (t, nodes) in enumerate(s.frames):
        by = {n["id"]: n for n in nodes}
        panels = [n for n in nodes if _panel(n)]
        pairs = set()
        for x, n in enumerate(panels):
            for o in panels[x + 1:]:
                if n["id"] not in o["within"] and o["id"] not in n["within"]:
                    pairs.add(tuple(sorted(_block(n, o))))
        ext: dict[str, tuple] = {}
        worded = {w for n in nodes if n["type"] == "text" and rb.shows(n) for w in (n["id"], *n["within"])}
        for a, b in pairs:
            par = by[a]["within"][-1] if by[a]["within"] else None
            if a == b or a not in worded or b not in worded or par and by[par]["props"].get("layout") == "stack":
                continue
            for k in (a, b):
                if k not in ext:
                    ext[k] = rb.extent(nodes, k)
            ea, eb = ext[a], ext[b]
            o = _clip(ea, eb)
            w, h = o[2] - o[0], o[3] - o[1]
            if min(w, h) <= INTO or w * h >= INSIDE * min(_area(ea), _area(eb)):
                continue
            if _ground(s, by, nodes, a, ea) or _ground(s, by, nodes, b, eb):
                continue
            hits.setdefault((a, b), {})[i] = (min(w, h), "y" if h <= w else "x")
    out = []
    for (a, b), at in hits.items():
        found = runs([i in at for i in range(len(s.times))], s.times, s.step, LEAST)
        if not found:
            continue
        t0, t1, i0, i1 = max(found, key=lambda r: r[1] - r[0])
        k = max(range(i0, i1 + 1), key=lambda i: at[i][0])
        px, axis = at[k]
        nodes = s.frames[k][1]
        ea, eb = rb.extent(nodes, a), rb.extent(nodes, b)
        first, second = (a, b) if ea[1 if axis == "y" else 0] <= eb[1 if axis == "y" else 0] else (b, a)
        out.append({"kind": "panel_overlap", "start": t0, "end": t1, "id": first, "ids": [first, second], "px": round(px),
                    "text": f'{t0:g}–{t1:g} s: "{first}" runs {px:.0f} px into "{second}" '
                            f'{"below" if axis == "y" else "beside"} it (where they really draw, words included): '
                            f'{rb.below(nodes, first, second, axis)}'})
    return out
