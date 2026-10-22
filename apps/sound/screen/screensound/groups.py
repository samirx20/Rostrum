"""Groups in the arrangement (DESIGN.md §3.1d): a bus that tracks play into is drawn as a header row above its tracks,
which sit under it indented; folded, the tracks hide behind the header, whose lane shows their blocks faintly. No Qt.

`arrange` puts the track rows (doc order) and the compact bus / master rows into the order the arrangement draws.
A track's place in the document does not change: a group's tracks are drawn together where its first track is.
Which groups are folded is the person's own screen state (the bridge holds it), never the song.
"""
from __future__ import annotations

from rostrum_sound import names


def _children(root: dict) -> dict[str, list[str]]:
    """{bus id: ids of the tracks and buses that play to it}, tracks first, each in document order."""
    out: dict[str, list[str]] = {}
    for item in [*root.get("tracks", []), *root.get("buses", [])]:
        if item.get("output", names.MASTER_OUT) in {b["id"] for b in root.get("buses", [])}:
            out.setdefault(item["output"], []).append(item["id"])
    return out


def arrange(root: dict, tracks: list[dict], mix: list[dict], folded) -> list[dict]:
    """Track rows and mix rows in drawing order: group headers (`group`, `depth`, `folded`, `count`) above their
    tracks (`depth` 1 and more), the bus rows that are not groups and the master last."""
    kids, by_id = _children(root), {r["id"]: r for r in [*tracks, *mix]}
    out, seen = [], set()

    def below(bus: str) -> list[str]:
        """Everything that plays into this bus, down through groups inside it."""
        return [x for k in kids.get(bus, []) for x in [k, *below(k)]]

    def emit(bus: str, depth: int):
        seen.add(bus)
        under, fold = [by_id[k] for k in below(bus) if not by_id[k].get("mix")], bus in folded
        out.append({**by_id[bus], "group": True, "depth": depth, "folded": fold, "count": len(under),
                    "solo": bool(under) and all(r.get("solo") for r in under),     # lit when every track in it is soloed
                    "blocks": [b for r in under for b in r["blocks"]] if fold else []})
        if fold:
            seen.update(below(bus))
            return
        for k in kids[bus]:
            if k in seen:
                continue
            if k in kids:
                emit(k, depth + 1)
            else:
                seen.add(k)
                out.append({**by_id[k], "depth": depth + 1, "bus": bus})      # `bus`: the group it plays into

    def top(item_id: str) -> str:
        item, hops = next(i for i in [*root.get("tracks", []), *root.get("buses", [])] if i["id"] == item_id), 0
        while item.get("output") in kids and hops < 99:
            item, hops = next(b for b in root["buses"] if b["id"] == item["output"]), hops + 1
        return item["id"]

    for r in tracks:
        if r["id"] in seen:
            continue
        group = top(r["id"])
        if group != r["id"]:
            emit(group, 0)
        else:
            seen.add(r["id"])
            out.append({**r, "depth": 0})
    for r in mix:                                       # a group holding only other groups, or nothing but them
        if r["id"] not in seen and r["id"] in kids and top(r["id"]) == r["id"]:
            emit(r["id"], 0)
    return out + [r for r in mix if r["id"] not in seen and r["id"] not in kids]
