"""2D's curve view: the kit's (rostrum_gui/curve_view.py, the timeline's Curves) on 2D's layers. The picked layer's
curves are its animated number fields and its effects' and masks' (outline._fields); All curves, every layer's. Keys
are read placed in the composition (a layer's offset, keys on shared markers), so a key drag writes back its own time
(on a marker: stays on it). Its time snaps to 2D's targets (time_snap.py).
"""
from __future__ import annotations

from rostrum2d import fields as F
from rostrum_core.keys import marked
from rostrum_gui import curve_steps
from rostrum_gui.curve_view import CurveView

from . import time_snap
from .outline import _fields, label_of


class Curves(CurveView):
    def __init__(self, bridge, parent=None):
        super().__init__(bridge, bridge.outlineChanged, parent)   # only news (the editor redid its curves on every edit)

    def state(self):
        return self.b.placed(), self.b.selectedLayer

    def picked_items(self):
        layer = self.b.selectedLayer
        return [self.b.placed_item(layer)] if layer else []

    def scene_items(self):
        out = []

        def walk(layers):
            for lay in layers:
                if lay.get("type") in F.LAYERS:
                    out.append(lay)
                    walk(lay.get("layers", []))
        walk(self.b.placed().get("layers", []))
        return out

    def fields_of(self, item):
        return _fields(item)

    def field_label(self, owner, prop, item):
        name = F.param(owner["type"], prop).label
        return name if owner["id"] == item["id"] else f"{label_of(owner)} · {name}"

    def item_label(self, item):
        return label_of(item)

    def limits(self, owner, prop):
        p = F.param(owner["type"], prop)
        return (p.min if p.min is not None else -1e9), (p.max if p.max is not None else 1e9)

    def item(self, id_):
        return self.b.placed_item(id_)          # keys on a marker: at their seconds

    def picked_keys(self):
        return list(self.b._keys.ids)

    def pick_key(self, key_id):
        self.b._keys.click([key_id], "", [])           # picked like a diamond (the key bar shows it)

    def snap_targets(self, key_id):
        return time_snap.targets(self.b, skip_keys=[key_id])

    def time_limits(self):
        c = self.b.comp()
        return 0.0, c["duration"], c["fps"]

    def key_time(self, owner, key, t):
        return marked.moved(key["ref"], t - key["t"]) if "ref" in key else t - self.b.offset(owner["id"])


# ---- screen steps (steps.py): the kit's, the same in 3D -----------------------------------------------------------
def steps_curves(bridge, step, rest):
    """curves on|off|all|mine | curvedrag <key> <dt s> <dv value> | handledrag <key> <1|2> <dx> <dy> (curve_steps.py)."""
    curve_steps.step(bridge.curves, step, rest)
