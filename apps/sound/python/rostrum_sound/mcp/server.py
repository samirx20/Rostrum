"""The `rostrum-sound` MCP server (stdio), on rostrum_core.mcp.

    python -m rostrum_sound.mcp                                        (opens the person's last song)
    python -m rostrum_sound.mcp --project <folder> [--item <id>]       (that project; --folder is the same)

With no options the server opens the song the Sound screen would open: the newest row of Recent songs still on disk. With
none, no document is open (inspect_project says so). While running, run_open_project lists the person's songs
(what "recent") and switches (the one engine process stays). Songs are `<folder>/docs/<item>.trk`, saved after every change.
"""
from __future__ import annotations

import argparse

import anyio
from mcp.server.stdio import stdio_server
from rostrum_core.mcp import Runtime, Tools, build_server

from rostrum_sound.modules import TOOLS
from . import tool_groups, tools_project
from .song_line import with_song_line
from .app import make_app


def sound_tools() -> Tools:
    tools = Tools()
    TOOLS.call("register", tools)
    return tool_groups.group(tools)


def make_runtime(app) -> Runtime:
    runtime = Runtime(app, sound_tools())
    tools_project.with_no_project_sentence(runtime)
    tools_project.with_sound_edit_help(runtime)
    tools_project.with_script_print(runtime)
    with_song_line(runtime)
    return runtime


async def _serve(app):
    server = build_server(app, runtime=make_runtime(app))
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


def main(argv=None):
    p = argparse.ArgumentParser(prog="rostrum-sound", description="The rostrum-sound MCP server (stdio). With no options it opens the person's last song.")
    p.add_argument("--project", "--folder", dest="project", help="The project folder (documents in docs/, renders in renders/). Default: the person's last song.")
    p.add_argument("--item", action="append", help="A Sound document's item id (repeatable). Default: the project's recent item, else its only / newest one.")
    a = p.parse_args(argv)
    folder, items = tools_project.start_choice(a.project, a.item)
    anyio.run(_serve, make_app(folder, items))


if __name__ == "__main__":
    main()
