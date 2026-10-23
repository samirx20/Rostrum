"""The colour pickers' swatches for a 2D window (kit colour_bank.py): the document's project colours and the project's
brand kit, refreshed after every change; the picker's "+" is the agents' `swatch.add`, one change, on the document whose
swatches the bank shows now (the window that changed or opened last). No widgets."""
from __future__ import annotations

from rostrum_gui.colour_bank import bank
from rostrum2d import brand_kit
from rostrum2d.ops_fill_paint import swatches

_showing = [None]                # the bridge whose colours the bank holds


def _add(hex_: str):
    bridge = _showing[0]
    if bridge is not None:
        bridge._guard(lambda: bridge.doc.apply([{"op": "swatch.add", "args": {"color": hex_}}], bridge.who))


def attach(bridge):
    b = bank()
    if _showing[0] is None:
        b.added.connect(_add)

    def refresh(*_):
        _showing[0] = bridge
        b.set_project([s["color"] for s in swatches(bridge.doc.data)])
        kit = brand_kit.read(bridge.doc.folder)["colors"] if bridge.doc.folder else []
        b.set_brand("Brand kit" if kit else "", [c["value"] for c in kit])
    bridge.doc.subscribe(refresh)
    refresh()
