"""What a change did, from its own edits: items added / changed / removed per type, their ids, each described by the app.

`edit_document`'s reply carries it (the sentence, and `changed["items"]`). Counted first from the edits; only the
listed ids (the first LIST of each) are looked up and described, so a whole-song move of thousands of notes stays cheap.
"""
from __future__ import annotations

from .. import edits as E

LIST = 12


def _gather(change) -> dict[str, dict]:
    """{"added": {id: type}, "changed": {id: None}, "removed": {id: type}}: an item added and removed in one change shows
    in neither; one added then edited stays added."""
    added, removed, changed = {}, {}, {}
    for e in E.flat(change.edits):
        if isinstance(e, E.Insert):
            if e.id in removed:
                removed.pop(e.id)
                changed[e.id] = None
            else:
                added[e.id] = e.item.get("type")
        elif isinstance(e, E.Remove):
            if e.id in added:
                added.pop(e.id)
            else:
                removed[e.id] = e.item.get("type")
                changed.pop(e.id, None)
        elif isinstance(e, E.Shift):
            changed.update(dict.fromkeys(e.ids))
        elif isinstance(e, (E.Set, E.Move)):
            changed[e.id] = None
    for i in added:
        changed.pop(i, None)
    return {"added": added, "changed": changed, "removed": removed}


def _types(group: dict, doc) -> dict[str, int]:
    out: dict[str, int] = {}
    for id_, t in group.items():
        if t is None:
            t = doc.item(id_).get("type") if doc.has(id_) else "item"
        out[t or "item"] = out.get(t or "item", 0) + 1
    return out


def _phrase(doc, id_: str, removed: dict | None) -> str:
    item = removed if removed is not None else (doc.item(id_) if doc.has(id_) else None)
    say = doc.kind.describe
    text = say(item, doc.data) if (say and item) else None
    return text or id_


def summarize(doc, change) -> dict:
    """{"added": {"count", "types", "items"}, …} for the three kinds; empty kinds left out. `items` are the first LIST."""
    out = {}
    removed_items = {e.id: e.item for e in E.flat(change.edits) if isinstance(e, E.Remove)}
    for name, group in _gather(change).items():
        if not group:
            continue
        ids = list(group)
        out[name] = {"count": len(ids), "types": _types(group, doc), "ids": ids[:LIST],
                     "items": [_phrase(doc, i, removed_items.get(i) if name == "removed" else None) for i in ids[:LIST]],
                     "more": max(0, len(ids) - LIST)}
    if "removed" in out:                                    # a thin / delete: how many of the targets stayed
        targets = {t for c in change.calls for t in c.get("target", []) if isinstance(t, str)}
        if targets:
            out["removed"]["kept_of_targeted"] = len(targets - set(_gather(change)["removed"]))
            out["removed"]["targeted"] = len(targets)
    return out


def sentence(summary: dict) -> str:
    """The summary in words: "Added 3 notes: a, b, c. Changed 2 notes: …"."""
    parts = []
    for name, s in summary.items():
        kinds = ", ".join(f"{n} {t}{'s' * (n != 1)}" for t, n in s["types"].items())
        tail = f" … {s['more']} more" if s["more"] else ""
        parts.append(f"{name.capitalize()} {kinds}: " + "; ".join(s["items"]) + tail + ".")
        if "targeted" in s:
            parts.append(f"Kept {s['kept_of_targeted']} of the {s['targeted']} targeted.")
    return " ".join(parts)
