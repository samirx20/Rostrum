"""What the person sees in RostrumSound, as plain data for `inspect_screen` (rostrum_core.screen_state.write). Read only:
it takes everything from the bridge's existing state and changes nothing. No Qt."""
from __future__ import annotations


def _times(bridge) -> dict:
    """{id: seconds} of every block on the arrangement (note, hit, clip, line), as the rows show them."""
    return {b["id"]: b["t"] for r in bridge._view["rows"] for b in r.get("blocks", [])}


def _selected(bridge) -> list[dict]:
    at, out = _times(bridge), []
    for i in bridge.selection:
        if not bridge.doc.has(i):
            continue
        item = bridge.doc.item(i)
        row = {"id": i, "kind": item["type"], "name": bridge.label_of(item)}
        if i in at:
            row["time"] = at[i]
        out.append(row)
    return out


def state(bridge) -> dict:
    ids = [r["id"] for r in _selected(bridge)]
    z = bridge._zoom
    w = bridge.workspace
    return {
        "selection": _selected(bridge),
        "playhead": bridge.time,                       # seconds
        "range": bridge.timeRange or None,             # [start, end] seconds of the ruler's time range
        "scene": bridge.name,                          # the open song
        # The one workspace: the arrangement always shows; the bottom dock shows the Editor (piano roll), the Mixer or
        # nothing. `focus` is the area last clicked (select_slots.focusArea): the arrangement or the Editor's roll.
        "focus": {"arrange": "arrangement", "roll": "editor"}.get(bridge._area, bridge._area or "arrangement"),
        "view": {"dock": w.dock, "library": w.library, "viewStart": z.start, "viewSpan": bridge.viewSpan, "fit": z.fit,
                 "track": bridge._track, "playing": bridge.playing},
        "dragging": ids if bridge._drag is not None or bridge._edit is not None else [],
    }
