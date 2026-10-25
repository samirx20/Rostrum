"""Ctrl+K edits any setting by name. The kit's list leaves out fields that need a value (numbers, text, colours: the
settings panel sets those), so here each of the selected item's such fields that applies now is a command too
("Edit Opacity"): running it jumps to the field (the kit's `revealField`: its group opens, the panel scrolls to it,
the cursor goes in). A number that switches its group on (motion blur's Amount: `sections.switch_of`) is named as the
panel names it: "Add Motion blur" while off (running it turns it on, then jumps to the amount), "Edit Motion blur
amount" once on. Search is the kit's one `commands.search` (word starts, label first, then the command's own
words); each command here carries its field's words (`field_words`: name, label, group, help) and its weight.
The synonyms ("move" -> X, Y) are the fields' own `help` in rostrum2d/fields.py, not a list here. A slot mix-in
for Bridge2D.
"""
from __future__ import annotations

from PySide6.QtCore import Slot
from rostrum_core.conditions import holds
from rostrum_core.params import IMPORTANCE
from rostrum_gui.commands import field_words, op_words
from rostrum_gui.parts import SlotMixin
from rostrum_gui.sections import switch_of

NEEDS_VALUE = ("number", "color", "text")


class CommandWords(SlotMixin):
    def _commands(self):
        return super()._commands() + self._field_commands()

    def _field_commands(self) -> list[dict]:
        if not self._sel:
            return []
        item = self.doc.item(self._sel)
        facts = self.doc.kind.facts(item, self.doc)
        out = []
        for op in self.doc.kind.registry.available(self.doc, [self._sel]):
            if op.fields and item["type"] in (op.targets or ()):
                out += [{"key": f"field:{p.name}", "label": (label := _label(p, op, item)),
                         "hint": self.label_of(item) + ("" if p.group in label else f" · {p.group}"),
                         "words": field_words(p), "context": op_words(op), "weight": IMPORTANCE.index(p.importance)}
                        for p in op.params if p.type in NEEDS_VALUE and holds(p.valid_when, item, facts)]
        return out

    @Slot(str, result=bool)
    def run(self, key):
        if key.startswith("field:"):
            return self.revealField(key.removeprefix("field:"))
        return super().run(key)


def _label(p, op, item) -> str:
    """ "Edit Opacity"; a group's switch says the group: "Add Motion blur" while it is off, "Edit Motion blur amount"."""
    if switch_of([q for q in op.params if q.group == p.group]) != p.name:
        return f"Edit {p.label}"
    return f"Edit {p.group} {p.label.lower()}" if item.get(p.name, p.default) != p.default else f"Add {p.group}"
