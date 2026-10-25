"""Sound's own keys as data (INTERACTION.md Part 2, the [Sound] rows) and the one key map: `KEYMAP` = the shared keys
plus these (rostrum_gui.keymap refuses a clash at start-up). Moved here from the kit's demo (sound_keys.py).

ROUTES: the shared jobs Sound answers that are not actions on the selection (play, the playhead, nudges, the loop,
zoom …): the hub (action_slots.SoundHub) calls these bridge methods with these arguments. SKIP: the jobs Main.qml or
the kit's AppShell bind themselves (files, undo, Ctrl+K, F1, record), so the root KeyMap leaves them alone.
"""
from rostrum_gui.keymap import KeyMap

SOUND_KEYS = [
    {"job": "record", "keys": ["R"], "label": "Record on the armed track", "area": "Play"},
    {"job": "click", "keys": ["Shift+K"], "label": "Click (metronome) on / off", "area": "Play"},
    {"job": "pitch_scale_up", "keys": ["Ctrl+Up"], "label": "Pitch up a scale step", "area": "Edit"},
    {"job": "pitch_scale_down", "keys": ["Ctrl+Down"], "label": "Pitch down a scale step", "area": "Edit"},
    {"job": "quantize", "keys": ["Q"], "label": "Quantise", "area": "Edit"},
    {"job": "repeat", "keys": ["Ctrl+R"], "label": "Repeat…", "area": "Edit"},
    {"job": "next_take", "keys": ["T"], "label": "Next take", "area": "Edit"},
    {"job": "swap_sound", "keys": ["S"], "label": "Swap a sound", "area": "Edit"},
    {"job": "hear_original", "keys": ["H"], "label": "Hear the original (hold)", "area": "Edit",
     "hold": True},
    {"job": "mute", "keys": ["Shift+M"], "label": "Mute", "area": "Edit"},
    {"job": "solo", "keys": ["Shift+S"], "label": "Solo", "area": "Edit"},
    {"job": "snap", "keys": ["Shift+G"], "label": "Snapping on / off", "area": "Edit"},
    {"job": "editor_dock", "keys": ["E"], "label": "Editor dock", "area": "Panels"},
    {"job": "mixer_dock", "keys": ["X"], "label": "Mixer dock", "area": "Panels"},
]
# the shared keys in a music app's words: the playhead moves by the grid (Grid ▾), "previous thing" is a start, an end or a marker
WORDS = {
    "frame_back": "Playhead back one grid step", "frame_on": "Playhead on one grid step",
    "frame_back_ten": "Playhead back ten grid steps", "frame_on_ten": "Playhead on ten grid steps",
    "prev_event": "Previous start, end or marker", "next_event": "Next start, end or marker",
}
# Shared jobs Sound has nothing behind: no key, and not on the Keys sheet (test_keys_wired keeps the sheet honest:
# every key listed runs a ROUTE, an action, a SKIP job (files, undo ...) or the kit's AppShell)
NOT_HERE = ("prev_beat", "next_beat", "go_in", "go_out", "find_item",     # Sound is the beat grid: no beat keys of its own; nothing behind Go in / Go out / Find an item
            "play_from_selection", "next_item", "prev_item", "nudge_up_fine", "nudge_down_fine", "front", "back", "hide",
            "trim_start", "trim_end", "copy_style", "paste_style", "key_here", "animated_rows", "smooth", "ease_in",
            "ease_out", "jump", "actual_size", "notes_tool", "paste_other",
            "find_setting")                # Sound's settings panel has no find box (the kit's needs `sections = True`: 2D has it)
SHELL = ("history", "key_list", "fold_panels", "next_area")      # bound by the kit's AppShell / Inspector
KEYMAP = KeyMap("RostrumSound", SOUND_KEYS, drop=NOT_HERE, words=WORDS)

_NUDGE = {"": "grid", "_big": "bar", "_fine": "fine"}
ROUTES = {
    "play": ("togglePlay",), "to_start": ("setTime", 0.0),
    "frame_back": ("playheadStep", -1), "frame_on": ("playheadStep", 1),
    "frame_back_ten": ("playheadStep", -10), "frame_on_ten": ("playheadStep", 10),
    "prev_event": ("jump", -1), "next_event": ("jump", 1), "loop": ("toggleLoop",), "click": ("toggleClick",),
    "range_start": ("rangeEdge", "in"), "range_end": ("rangeEdge", "out"),
    "select_all": ("selectAll",), "step_back": ("clearSelection",), "delete": ("removeSelected",),
    "marker": ("markerHere",), "fit": ("fitSelection",), "fit_all": ("fitView",),
    "zoom_in": ("zoomStep", 1.25), "zoom_out": ("zoomStep", 0.8),
    **{f"nudge_{d}{s}": ("nudge", how, 1 if d == "right" else -1) for d in ("left", "right") for s, how in _NUDGE.items()},
    "nudge_up": ("pitchStep", 1), "nudge_down": ("pitchStep", -1), "nudge_up_big": ("pitchStep", 12),
    "nudge_down_big": ("pitchStep", -12),
    "pitch_scale_up": ("pitchScaleStep", 1), "pitch_scale_down": ("pitchScaleStep", -1),
    "add_section": ("songDo", "add_section", ""),                       # no key: Ctrl+K and the song panel's "+ Section"
    "to_end": ("toEnd",), "next_marker": ("markerJump", 1), "prev_marker": ("markerJump", -1),
    "move_tool": ("setTool", "select"), "paint_tool": ("setTool", "draw"),        # V / B: the Editor's tools
    "snap": ("toggleSnap",),
    "editor_dock": ("dock", "editor"), "mixer_dock": ("dock", "mixer"), "library": ("dock", "library"),
}
SKIP = ["new", "open", "save_version", "duplicate_file", "add_file", "preferences", "quit", "export", "export_again",
        "undo", "redo", "command_box", "guides", "record"]
SHELL_RUN = ("undo", "redo", "export", "export_again", "history", "guides", "key_list", "fold_panels", "next_area", "preferences", "quit",
             "add_file", "record", "problems", "loudness", "sample_rate")       # the window runs these (Main.qml › runSoundJob, the kit's AppShell.runJob)
FILE_JOBS = ("new", "open", "save_version", "duplicate_file")   # the ≡ menu's rows are in Ctrl+K from the project files (file:*)
