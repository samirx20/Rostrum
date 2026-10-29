"""Paint mode's chosen layer rows, for QML as `paintMode.layerRowsObj` (SPEC §13, PR5): Fill (the layer covers the
whole surface with its Fill colour) and Mask (None, Edges, Cavities, Facing up, Thin parts; Spread and Invert only
while a mask is chosen), as the kit's own rows (InspectorRow talks to this object as its `bridge`). Each change is one
`paint.set` on the layer, one undo step; a Spread drag is one step when let go.

A mask is worked out from the item's shape the first time it is needed (rostrum3d.paint_masks, seconds on a big
clay): off the window's thread, the status line saying "Finding edges…", then the layer is set; after that it is kept.
"""
from __future__ import annotations

import threading
from types import SimpleNamespace

from PySide6.QtCore import Property, QObject, Signal, Slot
from rostrum3d import clay_paint, paint_masks, paint_scene
from rostrum3d.paint_fields import LAYER, MASKS
from rostrum_core import RostrumError
from rostrum_gui import rows
from rostrum_gui.model import RowsModel

PARAMS = [p for p in LAYER if p.name in ("fill", "fillColor", "shapeMask", "maskSpread", "maskInvert")]
FINDING = {"edges": "Finding edges…", "cavities": "Finding cavities…", "up": "Finding what faces up…",
           "thin": "Finding thin parts…"}


class PaintLayerRows(QObject):
    changed = Signal()
    found = Signal(object)                # (layer id, mask, error or "") from the worker thread

    def __init__(self, mode, parent=None):
        super().__init__(parent)
        self.m, self._pending, self._busy = mode, {}, False
        self.model = RowsModel(rows.ROLES, self)
        self._static = rows.layout(SimpleNamespace(params=PARAMS))
        self.model.reset(self._rows())
        self.found.connect(self._on_found)

    def _values(self) -> dict:
        layer = self.m._layer() or {}
        return {**{p.name: layer.get(p.name, p.default) for p in PARAMS}, **self._pending}

    def _rows(self):
        return rows.evaluate(self._static, self._values(), {}, False)

    def refresh(self):
        self._pending = {}
        self.model.update(self._rows())
        self.changed.emit()

    rows = Property(QObject, lambda s: s.model, constant=True)
    busy = Property(bool, lambda s: s._busy, notify=changed)

    def _set(self, name: str, value) -> bool:
        layer = self.m._layer()
        p = next((q for q in PARAMS if q.name == name), None)
        if layer is None or p is None or self._busy:
            return False
        try:
            value = p.check(round(value, 4) if isinstance(value, float) else value, f"layer.{name}")
        except RostrumError as e:
            self.m.b.fail_line(e.line())
            return False
        args = {name: value}
        if name == "fill" and value:
            args["fillColor"] = self.m.brush.values["color"]       # filled with the brush's colour; changed after
        if name == "shapeMask" and value != "none" and not self._mask_ready():
            return self._find(layer["id"], value)
        return self._apply(layer["id"], args)

    def _apply(self, layer_id: str, args: dict) -> bool:
        label = f'{PARAMS[[p.name for p in PARAMS].index(next(iter(args)))].label}'
        ok = self.m.b._guard(lambda: self.m.b._apply([{"op": "paint.set", "target": [layer_id], "args": args}],
                                                     f"Paint layer: {label}"))
        self.refresh()
        return bool(ok)

    # --- the first mask: worked out off the window's thread
    def _surface(self):
        item = self.m._item() or {}
        if item.get("type") != "clay":
            return None
        f = paint_scene.surface_of(self.m.v.sent()[0] or {}, item["id"])
        return clay_paint.read(f) if f else None

    def _mask_ready(self) -> bool:
        item = self.m._item() or {}
        if item.get("type") == "clay" and self._surface() is None:
            return True                                          # no surface yet: the paint waits for the engine anyway
        return paint_masks.ready(item, self._surface(), item.get("paintSize", 2048))

    def _find(self, layer_id: str, mask: str) -> bool:
        item, surface = dict(self.m._item()), self._surface()
        self._busy, self._pending = True, {"shapeMask": mask}
        self.model.update(self._rows())
        self.changed.emit()
        self.m.b.say(FINDING[mask])

        def work():
            try:
                paint_masks.masks(item, surface, item.get("paintSize", 2048))
                self.found.emit((layer_id, mask, ""))
            except Exception as e:  # noqa: BLE001  said on the status line, never a silent miss
                self.found.emit((layer_id, mask, str(e)))
        threading.Thread(target=work, name="paint-masks", daemon=True).start()
        return True

    def _on_found(self, got):
        layer_id, mask, err = got
        self._busy = False
        if err:
            self.refresh()
            return self.m.b.fail_line(f"Error: mask {MASKS[mask]}: {err}")
        self.m.b.say("")
        if self.m.b.doc.has(layer_id):
            self._apply(layer_id, {"shapeMask": mask})

    # --- InspectorRow's bridge
    @Slot(str, "QVariant", result=bool)
    def setValue(self, name, value):
        return self._set(name, value)

    @Slot(str)
    def beginScrub(self, name):
        pass

    @Slot(str, "QVariant")
    def scrub(self, name, value):                    # shown while dragged, one change when let go
        self._pending[name] = value
        self.model.update(self._rows())

    @Slot()
    def endScrub(self):
        pending, self._pending = dict(self._pending), {}
        layer = self.m._layer()
        if pending and layer is not None:
            name, value = next(iter(pending.items()))
            self._set(name, value)

    @Slot()
    def cancelScrub(self):
        self.refresh()

    @Slot(str)
    def toggleGroup(self, group):
        pass

    @Slot(str)
    def toggleAnimate(self, name):
        pass
