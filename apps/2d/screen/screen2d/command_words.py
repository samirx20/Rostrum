"""Ctrl+K edits any setting by name. The kit's list leaves out fields that need a value (numbers, text, colours: the
settings panel sets those), so here each of the selected item's such fields that applies now is a command too
("Edit Opacity"): running it jumps to the field (the kit's `revealField`: its group opens, the panel scrolls to it,
the cursor goes in). Search is the kit's one `commands.search` (word starts, label first, then the command's own
words); each command carries its field's words (`field_words`: name, label, group, help) and its weight
(the rows are the kit's `commands.field_rows`).
The synonyms ("move" -> X, Y) are the fields' own `help` in rostrum2d/fields.py, not a list here. A slot mix-in
for Bridge2D.
"""
from __future__ import annotations

from PySide6.QtCore import Slot
from rostrum_gui.commands import field_rows
from rostrum_gui.parts import SlotMixin


class CommandWords(SlotMixin):
    def _commands(self):
        return super()._commands() + self._field_commands()

    def _field_commands(self) -> list[dict]:
        return field_rows(self.doc, self._sel, self.label_of) if self._sel else []     # the kit's (Sound has the same)

    @Slot(str, result=bool)
    def run(self, key):
        if key.startswith("field:"):
            return self.revealField(key.removeprefix("field:"))
        return super().run(key)
