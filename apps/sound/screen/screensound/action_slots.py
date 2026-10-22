"""Sound on the kit's one action list (shared/gui-kit/ACTIONS.md): one `SoundHub` (the kit's ActionHub) hosted as
`backend.actions` feeds the kit's ContextBar, ActionMenu, Ctrl+K and KeyMap from actions.LIST, so every door agrees
and a key whose action doesn't apply says why. Each action is one change; what a duplicate, split, paste or new
section made is selected afterwards. The hub also answers the shared keys that are not actions on the selection
(keys.ROUTES: play, the playhead, nudges, the loop, zoom …), so the window has ONE key map. A slot mix-in for
SoundBridge; the empty-space menus ("Paste here", "Add marker here") are Sound's own (`atMenu`, `runAt`).
"""
from __future__ import annotations


from PySide6.QtCore import Property, QObject, Signal, Slot
from rostrum_gui import commands
from rostrum_gui.action_hub import ActionHub
from rostrum_gui.action_views import commands as do_commands
from rostrum_sound.doc import select_time as ST

from . import action_calls as C
from . import voice_actions as V
from . import clipboard, timing
from .actions import LIST
from .keys import ROUTES, SKIP

MAKES = ("note.duplicate", "hit.duplicate", "clip.duplicate", "clip.split", "section.add", "track.duplicate",
         "section.duplicate")          # what these made is selected afterwards


class SoundHub(ActionHub):
    """The kit's hub, plus Sound's shared keys that are not actions (keys.ROUTES → bridge methods)."""

    def __init__(self, bridge, *a):
        super().__init__(*a, parent=bridge)
        self.bridge = bridge

    @Property("QVariantList", constant=True)
    def skip(self):
        """The jobs Main.qml / the kit's AppShell bind themselves (KeyMap.qml's `skip`)."""
        return SKIP

    @Slot(str)
    def key(self, job):
        if job in ROUTES:
            name, *args = ROUTES[job]
            getattr(self.bridge, name)(*args)
            self.refresh()
            return
        super().key(job)


class ActionSlots:
    libraryWanted = Signal(str)       # "Place a sound here": the Library opens on this chip
    cleanWanted = Signal()            # "Clean up…": the host opens the clean-up popover
    askWanted = Signal(str, str, float)   # an action asks one number first (Land a bar here: "Bar", the nearest)
    voiceWanted = Signal(str)         # a voice track's lines need their speech made (editor_side starts the job)

    def _refuse(self, line):
        """An action asked for that can't run now: said in the message line, and kept so a scripted step that asked
        for it fails (a refusal is not a success, AGENTS rule 6)."""
        self.__dict__["_refused"] = line
        self.say(line)

    def _make_actions(self):
        self._hub = SoundHub(self, LIST, self._facts, self._what, self._act_apply, self._act_do, self._refuse)
        for sig in (self.picksChanged, self.rangeChanged, self.docChanged, self.selectionChanged):
            sig.connect(self._hub.refresh)
        self.timeChanged.connect(lambda: None if self.playing else self._hub.refresh())   # Split at playhead
        self._hub.refresh()

    actions = Property(QObject, lambda self: self._hub, constant=True)

    def _facts(self):
        return C.Facts(self.doc, self._picks.ids, self._t, self._picks.range, bool(self._board["items"]), self._track,
                       self.__dict__.get("_range_newer", False))

    def _what(self, f) -> str:
        return self.selectionWords or ("Time range" if self._picks.range else "")

    # ---- running ----------------------------------------------------------------------------------------------
    def _act_apply(self, calls, label):
        words = self.selectionWords
        made = any(c["op"] in MAKES for c in calls)
        if self._act(calls, f"{label} · {words}" if words else label, made) and any(c["op"] == "section.add" for c in calls):
            self.clearRange()
            if self._picks.ids:
                self.startRename(self._picks.ids[0])            # a new section's name field opens in place

    def _act_do(self, name, entry):
        """Sound's actions that are not operations by themselves."""
        ids, words = self._picks.ids, self.selectionWords
        if name == "inside":                                    # of the time range, or of the selected section
            sec = self.doc.item(ids[0]) if ids else None
            rng = (ST.start_of(self.doc.data, sec), ST.start_of(self.doc.data, {**sec, "at": sec["end"]})) if sec \
                else self._picks.range
            self._pick(C.inside(C.Facts(self.doc, [], rng=rng)))
        elif name == "rename":
            self.startRename(ids[0])
        elif name in ("copy", "cut"):
            self._board = clipboard.copy_items(self.doc, ids)
            if name == "copy":
                self.say(f"Copied {words}")
            else:
                self._act(C.delete(C.Facts(self.doc, ids)), f"Cut {words}")
        elif name == "paste":
            self._paste(self._paste_track())
        elif name == "library":                                 # the playhead on the marker, the Library on designed
            self.setTime(ST.start_of(self.doc.data, self.doc.item(ids[0])))
            self.workspace.setLibrary(True)
            self.libraryWanted.emit("designed")
        elif name == "swap":                                    # the Library opens; with a clip selected its rows say Swap
            self.workspace.setLibrary(True)
        elif name == "clean":
            self.cleanWanted.emit()
        elif name == "speak":                                   # Speak again: a new take of each line, made at once
            if self._act(V.speak_calls(self._facts()), f"Speak again · {words}"):
                for track in dict.fromkeys(self.doc.parent_of(i)[0] for i in ids):
                    self.voiceWanted.emit(track)
        elif name == "addline":                                 # Add line at playhead: the box opens in the lane
            self.side.startTyping(ids[0], self._t)
        elif name == "fit":
            self.askWanted.emit("fit_bar", "Bar", float(C.bar_near(self._facts())))
        else:
            raise ValueError(f'action {entry["id"]}: RostrumSound has no "{name}" action')

    @Slot(str, float, result=bool)
    def landBar(self, _key, bar):
        """The popover's answer for Land a bar here: `tempo.fit_bar` with that bar (one step)."""
        f = self._facts()
        if not (f.one == "marker" and f.count == 1):
            self._refuse("Land a bar needs one marker selected (placed in seconds)")
            return False
        return self._act(C.fit_bar(f, int(bar)), f"Land bar {int(bar)} on {f.items[0].get('name')}")

    @Slot(bool, bool, bool, result=bool)
    def cleanSelected(self, voice, noise, echo):
        """The clean-up popover's Clean: the steps set on every selected clip (one change); the screen then starts
        the cleaned takes (mixer.cleaning.makeFor)."""
        args = {"isolate": bool(voice), "denoise": 0.6 if noise else 0, "dereverb": 0.6 if echo else 0}
        clips = [i for i in self._picks.ids if self.doc.item(i)["type"] == "clip"]
        return bool(clips) and self._act([{"op": "clip.set_one", "target": [c], "args": args} for c in clips],
                                         "Clean up " + self.selectionWords)

    # ---- menus ------------------------------------------------------------------------------------------------
    @Slot(str, result="QVariantList")
    def itemMenu(self, item_id):
        """Right-click on an item: an unselected one is selected alone first; then the kit's menu for the selection."""
        if item_id not in self._picks.ids:
            self._pick([item_id])
        self._hub.refresh()
        return self._hub.menu()

    @Slot(str, float, result="QVariantList")
    def atMenu(self, track_id, t):
        """Right-click on empty lane space (a track) or on the ruler (""): what can be done at that time."""
        t, out = round(t, 4), []
        if track_id and self._board["items"]:
            out.append({"value": f"at:paste:{track_id}:{t}", "label": "Paste here", "keys": "Ctrl+V", "group": "here"})
        out.append({"value": f"at:marker:{t}", "label": "Add marker here", "keys": "M", "group": "here"})
        if track_id:
            out.append({"value": f"at:all:{track_id}", "label": "Select all on this track", "keys": "", "group": "select"})
        else:
            out.append({"value": f"at:section:{t}", "label": "Make a section from here", "keys": "", "group": "here"})
        return out

    @Slot(str, result=bool)
    def runAt(self, value):
        """An empty-space menu entry ("at:<what>:…"): paste here, a marker, select all on a track, a section."""
        parts = value.split(":")
        what = parts[1]
        if what == "paste":
            return self._paste(parts[2], float(parts[3]))
        if what == "all":
            return self._pick([b["id"] for r in self._view["rows"] if r["id"] == parts[2] for b in r["blocks"]]) or True
        t = float(parts[-1])
        if what == "marker":
            return self.markerAt(t)
        f = C.Facts(self.doc, [], rng=(timing.snap(t, self.doc.data, False, self._grid_now), self._length()))
        return self._act(C.section(f), "Make a section")

    @Slot(str)
    def menuPick(self, value):
        """Any ActionMenu's choice: an empty-space entry, else the action list's."""
        self.runAt(value) if value.startswith("at:") else self._hub.run(value)

    # ---- paste and apply --------------------------------------------------------------------------------------
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

    # ---- Ctrl+K and scripts -------------------------------------------------------------------------------------
    def _commands(self):
        """Ctrl+K: the action list first (with keys), then the kit's commands it doesn't repeat."""
        f = self._facts()
        mine = [{**c, "do": lambda k=c["key"]: self._hub.run(k)} if "do" in c else c
                for c in do_commands(LIST.available(f), self._what(f))]
        ops = {x["op"] for c in mine for x in c.get("calls", [])}
        rest = commands.build(self.doc, self._picks.ids, self.label_of)
        return mine + [c for c in rest if not any(x["op"] in ops for x in c.get("calls", []))]

    @Slot(str, result="QVariantList")
    def commands(self, query):
        return [{k: c.get(k, "") for k in ("key", "label", "hint", "keys")} for c in commands.search(self._commands(), query)]

    @Slot(str, result=bool)
    def run(self, key):
        """Ctrl+K, a menu or a script: an action of the list through the hub (one change; not valid now: it says
        why), an empty-space entry, else the kit's."""
        if key.startswith("at:"):
            return self.runAt(key)
        if not any(a.id == key for a in LIST.actions):
            return super().run(key)
        ok = any(e["id"] == key for e in LIST.available(self._facts()))
        self._hub.run(key)
        return ok
