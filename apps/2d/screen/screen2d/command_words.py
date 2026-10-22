"""Ctrl+K finds operations by their words AND their fields. Every command carries `words`: the operation's label,
name and summary, and each field's name, label, group and help (a colour field also says "color" and "colour").
The kit's list leaves out fields that need a value (numbers, text, colours: the inspector sets those), so here each
of the selected item's such fields is a command too ("Edit X"): running it points to its place in the inspector.
The synonyms ("move" -> X, Y) are the fields' own `help` in rostrum2d/fields.py, not a list here. A slot mix-in
for Bridge2D. Matching is at word starts ("move" is not in "remove") and ranked: label, then the command's own field,
then its operation; within one, the fields' own importance. When the kit's `commands.search` does the same, `commands()` below goes (kit request, H27 C2).
"""
from __future__ import annotations

import re

from PySide6.QtCore import Slot
from rostrum_core.params import IMPORTANCE
from rostrum_gui.parts import SlotMixin

NEEDS_VALUE = ("number", "color", "text")


def _field_words(p) -> str:
    kind = "color colour" if p.type == "color" else ""
    return f"{p.name} {p.label} {p.group} {p.help} {kind}"


class CommandWords(SlotMixin):
    def _commands(self):
        out = super()._commands()
        reg = self.doc.kind.registry
        ops = {op.name: op for op in reg.available(self.doc, [self._sel] if self._sel else [])}
        for c in out:
            call = (c.get("calls") or [{}])[0]
            op = ops.get(call.get("op", ""))
            if op and op.fields:        # a field command (a toggle, a choice): its own field's words rank above the op's
                named = [p for p in (op.param(a) for a in call.get("args", {})) if p]
                c["own"] = " ".join(_field_words(p) for p in named)
                c["weight"] = min((IMPORTANCE.index(p.importance) for p in named), default=0)
                c["words"] = f"{op.label} {op.name} {op.summary}"
            elif op:                    # any other operation: its fields are only its operation's words
                c["words"] = f"{op.label} {op.name} {op.summary} " + " ".join(_field_words(p) for p in op.params)
                c["weight"] = IMPORTANCE.index(op.importance)
        return out + self._field_commands(ops)

    def _field_commands(self, ops) -> list[dict]:
        if not self._sel:
            return []
        from rostrum_core.conditions import holds
        item = self.doc.item(self._sel)
        facts = self.doc.kind.facts(item, self.doc)
        out = []
        for op in ops.values():
            if op.fields and item["type"] in (op.targets or ()):
                out += [{"key": f"field:{p.name}", "label": f"Edit {p.label}", "hint": f"{self.label_of(item)} · {p.group}",
                         "own": _field_words(p), "weight": IMPORTANCE.index(p.importance), "words": f"{op.label} {op.name} {op.summary}", "field": p}
                        for p in op.params if p.type in NEEDS_VALUE and holds(p.valid_when, item, facts)]
        return out

    @Slot(str, result="QVariantList")
    def commands(self, query):
        every = self._commands()
        ranked = sorted((r, c.get("weight", 0), i) for i, c in enumerate(every) if (r := rank(c, query)) is not None)
        return [{k: every[i][k] for k in ("key", "label", "hint")} for _, _, i in ranked]

    @Slot(str, result=bool)
    def run(self, key):
        if key.startswith("field:"):
            c = next((c for c in self._commands() if c["key"] == key), None)
            if c is not None:
                self._set_status(f"{c['field'].label} is in the Inspector, under {c['field'].group}")
                return True
        return super().run(key)


def _starts(words: list[str], text: str) -> bool:
    """Every query word starts a word of the text ("move" finds "move it", not "layer.remove")."""
    return all(re.search(r"(?<![a-z0-9])" + re.escape(w), text) for w in words)


def rank(c: dict, query: str):
    """0: the label says it; 1: the command's own field says it; 2: its operation says it; None: no match."""
    words = query.lower().split()
    label, own = c["label"].lower(), f"{c['label']} {c.get('own', '')}".lower()
    rest = f"{own} {c['hint']} {c.get('words', '')} {' '.join(k['op'] for k in c.get('calls', []))}".lower()
    return next((r for r, text in enumerate((label, own, rest)) if _starts(words, text)), None)
