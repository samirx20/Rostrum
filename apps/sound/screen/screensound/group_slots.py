"""Folding groups in the arrangement: the person's own screen state (never the song, never undone, never saved);
`groups.py` draws it. Alt+click on a fold arrow folds or unfolds every group."""
from __future__ import annotations

from PySide6.QtCore import Slot

from . import group_drag


class GroupSlots:
    _folded: frozenset = frozenset()          # ids of the folded groups

    @Slot(str, bool)
    def toggleFold(self, bus_id, everyone):
        """Fold (or unfold) a group; with `everyone`, all groups: folded unless they all already are."""
        groups = [b["id"] for b in self.doc.data.get("buses", []) if any(
            x.get("output") == b["id"] for x in [*self.doc.data.get("tracks", []), *self.doc.data.get("buses", [])])]
        if everyone:
            self._folded = frozenset() if all(g in self._folded for g in groups) else frozenset(groups)
        else:
            self._folded = self._folded ^ {bus_id}
        self._rebuild()

    @Slot("QVariantList", str, bool)
    def dropTracks(self, dragged, over_id, below):
        """A track header dropped on the arrangement's row `over_id` (its lower half: `below`): onto a group's header it
        joins the group; onto a track it moves to sit there (above it, or under it) in that track's group, or out of its own.
        The selected tracks go with it when it is one of them; one undo step, the tracks' settings untouched."""
        def go():
            ids = list(self.selectedIds) if any(t in self.selectedIds for t in dragged) else list(dragged)
            calls = group_drag.drop_calls(self.doc.data, self._view["rows"], ids, over_id, below)
            if calls:
                self._apply(calls, {"bus.add_track": "Move into a group", "bus.remove_track": "Move out of a group"}.get(calls[0]["op"], "Move track"))
        self._guard(go)

    @Slot(str, str)
    def toggleGroupMS(self, bus_id, field):
        """M or S on a group's header (`field` mute / solo): the group's mute, or every track in it soloed."""
        def go():
            calls, label = group_drag.toggle_calls(self.doc.data, bus_id, field)
            if calls:
                self._apply(calls, label)
        self._guard(go)

    @Slot(str, str, result=str)
    def dropTarget(self, over_id, dragged_id):
        """What dropping the track header `dragged_id` on row `over_id` would do, for the drag's marks: "join:<group id>",
        "leave:" (it is in a group now), "move:" (the same group or none: only its place changes) or "" (nothing)."""
        t = group_drag.drop_target(self._view["rows"], over_id)
        if not t:
            return ""
        here = next((x for x in self.doc.data.get("tracks", []) if x["id"] == dragged_id), {}).get("output", "master")
        if t[0] == "join" and here == t[1]:
            return "move:" if over_id != dragged_id and not any(r["id"] == over_id and r.get("group") for r in self._view["rows"]) else ""
        if t[0] == "leave" and here in {b["id"] for b in self.doc.data.get("buses", [])}:
            return "leave:"
        return "join:" + t[1] if t[0] == "join" else "move:" if over_id != dragged_id else ""
