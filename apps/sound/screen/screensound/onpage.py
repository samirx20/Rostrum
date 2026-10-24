"""A control appears once per screen: which fields the workspace's own controls already show, so the inspector leaves
them out (no Qt). One table, read by the bridge's `on_page` hook: dock -> item type -> fields shown outside the inspector.

"*" holds what is always on screen (the arrangement's track headers: mute, solo). "mixer" is what the Mixer shows
while it is open in the bottom dock (workspace.py). The master's delivery settings (Normalize, the targets) are in
the Deliver dialog, not on the master strip, so the inspector keeps them.
"""
from __future__ import annotations

ON_SCREEN = {
    "*": {"track": ("mute", "solo")},                                   # the arrangement's track headers
    "mixer": {"track": ("volume", "pan", "output", "reverb"),           # MixStrip: the fader and its typed dB box, pan, where it plays to, reverb send:
              "bus": ("volume", "pan", "mute", "output"),               # one rule, the panel never repeats what the open Mixer shows
              "send": ("level",),                                       # MixSends
              "master": ("volume",)},
}


def fields(dock: str, item_type: str, registry=None) -> set[str]:
    """The fields of an item of this type that the screen shows outside the inspector, with this dock open."""
    return {*ON_SCREEN["*"].get(item_type, ()), *ON_SCREEN.get(dock, {}).get(item_type, ())}
