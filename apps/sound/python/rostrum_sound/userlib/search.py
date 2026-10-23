"""Searching the user's sound folders by kind and shape, in words or numbers:

    search(kind="whoosh", length="short", brightness="bright")
    search(kind=["click", "ui"], attack_ms=[0, 8], seconds=[0, 0.2])
    search(words="metal", kind="hit", lufs=[-30, 0])

and `closest`: the one sound nearest a target shape (a move's length, a brightness), for placing sounds by
themselves. Both are deterministic: the same library and the same ask give the same sounds in the same order.
"""
from __future__ import annotations

import math
from collections import Counter

from rostrum_core import RostrumError, codes

from . import folders as user_folders
from . import index, measure
from .kinds import KINDS, OFFERED

RANGES = {"seconds": "seconds", "brightness_range": "brightness", "attack_ms": "attack_ms", "lufs": "lufs"}


def sound_id(s: dict) -> str:
    return f"{s['path']}@{s['start']}"


def _list(v) -> list:
    return [] if v in (None, "", []) else ([v] if isinstance(v, str) else list(v))


def _spans(scale: str, words) -> list[tuple[float, float]]:
    try:
        return [measure.span(scale, w) for w in _list(words)]
    except ValueError as e:
        raise RostrumError(codes.BAD_ARGUMENT, "search", scale, str(e)) from e


def _rank(s: dict, kinds: list[str]) -> int:
    """How strongly the sound is one of the asked kinds: 0 = its strongest kind."""
    return min((s["kinds"].index(k) for k in kinds if k in s["kinds"]), default=99)


def library(folder_list=None, cache_dir=None) -> list[dict]:
    """Every indexed sound in the user's folders (or `folder_list`)."""
    return index.library(user_folders.folders() if folder_list is None else folder_list, cache_dir)


def search(kind=None, words=None, length=None, brightness=None, attack=None, seconds=None, brightness_range=None,
           attack_ms=None, lufs=None, limit=40, sounds=None, folder_list=None, cache_dir=None) -> dict:
    """The sounds matching every filter, strongest kind match first, then by file and time.
    kind: one kind or several (any of them). words: all must appear in the name, metadata or folders.
    length / brightness / attack: plain words (measure.SCALES) or several of them. seconds / brightness_range /
    attack_ms / lufs: [low, high] (either may be None). Returns {"total", "more", "sounds"}."""
    kinds = _list(kind)
    bad = [k for k in kinds if k not in KINDS and k != "other"]
    if bad:
        raise RostrumError(codes.BAD_ARGUMENT, "search", f"kind {bad}", "is not a sound kind", list(OFFERED))
    want = [w.lower() for w in (words or "").split()]
    spans = {f: _spans(s, v) for s, f, v in (("length", "seconds", length), ("brightness", "brightness", brightness),
                                             ("attack", "attack_ms", attack)) if _list(v)}
    ranges = {RANGES[k]: v for k, v in (("seconds", seconds), ("brightness_range", brightness_range),
                                        ("attack_ms", attack_ms), ("lufs", lufs)) if v is not None}
    pool = library(folder_list, cache_dir) if sounds is None else sounds
    found = []
    for s in pool:
        if kinds and _rank(s, kinds) == 99:
            continue
        text = f"{s['about']} {s.get('folder_words', '')} {s['path']}".lower()
        if any(w not in text for w in want):
            continue
        if any(not any(lo <= s[f] < hi for lo, hi in sp) for f, sp in spans.items()):
            continue
        if any((lo is not None and s[f] < lo) or (hi is not None and s[f] > hi) for f, (lo, hi) in ranges.items()):
            continue
        found.append(s)
    found.sort(key=lambda s: (_rank(s, kinds) if kinds else 0, s["path"].lower(), s["start"]))
    return {"total": len(found), "more": len(found) > limit, "sounds": found[:limit]}


def distance(s: dict, target: dict) -> float:
    """How far a sound is from a target shape: {"seconds", "brightness", "attack_ms"} (any of them)."""
    d = 0.0
    if "seconds" in target:
        d += abs(math.log(max(s["seconds"], 0.01) / max(target["seconds"], 0.01)))
    if "brightness" in target:
        d += 2.0 * abs(s["brightness"] - target["brightness"])
    if "attack_ms" in target:
        d += 0.5 * abs(math.log((s["attack_ms"] + 5) / (target["attack_ms"] + 5)))
    return d


def closest(sounds: list[dict], kinds: list[str], target: dict, used: Counter | None = None,
            nth: int = 0) -> dict | None:
    """The sound of one of `kinds` (earlier kinds preferred) nearest `target`; each earlier use in `used` pushes a
    sound back so a scene doesn't repeat one take; `nth` = the next-best (1), the one after (2)… Deterministic."""
    used = used or Counter()
    fits = [s for s in sounds if _rank(s, kinds) < 99]
    if not fits:
        return None

    def asked(s):            # its strongest kind and the first kind asked for count most
        return min(s["kinds"].index(k) + i for i, k in enumerate(kinds) if k in s["kinds"])
    ranked = sorted(fits, key=lambda s: (round(distance(s, target) + 0.6 * min(asked(s), 3)
                                               + 0.8 * used[sound_id(s)], 6), s["path"].lower(), s["start"]))
    return ranked[min(nth, len(ranked) - 1)]
