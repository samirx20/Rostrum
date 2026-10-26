"""What an action keyed on its own: an action that moves or sizes layers (Align, Even gaps, Match size, Fill the frame)
changes an animated setting by keying it at the playhead (ops_align.py, as value.set does). That key changes the
motion around it, so the top bar says so: "Align centre · keyed X at 3.00 s". Actions about keys (K, eases) say
their own words and get no note."""
from __future__ import annotations

from rostrum2d import fields as F
from rostrum_core import edits as E


VALUES = (["v"], ["c"], ["d"])         # a key's value fields (rostrum_core.keys.KEY_FIELDS)


def _made(changes) -> set:
    """Every item (and what is inside it) these changes put in that isn't a key: a layer the action made (Ctrl+D's
    copy) brings its keys along; it keys nothing ("Duplicate · keyed Scale at 2.00 s" was untrue)."""
    return {i for c in changes for e in E.flat(c.edits) if isinstance(e, E.Insert) and e.item.get("type") != "key"
            for i in _ids(e.item)}


def _keys(doc, change, made: set) -> list[tuple[str, str]]:
    """(owner id, prop) of every key the change added, or gave a different value, on an item that was there before."""
    edits = E.flat(change.edits)
    out = []
    for e in edits:
        if isinstance(e, E.Insert) and e.item.get("type") == "key":
            out.append((e.parent, e.item.get("prop", "")))
        elif (isinstance(e, E.Set) and e.path[:1] in VALUES and e.value != e.before and doc.has(e.id)
              and doc.item(e.id).get("type") == "key"):        # a key's value really changed (not its time, ease or id)
            out.append((doc.parent_of(e.id)[0], doc.item(e.id).get("prop", "")))
    return [(owner, prop) for owner, prop in out if owner not in made]


def _ids(item: dict):
    """The item's id and those of everything inside it (a group's layers, a layer's effects and masks)."""
    yield item.get("id")
    for v in item.values():
        if isinstance(v, list):
            for x in v:
                if isinstance(x, dict) and "id" in x:
                    yield from _ids(x)


def note(doc, change, calls: list[dict], t: float) -> str:
    """" · keyed X, Y at 3.00 s" for keys the action's own `change` made without being asked; "" when none. Only that
    change: a preview box kept first (Stagger open, then Ctrl+D: Document.make_way) is its own change and its own
    words ("Duplicate · keyed Scale at 2.00 s" came from the stagger's keys)."""
    if any(c.get("op", "").startswith("key.") for c in calls):
        return ""
    words = []
    for owner, prop in _keys(doc, change, _made([change])):
        p = doc.has(owner) and F.param(doc.item(owner)["type"], prop)
        label = p.label if p else prop
        if label not in words:
            words.append(label)
    return f" · keyed {', '.join(words)} at {t:.2f} s" if words else ""
