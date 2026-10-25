"""Rostrum2D's own keys, as data on top of the shared key map (rostrum_gui/keymap.py; INTERACTION.md Part 2, the
[2D] rows that 2D uses today). The kit refuses at start-up any of these that would take a shared key. The actions
(actions.py) take their keys from here through `job`. Every job here and in the shared map runs something: an action,
a ROUTE (a bridge method: key_routes.py), a WINDOW job (Main.qml `windowJobs`) or a SKIP job (bound by the kit's AppShell
and FilesMenu, or by a Shortcut that needs screen state). A shared job 2D has nothing behind is in NOT_HERE: no key, not
on the Keys sheet. tests/test_keys_wired.py keeps this honest.
"""
from __future__ import annotations

from rostrum_gui.keymap import KeyMap

OWN = [
    {"job": "pen_tool", "keys": ["P"], "label": "Pen"},
    {"job": "new_drawing", "keys": ["Alt+N"], "label": "New drawing"},
    {"job": "copy_drawing", "keys": ["Alt+Shift+N"], "label": "Copy of this drawing"},
    {"job": "onion", "keys": ["Alt+O"], "label": "Onion skin"},
    {"job": "hold_longer", "keys": ["=", "+"], "label": "Hold this drawing longer"},
    {"job": "hold_shorter", "keys": ["-"], "label": "Hold this drawing shorter"},
    {"job": "rect_tool", "keys": ["R"], "label": "Rectangle"},
    {"job": "ellipse_tool", "keys": ["O"], "label": "Ellipse"},
    {"job": "text_tool", "keys": ["T"], "label": "Text"},
    {"job": "pick_frame", "keys": ["C"], "label": "Pick the frame"},
    {"job": "look_through", "keys": ["Shift+C"], "label": "Look through the frame"},
    {"job": "fit_everything", "keys": ["Shift+1"], "label": "Fit everything"},
    {"job": "fit", "keys": ["Shift+2"], "label": "Fit the selection"},               # F's second key (Figma habit)
    {"job": "bone_tool", "keys": ["J"], "label": "Bone"},
    {"job": "hand_tool", "keys": ["H"], "label": "Hand"},
    {"job": "zoom_tool", "keys": ["Z"], "label": "Zoom"},
    {"job": "auto_layout", "keys": ["Shift+A"], "label": "Auto layout"},
    {"job": "align_left", "keys": ["Alt+A"], "label": "Align left"},
    {"job": "align_right", "keys": ["Alt+D"], "label": "Align right"},
    {"job": "align_top", "keys": ["Alt+W"], "label": "Align top"},
    {"job": "align_bottom", "keys": ["Alt+S"], "label": "Align bottom"},
    {"job": "centre_across", "keys": ["Alt+H"], "label": "Align centre"},
    {"job": "centre_down", "keys": ["Alt+V"], "label": "Align middle"},
    {"job": "mask", "keys": ["Ctrl+Alt+M"], "label": "Mask"},
    {"job": "union", "keys": ["Ctrl+Alt+U"], "label": "Combine: union"},
    {"job": "subtract", "keys": ["Ctrl+Alt+S"], "label": "Combine: subtract"},
    {"job": "intersect", "keys": ["Ctrl+Alt+I"], "label": "Combine: intersect"},
    {"job": "exclude", "keys": ["Ctrl+Alt+X"], "label": "Combine: exclude"},
    {"job": "make_painted_fill", "keys": [], "label": "Make painted fill"},          # no key: the right-click's Make block
]

NOT_HERE = ("preferences",          # no setting of 2D is a person's to change: Ctrl+, would open an empty window
            "play_from_selection", "go_out", "next_item", "prev_item", "find_item", "paste_other", "delete_close_gap",
            "split", "join", "trim_start", "trim_end", "loop", "range_start", "range_end", "notes_tool")
# a tool is listed by the name its button has in the tool rail ("Brush"), so searching the Keys sheet by a tool's name finds it
KEYS2D = KeyMap("Rostrum2D", OWN, drop=NOT_HERE, words={"paint_tool": "Brush (paint and draw)",
                                    "fit_all": "Fit the frame"})   # Ctrl+0 fits the frame here, not "all"

NUDGE = [f"{d}{s}" for d in ("left", "right", "up", "down") for s in ("", "_big", "_fine")]
ROUTES = {
    "to_start": ("setTime", 0.0), "to_end": ("toEnd",),
    "frame_back": ("stepFrames", -1), "frame_on": ("stepFrames", 1),
    "frame_back_ten": ("stepFrames", -10), "frame_on_ten": ("stepFrames", 10),
    "marker": ("markerHere",), "next_marker": ("markerJump", 1), "prev_marker": ("markerJump", -1),
    "select_all": ("selectAllKey",), "animated_rows": ("showAnimated",),
    **{f"nudge_{n}": ("nudgeKey", n) for n in NUDGE},
    "move_tool": ("toolKey", "move"), "pen_tool": ("toolKey", "pen"), "rect_tool": ("toolKey", "rect"),
    "ellipse_tool": ("toolKey", "ellipse"), "text_tool": ("toolKey", "text"), "hand_tool": ("toolKey", "hand"),
    "zoom_tool": ("toolKey", "zoom"), "bone_tool": ("toolKey", "bone"),
}
# the window's own (Main.qml `windowJobs`): they need the canvas, the rail or the painter
WINDOW = ("paint_tool", "pick_frame", "prev_event", "next_event", "prev_beat", "next_beat", "delete", "library", "add_file", "quit",
          "new_drawing", "copy_drawing", "onion", "hold_longer", "hold_shorter",
          "zoom_in", "zoom_out", "fit_all", "fit_everything", "actual_size", "fit", "look_through")
# bound where they are made: the kit's AppShell (undo, redo, Ctrl+K, F1, Keys, History, Export, F6, Ctrl+\, Ctrl+F in the
# Inspector), the kit's FilesMenu (files), Space (spacekey.py: a tap plays, held it pans), Esc and Enter (Main.qml: they
# step by what is open)
SKIP = ["play", "step_back", "go_in", "undo", "redo", "command_box", "guides", "key_list", "history", "export", "export_again",
        "fold_panels", "next_area", "find_setting", "new", "open", "save_version", "duplicate_file"]
# Ctrl+K runs these jobs too: ROUTES, WINDOW and the kit's shell jobs (AppShell.runJob); Space plays through spacekey.py, so its row calls
# the bridge itself. The ≡ menu's rows (New, Open, Save a version ...) and Add from a file are already rows of their own.
ASKED = {"play": ("togglePlay",)}
SHELL = ("undo", "redo", "history", "export", "export_again", "guides", "key_list", "fold_panels", "next_area",
         "find_setting", "problems")
HAVE_ROWS = ("new", "open", "save_version", "duplicate_file", "add_file",
           "zoom_in", "zoom_out", "fit_all", "fit_everything", "actual_size", "fit", "look_through")   # the view menu's rows are in Ctrl+K already (view_commands.py)
