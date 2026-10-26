"""Stepping through candidates for a placed sound (DESIGN.md §3.13 step 6): ↑ / ↓ put the next Library result in the
selected clip's place and loop the second round the spot; Enter keeps the one you are on (ONE history entry), Esc puts
the original back (nothing recorded). The document is changed only through `clip.swap`, in one drag (the kit's `Drag`:
live changes, one step when kept, none when cancelled). Every step swaps from the ORIGINAL clip (`original_args`), so a
shorter file never shortens the spot for good, and the level never drifts. An agent does the same with one `clip.swap`.
"""
from __future__ import annotations

import copy

from rostrum_gui.edits import Drag
from rostrum_sound.doc import ops_swap
from rostrum_sound.doc.select_time import clip_length, start_of

AROUND = 1.0                       # seconds looped before and after the spot
LABEL = "Swap sound"


class SwapTrial:
    def __init__(self, bridge):
        self.bridge, self.clip, self.row, self._drag, self._was_loop = bridge, "", -1, None, None
        self._original: dict = {}

    @property
    def active(self) -> bool:
        return self._drag is not None

    def step(self, clip_id: str, result: dict, row: int):
        """Put `result` (a Library row) in the place of `clip_id`, from the original, and loop round the spot."""
        b = self.bridge
        if not self.active:
            self.clip, self._original = clip_id, copy.deepcopy(b.doc.item(clip_id))
            self._drag = Drag(b.doc, b.who, LABEL, interrupt=self.keep)    # another edit keeps the one on show first
            self._was_loop = b.transport.loop
        args = {"media": result["path"], **({"in": result["start"]} if result["start"] > 0.05 else {}),
                **ops_swap.original_args(self._original, b.doc.data)}
        self._drag.preview([{"op": "clip.swap", "target": [self.clip], "args": args}])
        self.row = row
        self._hear()

    def keep(self) -> bool:
        """Enter: the result on show stays, as one change."""
        return self._end(False)

    def back(self) -> bool:
        """Esc: the original is put back; nothing is recorded."""
        return self._end(True)

    def _end(self, cancel: bool) -> bool:
        if not self.active:
            return False
        drag, self._drag, b = self._drag, None, self.bridge
        b.transport.loop, self.row = self._was_loop, -1
        b._guard(lambda: b._done(drag.end(cancel), "The original is back" if cancel else ""))
        b.transport.changed()               # a drag's changes are not rendered; this lands the final state
        return True

    def _hear(self):
        """Play (or keep playing) a loop from a second before the spot to a second after it."""
        b, root = self.bridge, self.bridge.doc.data
        at, length = start_of(root, self._original), clip_length(self._original, root)
        b.transport.loop = (max(0.0, at - AROUND), at + length + AROUND)
        b.transport.changed()
        if not b.transport.playing:
            b.transport.toggle(b.transport.loop[0])
