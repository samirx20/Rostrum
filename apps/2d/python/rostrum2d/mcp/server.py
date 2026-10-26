"""The `rostrum-2d` MCP server.

    python -m rostrum2d.mcp                                          (stdio; opens the person's last project)
    python -m rostrum2d.mcp --project <folder> [--item <id> ...]     (that project; --item opens or creates each item)

With no options the server opens the project the 2D screen would open: the newest row of Open recent still on disk.
With none, no document is open (inspect_project says so). While running, run_open_project lists the person's projects
(what "recent") and switches. Every change is saved at once, so the 2D screen process can open the same file.
Tools: the shared ones from rostrum_core, plus the 2D ones, few and clear (tool_groups.py joins the related ones under one
name with a `what` argument): look_frame, look_motion, look_at, look_drawing, look_painting, inspect_layout, inspect_sounds,
inspect_fonts, inspect_diagnose, render_video, render_export, run_import, run_brush, run_brand_kit, run_open_project, edit_sound_cue.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import anyio
from mcp.server.stdio import stdio_server
from rostrum_core.mcp import App, Guides, Runtime, build_server

from rostrum2d import run_source
from . import at, curves, diagnose_tool, draw, export_tool, fonts_tool, import_tool, layout_tool, look, motion, project_tool, rig, video, world
from . import tool_groups
from . import background_tool, brand_tool, brush_tool, lipsync, painting_tool, picture_tool, sound_cue_tool, soundtrack_tool, swap_tool
from .project_tool import open_documents, start_choice, with_no_project_sentence   # noqa: F401  (open_documents: its old import path)

GUIDES = Path(__file__).resolve().parents[3] / "guides"
INSTRUCTIONS = ("rostrum-2d makes motion graphics: compositions of shape / text / image / group layers animated by keys. "
                "Read inspect_guide 'start-here', build with run_script, then check your work with look_frame (one frame; what \"sheet\" a contact sheet, \"world\" the whole canvas with the frame's path, \"in_frame\" what is in or out of the frame) and look_motion. "
                "Paint on any shape, text, picture or path, or on a drawing, with paint.stroke (its paint stays inside the outline and "
                "moves with it; one call list = one undo step), fill a closed area with paint.fill {at, color, gap} (paint layers, shared by "
                "all of a layer's drawings: paint.add, paint.set, paint.move, paint.duplicate, paint.remove; saved brushes: run_brush) and check with look_drawing "
                "(what \"at\", \"landed\", \"change\"); read inspect_guide 'drawing'. Frame by frame: draw a cycle once and repeat it with the drawing layer's "
                "loop, loopTimes and loopStepX / loopStepY (inspect_guide 'drawing-and-frame-by-frame'); a filled polygon (a ridge, a silhouette) is fill.add or ink.fill in a script. A painting (painting.add) is a canvas many shapes and paths can use as one shared fill (layer.fill type \"painted\"): paint.stroke on it (its own px, or `through` a layer using it, in that layer's px; on a seamless painting a stroke over an edge comes back on the opposite side), look_painting (repeats: 1 shows it 3 × 3), look_painting what \"facts\" (with a seam check), look_at (where a point lands in it); to make it boil, frame.add on the painting (eachFrame turns on; every use boils from its own start, always looping, `phase` in layer.fill starts a use on another drawing). "
                "The server opens the person's last project; run_open_project lists the recent ones (what \"recent\") and switches.")


SCRIPT_HELP = ("The 2D script layer: comp(id, width=, height=, fps=, duration=, background=); layers shape / text / image / "
               "path / group(id, **fields), made inside `with group(...):` to go in it (their x, y are then in the group's "
               "box); item.key(field, {time: value}, ease=\"easeOut\"), times in comp seconds or a marker (\"#beat-0.2\"); "
               "item.effect(\"shadow\" | \"glow\" | \"blur\" | \"gradient\" | …, **fields); item.mask(x=, y=, w=, h=). "
               "The scene's frame (what is exported): f = frame(); f.key(\"x\", {0: 960, 4: 2600}); "
               "f.fit([\"hills\", \"tree\"], at=4) frames layers as they show then (depth counted), f.fit(rect=(x, y, w, h), at=4), "
               "f.cut(at=6, to=\"rect\", rect=(3200, 0, 1920, 1080)) or f.cut(at=\"#logo lands\") jumps it, f.home(at=8); "
               "the same as the operations frame.fit, frame.cut, frame.home (target \"frame\"). "
               "Fields: x, y (the anchor, default the centre), w, h, scale, rotation, opacity 0-1; shape: shape=\"rect\" | "
               "\"ellipse\" …, fill, radius, filled, stroke=\"#fff\", strokeWidth; text: body, size, weight, color, align (a text's x is its left edge, middle or right edge as align says); "
               "path: d (SVG; with no x, y, w, h its points are comp px), fill=\"none\". Colours \"#rrggbb\" or \"#rgb\". "
               "Drawings: d = drawing(id, w=, h=, eachFrame=True); f = d.frame(at); f.paint(); p.stroke(points, **brush) "
               "(every drawing's paint joins the layer's one set of paint layers). "
               "No import except math and random (seeded: the same numbers every run; random(7) is your own seeded generator "
               "with .uniform/.randint/.choice/.random) and no classes: use functions and dicts. "
               "Before a field's first key it holds that key's value. Every field and the first-time surprises: "
               "inspect_guide 'start-here'. An error names the line and what to write instead.")


def app_tools():
    return tool_groups.group(look.tools.merged_with(motion.tools).merged_with(at.tools).merged_with(video.tools)
            .merged_with(draw.tools).merged_with(rig.tools).merged_with(lipsync.tools).merged_with(curves.tools).merged_with(export_tool.tools)
            .merged_with(layout_tool.tools).merged_with(swap_tool.tools).merged_with(import_tool.tools).merged_with(diagnose_tool.tools).merged_with(fonts_tool.tools)
            .merged_with(background_tool.tools).merged_with(project_tool.tools).merged_with(soundtrack_tool.tools)
            .merged_with(sound_cue_tool.tools).merged_with(brand_tool.tools)
            .merged_with(picture_tool.tools).merged_with(brush_tool.tools).merged_with(painting_tool.tools).merged_with(world.tools))


def make_app(project: str | None = None, items: list[str] | None = None, documents: dict | None = None) -> App:
    docs = documents if documents is not None else (open_documents(project, items or []) if project else {})
    instructions = INSTRUCTIONS if docs else f"{INSTRUCTIONS} {project_tool.NO_PROJECT}"
    return App("rostrum-2d", docs, run_source=run_source, instructions=instructions, guides=Guides().load_folder(GUIDES),
               folder=project, script_help=SCRIPT_HELP)


def make_runtime(app: App) -> Runtime:
    from rostrum_core import markers
    from rostrum2d import placement
    placement.use(placement.Host(markers=lambda: markers.times(app.folder) if app.folder else None, folder=lambda: app.folder))   # comp-px strokes see the project's markers and renders
    from rostrum_paint import library
    library.use_project(app.folder)                  # the project's own tip and paper pictures are brush choices
    runtime = Runtime(app, app_tools())
    with_no_project_sentence(runtime)
    return runtime


async def _serve(app: App):
    server = build_server(app, runtime=make_runtime(app))
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


def main(argv=None):
    ap = argparse.ArgumentParser(prog="rostrum2d.mcp", description="The rostrum-2d MCP server (stdio). With no options it opens the person's last project.")
    ap.add_argument("--project", help="The project folder. Default: the person's last project (Open recent).")
    ap.add_argument("--item", action="append", help="A document's item id (repeat for several). Default: the project's recent item, else its only / newest one.")
    a = ap.parse_args(argv)
    project, items = start_choice(a.project, a.item)
    anyio.run(_serve, make_app(project, items))


if __name__ == "__main__":
    main()
