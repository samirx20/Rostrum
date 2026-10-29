"""The material picker's side of the screen (SPEC §6.1–6.2, brief 9), for QML as `backend.mats`: the project's
materials and the starting points (each with its rendered ball, material_balls.py), the material of the one selected
item ("Used by 3 items", Make its own), and that material's own settings inline under the item's (the kit's rows,
K3's rule: Surface open, changed groups open, the rest a row of names).

The material's ESSENTIALS (the primary params, Base colour, Metallic, Roughness, with the rest of their group, the images) go in `head`,
which the panel puts right under the item's name with the Material ▾ (above the item's own rows, so the colour is never
below a fold, whatever groups the item has open); every other row
(the other groups and their names) is in `rows`, under the item's rows. One split by importance, the same for every kind.

Every click is an operation through the bridge (material.assign / material.from / material.split), one undo step each.
The inline rows edit the MATERIAL (material.set through the bridge's edit_call), so every item sharing it changes:
that is what sharing means. InspectorRow talks to this object as its `bridge` (setValue, scrubs, toggleGroup). A drag of a number or a colour is
drawn live in the window's view and written once at the release (material_live.py).

A clay holds a material too (SPEC § 1 4:10: Base colour's square beside its Material ▾). New clays share the project's
"Clay" material without anyone choosing that (ops_clay.clay_material), so the first change to it from a clay's panel
first gives that clay its own copy (material.split, "Make its own material", its own undo step), then changes the copy:
colouring one clay never recolours the others. A material the person shared on purpose (assigned, named) stays shared.
"""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot
from rostrum3d import fields as F
from rostrum3d.material_starts import STARTS
from rostrum3d.ops_materials import users_of
from rostrum3d.ops_scene import USERS
from rostrum_gui import rows, sections
from rostrum_gui.edits import Scrub
from rostrum_gui.model import RowsModel

from . import material_live, outline, route, shown_blocks



class Materials3D(QObject):
    changed = Signal()
    rowsChanged = Signal()

    def __init__(self, bridge, balls=None, parent=None):
        super().__init__(parent or bridge)
        self.b, self.balls = bridge, balls
        self._open, self._scrub, self._mat = {}, None, ""
        self._live = None                               # a live drag (material_live.Drag): the view only, until the release
        self._held = None                               # a shown block setting's drag: [row id, value], written at the release
        self.model = RowsModel(rows.ROLES, self)       # the secondary rows, under the item's own
        self.headModel = RowsModel(rows.ROLES, self)   # the primary ones, over them
        bridge.outlineChanged.connect(self._refresh)
        bridge.frameChanged.connect(self._on_frame)
        if balls is not None:
            balls.updated.connect(self.changed)

    # ---- what QML reads ---------------------------------------------------------------------------------------
    def _ball(self, values: dict) -> str:
        return self.balls.url(values) if self.balls is not None else ""

    def _entry(self, mat: dict) -> dict:
        return {"id": mat["id"], "label": outline.label_of(mat), "colour": mat.get("baseColor", "#cccccc"),
                "users": len(users_of(self.b.doc.data, mat["id"])), "ball": self._ball(self._values(mat))}

    @staticmethod
    def _values(mat: dict) -> dict:
        return {p.name: mat.get(p.name, p.default) for p in F.FIELDS["material"]}

    @Property("QVariantList", notify=changed)
    def project(self):
        return [self._entry(m) for m in self.b.doc.data.get("materials", [])]

    @Property("QVariantList", notify=changed)
    def starts(self):
        return [{"value": k, "label": s["label"], "colour": s["values"].get("baseColor", "#cccccc"),
                 "ball": self._ball({**self._values({}), **s["values"]})} for k, s in STARTS.items()]

    def _holder(self) -> dict | None:
        """The one selected item that can hold a material, or None."""
        sel = self.b.selection
        if len(sel) != 1 or not self.b.doc.has(sel[0]):
            return None
        it = self.b.doc.item(sel[0])
        return it if it.get("type") in USERS else None

    @Property("QVariantMap", notify=changed)
    def current(self):
        it = self._holder()
        if it is None:
            return {}
        mid = self.b.shown_values(it).get("material", "")     # as the shown shot has it (Only in this shot)
        if not mid or not self.b.doc.has(mid):
            return {"id": "", "label": "None", "users": 0, "colour": "", "ball": "", "shared": False}
        e = self._entry(self.b.doc.item(mid))
        return {**e, "shared": e["users"] > 1}

    rows = Property(QObject, lambda self: self.model, constant=True)
    head = Property(QObject, lambda self: self.headModel, constant=True)

    # ---- the picker's clicks: each one operation ----------------------------------------------------------------
    def _run(self, call: dict, label: str):
        return self.b._guard(lambda: self.b._apply([call], label))

    def _sel(self) -> list[str]:
        return [i for i in self.b.selection if self.b.doc.item(i).get("type") in USERS]

    @Slot(str)
    def rowAction(self, action_id):
        """A material row's button (the inspector calls its bridge's rowAction): Use all shots, as on an item's rows."""
        self.b.rowAction(action_id)

    @Slot(str)
    def assign(self, material_id):
        if self.b.shotOnly:                     # Only in this shot: the shown shot's own material (bridge_shot_only.py)
            return self.b._guard(lambda: self.b._apply([self.b.edit_call(i, "material", material_id) for i in self._sel()], "Material"))
        self._run({"op": "material.assign", "target": self._sel(), "args": {"material": material_id}}, "Material")

    @Slot(str)
    def startFrom(self, start):
        self._run({"op": "material.from", "args": {"start": start, "to": self._sel()}},
                  f"New material: {STARTS[start]['label']}")

    @Slot()
    def split(self):
        self._run({"op": "material.split", "target": self._sel(), "args": {}}, "Make its own material")

    @Slot(str)
    def edit(self, material_id):
        self.b.select(material_id)

    @Slot(str, str)
    def dropOn(self, material_id, item_id):
        """A material dragged onto an item (the scene list, the viewport): that item gets it."""
        if not item_id:
            return
        if self.b.doc.item(item_id).get("type") not in USERS:
            return self.b.fail_line(f"Error: material: {outline.label_of(self.b.doc.item(item_id))} can't hold a material.")
        self._run({"op": "material.assign", "target": [item_id], "args": {"material": material_id}}, "Material")

    @Slot()
    def newMaterial(self):
        self.b.adder.add("material")

    # ---- the inline rows: InspectorRow's bridge -----------------------------------------------------------------
    def _on_frame(self):
        """A new frame changes only a keyed material's rows (their values at the playhead), never the picker's lists or
        balls: a scrub step redrew every ball (~20 ms a frame with a few materials)."""
        mat = self.b.doc.item(self._mat) if self._mat and self.b.doc.has(self._mat) else None
        if mat is not None and mat.get("keys"):
            self._rows()

    def _refresh(self):
        self.changed.emit()
        self._rows()

    def _rows(self):
        it = self._holder()
        mid = self.b.shown_values(it).get("material", "") if it else ""     # as the shown shot has them (PR1)
        mat = self.b.doc.item(mid) if mid and self.b.doc.has(mid) else None
        new = mat is None or mid != self._mat
        self._mat = mid if mat else ""
        if mat is None:
            self.model.reset([])
            self.headModel.reset([])
        else:
            op = self.b.doc.kind.registry.field_op("material")
            static = sections.layout(op, "material")
            out = self.b.mark_shot_own(mat["id"], rows.evaluate(static, self.b.shown_values(mat), self.b.facts_of(mat),
                                                                False, opened=self._open))
            top = [r for r in out if r["row"] == "param" and r.get("in") == ""]      # the essentials: primary params and their group's rest
            rest = [r for r in out if r not in top]
            top += shown_blocks.rows_for(mat, self.b.facts_of(mat))                  # block settings shown on it (PR5)
            for model, part in ((self.headModel, top), (self.model, rest)):
                model.reset(part) if new else model.update(part)
        self.rowsChanged.emit()

    def _own_first(self):
        """A clay changing the project's shared "Clay" material: give it its own copy first (see the module's words)."""
        it = self._holder()
        if (it is None or it.get("type") != "clay" or not self._mat
                or self.b.doc.item(self._mat).get("name") != STARTS["clay"]["label"]
                or len(users_of(self.b.doc.data, self._mat)) < 2):
            return
        self.split()
        self._refresh()                                 # self._mat is now the clay's own copy

    @Slot(str, "QVariant", result=bool)
    def setValue(self, param, value):
        self._own_first()
        if not self._mat:
            return False
        if shown_blocks.is_shown(param):
            call, label = shown_blocks.call_for(self.b.doc.item(self._mat), param, value)
            return self._run(call, label)
        return self._run(self.b.edit_call(self._mat, param, value), f"Material: {param}")

    @Slot(str)
    def beginScrub(self, param):
        self.endScrub()
        self._own_first()
        if not self._mat:
            return
        if shown_blocks.is_shown(param):            # a shown block setting: written once at the release
            self._held = [param, None]
            return
        if material_live.ok(self.b, param):        # drawn live in the window's view, written once at the release
            mat = self.b.doc.item(self._mat)
            self._live = material_live.Drag(self.b, self._mat, param, mat.get(param, F.param("material", param).default),
                                            lambda _why: self._live_refused())
            return
        self.b._guard(lambda: setattr(self, "_scrub", Scrub(self.b.doc, self.b.who, [self._mat], param, self.b.edit_call)))

    @Slot(str, "QVariant")
    def scrub(self, param, value):
        if shown_blocks.is_shown(param):
            if self._held is None or self._held[0] != param:
                self.beginScrub(param)
            self._held[1] = value
            return
        if self._live is not None and self._live.param == param:
            return self._live.send(value)
        if self._scrub is None or self._scrub.name != param:
            self.beginScrub(param)
            if self._live is not None:
                return self._live.send(value)
        if self._scrub is not None:
            self.b._guard(lambda: self._scrub.preview(value))

    def _live_refused(self):
        """The view refused the live request: the rest of this drag is previewed in the document."""
        lv, self._live = self._live, None
        if lv is not None and self._mat:
            self.b._guard(lambda: setattr(self, "_scrub", Scrub(self.b.doc, self.b.who, [self._mat], lv.param,
                                                                 self.b.edit_call)))
            if lv.value is not None and self._scrub is not None:
                self.b._guard(lambda: self._scrub.preview(lv.value))

    def _live_end(self, cancel: bool):
        lv, self._live = self._live, None
        value = lv.end(cancel)
        if value is not None:
            self._run(self.b.edit_call(lv.material, lv.param, value), f"Material: {lv.param}")

    @Slot()
    def endScrub(self):
        held, self._held = self._held, None
        if held is not None and held[1] is not None:
            self.setValue(held[0], held[1])
        if self._live is not None:
            return self._live_end(cancel=False)
        s, self._scrub = self._scrub, None
        if s is not None:
            self.b._guard(lambda: self.b._done(s.end(), ""))

    @Slot()
    def cancelScrub(self):
        self._held = None
        if self._live is not None:
            return self._live_end(cancel=True)
        s, self._scrub = self._scrub, None
        if s is not None:
            self.b._guard(lambda: self.b._done(s.end(True), ""))

    @Slot(str)
    def toggleGroup(self, group):
        row = next((r for r in self.model.rows if r.get("fold") == group), None)
        if row and row.get("own"):
            return
        if row and row.get("switch"):           # Lines, Halftone …: its name adds it (the switch on), its − removes it
            self.setValue(row["switch"], row["off"] if row["open"] else row["on"])
            return
        self._open[group] = not (row and row["open"])
        self._refresh()

    @Slot(str)
    def toggleAnimate(self, param):
        self.b.fail_line("Error: material settings are not keyed from here: select the material (Edit) to key them.")
