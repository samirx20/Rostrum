"""The settings panel's "Effects (n) +" row (no per-app panel): a layer's effects are child items with their own
settings, shown under the layer's own rows as folded groups, each with its settings and a × to remove it. The app
gives data and two operation names (`EffectsSpec`); the kit only ever calls those operations, one change each (undo,
history and "who changed what" work as for any edit):

    effects.attach(bridge, EffectsSpec(types=[EffectType("blur", "Blur"), EffectType("glow", "Glow", valid_when=…)]))

QML gets it with `bridge.invoke("effects", [])` (EffectsRow.qml, which `Inspector { effects: true }` shows under the rows). One item selected only;
several selected: the row is absent (their effects differ). A type that doesn't apply now is left out of the + list
(never greyed); nothing to add and nothing added: no row. Opening and closing a group is screen state.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from PySide6.QtCore import Property, QObject, Signal, Slot
from rostrum_core.conditions import holds

from .effects_group import EffectGroup


@dataclass(frozen=True)
class EffectType:
    type: str                                    # what the add operation takes ("blur")
    label: str                                   # in words ("Blur")
    valid_when: dict | None = None               # a registry condition on the layer (values and facts)
    valid: Callable | None = None                # or the app's own valid(layer item) -> bool


@dataclass(frozen=True)
class EffectsSpec:
    types: list                                  # [EffectType]: what may be added
    key: str = "effects"                         # the layer's list of effect items
    add_op: str = "effect.add"                   # {"op", "target": [layer], "args": {"type": …}}
    remove_op: str = "effect.remove"             # {"op", "target": [effect]}
    kinds: tuple | None = None                   # layer types that take effects (None: every one)
    label: Callable | None = None                # label(effect item) -> its name in the panel (default: name or type)


class EffectsPart(QObject):
    """`bridge.effects`: the row's count, what + may add now, and the effects' groups."""
    changed = Signal()                           # shown / count / the + list
    groupsChanged = Signal()                     # an effect came or went (not for value changes)

    def __init__(self, bridge, spec: EffectsSpec):
        super().__init__(bridge)
        self.bridge, self.spec = bridge, spec
        self.opened: set = set()
        self._groups: list = []
        self._opening = False
        bridge.docChanged.connect(self._sync)
        bridge.selectionChanged.connect(self._sync)
        self._sync()

    # ---- what QML reads ---------------------------------------------------------------------------------------
    @Property(bool, notify=changed)
    def shown(self):
        return self._layer() is not None and bool(self._groups or self.addable())

    @Property(int, notify=changed)
    def count(self):
        return len(self._groups)

    @Property("QVariantList", notify=groupsChanged)
    def groups(self):
        return list(self._groups)

    @Slot(result="QVariantList")
    def addable(self):
        """[{value, label}]: the types that apply to the layer now (a menu's entries)."""
        item = self._layer()
        if item is None:
            return []
        facts = self.bridge.doc.kind.facts(item, self.bridge.doc)
        return [{"value": t.type, "label": t.label} for t in self.spec.types
                if (t.valid is None or t.valid(item)) and holds(t.valid_when, item, facts)]

    # ---- the operations ---------------------------------------------------------------------------------------
    @Slot(str, result=bool)
    def add(self, type_):
        item, b = self._layer(), self.bridge
        label = next((t.label for t in self.spec.types if t.type == type_), type_)
        if item is None or type_ not in [a["value"] for a in self.addable()]:
            b._fail(f'Error: effects: "{label}" can\'t be added to this item.')
            return False
        self._opening = True                     # the effect just added is open, so its settings are in reach
        ok = b._guard(lambda: b._apply([{"op": self.spec.add_op, "target": [item["id"]], "args": {"type": type_}}],
                                       f"Add {label}"))
        self._opening = False
        return ok

    @Slot(str, result=bool)
    def remove(self, effect_id):
        b = self.bridge
        label = self.label_of(effect_id)
        return b._guard(lambda: b._apply([{"op": self.spec.remove_op, "target": [effect_id]}], f"Remove {label}"))

    def label_of(self, effect_id) -> str:
        item = self.bridge.doc.item(effect_id)
        return self.spec.label(item) if self.spec.label else str(item.get("name") or item["type"]).capitalize()

    # ---- inside ---------------------------------------------------------------------------------------------
    def _layer(self):
        """The one selected item when its kind takes effects, else None."""
        sel = self.bridge._kit.selection
        if len(sel) != 1:
            return None
        item = self.bridge.doc.item(sel[0])
        return item if self.spec.kinds is None or item["type"] in self.spec.kinds else None

    def _sync(self):
        item = self._layer()
        ids = [e["id"] for e in item.get(self.spec.key, [])] if item else []
        old = {g.id: g for g in self._groups}
        if self._opening:
            self.opened |= set(ids) - set(old)
        groups = [old.get(i) or EffectGroup(self, i) for i in ids]
        gone = [g for i, g in old.items() if i not in ids]
        self.opened &= set(ids)
        if [g.id for g in groups] != [g.id for g in self._groups]:
            self._groups = groups
            self.groupsChanged.emit()
        for g in groups:
            g.refresh()
        for g in gone:
            g.deleteLater()
        self.changed.emit()


def attach(bridge, spec: EffectsSpec) -> EffectsPart:
    """Offer the Effects row to the Inspector (`Inspector { effects: true }` asks for it by the handler "effects":
    a dynamic property from `bridge.attach` can't be read from QML, a handler's QObject can)."""
    part = EffectsPart(bridge, spec)
    bridge.handle("effects", lambda: part)
    return part
