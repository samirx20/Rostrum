"""Song sections (intro, verse, drop): named stretches of the song, and what moving one moves.

`moves(root, section, by)` plans `section.move`: the section and everything that starts inside it (at ≥ its start,
before its end) — notes, hits, clips, designed sounds, voice lines, markers, tempo and key changes, other sections,
and automation points — shifted by `by`: seconds (2.5, -1) or `{"beats": n}` (n may be negative). Every time keeps
its form: beats stay beats (moved by whole beats when `by` is in beats), seconds stay seconds, a time on a marker
that moves too follows it untouched, one on a marker that stays keeps the marker with a new offset. All new
values are worked out from the song as it was, then set together (one operation, one undo step).
"""
from __future__ import annotations

from rostrum_core import RostrumError, codes
from rostrum_core.tree import walk

from . import markers, tempo, times
from .registry import LISTS
from .shift import write_like

TIMED = ("note", "hit", "clip", "sound", "line", "marker", "tempo", "key", "section")


def by_problem(v) -> str | None:
    """Why `v` is not a move amount, or None."""
    if isinstance(v, bool):
        return "is not an amount"
    if isinstance(v, (int, float)):
        return None
    if isinstance(v, dict) and set(v) == {"beats"} and isinstance(v["beats"], (int, float)) \
            and not isinstance(v["beats"], bool):
        return None
    return 'must be seconds (2.5, -1) or {"beats": n}'


def _dt(sec: float, by, root) -> float:
    if isinstance(by, dict):
        return tempo.seconds_at(root, tempo.beat_at(root, sec) + float(by["beats"])) - sec
    return float(by)


def moves(root: dict, section: dict, by) -> list[tuple[str, str, object]]:
    """[(item id, field, new value)] for moving `section` by `by`. Raises when something would land before 0."""
    where = f"section.move {section['id']}"
    lo = times.seconds(section["at"], root, where)
    hi = times.seconds(section["end"], root, where)

    def inside(sec):
        return lo - 1e-9 <= sec < hi - 1e-9

    moved_marks = {name for name, sec in markers.all(root) if inside(sec)}

    def follows(value):
        return markers.ref(value) in moved_marks

    def new(value, w):
        s = times.seconds(value, root, w)
        to = s + _dt(s, by, root)
        if to < -1e-9:
            raise RostrumError(codes.BAD_ARGUMENT, where, f"by={by!r}", f"would put {w} before the start of the song")
        return write_like(value, max(0.0, to), root) if not follows(value) else value, to

    out = []
    for item in walk(root, LISTS):
        t, iid = item.get("type"), item["id"]
        if t in TIMED and "at" in item and (iid == section["id"] or inside(times.seconds(item["at"], root, iid))):
            for key in ("at", "end") if t == "section" else ("at",):
                v, _ = new(item[key], f"{iid}.{key}")
                if v != item[key]:
                    out.append((iid, key, v))
        elif t == "automation" and any(inside(times.seconds(p[0], root, iid)) for p in item.get("points", [])):
            pts = []
            for p in item["points"]:
                s = times.seconds(p[0], root, iid)
                pts.append(([new(p[0], iid)[0], p[1]], new(p[0], iid)[1]) if inside(s) else (list(p), s))
            out.append((iid, "points", [p for p, _ in sorted(pts, key=lambda x: x[1])]))
    return out


def problems(root: dict) -> list[str]:
    """Sections that end before they start, and two sections with one name."""
    out, names = [], [s.get("name") for s in root.get("sections", [])]
    out += [f"two sections are named {n!r}" for n in sorted(set(names), key=str) if names.count(n) > 1]
    for s in root.get("sections", []):
        try:
            if times.seconds(s["end"], root, s["id"]) <= times.seconds(s["at"], root, s["id"]):
                out.append(f"{s['id']}: ends before it starts")
        except (RostrumError, KeyError):
            pass                                        # a missing marker is reported by the marker check
    return out
