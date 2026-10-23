"""The project's own brush tip and paper pictures for agents (rostrum_paint/library.py; the screen's Edit brush page
lists the same choices):

    run_paint_picture {path, as: tip|paper, name?}     keep a picture in the project; its id is a brush choice

The picture is copied into the project (media/brushtip/ or media/paper/) and named by an item id. Paint with it by
that id: paint.stroke {texture: <id>} for a tip, {paper: <id>, grain > 0} for a paper.
"""
from __future__ import annotations

from pathlib import Path

from rostrum_core.errors import RostrumError, codes
from rostrum_core.mcp import Reply, Tools
from rostrum_paint import library

tools = Tools()


@tools.tool("run_paint_picture", {"properties": {
    "path": {"type": "string", "description": "The picture (png, jpg, webp …), relative to the project or absolute."},
    "as": {"type": "string", "enum": ["tip", "paper"], "description": "tip: the dab's shape (dark or opaque = paint). "
           "paper: a tile repeated over the canvas (light = raised tooth); its middle square is used."},
    "name": {"type": "string", "description": "What screens call it; the file's name when left out."}},
    "required": ["path", "as"]})
def run_paint_picture(ctx, args):
    """Load a picture as a brush tip or a paper of this project. The same picture loaded twice is one item. Returns
    its id: use it as paint.stroke's `texture` (tip) or `paper`. Strokes keep working when the project moves."""
    folder = ctx.app.folder
    if not folder:
        raise RostrumError(codes.BAD_ARGUMENT, ctx.tool, "a picture", "needs a project folder: none is open")
    path = Path(args["path"]) if Path(args["path"]).is_absolute() else Path(folder) / args["path"]
    row = library.load(folder, path, args["as"], args.get("name", ""))
    use = "texture" if args["as"] == "tip" else "paper"
    return Reply(f'Kept "{row["name"]}" as a {args["as"]} picture: {row["id"]} (paint.stroke {use}: "{row["id"]}").',
                 {"item": row})
