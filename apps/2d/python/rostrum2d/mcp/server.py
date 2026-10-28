"""The `rostrum-2d` MCP server.

    python -m rostrum2d.mcp                                          (stdio; the agent's own project, never the person's)
    python -m rostrum2d.mcp --project <folder> [--item <id> ...]     (that project; --item opens or creates each item)

With no options the server opens the project this agent session last opened (a resumed session gets it back),
else a fresh scratch project with an empty document (rostrum_core/agent_start.py); never the person's last project. The
first reply says what is open and whose. While running, run_open_project lists the person's projects (what "recent") and
switches. Every change is saved at once, so the 2D screen process can open the same file.
Tools: the shared ones from rostrum_core, plus the 2D ones, few and clear (tool_groups.py joins the related ones under one
name with a `what` argument): look_frame, look_motion, look_at, look_drawing, look_painting, inspect_sounds, inspect_fonts,
render_export, run_import, run_brush, run_brand_kit, run_open_project, edit_sound_cue. The core five (CORE) come first.
The tool list carries one short sentence per tool (tool_text.py); the full words are the guide 'tools-in-detail'.
"""
from __future__ import annotations

import argparse
from functools import reduce
from pathlib import Path

import anyio
from mcp.server.stdio import stdio_server
from rostrum_core import agent_start
from rostrum_core.mcp import App, Guides, Runtime, build_server

from rostrum2d import run_source
from rostrum2d.modules import TOOLS
from . import export_beats, export_wait, inspect_keys, project_tool, script_look, session_clock, small_toolset, tool_groups, tool_text
from .project_tool import open_documents, start_choice, with_no_project_sentence   # noqa: F401  (open_documents: its old import path)

GUIDES = Path(__file__).resolve().parents[3] / "guides"
INSTRUCTIONS = ("rostrum-2d makes motion graphics: compositions of shape / text / image / group layers animated by keys. "
                "Read inspect_guide 'start-here' first: it gives the loop (one script, run_script with look, fix, re-run under "
                "the same name, render_export), the core verbs and the five core tools. "
                "The server starts on your own project (the first reply says which), never the person's work; "
                "run_open_project lists theirs (what \"recent\") and switches. Every reply ends with a clock line.")


SCRIPT_HELP = ("2D script layer: lay out first with row / column / grid / stack(padding=, gap=, align=); a layer with no "
               "x / y sits at its parent's centre; anchor=\"top-left\"|…. Time by name: marker(\"reveal\", 3) -> \"#reveal+0.5\", "
               "after(item, gap=), stagger(items, every=), beats(). item.key(field, {time: value}, ease=). Every function: "
               "inspect_guide 'script-reference'.")


CORE = ["run_script", "look_frame", "look_motion", "inspect_guide", "render_export"]


def part_tools():
    """Every 2D tool as written, before the short words and the joining (their full text: guide 'tools-in-detail')."""
    first, *rest = TOOLS.attrs("tools")
    return reduce(lambda merged, tools: merged.merged_with(tools), rest, first)


def app_tools():
    tools = tool_text.tidy(tool_groups.group(tool_text.shorten(part_tools())), [g[0] for g in tool_groups.GROUPS])
    tools.core = CORE
    return tools


def guides() -> Guides:
    """The guide folder, plus 'tools-in-detail' made from the tools' own full words (always in step with the code)."""
    out = Guides().load_folder(GUIDES)
    out.add("tools-in-detail", tool_text.detail_page(part_tools()))
    return out


def make_app(project: str | None = None, items: list[str] | None = None, documents: dict | None = None) -> App:
    docs = documents if documents is not None else (open_documents(project, items or []) if project else {})
    lead = small_toolset.INSTRUCTIONS if small_toolset.wanted() else INSTRUCTIONS
    instructions = lead if docs else f"{lead} {small_toolset.NO_PROJECT if small_toolset.wanted() else project_tool.NO_PROJECT}"
    return App("rostrum-2d", docs, run_source=run_source, instructions=instructions, guides=guides(),
               folder=project, script_help=SCRIPT_HELP, script_look=script_look.after_run)


def make_runtime(app: App) -> Runtime:
    from rostrum_core import markers
    from rostrum2d import placement
    placement.use(placement.Host(markers=lambda: markers.times(app.folder) if app.folder else None, folder=lambda: app.folder))   # comp-px strokes see the project's markers and renders
    from rostrum_paint import library
    library.use_project(app.folder)                  # the project's own tip and paper pictures are brush choices
    runtime = Runtime(app, app_tools())
    with_no_project_sentence(runtime)
    export_wait.with_wait(runtime)                  # render_export (both what) waits for their job in the same call (wait_s)
    inspect_keys.with_key_summary(runtime)          # a layer's keys as a summary unless asked for all
    clock = session_clock.with_clock(runtime)        # every reply ends with the session's clock line
    export_beats.with_beats(runtime, clock)          # the exports take the brief's beats; the clock keeps them
    if small_toolset.wanted():                       # ROSTRUM2D_TOOLSET=small: the four-tool server (same engine)
        small_toolset.apply(runtime, clock)
    return runtime


async def _serve(app: App):
    server = build_server(app, runtime=make_runtime(app))
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


def main(argv=None):
    ap = argparse.ArgumentParser(prog="rostrum2d.mcp", description="The rostrum-2d MCP server (stdio). With no options it opens the agent's own last project, else a fresh scratch project; never the person's.")
    ap.add_argument("--project", help="The project folder. Default: this agent session's own project, else a new scratch project (not the person's Open recent).")
    ap.add_argument("--item", action="append", help="A document's item id (repeat for several). Default: the project's recent item, else its only / newest one.")
    a = ap.parse_args(argv)
    start = start_choice(a.project, a.item)
    app = make_app(start.folder, start.items)
    agent_start.settle(app, start)                  # on disk, remembered, and said in the instructions and first reply
    anyio.run(_serve, app)


if __name__ == "__main__":
    main()
