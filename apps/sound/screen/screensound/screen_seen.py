"""What the person sees in RostrumSound, as plain data for `inspect_screen` (rostrum_core.screen_state.write). Read only:
it takes everything from the bridge's existing state and changes nothing. No Qt of its own."""
from __future__ import annotations

from rostrum_gui.live_link import Later


def _selected(bridge) -> Later:
    """The selection as [{id, kind, name, time?}], named on the link's thread when it is written (live_link.Later):
    asked every 300 ms, and naming a whole-song selection held the screen ~40-70 ms. Its key: the song data, the
    rows and the ids (each change makes a new song tree and new rows, never written in place)."""
    data, rows, ids, locs = bridge.doc.data, bridge._view["rows"], tuple(bridge.selection), bridge.doc.locs()
    return Later((_Same(data), _Same(rows), ids), lambda: _named(locs, rows, ids, bridge.label_of))


class _Same:
    """Equal only to the very same object (a song tree or the rows: compared by identity, never by content)."""
    __slots__ = ("of",)

    def __init__(self, of):
        self.of = of

    def __eq__(self, other):
        return isinstance(other, _Same) and other.of is self.of


_NAMES: dict = {}       # item id -> (the item, its name): a change makes new objects only for what it changed (link thread)


def _named(locs, rows, ids, label_of) -> list[dict]:
    at = {b["id"]: b["t"] for r in rows for b in r.get("blocks", [])}      # seconds, as the rows show them
    out = []
    if len(_NAMES) > 50_000:
        _NAMES.clear()
    for i in ids:
        if i not in locs:
            continue
        item, kept = locs[i].item, _NAMES.get(i)
        if kept is None or kept[0] is not item:
            kept = _NAMES[i] = (item, label_of(item))
        row = {"id": i, "kind": item["type"], "name": kept[1]}
        if i in at:
            row["time"] = at[i]
        out.append(row)
    return out


def state(bridge) -> dict:
    ids = list(bridge.selection)
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
