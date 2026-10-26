"""Song sections (intro, verse, drop): named stretches of the song, and what moving one moves.

`moves(root, section, by, carry_markers=False)` plans `section.move`: the section and everything that starts inside
it (at ≥ its start, before its end) — notes, hits, clips, voice lines, tempo, time signature and key changes, other
sections and automation points — shifted by `by`: seconds (2.5, -1) or `{"beats": n}` (n may be negative). Every
time keeps its form: beats stay beats (moved by whole beats when `by` is in beats), seconds stay seconds, a time on
a marker keeps the marker with a new offset. All new values are worked out from the song as it was, then set
together (one operation, one undo step).

Which notes a section owns (`window`, the one rule for every section edit): a note, hit, clip or line belongs to the
section it starts in by its musical place, so both of the section's lines count EARLY beats (a 1/32 note, the
widest Humanise / Feel nudge) sooner: a chorus's first hit nudged to beat 47.989 belongs to the chorus that starts
at 48, and a crash at 79.99 belongs to the section that starts at 80, not the one ending there. Tempo, time
signature and key changes, markers, sections and automation points are placed exactly: they keep the plain lines.

What stays (the rule):
- **Markers stay.** A marker is a sync point (a picture cut, "logo lands"): moving music never moves it. The
  project's shared markers never move here; the song's own markers move only when asked (`carry_markers`, the
  operation's `markers: true`), and then only those inside the section.
- **The song's opening tempo, time signature and key changes (at 0) stay**, so the song never loses its start.
- **What a section carries is what is inside it in the song it is given.** A drag on the screen plans every step
  from the song as it was at the press (moves.section_calls, a fresh preview), so whatever the moving section
  passes over is never picked up, and its one recorded `by` (the whole drag) replays to the same song.
"""
from __future__ import annotations

from rostrum_core import RostrumError, codes
from rostrum_core.tree import walk

from . import markers, meter, tempo, times
from .registry import LISTS
from .shift import write_like

TIMED = ("note", "hit", "clip", "line", "marker", "tempo", "meter", "key", "section")
OPENING = ("tempo", "meter", "key")
PLAYED = ("note", "hit", "clip", "line")       # what a section owns by its musical place (window)
EARLY = meter.EARLY                             # beats: a 1/32 note, the widest nudge Humanise / Feel give


def _early(root: dict, sec: float) -> float:
    beat = tempo.beat_at(root, sec) - EARLY
    return float("-inf") if beat < 1e-9 else tempo.seconds_at(root, beat)


def window(root: dict, a: float, b: float) -> tuple[float, float]:
    """The seconds a section from `a` to `b` (seconds) owns notes, hits, clips and lines in: both lines EARLY beats
    sooner (at the tempo there), so a hit nudged a hair before a section line belongs to the section it opens. A
    section at the song's start owns everything before its end window."""
    return _early(root, a), _early(root, b)


def starts_in(sec: float, win: tuple[float, float]) -> bool:
    """Whether a start at `sec` seconds falls in `win` (from `window`)."""
    return win[0] - 1e-6 <= sec < win[1] - 1e-6


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


def moves(root: dict, section: dict, by, carry_markers: bool = False) -> list[tuple[str, str, object]]:
    """[(item id, field, new value)] for moving `section` by `by`. Raises when something would land before 0."""
    where = f"section.move {section['id']}"
    lo = times.seconds(section["at"], root, where)
    hi = times.seconds(section["end"], root, where)

    played = window(root, lo, hi)

    def inside(sec, t=None):
        return starts_in(sec, played) if t in PLAYED else lo - 1e-9 <= sec < hi - 1e-9

    moved_marks = {name for name, sec in markers.all(root, own=True) if inside(sec)} if carry_markers else set()

    def carried(t, sec):
        if t == "marker":
            return carry_markers
        return not (t in OPENING and sec < 1e-9)          # the song's opening tempo / time signature / key stays

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
        if t in TIMED and "at" in item and (iid == section["id"] or (
                inside(sec := times.seconds(item["at"], root, iid), t) and carried(t, sec))):
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
