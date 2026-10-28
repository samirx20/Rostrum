"""The `rostrum-3d` MCP server.

    python -m rostrum3d.mcp --project <folder> --item <id> [--item <id> ...]      (stdio; opens or creates each item)
    rostrum-3d --project <folder> --item <id>                                     (the same, as an installed command)

Every change is saved at once, so the 3D screen process can open the same file. Tools: the shared ones from rostrum_core, plus
look_frame, look_sheet, look_shots, look_material, look_at, look_paint, inspect_paint_strokes, look_coverage, look_where, look_shape, render_still, render_video, render_estimate, render_send_shot, inspect_model_file, inspect_shot,
inspect_animations, look_motion. One engine process (`rostrum3d-core
serve`) is started on first use and kept for the session.
"""
from __future__ import annotations

import argparse
import atexit
from functools import reduce
from dataclasses import dataclass
from pathlib import Path

from rostrum_core import Document
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
from . import session_clock

GUIDES = Path(__file__).resolve().parents[1] / "guides"
INSTRUCTIONS = ("rostrum-3d makes 3D shots: a scene of meshes (cut and joined live by combines), sculpted clay, imports, copies (one thing many times, scattered over a surface), lights and cameras, animated by keys and rendered by Hydra "
                "(Storm for quick looks, Cycles for the final picture). Read inspect_guide 'getting-started' first for the five-minute character. "
                "Read inspect_guide 'agents', build with run_script, then check "
                "your work through the shot's camera with look_frame, look_sheet and look_at before any render_still or render_video.")
SCRIPT_HELP = ("In Rostrum3D: write the whole scene as ONE script, look, edit that script, and re-run it whole under the same name. "
               "Any id already in the scene (another script's, or left by an undo) is taken over by the script that makes it again, "
               "under any name; edit(id) / item(id) gives a handle to anything in the scene. A re-run that leaves out most of what "
               "its last run made is refused with the list (send the whole script, or remove(...) what you mean to drop). "
               "Guide: inspect_guide 'script'.")


@dataclass
class ThreeDState:
    engine: Engine


def app_tools():
    first, *rest = TOOLS.attrs("tools")
    return reduce(lambda merged, tools: merged.merged_with(tools), rest, first)


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
    app = App("rostrum-3d", docs, run_source=run_source, instructions=INSTRUCTIONS, script_help=SCRIPT_HELP, guides=Guides().load_folder(GUIDES), folder=project)
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
    ap = argparse.ArgumentParser(prog="rostrum-3d", description="The rostrum-3d MCP server (stdio).")
    ap.add_argument("--project", required=True, help="The project folder.")
    ap.add_argument("--item", action="append", required=True, help="A document's item id (repeat for several).")
    a = ap.parse_args(argv)
    anyio.run(_serve, make_app(a.project, a.item))


if __name__ == "__main__":
    main()
