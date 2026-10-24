"""One added effect in the settings panel (effects.py): a folded group of rows. It is also the `bridge` of its own
rows (InspectorRow calls setValue, the scrub slots and toggleMore on it), so each edit is an operation on the effect
item through the real bridge (one change, as for any item)."""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot

from . import rows
from .edits import Scrub, edit_label
from .model import RowsModel


class EffectGroup(QObject):
    changed = Signal()

    def __init__(self, part, item_id):
        super().__init__(part)
        self._part, self._id, self._more = part, item_id, False
        self._scrub = None
        self.model = RowsModel(rows.ROLES, self)
        self._static = []
        self._told = None                       # (label, open, more) as QML last heard them

    # ---- what QML reads ---------------------------------------------------------------------------------------
    @Property(str, constant=True)
    def id(self):
        return self._id

    @Property(str, notify=changed)
    def label(self):
        return self._part.label_of(self._id)

    @Property(bool, notify=changed)
    def open(self):
        return self._id in self._part.opened

    @Property(QObject, constant=True)
    def rows(self):
        return self.model

    @Property(bool, notify=changed)
    def moreOpen(self):
        return self._more

    @Property(bool, constant=True)
    def typesExpressions(self):
        return False

    # ---- what its rows and header call ------------------------------------------------------------------------
    @Slot()
    def toggle(self):
        self._part.opened ^= {self._id}
        self.changed.emit()

    @Slot()
    def toggleMore(self):
        self._more = not self._more
        self.refresh()

    @Slot()
    def remove(self):
        self._part.remove(self._id)

    @Slot(str, "QVariant", result=bool)
    def setValue(self, param, value):
        b = self._part.bridge
        return b._guard(lambda: b._apply([b.edit_call(self._id, param, value)], edit_label(b.doc, self._id, param, value)))

    @Slot(str)
    def beginScrub(self, param):
        self.endScrub()
        b = self._part.bridge
        b._guard(lambda: setattr(self, "_scrub", Scrub(b.doc, b.who, self._id, param, b.edit_call)))

    @Slot(str, "QVariant")
    def scrub(self, param, value):
        if self._scrub is None or self._scrub.name != param:
            self.beginScrub(param)
        if self._scrub is not None:
            self._part.bridge._guard(lambda: self._scrub.preview(value))

    @Slot()
    def endScrub(self):
        s, self._scrub = self._scrub, None
        if s is not None:
            b = self._part.bridge
            b._guard(lambda: b._done(s.end(False), ""))

    # ---- inside ---------------------------------------------------------------------------------------------
    def refresh(self):
        """The rows for the effect's values now: changed in place (a drag keeps its field)."""
        b = self._part.bridge
        item = b.doc.item(self._id)
        op = b.doc.kind.registry.field_op(item["type"])
        if not self._static:
            self._static = rows.layout(op, item["type"])
        self.model.update(rows.evaluate(self._static, b.shown_values(item), b.doc.kind.facts(item, b.doc), self._more))
        told = (self.label, self.open, self._more)      # the rows changed in place above; the header only on news
        if told != self._told:
            self._told = told
            self.changed.emit()
