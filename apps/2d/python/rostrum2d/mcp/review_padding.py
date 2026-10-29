"""review's tight text: a text lying on a panel (a card, a glass sheet, a group's background behind it) whose letters
come within a few px of the panel's inner edge, or past it: no padding, the words touch the card's side. Argon film:
"VOICE • VISION • CODE • ACTION" at 60 px ran edge to edge across its glass card and the look said nothing (no text
was cut and nothing crossed it). Not faults: a text on the frame's ground (a backdrop), on a faint or hollow layer."""
from __future__ import annotations

from . import outline
from .geometry import drawn_box
from .review_layout import _glyphs
from .review_sample import Sampled, runs

PAD = 0.4                 # room under this share of the letters' height between them and the panel's side is no padding
LEAST_PAD = 6             # px, at the least
OPAQUE = 0.5              # a panel at least this opaque (a frosted sheet counts: its fill shows)
LEAST = 1.0               # s


def _panel(s: Sampled, n: dict) -> bool:
    """A card's sheet: a filled rectangle or a group's background (a ring, an arc or a disc is a mark, not a card)."""
    card = n["type"] == "group" or n["type"] == "shape" and n["props"].get("shape", "rect") == "rect" and not outline.hollow(n)
    return card and s.seen(n) and n["opacity"] >= OPAQUE and not s.backdrop(n) and n["props"].get("blend", "normal") == "normal"


def _room(tb, pb, wrapped: bool) -> tuple[str, float]:
    """(side, px) of the letters' least room to the panel's inner edges (negative: past it); a wrapped text's box is
    wider than its lines, so only its top and bottom are measured."""
    room = {"top": tb[1] - pb[1], "bottom": pb[3] - tb[3]}
    if not wrapped:
        room.update(left=tb[0] - pb[0], right=pb[2] - tb[2])
    side = min(room, key=room.get)
    return side, room[side]


def facts(s: Sampled) -> list[dict]:
    hits: dict[tuple, dict] = {}
    for i, (t, nodes) in enumerate(s.frames):
        for k, n in enumerate(nodes):
            if n["type"] != "text" or not s.seen(n) or n["opacity"] < 0.25:
                continue
            tb = _glyphs(drawn_box(n))
            cx, cy = (tb[0] + tb[2]) / 2, (tb[1] + tb[3]) / 2
            under = [o for o in nodes[:k] if _panel(s, o) and (b := drawn_box(o))[0] <= cx <= b[2] and b[1] <= cy <= b[3]]
            if not under:
                continue
            pb = drawn_box(under[-1])                  # the panel it lies on: the top one under its middle
            side, px = _room(tb, pb, n["props"].get("boxWidth", 0) > 0)
            need = max(LEAST_PAD, PAD * (tb[3] - tb[1]))
            if px < need:
                hits.setdefault((n["id"], under[-1]["id"]), {})[i] = (side, px, need)
    out = []
    for (tid, pid), at in hits.items():
        found = runs([i in at for i in range(len(s.times))], s.times, s.step, LEAST)
        if not found:
            continue
        t0, t1, a, b = max(found, key=lambda r: r[1] - r[0])
        side, px, need = min((at[i] for i in range(a, b + 1)), key=lambda r: r[1])
        where = f"runs {-px:.0f} px past" if px < 0 else f"comes {px:.0f} px from"
        out.append({"kind": "text_tight", "start": t0, "end": t1, "id": tid, "ids": [tid, pid], "px": round(px),
                    "text": f'{t0:g}–{t1:g} s: text "{tid}" {where} the {side} edge of "{pid}" behind it (no padding; '
                            f'{need:.0f} px would clear it)'})
    return out
