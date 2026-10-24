"""One typing session on the canvas = one gesture = one undo step (a new text, or an edit of one).

A new text is not in the document until the first letter: `layer.add` + `text.set` are previewed together, then every
key previews `text.set {body}` on top, and the session's end saves ONE change ("Add text"). Editing a text previews
`text.set {body}` the same way ("Edit text"). An empty result changes nothing (cancelled). A style choice made while
typing (font, weight, size, colour) rides in the same change and is remembered as the next text's start. From the
first letter the new text is selected, so the settings panel shows its settings while typing.
"""
from __future__ import annotations

from rostrum2d import KIND
from rostrum_core import ids
from rostrum_core.tree import index
from rostrum_gui.edits import Drag


class Session:
    def __init__(self, bridge, layer: str | None, style: dict, place: dict):
        """layer: an existing text to edit, or None for a new one at `place` ({x, y, boxWidth})."""
        self.b, self.layer, self.place, self.style = bridge, layer, place, dict(style)
        self.body = bridge.doc.item(layer)["body"] if layer else ""
        self.start = self.body
        self.drag = None
        self.id = layer or ids.counted(index(bridge.doc.data, KIND.lists), "text")

    def _open(self):
        if self.drag is None:
            self.drag = Drag(self.b.doc, self.b.who, "Edit text" if self.layer else "Add text")

    def _calls(self, **args) -> list[dict]:
        op = KIND.registry.field_op("text").name
        calls = []
        if self.layer is None and not self.b.doc.has(self.id):
            calls.append({"op": "layer.add", "target": [self.b.comp_id], "args": {"type": "text", "id": self.id}})
            args = {**self.place, **self.style, **args}
        return calls + [{"op": op, "target": [self.id], "args": args}]

    def type(self, body: str):
        self.body = body
        if self.layer is None and not body and self.drag is None:
            return                                     # nothing typed yet: nothing in the document
        self._open()
        self.drag.preview(self._calls(body=body))
        if self.layer is None and self.b.selected != self.id and self.b.doc.has(self.id):
            self.b.select(self.id)                     # the first letter: the settings panel shows the new text's

    def end(self):
        """Save the session as one change; nothing typed (or an edit that left it unchanged / empty) saves nothing."""
        if self.drag is None:
            return None
        empty = not self.body.strip()
        same = self.layer is not None and self.body == self.start
        mine = self.layer is None and self.b.selected == self.id
        change = self.drag.end(cancel=empty or same)
        if mine and empty:
            self.b.select("")                          # a new text typed and emptied again: it is gone, as before it
        return None if empty or same else change
