"""The `rostrum-sound` MCP server (stdio), on rostrum_core.mcp.

    python -m rostrum_sound.mcp.server --folder <project folder> [--item cue]

Opens (or creates) the Sound documents `<folder>/docs/<item>.trk` and starts one engine process for the session.
"""
from __future__ import annotations

import argparse

from rostrum_core.mcp import Tools, run_stdio

from . import tools_inspect, tools_look, tools_midi, tools_motion, tools_plugins, tools_render, tools_sfx, tools_voice
from .app import make_app


def sound_tools() -> Tools:
    tools = Tools()
    for m in (tools_render, tools_look, tools_inspect, tools_sfx, tools_voice, tools_motion, tools_plugins, tools_midi):
        m.register(tools)
    return tools


def main(argv=None):
    p = argparse.ArgumentParser(prog="rostrum-sound", description=__doc__.splitlines()[0])
    p.add_argument("--folder", required=True, help="The project folder (documents in docs/, renders in renders/).")
    p.add_argument("--item", action="append", help="A Sound document's item id (repeatable). Default: cue.")
    a = p.parse_args(argv)
    run_stdio(make_app(a.folder, a.item or ["cue"]), sound_tools())


if __name__ == "__main__":
    main()
