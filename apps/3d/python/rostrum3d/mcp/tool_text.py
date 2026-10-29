"""Short argument words for the tool list (CONVENTIONS § 2), applied to the parts before tool_groups joins them: the same
words across parts let combine() show an argument once, and an argument whose name and type say it all carries none.
Each part's own text stays the full account in its module; `tidy` writes the joined tools' choice lists in fewer
characters ('(for what "a", "b")' -> '(what a, b)'; quotes cost twice in the JSON a client reads)."""
from __future__ import annotations

from rostrum_core.mcp import short_text

# By name, for every part with the argument; "" = no words (the name and type say it).
ARG = {
    "item": "Document id, not an object; default the open scene.",
    "wait": "Wait for the job: true (50 s) or seconds.",
    "at": "Seconds from the shot's start.",
    "frame": "",
    "start": "Seconds from the shot's start.",
    "end": "Seconds from the shot's start.",
    "quality": "fast = Storm, final = Cycles (default fast).",
    "renderer": "Overrides quality by name (stylized: Lines and Halftone).",
    "width": "The picture's width in px (default 960; sheet 480; shots 320).",
    "count": "Frames (sheet, default 6; shots a row, 4) or angles (material, 6).",
    "samples": "Cycles samples per pixel.",
    "denoise": "Cycles noise clean-up.",
    "passes": "EXR layers beside Beauty (Cycles); [] = Beauty alone.",
    "notes": "Also list the checks' measured notes; off by default.",
    "x": "Pixels from the picture's left.",
    "y": "Pixels from the picture's top.",
    "zoom": "[x0, y0, x1, y1] canvas px.",
    "grid": "Grid step in canvas px; 0 = none.",
    "sampling": "pixels or smooth zoom.",
}

# One part's own words where its argument differs.
ARG_OF = {
    ("look_frame", "through"): "A light's id: look the way it shines.",
    ("look_frame", "onion"): "An item's ghosts at other frames.",
    ("look_frame", "highlight"): "Outline clay steps: \"steps:arm,foot\".",
    ("look_at", "width"): "The width of the picture you were shown (default 960).",
    ("look_at", "height"): "Its height (default: the shot's shape).",
    ("look_at", "points"): "[[x, y], …] instead of x and y.",
    ("look_material", "shape"): "ball, or plane (a flat square).",
    ("look_paint", "channel"): "Only layers painting this channel.",
    ("look_where", "uv"): "[u, v] on its unfolded surface.",
    ("look_shape", "cells"): "A clay's sampling along its longest side.",
    ("look_shots", "shots"): "Shot ids or names, a row each.",
    ("render_still", "quality"): "final = Cycles, fast = Storm.",
    ("render_video", "quality"): "final = Cycles, fast = Storm.",
    ("render_send_shot", "quality"): "final = Cycles, fast = Storm.",
    ("render_still", "renderer"): "Overrides quality by name.",
    ("render_video", "renderer"): "Overrides quality by name.",
    ("render_still", "width"): "Picture px wide (default: the shot's).",
    ("render_video", "width"): "Picture px wide (default: the shot's).",
    ("render_send_shot", "width"): "Picture px wide (default: the shot's).",
    ("render_still", "formats"): "png (sRGB) and / or exr (linear, for the Editor).",
    ("render_video", "exr"): "Also keep every frame as EXR.",
    ("render_video", "output_folder"): "An absolute folder to copy the mp4 into.",
    ("render_video", "file_name"): "The copy's name.",
    ("render_video", "budget_min"): "Minutes you can spend; over it nothing renders.",
    ("render_video", "estimate_only"): "Only measure the time.",
    ("render_estimate", "quality"): "draft 32, good 128, final 512 samples, or stylized.",
    ("render_estimate", "denoise"): "Noise clean-up (quality custom).",
    ("render_estimate", "all_shots"): "Every shot and a total.",
    ("render_estimate", "budget_min"): "Minutes you can spend; over it, changes that fit.",
    ("render_send_shot", "target"): "2d: a render layer in a 2D scene.",
    ("render_send_shot", "scene"): "\"<2D item>/<scene id>\" (default: the last).",
    ("edit_place_highlight", "fresh"): "A light just added: also set its distance and brightness.",
    ("edit_place_on", "mirror"): "On a mirrored clay, also a mirrored copy.",
    ("look_motion", "frames"): "[first, last] frame.",
    ("look_motion", "items"): "Only these items.",
    ("look_motion", "full"): "Speeds per frame, jumps and stretches too.",
    ("look_motion", "limit"): "Items and findings to list.",
    ("inspect_paint_strokes", "target"): "A mesh's or clay's id, or a paint layer's.",
    ("inspect_model_file", "file"): "USD, glTF, OBJ, FBX or Alembic.",
    ("inspect_assets", "query"): "Words to match in name or tags.",
    ("run_open_project", "folder"): "Absolute; made when new.",
    ("run_open_project", "item"): "The scene; a new name starts one.",
}

MOST = 15
PLAIN = {"wait", "item"} | {k for k, v in ARG.items() if not v}      # said without the choices that take them (a wrong one is refused by name)


def shorten(tools):
    """Every part's short argument words, in place (descriptions are short in each module); returns `tools`."""
    return short_text.shorten(tools, {}, ARG, ARG_OF, MOST)


def tidy(tools, names):
    return short_text.tidy(tools, names, PLAIN)
