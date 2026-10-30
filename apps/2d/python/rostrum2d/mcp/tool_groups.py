"""The 2D server's tools, few and clear (CONVENTIONS § 2): tools that answer the same kind of question are one tool, and
`what` picks the question. Each part is still written as its own small tool in its own module; this list joins them.
An old name answers with an error naming the tool and the `what` to pass (rostrum_core.mcp.combine). Each part's
sentence here is tool_text.SAY's; the full words are the guide 'tools-in-detail'."""
from __future__ import annotations

from rostrum_core.mcp.combine import combine

GROUPS = [
    ("look_frame", "See the composition as it renders, and what is wrong with it.",
     {"frame": "look_frame", "sheet": "look_sheet", "world": "look_world", "in_frame": "look_in_frame", "rig": "look_rig",
      "empty": "look_empty", "review": "look_review", "diagnose": "inspect_diagnose", "layout": "inspect_layout",
      "swaps": "inspect_swaps"}, "frame"),
    ("look_motion", "How things move, from the document's keys (no rendering).",
     {"moves": "look_motion", "path": "look_path", "curve": "inspect_curve", "keys": "inspect_animations", "rig": "inspect_rig_motion"}, "moves"),
    ("look_at", "What is at a point (x, y) at a time.",
     {"layers": "look_at", "colour": "inspect_colour_at"}, "layers"),
    ("look_drawing", "See and check a drawing layer in its own canvas pixels; use \"change\" or \"landed\" right after paint.stroke.",
     {"drawing": "look_drawing", "change": "look_drawing_change", "at": "inspect_drawing_at", "landed": "inspect_stroke_landed",
      "tiles": "look_background", "depths": "inspect_background", "coverage": "look_coverage"}, "drawing"),
    ("look_painting", "See and check a painting (a canvas shapes share as their fill).",
     {"picture": "look_painting", "facts": "inspect_painting"}, "picture"),
    ("inspect_sounds", "Sound for this composition.",
     {"sounds": "inspect_sounds", "soundtrack": "inspect_soundtrack", "lipsync": "inspect_lipsync"}, "sounds"),
    ("run_brand_kit", "The project's brand kit (colours and text styles every document shares).",
     {"list": "inspect_brand_kit", "change": "run_brand_kit", "use": "run_brand_use"}, None),
    ("run_import", "Bring a file into the project.",
     {"layers": "run_import", "paint_picture": "run_paint_picture"}, "layers"),
    ("run_open_project", "The person's projects.",
     {"open": "run_open_project", "recent": "inspect_recent_projects"}, "open"),
    ("render_export", "Export a composition. It waits for the file and answers once (a long one: inspect_job waits again; `wait_s` 0: the job id at once); "
     "an mp4 redraws only what changed since the last export (a stopped export keeps the pieces it finished). `notes: true` adds what the checks measured.",
     {"file": "render_export", "video": "render_video"}, "file"),
]


def group(tools):
    """Join the parts in place; returns `tools`."""
    for name, lead, parts, default in GROUPS:
        combine(tools, name, lead, parts, default=default)
    return tools
