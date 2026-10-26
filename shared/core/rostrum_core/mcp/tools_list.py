"""`inspect_tools`: the server lists its own tools, read from the registrations (CONVENTIONS § 10). Nothing is written by hand."""
from __future__ import annotations

import re

from ..errors import RostrumError
from .reply import Reply
from .tools import VERBS, Tool, Tools


def purpose(tool: Tool) -> str:
    """The first sentence of the tool's description, on one line."""
    first = " ".join(tool.description.split("\n\n")[0].split())
    return re.split(r"(?<=[.!?])\s", first, maxsplit=1)[0]


def _args(tool: Tool) -> list[dict]:
    props, required = tool.schema.get("properties", {}), set(tool.schema.get("required", []))
    return [{"name": k, "required": k in required, "type": v.get("type") or ("enum" if "enum" in v else "any"),
             **({"accepted": v["enum"]} if "enum" in v else {}), **({"description": v["description"]} if "description" in v else {})}
            for k, v in props.items()]


def _origin(tool: Tool) -> dict:
    return {} if tool.origin == "builtin" or tool.origin.startswith("builtin:") else {"origin": tool.origin}


def register(tools: Tools):
    schema = {"properties": {
        "verb": {"type": "string", "description": f"Only the tools of this verb: {', '.join(VERBS)}."},
        "name": {"type": "string", "description": "One tool, for its full description and argument names."}}}

    @tools.tool("inspect_tools", schema)
    def inspect_tools(ctx, args):
        """This server's tools, grouped by verb, each with a one-line purpose; with name, one tool's full description and arguments."""
        mine = {t.name: t for t in ctx.tools.all()}
        if "name" in args:
            if args["name"] not in mine:
                if args["name"] in ctx.tools._renamed:
                    ctx.tools.get(args["name"])            # an old name: the error names the new tool and its argument
                raise RostrumError.not_found("", "tool", args["name"], mine, "this server")
            t = mine[args["name"]]
            names = ", ".join(a["name"] + ("*" if a["required"] else "") for a in _args(t)) or "none"
            return Reply(f"{t.name}: {purpose(t)} Arguments (* required): {names}.",
                         {"tool": {"name": t.name, "verb": t.verb, "description": t.description, "arguments": _args(t),
                                  **_origin(t)}})   # origin only for a plugin's tool: built-in replies keep their size
        if "verb" in args and args["verb"] not in VERBS:
            raise RostrumError.not_found("", "verb", args["verb"], VERBS, "the verbs")
        verbs = [args["verb"]] if "verb" in args else list(VERBS)
        groups = {v: [{"name": t.name, "purpose": purpose(t), **_origin(t)} for t in mine.values() if t.verb == v] for v in verbs}
        counts = ", ".join(f"{v} {len(g)}" for v, g in groups.items())
        listing = "\n".join(f"{v}: " + "; ".join(f'{t["name"]} ({t["purpose"]})' for t in g) for v, g in groups.items() if g)
        return Reply(f"{sum(map(len, groups.values()))} tools ({counts}). Ask with name for one tool's arguments.\n{listing}", {"verbs": groups})
