"""Sound on the kit's one action list (shared/gui-kit/ACTIONS.md): one `SoundHub` (the kit's ActionHub) hosted as
`backend.actions` feeds the settings panel's actions, the kit's short ActionMenu, Ctrl+K and KeyMap from actions.LIST, so every door agrees
and a key whose action doesn't apply says why. Each action is one change; what a duplicate, split, paste or new
section made is selected afterwards. The hub also answers the shared keys that are not actions on the selection
(keys.ROUTES: play, the playhead, nudges, the loop, zoom …), so the window has ONE key map. A slot mix-in for
SoundBridge; the empty-space menus ("Paste here", "Add marker here") are Sound's own (`atMenu`, `runAt`).
"""
from __future__ import annotations


from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot
from rostrum_gui import commands
from rostrum_gui.action_hub import ActionHub
from rostrum_gui.action_views import commands as do_commands
from rostrum_gui.edits import Drag
from rostrum_sound.doc import musical
from rostrum_sound.doc import select_time as ST

from rostrum_sound import main_mix

from . import action_calls as C
from . import amount_actions as A
from . import voice_actions as V
from . import block_menu, clipboard, inspect, palette, timing
from .actions import ACTS_ON, LIST, RANGE

AMOUNTS = {a.id for a in LIST.actions if a.amounts}      # Ctrl+K opens their popover ("Quantise…")
ASKED_OPS = {"note.strum", "note.arpeggiate"}     # what Strum… / Arpeggio… run: their calls wait for the popover, so the
# kit's own "Strum" / "Arpeggiate" rows are left out by name (each was a whole plan of the selection on every Ctrl+K)
from .keys import ROUTES, SKIP
from .select_slots import SETTLE_MS

# Ctrl+K lists only the named things you would go to, in our words (never a single note, hit or effect)
KINDS = {"track": "Track", "bus": "Group", "marker": "Marker", "section": "Section", "clip": "Clip"}

MAKES = ("note.duplicate", "hit.duplicate", "clip.duplicate", "clip.split", "section.add", "track.duplicate",
         "section.duplicate")          # what these made is selected afterwards


class SoundHub(ActionHub):
    """The kit's hub, plus Sound's shared keys that are not actions (keys.ROUTES → bridge methods)."""

    def __init__(self, bridge, *a, **kw):
        super().__init__(*a, parent=bridge, **kw)
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
            if not self.bridge.__dict__.get("_unsettled"):     # (a pick whose panel follows: its actions come with it)
                self.refresh_later()
            return
        super().key(job)

    def _go(self, entry):
        """Which action runs, so its step and message name what it acts on (`_subject`)."""
        self.bridge.__dict__["_acting"] = entry["id"]
        try:
            super()._go(entry)
        finally:
            self.bridge.__dict__["_acting"] = ""


class ActionSlots:
    files = None                      # the kit's ProjectFiles (main.py sets it): the ≡ menu's rows are Ctrl+K's too
    jobWanted = Signal(str)           # Ctrl+K named a job only the window can run (Preferences, Export, files ...): Main.qml runs it
    libraryWanted = Signal(str)       # "Place a sound": the Library opens on this chip
    cleanWanted = Signal()            # "Clean up…": the host opens the Cleanup group (its three fields, once)
    mainMixChanged = Signal()         # the main-mix mark moved (the Song panel's mark and button re-read)
    voiceWanted = Signal(str)         # a voice track's lines need their speech made (editor_side starts the job)

    def _refuse(self, line):
        """An action asked for that can't run now: said in the message line, and kept so a scripted step that asked
        for it fails (a refusal is not a success, AGENTS rule 6)."""
        self.__dict__["_refused"] = line
        self.say(line)

    def _make_actions(self):
        self._hub = SoundHub(self, LIST, self._facts, self._what, self._act_apply, self._act_do, self._refuse,
                             drag_fn=lambda label: Drag(self.doc, self.who, label), kept_fn=self._amounts_kept,
                             subject_fn=lambda key, f: self._subject(key))
        for sig in (self.picksChanged, self.docChanged):       # picks follow the selected items
            sig.connect(self._refresh_actions)
        later = QTimer(self, singleShot=True, interval=SETTLE_MS, timeout=self._refresh_actions)
        self.rangeChanged.connect(later.start)           # a range drawn on the ruler: its band at once, its actions after the frame
        self.timeChanged.connect(lambda: None if self.playing else self._refresh_actions())   # Split at playhead
        self._hub.amounts.changed.connect(self._fill_over)       # Fill row… is offered only while its popover is open
        self._hub.refresh()

    def _refresh_actions(self):
        """The actions follow the selection the panel shows: while a press or a drag has picked and not settled yet
        (select_slots._pick `later`), they wait with the panel and come once with it (making them costs the press
        ~35 ms of redrawn rows). They come the frame after the change or the pick (the whole song selected: ~15-25 ms
        of rules, never inside the key's own frame); a key pressed meanwhile reads the selection's rules now
        (ActionHub.key: `available` with `among`), so it never runs a stale list's action."""
        if not self.__dict__.get("_unsettled") and "_hub" in self.__dict__:     # (a pick while the screen is made)
            self._hub.refresh_later()

    actions = Property(QObject, lambda self: self._hub, constant=True)

    def _facts(self):
        return C.Facts(self.doc, self._picks.ids, self._t, self._picks.range, bool(self._board["items"]), self._track,
                       self.__dict__.get("_range_newer", False), self.__dict__.get("_fill"))

    def _what(self, f) -> str:
        return self.selectionWords or ("Time range" if self._picks.range else "")

    def _subject(self, key) -> str:
        """What action `key` acts on, in words: a time range action names the range ("time range 5.1–9.1"), even with
        items selected too (critic r4: "Duplicate · 26 drum hits" duplicated the whole range); an action on some kinds
        the part it takes ("Quantise · 178 notes and 202 drum hits" on Select all); the rest the selection."""
        rng = self._picks.range
        if key == "repeat_range" and rng:
            return A.range_words(self._facts())
        if key == "fill_row" and self.__dict__.get("_fill"):          # "Fill row · Hat, bar 5"
            f = self._fill
            return f'{inspect.drum_words(f["drum"]).lower()}, {self._words_of(f["from"], f["to"])}'
        if key == "fit_bar" and len(self._picks.ids) == 1:          # "Start a bar here · marker logo"
            return f'marker {self.doc.item(self._picks.ids[0]).get("name") or self._picks.ids[0]}'
        if key in RANGE and rng:
            at = [".".join(musical.position(t, self.doc.data).split(".")[:2]) for t in rng]
            return f"time range {at[0]}–{at[1]}"
        if key in ACTS_ON:
            return C.Facts(self.doc, self._picks.ids).words(ACTS_ON[key]) or self.selectionWords
        return self.selectionWords

    # ---- running ----------------------------------------------------------------------------------------------
    def _act_apply(self, calls, label):
        words = self._subject(self.__dict__.get("_acting", ""))
        made = any(c["op"] in MAKES for c in calls) and not self.__dict__.get("_acting", "").startswith("repeat")
        if self._act(calls, f"{label} · {words}" if words else label, made) and any(c["op"] == "section.add" for c in calls):
            self.clearRange()
            if self._picks.ids:
                self.startRename(self._picks.ids[0])            # a new section's name field opens in place

    def _amounts_kept(self, change, label):
        """The amounts popover kept its session (one change, named with its amounts): said in the message line."""
        self._done(change, f"{label}: already so, nothing changed", said=True)

    def _act_do(self, name, entry):
        """Sound's actions that are not operations by themselves."""
        ids, words = self._picks.ids, self.selectionWords
        if name in ("inside", "inside_section"):                # of the time range, or of the selected section
            if name == "inside_section":                        # each action names its subject, never guessed from the
                sec = self.doc.item(ids[0])                     # selection (a picked track is not a section, critic r4 M2)
                rng = (ST.start_of(self.doc.data, sec), ST.start_of(self.doc.data, {**sec, "at": sec["end"]}))
            else:
                rng = self._picks.range
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
        elif name == "library":                                 # the playhead on the marker, the Library on My sounds
            self.setTime(ST.start_of(self.doc.data, self.doc.item(ids[0])))
            self.workspace.setLibrary(True)
            self.libraryWanted.emit("mine")
        elif name == "swap":                                    # the Library opens on My sounds; ↑ / ↓ step (swap_trial.py)
            self.workspace.setLibrary(True)
            self.libraryWanted.emit("mine")
        elif name == "clean":
            self.askClean()
        elif name == "speak":                                   # Speak again: a new take of each line, made at once
            if self._act(V.speak_calls(self._facts()), f"Speak again · {words}"):
                for track in dict.fromkeys(self.doc.parent_of(i)[0] for i in ids):
                    self.voiceWanted.emit(track)
        elif name == "addline":                                 # Add line at playhead: the Lines box takes the keys
            self.workspace.setDock("editor")
            self.side.linesWanted.emit()
        elif name == "hear_back":                               # H let go: the other side back (the press flipped it)
            self._hub.run("before_after")
        elif name == "mainmix":                                 # a mark on the project, not a song edit: no undo step
            self.makeMainMix()
        else:
            raise ValueError(f'action {entry["id"]}: RostrumSound has no "{name}" action')

    @Slot(result=bool)
    def makeMainMix(self):
        """Make this song the project's main mix (main_mix.make_main, the run_set_main_mix tool's one door)."""
        def go():
            r = main_mix.make_main(self.doc.folder, self.doc.item_id)
            self.say(f'"{r["name"]}" is now the main mix')
            self.mainMixChanged.emit()
            self._hub.refresh()
            return True
        return self._guard(go)

    @Slot(result="QVariantMap")
    def cleanState(self):
        """Which presets are on for the first selected clip: {voice, noise, echo}."""
        clip = next((self.doc.item(i) for i in self._picks.ids if self.doc.item(i)["type"] == "clip"), {})
        return {"voice": bool(clip.get("isolate")), "noise": bool(clip.get("denoise")), "echo": bool(clip.get("dereverb"))}

    @Slot(bool, bool, bool, result=bool)
    def cleanSelected(self, voice, noise, echo):
        """A Cleanup preset: the steps set on every selected clip (one change); the screen then starts
        the cleaned takes (mixer.cleaning.makeFor)."""
        args = {"isolate": bool(voice), "denoise": 0.6 if noise else 0, "dereverb": 0.6 if echo else 0}
        clips = [i for i in self._picks.ids if self.doc.item(i)["type"] == "clip"]
        return bool(clips) and self._act([{"op": "clip.set_one", "target": [c], "args": args} for c in clips],
                                         "Clean up " + self.selectionWords)

    # ---- menus ------------------------------------------------------------------------------------------------
    @Slot(str, result="QVariantList")
    def itemMenu(self, item_id):
        """A menu opened without a pointer (a header, the selection's bar): as blockMenu, at the playhead."""
        return self.blockMenu(item_id, self._t)

    @Slot(str, float, result="QVariantList")
    def blockMenu(self, item_id, t):
        """Right-click on an item at time `t`: an unselected one is selected alone first; then the kit's menu for the
        selection, and for an audio clip its own rows at the pointer (block_menu)."""
        if item_id not in self._picks.ids:
            self._pick([item_id])
        self._hub.refresh()
        out = self._hub.menu()
        valid = LIST.available(self._facts())
        swap = any(e["id"] == "swap" for e in valid)
        return out + block_menu.selection_entries(valid) + block_menu.clip_entries(self.doc, item_id, t, swap)

    @Slot(float, float, float, result="QVariantList")
    def rollMenu(self, t, row, px):
        """Right-click on empty space in the Editor's roll (`row`: the key, or the drum row; `px`: one screen pixel
        in seconds): what can be done there (block_menu.roll_entries)."""
        roll = self._view["roll"]
        key = timing.name(int(round(row))) if roll.get("kind") == "notes" else ""
        return block_menu.roll_entries(roll.get("kind"), self._track, round(t, 4), int(round(row)), px,
                                       bool(self._track and self._board["items"]), key)

    @Slot(str, float, result="QVariantList")
    @Slot(str, float, float, result="QVariantList")
    def atMenu(self, track_id, t, px=0.0):
        """Right-click on empty lane space (a track) or on the ruler (""): what can be done at that time (`px`: one
        screen pixel in seconds, so a section starts on a line within a few px, as a range drawn on the ruler does)."""
        t, out = round(t, 4), []
        if track_id:
            out.append({"value": "at:addtrack:0", "label": "Add track…", "keys": "Ctrl+L", "group": "here"})
        if track_id and self._board["items"]:
            out.append({"value": f"at:paste:{track_id}:{t}:{px:.6g}", "label": "Paste here", "keys": "Ctrl+V", "group": "here"})
        out.append({"value": f"at:marker:{t}", "label": "Add marker here", "keys": "M", "group": "here"})
        if track_id:
            out.append({"value": f"at:all:{track_id}", "label": "Select all on this track", "keys": "", "group": "select"})
        else:
            out.append({"value": f"at:section:{t}:{px:.6g}", "label": "Make a section from here", "keys": "", "group": "here"})
            out.append({"value": "at:seconds:0", "label": "Hide seconds" if self.workspace.seconds else "Show seconds",
                        "keys": "", "group": "view"})
        return out

    @Slot(str, result=bool)
    def runAt(self, value):
        """An empty-space menu entry ("at:<what>:…"): paste here, a marker, select all on a track, a section."""
        parts = value.split(":")
        what = parts[1]
        if what == "drum":                                     # a drum row's menu (drum_menu.py, drum_step_slots.py)
            return self.runDrum(parts[2:])
        if what == "paste":                                    # in the grid cell under the pointer, as a click that adds a note
            px = float(parts[4]) if len(parts) > 4 else 0.0
            return self._paste(parts[2], timing.snap(float(parts[3]), self.doc.data, False, self._grid_now, "cell", px))
        if what == "rolladd":
            t, row, px = float(parts[2]), float(parts[3]), float(parts[4])
            return bool(self.addHit(t, row, px)) if self._view["roll"].get("kind") == "drums" else self.addNote(t, int(row), px) or True
        if what == "allkey":
            key = int(parts[3])
            return self._pick([b["id"] for b in self._view["roll"].get("blocks", []) if b["type"] == "note" and key in b["keys"]]) or True
        if what == "addtrack":
            self.workspace.setLibrary(True)
            return True
        if what in ("split", "fadein", "fadeout"):
            calls, label = block_menu.calls_for(what, parts[2], float(parts[3]))
            return self._act(calls, label, what == "split")
        if what == "all":
            return self._pick([b["id"] for r in self._view["rows"] if r["id"] == parts[2] for b in r["blocks"]]) or True
        if what == "point":                                    # a lane point's menu (lane_slots.pointMenu): Delete point
            return self._remove_point() or True
        if what == "seconds":
            self.workspace.toggleSeconds()
            return True
        if what == "marker":                                   # on the grid line nearest the click (Snap off: where it was)
            return self.markerAt(timing.snap(float(parts[-1]), self.doc.data, False, self._grid_now))
        t = float(parts[2])                                    # a section: starts as a drawn range's start does
        f = C.Facts(self.doc, [], rng=(timing.snap(t, self.doc.data, self.workspace.seconds, self._grid_now),
                                       self._length()))
        return self._act(C.section(f), "Make a section")

    @Slot(str)
    def menuPick(self, value):
        """Any ActionMenu's choice: an empty-space entry, else the action list's."""
        self.runAt(value) if value.startswith("at:") else self._hub.choose(value)

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
            self._done(change, f"{label}: already so, nothing changed")    # a key never does nothing silently
            made = [i for i in ST.inserted(change) if self.doc.has(i)] if change and select_made else []
            made = [i for i in made if self.doc.item(i)["type"] == "section"] or made   # a new section stands for what
            # it holds: it alone is selected, so its own actions show (Duplicate section, Ctrl+D again)
            if made:                            # the outlines with the change, the panel once both are drawn
                self._pick(made, later=True)
                self._settle()
        return self._guard(go)

    # ---- Ctrl+K and scripts -------------------------------------------------------------------------------------
    def _commands(self):
        """Ctrl+K: the action list first (with keys), the selected item's settings that need a value ("Edit Velocity":
        the field in the settings panel) and its track's lanes, then the kit's commands it doesn't repeat."""
        f = self._facts()
        mine = [{**c, "do": lambda k=c["key"]: self._hub.choose(k)} if "do" in c or c["key"] in AMOUNTS else c
                for c in do_commands(LIST.available(f), self._what(f))]
        mine = [{**c, "hint": self._subject(c["key"]) or c["hint"], "own": True} for c in mine]
        ops = {x["op"] for c in mine for x in c.get("calls", [])} | ASKED_OPS
        rest = commands.build(self.doc, self._picks.ids, self.label_of, kind_of=lambda it: KINDS.get(it["type"], ""),
                              where=self._what(f), skip=ops)
        picked = self._picks.ids
        own = commands.field_rows(self.doc, picked[0], self.label_of) if len(picked) == 1 else []     # "velocity", "volume"
        own += palette.lane_rows(self.doc, self._paste_track(), self.openLane, self.openPlayLane)      # "automation", "sustain"
        return (mine + own + [c for c in rest if not any(x["op"] in ops for x in c.get("calls", []))
                              and ("select" not in c or self.doc.item(c["select"])["type"] in KINDS)]
                + (self.files.commands() if self.files else []) + palette.rows({LIST.job_of(a) for a in LIST.actions},
                                                                              {"selected": bool(self._picks.ids), "problems": bool(self.problems.rows)}))

    @Slot(str, result="QVariantList")
    def commands(self, query):
        return [{k: c.get(k, "") for k in ("key", "label", "hint", "keys")} for c in commands.search(self._commands(), query)]

    @Slot(str, result=bool)
    def run(self, key):
        """Ctrl+K, a menu or a script: an action of the list through the hub (one change; not valid now: it says
        why), an empty-space entry, else the kit's."""
        if key.startswith("at:"):
            return self.runAt(key)
        if key.startswith("file:") and self.files:        # the ≡ menu's rows (New, Open, Open recent, Show folder, Start screen ...)
            self.files.pickLater(key)
            return True
        if key.startswith("job:"):                       # a key-map job named in Ctrl+K (palette.py)
            job = key[4:]
            self._hub.key(job) if job in ROUTES else self.jobWanted.emit(job)
            return True
        if not any(a.id == key for a in LIST.actions):
            return super().run(key)
        ok = any(e["id"] == key for e in LIST.available(self._facts(), amounts=self._hub.amounts.memory))
        self._hub.choose(key)
        return ok
