"""What the person sees in Rostrum2D, as plain data for `inspect_screen` (rostrum_core.screen_state.write). Read only:
it takes everything from the bridge's existing state and changes nothing. No Qt."""
from __future__ import annotations


def _selected(bridge) -> list[dict]:
    out = []
    for i in bridge.selection:
        if not bridge.doc.has(i):
            continue
        item = bridge.doc.item(i)
        row = {"id": i, "kind": item["type"], "name": bridge.label_of(item)}
        if item["type"] == "key":                      # a key sits at a time (its own seconds) ...
            row["time"] = bridge.placed_item(i).get("t", item.get("t"))
        elif "start" in item:                          # ... a layer starts at one (composition seconds)
            row["time"] = bridge.placed_item(i).get("start", item["start"])
        out.append(row)
    return out


def state(bridge) -> dict:
    comp = bridge.comp()
    ids = [r["id"] for r in _selected(bridge)]
    return {
        "selection": _selected(bridge),
        "playhead": bridge._t,                         # composition seconds
        "range": None,                                 # 2D has no time range yet
        "scene": bridge.label_of(comp),                # the open composition
        # the area last pressed (the kit's AppShell.focusArea, named by Main.qml's areaNames, via bridge.setFocusArea)
        "focus": getattr(bridge, "_focus_area", "") or "canvas",
        "view": {"tool": bridge.tool, "playing": bridge.playing, "previewSize": bridge.frameInfo["previewSize"]},
        # every move, resize, turn, bar, key or point drag acts on the selection, so that is what is being dragged
        "dragging": ids if bridge._drag is not None else [],
    }
