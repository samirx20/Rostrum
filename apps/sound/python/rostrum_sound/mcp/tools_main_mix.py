"""run_set_main_mix: which song of the project is the main mix (the one 2D plays with the picture and the Editor mixes
with). A mark on the project, not an edit of a song, so it records no history step."""
from __future__ import annotations

from rostrum_core import RostrumError, codes
from rostrum_core.mcp import Reply, Tools

from .. import main_mix


def register(tools: Tools):
    @tools.tool("run_set_main_mix", {"properties": {"item": {"type": "string", "description": "The song to make the main mix. Optional when only one is open."}}})
    def run_set_main_mix(ctx, args):
        """Make a song the project's main mix: the song 2D plays with the picture and the Editor uses for the final mix. Answers the new main mix and the one it replaced. No change when the song already is the main mix."""
        folder = ctx.app.folder
        if not folder:
            raise RostrumError(codes.BAD_ARGUMENT, "run_set_main_mix", "the project", "is not in a project folder")
        item = ctx.document(args.get("item")).item_id
        if main_mix.is_main(folder, item):
            return Reply(f'"{item}" already is the main mix; nothing changed.', {"item": item, "was": item})
        r = main_mix.make_main(folder, item)
        return Reply(f'"{r["name"]}" is now the main mix.', r)
