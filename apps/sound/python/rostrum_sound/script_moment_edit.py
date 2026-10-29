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
HIT_RING = 6.0          # a drum hit struck this long before the moment may still ring into it (a crash, a ride bell)
LEFT_RINGING = "drum hits left ringing"
WHY_HITS = ("a drum hit has no length to cut: it rings as its sample was recorded, so stop's short / release and choke "
            "leave hits as struck (they only drop hits that would start in the stop). To end one sooner: a shorter "
            "ring time written on the hit itself (track.hit('crash', at, decay=0.3); a recorded kit's one-shot samples ring on), or the cymbal on its own "
            "track with a volume lane falling after the moment")


class Counts(dict):
    def add(self, k, n=1):
        self[k] = self.get(k, 0) + n

    def said(self) -> str:
        return ", ".join(f"{n} {k}" for k, n in self.items() if n) or "nothing there to change"


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
            counts.add("notes dropped")
            continue
        new = end_at(start, end)
        if new is not None and new < end - 1e-6:
            if new - start < SLIVER:
                counts.add("notes dropped")
                continue
            f = {**f, "dur": _length(f, start, new, root)}
            counts.add("notes shortened")
        out.append((id_, f, own))
    track.notes = out


def drop_hits(track, root, where, keep, counts):
    kept = [h for h in track.hits if keep(times.seconds(h[1]["at"], root, where))]
    counts.add("hits dropped", len(track.hits) - len(kept))
    track.hits = kept


def hits_ringing(track, root, where, struck, counts):
    """Hits an end asked for would have shortened (`struck(start)`): kept as struck, counted, so the reply says why."""
    counts.add(LEFT_RINGING, sum(1 for _, h, _ in track.hits if struck(times.seconds(h["at"], root, where))))


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
    hits_ringing(track, root, where, lambda s: (on(s) and short is not None) or at - HIT_RING <= s < at - AT_ONCE, counts)


def choke(track, at, after, root, where, counts):
    """Notes sounding at the moment (started on it or before) end `after` seconds past it."""
    cut = at + after
    edit(track, root, where, lambda s: True, lambda s, e: cut if s <= at + AT_ONCE and e > cut else None, counts)
    hits_ringing(track, root, where, lambda s: at - HIT_RING <= s <= min(at + AT_ONCE, cut), counts)


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
