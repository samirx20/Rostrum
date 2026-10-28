"""review's declared beats: [{at, to, expect}] checked against the document; a beat that never happens is a fault."""
from __future__ import annotations

from rostrum_core.errors import RostrumError, codes

from . import world_facts as wf
from .geometry import comp_size, drawn_box, flatten
from .review_facts import FRAMING_SAME, POSE_SAME, SHOWN, _pose_moved, _same_shot, _span, _visible, shots

BEAT_KINDS = ("camera move", "cut", "pose change", "<layer id> moves", "<layer id> shows")


def beats(comp: dict, asked: list[dict], times: list[float], vectors: dict[str, list], where: str) -> list[dict]:
    """The declared beats that never happened: {at, to, expect} with expect one of BEAT_KINDS."""
    W, _ = comp_size(comp)
    ids = {n["id"] for n in flatten(comp, times[0])} if times else set()
    out = []
    for b in asked:
        at, to, want = float(b.get("at", 0)), float(b.get("to", b.get("at", 0))), str(b.get("expect", "")).strip()
        inside = [i for i, t in enumerate(times) if at - 1e-9 <= t <= to + 1e-9] or [min(range(len(times)), key=lambda i: abs(times[i] - at))]
        ts = [times[i] for i in inside]
        if want == "camera move":
            got = shots(comp, ts)
            ok = any(not _same_shot(got[0], s, W) for s in got[1:])
        elif want == "cut":
            ok = any(at - 1e-9 <= c <= to + 1e-9 for c in wf.cuts(comp))
        elif want == "pose change":
            ok = any(_pose_moved(rows[inside[0]], rows[i]) >= POSE_SAME for rows in vectors.values() for i in inside[1:])
        elif want.endswith((" moves", " shows")) and want.rsplit(" ", 1)[0] in ids:
            lid, verb = want.rsplit(" ", 1)
            ns = [next(n for n in flatten(comp, t) if n["id"] == lid) for t in ts]
            if verb == "shows":
                ok = any(_visible(n) and n["opacity"] >= SHOWN for n in ns)
            else:
                boxes = [drawn_box(n) for n in ns]
                ok = any(max(abs(p - q) for p, q in zip(boxes[0], bx)) > FRAMING_SAME * W for bx in boxes[1:])
        else:
            raise RostrumError(codes.BAD_ARGUMENT, where, f'beat expect "{want}"', "is not a beat review can check",
                               hint=f"Accepted: {', '.join(BEAT_KINDS)} (a layer id that exists).")
        if not ok:
            out.append({"kind": "beat_missing", "start": at, "end": to,
                        "text": f"{_span(at, to)}: the beat you declared, '{want}', never happens"})
    return out
