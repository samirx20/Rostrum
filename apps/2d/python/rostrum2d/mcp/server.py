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
from functools import reduce
from pathlib import Path

import anyio
from mcp.server.stdio import stdio_server
from rostrum_core.mcp import App, Guides, Runtime, build_server

from rostrum2d import run_source
from rostrum2d.modules import TOOLS
from . import inspect_keys, project_tool, session_clock, tool_groups
from .project_tool import open_documents, start_choice, with_no_project_sentence   # noqa: F401  (open_documents: its old import path)

GUIDES = Path(__file__).resolve().parents[3] / "guides"
INSTRUCTIONS = ("rostrum-2d makes motion graphics: compositions of shape / text / image / group layers animated by keys. "
                "Read inspect_guide 'start-here', build with run_script, then check your work with look_frame (one frame; what \"sheet\" a contact sheet, \"world\" the whole canvas with the frame's path, \"in_frame\" what is in or out of the frame) and look_motion. "
                "Paint on any shape, text, picture or path, or on a drawing, with paint.stroke (its paint stays inside the outline and "
                "moves with it; one call list = one undo step), fill a closed area with paint.fill {at, color, gap} (paint layers, shared by "
                "all of a layer's drawings: paint.add, paint.set, paint.move, paint.duplicate, paint.remove; saved brushes: run_brush) and check with look_drawing "
                "(what \"at\", \"landed\", \"change\", \"coverage\": what is painted and where bare paper shows); a wash to the canvas's or a region's edges: paint.wash; read inspect_guide 'drawing'. Frame by frame: draw a cycle once and repeat it with the drawing layer's "
                "loop, loopTimes and loopStepX / loopStepY (inspect_guide 'drawing-and-frame-by-frame'); to paint strokes on over time (write on), key drawnSoFar 0 → 1 on the drawing layer or painted element (strokes in painting order, each along its path); a filled polygon (a ridge, a silhouette) is fill.add or ink.fill in a script. A painting (painting.add) is a canvas many shapes and paths can use as one shared fill (layer.fill type \"painted\"): paint.stroke on it (its own px, or `through` a layer using it, in that layer's px; on a seamless painting a stroke over an edge comes back on the opposite side), look_painting (repeats: 1 shows it 3 × 3), look_painting what \"facts\" (with a seam check), look_at (where a point lands in it); to make it boil, frame.add on the painting (eachFrame turns on; every use boils from its own start, always looping, `phase` in layer.fill starts a use on another drawing). "
                "Every reply ends with a clock line (time since your first call; the minutes left when you have a budget): the time is "
                "for making, looking and refining in passes, and inspect_project what \"session\" lists what is still unchecked. "
                "The server opens the person's last project; run_open_project lists the recent ones (what \"recent\") and switches.")


SCRIPT_HELP = ("The 2D script layer: comp(id, width=, height=, fps=, duration=, background=); layers shape / text / image / "
               "path / group(id, **fields), made inside `with group(...):` to go in it (their x, y are then in the group's "
               "box); item.key(field, {time: value}, ease=\"easeOut\"), times in comp seconds or a marker (\"#beat-0.2\"); "
               "item.effect(\"shadow\" | \"glow\" | \"blur\" | \"gradient\" | …, **fields); item.mask(x=, y=, w=, h=); "
               "item.pivot(x, y): the anchor on that comp point, nothing moves (a grown drawing's turning point); "
               "w, h = t.measure(): a text's real box in its own px (before scale), to place things by its width; "
               "w, h = measure_text(\"words\", size=64, font=\"…\") measures a text you have not made (no probe layer, nothing left in the picture). "
               "The scene's frame (what is exported): f = frame(); f.key(\"x\", {0: 960, 4: 2600}); "
               "f.fit([\"hills\", \"tree\"], at=4) frames layers as they show then (depth counted), f.fit(rect=(x, y, w, h), at=4, "
               "ease=\"easeInOut\") (ease: how it moves into that framing; a fit where it already is changes nothing), "
               "f.cut(at=6, to=\"rect\", rect=(3200, 0, 1920, 1080)) or f.cut(at=\"#logo lands\") jumps it, f.home(at=8); "
               "the same as the operations frame.fit, frame.cut, frame.home (target \"frame\"). "
               "Fields: x, y (the anchor, default the centre), w, h, scale, rotation, opacity 0-1; shape: shape=\"rect\" | "
               "\"ellipse\" …, fill, radius, filled, stroke=\"#fff\", strokeWidth; text: body, size, weight, color, align (a text's x is its left edge, middle or right edge as align says); "
               "path: d (SVG; with no x, y, w, h its points are comp px), fill=\"none\". Colours \"#rrggbb\" or \"#rgb\". "
               "Drawings: d = drawing(id, w=, h=, eachFrame=True); f = d.frame(at); f.paint(); p.stroke(points, **brush) "
               "(every drawing's paint joins the layer's one set of paint layers). "
               "No import except math and random (seeded: the same numbers every run; random(7) is your own seeded generator "
               "with .uniform/.randint/.choice/.random) and no classes: use functions and dicts. "
               "Equations, graphs and charts: plot_area, curve_points, param_points, polar_points, line_d, lines_d, "
               "nice_ticks, tick_label, view3d, surface_lines, parse_table (inspect_guide 'data-math-and-graphs'). "
               "Before a field's first key it holds that key's value. Every field and the first-time surprises: "
               "inspect_guide 'start-here'. An error names the line and what to write instead.")


def app_tools():
    first, *rest = TOOLS.attrs("tools")
    return tool_groups.group(reduce(lambda merged, tools: merged.merged_with(tools), rest, first))


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
    inspect_keys.with_key_summary(runtime)          # a layer's keys as a summary unless asked for all
    session_clock.with_clock(runtime)                # last: every reply ends with the session's clock line
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
