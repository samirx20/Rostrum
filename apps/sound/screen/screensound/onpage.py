"""A control appears once per screen: which fields the page's own controls already show, so the inspector leaves them
out (no Qt). One table, read by the bridge's `on_page` hook: page -> item type -> fields shown outside the inspector.

"*" holds what every page shows (the arrangement's track headers: mute, solo). The master strip's rows are its own
layout (strips.master_layout), so they are read from there, not listed twice.
"""
from __future__ import annotations

from . import strips

ON_PAGE = {
    "*": {"track": ("mute", "solo")},                                   # Timeline track headers (slim on every page)
    "mix": {"track": ("volume", "pan", "output"),                       # MixStrip: fader, pan, where it plays to
            "bus": ("volume", "pan", "mute", "output"),
            "send": ("level",),                                         # MixSends
            "master": ("volume",)},                                     # MixMaster's fader (+ its layout rows below)
}


def fields(page: str, item_type: str, registry) -> set[str]:
    """The fields of an item of this type that the page shows outside the inspector."""
    out = {*ON_PAGE["*"].get(item_type, ()), *ON_PAGE.get(page, {}).get(item_type, ())}
    if page == "mix" and item_type == "master":
        out |= {r["id"] for r in strips.master_layout(registry.field_op("master"))}
    return out

