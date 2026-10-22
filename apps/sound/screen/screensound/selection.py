"""What is selected, as a list (no Qt): the ids in the order they were picked, the anchor a Shift-click ranges from,
the time range (separate from the items), and the lookups that turn a click or a box into ids (the run between two
items on a track, the items a box touches). The bridge (select_slots.py) holds one; `ids[0]` is the one the
inspector shows. Selecting is screen state: never an undo step, never saved. `describe` is what an agent reads
(`inspect_selection`): one line per selected id, plus the range.
"""
from __future__ import annotations

PICKABLE = ("note", "hit", "clip", "line")          # what a box, Ctrl+A and a drag of many take along


class Selection:
    def __init__(self):
        self.ids: list[str] = []
        self.anchor = ""
        self.range: tuple[float, float] | None = None    # a time range on the ruler (seconds), or none

    def set(self, ids, anchor: str | None = None) -> list[str]:
        self.ids = list(dict.fromkeys(i for i in ids if i))
        self.anchor = anchor if anchor is not None else (self.ids[-1] if self.ids else "")
        return self.ids

    def toggle(self, item_id: str) -> list[str]:
        """Ctrl-click: in when out, out when in. The anchor moves to the clicked one."""
        ids = [i for i in self.ids if i != item_id] if item_id in self.ids else [*self.ids, item_id]
        return self.set(ids, item_id)

    def keep(self, alive) -> bool:
        """Drop ids that are gone; True when anything was dropped."""
        kept = [i for i in self.ids if alive(i)]
        changed = kept != self.ids
        if changed:
            self.ids = kept
            self.anchor = self.anchor if self.anchor in kept else (kept[-1] if kept else "")
        return changed


def run_between(order: list[str], a: str, b: str) -> list[str]:
    """The ids from `a` to `b` in `order` (both ends in), [] when either is not in it."""
    if a not in order or b not in order:
        return []
    i, j = sorted((order.index(a), order.index(b)))
    return order[i:j + 1]


def time_order(blocks: list[dict]) -> list[str]:
    """A track's blocks' ids in time order (Shift-click's run is "the notes between, in time")."""
    return [x["id"] for x in sorted(blocks, key=lambda x: (x["t"], x["id"]))]


def in_box(blocks: list[dict], t0: float, t1: float, r0: float = float("-inf"), r1: float = float("inf"),
           drums: list[str] | None = None) -> list[str]:
    """Blocks whose time span touches [t0, t1] (either order) and, in the piano roll, whose key (notes) or drum row
    (hits) lies between rows r0 and r1; clips and lines count on any row."""
    t0, t1 = sorted((t0, t1))
    r0, r1 = sorted((r0, r1))
    out = []
    for b in blocks:
        if b["type"] not in PICKABLE or b["t"] + max(b["dur"], 0.0) < t0 or b["t"] > t1:
            continue
        if b["type"] == "note" and not any(r0 - 0.5 <= k <= r1 + 0.5 for k in b["keys"]):
            continue
        if b["type"] == "hit" and drums and b["drum"] in drums and not (r0 - 0.5 <= drums.index(b["drum"]) <= r1 + 0.5):
            continue
        out.append(b["id"])
    return out


def blocks_by_id(rows: list[dict]) -> dict[str, dict]:
    """Every drawn block of the arrangement, by id, with its track id (`track`)."""
    return {b["id"]: {**b, "track": r["id"]} for r in rows for b in r.get("blocks", [])}


def count_words(kinds: list[str]) -> str:
    """The count chip: "5 notes", "1 clip", "3 items" (mixed kinds)."""
    names = {"note": "note", "hit": "drum hit", "clip": "clip", "line": "line", "track": "track", "marker": "marker",
             "section": "section", "bus": "group", "master": "master"}
    n = len(kinds)
    if not n:
        return ""
    one = names.get(kinds[0], "item") if len(set(kinds)) == 1 else "item"
    return f"{n} {one}" + ("" if n == 1 else "s")


def describe(doc, ids: list[str], rows: list[dict], rng, label_of) -> dict:
    """`inspect_selection`: the selected ids with kind, track, start, end and a one-line description, plus the
    time range (seconds) when one is set."""
    drawn = blocks_by_id(rows)
    out = []
    for i in ids:
        it = doc.item(i)
        b = drawn.get(i)
        one = {"id": i, "kind": it["type"], "label": label_of(it)}
        if b is not None:
            one.update(track=b["track"], start=round(b["t"], 3), end=round(b["t"] + b["dur"], 3))
        out.append(one)
    lines = [f'{o["id"]}: {o["kind"]} "{o["label"]}"' + (f' on {o["track"]}, {o["start"]}–{o["end"]} s' if "track" in o else "")
             for o in out]
    if rng:
        lines.append(f"time range {rng[0]:.3f}–{rng[1]:.3f} s")
    return {"items": out, "range": list(rng) if rng else None, "lines": lines or ["nothing selected"]}
