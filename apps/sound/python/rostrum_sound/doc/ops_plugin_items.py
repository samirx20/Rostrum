"""An item of a plugin this Rostrum doesn't have ("wiggle:generator": plugin_parts.py), kept in the file as it is and never
played. Delete, lock, unlock and move are the track operations (their targets take any plugin's item: PLUGIN_ITEM);
`plugin.set` is its one field here, Mute: it skips the item where the plugin would play it, and adds only that field."""
from __future__ import annotations

from rostrum_core import PLUGIN_ITEM, Param

from .registry import REGISTRY, set_fields

REGISTRY.operation("plugin.set", "Mute an item of a plugin this Rostrum doesn't have (it is kept as it is, never played here). "
                   "Its target is the item's id.", target=PLUGIN_ITEM, params=[Param.toggle("mute", group="Mix")],
                   label="Edit plugin item", fields=True)(set_fields)
