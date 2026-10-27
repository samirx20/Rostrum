"""The 2D server's tools, few and clear (CONVENTIONS § 2): tools that answer the same kind of question are one tool, and
`what` picks the question. Each part is still written as its own small tool in its own module; this list joins them.
An old name answers with an error naming the tool and the `what` to pass (rostrum_core.mcp.combine)."""
from __future__ import annotations

from rostrum_core.mcp.combine import combine

GROUPS = [
    ("look_frame", "See the composition as it renders: one frame (default; or `times: [0.5, 1.2, 3.0]` for one sheet of exactly those moments), a contact sheet of a range, the whole world with "
     "the frame's path, the rig's bones over a frame, or which layers are in or out of the frame, or where the piece is blank, pale or standing still (\"empty\", with times). Use \"frame\" to check "
     "a moment, \"sheet\" to check timing across a range, \"world\" when the frame moves over a big canvas.",
     {"frame": "look_frame", "sheet": "look_sheet", "world": "look_world", "in_frame": "look_in_frame", "rig": "look_rig", "empty": "look_empty"}, "frame"),
    ("look_motion", "How things move, from the document's keys (no rendering): every move's start, landing, ease and "
     "speed (default), one layer's path, one field's value curve, a layer's keys as the timeline shows them, or an IK "
     "rig's tip path and gaps.",
     {"moves": "look_motion", "path": "look_path", "curve": "inspect_curve", "keys": "inspect_animations", "rig": "inspect_rig_motion"}, "moves"),
    ("look_at", "What is at a point (x, y) at a time: the layers covering it, top first (default), or the rendered colour there.",
     {"layers": "look_at", "colour": "inspect_colour_at"}, "layers"),
    ("look_drawing", "See and check a drawing layer in its own canvas pixels: the drawing at a frame (default), before | "
     "after of the last change, what is at one canvas pixel, whether a stroke landed on its path, a big drawing tile by "
     "tile, or the composition's drawing layers by depth. Use \"change\" or \"landed\" right after paint.stroke.",
     {"drawing": "look_drawing", "change": "look_drawing_change", "at": "inspect_drawing_at", "landed": "inspect_stroke_landed",
      "tiles": "look_background", "depths": "inspect_background"}, "drawing"),
    ("look_painting", "See and check a painting (a canvas shapes share as their fill): the painting in its own pixels "
     "(default), or the facts of every painting (size, paint layers, drawings, who uses it, a seam check).",
     {"picture": "look_painting", "facts": "inspect_painting"}, "picture"),
    ("inspect_layout", "How groups place their children at a time: auto layouts (default) or swap sets (which child shows).",
     {"layout": "inspect_layout", "swaps": "inspect_swaps"}, "layout"),
    ("inspect_sounds", "Sound for this composition: the sounds you can tie to a layer with edit_sound_cue (default), what "
     "plays with the composition (its soundtrack), or a voice clip heard as lip sync hears it.",
     {"sounds": "inspect_sounds", "soundtrack": "inspect_soundtrack", "lipsync": "inspect_lipsync"}, "sounds"),
    ("run_brand_kit", "The project's brand kit (colours and text styles every document shares): list it, change an "
     "entry, or put an entry on layers.",
     {"list": "inspect_brand_kit", "change": "run_brand_kit", "use": "run_brand_use"}, None),
    ("run_import", "Bring a file into the project: as new layers of a composition (svg, pdf, psd, figma, …; default), or "
     "a picture as a brush tip or paper for painting.",
     {"layers": "run_import", "paint_picture": "run_paint_picture"}, "layers"),
    ("run_open_project", "The person's projects: open one, or make a new one by giving a folder that doesn't exist yet "
     "(default; every change is already saved, so nothing is lost), or list the recent ones to pick from.",
     {"open": "run_open_project", "recent": "inspect_recent_projects"}, "open"),
]


def group(tools):
    """Join the parts in place; returns `tools`."""
    for name, lead, parts, default in GROUPS:
        combine(tools, name, lead, parts, default=default)
    return tools
