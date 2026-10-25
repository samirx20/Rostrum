"""2D's part of the picked stretch (the kit's rostrum_gui/stretch_select.py, `backend.stretch`): a layer's animations
in 2D's names (anims.py) and composition seconds (a key as placed: retime.py), its settings' labels and units."""
from __future__ import annotations

from rostrum2d import fields as F
from rostrum2d.anims import animations
from rostrum2d.names import display_name
from rostrum_gui.stretch_select import StretchSelect as KitStretchSelect


class StretchSelect(KitStretchSelect):
    def animations(self, owner_id):
        return animations(self.b.placed_item(owner_id))

    def key(self, key_id):
        return self.b.placed_item(key_id)

    def own_t(self, owner_id, t):
        return self.b.own_t(owner_id, t)

    def fps(self):
        return self.b.comp()["fps"]

    def owner_label(self, item):
        return display_name(item)

    def param(self, type_, prop):
        return F.param(type_, prop)

    def picked_items(self):
        return self.b.selected_layers()

    def let_keys_go(self):
        self.b._keys.clear()

    def preview_ease(self, ids, ease):
        self.b._ease_play.preview(ids, ease)         # a hovered ease plays, nothing kept (ease_play.py)
