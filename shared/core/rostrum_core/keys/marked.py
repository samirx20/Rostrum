"""Keys timed on a shared marker: a key's `t` may be a marker reference (`"#drop+0.2"`, `"#hush-0.5"`, read by
marker_times.py, the one reader every app shares) instead of seconds. It means that moment on the project
timeline, the marker's time plus the offset, whatever its owner counts its other times from; so a key may sit
before its layer's own start (a pre-roll: the move is already under way when the layer appears).

The document keeps the reference as written. An app turns it into seconds once, where its document becomes times
(`resolve`; 2D: retime.py), so moving the marker moves the key and a marker that is gone fails loudly naming the
key. Readers of the document as written never do arithmetic on such a `t`: they sort with `order`, match with
`same_time` and show the key with `label` (the marker's name).
"""
from __future__ import annotations

import re

from ..marker_times import FORMS, ref, seconds, split, write  # noqa: F401  (FORMS: for errors)


def marked(key: dict) -> bool:
    """True when the key's time names a marker."""
    return isinstance(key.get("t"), str)


def order(t) -> tuple:
    """A sort key for times as written: seconds by value, then marker keys by name (their seconds need markers)."""
    return (1, str(t)) if isinstance(t, str) else (0, float(t))


def same_time(a, b) -> bool:
    """Two written times are the same moment: equal seconds, or the same marker and offset."""
    if isinstance(a, str) or isinstance(b, str):
        pa, pb = split(a), split(b)
        return pa is not None and pb is not None and pa[0].lower() == pb[0].lower() and abs(pa[1] - pb[1]) < 1e-6
    return abs(a - b) < 1e-6


def label(t) -> str:
    """How a person reads a key time: "1.25 s", or "drop +0.2 s" / "hush -0.5 s" / "drop"."""
    parts = split(t)
    if parts is None:
        return f"{float(t):g} s"
    name, off = parts
    return name if abs(off) < 1e-6 else f"{name} {off:+g} s"


def id_part(t) -> str:
    """The time part of a key's id: `k1500` for 1.5 s, `k_drop_p200` for "#drop+0.2" (a re-run finds it again)."""
    parts = split(t)
    if parts is None:
        return f"k{int(round(float(t) * 1000))}"
    name, off = parts
    ms = int(round(off * 1000))
    slug = re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_").lower() or "marker"
    return f"k_{slug}" + ("" if ms == 0 else f"_{'p' if ms > 0 else 'm'}{abs(ms)}")


def resolve(owner: dict, times: dict[str, float] | None, origin: float = 0.0) -> None:
    """In place, on a copy the app made: every marker key of `owner` gets `t` in the owner's seconds (the
    marker's time + offset - `origin`, where the owner's time 0 sits) and keeps what was written in `ref`."""
    for k in owner.get("keys", []):
        if marked(k):
            k["ref"] = k["t"]
            k["t"] = seconds(k["t"], times or {}, k.get("id", "key")) - origin


def moved(written, by: float):
    """The time to write for a key dragged `by` seconds: a key on a marker stays on that marker with a new offset
    ("#drop+0.2" by 0.15 -> "#drop+0.35"), so moving the marker still moves it; seconds just add."""
    parts = split(written)
    if parts is None:
        return round(float(written) + by, 6)
    return write(parts[0], round(parts[1] + by, 6))


def names(node) -> set[str]:
    """Every marker name a key inside `node` (a document, a composition, a layer) is timed on: part of a render's
    cache key, so moving one of them re-renders and moving any other doesn't."""
    out: set[str] = set()
    if isinstance(node, dict):
        if "prop" in node and marked(node):
            out.add(ref(node["t"]))
        for v in node.values():
            out |= names(v)
    elif isinstance(node, list):
        for v in node:
            out |= names(v)
    return out
