"""A song marker's right-click menu (sound-pro-workflows SPEC § 3.7): the kit's marker menu (rostrum_gui/marker_menu.py)
built from Sound's OWN marker operations (one `marker.set` renames, moves and colours; `marker.remove` deletes), plus
Sound's rows on a marker: Put a sound here and Start a bar here… (the one action list's own actions, run through it, so
the menu, the settings panel and Ctrl+K agree), and Loop to the next marker (the time range from this marker to the
next, Loop on; absent on the last marker). Every row is there only when it applies. A slot mix-in for SoundBridge.
"""
from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Slot
from rostrum_gui import marker_menu as MM
from rostrum_gui.actions import Action
from rostrum_sound import KIND

from .actions import LIST

OPS = MM.MarkerOps(KIND.registry, rename=("marker.set", "Rename"), move="marker.set", colour="marker.set",
                   remove="marker.remove")
OWN = ("place_sound", "fit_bar")              # the action list's marker actions, offered here when the list offers them


@dataclass
class Facts(MM.MarkerFacts):
    next_at: float | None = None               # the next marker's time (None: this is the last)
    offered: tuple = ()                        # the OWN actions the action list offers on this marker now


def _own(id_, rank):
    a = LIST.find(id_)
    return Action(id=id_, label=a.label, do="list", kinds=("marker",), valid=lambda f: id_ in f.offered,
                  importance="secondary", rank=rank, group="sound")


MENU = MM.MarkerMenu(OPS, extra=[_own("place_sound", 42), _own("fit_bar", 43),
                                 Action(id="loop_next", label="Loop to the next marker", do="loop_next",
                                        kinds=("marker",), valid=lambda f: f.next_at is not None,
                                        importance="secondary", rank=45, group="loop")])


class MarkerSlots:
    def _marker_facts(self, marker_id) -> Facts:
        marks = [m for m in self._view["markers"] if not m.get("shared")]
        at = next((m["t"] for m in marks if m["id"] == marker_id), 0.0)
        later = [m["t"] for m in self._view["markers"] if m["t"] > at + 1e-3]
        offered = tuple(e["id"] for e in LIST.available(self._facts()) if e["id"] in OWN)
        return Facts([marker_id], self._t, at, next_at=min(later) if later else None, offered=offered)

    @Slot(str, result="QVariantList")
    def markerMenu(self, marker_id):
        """Right-click on a song marker's tag: it is selected (so its own actions apply to it), then its menu."""
        if list(self._picks.ids) != [marker_id]:
            self._pick([marker_id])
        self._hub.refresh()
        return MENU.rows(self._marker_facts(marker_id))

    @Slot(str, str)
    def markerPick(self, marker_id, value):
        """A row of markerMenu chosen: its operation as one change, or the screen's own job."""
        def go():
            facts = self._marker_facts(marker_id)
            e = MENU.entry(facts, value)
            if e["do"] == "rename":
                return self.startRename(marker_id)
            if e["do"] == "list":                         # the action list's own (Put a sound here, Start a bar here…)
                return self._hub.choose(value)
            if e["do"] == "loop_next":
                self._set_range(facts.at, facts.next_at, True, False)
                if not getattr(self, "_loop", False):
                    self.toggleLoop()
                return True
            words = {"marker.move": "Move marker to playhead"}.get(e["id"]) or (
                f"Marker colour · {e['label']}" if e["id"].startswith("colour:") else e["label"])
            return self._act(e["calls"], words)
        return self._guard(go)
