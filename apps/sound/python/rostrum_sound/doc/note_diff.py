"""What happened to the notes and drum hits between two states of a song: per track, which were added, removed, or
changed (pitch or drum, start, length, velocity). Notes are matched by id (an id is kept when a note moves or changes);
a note that moved to another track shows as removed on one and added on the other.

Plain data, no tool or screen: `inspect_note_changes` (mcp/tools_note_diff.py) words it.
"""
from __future__ import annotations

from . import tempo
from .select_time import end_of, start_of

_KEYS = (("notes", "note"), ("hits", "hit"))


def facts(root: dict, item: dict) -> dict:
    """One note's or hit's comparable facts: what (pitch or drum), start (s), length (beats; hits none), vel."""
    start = start_of(root, item)
    if item.get("type") == "hit":
        what, length = str(item["drum"]), None
    else:
        p = item["pitch"]
        what = "+".join(map(str, p)) if isinstance(p, list) else str(p)
        length = round(tempo.beat_at(root, end_of(root, item)) - tempo.beat_at(root, start), 4)
    return {"what": what, "start": round(start, 4), "length": length, "vel": round(float(item.get("vel", 0.85)), 3)}


def _items(root: dict, track_ids) -> dict:
    """{track id: {item id: item}} for the tracks asked (None: every track)."""
    out = {}
    for t in root.get("tracks", []):
        if track_ids is None or t["id"] in track_ids:
            out[t["id"]] = {i["id"]: i for key, _ in _KEYS for i in t.get(key, [])}
    return out


def changes(before: dict, after: dict, track_ids=None, window=None) -> dict:
    """{track id: {"added": [(id, facts)], "removed": [(id, facts)], "changed": [(id, old facts, new facts)]}}, only
    tracks with something in them, each list in time order. `window` (a, b) seconds keeps an item when it starts in it
    (`a` included, `b` not) before or after."""
    a_items, b_items = _items(before, track_ids), _items(after, track_ids)

    def inside(f):
        return window is None or window[0] - 1e-9 <= f["start"] < window[1] - 1e-9
    out = {}
    for tid in list(a_items) + [t for t in b_items if t not in a_items]:
        old, new = a_items.get(tid, {}), b_items.get(tid, {})
        fa = {i: facts(before, x) for i, x in old.items()}
        fb = {i: facts(after, x) for i, x in new.items()}
        added = [(i, fb[i]) for i in new if i not in old and inside(fb[i])]
        removed = [(i, fa[i]) for i in old if i not in new and inside(fa[i])]
        changed = [(i, fa[i], fb[i]) for i in new if i in old and fa[i] != fb[i] and (inside(fa[i]) or inside(fb[i]))]
        if added or removed or changed:
            out[tid] = {"added": sorted(added, key=lambda r: r[1]["start"]),
                        "removed": sorted(removed, key=lambda r: r[1]["start"]),
                        "changed": sorted(changed, key=lambda r: r[2]["start"])}
    return out


def counts(diff: dict) -> dict:
    return {k: sum(len(t[k]) for t in diff.values()) for k in ("added", "removed", "changed")}
