"""My brushes for agents (rostrum2d/brushes.py; the screen's brush panel shows the same ones under My brushes):

    run_brush {action: list | save | use | duplicate | rename | delete | keep | drop, …}

A saved brush lives in the project, in the person's own library (kept across projects), or in both. Paint with one
by `use` (it copies a loaded tip or paper into the project if it must) and passing its `stroke` settings to
paint.stroke (plus your points and colour).
"""
from __future__ import annotations

from rostrum_core.errors import RostrumError, codes
from rostrum_core.mcp import Reply, Tools

from .. import brushes

tools = Tools()
NEEDS = {"save": ("name", "settings"), "rename": ("id", "name"), "keep": ("id", "place"), "drop": ("id", "place")}


def _out(b):
    return {**b, "stroke": brushes.for_stroke(b["settings"])}


@tools.tool("run_brush", {"properties": {
    "action": {"type": "string", "enum": ["list", "save", "use", "duplicate", "rename", "delete", "keep", "drop"],
               "description": "list: My brushes with their settings and where each is kept. save: keep `settings` as a "
                              "new brush named `name`. use: brush `id`, ready to paint in this project. duplicate: a new "
                              "brush with brush `id`'s settings. rename: give brush `id` the name `name`. delete: remove "
                              "brush `id` everywhere. keep / drop: add brush `id` to / take it out of `place`."},
    "id": {"type": "string", "description": "A saved brush's id."},
    "name": {"type": "string", "description": "The brush's name (save, rename)."},
    "place": {"type": "string", "enum": list(brushes.PLACES),
              "description": "keep / drop: the project, or the person's own library (kept across projects)."},
    "where": {"type": "array", "items": {"type": "string", "enum": list(brushes.PLACES)},
              "description": "save: where to keep it (default both; the library alone when no project is open)."},
    "settings": {"type": "object", "description": "save: brush settings as paint.stroke takes them (brush, size, "
                 "hardness, opacity, texture, paper …); colour and seed are never kept. A loaded tip or paper is named "
                 "by its project item id (run_import (what: paint_picture)); keeping the brush in the library copies that picture too."}},
    "required": ["action"]})
def run_brush(ctx, args):
    """List, save, use, duplicate, rename, delete, keep or drop saved brushes (My brushes: the project's and the
    person's own library). Each listed brush has `where` and `stroke`: the settings to pass to paint.stroke (or paint.letters, which writes words with it)."""
    folder, act = ctx.app.folder, args["action"]
    for need in NEEDS.get(act, ("id",) if act != "list" else ()):
        if not args.get(need):
            raise RostrumError(codes.BAD_ARGUMENT, ctx.tool, f"action {act}", f"needs `{need}`")
    if act == "save":
        b = brushes.save(folder, args["name"], args["settings"], args.get("where"))
        return Reply(f'Saved "{b["name"]}" in My brushes ({" and ".join(b["where"])}): {b["id"]}.', {"brush": _out(b)})
    if act == "duplicate":
        b = brushes.duplicate(folder, args["id"])
        return Reply(f'Duplicated {args["id"]} as "{b["name"]}": {b["id"]}.', {"brush": _out(b)})
    if act == "use":
        b = brushes.use(folder, args["id"])
        return Reply(f'"{b["name"]}" is ready to paint: pass its `stroke` to paint.stroke.', {"brush": _out(b)})
    if act in ("keep", "drop"):
        (brushes.keep if act == "keep" else brushes.drop)(folder, args["id"], args["place"])
        left = next((b["where"] for b in brushes.saved(folder) if b["id"] == args["id"]), [])
        return Reply(f'{args["id"]} is now kept in: {", ".join(left) or "nowhere (deleted)"}.', {"where": left})
    if act == "rename":
        brushes.rename(folder, args["id"], args["name"])
        return Reply(f'Renamed {args["id"]} to "{args["name"]}".', {})
    if act == "delete":
        brushes.remove(folder, args["id"])
        return Reply(f'Deleted {args["id"]} from My brushes.', {})
    every = [_out(b) for b in brushes.saved(folder)]
    names = ", ".join(f'"{b["name"]}" ({b["id"]}, {"+".join(b["where"])})' for b in every) or "none yet"
    return Reply(f"My brushes: {names}.", {"brushes": every})
