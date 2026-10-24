"""The edge the paint stays inside, shown while painting (UX_SPEC §3.8): a thin line along the target element's true
outline (rounded corners, an ellipse, a path's shape, a text's letters), not its box. The engine works it out with the
frame it draws (frames.py `place`, the engine's `place`: through the layer's groups, the camera and tilt), so the line
and the picture always agree. Only with the Draw tool on and an element (or drawing) to paint on. A QObject part, read
in QML as `backend.paintEdge`.
"""
from __future__ import annotations

import re

import pathops
from PySide6.QtCore import Property, QObject, Signal


def corner(d: str) -> tuple[float, float]:
    """The path's top-left (its smallest x and y): the edge is sent from there, as Qt's dashed line drops the dashes
    of a path at negative coordinates (a drawing that grew left or up of the world's 0, 0 lost its top and left edges)."""
    v = [float(n) for n in re.findall(r"-?[\d.]+(?:e-?\d+)?", d)]
    return (min(v[0::2]), min(v[1::2])) if v else (0.0, 0.0)


def moved(d: str, dx: float, dy: float) -> str:
    """M / L / Z path data moved by dx, dy."""
    def one(m):
        v = [float(n) for n in re.findall(r"-?[\d.]+(?:e-?\d+)?", m.group(2))]
        return m.group(1) + " ".join(f"{v[i] + (dx if i % 2 == 0 else dy):.2f}" for i in range(len(v)))
    return re.sub(r"([ML])([^MLZ]*)", one, d)


def outer(d: str) -> str:
    """The engine's edge (flattened M / L / Z contours) with overlaps merged: a path's fill and stroke outlines, a
    variable font's overlapping letter contours, so the line shows only the edge paint stops at, never lines inside."""
    path = pathops.Path()
    pen = path.getPen()
    for cmd, nums in re.findall(r"([MLZ])([^MLZ]*)", d):
        if cmd == "Z":
            pen.closePath()
            continue
        v = [float(n) for n in re.findall(r"-?[\d.]+(?:e-?\d+)?", nums)]
        for i in range(0, len(v) - 1, 2):
            (pen.moveTo if cmd == "M" and i == 0 else pen.lineTo)((v[i], v[i + 1]))
    path.simplify(fix_winding=True)
    out = []
    for op, pts in path.segments:
        if op == "closePath":
            out.append("Z")
        elif pts:
            out.append(("M" if op == "moveTo" else "L") + " ".join(f"{x:.2f} {y:.2f}" for x, y in pts[-1:]))
    return " ".join(out)


class PaintEdge(QObject):
    changed = Signal()

    def __init__(self, bridge):
        super().__init__(bridge)
        self.b = bridge
        self._asked, self._layer, self._path, self._at = [], "", "", (0.0, 0.0)
        bridge.frames.placed.connect(self._on_placed)
        for s in (bridge.toolChanged, bridge.selectedItemsChanged, bridge.painter.changed):
            s.connect(self._retarget)

    def ids(self) -> list[str]:
        """The layer whose edge the next frame asks for: the pen's target while Draw is on."""
        target = self.b.painter._aim() if self.b.tool == "draw" else None
        return [target["id"]] if target else []

    def asked(self, ids: list[str]):
        """A frame job asking for these layers' places was just requested."""
        self._asked = ids
        if not ids and self._layer:
            self._layer, self._path = "", ""
            self.changed.emit()

    def _retarget(self):
        if self.ids() != self._asked:
            self.b._show()

    def _on_placed(self, places: dict):
        layer = next(iter(places), "")
        path = outer(places[layer]["edge"]) if layer else ""
        at = corner(path)
        path = moved(path, -at[0], -at[1]) if path else ""
        if (layer, path, at) != (self._layer, self._path, self._at):
            self._layer, self._path, self._at = layer, path, at
            self.changed.emit()

    layer = Property(str, lambda self: self._layer, notify=changed)      # "" while there is no edge to show
    path = Property(str, lambda self: self._path, notify=changed)        # path data in composition px, from `at`
    at = Property("QVariantMap", lambda self: {"x": self._at[0], "y": self._at[1]}, notify=changed)
