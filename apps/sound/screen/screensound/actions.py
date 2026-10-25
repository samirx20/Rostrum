"""Sound's entries in the ONE action list (select first, then act: shared/gui-kit/INTERACTION.md §1.2; Sound's table:
apps/sound/DESIGN.md §3.0 point 3). Data only, one entry per action, shaped like the kit's coming action list so the
entries move there as they are:

    key (the action's id), label (words, or a function of the selection), shortcut, valid_when(Facts),
    importance ("primary" = a button in the settings panel's actions, "secondary" = its More menu), promoted_when(Facts)
    (a selection that makes a secondary one primary), calls(Facts) -> operation calls, group (a divider in menus;
    "edit" = the edit block: keys and the right-click menu, never the panel), menu (the titled row it sits in,
    e.g. "Transpose"), on (the kinds it acts on: in a mixed selection, e.g. Select all, it acts on those items and
    names them, `ACTS_ON`; it is absent only when none are selected), panel (False: keys and Ctrl+K only), do ("copy" / "cut" / "paste" / "inside" / "rename" / "library" / "clean": not a document
    change by itself), needs (what the message line says when its key is pressed while it doesn't apply), amounts
    (its operation's parameter names, or a Param of the screen's own: the kit's amounts popover, rostrum_gui/amounts.py;
    then calls(Facts, amounts) and fit(Facts, amounts) gives the screen's say on each row: amount_actions.py), asks
    (every door opens that popover first: Repeat…; else its button runs at once with the last amounts and ▾ opens it).

`LIST` is them on the kit's one action list (rostrum_gui.actions, through action_adapt.from_dicts; keys from keys.py):
the settings panel's actions (kit ActionsSection), the kit's ONE short right-click menu (rostrum_gui.actions.SHORT_MENU,
everywhere the same), Ctrl+K (everything) and the KeyMap read it through the hub (action_slots.py). The short menu's
meanings for sound: Group = send tracks to a new group, or layer clips as one sound (Ctrl+G); Bring forward / Send
backward = move a track up / down (Ctrl+] / Ctrl+[); Lock; Rename. Hide has no meaning here (Mute is in the panel). No Qt.
"""
from __future__ import annotations

from dataclasses import replace

from rostrum_sound import main_mix
from rostrum_sound.doc import select_time as ST
from rostrum_sound.doc.effects import TYPES as EFFECT_TYPES, WORDS as EFFECT_WORDS

from rostrum_gui.action_adapt import from_dicts
from rostrum_gui.actions import SHORT_MENU, ActionList

from . import action_calls as C
from . import amount_actions as A
from . import key_lock
from . import voice_actions as V
from .action_calls import REMOVABLE, TIMED
from .keys import KEYMAP

EFFECTS = [t for t in EFFECT_TYPES if t != "plugin"]      # the words are effects.WORDS (one place)
CLIPS = {"note", "hit", "clip", "line"}


def act(key, label, valid_when, calls=None, shortcut="", importance="secondary", group="", menu="", do="",
        promoted_when=None, needs="", min_targets=0, release="", panel=True, on=(), amounts=(), asks=False, fit=None):
    return {"key": key, "label": label, "shortcut": shortcut, "valid_when": valid_when, "importance": importance,
            "promoted_when": promoted_when, "calls": calls, "group": group, "menu": menu, "do": do, "needs": needs,
            "min_targets": min_targets, "release": release, "panel": panel, "on": on, "amounts": amounts, "asks": asks,
            "fit": fit}


def on(kinds, op, **args):
    """(valid_when, calls) of an action on the selected items of `kinds`, whatever else is selected: one call per
    kind, e.g. Quantise on Select all = note.quantize on its notes + hit.quantize on its hits."""
    return (lambda f: bool(f.by_kind(kinds)),
            lambda f: [C.call(f"{k}.{op}", ids, **args) for k, ids in f.by_kind(kinds).items()])


def _inside_clip(f):
    return f.one == "clip" and any(ST.start_of(f.doc.data, c) + 1e-6 < f.playhead < ST.end_of(f.doc.data, c) - 1e-6
                                   for c in f.items)


def _can_make_main(f):
    """Nothing selected, the song is in a project and is not its main mix yet (rule of individuality: else absent)."""
    return f.count == 0 and bool(f.doc.folder) and not main_mix.is_main(f.doc.folder, f.doc.item_id)


def _outside_key(f):
    """The selection holds a note with a tone outside the key playing at its start (Fit to key leads then)."""
    return any(key_lock.outside(f.doc.data, n, ST.start_of(f.doc.data, n)) for n in f.items if n["type"] == "note")


_STEPS = (("up", 1, "Up a half step", "Up"), ("down", -1, "Down a half step", "Down"),
          ("up12", 12, "Up an octave", "Shift+Up"), ("down12", -12, "Down an octave", "Shift+Down"))
TRACK, CLIP = (lambda f: f.one == "track"), (lambda f: f.one == "clip")
NOTE_HIT, NOTE = ("note", "hit"), ("note",)
MARKER = lambda f: f.one == "marker" and f.count == 1 and isinstance(f.items[0].get("at"), (int, float))  # noqa: E731
NAMED = ("track", "bus", "marker", "section")

ACTIONS = [
    # tracks
    act("group", "Group", lambda f: TRACK(f) and not C.is_whole_group(f), lambda f: [C.call("bus.from_tracks", f.ids)],
        "Ctrl+G", "primary", "make", needs="Group needs two or more tracks selected", min_targets=2),
    act("ungroup", "Ungroup", lambda f: bool(C.group_buses(f)) and C.tries(f, [C.call("bus.ungroup", C.group_buses(f))]),
        lambda f: [C.call("bus.ungroup", C.group_buses(f))], "Ctrl+Shift+G", "primary", "make"),
    act("mute", C.flip("mute", "Mute", "Unmute"), TRACK, C.toggle_all("mute"), "Shift+M", group="track",
        needs="Mute needs tracks selected"),
    act("solo", C.flip("solo", "Solo", "Unsolo"), TRACK, C.toggle_all("solo"), "Shift+S", group="track",
        needs="Solo needs tracks selected"),
    *[act(f"effect_{e}", f"Add {EFFECT_WORDS[e]}", lambda f: f.one in ("track", "clip"),
          lambda f, e=e: [C.call("effect.add", f.ids, effect=e)], group="effect", menu="Add effect")
      for e in EFFECTS],
    act("move_up", "Move up", lambda f: TRACK(f) and C.can_move(f, -1), lambda f: [C.call("track.move", f.ids, by=-1)],
        "Ctrl+]", group="order", needs="Move up needs tracks selected that aren't already at the top"),
    act("move_down", "Move down", lambda f: TRACK(f) and C.can_move(f, 1), lambda f: [C.call("track.move", f.ids, by=1)],
        "Ctrl+[", group="order", needs="Move down needs tracks selected that aren't already at the bottom"),
    act("lock", "Lock", lambda f: TRACK(f) and not all(it.get("locked") for it in f.items),
        lambda f: [C.call("track.lock", [it["id"] for it in f.items if not it.get("locked")])], "Ctrl+Shift+L",
        group="order", needs="Lock needs tracks selected"),
    act("unlock", "Unlock", lambda f: TRACK(f) and any(it.get("locked") for it in f.items),
        lambda f: [C.call("track.unlock", [it["id"] for it in f.items if it.get("locked")])], "Ctrl+Shift+L",
        group="order"),
    # notes and drum hits
    act("quantize", "Quantise", *A.on(NOTE_HIT, "quantize"), "Q", "primary", "time",
        needs="Quantise needs notes or drum hits selected", on=NOTE_HIT, amounts=("grid", "strength", "swing", "ends"),
        fit=A.quantize_fit),
    *[act(f"transpose_{k}", label, *on(NOTE, "transpose", semitones=n), keys, "primary", "pitch", "Transpose", on=NOTE)
      for k, n, label, keys in _STEPS],
    act("transpose_by", "By…", lambda f: bool(f.by_kind(NOTE)), A.transpose_calls, importance="primary", group="pitch",
        menu="Transpose", on=NOTE, amounts=("semitones", "steps", A.ALONG), asks=True, fit=A.transpose_fit),
    act("fit_key", "Fit to key", lambda f: bool(f.by_kind(NOTE)) and key_lock.has_key(f.doc.data), *A.on(NOTE, "fit_key")[1:],
        group="pitch", on=NOTE, promoted_when=_outside_key,         # first only while the selection holds notes outside the key
        needs="Fit to key needs notes selected, in a song with a key"),
    act("humanize", "Humanise", *A.on(NOTE_HIT, "humanize"), importance="primary", group="time", on=NOTE_HIT,
        amounts=("timing", "velocity", "length", "seed")),
    act("repeat", "Repeat…", A.repeat_valid, A.repeat_calls, "Ctrl+R", group="time", asks=True,
        amounts=("times", A.UNTIL), fit=A.repeat_fit,
        needs="Repeat needs notes, drum hits or clips selected, or a time range with something inside"),
    # a drum row's Fill row… (its menu sets the target; keys and Ctrl+K only while it is open: drum_step_slots.py)
    act("fill_row", "Fill row…", lambda f: f.fill is not None, A.fill_calls, group="fill", asks=True, panel=False,
        amounts=("every", "offset", "vel", "accentEvery"), fit=A.fill_fit),
    # markers (the song's own, placed in seconds)
    act("place_sound", "Put a sound here", lambda f: f.one == "marker" and f.count == 1, importance="primary",
        group="marker", do="library"),
    act("fit_bar", "Start a bar here…", MARKER, A.fit_bar_calls, importance="primary", group="marker", asks=True,
        amounts=("bar",), fit=A.fit_bar_fit,
        needs="Start a bar here needs one marker selected (placed in seconds)"),       # asks the bar first (the popover)
    act("speak_again", "Speak again", lambda f: f.one == "line", shortcut="T", importance="primary", group="line",
        do="speak", needs="Speak again needs voice lines selected"),
    act("take_prev", "Earlier take", V.take_valid(-1), V.take_calls(-1), group="line"),
    act("take_next", "Later take", V.take_valid(1), V.take_calls(1), group="line"),
    act("add_line", "Type a line", V.voice_track, group="line", do="addline",
        panel=False),                                   # the Lines panel has the field: keys and Ctrl+K only
    # the song itself (nothing selected): absent once it is the main mix
    act("main_mix", "Make this the main mix", _can_make_main, importance="secondary", group="song", do="mainmix",
        panel=False),                                   # the Song panel has its own button for it
    # clips
    act("clean", "Clean up…", CLIP, importance="primary", group="clip", do="clean",
        panel=False),                                   # the panel's Cleanup group is the one place (its fields are right there); keys and Ctrl+K jump to it
    act("before_after", V.ba_label, V.ba_valid, V.ba_calls, shortcut="H", group="clip",
        needs="Before / After needs clips with a clean-up set", release="hear_back"),   # hold H: the other side, let go: back
    act("swap", "Swap…", lambda f: f.one == "clip" and f.count == 1, shortcut="S", importance="primary", group="clip",
        do="swap", needs="Swap needs one clip selected"),            # opens the Library; its Swap button is clip.swap
    act("normalize", "Even out level", CLIP, lambda f: [C.call("clip.normalize", f.ids, by="loudness")],
        importance="primary", group="clip"),
    act("split", "Split at playhead", _inside_clip, lambda f: [C.call("clip.split", f.ids, at=round(f.playhead, 4))],
        "Ctrl+T", "primary", "clip", needs="Split needs clips selected with the playhead inside one"),
    act("join", "Join", lambda f: C.clips_one_track(f) and C.tries(f, [C.call("clip.join", f.ids)]),
        lambda f: [C.call("clip.join", f.ids)], "Ctrl+J", "primary", "clip",
        needs="Join needs two or more clips that play one file back to back on one track"),
    act("crossfade", "Crossfade", lambda f: C.clips_one_track(f) and C.tries(f, [C.call("clip.crossfade", f.ids)]),
        lambda f: [C.call("clip.crossfade", f.ids)], importance="primary", group="clip"),
    act("layer", "Layer together", CLIP, lambda f: [C.call("clip.set", f.ids, group=C.layer_name(f))], "Ctrl+G",
        group="clip", needs="Layer together needs two or more clips selected", min_targets=2),
    act("stems", "Split into parts (stems)", lambda f: CLIP(f) and f.count == 1,
        lambda f: [C.call("clip.split_stems", f.ids)], group="clip"),
    act("section_duplicate", "Duplicate section", lambda f: f.one == "section", lambda f: [C.call("section.duplicate", f.ids)],
        importance="primary", group="section"),
    act("section_inside", "Select inside", lambda f: f.one == "section" and f.count == 1, importance="primary",
        group="section", do="inside_section"),
    # a time range (a section is made from the range whatever else is selected; the rest when the range is newer)
    act("section", "Make a section", lambda f: bool(f.range), C.section, group="range",
        promoted_when=lambda f: f.on_range),      # first only while the range is what you mean, not an old one under a pick
    act("inside", "Select inside", lambda f: f.on_range, importance="primary", group="range",
        do="inside"),
    act("repeat_range", "Repeat…", A.repeat_range_valid, A.repeat_calls, "Ctrl+R", "primary", "range", asks=True,
        amounts=("times", A.UNTIL), fit=A.repeat_fit),
    act("delete_time", "Delete time", lambda f: bool(f.range), C.delete_time, group="range",
        needs="Delete time needs a time range"),
    act("insert_time", "Insert time", lambda f: bool(f.range), C.insert_time, group="range",
        needs="Insert time needs a time range"),
    # the edit block: keys and the right-click menu, never the settings panel
    act("copy", "Copy", lambda f: f.count and f.kinds <= CLIPS, shortcut="Ctrl+C", group="edit", do="copy",
        needs="Copy needs notes, hits, clips or lines selected"),
    act("cut", "Cut", lambda f: f.count and f.kinds <= CLIPS, shortcut="Ctrl+X", group="edit", do="cut",
        needs="Cut needs notes, hits, clips or lines selected"),
    act("paste", "Paste", lambda f: f.clipboard, shortcut="Ctrl+V", group="edit", do="paste",
        needs="Nothing to paste yet: copy something first"),
    act("duplicate", "Duplicate", lambda f: f.count and not f.on_range and (f.kinds <= set(TIMED) or TRACK(f)),
        C.duplicate, "Ctrl+D",
        group="edit", needs="Duplicate needs notes, hits, clips or tracks selected"),
    act("range_duplicate", "Duplicate", lambda f: f.on_range and bool(C.inside(f)), C.range_duplicate,
        "Ctrl+D", group="edit"),
    act("rename", "Rename", lambda f: f.one in NAMED and f.count == 1, shortcut="F2", group="edit", do="rename",
        needs="Rename needs one track, group, marker or section selected"),
    act("cut_range", "Cut out and close the gap", lambda f: bool(f.range), C.cut_range, "Shift+Delete", group="range",
        needs="Cut out and close the gap needs a time range over a clip"),
    act("delete", "Delete", lambda f: f.count and f.kinds <= set(REMOVABLE), C.delete, "Delete", group="edit"),
]
ACTS_ON = {a["key"]: a["on"] for a in ACTIONS if a["on"]}      # what each names in its step ("Quantise · 178 notes and 202 drum hits")
RANGE = frozenset(a["key"] for a in ACTIONS if a["group"] == "range") | {"range_duplicate"}   # they act on the time range
# the kit's adapter doesn't read `release` or `panel` yet (kit request in the P30 report): put them on the Actions here
LIST = ActionList([replace(a, release=d["release"], panel=d["panel"]) for a, d in zip(from_dicts(ACTIONS, KEYMAP), ACTIONS)],
                  KEYMAP, noun="item", short_menu=SHORT_MENU)
