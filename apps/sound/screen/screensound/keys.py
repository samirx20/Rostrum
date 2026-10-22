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
KEYMAP = KeyMap("RostrumSound", SOUND_KEYS)

_NUDGE = {"": "grid", "_big": "bar", "_fine": "fine"}
ROUTES = {
    "play": ("togglePlay",), "to_start": ("setTime", 0.0),
    "frame_back": ("playheadStep", -1), "frame_on": ("playheadStep", 1),
    "frame_back_ten": ("playheadStep", -10), "frame_on_ten": ("playheadStep", 10),
    "prev_event": ("jump", -1), "next_event": ("jump", 1), "loop": ("toggleLoop",),
    "range_start": ("rangeEdge", "in"), "range_end": ("rangeEdge", "out"),
    "select_all": ("selectAll",), "step_back": ("clearSelection",), "delete": ("removeSelected",),
    "marker": ("markerHere",), "fit": ("fitSelection",), "fit_all": ("fitView",),
    "zoom_in": ("zoomStep", 1.25), "zoom_out": ("zoomStep", 0.8),
    **{f"nudge_{d}{s}": ("nudge", how, 1 if d == "right" else -1) for d in ("left", "right") for s, how in _NUDGE.items()},
    "nudge_up": ("pitchStep", 1), "nudge_down": ("pitchStep", -1), "nudge_up_big": ("pitchStep", 12),
    "nudge_down_big": ("pitchStep", -12),
    "move_tool": ("setTool", "select"), "paint_tool": ("setTool", "draw"),        # V / B: the Editor's tools
    "snap": ("toggleSnap",),
    "editor_dock": ("dock", "editor"), "mixer_dock": ("dock", "mixer"), "library": ("dock", "library"),
}
SKIP = ["new", "open", "save_version", "duplicate_file", "add_file", "preferences", "quit", "export", "export_again",
        "undo", "redo", "command_box", "guides", "record"]
