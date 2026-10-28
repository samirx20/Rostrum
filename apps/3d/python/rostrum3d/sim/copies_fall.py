"""Is a falling copies item's fall seen (fall_view for copies, round 4 of the 3D gaps): each copy is judged on its own,
then the group. A staggered stream (varyStart, a pour) is many short falls one after another, so the first copy alone
says nothing ("drops 0 m in frames 8–8 … a pop" was the first copy of a 36-copy pour). A copy is fine when the picture
shows it dropping for MIN_ON frames or more; a pop when it is seen for fewer; unseen when none of its drop is in the picture.
The group needs a fix when more than a quarter of the copies that fall are pops or unseen.

    facts, text, fix = judge("dice", tracks, frames, seen_at, fps)   # tracks: per copy, its pivot per shot frame (world)
"""
from __future__ import annotations

from statistics import median

SAMPLE = 200          # at most this many copies are judged (evenly picked), so 10,000 confetti stay quick
BAD_SHARE = 0.25      # more pops + unseen than this share of the falling copies is named with a fix
_FIX = ("raise the copies item (or the pour's mouth) so the copies start inside the picture, near its top: sim.start_in_view "
        "(fromTop 0.1); or widen or pull back the camera so the landing and the drop are both in it")


def _picked(n: int) -> list[int]:
    return list(range(n)) if n <= SAMPLE else sorted({round(i * (n - 1) / (SAMPLE - 1)) for i in range(SAMPLE)})


def judge(id_: str, tracks: list[list[list[float]]], frames: list[int], seen_at, fps: float) -> tuple[dict, str, bool]:
    """(the facts, the plain-words line, whether it needs a fix). `seen_at(frame, point)`: "in" | "part" | "above" |
    "below" | "side" | "out" for one world point at that shot frame."""
    from .fall_view import MIN_ON, MOVE_M, classify, line
    picked = _picked(len(tracks))
    per = []
    for c in picked:
        pts = tracks[c]
        pace = [sum((a - b) ** 2 for a, b in zip(pts[i - 1], pts[i])) ** 0.5 for i in range(1, len(pts))]
        if not any(d >= MOVE_M for d in pace):
            per.append(None)
            continue
        seen = [seen_at(f, p) for f, p in zip(frames, pts)]
        per.append(classify(frames, pace, seen, fps, [p[1] for p in pts]))
    movers = [f for f in per if f is not None]
    if not movers:
        facts = classify(frames, [0.0] * (len(frames) - 1), ["in"] * len(frames), fps)
        return facts, line(id_, "copies", facts, fps)[0], True
    pops = [f for f in movers if 0 < f["onScreen"] < MIN_ON]
    unseen = [f for f in movers if f["onScreen"] == 0]
    good = len(movers) - len(pops) - len(unseen)
    a, b = min(f["drop"][0] for f in movers), max(f["drop"][1] for f in movers)
    dropping = {g for f in movers for g in range(f["drop"][0], f["drop"][1] + 1)}
    shown = {g for f in movers if f["enters"] is not None for g in range(f["enters"], f["drop"][1] + 1)}
    on = len(dropping & shown)
    sides = [f["where"] for f in [*pops, *unseen] if f["where"]]
    facts = {"moving": [min(f["moving"][0] for f in movers), max(f["moving"][1] for f in movers)],
             "movingFrames": len({g for f in movers for g in range(f["moving"][0], f["moving"][1] + 1)}),
             "drop": [a, b], "onScreen": on, "offScreen": len(dropping) - on,
             "enters": min((f["enters"] for f in movers if f["enters"] is not None), default=None), "lands": b,
             "where": max(set(sides), key=sides.count) if sides else None, "startsAtRest": False,
             "underway": any(f["underway"] for f in movers), "seconds": round(median(f["seconds"] for f in movers), 2),
             "drop_m": round(median(f["drop_m"] for f in movers), 3),
             "copies": {"judged": len(picked), "of": len(tracks), "falling": len(movers), "seenFalling": good,
                        "pops": len(pops), "unseen": len(unseen), "still": len(per) - len(movers)}}
    starts = sorted({f["drop"][0] for f in movers})
    how = (f"one after another, starting over frames {starts[0]}–{starts[-1]}" if len(starts) > 1 else f"all at once from frame {a}")
    some = f" ({len(picked)} of {len(tracks)} judged)" if len(picked) < len(tracks) else ""
    head = (f"{id_} (copies): {len(movers)} copies fall{some}, {how}, landing by frame {b}; each drops a median "
            f"{facts['drop_m']:g} m and is seen dropping for a median {facts['seconds']:g} s; {good} seen falling well")
    bad = len(pops) + len(unseen)
    if bad == 0 or bad <= BAD_SHARE * len(movers):
        tail = f" ({bad} only briefly or not at all)" if bad else ""
        return facts, f"{head}{tail}.", False
    where = {"above": "above the picture", "below": "below the picture", "side": "beside the picture"}.get(facts["where"], "outside the picture")
    return facts, (f"{head}; {len(unseen)} drop where the picture doesn't show them (mostly {where}) and {len(pops)} are seen "
                   f"dropping for under {MIN_ON} frames (a pop, not a fall). To see them fall: {_FIX}."), True
