"""A plugin's items on the Sound screen (plugin_parts.py: "wiggle:generator", kept byte for byte, never played). The
rest of the screen reads only the kinds Sound knows, through `known`; a plugin's item in the track list is a plain row
the person can select, lock, mute, move and delete with the same operations a track has, `row`. No Qt."""
from __future__ import annotations

from rostrum_core import plugin_parts

is_plugin = plugin_parts.is_plugin


def known(items):
    """`items` without the plugin's: what a block, a chain or a lane built from a child list may read."""
    if not any(is_plugin(i.get("type")) for i in items):
        return items                    # the very same list: what is kept by a list's identity (block_memo) stays kept
    return [i for i in items if not is_plugin(i.get("type"))]


def row(item: dict, index: int, hue: str) -> dict:
    """A plugin item's row in the arrangement: its name (else its kind in words), nothing on its lane."""
    return {"id": item["id"], "name": item.get("name") or plugin_parts.label(item["type"]), "hue": hue, "span": [60, 60],
            "drums": [], "mute": bool(item.get("mute")), "solo": False, "locked": bool(item.get("locked")),
            "kind": "plugin", "blocks": [], "icon": "audio", "canRecord": False, "canSolo": False, "canLane": False, "autoUsed": [], "auto": None}
