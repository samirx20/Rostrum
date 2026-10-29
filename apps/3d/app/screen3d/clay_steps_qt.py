"""The Clay panel's Steps list and Puff row (CL3 CONTRACT § 5; SPEC § 3.1), for QML as `viewport.clay.stepsObj`.

- `items`: the selected clay's steps, newest at the bottom, each its name or what it is ("Drawn shape", "Lump",
  "Stroke · Add"), its eye (`hidden`) and whether it is the chosen one. A clay may hold thousands: the model changes
  rows in place (RowsModel.update) and QML draws only the visible ones (ListView).
- `rows`: the chosen step's own fields (the kit's InspectorRow, the way it draws any item's), `claystep.set` on
  that step; `puff`: the Puff row of the clay's last step while it is a drawn shape, so it stays at the panel's top
  until the next stroke. Both are InspectorRow bridges (StepRows), one undo step per change or scrub.
- `toggleHidden`, `rename`: `claystep.set hidden / name`, one undo step each, the calls agents make.
"""
from __future__ import annotations

from types import SimpleNamespace

from PySide6.QtCore import Property, QObject, Signal, Slot
from rostrum3d import fields as F
from rostrum_gui import rows
from rostrum_gui.edits import Scrub
from rostrum_gui.model import RowsModel

from . import outline

ROLES = ("id", "label", "hidden", "chosen")
OFF_ROWS = {"step", "name", "hidden", "shape", "source"}          # shown by the list itself, or what made the step
WORDS = {"outline": "Drawn shape", "spin": "Spun shape", "sphere": "Lump", "capsule": "Lump"}


def step_label(doc, step: dict) -> str:
    """A step's name, else what it is: "Drawn shape", "Spun shape", "From Box", "Lump", "Stroke · Add"."""
    if step.get("name"):
        return step["name"]
    if step.get("step") == "stroke":
        return f"Stroke · {F.param('claystep', 'brush').option_label(step.get('brush', 'add'))}"
    if step.get("shape") == "item":
        src = step.get("source", "")
        return f"From {outline.label_of(doc.item(src)) if doc.has(src) else src}"
    word = WORDS.get(step.get("shape"), "Piece")
    return f"{word} · Carve" if step.get("mode") == "carve" else word


class StepRows(QObject):
    """One step's rows for InspectorRow: `pick(step)` says which step and refreshes them. `kind`: whose fields (a
    sculpt layer's too, clay_layers_qt.py)."""

    def __init__(self, b, names=None, parent=None, kind="claystep"):
        super().__init__(parent)
        self.b, self.step, self._scrub = b, "", None
        params = [p for p in F.FIELDS[kind]
                  if (p.name in names if names else p.name not in OFF_ROWS and p.group != "Step data")]
        self._static = rows.layout(SimpleNamespace(params=params), "Step")
        self.model = RowsModel(rows.ROLES, self)

    def pick(self, step: dict | None):
        new = (step or {}).get("id", "") != self.step
        self.step = (step or {}).get("id", "")
        out = rows.evaluate(self._static, step, self.b.facts_of(step), False) if step is not None else []
        self.model.reset(out) if new else self.model.update(out)

    rows = Property(QObject, lambda s: s.model, constant=True)

    @Slot(str, "QVariant", result=bool)
    def setValue(self, name, value):
        return bool(self.step) and self.b._guard(lambda: self.b._apply([self.b.edit_call(self.step, name, value)],
                                                                         f"Step: {name}"))

    @Slot(str)
    def beginScrub(self, name):
        self.endScrub()
        if self.step:
            self.b._guard(lambda: setattr(self, "_scrub", Scrub(self.b.doc, self.b.who, [self.step], name,
                                                                  self.b.edit_call)))

    @Slot(str, "QVariant")
    def scrub(self, name, value):
        if self._scrub is None or self._scrub.name != name:
            self.beginScrub(name)
        if self._scrub is not None:
            self.b._guard(lambda: self._scrub.preview(value))

    @Slot()
    def endScrub(self):
        s, self._scrub = self._scrub, None
        if s is not None:
            self.b._guard(lambda: self.b._done(s.end(), ""))

    @Slot()
    def cancelScrub(self):
        s, self._scrub = self._scrub, None
        if s is not None:
            self.b._guard(lambda: self.b._done(s.end(True), ""))

    @Slot(str)
    def toggleGroup(self, group):
        pass

    @Slot(str)
    def toggleAnimate(self, name):
        pass                                    # steps are never keyed


class ClaySteps(QObject):
    changed = Signal()

    def __init__(self, tool):
        super().__init__(tool)
        self.t, self.b, self._chosen = tool, tool.b, ""
        self.model = RowsModel(ROLES, self)
        self.chosenRows, self.puffRows = StepRows(self.b, parent=self), StepRows(self.b, ["puff"], self)
        self.b.docChanged.connect(self.refresh)
        self.b.selectionChanged.connect(self.refresh)
        self.refresh()

    def _steps(self) -> list[dict]:
        it = self.t._item()
        return it.get("steps", []) if it is not None else []

    def refresh(self, *_):
        steps = self._steps()
        if self._chosen not in {s["id"] for s in steps}:
            self._chosen = ""
        self.model.update([{"id": s["id"], "label": step_label(self.b.doc, s), "hidden": bool(s.get("hidden")),
                            "chosen": s["id"] == self._chosen} for s in steps])
        self.chosenRows.pick(next((s for s in steps if s["id"] == self._chosen), None))
        last = steps[-1] if steps else None
        # not while that step is chosen in the list: its own rows show Puff there (one control, one place)
        self.puffRows.pick(last if last is not None and last.get("shape") == "outline"
                           and last.get("step") == "piece" and last["id"] != self._chosen else None)
        self.changed.emit()

    items = Property(QObject, lambda s: s.model, constant=True)
    rows = Property(QObject, lambda s: s.chosenRows, constant=True)
    puff = Property(QObject, lambda s: s.puffRows, constant=True)
    count = Property(int, lambda s: len(s._steps()), notify=changed)
    chosen = Property(str, lambda s: s._chosen, notify=changed)
    hasPuff = Property(bool, lambda s: bool(s.puffRows.step), notify=changed)

    @Slot(str)
    def choose(self, step_id):
        """A click: that step's rows show under the list (a click on the chosen one closes them)."""
        self._chosen = "" if step_id == self._chosen else step_id
        self.refresh()

    def _set(self, step_id, values: dict, label: str):
        self.b._guard(lambda: self.b._apply([{"op": "claystep.set", "target": [step_id], "args": values}], label))

    @Slot(str)
    def toggleHidden(self, step_id):
        hidden = bool(self.b.doc.item(step_id).get("hidden"))
        self._set(step_id, {"hidden": not hidden}, "Show step" if hidden else "Hide step")

    @Slot(str, str)
    def rename(self, step_id, name):
        step = self.b.doc.item(step_id)
        if name.strip() not in (step.get("name", ""), step_label(self.b.doc, step)):     # Enter on the words: no change
            self._set(step_id, {"name": name.strip()}, "Rename step")
