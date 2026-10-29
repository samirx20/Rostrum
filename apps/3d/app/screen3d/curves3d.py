"""3D's curve view (`backend.curves`): the kit's (rostrum_gui/curve_view.py, the timeline's Curves) on 3D's scene
items. An item's curves are its keyed number fields (on / off fields such as Visible have no curve); the picked items'
show, or every animated item's with nothing picked or All curves chosen. A key's time snaps as on the rows
(timeline3d.targets) and stays in the shot.
"""
from __future__ import annotations

from rostrum3d import fields as F
from rostrum_core.keys import animated
from rostrum_gui.curve_view import CurveView

from . import outline, timeline3d


class Curves3D(CurveView):
    def __init__(self, bridge, parent=None):
        super().__init__(bridge, bridge.outlineChanged, parent)
        bridge._keys.changed.connect(self.changed)      # the picked key's handles show

    def state(self):
        return self.b.doc.data, tuple(self.b.selectedRows), self.b.selectedOwner

    def picked_items(self):
        ids = self.b.selectedRows or ([self.b.selectedOwner] if self.b.selectedOwner else [])
        return [self.b.doc.item(i) for i in ids if self.b.doc.has(i)]

    def scene_items(self):
        return [it for it in outline.scene_items(self.b.doc.data) if it.get("type") in F.KEYED]

    def fields_of(self, item):
        keyed = animated(item)
        return [(item, p) for p in F.animatable(item["type"]) if p in keyed and not F.is_toggle(item["type"], p)]

    def field_label(self, owner, prop, item):
        p = F.param(owner["type"], prop)
        return p.label if p is not None else prop

    def item_label(self, item):
        return outline.label_of(item)

    def limits(self, owner, prop):
        p = F.param(owner["type"], prop)
        lo = p.min if p is not None and p.min is not None else -1e9
        return lo, p.max if p is not None and p.max is not None else 1e9

    def picked_keys(self):
        return list(self.b._keys.ids)

    def pick_key(self, key_id):
        self.b._keys.click([key_id], "", [])           # as a diamond click: one key is also the selection

    def snap_targets(self, key_id):
        return timeline3d.targets(self.b, {key_id})

    def time_limits(self):
        info = self.b.shot_info()
        return info["start"] / info["fps"], (info["end"] + 1) / info["fps"], info["fps"]

