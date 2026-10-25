"""A part's reads worked out once per state: what a panel shows is read twice per change or drag step (news.relay
reads every property to tell whether anything differs, then QML reads the ones it binds), and each read worked it all
out again from the document (a key's ease curve: 61 evaluations per read, every pointer move of a key drag).

    self._kept = PerState()
    def _state(self): return self.b.doc.data, tuple(self.b._keys.ids)    # the document first (compared by identity)
    @Property(...) def curve(self): return self._kept.read(self._state(), "curve", self._curve)

The document's data is never changed in place (every change and drag step makes a new tree: document.py), so the same
object is the same state; the rest of the state (screen state: picks, the selection) is compared by value.
"""
from __future__ import annotations


class PerState:
    def __init__(self):
        self._at, self._got = None, {}

    def read(self, state: tuple, name: str, fn):
        """`fn()` once per `state` (its first element compared by identity, the rest by value) and `name`."""
        at = self._at
        if at is None or at[0] is not state[0] or at[1:] != state[1:]:
            self._at, self._got = state, {}
        if name not in self._got:
            self._got[name] = fn()
        return self._got[name]

    def forget(self):
        """Screen state the `state` tuple does not hold changed: the next reads work it out again."""
        self._at, self._got = None, {}
