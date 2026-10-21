"""rostrum-toy: a tiny MCP server over the toy document kind. Shows what an app adds on top of rostrum_core.mcp.

Run (stdio): python shared/mcp/demo/toy_server.py, with the worktree's .venv python.
The script layer here (a builder: rect("logo", x=400)) is the *app's* job; core only merges the tree it makes.
"""
from __future__ import annotations

from rostrum_core import toy
from rostrum_core.errors import RostrumError, codes
from rostrum_core.mcp import App, Reply, Tools, run_stdio

TOY_INSTRUCTIONS = "rostrum-toy edits a small toy document (camera, light, rects, texts). Start with inspect_operations."


class Builder:
    """What a script sees: one function per item type, each returns nothing and adds an item to the tree in order."""

    def __init__(self):
        self.layers: list[dict] = []

    def add(self, kind: str, id: str, **fields):
        if any(i["id"] == id for i in self.layers):
            raise ValueError(f'id "{id}" is used twice in the script')
        known = [p.name for p in toy.FIELDS[kind]]
        bad = [k for k in fields if k not in known and k != "name"]
        if bad:
            raise ValueError(f'{kind} has no field "{bad[0]}"; it has: {", ".join(known)}')
        self.layers.append({"id": id, "type": kind, "name": toy.LABELS[kind], **toy.DEFAULTS[kind], **fields})

    def tree(self) -> dict:
        return {"id": "root", "type": "doc", "layers": self.layers}


def run_source(source: str, name: str) -> dict:
    """The toy's script layer: Python source -> output tree. A script error is a loud BAD_ARGUMENT, nothing is merged."""
    b = Builder()
    scope = {k: (lambda id, _k=k, **f: b.add(_k, id, **f)) for k in ("rect", "text", "camera", "light")}
    try:
        exec(compile(source, name, "exec"), {"__builtins__": {"range": range, "len": len, "min": min, "max": max, "abs": abs}, **scope})
    except Exception as e:
        raise RostrumError(codes.BAD_ARGUMENT, "", f'script "{name}"', f"failed: {type(e).__name__}: {e}",
                           ["rect(id, **fields)", "text(id, **fields)", "camera(id, **fields)", "light(id, **fields)"]) from e
    return b.tree()


toy_tools = Tools()


@toy_tools.tool("look_summary", {"properties": {"item": {"type": "string"}}})
def look_summary(ctx, args):
    """A text picture of the toy document: its items in order with their main values."""
    doc = ctx.document(args.get("item"))
    rows = [f'{i["id"]} ({i["type"]}): ' + ", ".join(f"{k}={v}" for k, v in i.items() if k not in ("id", "type")) for i in doc.items() if i["id"] != "root"]
    return Reply(f"{len(rows)} items.", {"items": rows})


def make_app() -> App:
    return App("rostrum-toy", {"toy_1": toy.sample()}, run_source=run_source, instructions=TOY_INSTRUCTIONS)


if __name__ == "__main__":
    run_stdio(make_app(), toy_tools)
