"""part_read: what each track plays, read from the song's document: when its notes and hits start and end, how loud
each is meant to be, which sound it plays and whether its brightness is written to move. Read by stall.py (which parts
did not rise into a peak) and static_part.py (a part that holds one sound at one level for many bars).

A note's level here is the level the document asks for, not a measurement: velocity x the track's dynamics lane
(automation "dynamics", CC 11) x its volume lane x its perform dynamics curve, at the note's start, x the mean of the
note's own dynamics shape. Times (seconds, beats or "#marker") go through doc/times.py, so call inside
markers.project(folder) when the song has project markers.

    played(track, data) -> [{"at", "end", "level", "art"}] in time order (notes and hits; a hit lasts 0.1 s)
    sound(track) -> "sfz:strings" / "builtIn:piano" ... (None: a track that plays no instrument)
    bright_moves(track) -> True when an effect's envelope on the track (a lowpass band's freq, a filter cutoff ...)
                           changes value: its brightness is written to move
"""
from __future__ import annotations

from ..doc import lanes as LN
from ..doc import times

HIT_S = 0.1


def _curve(pts, data, where) -> list[tuple[float, float]]:
    out = []
    for p in pts or []:
        try:
            out.append((times.seconds(p[0], data, where), float(p[1])))
        except Exception:  # noqa: BLE001  a point the document checks refuse is theirs to name
            continue
    return sorted(out)


def value_at(curve, t: float, rest: float = 1.0) -> float:
    """A lane's value at `t`: straight lines between points, held before the first and after the last."""
    if not curve:
        return rest
    if t <= curve[0][0]:
        return curve[0][1]
    for (a, va), (b, vb) in zip(curve, curve[1:]):
        if a <= t <= b:
            return va if b <= a else va + (vb - va) * (t - a) / (b - a)
    return curve[-1][1]


def lanes(track, data) -> list[list]:
    """The track's level lanes as curves in seconds: its dynamics and volume automation, its perform dynamics."""
    out = [_curve(LN.points(track, k), data, f"{track.get('id')} {k}") for k in ("dynamics", "volume")]
    perf = track.get("perform")
    if isinstance(perf, dict) and isinstance(perf.get("dynamics"), list):
        out.append(_curve(perf["dynamics"], data, f"{track.get('id')} perform.dynamics"))
    return [c for c in out if c]


def _shape_mean(note) -> float:
    pts = note.get("dynamics")
    if not isinstance(pts, list) or not pts:
        return 1.0
    return sum(float(p[1]) for p in pts) / len(pts)


def played(track, data) -> list[dict]:
    curves = lanes(track, data)
    out = []
    for key in ("notes", "hits"):
        for n in track.get(key) or []:
            try:
                at = times.seconds(n["at"], data, f"{n.get('id')} at")
                end = at + (times.length_seconds(n["dur"], data, at, n) if key == "notes" and n.get("dur") is not None else HIT_S)
            except Exception:  # noqa: BLE001
                continue
            level = float(n.get("vel", 0.8)) * _shape_mean(n)
            for c in curves:
                level *= value_at(c, at)
            out.append({"at": at, "end": max(end, at + HIT_S), "level": level, "art": n.get("art")})
    return sorted(out, key=lambda r: r["at"])


def sound(track) -> str | None:
    form = track.get("instrument")
    if isinstance(form, str) and isinstance(track.get(form), (str, dict)):
        v = track[form]
        return f"{form}:{v if isinstance(v, str) else v.get('name') or v.get('preset') or form}"
    return None


def bright_moves(track) -> bool:
    for fx in track.get("effects") or []:
        if not isinstance(fx, dict) or fx.get("type") != "effect":
            continue
        try:
            names = LN.offered(fx)
        except Exception:  # noqa: BLE001  an effect this reader does not know: not a written brightness move
            continue
        for lane in names:
            vals = {round(float(p[1]), 3) for p in LN.points(fx, lane)}
            if len(vals) > 1:
                return True
    return False
