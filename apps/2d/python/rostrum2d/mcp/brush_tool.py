"""My brushes for agents (rostrum2d/brushes.py; the screen's brush panel shows the same ones under My brushes):

    run_brush {action: list | save | rename | delete, …}

A saved brush is kept in the project (an item of kind "brush"), so people and agents share it. Paint with one by
passing its `stroke` settings to paint.stroke (plus your points and colour).
"""
from __future__ import annotations

from rostrum_core.errors import RostrumError, codes
from rostrum_core.mcp import Reply, Tools

from .. import brushes

tools = Tools()


@tools.tool("run_brush", {"properties": {
    "action": {"type": "string", "enum": ["list", "save", "rename", "delete"],
               "description": "list: My brushes with their settings. save: keep `settings` as a brush named `name`. "
                              "rename: give brush `id` the name `name`. delete: remove brush `id`."},
    "id": {"type": "string", "description": "A saved brush's id (rename, delete)."},
    "name": {"type": "string", "description": "The brush's name (save, rename)."},
    "settings": {"type": "object", "description": "save: brush settings as paint.stroke takes them (brush, size, "
                 "hardness, opacity, texture, paper …); colour and seed are never kept. A loaded tip or paper is named "
                 "by its project item id (run_paint_picture)."}},
    "required": ["action"]})
def run_brush(ctx, args):
    """List, save, rename or delete the project's saved brushes (My brushes). Each listed brush has `stroke`: the
    settings to pass to paint.stroke to paint with it."""
    folder, act = ctx.app.folder, args["action"]
    if not folder:
        raise RostrumError(codes.BAD_ARGUMENT, ctx.tool, "My brushes", "needs a project folder: none is open")
    for need in {"save": ("name", "settings"), "rename": ("id", "name"), "delete": ("id",)}.get(act, ()):
        if not args.get(need):
            raise RostrumError(codes.BAD_ARGUMENT, ctx.tool, f"action {act}", f"needs `{need}`")
    if act == "save":
        b = brushes.save(folder, args["name"], args["settings"])
        return Reply(f'Saved "{b["name"]}" in My brushes: {b["id"]}.', {"brush": {**b, "stroke": brushes.for_stroke(b["settings"])}})
    if act == "rename":
        brushes.rename(folder, args["id"], args["name"])
        return Reply(f'Renamed {args["id"]} to "{args["name"]}".', {})
    if act == "delete":
        brushes.remove(folder, args["id"])
        return Reply(f'Deleted {args["id"]} from My brushes.', {})
    every = [{**b, "stroke": brushes.for_stroke(b["settings"])} for b in brushes.saved(folder)]
    names = ", ".join(f'"{b["name"]}" ({b["id"]})' for b in every) or "none yet"
    return Reply(f"My brushes: {names}.", {"brushes": every})
