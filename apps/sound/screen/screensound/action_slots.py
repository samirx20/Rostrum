"""The selection's actions for the context bar, the right-click menu, Ctrl+K and the keys (a slot mix-in for
SoundBridge, next to select_slots.py): every door reads the one action list (actions.py, action_list.py) and runs
through `runAction`, as one change (copy only fills the clipboard). A key whose action doesn't apply does nothing and
the message line says why. Paste goes to the playhead on the selection's top track (clipboard.py); what a
duplicate, split or paste made is selected afterwards. The arrow and playhead keys are key_slots.py.
"""
from __future__ import annotations

from PySide6.QtCore import Signal, Slot
from rostrum_gui import commands
from rostrum_sound.doc import select_time as ST

from . import action_calls as C
from . import action_list as L
from . import clipboard, timing

MAKES = ("sel:duplicate", "sel:range_duplicate", "sel:split", "sel:paste", "sel:section")   # select what they made


class ActionSlots:
    libraryWanted = Signal(str)       # "Place a sound here": the Library opens on this chip
    cleanWanted = Signal()            # "Clean up…": the host opens the clean-up popover
    def _acts(self):
        return L.available(self.doc, self._picks.ids, self._t, self._picks.range, bool(self._board["items"]),
                           self._track)

    @Slot(result="QVariantList")
    def actionBar(self):
        """The context bar's buttons in rank order: [{key, label, shortcut, menu}] ([] = no bar)."""
        return L.bar_items(self._acts())

    @Slot(int, result="QVariantList")
    def overflowMenu(self, shown):
        """⋯: what the bar doesn't show (its buttons past `shown`, then the secondary actions)."""
        return L.overflow(self._acts(), shown)

    @Slot(result="QVariantList")
    def actionMenu(self):
        """The right-click menu: every valid action, the edit block last: [{value, label, hint, group}]."""
        return L.menu_entries(self._acts())

    @Slot(str, result="QVariantList")
    def subMenu(self, value):
        """The choices behind a folded entry ("menu:Add effect")."""
        return L.submenu(self._acts(), value)

    @Slot(str, result="QVariantList")
    def itemMenu(self, item_id):
        """Right-click on an item: an unselected one is selected alone first; a selected one keeps the selection."""
        if item_id not in self._picks.ids:
            self._pick([item_id])
        return self.actionMenu()

    @Slot(str, float, result="QVariantList")
    def atMenu(self, track_id, t):
        """Right-click on empty lane space (a track) or on the ruler (""): what can be done at that time."""
        return L.at_menu(self.doc, track_id, round(t, 4), bool(self._board["items"]))

    @Slot(str, result=bool)
    def applies(self, key):
        """Whether an action is valid for the selection right now (a key choosing between two, e.g. Ctrl+G)."""
        return any(a["key"] == key for a in self._acts())

    @Slot(str, result=bool)
    def keyAction(self, key):
        """A key's action: done when it applies, else nothing changes and the message line says why."""
        if any(a["key"] == key for a in self._acts()):
            return self.runAction(key)
        self.say(L.why(self.doc, self._picks.ids, key))
        return False

    @Slot(str, result=bool)
    def runAction(self, key):
        if key.startswith("at:"):
            return self._run_at(key.split(":"))
        a = next((x for x in self._acts() if x["key"] == key), None)
        if a is None:
            self._fail(f'Error: "{key}" does not apply to what is selected right now.')
            return False
        words = self.selectionWords
        if a["do"] == "inside":
            self._pick(C.inside(C.Facts(self.doc, [], rng=self._picks.range)))
            return True
        if a["do"] == "rename":
            return self.startRename(self._picks.ids[0])
        if a["do"] in ("copy", "cut"):
            self._board = clipboard.copy_items(self.doc, self._picks.ids)
            if a["do"] == "copy":
                self.say(f"Copied {words}")
                return True
            return self._act(C.delete(C.Facts(self.doc, self._picks.ids)), f"Cut {words}")
        if a["do"] == "paste":
            return self._paste(self._paste_track())
        if a["do"] == "library":                       # the playhead on the marker, the Library on designed sounds
            self.setTime(ST.start_of(self.doc.data, self.doc.item(self._picks.ids[0])))
            self.workspace.setLibrary(True)
            self.libraryWanted.emit("designed")
            return True
        if a["do"] == "clean":
            self.cleanWanted.emit()
            return True
        if a["amount"]:                                # asks a number first: the bar's popover answers runActionWith
            return self.runActionWith(key, a["amount"]["value"])
        done = self._act(a["calls"], f"{a['label']} · {words}" if words else a["label"], key in MAKES)
        if done and key == "sel:section" and self._picks.ids:
            self.clearRange()
            self.startRename(self._picks.ids[0])        # its name field opens in place
        return done

    @Slot(str, float, result=bool)
    def runActionWith(self, key, value):
        """An action that asked a number (the context bar's popover): Land a bar here with bar `value`."""
        if not self.applies(key):
            self.say(L.why(self.doc, self._picks.ids, key))
            return False
        calls = L.with_amount(self.doc, self._picks.ids, key, value, playhead=self._t, rng=self._picks.range)
        label = next(a["label"] for a in self._acts() if a["key"] == key)
        return self._act(calls, f"{label}: {value:g}")

    @Slot(bool, bool, bool, result=bool)
    def cleanSelected(self, voice, noise, echo):
        """The clean-up popover's Clean: the steps set on every selected clip (one change); the screen then starts
        the cleaned takes (mixer.cleaning.makeFor)."""
        args = {"isolate": bool(voice), "denoise": 0.6 if noise else 0, "dereverb": 0.6 if echo else 0}
        clips = [i for i in self._picks.ids if self.doc.item(i)["type"] == "clip"]
        return bool(clips) and self._act([{"op": "clip.set_one", "target": [c], "args": args} for c in clips],
                                         "Clean up " + self.selectionWords)

    def _run_at(self, parts):
        what = parts[1]
        if what == "paste":
            return self._paste(parts[2], float(parts[3]))
        if what == "all":
            return self._pick([b["id"] for r in self._view["rows"] if r["id"] == parts[2] for b in r["blocks"]]) or True
        t = float(parts[-1])
        if what == "marker":
            return self.markerAt(t)
        f = C.Facts(self.doc, [], rng=(timing.snap(t, self.doc.data, False), self._length()))
        return self._act(C.section(f), "Make a section")

    def _paste_track(self):
        picked = [self.doc.item(i) for i in self._picks.ids]
        if not picked:
            return ""
        order = [t["id"] for t in self.doc.data.get("tracks", [])]
        tracks = [i["id"] if i["type"] == "track" else self.doc.parent_of(i["id"])[0] for i in picked]
        tracks = [t for t in tracks if t in order]
        return min(tracks, key=order.index) if tracks else self._track

    def _paste(self, onto, at=None):
        def go():
            calls = clipboard.paste_calls(self.doc, self._board, self._t if at is None else at, onto)
            n = len(self._board["items"])
            return self._act(calls, f"Paste {n} item{'s' if n != 1 else ''}", True)
        return self._guard(go)

    def _act(self, calls, label, select_made=False):
        def go():
            change = self.doc.apply(calls, self.who, label=label)
            self._done(change, "")
            made = [i for i in ST.inserted(change) if self.doc.has(i)] if change and select_made else []
            if made:
                self._pick(made)
        return self._guard(go)

    # ---- Ctrl+K ------------------------------------------------------------------------------------------------
    def _commands(self):
        """Ctrl+K: the selection's actions first (the same list), then every other command."""
        words = self.selectionWords or "Song"
        mine = [{"key": a["key"], "label": a["label"], "hint": words + (f" · {a['shortcut']}" if a["shortcut"] else ""),
                 "calls": a["calls"]} for a in self._acts()]
        ops = {c["op"] for a in mine for c in a["calls"]}
        rest = commands.build(self.doc, self._picks.ids, self.label_of)
        return mine + [c for c in rest if not any(x["op"] in ops for x in c.get("calls", []))]

    @Slot(str, result=bool)
    def run(self, key):
        return self.runAction(key) if key.startswith(("sel:", "at:")) else super().run(key)
