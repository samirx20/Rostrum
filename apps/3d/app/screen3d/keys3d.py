"""Rostrum3D's own keys, as data on top of the shared key map (rostrum_gui/keymap.py; INTERACTION.md Part 2). A shared key
means here what it means in 2D and Sound (the arrows nudge, Tab walks the items, Ctrl+1 is no page, V is Select, B is
Paint, Enter goes in: on a shape that is Edit mesh, as 2D's Enter edits a path's points); 3D's own jobs have keys no
shared job uses. The kit refuses at start-up an own key that would take a shared one. The actions (actions3d.py) take
their keys from here through `job`.

Every job here and in the shared map runs something: an action, a ROUTE (a bridge method: key_routes3d.py), a WINDOW job
(Main.qml `windowJobs`: it needs the rail or the window) or a SKIP job (bound by the kit's AppShell and FilesMenu). A
shared job 3D has nothing behind is in NOT_HERE: no key, not on the Keys sheet. tests/test_keys_wired.py keeps this
honest. Q is Clay (clay_tool_qt.py; Q again, V or Esc: back to Select). F, held while Clay is on, sizes the brush: the
Clay tool watches it itself (a shortcut never sees a key come up), so it is in SKIP and TOOL. (The shared Fit, F, has no
meaning in 3D yet: it is in NOT_HERE.)
"""
from __future__ import annotations

from rostrum_gui.keymap import KeyMap

OWN = [
    # the rail (Rail3D.qml): the flyouts and the Animate page's two panels
    {"job": "clay_tool", "keys": ["Q"], "label": "Clay: make and sculpt clay", "area": "Tools"},
    {"job": "clay_size", "keys": ["F"], "label": "Clay: hold and move left or right to size the brush", "area": "Tools",
     "hold": True},
    {"job": "shapes_menu", "keys": ["R"], "label": "Shapes", "area": "Tools"},
    {"job": "type_menu", "keys": ["T"], "label": "Type & logo", "area": "Tools"},
    {"job": "lights_menu", "keys": ["L"], "label": "Lights", "area": "Tools"},
    {"job": "camera_menu", "keys": ["C"], "label": "Camera", "area": "Tools"},
    {"job": "poses_panel", "keys": ["P"], "label": "Poses (Animate page)", "area": "Panels"},
    {"job": "onion", "keys": ["O"], "label": "Onion skin on / off (Animate page)", "area": "Animate"},
    # Bones (bones_qt.py): Shift+B, beside B (Paint, the shared tool key): B was both once; Shift+B keeps the letter
    {"job": "bones_tool", "keys": ["Shift+B"], "label": "Bones: a chain on the selected mesh (Animate page)", "area": "Animate"},
    # the gizmo (gizmo_qt.py): which handles the selected item shows (V, Select, shows them all)
    {"job": "gizmo_move", "keys": ["W"], "label": "Move handles only", "area": "Tools"},
    {"job": "gizmo_turn", "keys": ["E"], "label": "Turn handles only", "area": "Tools"},
    {"job": "gizmo_scale", "keys": ["S"], "label": "Scale handles only", "area": "Tools"},
    # Edit mesh (mesh_edit_qt.py): Enter goes in (the shared Go in), Shift+Enter or Esc comes out
    {"job": "mesh_points", "keys": ["1"], "label": "Edit mesh: points", "area": "Edit mesh"},
    {"job": "mesh_edges", "keys": ["2"], "label": "Edit mesh: edges", "area": "Edit mesh"},
    {"job": "mesh_faces", "keys": ["3"], "label": "Edit mesh: faces", "area": "Edit mesh"},
    {"job": "mesh_xray", "keys": ["Alt+Z"], "label": "Edit mesh: see through (X-ray)", "area": "Edit mesh"},
    {"job": "mesh_knife", "keys": ["Shift+K"], "label": "Edit mesh: Knife", "area": "Edit mesh"},
    # the pages, the view, the look and the render
    {"job": "page_build", "keys": ["Alt+1"], "label": "Build page", "area": "View"},
    {"job": "page_animate", "keys": ["Alt+2"], "label": "Animate page", "area": "View"},
    {"job": "page_render", "keys": ["Alt+3"], "label": "Render page", "area": "View"},
    {"job": "shot_view", "keys": ["`"], "label": "Shot camera / free camera", "area": "View"},
    {"job": "look", "keys": ["Shift+F"], "label": "Look: Quick / Final", "area": "View"},
    {"job": "render", "keys": ["F12"], "label": "Render", "area": "Files"},
    {"job": "materials_list", "keys": [], "label": "Materials: the project's materials", "area": "Panels"},   # no key: the rail's ball, Ctrl+K
]

NOT_HERE = ("preferences",                  # no setting of 3D is a person's to change: Ctrl+, would open an empty window
            "play_from_selection", "prev_beat", "next_beat", "loop", "range_start", "range_end",
            "copy", "cut", "paste", "paste_other",          # no copy of items yet (materials: Copy / Paste material below)
            "delete_close_gap", "rename", "forward", "backward", "front", "back", "group", "ungroup", "hide", "lock",
            "split", "join", "trim_start", "trim_end", "animated_rows",
            "actual_size", "fit", "fit_all",                # the viewport has no 100 % and no framing yet (` is the shot's view)
            "find_item", "library", "add_file", "notes_tool")
KEYS3D = KeyMap("Rostrum3D", OWN, drop=NOT_HERE, words={
    "move_tool": "Select (all handles; leaves Paint and Clay)", "paint_tool": "Paint on the mesh or clay",
    "go_in": "Go in (Edit mesh; cut with the Knife; make the bones)",
    "go_out": "Go out (leave Edit mesh; pick the group)",
    "copy_style": "Copy material", "paste_style": "Paste material",
    "prev_event": "Previous key or marker", "next_event": "Next key or marker",
    "key_here": "Key what the gizmo moved, here", "jump": "Hold (no ease)",
    "nudge_left": "Nudge left (1 cm)", "nudge_right": "Nudge right (1 cm)", "nudge_up": "Nudge up (1 cm)",
    "nudge_down": "Nudge down (1 cm)",
    **{f"nudge_{d}_big": f"Nudge {d} (10 cm)" for d in ("left", "right", "up", "down")},
    **{f"nudge_{d}_fine": f"Nudge {d} (1 mm)" for d in ("left", "right", "up", "down")}})

NUDGE = [f"{d}{s}" for d in ("left", "right", "up", "down") for s in ("", "_big", "_fine")]
ROUTES = {
    "play": ("togglePlay",), "to_start": ("toStart",), "to_end": ("toEnd",),
    "frame_back": ("stepFrames", -1), "frame_on": ("stepFrames", 1),
    "frame_back_ten": ("stepFrames", -10), "frame_on_ten": ("stepFrames", 10),
    "prev_event": ("eventJump", -1), "next_event": ("eventJump", 1),
    "marker": ("markerHere",), "next_marker": ("markerJump", 1), "prev_marker": ("markerJump", -1),
    "select_all": ("selectAllItems",), "next_item": ("walk", 1), "prev_item": ("walk", -1),
    "go_in": ("goIn",), "go_out": ("goOut",), "step_back": ("stepBack",),
    **{f"nudge_{n}": ("nudgeKey", n) for n in NUDGE},
    "key_here": ("keyHere",),
    "smooth": ("easeKey", "smooth"), "ease_in": ("easeKey", "easeIn"), "ease_out": ("easeKey", "easeOut"),
    "jump": ("easeKey", "hold"),
    "zoom_in": ("zoomKey", 1), "zoom_out": ("zoomKey", -1),
    "move_tool": ("selectTool",), "paint_tool": ("paintKey",), "onion": ("onionKey",), "bones_tool": ("bonesKey",),
    "gizmo_move": ("gizmoKey", "move"), "gizmo_turn": ("gizmoKey", "turn"), "gizmo_scale": ("gizmoKey", "scale"),
    "mesh_points": ("meshKind", "points"), "mesh_edges": ("meshKind", "edges"), "mesh_faces": ("meshKind", "faces"),
    "mesh_xray": ("meshXray",), "mesh_knife": ("meshKnife",),
    "page_build": ("setPage", "build"), "page_animate": ("setPage", "animate"), "page_render": ("setPage", "render"),
    "shot_view": ("shotViewKey",), "look": ("lookKey",), "render": ("renderKey",),
}
# the window's own (Main.qml `windowJobs`): they need the rail
WINDOW = ("clay_tool", "shapes_menu", "type_menu", "lights_menu", "camera_menu", "poses_panel", "materials_list", "quit")
# held keys a tool watches itself (clay_tool_qt.SizeKey: F down and up while Clay is on): no shortcut, no Ctrl+K row
TOOL = ("clay_size",)
# bound where they are made: the kit's AppShell (undo, redo, Ctrl+K, F1, Keys, History, Export, F6, Ctrl+\, Ctrl+F in the
# settings panel, Alt+Shift+J in the timeline's time box) and the kit's FilesMenu (the files)
SKIP = ["undo", "redo", "command_box", "guides", "key_list", "history", "export", "export_again", "fold_panels", "next_area",
        "find_setting", "go_to_time", "new", "open", "save_version", "duplicate_file", *TOOL]
# Ctrl+K runs these through the kit's AppShell.runJob (Main.qml hands on every job it doesn't answer itself)
SHELL = ("undo", "redo", "history", "export", "export_again", "guides", "key_list", "fold_panels", "next_area",
         "find_setting", "problems", "go_to_time")
# jobs with a row of their own in Ctrl+K already (the ≡ menu's files) or none on purpose (Esc steps back: no row)
HAVE_ROWS = ("new", "open", "save_version", "duplicate_file", "step_back", *TOOL)
