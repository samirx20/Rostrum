"""review's room facts, read from the document (nothing drawn): a title closer to the frame edge than a safe margin, a title
crowding the layer stacked right above or below it, a small layer (a cursor, a badge) showing outside the screen or panel it
otherwise sits in, and a shape parked as a dot for seconds before it grows (a wipe circle left showing). Each fault is
{kind, start, end, id, text} with times, the same as review_facts; no taste: a bleed off the edge may be meant."""
from __future__ import annotations

from rostrum2d import lettered

from . import edge_cut
from .geometry import comp_size, drawn_box, flatten
from .review_facts import TITLE_H, _runs, _span

SAFE = 0.025          # a title's box closer than this share of the frame width to an edge is at the edge
WIDE = 0.5            # a text line this share of the frame's width or wider is held to the margin too, however small
CROWD = 0.05          # two stacked layers closer than this share of the title's height are crowded
SETTLED, STEADY = 1.5, 0.1  # ... held this long (s), the gap changing less than this share of the title's height
NEIGHBOUR = 4.0       # ... a layer up to this many times the title's area (bigger: a backdrop behind it)
SHOWN = 0.25          # opacity from which a layer counts as seen
SMALL = 0.02          # a layer this share of the frame's area or under can sit in a container (a cursor, a badge)
CONTAINER = 6.0       # ... a container is a clipped group at least this many times its area
SPECK_PX = 24         # a shape this many px or under on each side is a dot ...
SPECK_GROW = 10.0     # ... and parked when it later grows to this many times that size
SPECK_S = 1.0         # ... for this long while showing


def _screen(n: dict) -> bool:
    """A device's screen (device(): the group "<device>_screen" inside the device's group)."""
    return bool(n["within"]) and n["id"] == f'{n["within"][-1]}_screen'


def _seen(n: dict, W: float, H: float) -> bool:
    x0, y0, x1, y1 = drawn_box(n)
    return n["in_time"] and n["opacity"] >= SHOWN and x1 > 0 and y1 > 0 and x0 < W and y0 < H and (x1 - x0) * (y1 - y0) > 4


def _related(a: dict, b: dict) -> bool:
    return a["id"] in b["within"] or b["id"] in a["within"]


def _margin(n: dict, W: float, H: float) -> tuple[str, float] | None:
    """(side, px inside the frame; negative = past it) of a title nearer an edge than SAFE, else None."""
    x0, y0, x1, y1 = drawn_box(n)
    m = SAFE * W
    room = {"left": x0, "right": W - x1, "top": y0, "bottom": H - y1}
    side = min(room, key=room.get)
    return (side, room[side]) if room[side] < m else None


def _gap(a, b) -> tuple[float, float] | None:
    """(vertical gap in px, share of the narrower width they share) when a sits right above b, else None."""
    over = min(a[2], b[2]) - max(a[0], b[0])
    narrow = min(a[2] - a[0], b[2] - b[0]) or 1.0
    if over <= 0:
        return None
    return b[1] - a[3], over / narrow


def facts(comp: dict, times: list[float], step: float) -> list[dict]:
    W, H = comp_size(comp)
    edge, crowd, outside, dots, size = {}, {}, {}, {}, {}
    homes: dict[str, set] = {}
    frames = [(t, flatten(comp, t)) for t in times]
    for t, nodes in frames:
        clipped = {n["id"] for n in nodes if n["type"] == "group" and n["props"].get("clip")}
        seen = [n for n in nodes if _seen(n, W, H) and not clipped & set(n["within"])]     # not screen content in a clipped group
        titles = [n for n in lettered.texts(seen) if drawn_box(n)[3] - drawn_box(n)[1] >= TITLE_H * H]   # painted words too
        wide = [n for n in lettered.texts(seen) if n not in titles and drawn_box(n)[2] - drawn_box(n)[0] >= WIDE * W]
        for n in titles + wide:                 # a small line spanning the frame (a credit) runs into its edges too
            x0, y0, x1, y1 = drawn_box(n)
            if (hit := _margin(n, W, H)) and hit[1] > -0.03 * (x1 - x0):      # further past it: review_facts names it cut off
                edge.setdefault((n["id"], hit[0]), []).append((t, hit[1]))
        for n in titles:
            x0, y0, x1, y1 = drawn_box(n)
            for o in ([] if n["layer"].get("matte") else seen):     # a matted title shows only where its matte is
                if o is n or o["id"] == n.get("lettering") or edge_cut.soft(o["layer"]) or _related(n, o) or o["matte_for"] or o["type"] == "group" and not o["paint"]:
                    continue
                ob = drawn_box(o)
                if (ob[2] - ob[0]) * (ob[3] - ob[1]) > NEIGHBOUR * (x1 - x0) * (y1 - y0):   # a backdrop or a blob, not a neighbour
                    continue
                for upper, lower, a, b in ((o, n, ob, (x0, y0, x1, y1)), (n, o, (x0, y0, x1, y1), ob)):
                    g = _gap(a, b)
                    tall = y1 - y0
                    if g and g[1] > 0.3 and -0.1 * tall < g[0] < CROWD * tall:
                        crowd.setdefault((lower["id"], upper["id"]), []).append((t, g[0], tall))
        boxes = {n["id"]: (n, drawn_box(n)) for n in nodes}
        holders = [(n, b) for n, b in boxes.values() if n["type"] == "group" and n["in_time"]
                   and (n["props"].get("clip") or _screen(n))]      # a device's screen holds its layers, clipped or not
        for n in seen:
            b = drawn_box(n)
            area = (b[2] - b[0]) * (b[3] - b[1])
            if n["within"] or n["type"] == "group" or area > SMALL * W * H:
                continue
            cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
            for g, gb in holders:
                if (gb[2] - gb[0]) * (gb[3] - gb[1]) < CONTAINER * area:
                    continue
                name = g["within"][0] if g["within"] else g["id"]
                inside = gb[0] <= cx <= gb[2] and gb[1] <= cy <= gb[3]
                if inside:
                    homes.setdefault(n["id"], set()).add(name)
                else:
                    outside.setdefault((n["id"], name), []).append(t)
        for n in nodes:
            if n["type"] == "shape" and not n["within"]:
                b = drawn_box(n)
                side = max(b[2] - b[0], b[3] - b[1])
                size[n["id"]] = max(size.get(n["id"], 0.0), side)
                if _seen(n, W, H) and side <= SPECK_PX:
                    dots.setdefault(n["id"], []).append((t, side))
    out = []
    for (lid, side), rows in edge.items():
        for t0, t1, a, b in _runs(times, [t in {r[0] for r in rows} for t in times], step, step):
            px = min(r[1] for r in rows if t0 <= r[0] < t1)
            where = f"runs {-px:.0f} px past" if px < 0 else f"is {px:.0f} px from"
            out.append({"kind": "text_edge" if px < 0 else "text_margin", "start": t0, "end": t1, "id": lid,
                        "text": f'{_span(t0, t1)}: text "{lid}" {where} the {side} edge of the frame (a safe margin is '
                                f'{SAFE * W:.0f} px): it reads as running into the edge'})
    tight: dict[str, tuple] = {}
    for (low, up), rows in crowd.items():           # a pair that holds its gap (a lock-up), not a shape drifting past
        for t0, t1, a, b in _runs(times, [t in {r[0] for r in rows} for t in times], step, SETTLED):
            gaps = [g for t, g, _ in rows if t0 <= t < t1]
            if max(gaps) - min(gaps) <= STEADY * min(h for _, _, h in rows) and (low not in tight or min(gaps) < tight[low][2]):
                tight[low] = (t0, t1, min(gaps), up)
    for low, (t0, t1, px, up) in tight.items():
        out.append({"kind": "crowded", "start": t0, "end": t1, "id": low,
                    "text": f'{_span(t0, t1)}: "{low}" sits {max(px, 0):.0f} px under "{up}" (boxes nearly touching): tight; open the gap'})
    for (lid, name), ts in outside.items():
        if name not in homes.get(lid, ()):
            continue                                  # never in it: it belongs outside
        runs = _runs(times, [t in set(ts) for t in times], step, step)
        out.append({"kind": "outside", "start": runs[0][0], "end": runs[-1][1], "id": lid, "spans": [r[:2] for r in runs],
                    "text": f'{", ".join(_span(a, b) for a, b, _, _ in runs)}: "{lid}" shows outside "{name}", where it sits the '
                            f'rest of the time, so it floats off it; fade it out inside, or move it in before it shows'})
    for lid, rows in dots.items():
        if size.get(lid, 0.0) < SPECK_GROW * max(r[1] for r in rows):
            continue
        for t0, t1, _, _ in _runs(times, [t in {r[0] for r in rows} for t in times], step, SPECK_S):
            out.append({"kind": "speck", "start": t0, "end": t1, "id": lid,
                        "text": f'{_span(t0, t1)}: shape "{lid}" shows as a {max(r[1] for r in rows):.0f} px dot before it '
                                f'grows to {size[lid]:.0f} px: hide it until it starts (opacity 0) or start it at size 0'})
    return out
