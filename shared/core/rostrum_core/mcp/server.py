"""The MCP server (stdio) on the official MCP Python SDK: every call is checked, run once, and answered in the one reply shape.

    server = build_server(app, tools)      # app: rostrum_core.mcp.App;  tools: the app's own Tools (optional)
    run_stdio(app, tools)                  # blocks; for a script's `if __name__ == "__main__"`
"""
from __future__ import annotations

import base64
import json
import threading
import time
import traceback
from pathlib import Path

import anyio
import mcp_types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from ..errors import RostrumError, codes
from ..who import Who
from . import shared_edit, shared_inspect, shared_markers
from .context import App, Groups, ToolContext
from .guides import URI
from .jobs import InProcessJobs
from .reply import Reply, error_dict
from .tools import Tools

LOG_DIR = Path.home() / ".rostrum" / "logs"
STANDARD_INSTRUCTIONS = "Read inspect_guide topic 'start-here' first. Replies always carry ok + summary; failures say what is accepted."


def _log(text: str) -> str:
    """Write a bug's traceback to a log file and return its path (INTERNAL errors name it)."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    path = LOG_DIR / f"mcp-{time.strftime('%Y%m%d')}.log"
    with path.open("a", encoding="utf-8") as f:
        f.write(f"--- {time.strftime('%H:%M:%S')}\n{text}\n")
    return str(path)


class Runtime:
    """Everything one server needs, kept apart from the SDK so tests can call `call()` directly."""

    def __init__(self, app: App, tools: Tools | None = None, jobs=None, groups: Groups | None = None):
        shared = Tools()
        shared_inspect.register(shared)
        shared_edit.register(shared)
        shared_markers.register(shared)
        self.app, self.tools = app, shared.merged_with(tools) if tools else shared
        self.jobs = jobs or InProcessJobs(log=_log)
        self.groups = groups or Groups(used=lambda: {c.session for d in app.documents.values() for c in d.history.changes})
        self._one_at_a_time = threading.Lock()          # one writer: tools never overlap on the document

    def call(self, name: str, args: dict | None, who: Who) -> tuple[dict, list]:
        """Run one tool. Returns (reply dict, images). A failure is `ok: false`, never an exception."""
        try:
            tool = self.tools.get(name)
            checked = tool.check(args)
            group = self.groups.current(who, (args or {}).get("group"))
            ctx = ToolContext(self.app, who, group, self.jobs, name, self.tools)
            with self._one_at_a_time:
                reply = tool.fn(ctx, checked)
            if not isinstance(reply, Reply):
                raise TypeError(f"tool {name} returned {type(reply).__name__}, not Reply")
            return reply.to_dict(), reply.images
        except RostrumError as e:
            return error_dict(e.within(name) if not e.where.startswith(name) else e), []
        except Exception as e:                           # a bug: loud, with a log, never a silent success
            path = _log(traceback.format_exc())
            err = RostrumError(codes.INTERNAL, name, f"unexpected {type(e).__name__}", f"in Rostrum: {e}", hint=f"Log: {path}")
            return error_dict(err), []


def _content(reply: dict, images: list) -> list:
    blocks = [types.TextContent(type="text", text=json.dumps(reply, ensure_ascii=False, indent=1))]
    for img in images:
        raw = Path(img).read_bytes() if isinstance(img, (str, Path)) else bytes(img)
        blocks.append(types.ImageContent(type="image", data=base64.b64encode(raw).decode(), mime_type="image/png"))
    return blocks


def build_server(app: App, tools: Tools | None = None, runtime: Runtime | None = None) -> Server:
    rt = runtime or Runtime(app, tools)

    async def list_tools(ctx, params):
        return types.ListToolsResult(tools=[types.Tool(name=t.name, description=t.description, input_schema=t.schema) for t in rt.tools.all()])

    async def call_tool(ctx, params):
        info = ctx.session.client_params.client_info if ctx.session.client_params else None
        who = Who.agent(info.name if info and info.name else "unknown-agent")
        reply, images = await anyio.to_thread.run_sync(rt.call, params.name, params.arguments, who)
        return types.CallToolResult(content=_content(reply, images), structured_content=reply, is_error=not reply["ok"])

    async def list_resources(ctx, params):
        g = app.guides
        return types.ListResourcesResult(resources=[types.Resource(uri=URI + t, name=t, description=g.title(t), mime_type="text/markdown") for t in g.topics()])

    async def read_resource(ctx, params):
        topic = params.uri.removeprefix(URI) if params.uri.startswith(URI) else None
        if topic is None:
            raise RostrumError(codes.NOT_FOUND, "resources/read", f'"{params.uri}"', "is not a Rostrum resource", [URI + t for t in app.guides.topics()])
        return types.ReadResourceResult(contents=[types.TextResourceContents(uri=params.uri, mime_type="text/markdown", text=app.guides.get(topic))])

    server = Server(app.name, version=app.version, instructions=f"{app.instructions}\n\n{STANDARD_INSTRUCTIONS}".strip(),
                    on_list_tools=list_tools, on_call_tool=call_tool, on_list_resources=list_resources, on_read_resource=read_resource)
    server.runtime = rt
    return server


async def serve_stdio(app: App, tools: Tools | None = None):
    server = build_server(app, tools)
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


def run_stdio(app: App, tools: Tools | None = None):
    anyio.run(serve_stdio, app, tools)
