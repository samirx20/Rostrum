"""review's layout facts, read from the document's boxes (review_sample): a text partly crossed by a layer in front of it,
two showing texts on top of each other, a pointer (cursor, finger) sitting on a label, and an end card whose lock-up is tiny
in the frame. Each fault is {kind, start, end, id, ids, text} with times, layer ids and a fix. Not faults: a text fully
under an opaque panel or sheet (hidden, not crossed), a frosted or blurred scrim over it, a short cross-fade swap."""
from __future__ import annotations

import re

from .geometry import covers, drawn_box
from .review_cover import _in_front, _over, _related
from .review_sample import Sampled, runs

PARTIAL = (0.1, 0.85)     # a layer in front painting over this share of a text's box crosses it (more: the text is hidden)
HIDDEN = 0.85             # a text this much under opaque layers in front is hidden, not crossed
OPAQUE = 0.6              # a layer in front this opaque or more hides what is under it
CROSS_S = 1.0             # a crossing this long or longer (shorter: a wipe or a morph passing over)
ON_TEXT_S = 0.5           # two texts overlapping this long or longer ...
SWAP_S, SWAP_SAME = 1.0, 0.6   # ... texts this much on the same spot overlapping under SWAP_S: a cross-fade swap
ON_TEXT = 0.1             # two texts overlapping by this share of the smaller one's box
POINTER = re.compile(r"(^|[_\-\s])(cursor|pointer|mouse|finger|hand)s?($|[_\-\s\d])", re.I)
POINTER_ON, POINTER_S = 0.2, 0.25   # a pointer over this share of a showing text's box, this long or longer
END_S = 1.5               # the end card: the last picture held this long or longer ...
END_MARK, END_LOCKUP = 0.04, 0.07   # ... its biggest mark under this share of the frame (brief: "a logo under ~5 %"), or all of it in a box under this share
# (measured: Tally's two end cards, a normal app lock-up, mark 1.8-2.2 %, lock-up 12.6-16.7 %; Lumen's lamp lock-up
# mark ~5 %, ~60 %; a tiny wordmark alone on a big empty card, mark ~0.3 %, lock-up ~4 %)
GLYPHS = 0.7             # the share of a text's box height its letters fill
GAP = 16                  # the gap suggested between a block and the one above it (px)
GRID = [(u, v) for u in (0.1, 0.3, 0.5, 0.7, 0.9) for v in (0.2, 0.5, 0.8)]


def _frosted(n: dict) -> bool:
    return any(e.get("type") in ("backdrop", "blur") for e in n["layer"].get("effects", []))


def _box(s: Sampled, n: dict, by: dict) -> tuple | None:
    """A layer's box cut to the frame and to the clipping groups it sits in (a phone screen), or None when nothing is left."""
    x0, y0, x1, y1 = drawn_box(n)
    x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, s.W), min(y1, s.H)
    for g in n["within"]:
        if g in by and by[g]["props"].get("clip"):
            a, b, c, d = drawn_box(by[g])
            x0, y0, x1, y1 = max(x0, a), max(y0, b), min(x1, c), min(y1, d)
    return (x0, y0, x1, y1) if x1 - x0 > 2 and y1 - y0 > 2 else None


def _glyphs(box) -> tuple:
    """A text's box without its line spacing (GLYPHS of its height, centred): where its letters are."""
    x0, y0, x1, y1 = box
    pad = (1 - GLYPHS) / 2 * (y1 - y0)
    return x0, y0 + pad, x1, y1 - pad


def _share(parts: list[dict], box) -> float:
    x0, y0, x1, y1 = box
    return sum(any(covers(o, x0 + (x1 - x0) * u, y0 + (y1 - y0) * v) for o in parts) for u, v in GRID) / len(GRID)


def _texts(s: Sampled, nodes: list[dict], by: dict):
    """(index, node, box, the opaque layers in front) of each text that shows and is not hidden under them."""
    for k, n in enumerate(nodes):
        if n["type"] != "text" or not s.seen(n) or n["opacity"] < 0.25 or not (box := _box(s, n, by)):
            continue
        front = [o for o in nodes[k + 1:] if not _related(n, o) and s.seen(o) and o["type"] != "text"
                 and o["props"].get("blend", "normal") == "normal" and o["opacity"] >= OPAQUE]      # a full-frame cover hides too
        if _share(front, box) < HIDDEN:
            yield k, n, box, front


def _block(n: dict, o: dict) -> tuple[str, str]:
    """The two sibling blocks (children of their nearest shared group) that hold layers n and o."""
    a, b = n["within"] + (n["id"],), o["within"] + (o["id"],)
    i = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)) - 1)
    return a[i], b[i]


def _fix(by: dict, a: str, b: str) -> str:
    """'place <lower> below <upper> (…ends at y=…)' in the upper block's parent's own px, the units the script uses."""
    na, nb = by.get(a), by.get(b)
    if not na or not nb:
        return f'move "{b}" off "{a}"'
    up, low = (na, nb) if drawn_box(na)[1] <= drawn_box(nb)[1] else (nb, na)
    par = by.get(up["within"][-1]) if up["within"] else None
    bottom = drawn_box(up)[3]
    if par is not None:
        from .geometry import _apply, _invert
        inv = _invert(par["matrix"])
        bottom = _apply(inv, drawn_box(up)[0], bottom)[1] if inv else bottom
    return (f'place "{low["id"]}" below "{up["id"]}" ("{up["id"]}" ends at y = {bottom:.0f}): e.g. y = {bottom:.0f} + {GAP}, '
            f'or stack the blocks')


def _named(s: Sampled, hits: dict, least: float, line) -> list[dict]:
    out = []
    for key, at in hits.items():
        found = runs([i in at for i in range(len(s.times))], s.times, s.step, least(key, at))
        if found:
            t0, t1, a, b = max(found, key=lambda r: r[1] - r[0])
            out.append(line(key, t0, t1, max(at[i][0] for i in range(a, b + 1)), at[a][1]))
    return out


def overlaps(s: Sampled) -> list[dict]:
    """Texts partly crossed by a layer in front (PARTIAL of their box), texts on texts, pointers on texts."""
    crossed, on_text, pointed = {}, {}, {}
    for i, (t, nodes) in enumerate(s.frames):
        by = {n["id"]: n for n in nodes}
        texts = list(_texts(s, nodes, by))
        for k, n, box, front in texts:
            for o in front:
                if not _in_front(s, o) or o["type"] == "group" or _frosted(o) or POINTER.search(o["id"]) or any(POINTER.search(w) for w in o["within"]):
                    continue
                share = _over(o, box)
                if PARTIAL[0] <= share <= PARTIAL[1]:
                    crossed.setdefault((n["id"], o["id"]), {})[i] = (share, _block(n, o))
            tips = [o for o in nodes[k + 1:] if s.seen(o) and (POINTER.search(o["id"]) or POINTER.search(o["name"] or "")
                                                               or any(POINTER.search(w) for w in o["within"]))]
            if tips and (share := _share(tips, box)) >= POINTER_ON:
                tip = next((w for w in tips[0]["within"] if POINTER.search(w)), tips[0]["id"])
                pointed.setdefault((n["id"], tip), {})[i] = (share, None)
        glyphs = [(n, _glyphs(box)) for _, n, box, _ in texts]
        for x, (n, a) in enumerate(glyphs):
            for m, b in glyphs[x + 1:]:
                w, h = min(a[2], b[2]) - max(a[0], b[0]), min(a[3], b[3]) - max(a[1], b[1])
                small = min((a[2] - a[0]) * (a[3] - a[1]), (b[2] - b[0]) * (b[3] - b[1]))
                if w > 0 and h > 0 and w * h >= ON_TEXT * small:
                    on_text.setdefault((n["id"], m["id"]), {})[i] = (w * h / small, _block(n, m))

    def crossed_line(key, t0, t1, share, blocks):
        tid, lid = key
        return {"kind": "text_crossed", "start": t0, "end": t1, "id": tid, "ids": [tid, lid], "cover_pct": round(100 * share),
                "text": f'{t0:g}–{t1:g} s: "{lid}" is drawn over part of text "{tid}" ({100 * share:.0f} % of its box): '
                        f'{_fix(by_any(blocks), *blocks)}'}

    def on_text_line(key, t0, t1, share, blocks):
        return {"kind": "text_on_text", "start": t0, "end": t1, "id": key[0], "ids": list(key), "overlap_pct": round(100 * share),
                "text": f'{t0:g}–{t1:g} s: texts "{key[0]}" and "{key[1]}" sit on top of each other ({100 * share:.0f} % of the '
                        f'smaller one): {_fix(by_any(blocks), *blocks)}'}

    def pointer_line(key, t0, t1, share, _):
        return {"kind": "pointer_on_text", "start": t0, "end": t1, "id": key[0], "ids": list(key), "cover_pct": round(100 * share),
                "text": f'{t0:g}–{t1:g} s: pointer "{key[1]}" covers {100 * share:.0f} % of label "{key[0]}": put the pointer\'s '
                        f'tip on the button beside the label, not on it (tap() in ui_blocks does this)'}

    def by_any(blocks):        # the blocks' nodes at the last frame they both show (for the fix's numbers)
        for t, nodes in reversed(s.frames):
            by = {n["id"]: n for n in nodes}
            if all(b in by and by[b]["in_time"] for b in blocks):
                return by
        return {}

    def swap(key, at):          # two texts on the same spot: a cross-fade swap is fine under SWAP_S
        return SWAP_S if max(v[0] for v in at.values()) >= SWAP_SAME else ON_TEXT_S

    return (_named(s, crossed, lambda k, a: CROSS_S, crossed_line) + _named(s, on_text, swap, on_text_line)
            + _named(s, pointed, lambda k, a: POINTER_S, pointer_line))


def end_card(s: Sampled) -> list[dict]:
    """The last picture, held END_S or longer, whose mark (its biggest non-text item) or whole lock-up is tiny in the frame."""
    if not s.frames or s.duration < 2 * END_S:
        return []
    held = [i for i, t in enumerate(s.times) if t >= s.duration - END_S - 1e-9]
    ids = [frozenset(n["id"] for n in s.frames[i][1] if s.seen(n)) for i in held]
    if len(set(ids)) > 1:
        return []
    nodes = s.frames[-1][1]
    top = max((k for k, n in enumerate(nodes) if s.seen(n) and s.backdrop(n) and n["type"] != "text"), default=-1)
    content = [n for n in nodes[top + 1:] if s.seen(n) and not s.backdrop(n) and n["opacity"] >= OPAQUE
               and n["props"].get("blend", "normal") == "normal"]      # a glow or a light pool is not the lock-up
    if not content:
        return []
    marks = [n for n in content if n["type"] != "text"]
    mark = max(marks, key=lambda n: s.share(drawn_box(n)), default=None)
    boxes = [drawn_box(n) for n in content]
    x0, y0, x1, y1 = min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes)
    lockup, mark_share = s.share((x0, y0, x1, y1)), s.share(drawn_box(mark)) if mark else 1.0
    if mark_share >= END_MARK and lockup >= END_LOCKUP:
        return []
    t0 = s.times[held[0]]
    grow = max(1.5, (3 * (END_MARK / max(mark_share, 1e-6) if mark_share < END_MARK else END_LOCKUP / max(lockup, 1e-6))) ** 0.5)
    what = (f'its mark "{mark["id"]}" fills {100 * mark_share:.1f} % of the frame' if mark and mark_share < END_MARK else
            f'everything on it fits in {100 * lockup:.0f} % of the frame')
    return [{"kind": "end_small", "start": t0, "end": s.duration, "id": mark["id"] if mark else content[0]["id"],
             "ids": [n["id"] for n in content], "mark_pct": round(100 * mark_share, 1), "lockup_pct": round(100 * lockup, 1),
             "text": f'{t0:g} s to the end: the end card is tiny on an empty frame: {what}; scale the lock-up up about '
                     f'{grow:.1f}x, to ~{min(50, 100 * (y1 - y0) / s.H * grow):.0f} % of the frame height'}]


CHECKS = (overlaps, end_card)


def facts(s: Sampled) -> list[dict]:
    return [f for check in CHECKS for f in check(s)]
