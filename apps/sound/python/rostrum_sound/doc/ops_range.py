"""`range.remove` / `range.insert`: take time out of the whole song, or make room in it, across ALL tracks.

Everything the song's own document places in time after the range shifts: notes, hits, clips,
voice lines, automation points, sections, tempo and key changes, the song's own markers and a set song length.
What lies inside a removed range goes (a clip or note crossing its edge is cut there, a section is cut to what is
left, the last tempo / key change inside moves to the start of the range so the song keeps playing in it after).
Insert cuts a clip that crosses the point in two and leaves notes as long as they were.

Project (shared) markers are NOT moved: they belong to the whole project (the Editor and 2D read them), so a Sound
operation never rewrites them. Times written on a marker keep it ("#drop+0.5") and follow it when it is the
song's own. Beat times move in beats and seconds in seconds (the tempo map stays true, tempo.py); an insert is
played at the tempo where it lands. All new times are worked out from the song as it was, then set together:
one operation, one undo step. Clips are cut with `clip.cut_range`'s own cutter (ops_select_place._cut).
"""
from __future__ import annotations

from rostrum_core import codes
from rostrum_core.tree import walk

from . import markers, tempo, times
from . import values as V
from .ops_select_place import _cut
from .registry import LISTS, REGISTRY
from .select_time import clip_length, start_of

POINTS = ("note", "hit", "line")                       # a moment each: inside a removed range = gone
CHANGES = ("tempo", "meter", "key")


class Map:
    """Where a time goes, in seconds and in beats: the one rule both operations share. `grow`: time is made at `a`."""

    def __init__(self, root, a, b, grow):
        self.root, self.a, self.b, self.grow, self.size = root, a, b, grow, b - a
        self.ba = tempo.beat_at(root, a)
        self.beats = self.size * tempo.bpm_at(root, a) / 60.0 if grow else tempo.beat_at(root, b) - self.ba
        self.moved = {markers.key(n): self.at(t) for n, t in markers.all(root, own=True)}   # own markers: new place

    def at(self, t: float) -> float:
        if self.grow:
            return t + self.size if t >= self.a - 1e-9 else t
        return t if t < self.a else self.a if t < self.b - 1e-9 else t - self.size

    def beat(self, x: float) -> float:
        if self.grow:
            return x + self.beats if x >= self.ba - 1e-9 else x
        return x if x < self.ba else self.ba if x < self.ba + self.beats - 1e-9 else x - self.beats

    def inside(self, t: float) -> bool:
        return not self.grow and self.a - 1e-9 <= t < self.b - 1e-9

    def put(self, old, where: str):
        """`old` (a time in any form) after the move, written in the same form."""
        name = markers.ref(old)
        if name is not None:
            base = self.moved.get(markers.key(name), markers.time_of(self.root, name))
            off = round(self.at(times.seconds(old, self.root, where)) - base, 4)
            return f"#{name}" if abs(off) < 1e-6 else f"#{name}{off:+g}"
        if isinstance(old, dict) and "beat" in old:
            return {"beat": round(self.beat(float(old["beat"])), 4)}
        return round(self.at(float(old)), 4)


def _note_dur(root, m: Map, note, s):
    """A note's new length: tied ends move with their time; a note running into a removed range ends at its start."""
    d, i = note["dur"], note["id"]
    if d == "next":
        return []
    if isinstance(d, dict) and "to" in d:
        new = {"to": m.put(d["to"], i)}
        return [(i, "dur", new)] if new != d else []
    e = s + times.length_seconds(d, root, s, note, i)
    if m.grow or s >= m.a or e <= m.a:
        return []
    new = max(m.at(e), s + 0.01) - s
    return [(i, "dur", {"beats": round(tempo.beat_at(root, s + new) - tempo.beat_at(root, s), 4)}
             if isinstance(d, dict) else round(new, 4))]


def _changes(root, m: Map) -> tuple[list, list]:
    """Tempo / key changes inside a removed range: all go, except the last, which moves to the range's start
    (so the song keeps its tempo / key there) unless a change already sits at the range's end."""
    gone, sets = [], []
    for kind in CHANGES:
        items = [c for c in root.get(kind + "s", []) if "at" in c]
        inside = sorted((c for c in items if m.inside(times.seconds(c["at"], root, c["id"]))),
                        key=lambda c: times.seconds(c["at"], root, c["id"]))
        gone += [c["id"] for c in inside]
        if inside and not any(abs(times.seconds(c["at"], root, c["id"]) - m.b) < 1e-6 for c in items):
            gone.pop()
            sets.append((inside[-1]["id"], "at", {"beat": round(m.ba, 4)} if isinstance(inside[-1]["at"], dict)
                         else round(m.a, 4)))
    return sets, gone


def _plan(root: dict, m: Map) -> tuple[list, list]:
    """([(id, field, value)], [ids to remove]) for everything but the clips that cross the range."""
    sets, gone = _changes(root, m) if not m.grow else ([], [])
    cut = set(gone) | {i for i, _, _ in sets}
    named = {markers.key(markers.ref(r)) for r in markers.refs_in(root)}
    for item in walk(root, LISTS):
        t, i = item.get("type"), item["id"]
        if t == "automation":
            pts = [[m.put(p[0], i), *p[1:]] for p in item.get("points", [])
                   if not m.inside(times.seconds(p[0], root, i))]
            if pts != item.get("points", []):
                sets.append((i, "points", pts))
        elif "at" not in item or i in cut or t not in POINTS + CHANGES + ("clip", "marker", "section"):
            continue
        else:
            s = times.seconds(item["at"], root, i)
            if t in POINTS + ("marker",) and m.inside(s) and (t != "marker" or markers.key(item.get("name", i)) not in named):
                gone.append(i)
            elif t == "section" and m.at(times.seconds(item["end"], root, i)) - m.at(s) < 1e-6:
                gone.append(i)
            elif t == "section":
                sets += [(i, k, m.put(item[k], i)) for k in ("at", "end")]
            elif t != "clip" or s >= (m.a if m.grow else m.b) - 1e-9:
                sets.append((i, "at", m.put(item["at"], i)))
            if t == "note" and i not in gone:
                sets += _note_dur(root, m, item, s)
    if "length" in root:
        sets.append(("root", "length", m.put(root["length"], "length")))
    return sets, gone


def _apply(ctx, a: float, b: float, grow: bool):
    root = ctx.doc
    if b - a < 1e-4:
        ctx.fail(codes.BAD_ARGUMENT, "end" if not grow else "length", "must be more than nothing",
                 hint="Give a stretch, not a moment.")
    cross = [(t["id"], c["id"]) for t in root.get("tracks", []) for c in t.get("clips", [])
             if start_of(root, c) < (a if grow else b) - 1e-6 and start_of(root, c) + clip_length(c, root) > a + 1e-6
             and (grow or start_of(root, c) < b - 1e-6)]
    m = Map(root, a, b, grow)
    if grow:                                                      # cut crossing clips at the point first, then move
        for t, c in cross:
            _cut(ctx, t, ctx.item(c), a, a)
        m.root = ctx.doc
    sets, gone = _plan(ctx.doc, m)
    for id_, key, value in sets:
        ctx.set(id_, key, value)
    if not grow:
        for t, c in cross:
            _cut(ctx, t, ctx.item(c), a, b)
    for id_ in gone:
        ctx.remove(id_)


FROM = V.time("at", required=True, group="Range", label="From", help="Where the time starts.")
TO = V.time("end", required=True, group="Range", label="To", help="Where it ends; what follows moves earlier.")
LEN = V.length("length", required=True, group="Range", label="How long",
               help='Seconds (2.5) or {"beats": 4}: how much time to make; everything after moves later.')


@REGISTRY.operation("range.remove", "Delete a stretch of time from the whole song, every track: what is inside "
                    "goes, what follows moves earlier. Project (shared) markers do not move.", params=[FROM, TO],
                    label="Delete time", importance="secondary")
def range_remove(ctx, targets, args):
    a, b = sorted(times.seconds(args[k], ctx.doc, "range.remove") for k in ("at", "end"))
    _apply(ctx, a, b, False)


@REGISTRY.operation("range.insert", "Make room in the whole song, every track: everything from the point on moves "
                    "later (a clip across the point is cut in two). Project (shared) markers do not move.",
                    params=[FROM, LEN], label="Insert time", importance="secondary")
def range_insert(ctx, targets, args):
    a = times.seconds(args["at"], ctx.doc, "range.insert")
    n = args["length"]
    sec = tempo.seconds_at(ctx.doc, tempo.beat_at(ctx.doc, a) + float(n["beats"])) - a if isinstance(n, dict) \
        else times.seconds(n, ctx.doc, "range.insert")
    _apply(ctx, a, a + sec, True)
