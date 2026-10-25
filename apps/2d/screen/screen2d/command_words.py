"""Ctrl+K edits any setting by name. The kit's list leaves out fields that need a value (numbers, text, colours: the
settings panel sets those), so here each of the selected item's such fields that applies now is a command too
("Edit Opacity"): running it jumps to the field (the kit's `revealField`: its group opens, the panel scrolls to it,
the cursor goes in); only a setting whose row the panel shows now is offered (a colour drawn in a Fill row of its
own, a setting that needs another on, is not). A number that switches its group on (motion blur's Amount: `sections.switch_of`) is named as the
panel names it: "Add Motion blur" while off (running it turns it on, then jumps to the amount), "Edit Motion blur
amount" once on. Search is the kit's one `commands.search` (word starts, label first, then the command's own
words); the rows are the kit's `commands.field_rows` (Sound has the same), each with its field's words and weight.
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
        if not self._sel:
            return []
        self._panel_now()                   # a setting is offered only when the panel can show its row (revealField's own test)
        rows = {r["id"]: r for r in self.model.rows if r["row"] == "param"}
        return field_rows(self.doc, self._sel, self.label_of, shows=lambda name: bool(rows.get(name, {}).get("holds")))

    @Slot(str, result=bool)
    def run(self, key):
        if key.startswith("field:"):
            return self.revealField(key.removeprefix("field:"))
        return super().run(key)

