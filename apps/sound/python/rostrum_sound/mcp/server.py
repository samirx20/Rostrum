"""The `rostrum-sound` MCP server (stdio), on rostrum_core.mcp.

    python -m rostrum_sound.mcp                                        (the agent's own song, never the person's)
    python -m rostrum_sound.mcp --project <folder> [--item <id>]       (that project; --folder is the same)

With no options the server opens the song this agent session last opened (a resumed session gets it back), else
a fresh scratch project with an empty song (rostrum_core/agent_start.py); never the person's last song. The first reply
says what is open and whose. While running, run_open_project lists the person's songs (what "recent") and switches (the
one engine process stays). Songs are `<folder>/docs/<item>.trk`, saved after every change.
"""
from __future__ import annotations

import argparse

import anyio
from mcp.server.stdio import stdio_server
from rostrum_core import agent_start
from rostrum_core.mcp import Runtime, Tools, build_server

from rostrum_sound.modules import TOOLS
from . import script_render, session_clock, tool_groups, tools_project
from .marker_lead import with_marker_lead, with_song_markers
from .song_line import with_song_line
from .track_line import with_track_feel
from .app import make_app


def sound_tools() -> Tools:
    tools = Tools()
    TOOLS.call("register", tools)
    return tool_groups.group(tools)


def make_runtime(app) -> Runtime:
    runtime = Runtime(app, sound_tools())
    tools_project.with_no_project_sentence(runtime)
    tools_project.with_short_operations(runtime)
    tools_project.with_sound_edit_help(runtime)
    tools_project.with_script_print(runtime)
    script_render.with_look(runtime)            # Sound's `look` (App.script_look renders and listens after the merge)
    tools_project.with_job_word(runtime)
    with_song_line(runtime)
    with_track_feel(runtime)
    with_marker_lead(runtime)
    with_song_markers(runtime)
    session_clock.with_clock(runtime)                # last: every reply ends with the session's clock line
    return runtime


async def _serve(app):
    server = build_server(app, runtime=make_runtime(app))
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


def main(argv=None):
    p = argparse.ArgumentParser(prog="rostrum-sound", description="The rostrum-sound MCP server (stdio). With no options it opens the agent's own last song, else a fresh scratch project; never the person's.")
    p.add_argument("--project", "--folder", dest="project", help="The project folder (documents in docs/, renders in renders/). Default: this agent session's own song, else a new scratch project (not the person's Recent songs).")
    p.add_argument("--item", action="append", help="A Sound document's item id (repeatable). Default: the project's recent item, else its only / newest one.")
    a = p.parse_args(argv)
    start = tools_project.start_choice(a.project, a.item)
    app = make_app(start.folder, start.items)
    agent_start.settle(app, start)                  # on disk, remembered, and said in the instructions and first reply
    anyio.run(_serve, app)


if __name__ == "__main__":
    main()
