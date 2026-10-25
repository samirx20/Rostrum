"""What the person sees in RostrumSound, as plain data for `inspect_screen` (rostrum_core.screen_state.write). Read only:
it takes everything from the bridge's existing state and changes nothing. No Qt."""
from __future__ import annotations


def _times(bridge) -> dict:
    """{id: seconds} of every block on the arrangement (note, hit, clip, line), as the rows show them."""
    return {b["id"]: b["t"] for r in bridge._view["rows"] for b in r.get("blocks", [])}


def _selected(bridge) -> list[dict]:
    """Kept while the song, the selection and the rows are the very same (asked every 300 ms: naming 3,000 selected
    notes took ~40 ms each time)."""
    key = (bridge.doc.data, bridge._view["rows"], tuple(bridge.selection))
    kept = getattr(bridge, "_seen_selected", None)
    if kept and kept[0][0] is key[0] and kept[0][1] is key[1] and kept[0][2] == key[2]:
        return kept[1]
    out = _named(bridge)
    bridge._seen_selected = key, out
    return out


def _named(bridge) -> list[dict]:
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
    selected = _selected(bridge)
    ids = [r["id"] for r in selected]
    z = bridge._zoom
    w = bridge.workspace
    return {
        "selection": selected,
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
