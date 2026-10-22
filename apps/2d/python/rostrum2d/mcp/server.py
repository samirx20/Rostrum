"""The `rostrum-2d` MCP server.

    python -m rostrum2d.mcp                                          (stdio; opens the person's last project)
    python -m rostrum2d.mcp --project <folder> [--item <id> ...]     (that project; --item opens or creates each item)

With no options the server opens the project the 2D screen would open: the newest row of Open recent still on disk.
With none, no document is open (inspect_project says so). While running, inspect_recent_projects lists the person's
projects and run_open_project switches. Every change is saved at once, so the 2D screen process can open the same file.
Tools: the shared ones from rostrum_core, plus look_frame, look_sheet, look_motion, look_at, render_video, render_export,
run_import, inspect_layout, inspect_swaps, inspect_diagnose, inspect_soundtrack, inspect_recent_projects, run_open_project.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import anyio
from mcp.server.stdio import stdio_server
from rostrum_core.mcp import App, Guides, Runtime, build_server

from rostrum2d import run_source
from . import at, curves, diagnose_tool, draw, export_tool, import_tool, layout_tool, look, motion, project_tool, rig, video
from . import background_tool, lipsync, sound_cue_tool, soundtrack_tool, swap_tool
from .project_tool import open_documents, start_choice, with_no_project_sentence   # noqa: F401  (open_documents: its old import path)

GUIDES = Path(__file__).resolve().parents[3] / "guides"
INSTRUCTIONS = ("rostrum-2d makes motion graphics: compositions of shape / text / image / group layers animated by keys. "
                "Read inspect_guide 'start-here', build with run_script, then check your work with look_frame, look_sheet and look_motion. "
                "Paint on any shape, text, picture or path, or on a drawing, with paint.stroke (its paint stays inside the outline and "
                "moves with it; one call list = one undo step), fill a closed area with paint.fill {at, color, gap} (paint layers: "
                "paint.set, paint.move, paint.remove) and check with look_drawing, "
                "inspect_drawing_at and inspect_stroke_landed; read inspect_guide 'drawing'. "
                "The server opens the person's last project; inspect_recent_projects and run_open_project switch.")


def app_tools():
    return (look.tools.merged_with(motion.tools).merged_with(at.tools).merged_with(video.tools)
            .merged_with(draw.tools).merged_with(rig.tools).merged_with(lipsync.tools).merged_with(curves.tools).merged_with(export_tool.tools)
            .merged_with(layout_tool.tools).merged_with(swap_tool.tools).merged_with(import_tool.tools).merged_with(diagnose_tool.tools)
            .merged_with(background_tool.tools).merged_with(project_tool.tools).merged_with(soundtrack_tool.tools)
            .merged_with(sound_cue_tool.tools))


def make_app(project: str | None = None, items: list[str] | None = None, documents: dict | None = None) -> App:
    docs = documents if documents is not None else (open_documents(project, items or []) if project else {})
    instructions = INSTRUCTIONS if docs else f"{INSTRUCTIONS} {project_tool.NO_PROJECT}"
    return App("rostrum-2d", docs, run_source=run_source, instructions=instructions, guides=Guides().load_folder(GUIDES),
               folder=project)


def make_runtime(app: App) -> Runtime:
    from rostrum_core import markers
    from rostrum2d import placement
    placement.use(placement.Host(markers=lambda: markers.times(app.folder) if app.folder else None, folder=lambda: app.folder))   # comp-px strokes see the project's markers and renders
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
