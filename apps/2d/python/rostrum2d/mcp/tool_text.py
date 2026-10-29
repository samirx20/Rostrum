"""What the agent reads in the tool list: one short sentence per tool (part) and short argument words (CONVENTIONS § 2: a
tool's description at most 150 words). Each part's own docstring and argument texts stay the full account: they make the
guide page `tools-in-detail` (every part, every argument), so moving the words here loses nothing.

`shorten(tools)` runs on the parts before tool_groups joins them, so a joined tool pastes these short sentences."""
from __future__ import annotations

from rostrum_core.mcp import short_text

# One sentence per part: what it is for, when to pick it. A part not listed keeps its own text (already short).
SAY = {
    "look_frame": "One frame at `time`; `times` [..] one sheet of those moments; `area` zooms; `video` reads an mp4.",
    "look_sheet": "A contact sheet of `count` moments from `start` to `end`.",
    "look_world": "The whole canvas with the frame's path.",
    "look_in_frame": "Which layers are in, partly in or out of the frame.",
    "look_rig": "The rigs' bones over one frame.",
    "look_empty": "Blank, washed-out or still stretches and edge-cut subjects, with times.",
    "look_review": "What the checks measure, ranked, with times (notes, never a verdict); `beats` checks the brief's beats.",
    "inspect_diagnose": "Everything broken: missing fonts or files, broken links, bad expressions, unseen layers.",
    "look_motion": "Every move per layer from the keys (start, landing, ease, speed) and overlap / stillness facts; no rendering.",
    "look_path": "The path a layer or the frame travels, with its key handles and speed on screen.",
    "inspect_curve": "One number field's value curve and each key's ease handles.",
    "inspect_animations": "A layer's keys and stretches as the timeline shows them.",
    "inspect_rig_motion": "An IK chain's tip path, its gaps and sliding pinned feet over a time range.",
    "look_at": "The layers covering a point (x, y) at a time, top first, with their values and boxes.",
    "inspect_colour_at": "The rendered colour at a point, every effect counted (an eyedropper).",
    "look_drawing": "One drawing in its own canvas px: zoom, grid, one paint layer, onion skin, or `crop` at 100 %.",
    "look_drawing_change": "Before | after | difference of the last change to a drawing.",
    "inspect_drawing_at": "What is at one canvas pixel: colour per paint layer, the top stroke, masks.",
    "inspect_stroke_landed": "Whether a stroke left paint on its path, in words.",
    "look_background": "A big painted background tile by tile, with the frame's move drawn on it.",
    "inspect_background": "The drawing layers by depth and whether each covers the frame's whole move.",
    "look_coverage": "How much of a drawing is painted and where bare paper shows, as boxes in words.",
    "look_painting": "A painting in its own px (`repeats` 1 shows it 3 × 3 to see seams).",
    "inspect_painting": "Every painting's size, paint layers, drawings, users and a seam check.",
    "inspect_layout": "Where each auto-layout group places its children.",
    "inspect_swaps": "Each swap set's children and which one shows.",
    "inspect_sounds": "Sounds to tie to a layer with edit_sound_cue, the song's own instruments first; `words` searches.",
    "inspect_soundtrack": "What plays with the composition: its song, tempo, bars and markers.",
    "inspect_lipsync": "A voice clip's phones, words and mouth cues as lip sync hears them.",
    "inspect_brand_kit": "List the brand kit.",
    "run_brand_kit": "Add, replace or remove a brand kit entry.",
    "run_brand_use": "Put a brand colour or text style on layers (one undo step).",
    "run_import": "A file (svg, pdf, psd, figma, image, video) as new layers; `report` says what did not come across.",
    "run_paint_picture": "A picture as a brush tip or paper; its id goes to paint.stroke `texture` or `paper`.",
    "run_open_project": "Open the person's project folder, or make a new one (every change is already saved).",
    "inspect_recent_projects": "The person's recent projects, newest first.",
    "render_export": "A file in an Export-button format (`format`): mp4, prores4444, webm, gif, png, lottie, motion samples.",
    "render_video": "The project render: an mp4 in renders/<item>/vNNN with a manifest, which Sound and the Editor find.",
    "run_brush": "Saved brushes (My brushes): list, save, use, duplicate, rename, delete, keep, drop.",
    "edit_sound_cue": "Tie a sound to a layer: it plays at the layer's start in the soundtrack song and follows the layer.",
    "inspect_fonts": "Every font a text may name, shipped first, with its weights and italic; `search` filters.",
    "inspect_table": "Read a csv / tsv / json table as rows to paste into a script, with axis ticks per number column.",
}

# Argument words, by name, for every part that has the argument (the same words let tool_groups show them once);
# "" = none: the name and type say it.
ARG = {
    "paint": "Only this paint layer (id).",
    "ids": "",
    "to": "",
    "from": "",
    "painting": "",
    "stroke": "",
    "y": "",
    "x": "",
    "wait": "Wait for the job: true (50 s) or seconds.",
    "item": "Document id, not a layer; default the open one.",
    "comp": "",
    "time": "",
    "frame": "",
    "times": "Seconds: one sheet of these moments.",
    "video": "An mp4 to read instead.",
    "start": "",
    "end": "",
    "cols": "Tiles per row.",
    "grid": "Grid step, canvas px; 0 = none.",
    "sampling": "pixels or smooth zoom.",
    "crop": "[x, y] canvas px at 100 %.",
    "onion": "Faint neighbours: true or {before, after}.",
    "quality": "mp4 detail.",
    "bitrate": "mp4 Mbit/s instead of quality.",
    "sound": "mp4: the project's sound under it.",
    "beats": "Timed beats [{at, to, expect}] to check.",
    "alpha": "Keep transparency.",
    "width": "Picture px wide.",
    "layer": "",
    "zoom": "[x0, y0, x1, y1] canvas px.",
}

# Where one part's argument needs its own words (the same name means something else in another part).
ARG_OF = {
    ("run_brand_kit", "style"): "A document text style's name.",
    ("run_brand_use", "layers"): "",
    ("run_brand_kit", "layers"): "",
    ("run_brand_kit", "name"): "",
    ("inspect_diagnose", "engine"): "Also ask the engine.",
    ("look_painting", "painting"): "",
    ("inspect_painting", "painting"): "",
    ("inspect_animations", "owner"): "Layer, effect or mask id.",
    ("inspect_curve", "owner"): "Layer, effect or mask id.",
    ("look_motion", "owner"): "Layer, effect or mask id.",
    ("run_paint_picture", "path"): "The file.",
    ("inspect_lipsync", "pronounce"): "{word: phones} for unknown words.",
    ("look_frame", "area"): "[x, y, w, h] comp px to zoom on (one frame).",
    ("look_frame", "width"): "Picture px wide.",
    ("look_sheet", "width"): "Picture px wide.",
    ("look_sheet", "count"): "Moments, evenly spaced.",
    ("look_world", "area"): "all, frame, or {x, y, w, h} world px.",
    ("look_world", "path"): "Draw the frame's path.",
    ("look_empty", "every"): "Seconds between samples.",
    ("look_empty", "min_still"): "Still seconds before named.",
    ("look_review", "limit"): "Moments to name.",
    ("look_motion", "full"): "Every move, full data.",
    ("look_motion", "limit"): "Lines to list.",
    ("look_motion", "all"): "No cap.",
    ("look_path", "layer"): "A layer id or frame.",
    ("look_path", "rate"): "Samples a second.",
    ("look_at", "space"): "frame (picture px) or world (world px).",
    ("look_coverage", "time"): "",
    ("look_background", "tile"): "One tile close, e.g. B2.",
    ("look_painting", "repeats"): "1: show its repeats, to see seams.",
    ("look_in_frame", "step"): "Seconds between looks.",
    ("inspect_lipsync", "source"): "A WAV or voice:<line id>.",
    ("inspect_lipsync", "shapes"): "{shape: mouth layer id}.",
    ("render_export", "format"): "motion = samples for RostrumSound.",
    ("render_export", "layers"): "motion: layer ids (default: moving ones).",
    ("render_export", "area"): "png: frame, items (ids) or world.",
    ("render_export", "scale"): "png: px per world px.",
    ("render_export", "size"): "gif size.",
    ("render_export", "path"): "Output path.",
    ("render_export", "name"): "File name without its type.",
    ("render_export", "overwrite"): "Replace an existing file.",
    ("render_export", "time"): "png: one picture at this time.",
    ("render_export", "rate"): "gif frame rate.",
    ("render_video", "path"): "Output path.",
    ("render_video", "overwrite"): "Replace an existing file.",
    ("render_video", "with_project"): "Also save the project beside it.",
    ("run_import", "path"): "The file.",
    ("run_import", "page"): "pdf page from 1; 0 = all.",
    ("run_import", "text"): "svg text as text or outline.",
    ("run_import", "figma"): "{key, frame, token}.",
    ("run_import", "fit"): "Fit into the composition.",
    ("inspect_fonts", "search"): "Name holds this, e.g. serif.",
    ("inspect_table", "path"): "The file.",
    ("inspect_table", "rows"): "Rows at most.",
    ("run_open_project", "folder"): "Absolute; made when new.",
    ("run_open_project", "item"): "Document; a new name starts one.",
    ("inspect_sounds", "words"): "Search words, e.g. cello.",
    ("edit_sound_cue", "layer"): "Plays at its start, follows it.",
    ("edit_sound_cue", "sound"): "A path from inspect_sounds.",
    ("run_brand_kit", "file"): "logos: the picture.",
    ("run_paint_picture", "as"): "",
    ("run_brush", "action"): "",
    ("run_brush", "place"): "library: the person's own.",
    ("run_brush", "settings"): "save: paint.stroke settings.",
}

MOST = 15        # argument words kept from a part's own text when neither table names it
PLAIN = {"wait", "width", "item"} | {k for k, v in ARG.items() if not v}    # said without the choices that take them (a wrong one is refused by name)


def shorten(tools):
    """Every part's short sentence and short argument words, in place; returns `tools`."""
    return short_text.shorten(tools, SAY, ARG, ARG_OF, MOST)


def tidy(tools, names):
    return short_text.tidy(tools, names, PLAIN)


def detail_page(tools) -> str:
    from . import tool_groups
    return short_text.detail_page(tools, tool_groups.GROUPS,
        "The full account of each tool and each of its arguments. The tool list keeps one short sentence each; a joined tool "
        "(look_frame, look_motion, render_export, ...) is listed here per `what` choice.")
