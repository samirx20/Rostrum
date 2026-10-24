"""3D's part of the picked stretch (the kit's rostrum_gui/stretch_select.py, `backend.stretch`): a scene item's
animations in 3D's names (rostrum3d/anims.py: Position, Turn, Scale each one) and document seconds; its fields'
labels and units (fields.py). Click a stretch on the timeline: the settings panel is that animation (AnimPanel.qml)."""
from __future__ import annotations

from rostrum3d import fields as F
from rostrum3d.anims import animations
from rostrum_gui.stretch_select import StretchSelect

from . import outline


class Stretch3D(StretchSelect):
    def animations(self, owner_id):
        return animations(self.b.doc.item(owner_id))

    def fps(self):
        return self.b.shot_info()["fps"]

    def owner_label(self, item):
        return outline.label_of(item)

    def param(self, type_, prop):
        return F.param(type_, prop)

    def picked_items(self):
        return [self.b.selectedOwner] if self.b.selectedOwner else []

    def let_keys_go(self):
        self.b.keys.clear()
