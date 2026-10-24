"""Edit mesh's actions (SPEC §4.3), a mix-in for MeshEdit: what fits the selection type (faces: Extrude, Inset), each run
at once with its last numbers (one undo step), its numbers then editable below it until the next action: a new number
takes that step back and runs it again with the number, so it stays ONE step. And the extrude arrow: faces picked and
Extrude the last action, an arrow on their centre along their normal; dragging it shows the new distance, letting go
runs the extrude again with it (one step). Numbers are shown in mm; the operations get metres.
"""
from __future__ import annotations

from PySide6.QtCore import Slot

from . import gizmo as G, mesh_edit as M

ACTIONS = {"faces": [("extrude", "Extrude"), ("inset", "Inset")], "edges": [], "points": []}
NUMBERS = {"extrude": [("distance", "Distance")], "inset": [("width", "Width"), ("depth", "Depth")]}
START = {"extrude": {"distance": 5.0}, "inset": {"width": 3.0, "depth": 0.0}}       # mm, until the person types others
OPS = {"extrude": "faces.extrude", "inset": "faces.inset"}
WORDS = {"extrude": "Extrude", "inset": "Inset"}


class MeshActions:
    def _init_actions(self):
        self._nums = {k: dict(v) for k, v in START.items()}
        self._last = None                      # {"name", "change", "selector"}: the action whose numbers show
        self._arrow = None                     # the open arrow drag: {"start", "base", "tip", "units", "mm"}

    def _actions(self):
        return [{"id": i, "label": w} for i, w in ACTIONS[self._kind]] if self._on and self._sel else []

    def _last_word(self):
        return WORDS[self._last["name"]] if self._last else ""

    def _numbers(self):
        if self._last is None:
            return []
        n = self._last["name"]
        return [{"name": k, "label": lab, "value": self._nums[n][k]} for k, lab in NUMBERS[n]]

    def _drag_label(self):
        return f"Distance {self._arrow['mm']:.1f} mm" if self._arrow else ""

    def _call(self, name, selector):
        n = self._nums[name]
        args = {"faces": selector}
        args.update({"distance": n["distance"] / 1000} if name == "extrude" else
                    {"width": n["width"] / 1000, "depth": n["depth"] / 1000})
        return {"op": OPS[name], "target": [self._id], "args": args}

    def _run(self, name, selector):
        it = self.bridge.doc.item(self._id)
        made = []

        def go():
            self.bridge._apply([self._call(name, selector)], f"{WORDS[name]} {M.label(self._kind, len(self._sel))}")
            made.append(self.bridge.doc.history.changes[-1])
        if self.bridge._guard(go):
            self._last = {"name": name, "change": made[0], "selector": selector, "item": it["id"]}
        self.changed.emit()

    @Slot(str)
    def runAction(self, name):
        if self._geo is None or not self._sel or name not in OPS:
            return
        self._run(name, self.selector())

    @Slot(str, float)
    def setNumber(self, key, value):
        """A number typed under the last action: that step taken back and run again with it (still one step)."""
        if self._last is None:
            return
        name = self._last["name"]
        self._nums[name][key] = float(value)
        self._again()

    def _again(self):
        last, doc = self._last, self.bridge.doc
        if doc.history.changes and doc.history.changes[-1] is last["change"]:
            self.bridge._guard(lambda: doc.undo_changes([last["change"]], self.bridge.who))
        self._run(last["name"], last["selector"])

    # --- the extrude arrow (positions in parts of the viewport, 0..1)
    def arrow_shown(self) -> bool:
        return bool(self._on and self._geo is not None and self._kind == "faces" and self._sel
                    and self._last is not None and self._last["name"] == "extrude")

    def arrow_now(self):
        if not self.arrow_shown():
            return None
        moved = (self._arrow["mm"] - self._nums["extrude"]["distance"]) / 1000 if self._arrow else 0.0
        return M.arrow(self._geo, self._sel, self.px(), moved)

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
        self._arrow = {"start": self._pt(fx, fy), "base": a[0], "tip": a[1], "units": a[2],
                       "mm": self._nums["extrude"]["distance"], "from": self._nums["extrude"]["distance"]}
        return True

    @Slot(float, float, bool)
    def arrowDrag(self, fx, fy, free):
        g = self._arrow
        if g is None:
            return
        mm = g["from"] + M.along(g["base"], g["tip"], g["units"], g["start"], self._pt(fx, fy)) * 1000
        g["mm"] = mm if free else round(mm * 2) / 2                      # 0.5 mm steps; Ctrl frees
        self.changed.emit()

    @Slot()
    def arrowEnd(self):
        g, self._arrow = self._arrow, None
        if g is not None and abs(g["mm"] - g["from"]) > 1e-6:
            self._nums["extrude"]["distance"] = g["mm"]
            self._again()
        self.changed.emit()

    # --- the gizmo on the selection (gizmo_qt.py's drag, in Edit mode)
    def gizmo_step(self, g, c, now, free):
        """(this move's `mesh.transform` call, the readout): only what changed since the last move, as the gesture
        adds its previews up."""
        k, done = g["kind"], g.get("done")
        if k in ("move", "pivot"):
            total = G.moved_by(c["view"], g["handle"], c["origin"], c["axes"], g["start"], now)
            step = [t - d for t, d in zip(total, done or [0.0] * 3)]
            word = "Move " + " ".join(f"{x * 1000:.1f}" for x in total) + " mm"
        elif k == "turn":
            total = G.turned_by(c["view"], g["handle"], c["origin"], c["axes"], g["start"], now)
            total, _ = G.snapped(total, G.angle_targets(total), G.ARM * 0.8 * 3.14159 / 180, free)
            step, word = total - (done or 0.0), f"Turn {total:.1f}°"
        else:
            total = G.scaled_by(g["line"], g["start"], now)
            step, word = total / (done or 1.0), f"Scale ×{total:.2f}"
        g["done"] = total
        axis = int(g["handle"][-1]) if g["handle"][-1].isdigit() else -1
        return self.gizmo_call("move" if k == "pivot" else k, axis, step), word
