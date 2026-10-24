"""The gizmo on Edit mesh's selection (gizmo_qt.py's drag, in Edit mode), a mix-in for MeshEdit: where it stands, and each
drag step as a `mesh.transform` call in the item's own space.
"""
from __future__ import annotations

from rostrum3d import aim

from . import gizmo as G


class MeshGizmo:
    def gizmo_frame(self):
        """{origin, own} for the gizmo: the selection's centre and the item's own axes in the world; None without one."""
        from . import mesh_edit as M
        if not self._on or self._geo is None or not self._sel or self._knife is not None or self.arrow_shown():
            return None
        return {"origin": M.centre(self._geo, self._kind, self._sel), "own": G.columns(self._geo.world[0])}

    def gizmo_call(self, kind, axis, amount):
        """One drag step of the gizmo as a `mesh.transform` call in the item's own space: move (a world vector), turn
        (degrees around own axis `axis`), scale (a factor along own axis `axis`)."""
        a = {"select": self.selector()}
        if kind == "move":
            a["move"] = [round(x, 7) for x in aim._apply(aim._inverse(self._geo.world[0]), amount)]
        elif kind == "turn":
            a["turn"] = [round(amount, 5) if i == axis else 0.0 for i in range(3)]
        else:
            a["scale"] = [round(amount, 6) if i == axis else 1.0 for i in range(3)]
        return {"op": "mesh.transform", "target": [self._id], "args": a}

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
