"""review's screen spill: a layer made in a device's screen (device()) that runs past the screen's edge, while the screen
does not clip (overflow="hidden" cuts it at the edge; review_clip then names a cut text). Canary 3E R8: a dashboard's
third card and a chart card hung off a laptop's screen and the look said nothing. Only the outermost spilling layer is
named (a card, not each of its words)."""
from __future__ import annotations

from .geometry import drawn_box
from .review_sample import Sampled, runs
from .review_device import devices

SPILL = 0.03        # past the screen's edge by this share of the screen's width / height: a client sees it spill


def _past(b, sb) -> tuple[str, float]:
    """(side, px) the box b runs furthest past the screen box sb."""
    past = {"left": sb[0] - b[0], "right": b[2] - sb[2], "top": sb[1] - b[1], "bottom": b[3] - sb[3]}
    side = max(past, key=past.get)
    return side, past[side]


def facts(s: Sampled) -> list[dict]:
    out = []
    for did in devices(s.comp):
        scr, hits = f"{did}_screen", {}            # id -> {frame index: (side, px)}
        within: dict[str, list] = {}
        for i, (t, nodes) in enumerate(s.frames):
            sn = next((n for n in nodes if n["id"] == scr), None)
            if sn is None or not sn["in_time"] or sn["props"].get("clip"):
                continue
            sb = drawn_box(sn)
            for n in nodes:
                if scr not in n["within"] or not s.seen(n):
                    continue
                side, px = _past(drawn_box(n), sb)
                if px > SPILL * ((sb[2] - sb[0]) if side in ("left", "right") else (sb[3] - sb[1])):
                    hits.setdefault(n["id"], {})[i] = (side, px)
                    within[n["id"]] = n["within"]
        for lid, at in hits.items():
            if any(a in hits and set(hits[a]) & set(at) for a in within[lid]):     # its card spills too: the card is named
                continue
            for t0, t1, a, b in runs([i in at for i in range(len(s.times))], s.times, s.step, s.step):
                side, px = max((at[i] for i in range(a, b + 1) if i in at), key=lambda r: r[1])
                out.append({"kind": "screen_spill", "start": t0, "end": t1, "id": lid, "ids": [lid, did],
                            "text": f'{t0:g}–{t1:g} s: "{lid}" runs {px:.0f} px past the {side} edge of device "{did}"\'s screen '
                                    f'(the screen does not clip)'})
    return out
