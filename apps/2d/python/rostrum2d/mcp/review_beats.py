"""review's declared beats: [{at, to, expect}] checked against the document. A beat that never happens is a fault; so is
one that happens at the wrong time: a layer already showing (or already whole, for a reveal) well before the beat, or a
move, cut or pose change that happens only somewhere else in the film. How much of a layer shows is measured from the
document: its opacity, the share of it inside the frame, a stroke's trim, its track matte and a clipping group's box."""
from __future__ import annotations

from rostrum_core.errors import RostrumError, codes

from . import world_facts as wf
from .geometry import VISIBLE_OPACITY, aabb, comp_size, drawn_box, flatten
from .review_facts import FRAMING_SAME, POSE_SAME, SHOWN, _pose_moved, _same_shot, _span, shots

BEAT_KINDS = ("camera move", "cut", "pose change", "<layer id> moves", "<layer id> shows", "<layer id> reveals")
LAYER_VERBS = ("moves", "shows", "reveals")
EARLY_S = 1.0        # a layer shown (or whole) this long or more before its beat's time came too soon
REVEAL_GROW = 0.25   # a reveal: this much more of the layer shows by the end of the beat than at its start
WHOLE = 0.9          # this share of a layer's most-shown amount counts as whole


def parsed(b: dict, ids: set[str], where: str) -> tuple[float, float, str, str | None]:
    """(at, to, what, layer id or None) of one declared beat; an expect review can't check fails loudly."""
    at = float(b.get("at", 0))
    to, want = max(at, float(b.get("to", at))), str(b.get("expect", "")).strip()
    if want in ("camera move", "cut", "pose change"):
        return at, to, want, None
    lid, _, verb = want.rpartition(" ")
    if verb in LAYER_VERBS and lid in ids:
        return at, to, want, lid
    known = f' "{lid}" is not a layer of this composition.' if verb in LAYER_VERBS and lid else ""
    raise RostrumError(codes.BAD_ARGUMENT, where, f'beat expect "{want}"', "is not a beat review can check",
                       hint=f"Accepted: {', '.join(BEAT_KINDS)}.{known} A whole object made of several layers: name its group.")


def check(comp: dict, asked: list[dict], where: str) -> None:
    """Fail loudly now on a beat that can't be checked, before it is remembered or a job starts."""
    ids = {n["id"] for n in flatten(comp, 0.0)}
    for b in asked:
        parsed(b, ids, where)


def _inside(box, outer) -> float:
    w, h = min(box[2], outer[2]) - max(box[0], outer[0]), min(box[3], outer[3]) - max(box[1], outer[1])
    area = (box[2] - box[0]) * (box[3] - box[1])
    return max(0.0, w) * max(0.0, h) / area if area > 1e-9 else 0.0


def _seen(n: dict, by_id: dict, W: float, H: float) -> float:
    """How much of one drawn layer shows (0..1)."""
    if not n["in_time"] or n["opacity"] < VISIBLE_OPACITY or n["matte_for"]:
        return 0.0
    p, box = n["props"], drawn_box(n)
    v = n["opacity"] * wf.share_inside(wf.polygon(n), W, H)
    if "trimEnd" in p:
        v *= max(0.0, min(1.0, p["trimEnd"]) - max(0.0, p.get("trimStart", 0.0)))
    if (m := by_id.get(n["layer"].get("matte", ""))) is not None:
        cut = _inside(box, drawn_box(m)) * (m["opacity"] if m["in_time"] else 0.0)
        v *= 1 - cut if str(p.get("matteMode", "alpha")).endswith("Inverted") else cut
    for a in n["within"]:
        if a in by_id and by_id[a]["props"].get("clip"):
            v *= _inside(box, aabb(by_id[a]["corners"]))
    return v


def shown(nodes: list[dict], lid: str, W: float, H: float) -> float:
    """How much of a layer shows (0..1): its drawn parts (a group's: every layer in it), weighted by their size on screen."""
    by_id = {n["id"]: n for n in nodes}
    parts = [n for n in nodes if (n["id"] == lid or lid in n["within"]) and n["type"] != "group"]
    sizes = [max(wf._area(wf.polygon(n)), 0.0) for n in parts]
    total = sum(sizes)
    return sum(s * _seen(n, by_id, W, H) for s, n in zip(sizes, parts)) / total if total > 1e-9 else 0.0


def beats(comp: dict, asked: list[dict], times: list[float], vectors: dict[str, list], where: str) -> list[dict]:
    """The declared beats that never happen, or happen at the wrong time: {at, to, expect} with expect one of BEAT_KINDS."""
    if not times:
        return []
    W, H = comp_size(comp)
    frames = [flatten(comp, t) for t in times]
    ids = {n["id"] for n in frames[0]}
    shot, cuts = None, wf.cuts(comp)
    out = []
    for b in asked:
        at, to, want, lid = parsed(b, ids, where)
        inside = [i for i, t in enumerate(times) if at - 1e-9 <= t <= to + 1e-9]
        if len(inside) < 2:              # a beat at one moment: the samples either side of it, so a change can show
            i = min(max(0, len(times) - 2), min(range(len(times)), key=lambda i: abs(times[i] - at)))
            inside = list(range(i, min(i + 2, len(times))))
        if want == "cut":
            ok = lambda idx: any(times[idx[0]] - 1e-9 <= c <= times[idx[-1]] + 1e-9 for c in cuts)
            if any(at - 1e-9 <= c <= to + 1e-9 for c in cuts):
                continue
        elif want == "camera move":
            shot = shot or shots(comp, times)
            ok = lambda idx: any(not _same_shot(shot[idx[0]], shot[i], W) for i in idx[1:])
        elif want == "pose change":
            ok = lambda idx: any(_pose_moved(rows[idx[0]], rows[i]) >= POSE_SAME for rows in vectors.values() for i in idx[1:])
        elif want.endswith(" moves"):
            boxes = [drawn_box(next(n for n in f if n["id"] == lid)) for f in frames]
            ok = lambda idx: any(max(abs(p - q) for p, q in zip(boxes[idx[0]], boxes[i])) > FRAMING_SAME * W for i in idx[1:])
        else:
            amount = [shown(f, lid, W, H) for f in frames]
            out += _showing(want, lid, at, to, inside, times, amount)
            continue
        if want == "cut" or not ok(inside):
            out.append(_elsewhere(want, at, to, inside, times, ok))
    return out


def _showing(want: str, lid: str, at: float, to: float, inside: list[int], times: list[float], amount: list[float]) -> list[dict]:
    """'<layer> shows' / '<layer> reveals': never (enough), or already before the beat."""
    span = _span(at, to) if to > at else f"{at:g} s"
    reveal = want.endswith(" reveals")
    whole = WHOLE * max(amount) if reveal else SHOWN
    early = next((i for i, t in enumerate(times) if t < at - EARLY_S + 1e-9 and amount[i] >= max(whole, 1e-6)), None)
    if early is not None:
        pct = round(amount[early] * 100)
        what = f"{lid} whole, {pct} % showing" if reveal else f"{pct} % of {lid} showing"
        return [{"kind": "beat_wrong_time", "start": times[early], "end": at, "id": lid,
                 "text": f"{span}: '{want}' already happened at {times[early]:g} s ({what}); the beat is meant at {span}"}]
    got = [amount[i] for i in inside]
    ok = max(got) - got[0] >= REVEAL_GROW if reveal else max(got) >= SHOWN
    if ok:
        return []
    say = (f"never happens: {lid} shows {round(got[0] * 100)} % at the start and at most {round(max(got) * 100)} % by the end"
           if reveal else f"never happens: at most {round(max(got) * 100)} % of {lid} shows then")
    return [{"kind": "beat_missing", "start": at, "end": to, "id": lid, "text": f"{span}: the beat you declared, '{want}', {say}"}]


def _elsewhere(want: str, at: float, to: float, inside: list[int], times: list[float], ok) -> dict:
    """A move, cut or pose change missing at its time: where in the film it does happen (nearest first), else never."""
    n, span = len(inside), _span(at, to) if to > at else f"{at:g} s"
    found = [j for j in range(len(times) - max(n, 2) + 1) if not set(range(j, j + max(n, 2))) & set(inside) and ok(list(range(j, j + max(n, 2))))]
    if not found:
        return {"kind": "beat_missing", "start": at, "end": to, "text": f"{span}: the beat you declared, '{want}', never happens"}
    j = min(found, key=lambda j: abs(times[j] - at))
    when = "already happened" if times[j] < at else "happens only later"
    return {"kind": "beat_wrong_time", "start": min(times[j], at), "end": max(times[j], to),
            "text": f"{span}: '{want}' {when}, at {times[j]:g} s; the beat is meant at {span}"}
