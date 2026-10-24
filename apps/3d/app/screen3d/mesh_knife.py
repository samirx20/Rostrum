"""The Knife tool of Edit mesh (SPEC 4.3), a mix-in for MeshEdit: K starts it; a click puts a point on the surface under
the pointer (the nearest face the ray goes through), a line is drawn through the points as they are placed; Enter
cuts along it (one `mesh.knife`, one undo step), Esc drops it. Points are kept in the item's own space, as the
operation takes them, with the view direction in that space so the cut can pass straight through (SPEC 4.3).
"""
from __future__ import annotations

from PySide6.QtCore import Slot

from rostrum3d import aim

from . import mesh_edit as M


class MeshKnife:
    def _init_knife(self):
        self._knife = None                    # None: the tool is off; else the points placed so far, in the item's space

    def _knife_hint(self):
        if self._knife is None:
            return ""
        n = len(self._knife)
        return ("Click to put the cut's first point on the surface" if n == 0 else
                "Click the next point" if n == 1 else f"{n} points · Enter cuts · Esc cancels")

    def _knife_line(self):
        """The placed points on the picture (px)."""
        g = self._geo
        out = [g.view.project(aim.point(g.world, p)) for p in self._knife or []]
        return [p[:2] for p in out if p]

    @Slot()
    def toggleKnife(self):
        if not self._on or self._geo is None:
            return
        self._knife = None if self._knife is not None else []
        self.changed.emit()

    @Slot()
    def escape(self):
        """Esc: the knife drops its line; with no knife, Edit mesh is left."""
        if self._knife is not None:
            self._knife = None
            self.changed.emit()
        else:
            self.leave()

    @Slot(float, float)
    def knifeAt(self, fx, fy):
        if self._knife is None or self._geo is None:
            return
        x, y = self._pt(fx, fy)
        face, t = M.face_hit(self._geo, x, y)
        if face is None:
            return self.bridge.fail_line("Knife: put the point on the mesh.")
        v = self._geo.view
        d = v.ray(x, y)
        spot = [v.eye[i] + d[i] * t for i in range(3)]
        self._knife.append([round(c, 7) for c in aim._apply(aim._inverse(self._geo.world[0]), spot)])
        self.changed.emit()

    @Slot()
    def knifeApply(self):
        if self._knife is None:
            return
        if len(self._knife) < 2:
            return self.bridge.fail_line("Knife needs two points on the mesh at least.")
        g, inv = self._geo, aim._inverse(self._geo.world[0])
        eye, ahead = (aim._apply(inv, p) for p in (g.view.eye, [g.view.eye[i] + g.view.fwd[i] for i in range(3)]))
        look = M._norm([ahead[i] - eye[i] for i in range(3)])
        call = {"op": "mesh.knife", "target": [self._id], "args": {"points": self._knife, "view": [round(c, 7) for c in look]}}
        if self.bridge._guard(lambda: self.bridge._apply([call], "Knife")):
            self._knife, self._sel, self._last = None, set(), None
        self.changed.emit()
