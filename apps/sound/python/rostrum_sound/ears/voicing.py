"""Voicing checks on the notes a document writes: plain facts about what sounds together, never taste. Each returns
events {kind, at_s, tracks, notes, why, count}; a repeated figure (an ostinato) is one event with `count`."""
from __future__ import annotations

from itertools import combinations

import numpy as np

from ..doc import keys, meter, tempo, times
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
    """Close intervals low down (under the low-interval limit, across all tracks: parts piling up low are mud) and upper voices more than an octave apart (inside one track)."""
    ev = []
    for t, st in _stacks(notes):
        mids = sorted({m for m, _ in st})
        for lo, hi in zip(mids, mids[1:]):
            lim = low_interval_limit(hi - lo)
            if lim is not None and lo < lim:
                who = sorted({tr for m, tr in st if m in (lo, hi)})
                ev.append({"kind": "close_interval_low", "at_s": t, "tracks": who, "notes": [_name(lo), _name(hi)],
                           "why": f"a {interval_name(hi - lo)} ({_name(lo)}–{_name(hi)}) under {_name(lim)} is muddy"})
    return merge_repeats(ev + _wide_upper(notes))


def _wide_upper(notes) -> list[dict]:
    """Upper voices more than an octave apart, judged inside each track's own chord (a melody over its accompaniment is
    two parts, not one voicing: their distance is not a spacing problem)."""
    ev = []
    for tr in sorted({n["track"] for n in notes}):
        for t, st in _stacks([n for n in notes if n["track"] == tr]):
            mids = sorted({m for m, _ in st})
            for lo, hi in zip(mids[1:], mids[2:]):
                if hi - lo > WIDE_UPPER:
                    ev.append({"kind": "wide_upper_spacing", "at_s": t, "tracks": [tr], "notes": [_name(lo), _name(hi)],
                               "why": f"{_name(lo)} and {_name(hi)} are {hi - lo} semitones apart (over an octave) between {tr}'s upper voices"})
    return ev


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


def key_changes(root: dict) -> list[tuple[float, str]]:
    """The document's key list as (seconds, key), in time order: the one source every key check reads."""
    return sorted((times.seconds(k.get("at", 0), root, k["id"]), k["key"]) for k in root.get("keys", []) if k.get("key"))


def _leads_into(root: dict, changes, sec: float, midi: int, now: str):
    """(seconds, key) of the key change this note leads into: the next change, at most a bar after the note, to a key
    the note belongs to (the new key's dominant in the bar before it, say); None otherwise."""
    t, k = next(((t, k) for t, k in changes if t > sec + 1e-9), (None, None))
    if t is None or k == now or not keys.in_key(midi, k):
        return None
    b0, b1 = tempo.beat_at(root, sec), tempo.beat_at(root, t)
    return (t, k) if b1 - b0 <= meter.per_bar_at(root, int(b1)) + 1e-6 else None


def out_of_key(notes, root: dict, fallback: str | None) -> list[dict]:
    """Notes whose pitch class is not in the key playing at the time (the document's key map, else `fallback`). A note of
    the next key in the bar before a key change is not out of key: it leads into that key (kind "leads_into_key")."""
    ev = []
    changes = key_changes(root)
    for n in notes:
        k = keys.key_at(root, n["start"]) or fallback
        if k is None:
            continue
        for m in n["midis"]:
            if keys.in_key(m, k):
                continue
            lead = _leads_into(root, changes, n["start"], m, k)
            if lead:
                ev.append({"kind": "leads_into_key", "at_s": n["start"], "tracks": [n["track"]], "notes": [_name(m)], "key": k,
                           "into": lead[1], "why": f"{_name(m)} is not in {k}: it leads into {lead[1]} (from {lead[0]:.1f} s)"})
            else:
                ev.append({"kind": "out_of_key", "at_s": n["start"], "tracks": [n["track"]], "notes": [_name(m)], "key": k,
                           "why": f"{_name(m)} is not in {k}"})
    return merge_repeats(ev)
