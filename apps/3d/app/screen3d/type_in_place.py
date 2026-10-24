"""Typing a 3D text in place (SPEC §4.4): right after Type & logo › 3D text is placed, a text cursor shows in the
viewport where it landed (TypeInPlace.qml) and typing changes the words live. The whole typing session is ONE change
(one undo step): each key previews `mesh.set text` inside one document gesture (rostrum_gui.edits.Drag, as a drag on a
number does); Enter or Esc ends it. The new text starts as the field's placeholder word ("Text"); the first key
replaces it, and an empty line shows the placeholder again, so the mesh is never blank (a blank text fails loudly).
Ending with nothing typed keeps the placeholder (the session leaves no change). No maths here, no engine.
"""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot
from rostrum_gui.edits import Drag


class Typer(QObject):
    changed = Signal()

    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        self.b = bridge
        self._item, self._text, self._at, self._drag, self._placeholder = "", "", [0.0, 0.0], None, ""

    @Property(str, notify=changed)
    def item(self):
        """The text item being typed, "" when no typing is going on."""
        return self._item

    @Property(str, notify=changed)
    def text(self):
        return self._text

    @Property("QVariantList", notify=changed)
    def at(self):
        """Where the cursor shows: the click that placed the text, in viewport device pixels [x, y]."""
        return list(self._at)

    def start(self, item_id: str, at=None):
        self.end()
        self._item, self._text, self._at = item_id, "", list(at or [0.0, 0.0])
        self._placeholder = self.b.doc.item(item_id).get("text", "Text")
        self._drag = Drag(self.b.doc, self.b.who, f"Type {self.b.label_of(self.b.doc.item(item_id))}")
        self.changed.emit()

    @Slot(str)
    def setText(self, text):
        if self._drag is None:
            return self.b.fail_line("Error: type: no text is waiting for typing; place a 3D text first.")
        self._text = text
        words = text if text.strip() else self._placeholder
        self.b._guard(lambda: self._drag.preview([self.b.edit_call(self._item, "text", words)]))
        self.changed.emit()

    @Slot()
    def end(self):
        """Enter or Esc: the typing is one change (none when nothing was typed)."""
        d, self._drag = self._drag, None
        if d is None:
            return
        typed = self._text.strip() != ""
        self.b._guard(lambda: self.b._done(d.end(cancel=not typed), ""))
        self._item, self._text = "", ""
        self.changed.emit()
