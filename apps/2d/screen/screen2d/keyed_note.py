"""What an action keyed on its own: an action that moves or sizes layers (Align, Even gaps, Match size, Fill the frame)
changes an animated setting by keying it at the playhead (ops_align.py, as value.set does). That key changes the
motion around it, so the top bar says so: "Align centre · keyed X at 3.00 s". Actions about keys (K, eases) say
their own words and get no note."""
from __future__ import annotations

from rostrum2d import fields as F
from rostrum_core import edits as E


def _keys(doc, change) -> list[tuple[str, str]]:
    """(owner id, prop) of every key the change added or gave a new value."""
    out = []
    for e in change.edits:
        if isinstance(e, E.Insert) and e.item.get("type") == "key":
            out.append((e.parent, e.item.get("prop", "")))
        elif isinstance(e, E.Set) and doc.has(e.id) and doc.item(e.id).get("type") == "key" and e.path[:1] != ["ease"]:
            out.append((doc.parent_of(e.id)[0], doc.item(e.id).get("prop", "")))
    return out


def note(doc, since: int, calls: list[dict], t: float) -> str:
    """" · keyed X, Y at 3.00 s" for keys the changes after step `since` made without being asked; "" when none."""
    if any(c.get("op", "").startswith("key.") for c in calls):
        return ""
    words = []
    for change in reversed(doc.history.changes):            # the newest first: only this action's own changes
        if change.seq <= since:
            break
        for owner, prop in _keys(doc, change):
            p = doc.has(owner) and F.param(doc.item(owner)["type"], prop)
            label = p.label if p else prop
            if label not in words:
                words.append(label)
    return f" · keyed {', '.join(words)} at {t:.2f} s" if words else ""
