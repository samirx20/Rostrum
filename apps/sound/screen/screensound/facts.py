"""What the selection is, for the action list (action_calls.py, actions.py): `Facts`. The facts that follow from the
song and the selection alone are worked out once per song data and selection and shared (`once`): a refresh of the
action list makes several Facts and runs ~90 actions' rules on them, which read the same few facts again and again.
No Qt.
"""
from __future__ import annotations

TIMED = ("note", "hit", "clip")                       # what has `<kind>.duplicate` / `.move`
_NAMES = {"note": "note", "hit": "drum hit", "clip": "clip"}


_SHARED: list = [None, None, None]                  # [song, ids, memo]: the facts of the last selection asked


def _memo(doc, ids: tuple) -> dict:
    """The facts that follow from the song and the selection alone (items, kinds, by kind, has a chord …), worked out
    once and shared by every Facts of the same song data and ids: a refresh makes several Facts and ~90 action rules
    read them. Keyed on the data's identity: every change makes a new tree, never written in place (document.py)."""
    if _SHARED[0] is not doc.data or _SHARED[1] != ids:
        _SHARED[:] = doc.data, ids, {}
    return _SHARED[2]


class Facts:
    """What the selection is: ids in pick order, their items and kinds, their tracks, the playhead, the range."""

    def __init__(self, doc, ids, playhead=0.0, rng=None, clipboard=False, track="", range_newer=False, fill=None):
        self.doc, self.ids, self.count = doc, list(ids), len(ids)
        self._memo = _memo(doc, tuple(self.ids))
        self.items, self.kinds, self.one, self.parents = self.once("items", _items)
        self.playhead, self.range, self.clipboard, self.track = playhead, rng, clipboard, track
        self.fill = fill                  # a drum row's Fill row… being asked: {track, drum, from, to} (drum_step_slots.py)
        # what Ctrl+D and "Select what's inside" act on when both a time range and items are selected: the one made
        # last (a range drawn after picking items is the newer intent; picking items after a range means them)
        self.on_range = bool(rng) and (not self.count or range_newer)

    def once(self, name, fn):
        """`fn(self)` worked out once for this song data and selection (`_memo`); only for what depends on those
        alone (never the playhead, the range or the clipboard). What it gives is shared: read it, never change it."""
        m = self._memo
        if name not in m:
            m[name] = fn(self)
        return m[name]

    def by_kind(self, kinds=TIMED):
        """{kind: ids} of the selected items of `kinds`, in pick order (shared: read only)."""
        return self.once(("by_kind", kinds), lambda f: _by_kind(f.items, kinds))

    def words(self, kinds=TIMED) -> str:
        """The part of the selection an action on `kinds` takes, in words: "178 notes and 202 drum hits". The one
        rule for a mixed selection (Select all): an action acts on the items it can take and names them."""
        parts = [f"{len(ids)} {_NAMES.get(k, k)}{'' if len(ids) == 1 else 's'}" for k, ids in self.by_kind(kinds).items()]
        return " and ".join([", ".join(parts[:-1]), parts[-1]] if len(parts) > 1 else parts)


def _items(f):
    items = [f.doc.item(i) for i in f.ids]
    kinds = {it["type"] for it in items}
    one = next(iter(kinds)) if len(kinds) == 1 else ""
    return items, kinds, one, {f.doc.parent_of(i)[0] for i in f.ids if one != "track"}


def _by_kind(items, kinds) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for it in items:
        if it["type"] in kinds:
            out.setdefault(it["type"], []).append(it["id"])
    return out
