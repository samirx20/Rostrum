"""A layer a press made, picked the frame after (after_frame.py): the press's own frame holds only what it made (a
shape, the first stroke's ink), and the pick (its outline, the panels, the rows) follows one screen refresh later.
Picked at once in the press, the new layer's panels and lists doubled the press's frame (~30 ms a first stroke).

    self._soon = SelectSoon(bridge, self)
    self._soon.ask(new_id)          # in the press, after the change
A reader that needs the pick now (a release before the frame came, a script) calls `flush()`; an item gone by then
(the press undone) is not picked.
"""
from __future__ import annotations

from .after_frame import AfterFrame


class SelectSoon:
    def __init__(self, bridge, parent):
        self._b, self._id = bridge, None
        self._job = AfterFrame(self._pick, parent)

    def ask(self, item_id: str):
        self._id = item_id
        self._job.ask()

    def flush(self):
        self._job.flush()

    def _pick(self):
        item_id, self._id = self._id, None
        if item_id and self._b.doc.has(item_id):
            self._b.select(item_id)
