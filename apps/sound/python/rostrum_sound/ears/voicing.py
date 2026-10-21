"""Voicing checks on the notes a document writes: plain facts about what sounds together, never taste. Each returns
events {kind, at_s, tracks, notes, why, count}; a repeated figure (an ostinato) is one event with `count`."""
from __future__ import annotations

from itertools import combinations

import numpy as np

from ..doc import keys
from ..doc.keys import pitch_name as _name
from .theory import interval_name, low_interval_limit

WIDE_UPPER = 12                 # semitones: more than an octave between neighbouring upper voices


def merge_repeats(events: list[dict]) -> list[dict]:
    """The same finding at several times becomes one event (first time, `count`, up to 3 `also_at_s`)."""
    out: dict = {}
    for e in events:
        k = (e["kind"], tuple(e["notes"]), tuple(e["tracks"]))
        if k in out:
            out[k]["count"] += 1
            if len(out[k]["also_at_s"]) < 3:
                out[k]["also_at_s"].append(round(e["at_s"], 2))
        else:
            out[k] = {**e, "at_s": round(e["at_s"], 2), "count": 1, "also_at_s": []}
    return list(out.values())


def range_problems(notes, ranges: dict) -> list[dict]:
    """Notes outside what their track's instrument can play. `ranges` {track: (lowest MIDI, highest MIDI)}."""
    ev = []
    for n in notes:
        lo, hi = ranges.get(n["track"], (None, None))
        for m in n["midis"]:
            if lo is not None and not lo <= m <= hi:
                side = f"below its lowest note {_name(lo)}" if m < lo else f"above its highest note {_name(hi)}"
                ev.append({"kind": "out_of_range", "at_s": n["start"], "tracks": [n["track"]], "notes": [_name(m)],
                           "why": f"{_name(m)} is {side}"})
    return merge_repeats(ev)


def _stacks(notes):
    """[(time, [(midi, track)] sounding)] at each distinct note start."""
    starts = np.array([n["start"] for n in notes])
    ends = np.array([n["end"] for n in notes])
    for t in sorted(set(np.round(starts, 4))):
        idx = np.nonzero((starts <= t + 1e-4) & (ends > t + 1e-4))[0]
        yield float(t), sorted({(m, notes[i]["track"]) for i in idx for m in notes[i]["midis"]})


def stack_problems(notes) -> list[dict]:
    """Close intervals low down (under the low-interval limit) and upper voices more than an octave apart."""
    ev = []
    for t, st in _stacks(notes):
        mids = sorted({m for m, _ in st})
        for lo, hi in zip(mids, mids[1:]):
            lim = low_interval_limit(hi - lo)
            if lim is not None and lo < lim:
                who = sorted({tr for m, tr in st if m in (lo, hi)})
                ev.append({"kind": "close_interval_low", "at_s": t, "tracks": who, "notes": [_name(lo), _name(hi)],
                           "why": f"a {interval_name(hi - lo)} ({_name(lo)}–{_name(hi)}) under {_name(lim)} is muddy"})
        for lo, hi in zip(mids[1:], mids[2:]):
            if hi - lo > WIDE_UPPER:
                ev.append({"kind": "wide_upper_spacing", "at_s": t, "tracks": sorted({tr for m, tr in st if m in (lo, hi)}),
                           "notes": [_name(lo), _name(hi)],
                           "why": f"{_name(lo)} and {_name(hi)} are {hi - lo} semitones apart (over an octave) between upper voices"})
    return merge_repeats(ev)


def crossings(notes, min_apart: int = 3) -> list[dict]:
    """Single-line tracks whose order flips: the track that sits lower on average goes above the other one."""
    by: dict = {}
    for n in notes:
        by.setdefault(n["track"], []).append(n)
    lines = {t: v for t, v in by.items() if all(len(n["midis"]) == 1 for n in v)}
    mean = {t: float(np.mean([n["midis"][0] for n in v])) for t, v in lines.items()}
    ev = []
    for a, b in combinations(lines, 2):
        up, low = (a, b) if mean[a] >= mean[b] else (b, a)
        if mean[up] - mean[low] < min_apart:
            continue
        for lo_n in lines[low]:
            for up_n in lines[up]:
                if min(lo_n["end"], up_n["end"]) - max(lo_n["start"], up_n["start"]) > 0.05 and lo_n["midis"][0] > up_n["midis"][0]:
                    ev.append({"kind": "voice_crossing", "at_s": max(lo_n["start"], up_n["start"]), "tracks": [low, up],
                               "notes": [_name(lo_n["midis"][0]), _name(up_n["midis"][0])],
                               "why": f"{low} (usually lower) plays {_name(lo_n['midis'][0])}, above {up}'s {_name(up_n['midis'][0])}"})
    return merge_repeats(ev)


def out_of_key(notes, root: dict, fallback: str | None) -> list[dict]:
    """Notes whose pitch class is not in the key playing at the time (the document's key map, else `fallback`)."""
    ev = []
    for n in notes:
        k = keys.key_at(root, n["start"]) or fallback
        if k is None:
            continue
        for m in n["midis"]:
            if not keys.in_key(m, k):
                ev.append({"kind": "out_of_key", "at_s": n["start"], "tracks": [n["track"]], "notes": [_name(m)],
                           "why": f"{_name(m)} is not in {k}"})
    return merge_repeats(ev)
