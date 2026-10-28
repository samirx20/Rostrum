"""The `rostrum-3d` MCP server.

    python -m rostrum3d.mcp                                                       (stdio; the agent's own scene, never the person's)
    python -m rostrum3d.mcp --project <folder> [--item <id> ...]                  (that project; --item opens or creates each item)
    rostrum-3d --project <folder> --item <id>                                     (the same, as an installed command)

With no options the server opens the scene this agent session last opened (a resumed session gets it back), else
a fresh scratch project with a new scene (the start scene; rostrum_core/agent_start.py); never the person's last scene.
The first reply says what is open and whose; run_open_project lists the person's scenes (what "recent") and switches.

Every change is saved at once, so the 3D screen process can open the same file. Tools: the shared ones from rostrum_core, plus
the 3D ones, few and clear (tool_groups.py joins the look family under look_frame `what`; the core five come first). One engine process (`rostrum3d-core
serve`) is started on first use and kept for the session.
"""
from __future__ import annotations

import argparse
import atexit
from functools import reduce
from dataclasses import dataclass
from pathlib import Path

from rostrum_core import Document, agent_start
import anyio
from mcp.server.stdio import stdio_server
from rostrum_core.mcp import App, Guides
from rostrum_core.mcp.server import Runtime, build_server
from rostrum_core.storage import paths

from rostrum3d import ops_mesh
from rostrum3d.engine import Engine
from rostrum3d.kind import KIND
from rostrum3d.modules import TOOLS
from rostrum3d.script import run_source
from rostrum3d.start_scene import SOURCE as START
from . import project_tool, script_look, session_clock, tool_groups, tool_text

GUIDES = Path(__file__).resolve().parents[1] / "guides"
INSTRUCTIONS = ("rostrum-3d makes 3D shots: meshes, sculpted clay, imports, lights and cameras, animated by keys, rendered by Storm (quick) "
                "and Cycles (final). Read inspect_guide 'start-here' first: write the scene as one run_script, look through the shot "
                "camera with look_frame, fix the script, re-run it, then render. "
                "The server starts on your own scene: the one you last opened from this folder (a resumed session gets it back), else a fresh "
                "scratch project made for you, never the person's work (the first reply says which); the person's scenes open only when you ask: "
                "run_open_project lists them (what \"recent\") and switches.")
SCRIPT_HELP = ("In Rostrum3D: the whole scene as ONE script, re-run whole under the same name; edit(id) reaches anything "
               "in the scene. A character is ONE clay (it stands on the ground; positions are heights above it): c.lump(...) "
               "pieces, then c.bend / c.pose keys its joints. Guide 'script'.")


@dataclass
class ThreeDState:
    engine: Engine


def app_tools():
    first, *rest = TOOLS.attrs("tools")
    tools = tool_groups.group(tool_text.shorten(reduce(lambda merged, tools: merged.merged_with(tools), rest, first)))
    return tool_text.tidy(tools, [g[0] for g in tool_groups.GROUPS] + [n for n in ("run_open_project",) if n in tools._tools])


def open_documents(project: str, items: list[str]) -> dict:
    """Open each item from the project folder (or start it as New does when it has no file yet: start_scene.py, a
    ground, the Studio sky and Shot 1's camera), saving after every change."""
    docs = {}
    for item in items:
        exists = paths(project, item, KIND.ext)["doc"].exists()
        doc = Document.open(project, item, KIND) if exists else Document.new(KIND, project, item)
        if not exists:
            doc.run_script("start.py", run_source(START, "start.py"))
        doc.subscribe(lambda ev, d=doc: d.save() if ev.kind == "change" else None)
        if not exists:
            doc.save()
        docs[item] = doc
    return docs


def make_app(project: str | None = None, items: list[str] | None = None, documents: dict | None = None, engine: Engine | None = None) -> App:
    docs = documents if documents is not None else open_documents(project, items or [])
    app = App("rostrum-3d", docs, run_source=run_source, instructions=INSTRUCTIONS, script_help=SCRIPT_HELP, guides=Guides().load_folder(GUIDES), folder=project,
              script_look=script_look.after_run)
    app.state = ThreeDState(engine or Engine())          # the process starts on the first request, not now
    atexit.register(app.state.engine.close)
    ops_mesh.use_engine(app.state.engine, project)          # mesh.edit and mesh.unfold read a shape's mesh from this engine
    return app


async def _serve(app: App):
    runtime = Runtime(app, app_tools())
    session_clock.with_clock(runtime)                # last: every reply ends with the session's clock line
    server = build_server(app, runtime=runtime)
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


def main(argv=None):
    ap = argparse.ArgumentParser(prog="rostrum-3d", description="The rostrum-3d MCP server (stdio). With no options it opens the agent's own last scene, else a fresh scratch project; never the person's.")
    ap.add_argument("--project", help="The project folder. Default: this agent session's own scene, else a new scratch project (not the person's Open recent).")
    ap.add_argument("--item", action="append", help="A document's item id (repeat for several). Default: the project's recent item, else its newest scene, else a new \"scene\".")
    a = ap.parse_args(argv)
    start = project_tool.start_choice(a.project, a.item)
    app = make_app(start.folder, start.items)
    agent_start.settle(app, start)                  # on disk, remembered, and said in the instructions and first reply
    anyio.run(_serve, app)


if __name__ == "__main__":
    main()
