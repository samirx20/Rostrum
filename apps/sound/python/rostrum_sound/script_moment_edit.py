"""The note and hit edits behind a script's `moment(...)` (script_moment.py), on one track's written notes and hits.

Every edit works in seconds on the finished tempo map, then writes the new length back in the note's own form: a length
in beats stays in beats, seconds stay seconds, a tie (`end=` / "next") becomes a tie to the cut time. A note cut to
almost nothing (under a millisecond) is dropped, never kept as a silent sliver.
"""
from __future__ import annotations

from .doc import tempo, times
from .script_time import Beats

AT_ONCE = 0.03          # a note starting this close to the moment is played *on* it
SLIVER = 0.001
# How long before the moment a hit may still ring into it: cymbals and open hats for seconds, the other drums under one.
LONG_RING = frozenset({"crash", "crash2", "cymbal", "ride", "ride2", "rideBell", "china", "splash", "openHat"})
HIT_RING, DRUM_RING = 6.0, 1.0


class Counts(dict):
    """How many notes / hits each kind of change touched, and which (track and time), so a reply names what it dropped."""
    NAMED = 4                   # at most this many named per kind; then "+N more"

    def __init__(self):
        super().__init__()
        self.which = {}

    def add(self, k, n=1, which=()):
        self[k] = self.get(k, 0) + n
        self.which.setdefault(k, []).extend(which)

    def said(self) -> str:
        def one(k, n):
            w = self.which.get(k, [])
            more = f", +{len(w) - self.NAMED} more" if len(w) > self.NAMED else ""
            return f"{n} {k}" + (f" ({', '.join(w[:self.NAMED])}{more})" if w else "")
        return ", ".join(one(k, n) for k, n in self.items() if n) or "nothing there to change"


def _which(track, s) -> list[str]:
    return [f"{track.id} {s:.2f} s"]


def _span(track, f, root, where):
    """(start, end) seconds of a written note; "next" reads the track's other written notes."""
    start = times.seconds(f["at"], root, where)
    own = {**root, "tracks": [{"notes": [g for _, g, _ in track.notes]}]}
    return start, start + times.length_seconds(f["dur"], own, start, f, where)


def _length(f, start, end, root):
    d = f["dur"]
    if isinstance(d, dict) and "beats" in d:
        return Beats(round(tempo.beat_at(root, end) - tempo.beat_at(root, start), 9))
    if d == times.NEXT or (isinstance(d, dict) and "to" in d):
        return {"to": round(end, 6)}
    return round(end - start, 6)


def edit(track, root, where, keep, end_at, counts):
    """Each written note: `keep(start)` False drops it; `end_at(start, end)` gives a new end (or None: as written)."""
    out = []
    for id_, f, own in track.notes:
        start, end = _span(track, f, root, where)
        if not keep(start):
            counts.add("notes dropped", which=_which(track, start))
            continue
        new = end_at(start, end)
        if new is not None and new < end - 1e-6:
            if new - start < SLIVER:
                counts.add("notes dropped", which=_which(track, start))
                continue
            f = {**f, "dur": _length(f, start, new, root)}
            counts.add("notes shortened", which=_which(track, start))
        out.append((id_, f, own))
    track.notes = out


def drop_hits(track, root, where, keep, counts):
    kept, gone = [], []
    for h in track.hits:
        s = times.seconds(h[1]["at"], root, where)
        if keep(s):
            kept.append(h)
        else:
            gone += _which(track, s)
    counts.add("hits dropped", len(gone), gone)
    track.hits = kept


def rings_into(h, s, at) -> bool:
    """A hit struck at `s` before `at` may still sound at it (by its drum: a cymbal for seconds, a kick under one)."""
    ring = HIT_RING if not isinstance(h["drum"], str) or h["drum"] in LONG_RING else DRUM_RING
    return at - ring <= s < at - AT_ONCE


def cut_hits(track, root, where, end_at, counts):
    """Each hit `end_at(start, hit)` gives an end for (seconds, or None) gets `cut` = that end less its start (a cut
    already shorter stays); one cut to nothing is dropped. The engine stops it there on every kit, with a 10 ms fade."""
    out = []
    for id_, h, own in track.hits:
        s = times.seconds(h["at"], root, where)
        end = end_at(s, h)
        if end is not None:
            cut = round(end - s, 6)
            if cut < SLIVER:
                counts.add("hits dropped", which=_which(track, s))
                continue
            if h.get("cut") is None or cut < h["cut"]:
                h = {**h, "cut": cut}
                counts.add("hits cut")
        out.append((id_, h, own))
    track.hits = out


def rest(track, at, before, root, where, counts):
    """Nothing starts in [at-before, at); what sounds into it ends at at-before."""
    gap = at - before
    keep = lambda s: not gap - 1e-6 <= s < at - AT_ONCE
    edit(track, root, where, keep, lambda s, e: gap if s < gap - 1e-6 < e else None, counts)
    drop_hits(track, root, where, keep, counts)


def stop(track, at, until, short, release, root, where, counts):
    """On the moment plays (cut to `short` if given); ringing across it ends at at+release; nothing starts before `until`."""
    on = lambda s: abs(s - at) <= AT_ONCE
    keep = lambda s: not (at + AT_ONCE < s < until - 1e-6)

    def end_at(s, e):
        if on(s):
            return s + short if short is not None else None
        return at + release if s < at and e > at + release else None
    edit(track, root, where, keep, end_at, counts)
    drop_hits(track, root, where, keep, counts)
    cut_hits(track, root, where, lambda s, h: s + short if on(s) and short is not None else at + release if rings_into(h, s, at) else None, counts)


def choke(track, at, after, root, where, counts):
    """Notes sounding at the moment (started on it or before) end `after` seconds past it."""
    cut = at + after
    edit(track, root, where, lambda s: True, lambda s, e: cut if s <= at + AT_ONCE and e > cut else None, counts)
    cut_hits(track, root, where, lambda s, h: cut if (rings_into(h, s, at) or abs(s - at) <= AT_ONCE) and s < cut else None, counts)


def swell(track, at, over, low, root, where, counts):
    """Velocity of notes and hits starting in [at-over, at] scaled from `low` up to its full value at the moment."""
    a = at - over

    def scaled(entries, phrased):
        out = []
        for id_, f, own in entries:
            s = times.seconds(f["at"], root, where)
            if a - 1e-6 <= s <= at + AT_ONCE:
                base = f["vel"] if own else next((v for ph in reversed(phrased) if (v := ph.velocity(f["at"], root, where)) is not None), f["vel"])
                k = low + (1 - low) * min(1.0, max(0.0, (s - a) / over))
                f, own = {**f, "vel": round(base * k, 4)}, True
                counts.add("velocities shaped")
            out.append((id_, f, own))
        return out
    track.notes, track.hits = scaled(track.notes, track.phrases), scaled(track.hits, track.phrases)
