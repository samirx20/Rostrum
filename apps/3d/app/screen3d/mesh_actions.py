"""Edit mesh's actions (SPEC 4.3), a mix-in for MeshEdit: what fits the selection type (mesh_spec.py: faces Extrude,
Inset; edges Bevel, Loop cut, Sharp, Not sharp), each run at once with its last numbers (one undo step), its numbers
then editable below it until the next action: a new number takes that step back and runs it again with the number, so
it stays ONE step. Faces also take a Material. And the grip: faces picked and Extrude the last action (an arrow along
their normal), or edges picked and Bevel (an arrow to the right): dragging it shows the new number live, letting go
runs the action again with it (one step). Numbers are shown in mm; the operations get metres.
"""
from __future__ import annotations

from PySide6.QtCore import Slot

from . import mesh_arrow as A, mesh_edit as M, mesh_spec as S


class MeshActions:
    def _init_actions(self):
        self._nums = {k: dict(v) for k, v in S.START.items()}
        self._last = None                      # {"name", "change", "selector"}: the action whose numbers show
        self._arrow = None                     # the open grip drag: {"start", "base", "tip", "units", "mm", "from"}

    def _actions(self):
        return [{"id": i, "label": S.WORDS[i]} for i in S.ACTIONS[self._kind]] if self._on and self._sel else []

    def _last_word(self):
        return S.WORDS[self._last["name"]] if self._last else ""

    def _numbers(self):
        return S.numbers(self._last["name"], self._nums) if self._last else []

    def _grip(self):
        """(name, number key) of the last action's grip, or None."""
        return S.ARROWED.get(self._last["name"]) if self._last else None

    def _drag_label(self):
        if not self._arrow:
            return ""
        key = self._grip()[0]
        return f"{key.capitalize()} {self._arrow['mm']:.1f} mm"

    def _run(self, name, selector, extra=None, remember=True, at=None):
        it = self.bridge.doc.item(self._id)
        made = []
        args = {**S.args(name, self._nums, selector), **(extra or {})}
        count = len(self._sel)

        def go():
            self.bridge._apply([{"op": S.OPS[name], "target": [self._id], "args": args}],
                               f"{S.WORDS[name]} {M.label(self._kind, count)}")
            made.append(self.bridge.doc.history.changes[-1])
        if at is None and self._geo is not None and self._sel:
            at = A.centre(self._geo, self._kind, self._sel)
        if self.bridge._guard(go) and remember:                      # `at`: where a bevel's grip stays (its edges go)
            self._last = {"name": name, "change": made[0], "selector": selector, "item": it["id"], "at": at}
        self.changed.emit()

    @Slot(str)
    def runAction(self, name):
        if self._geo is None or not self._sel or name not in S.ACTIONS[self._kind]:
            return
        self._run(name, self.selector())

    @Slot(str)
    def setFaceMaterial(self, material_id):
        """The picked faces take this material ("" gives them the shape's own again): `faces.material`, one step."""
        if self._geo is None or self._kind != "faces" or not self._sel:
            return
        self._run("material", self.selector(), {"material": material_id}, remember=False)

    @Slot(str, float)
    def setNumber(self, key, value):
        """A number typed under the last action: that step taken back and run again with it (still one step)."""
        if self._last is None:
            return
        name = self._last["name"]
        self._nums[name][key] = int(value) if key in S.INTS else float(value)
        self._again()

    def _again(self):
        last, doc = self._last, self.bridge.doc
        if doc.history.changes and doc.history.changes[-1] is last["change"]:
            self.bridge._guard(lambda: doc.undo_changes([last["change"]], self.bridge.who))
        self._run(last["name"], last["selector"], at=last.get("at"))

    # --- the grip (positions in parts of the viewport, 0..1)
    def arrow_shown(self) -> bool:
        g = self._grip()
        held = self._sel or (g and self._last["name"] != "extrude" and self._last.get("at"))
        return bool(self._on and self._geo is not None and g and self._kind == g[1] and held and self._knife is None)

    def arrow_now(self):
        if not self.arrow_shown():
            return None
        name, key = self._last["name"], self._grip()[0]
        moved = (self._arrow["mm"] - self._nums[name][key]) / 1000 if self._arrow else 0.0
        if name == "extrude":
            return A.arrow(self._geo, self._sel, self.px(), moved)
        return A.side_arrow(self._geo, self._last["at"], self.px())

    @Slot(float, float, result=bool)
    def arrowHit(self, fx, fy):
        a = self.arrow_now()
        if a is None:
            return False
        x, y = self._pt(fx, fy)
        return M._seg([x, y], a[0], a[1]) <= M.NEAR * self.px()

    @Slot(float, float, result=bool)
    def arrowBegin(self, fx, fy):
        a = self.arrow_now()
        if a is None:
            return False
        was = self._nums[self._last["name"]][self._grip()[0]]
        self._arrow = {"start": self._pt(fx, fy), "base": a[0], "tip": a[1], "units": a[2], "mm": was, "from": was}
        return True

    @Slot(float, float, bool)
    def arrowDrag(self, fx, fy, free):
        g = self._arrow
        if g is None:
            return
        mm = g["from"] + A.along(g["base"], g["tip"], g["units"], g["start"], self._pt(fx, fy)) * 1000
        mm = mm if free else round(mm * 2) / 2                           # 0.5 mm steps; Ctrl frees
        g["mm"] = max(mm, 0.1) if self._last["name"] == "bevel" else mm
        self.changed.emit()

    @Slot()
    def arrowEnd(self):
        g, self._arrow = self._arrow, None
        if g is not None and abs(g["mm"] - g["from"]) > 1e-6:
            self._nums[self._last["name"]][self._grip()[0]] = g["mm"]
            self._again()
        self.changed.emit()
