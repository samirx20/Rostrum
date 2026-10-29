"""Ids for things inside a track, from their content (shared/core OPERATIONS.md § 2): a note `strings.n1500`
(starts at 1500 ms), a hit `drums.kick0`, a clip `door.c3000`, an effect `pad.eq_1`, a lane `pad.auto_volume`,
a marker `marker.drop`. Two things at the same place get `_2`, `_3` in the order they were made, so the same
script gives the same ids every run and inserting one earlier shifts no other id. Written ids always win.
"""
from __future__ import annotations

from rostrum_core import ids as core_ids

from . import times


def _free(id_: str, taken) -> str:
    n, out = 1, id_
    while out in taken:
        n += 1
        out = f"{id_}_{n}"
    return out


def timed(parent: str, tag: str, at, root: dict, taken, where: str) -> str:
    """`<parent>.<tag><ms>` from where the thing starts (marker references and beats made seconds)."""
    ms = times.seconds(at, root, where) * 1000
    return _free(core_ids.from_content(parent, tag, ms), taken)


def note(track: str, at, root, taken, where="note") -> str:
    return timed(track, "n", at, root, taken, where)


def hit(track: str, drum, at, root, taken, where="hit") -> str:
    return timed(track, drum if isinstance(drum, str) else f"k{drum}", at, root, taken, where)


def clip(track: str, at, root, taken, where="clip") -> str:
    return timed(track, "c", at, root, taken, where)


def effect(parent: str, type_: str, taken) -> str:
    return core_ids.counted(taken, f"{parent}.{type_}")


def named(parent: str, tag: str, taken) -> str:
    """`<parent>.<tag>`: a thing made once per parent under a fixed name (a track's shape lowpass)."""
    return _free(f"{parent}.{tag}", taken)


def lane(parent: str, lane_: str) -> str:
    return f"{parent}.auto_{lane_}"


def marker(name: str) -> str:
    """`marker.logo_lands` for "logo lands": no spaces, so an id is one word in a list. (Older files keep their ids.)"""
    return "marker." + "_".join(name.split())
